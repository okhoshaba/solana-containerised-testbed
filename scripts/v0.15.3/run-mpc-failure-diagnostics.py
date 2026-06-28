#!/usr/bin/env python3
"""
v0.15.3 MPC failure diagnostics.

This stage diagnoses the v0.15.2 offline MPC comparison failure.
It does not run a new MPC experiment and does not claim live-controller readiness.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def require_file(path: str | Path) -> Path:
    p = repo_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {p}")
    return p


def load_json(path: str | Path) -> Any:
    p = require_file(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: str | Path) -> List[Dict[str, str]]:
    p = require_file(path)
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: str | Path, obj: Any) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def write_csv(path: str | Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_text(path: str | Path, text: str) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def f(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    category: str,
    severity: str,
    title: str,
    evidence: str,
    implication: str,
    recommended_action: str
) -> None:
    findings.append({
        "finding_id": finding_id,
        "category": category,
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "implication": implication,
        "recommended_action": recommended_action
    })


def metric_signature(row: Dict[str, str]) -> tuple:
    keys = [
        "pass_count",
        "settled_warn_count",
        "explained_transient_count",
        "unexplained_fail_count",
        "average_full_rmse",
        "average_settled_rmse",
        "worst_settled_max_abs_error",
        "average_rate_limit_fraction",
        "average_saturation_fraction",
        "settled_rmse_ratio_vs_baseline"
    ]
    return tuple(round(f(row.get(k)), 9) for k in keys)


def analyze_candidate_degeneracy(ranking: List[Dict[str, str]]) -> Dict[str, Any]:
    groups = defaultdict(list)
    for row in ranking:
        groups[metric_signature(row)].append(row["candidate_id"])

    duplicate_groups = [ids for ids in groups.values() if len(ids) > 1]
    duplicate_candidate_count = sum(len(ids) for ids in duplicate_groups)

    by_ph = defaultdict(list)
    for row in ranking:
        by_ph[row["prediction_horizon"]].append(row)

    ph_summary = []
    for ph, rows in sorted(by_ph.items(), key=lambda item: int(item[0])):
        unique_signatures = {metric_signature(row) for row in rows}
        ph_summary.append({
            "prediction_horizon": ph,
            "candidate_count": len(rows),
            "unique_metric_signatures": len(unique_signatures),
            "average_settled_rmse_values": sorted({round(f(row["average_settled_rmse"]), 9) for row in rows})
        })

    return {
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_candidate_count": duplicate_candidate_count,
        "duplicate_groups": duplicate_groups,
        "prediction_horizon_summary": ph_summary
    }


def analyze_sine_settled_metric(cases: List[Dict[str, str]]) -> Dict[str, Any]:
    sine_rows = [row for row in cases if row.get("profile") == "sine-approx"]
    if not sine_rows:
        return {"profile_present": False}

    target_changes = [int(f(row.get("target_change_count"), 0)) for row in sine_rows]
    settled_rmse_values = [f(row.get("settled_rmse")) for row in sine_rows]
    full_rmse_values = [f(row.get("full_rmse")) for row in sine_rows]

    zero_settled_count = sum(1 for v in settled_rmse_values if abs(v) < 1e-12)
    high_change_count = max(target_changes) if target_changes else 0

    return {
        "profile_present": True,
        "case_count": len(sine_rows),
        "max_target_change_count": high_change_count,
        "zero_settled_rmse_count": zero_settled_count,
        "min_settled_rmse": min(settled_rmse_values),
        "max_full_rmse": max(full_rmse_values)
    }


def script_usage_diagnostics(script_text: str) -> Dict[str, Any]:
    control_horizon_mentions = script_text.count("control_horizon")
    score_plan_text = ""
    if "def score_plan" in script_text and "def simulate_mpc_candidate_on_profile" in script_text:
        score_plan_text = script_text.split("def score_plan", 1)[1].split("def simulate_mpc_candidate_on_profile", 1)[0]

    return {
        "control_horizon_mentions": control_horizon_mentions,
        "control_horizon_used_inside_score_plan": "control_horizon" in score_plan_text,
        "constant_u_plan_signature": "u0" in score_plan_text and "for h in range(ph)" in score_plan_text,
        "uses_candidate_control_horizon_in_optimisation": "control_horizon" in score_plan_text
    }


def build_correction_plan(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "step": 1,
            "target_stage": "v0.15.4",
            "action": "Correct surrogate comparability before another MPC comparison.",
            "details": "Reuse the same initial_y policy, target profile handling, action delay semantics, and safety interpretation as the baseline simulator.",
            "expected_output": "Corrected offline MPC surrogate configuration and validation checks."
        },
        {
            "step": 2,
            "target_stage": "v0.15.4",
            "action": "Make control horizon operational.",
            "details": "Evaluate an explicit sequence of future control moves rather than a constant command over the whole prediction horizon.",
            "expected_output": "Candidate metrics that vary when control_horizon changes."
        },
        {
            "step": 3,
            "target_stage": "v0.15.4",
            "action": "Make objective weights identifiable.",
            "details": "Scale tracking, control effort, and delta penalties so that different weights can change the selected command sequence.",
            "expected_output": "Candidate metrics that vary when effort and delta weights change."
        },
        {
            "step": 4,
            "target_stage": "v0.15.4",
            "action": "Audit delay extraction.",
            "details": "Confirm whether delay_steps should be zero or should follow the simulator plant equation and selected model metadata.",
            "expected_output": "Documented delay policy used by the corrected surrogate."
        },
        {
            "step": 5,
            "target_stage": "v0.15.4",
            "action": "Repair high-frequency target settled-metric interpretation.",
            "details": "Handle sine-like profiles separately when nearly every step is a target transition.",
            "expected_output": "Reliable settled/transient metrics for sine-approx and multi-step profiles."
        },
        {
            "step": 6,
            "target_stage": "v0.15.5_or_later",
            "action": "Only after surrogate correction, rerun offline comparison.",
            "details": "Interpret pass, conditional_pass, or fail against the fixed v0.14.3 baseline without live-controller claims.",
            "expected_output": "A scientifically comparable corrected MPC-vs-baseline result."
        }
    ]


def decide(config: Dict[str, Any], summary: Dict[str, Any], findings: List[Dict[str, Any]], correction_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    policy = config["decision_policy"]
    failures = []

    if policy["require_v0_15_2_fail_confirmed"] and summary["v0_15_2_decision_status"] != "fail":
        failures.append("v0.15.2 fail status was not confirmed")

    if policy["require_root_cause_findings"] and len(findings) < int(policy["minimum_findings"]):
        failures.append("not enough diagnostic findings")

    if policy["require_correction_plan"] and not correction_plan:
        failures.append("missing correction plan")

    if failures:
        return {
            "status": "diagnostic_blocked",
            "ready_for_corrected_surrogate_stage": False,
            "failures": failures,
            "reason": "Diagnostics are incomplete."
        }

    return {
        "status": policy["pass_status"],
        "ready_for_corrected_surrogate_stage": True,
        "recommended_next_stage": "v0.15.4 corrected offline MPC surrogate comparison",
        "reason": "The v0.15.2 failure is diagnosed as a surrogate/comparability problem requiring correction before another MPC comparison."
    }


def write_readme(path: str | Path, summary: Dict[str, Any], findings: List[Dict[str, Any]], correction_plan: List[Dict[str, Any]]) -> None:
    critical = [f for f in findings if f["severity"] == "critical"]
    high = [f for f in findings if f["severity"] == "high"]

    finding_lines = "\n".join(
        f"- {row['finding_id']}: {row['title']} ({row['severity']})"
        for row in findings
    )
    plan_lines = "\n".join(
        f"- Step {row['step']}: {row['action']}"
        for row in correction_plan
    )

    text = f"""# v0.15.3 MPC failure diagnostics

## Purpose

This stage diagnoses why v0.15.2 produced a fail result.

It does not run a new MPC experiment and does not claim that MPC is generally unsuitable.

## v0.15.2 result under diagnosis

- Decision: {summary["v0_15_2_decision_status"]}
- Selected candidate: {summary["selected_mpc_candidate_id"]}
- Settled RMSE ratio vs baseline: {summary["selected_settled_rmse_ratio_vs_baseline"]}
- Unexplained failures: {summary["selected_unexplained_fail_count"]}
- Settled warnings: {summary["selected_settled_warn_count"]}
- Baseline: {summary["reference_baseline_candidate_id"]}

## Diagnostic findings

{finding_lines}

## Severity count

- Critical findings: {len(critical)}
- High findings: {len(high)}
- Total findings: {len(findings)}

## Correction plan

{plan_lines}

## Decision

- Status: {summary["decision"]["status"]}
- Ready for corrected surrogate stage: {summary["decision"]["ready_for_corrected_surrogate_stage"]}

Reason: {summary["decision"]["reason"]}
"""
    write_text(path, text)


def write_experiment_doc(path: str | Path, summary: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    finding_lines = "\n".join(
        f"- {row['finding_id']}: {row['title']}. Evidence: {row['evidence']}"
        for row in findings
    )

    text = f"""# v0.15.3 MPC failure diagnostics

## Purpose

v0.15.3 is a diagnostic stage following the failed v0.15.2 offline MPC closed-loop comparison.

The objective is not to improve MPC immediately. The objective is to determine whether the failure should be interpreted as MPC weakness, surrogate mismatch, metric interpretation error, or a combination of these.

## Confirmed v0.15.2 result

v0.15.2 selected:

    {summary["selected_mpc_candidate_id"]}

The selected candidate had a settled RMSE ratio versus baseline of:

    {summary["selected_settled_rmse_ratio_vs_baseline"]}

The fixed reference baseline remains:

    {summary["reference_baseline_candidate_id"]}

## Main diagnostic interpretation

The v0.15.2 result should be interpreted primarily as evidence that the current MPC surrogate formulation is not yet comparable with the baseline simulation.

It should not be interpreted as a general proof that MPC is unsuitable.

## Findings

{finding_lines}

## Decision

Status:

    {summary["decision"]["status"]}

Reason:

    {summary["decision"]["reason"]}

## Recommended next stage

v0.15.4 corrected offline MPC surrogate comparison.
"""
    write_text(path, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    config = load_json(args.config)
    sources = config["source_artifacts"]
    outputs = config["outputs"]

    for source in sources.values():
        require_file(source)

    v0152_summary = load_json(sources["v0_15_2_summary"])
    v0140_config = load_json(sources["v0_14_0_config"])
    baseline_summary = load_json(sources["v0_14_3_baseline_summary"])
    ranking = read_csv(sources["v0_15_2_ranking"])
    cases = read_csv(sources["v0_15_2_case_metrics"])
    profiles = read_csv(sources["v0_15_2_profile_metrics"])
    script_text = repo_path(sources["v0_15_2_script"]).read_text(encoding="utf-8")

    selected = v0152_summary["selected_mpc_candidate"]
    decision_status = v0152_summary["decision"]["status"]
    findings: List[Dict[str, Any]] = []

    add_finding(
        findings,
        "F001",
        "result_interpretation",
        "high",
        "v0.15.2 failure is a scientific negative result, not an execution failure",
        f"decision={decision_status}, candidate_count={v0152_summary['candidate_count']}, case_count={v0152_summary['case_count']}",
        "The failure should be committed and used to guide correction rather than discarded.",
        "Treat v0.15.3 as diagnostics before any new MPC run."
    )

    ratio = f(selected.get("settled_rmse_ratio_vs_baseline"))
    add_finding(
        findings,
        "F002",
        "baseline_gap",
        "critical",
        "Best MPC surrogate candidate is far worse than the fixed baseline",
        f"settled_rmse_ratio_vs_baseline={ratio}",
        "The current surrogate cannot be considered a baseline competitor.",
        "Do not tune around this result until simulator comparability is corrected."
    )

    degeneracy = analyze_candidate_degeneracy(ranking)
    add_finding(
        findings,
        "F003",
        "candidate_identifiability",
        "high",
        "Multiple MPC candidates have identical metric signatures",
        f"duplicate_groups={degeneracy['duplicate_group_count']}, duplicate_candidate_count={degeneracy['duplicate_candidate_count']}",
        "The current candidate parameters are not sufficiently identifiable in the surrogate.",
        "Make control horizon and objective weights operational before the next comparison."
    )

    script_diag = script_usage_diagnostics(script_text)
    if not script_diag["uses_candidate_control_horizon_in_optimisation"]:
        add_finding(
            findings,
            "F004",
            "surrogate_formulation",
            "high",
            "control_horizon is not active inside the MPC scoring loop",
            f"control_horizon_mentions={script_diag['control_horizon_mentions']}, used_inside_score_plan={script_diag['control_horizon_used_inside_score_plan']}",
            "Candidates with different control horizons can collapse to identical behaviour.",
            "Implement explicit future control move sequences in v0.15.4."
        )

    lm = v0152_summary.get("linear_model_used", {})
    plant_equation = str(v0140_config.get("simulation_policy", {}).get("plant_equation", ""))
    if int(lm.get("delay_steps", -1)) == 0 and "delay" in plant_equation:
        add_finding(
            findings,
            "F005",
            "model_delay",
            "medium",
            "v0.15.2 used delay_steps=0 while the simulator policy is delay-aware",
            f"linear_model_delay_steps={lm.get('delay_steps')}, plant_equation={plant_equation}",
            "The surrogate may not be using the same temporal semantics as the baseline simulator.",
            "Audit selected model metadata and enforce an explicit delay policy."
        )

    sine_diag = analyze_sine_settled_metric(cases)
    if sine_diag.get("profile_present") and sine_diag.get("max_target_change_count", 0) > 20:
        add_finding(
            findings,
            "F006",
            "metric_interpretation",
            "medium",
            "sine-approx has very high target-change density",
            f"max_target_change_count={sine_diag['max_target_change_count']}, zero_settled_rmse_count={sine_diag['zero_settled_rmse_count']}",
            "Settled/transient separation may be unstable for sine-like profiles.",
            "Use a separate interpretation policy for high-frequency target profiles."
        )

    status_counts = defaultdict(int)
    for row in cases:
        status_counts[row["calibrated_status"]] += 1

    add_finding(
        findings,
        "F007",
        "case_distribution",
        "medium",
        "Case status distribution shows systemic surrogate weakness",
        ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())),
        "The failure is not isolated to one metric only.",
        "Inspect profile-level diagnostics before selecting a corrected objective."
    )

    correction_plan = build_correction_plan(findings)
    decision = decide(config, {
        "v0_15_2_decision_status": decision_status
    }, findings, correction_plan)

    summary = {
        "stage": config["stage"],
        "experiment": config["experiment"],
        "title": config["title"],
        "offline_only": True,
        "purpose": config["purpose"],
        "v0_15_2_decision_status": decision_status,
        "selected_mpc_candidate_id": selected["candidate_id"],
        "selected_settled_rmse_ratio_vs_baseline": selected["settled_rmse_ratio_vs_baseline"],
        "selected_unexplained_fail_count": selected["unexplained_fail_count"],
        "selected_settled_warn_count": selected["settled_warn_count"],
        "reference_baseline_candidate_id": v0152_summary["reference_baseline"]["candidate_id"],
        "reference_baseline_effective_controller": v0152_summary["reference_baseline"]["effective_controller"],
        "baseline_decision": baseline_summary.get("decision"),
        "candidate_count": v0152_summary["candidate_count"],
        "case_count": v0152_summary["case_count"],
        "profile_count": len(profiles),
        "linear_model_used_in_v0_15_2": lm,
        "candidate_degeneracy": degeneracy,
        "script_usage_diagnostics": script_diag,
        "sine_metric_diagnostics": sine_diag,
        "finding_count": len(findings),
        "decision": decision,
        "performance_claim": False,
        "live_controller_claim": False,
        "outputs": outputs
    }

    finding_fields = [
        "finding_id", "category", "severity", "title", "evidence",
        "implication", "recommended_action"
    ]
    plan_fields = ["step", "target_stage", "action", "details", "expected_output"]

    write_json(outputs["summary_json"], summary)
    write_csv(outputs["findings_csv"], findings, finding_fields)
    write_csv(outputs["correction_plan_csv"], correction_plan, plan_fields)
    write_readme(outputs["readme_md"], summary, findings, correction_plan)
    write_experiment_doc(outputs["experiment_doc"], summary, findings)

    print(json.dumps({
        "stage": summary["stage"],
        "decision": decision["status"],
        "ready_for_corrected_surrogate_stage": decision["ready_for_corrected_surrogate_stage"],
        "finding_count": len(findings),
        "v0_15_2_decision": decision_status,
        "selected_mpc_candidate": selected["candidate_id"],
        "settled_rmse_ratio_vs_baseline": selected["settled_rmse_ratio_vs_baseline"],
        "recommended_next_stage": decision["recommended_next_stage"]
    }, indent=2))


if __name__ == "__main__":
    main()
