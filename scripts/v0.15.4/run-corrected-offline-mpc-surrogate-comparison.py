#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def rp(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_json(path: str | Path) -> Any:
    with rp(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with rp(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_json(path: str | Path, obj: Any) -> None:
    p = rp(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    p = rp(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_text(path: str | Path, text: str) -> None:
    p = rp(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def import_script(path: str | Path):
    spec = importlib.util.spec_from_file_location("v0142_sim", str(rp(path)))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ff(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def clip(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def target_at(mod, profile: dict[str, Any], step: int) -> float:
    return float(mod.target_at_step(profile, step))


def eq_cmd(mod, model: dict[str, Any], target: float, safety: dict[str, Any]) -> float:
    try:
        value = float(mod.equilibrium_command(model, target))
    except Exception:
        value = target
    return clip(value, float(safety["action_min"]), float(safety["action_max"]))


def apply_limits(raw_u: float, prev_u: float, safety: dict[str, Any]) -> tuple[float, bool, bool]:
    action_min = float(safety["action_min"])
    action_max = float(safety["action_max"])
    max_step = float(safety["max_step_change"])

    rate_u = clip(raw_u, prev_u - max_step, prev_u + max_step)
    rate_limited = abs(rate_u - raw_u) > 1e-12

    sat_u = clip(rate_u, action_min, action_max)
    saturated = abs(sat_u - rate_u) > 1e-12 or sat_u in (action_min, action_max)

    return sat_u, rate_limited, saturated


def predict(y: float, u: float, lm: dict[str, float]) -> float:
    return lm["c"] + lm["a_y"] * y + lm["b_u"] * u


def target_change_count(mod, profile: dict[str, Any], steps: int) -> int:
    count = 0
    prev = None
    for k in range(steps):
        t = target_at(mod, profile, k)
        if prev is not None and abs(t - prev) > 1e-9:
            count += 1
        prev = t
    return count


def tracking_fraction(candidate: dict[str, Any], cfg: dict[str, Any]) -> float:
    q = ff(candidate["tracking_error_weight"])
    r = ff(candidate["control_effort_weight"])
    du = ff(candidate["control_delta_weight"])
    ch = int(candidate["control_horizon"])
    ph = int(candidate["prediction_horizon"])
    pol = cfg["correction_policy"]

    denom = q + float(pol["control_effort_scale"]) * r + float(pol["control_delta_scale"]) * du + 1e-12
    base = q / denom
    ch_bonus = 0.08 * max(ch - 1, 0)
    ph_penalty = 0.01 * max((ph - 5) / 5.0, 0.0)

    return clip(base + ch_bonus - ph_penalty, 0.05, 1.0)


def metric_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    errors = [float(r["error"]) for r in rows]
    abs_errors = [abs(e) for e in errors]
    return {
        "rmse": math.sqrt(statistics.mean([e * e for e in errors])),
        "mae": statistics.mean(abs_errors),
        "max_abs_error": max(abs_errors),
    }


def transient_steps(changes: list[int], window: int) -> set[int]:
    out = set()
    for change in changes:
        out.update(range(change, change + window))
    return out


def classify(metric: dict[str, float], full: dict[str, float], saturation: float, thresholds: dict[str, Any], high_freq: bool) -> str:
    sat_limit = ff(thresholds.get("maximum_saturation_fraction_for_calibrated_pass"), 0.2)
    warn_rmse = ff(thresholds.get("settled_warn_rmse"), 4.0)
    fail_rmse = ff(thresholds.get("settled_fail_rmse"), 8.0)
    warn_max = ff(thresholds.get("settled_warn_max_abs_error"), 12.0)
    fail_max = ff(thresholds.get("settled_fail_max_abs_error"), 24.0)

    if saturation > sat_limit:
        return "UNEXPLAINED_FAIL"
    if metric["rmse"] > fail_rmse or metric["max_abs_error"] > fail_max:
        return "UNEXPLAINED_FAIL"
    if metric["rmse"] > warn_rmse or metric["max_abs_error"] > warn_max:
        return "HIGH_FREQ_WARN" if high_freq else "SETTLED_WARN"
    if not high_freq and full["max_abs_error"] > warn_max:
        return "EXPLAINED_TRANSIENT"
    return "PASS"


def simulate_case(mod, model, candidate, profile, sim_policy, safety, lm, thresholds, cfg) -> dict[str, Any]:
    steps = int(sim_policy.get("steps_per_profile", 80))
    high_freq = target_change_count(mod, profile, steps) >= int(cfg["correction_policy"]["high_frequency_target_change_threshold"])

    y = float(profile.get("initial_y", target_at(mod, profile, 0)))
    u_prev = eq_cmd(mod, model, target_at(mod, profile, 0), safety)

    delay_steps = int(lm["delay_steps"])
    delay_buffer = [u_prev for _ in range(max(delay_steps, 1))]

    rows = []
    changes = []
    prev_target = None
    alpha = tracking_fraction(candidate, cfg)

    for k in range(steps):
        target = target_at(mod, profile, k)
        if prev_target is not None and abs(target - prev_target) > 1e-9:
            changes.append(k)
        prev_target = target

        u_eq = eq_cmd(mod, model, target, safety)
        raw_u = u_prev + alpha * (u_eq - u_prev)
        u, rate_limited, saturated = apply_limits(raw_u, u_prev, safety)

        plant_u = delay_buffer.pop(0)
        delay_buffer.append(u)

        err = y - target
        rows.append({
            "step": k,
            "target": target,
            "y": y,
            "error": err,
            "u": u,
            "plant_u": plant_u,
            "rate_limited": rate_limited,
            "saturated": saturated,
        })

        y = predict(y, plant_u, lm)
        u_prev = u

    full = metric_rows(rows)
    transient = transient_steps(changes, 5)
    settled_rows = [r for r in rows if int(r["step"]) not in transient] or rows
    settled = metric_rows(settled_rows)

    rate_fraction = sum(1 for r in rows if r["rate_limited"]) / len(rows)
    sat_fraction = sum(1 for r in rows if r["saturated"]) / len(rows)

    comparison_metric = full if high_freq else settled
    status = classify(comparison_metric, full, sat_fraction, thresholds, high_freq)
    errors = [float(r["error"]) for r in rows]

    return {
        "candidate_id": candidate["candidate_id"],
        "prediction_horizon": int(candidate["prediction_horizon"]),
        "control_horizon": int(candidate["control_horizon"]),
        "tracking_error_weight": ff(candidate["tracking_error_weight"]),
        "control_effort_weight": ff(candidate["control_effort_weight"]),
        "control_delta_weight": ff(candidate["control_delta_weight"]),
        "soft_constraint_weight": ff(candidate["soft_constraint_weight"]),
        "profile": profile["name"],
        "calibrated_status": status,
        "interpretation_mode": "high_frequency" if high_freq else "normal_settled",
        "comparison_metric_source": "full_rmse" if high_freq else "settled_rmse",
        "comparison_rmse": comparison_metric["rmse"],
        "full_rmse": full["rmse"],
        "full_mae": full["mae"],
        "full_max_abs_error": full["max_abs_error"],
        "settled_rmse": settled["rmse"],
        "settled_mae": settled["mae"],
        "settled_max_abs_error": settled["max_abs_error"],
        "final_error": errors[-1],
        "final_abs_error": abs(errors[-1]),
        "rate_limit_fraction": rate_fraction,
        "saturation_fraction": sat_fraction,
        "target_change_count": len(changes),
        "tracking_fraction": alpha,
        "closed_loop_simulated": True,
        "performance_claim": False,
    }


def baseline_rmse(mod, baseline_cases, profiles, steps, cfg) -> tuple[float, dict[str, float]]:
    by_profile = {p["name"]: p for p in profiles}
    threshold = int(cfg["correction_policy"]["high_frequency_target_change_threshold"])

    vals = []
    per_profile = {}
    for row in baseline_cases:
        name = row["profile"]
        profile = by_profile.get(name)
        high = bool(profile and target_change_count(mod, profile, steps) >= threshold)
        key = "full_rmse" if high else "settled_rmse"
        val = ff(row.get(key))
        if math.isfinite(val):
            vals.append(val)
            per_profile[name] = val

    return statistics.mean(vals), per_profile


def summarize_candidate(candidate, rows, base_rmse):
    statuses = [r["calibrated_status"] for r in rows]
    avg = lambda key: statistics.mean([float(r[key]) for r in rows])
    warning_count = statuses.count("SETTLED_WARN") + statuses.count("HIGH_FREQ_WARN")
    comp = avg("comparison_rmse")

    return {
        "candidate_id": candidate["candidate_id"],
        "prediction_horizon": int(candidate["prediction_horizon"]),
        "control_horizon": int(candidate["control_horizon"]),
        "tracking_error_weight": ff(candidate["tracking_error_weight"]),
        "control_effort_weight": ff(candidate["control_effort_weight"]),
        "control_delta_weight": ff(candidate["control_delta_weight"]),
        "soft_constraint_weight": ff(candidate["soft_constraint_weight"]),
        "case_count": len(rows),
        "pass_count": statuses.count("PASS"),
        "settled_warn_count": statuses.count("SETTLED_WARN"),
        "high_frequency_warn_count": statuses.count("HIGH_FREQ_WARN"),
        "warning_count": warning_count,
        "explained_transient_count": statuses.count("EXPLAINED_TRANSIENT"),
        "unexplained_fail_count": statuses.count("UNEXPLAINED_FAIL"),
        "average_comparison_rmse": comp,
        "comparison_rmse_ratio_vs_baseline": comp / base_rmse if base_rmse > 0 else float("inf"),
        "average_full_rmse": avg("full_rmse"),
        "average_settled_rmse": avg("settled_rmse"),
        "average_rate_limit_fraction": avg("rate_limit_fraction"),
        "average_saturation_fraction": avg("saturation_fraction"),
        "average_tracking_fraction": avg("tracking_fraction"),
        "closed_loop_simulated": True,
        "performance_claim": False,
    }


def rank_candidates(rows):
    ranked = sorted(rows, key=lambda r: (
        int(r["unexplained_fail_count"]),
        int(r["warning_count"]),
        float(r["comparison_rmse_ratio_vs_baseline"]),
        float(r["average_comparison_rmse"]),
    ))
    for i, row in enumerate(ranked, 1):
        row["rank"] = i
    return ranked


def correction_validation(v0153, lm, ranking, cases):
    def sig(row):
        return (
            round(float(row["average_comparison_rmse"]), 9),
            round(float(row["average_tracking_fraction"]), 9),
            int(row["control_horizon"]),
            float(row["control_effort_weight"]),
        )

    unique = len({sig(r) for r in ranking})
    high_cases = [r for r in cases if r["interpretation_mode"] == "high_frequency"]

    rows = [
        ("C001", "v0.15.3 diagnostic_pass confirmed", v0153["decision"]["status"] == "diagnostic_pass", v0153["decision"]["status"]),
        ("C002", "explicit one-step delay applied", int(lm["delay_steps"]) == 1, str(lm["delay_steps"])),
        ("C003", "candidate metrics identifiable", unique > 3, f"unique_signatures={unique}"),
        ("C004", "control_horizon active", len({float(r["average_tracking_fraction"]) for r in ranking}) > 1, "tracking_fraction_varies"),
        ("C005", "objective weights active", len({float(r["control_effort_weight"]) for r in ranking}) > 1, "control_effort_weight_varies"),
        ("C006", "high-frequency interpretation active", len(high_cases) > 0, f"high_frequency_cases={len(high_cases)}"),
        ("C007", "no live or performance claim emitted", True, "performance_claim=False live_controller_claim=False"),
    ]
    return [
        {"check_id": a, "description": b, "passed": bool(c), "evidence": d}
        for a, b, c, d in rows
    ]


def decide(best, validations, cfg):
    failed = [v["check_id"] for v in validations if not v["passed"]]
    if failed:
        return {
            "status": "blocked",
            "selected_candidate_id": best["candidate_id"],
            "corrected_surrogate_comparable": False,
            "usable_offline_tradeoff_vs_baseline": False,
            "failed_correction_checks": failed,
            "reason": "Correction validation failed, so comparison is not interpretable."
        }

    ratio = float(best["comparison_rmse_ratio_vs_baseline"])
    fails = int(best["unexplained_fail_count"])
    warns = int(best["warning_count"])
    sat = float(best["average_saturation_fraction"])

    pp = cfg["decision_policy"]["pass"]
    cp = cfg["decision_policy"]["conditional_pass"]

    if fails <= pp["maximum_unexplained_fail_count"] and warns <= pp["maximum_warning_count"] and sat <= pp["maximum_average_saturation_fraction"] and ratio <= pp["maximum_comparison_rmse_ratio_vs_baseline"]:
        status = "pass"
        usable = True
        reason = "Corrected surrogate is comparable and best MPC candidate meets pass thresholds."
    elif fails <= cp["maximum_unexplained_fail_count"] and sat <= cp["maximum_average_saturation_fraction"] and ratio <= cp["maximum_comparison_rmse_ratio_vs_baseline"]:
        status = "conditional_pass"
        usable = True
        reason = "Corrected surrogate is comparable, but metric trade-offs remain."
    else:
        status = "fail"
        usable = False
        reason = "Corrected surrogate is comparable, but MPC candidates remain unsuitable against the fixed baseline."

    return {
        "status": status,
        "selected_candidate_id": best["candidate_id"],
        "corrected_surrogate_comparable": True,
        "usable_offline_tradeoff_vs_baseline": usable,
        "reason": reason
    }


def docs(summary):
    best = summary["selected_candidate"]
    decision = summary["decision"]

    readme = f"""# v0.15.4 corrected offline MPC surrogate comparison

## Purpose

This stage reruns MPC-vs-baseline comparison after correcting surrogate/comparability defects from v0.15.3.

It is offline-only and does not claim live-controller readiness.

## Baseline

- Candidate: {summary["reference_baseline"]["candidate_id"]}
- Effective controller: {summary["reference_baseline"]["effective_controller"]}
- Corrected baseline comparison RMSE: {summary["baseline_comparison_rmse"]}

## Correction validation

- Correction checks passed: {summary["correction_checks_passed"]}
- Correction checks failed: {summary["correction_checks_failed"]}
- Explicit delay steps: {summary["linear_model_used"]["delay_steps"]}

## Selected corrected MPC candidate

- Candidate: {best["candidate_id"]}
- Average comparison RMSE: {best["average_comparison_rmse"]}
- Comparison RMSE ratio vs baseline: {best["comparison_rmse_ratio_vs_baseline"]}
- Unexplained failures: {best["unexplained_fail_count"]}
- Warnings: {best["warning_count"]}

## Decision

- Status: {decision["status"]}
- Corrected surrogate comparable: {decision["corrected_surrogate_comparable"]}
- Usable offline trade-off vs baseline: {decision["usable_offline_tradeoff_vs_baseline"]}

Reason: {decision["reason"]}
"""

    exp = f"""# v0.15.4 corrected offline MPC surrogate comparison

## Purpose

v0.15.4 reruns the offline MPC comparison after applying correction requirements from v0.15.3.

## Corrections applied

- Explicit one-step delay policy
- Active control horizon through candidate-specific tracking fraction
- Active objective weights through effort and delta penalties
- High-frequency profile handling using full RMSE

## Reference baseline

    {summary["reference_baseline"]["candidate_id"]}

## Selected candidate

    {best["candidate_id"]}

Comparison RMSE ratio vs baseline:

    {best["comparison_rmse_ratio_vs_baseline"]}

## Decision

Status:

    {decision["status"]}

Reason:

    {decision["reason"]}

## Interpretation

A blocked result means correction checks failed. A fail means the corrected comparison is interpretable but MPC remains weak. A conditional pass or pass supports continued offline MPC development only.
"""
    return readme, exp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_json(args.config)
    src = cfg["source_artifacts"]
    out = cfg["outputs"]

    for path in src.values():
        if not rp(path).is_file():
            raise FileNotFoundError(path)

    mod = import_script(src["v0_14_2_script"])
    v0153 = load_json(src["v0_15_3_summary"])
    v0152 = load_json(src["v0_15_2_summary"])
    v0140 = load_json(src["v0_14_0_config"])
    v0142 = load_json(src["v0_14_2_config"])
    model = load_json(src["selected_recursive_model"])

    candidates = read_csv(src["v0_15_1_candidate_specs"])
    baseline_cases = read_csv(src["v0_14_3_baseline_case_metrics"])

    profiles = v0140["profiles"]
    sim_policy = v0140["simulation_policy"]
    safety = v0140["safety_policy"]
    thresholds = v0142["settled_metric_thresholds"]

    old_lm = v0152["linear_model_used"]
    lm = {
        "c": float(old_lm["c"]),
        "a_y": float(old_lm["a_y"]),
        "b_u": float(old_lm["b_u"]),
        "discovered_delay_steps": old_lm.get("delay_steps"),
        "delay_steps": int(cfg["correction_policy"]["force_explicit_delay_steps"]),
    }

    base_rmse, base_profile_rmse = baseline_rmse(
        mod, baseline_cases, profiles, int(sim_policy.get("steps_per_profile", 80)), cfg
    )

    case_rows = []
    summaries = []
    for cand in candidates:
        rows = []
        for profile in profiles:
            row = simulate_case(mod, model, cand, profile, sim_policy, safety, lm, thresholds, cfg)
            rows.append(row)
            case_rows.append(row)
        summaries.append(summarize_candidate(cand, rows, base_rmse))

    ranking = rank_candidates(summaries)
    validations = correction_validation(v0153, lm, ranking, case_rows)
    decision = decide(ranking[0], validations, cfg)

    profile_rows = []
    for name in sorted({r["profile"] for r in case_rows}):
        rows = [r for r in case_rows if r["profile"] == name]
        best = min(rows, key=lambda r: float(r["comparison_rmse"]))
        profile_rows.append({
            "profile": name,
            "candidate_count": len(rows),
            "best_candidate_id": best["candidate_id"],
            "best_comparison_rmse": best["comparison_rmse"],
            "interpretation_mode": best["interpretation_mode"],
        })

    summary = {
        "stage": cfg["stage"],
        "experiment": cfg["experiment"],
        "offline_only": True,
        "v0_15_3_decision": v0153["decision"]["status"],
        "v0_15_2_previous_decision": v0152["decision"]["status"],
        "reference_baseline": cfg["reference_baseline"],
        "baseline_comparison_rmse": base_rmse,
        "baseline_profile_comparison_rmse": base_profile_rmse,
        "candidate_count": len(candidates),
        "profile_count": len(profiles),
        "case_count": len(case_rows),
        "linear_model_used": lm,
        "selected_candidate": ranking[0],
        "correction_checks_passed": sum(1 for v in validations if v["passed"]),
        "correction_checks_failed": sum(1 for v in validations if not v["passed"]),
        "decision": decision,
        "performance_claim": False,
        "live_controller_claim": False,
        "outputs": out,
    }

    candidate_fields = list(ranking[0].keys())
    case_fields = list(case_rows[0].keys())
    profile_fields = list(profile_rows[0].keys())
    validation_fields = list(validations[0].keys())

    write_json(out["summary_json"], summary)
    write_csv(out["candidate_ranking_csv"], ranking, candidate_fields)
    write_csv(out["case_metrics_csv"], case_rows, case_fields)
    write_csv(out["profile_metrics_csv"], profile_rows, profile_fields)
    write_csv(out["correction_validation_csv"], validations, validation_fields)

    readme, exp = docs(summary)
    write_text(out["readme_md"], readme)
    write_text(out["experiment_doc"], exp)

    print(json.dumps({
        "stage": summary["stage"],
        "decision": decision["status"],
        "corrected_surrogate_comparable": decision["corrected_surrogate_comparable"],
        "selected_candidate": ranking[0]["candidate_id"],
        "comparison_rmse_ratio_vs_baseline": ranking[0]["comparison_rmse_ratio_vs_baseline"],
        "correction_checks_passed": summary["correction_checks_passed"],
        "correction_checks_failed": summary["correction_checks_failed"],
        "candidate_count": summary["candidate_count"],
        "case_count": summary["case_count"],
        "performance_claim": False,
        "live_controller_claim": False
    }, indent=2))


if __name__ == "__main__":
    main()
