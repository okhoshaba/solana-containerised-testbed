#!/usr/bin/env python3
"""
v0.15.1 offline MPC prototype skeleton.

This stage creates deterministic MPC candidate specifications and validates
that the project is ready for a future offline closed-loop MPC simulation.
It does not run MPC optimisation and does not claim performance.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def load_json(path: str | Path) -> Any:
    p = repo_path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, obj: Any) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def write_text(path: str | Path, text: str) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def require_file(path: str | Path) -> Path:
    p = repo_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {p}")
    return p


def validate_v0150(summary: Dict[str, Any]) -> Dict[str, Any]:
    decision = summary.get("decision", {})
    checks = {
        "stage_is_v0_15_0": summary.get("stage") == "v0.15.0",
        "experiment_is_mpc_preparation": summary.get("experiment") == "mpc-controller-preparation",
        "ready_for_offline_mpc_prototype": decision.get("ready_for_offline_mpc_prototype") is True,
        "decision_status_ready": decision.get("status") == "ready_for_offline_mpc_prototype"
    }
    return {"checks": checks, "valid": all(checks.values())}


def validate_baseline(summary: Dict[str, Any], expected_candidate: str) -> Dict[str, Any]:
    selected = summary.get("selected_candidate", {})
    decision = summary.get("decision", {})
    checks = {
        "stage_is_v0_14_3": summary.get("stage") == "v0.14.3",
        "candidate_count_is_one": summary.get("candidate_count") == 1,
        "candidate_matches": selected.get("candidate_id") == expected_candidate,
        "effective_controller_is_p_only": selected.get("effective_controller") == "p_only",
        "accepted_for_mpc_reference": decision.get("accepted_as_reference_baseline_for_mpc") is True,
        "decision_status_pass": decision.get("status") == "pass"
    }
    return {
        "expected_candidate_id": expected_candidate,
        "observed_candidate_id": selected.get("candidate_id"),
        "effective_controller": selected.get("effective_controller"),
        "checks": checks,
        "valid": all(checks.values())
    }


def generate_candidates(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    policy = config["mpc_skeleton_policy"]
    rows: List[Dict[str, Any]] = []
    idx = 1

    for prediction_horizon in policy["prediction_horizons"]:
        for control_horizon in policy["control_horizons"]:
            if policy.get("require_control_horizon_lte_prediction_horizon", True):
                if control_horizon > prediction_horizon:
                    continue
            for tracking_weight in policy["tracking_error_weights"]:
                for effort_weight in policy["control_effort_weights"]:
                    for delta_weight in policy["control_delta_weights"]:
                        for soft_weight in policy["soft_constraint_weights"]:
                            candidate_id = (
                                "mpc_skeleton_"
                                f"ph{prediction_horizon:02d}_"
                                f"ch{control_horizon:02d}_"
                                f"q{tracking_weight:.3f}_"
                                f"r{effort_weight:.3f}_"
                                f"du{delta_weight:.3f}_"
                                f"sc{soft_weight:.1f}"
                            )
                            rows.append({
                                "rank": idx,
                                "candidate_id": candidate_id,
                                "prediction_horizon": prediction_horizon,
                                "control_horizon": control_horizon,
                                "tracking_error_weight": tracking_weight,
                                "control_effort_weight": effort_weight,
                                "control_delta_weight": delta_weight,
                                "soft_constraint_weight": soft_weight,
                                "objective_placeholder": True,
                                "constraint_placeholder": True,
                                "optimizer_placeholder": True,
                                "closed_loop_simulated": False,
                                "performance_claim": False
                            })
                            idx += 1

    return rows


def write_csv(path: str | Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("No rows to write")

    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def decide(config: Dict[str, Any], v0150_validation: Dict[str, Any], baseline_validation: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    policy = config["decision_policy"]
    failures = []

    if policy.get("require_v0_15_0_ready", True) and not v0150_validation["valid"]:
        failures.append("v0.15.0 preparation summary is not ready")

    if policy.get("require_v0_14_3_baseline_valid", True) and not baseline_validation["valid"]:
        failures.append("v0.14.3 baseline is not valid for MPC reference")

    if len(candidates) < int(policy.get("minimum_candidate_count", 1)):
        failures.append("not enough MPC skeleton candidates generated")

    if policy.get("require_no_performance_claim", True):
        claimed = [c for c in candidates if c.get("performance_claim") is not False]
        if claimed:
            failures.append("one or more candidates contain a performance claim")

    if failures:
        return {
            "status": "blocked",
            "ready_for_offline_mpc_simulation": False,
            "reason": "The MPC prototype skeleton is not ready for offline simulation.",
            "failures": failures
        }

    return {
        "status": policy["pass_status"],
        "ready_for_offline_mpc_simulation": True,
        "reason": "The MPC prototype skeleton defines deterministic candidates, placeholders, constraints, and a fixed reference baseline for the next offline simulation stage."
    }


def write_readme(path: str | Path, summary: Dict[str, Any]) -> None:
    config = summary["config"]
    baseline = config["reference_baseline"]
    decision = summary["decision"]

    text = f"""# v0.15.1 offline MPC prototype skeleton

## Purpose

This stage creates a minimal offline MPC prototype skeleton.

It does not run closed-loop MPC optimisation and does not claim that MPC is better than the v0.14.3 baseline.

## Reference baseline

- Source stage: {baseline["source_stage"]}
- Candidate: {baseline["candidate_id"]}
- Effective controller: {baseline["effective_controller"]}
- Role: {baseline["role"]}

Future MPC simulation must compare against this fixed P-only baseline.

## Skeleton components

- Problem loader: {config["prototype_components"]["problem_loader"]}
- Baseline loader: {config["prototype_components"]["baseline_loader"]}
- Candidate spec generator: {config["prototype_components"]["candidate_spec_generator"]}
- Objective placeholder: {config["prototype_components"]["objective_placeholder"]}
- Constraint placeholder: {config["prototype_components"]["constraint_placeholder"]}
- Optimizer placeholder: {config["prototype_components"]["optimizer_placeholder"]}
- Closed-loop simulation: {config["prototype_components"]["closed_loop_simulation"]}
- Performance claim: {config["prototype_components"]["performance_claim"]}

## Candidate grid

- Candidate generation mode: {config["mpc_skeleton_policy"]["candidate_generation_mode"]}
- Candidate count: {summary["candidate_count"]}
- Prediction horizons: {config["mpc_skeleton_policy"]["prediction_horizons"]}
- Control horizons: {config["mpc_skeleton_policy"]["control_horizons"]}
- Tracking error weights: {config["mpc_skeleton_policy"]["tracking_error_weights"]}
- Control effort weights: {config["mpc_skeleton_policy"]["control_effort_weights"]}
- Control delta weights: {config["mpc_skeleton_policy"]["control_delta_weights"]}
- Soft constraint weights: {config["mpc_skeleton_policy"]["soft_constraint_weights"]}

## Decision

- Status: {decision["status"]}
- Ready for offline MPC simulation: {decision["ready_for_offline_mpc_simulation"]}

Reason: {decision["reason"]}

## Next step

Proceed to v0.15.2 offline MPC closed-loop simulation comparison.
"""
    write_text(path, text)


def write_experiment_doc(path: str | Path, summary: Dict[str, Any]) -> None:
    config = summary["config"]
    decision = summary["decision"]

    text = f"""# v0.15.1 offline MPC prototype skeleton

## Purpose

v0.15.1 creates the first offline MPC prototype skeleton for the Solana Containerised Testbed throughput-control research line.

The stage is deliberately architectural. It defines the candidate structure and simulation interface, but it does not yet perform MPC closed-loop optimisation.

## Why this stage exists

v0.15.0 established the MPC problem formulation and accepted v0.14.3 as the fixed reference baseline.

v0.15.1 converts that formulation into a reproducible skeleton with deterministic MPC candidate specifications.

## Non-goals

This stage does not:

- run a live controller
- perform full MPC optimisation
- claim MPC superiority
- replace the v0.14.3 P-only baseline

## Reference baseline

The fixed comparison baseline remains:

    p_kp0.350_ki0.000_kd0.000

This is the P-only baseline validated in v0.14.3.

## Candidate specification

The skeleton generates deterministic MPC candidate specifications from:

- prediction horizon candidates
- control horizon candidates
- tracking error weights
- control effort weights
- control delta weights
- soft constraint weights

Generated candidate count:

    {summary["candidate_count"]}

## Interface to future closed-loop simulation

The generated candidates are not performance results. They are candidate specifications for a future offline MPC closed-loop simulation comparison.

The next stage should use these candidate specifications, the selected recursive plant model, the v0.14.x safety and calibration interpretation, and the fixed v0.14.3 baseline.

## Decision

Status:

    {decision["status"]}

Reason:

    {decision["reason"]}

## Recommended next stage

v0.15.2 offline MPC closed-loop simulation comparison.
"""
    write_text(path, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    config = load_json(args.config)
    sources = config["source_artifacts"]
    outputs = config["outputs"]

    for path in sources.values():
        require_file(path)

    v0150_summary = load_json(sources["v0_15_0_summary_path"])
    baseline_summary = load_json(sources["v0_14_3_baseline_summary_path"])

    v0150_validation = validate_v0150(v0150_summary)
    baseline_validation = validate_baseline(
        baseline_summary,
        config["reference_baseline"]["candidate_id"]
    )

    candidates = generate_candidates(config)
    decision = decide(config, v0150_validation, baseline_validation, candidates)

    summary = {
        "stage": config["stage"],
        "experiment": config["experiment"],
        "title": config["title"],
        "offline_only": True,
        "purpose": config["purpose"],
        "config_path": args.config,
        "config": config,
        "v0_15_0_validation": v0150_validation,
        "baseline_validation": baseline_validation,
        "candidate_count": len(candidates),
        "candidate_generation_mode": config["mpc_skeleton_policy"]["candidate_generation_mode"],
        "closed_loop_simulation_performed": False,
        "performance_claim": False,
        "decision": decision,
        "outputs": outputs
    }

    write_json(outputs["summary_json"], summary)
    write_csv(outputs["candidate_specs_csv"], candidates)
    write_readme(outputs["readme_md"], summary)
    write_experiment_doc(outputs["experiment_doc"], summary)

    print(json.dumps({
        "stage": summary["stage"],
        "decision": decision["status"],
        "ready_for_offline_mpc_simulation": decision["ready_for_offline_mpc_simulation"],
        "candidate_count": len(candidates),
        "reference_baseline": config["reference_baseline"]["candidate_id"],
        "closed_loop_simulation_performed": False,
        "performance_claim": False
    }, indent=2))


if __name__ == "__main__":
    main()
