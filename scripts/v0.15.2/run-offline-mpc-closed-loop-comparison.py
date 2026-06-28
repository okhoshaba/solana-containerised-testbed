#!/usr/bin/env python3
"""
v0.15.2 offline MPC closed-loop simulation comparison.

This stage evaluates deterministic MPC skeleton candidates in an offline
closed-loop simulation and compares them against the fixed v0.14.3 P-only
baseline. It is not a live controller and does not claim production readiness.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def require_file(path: str | Path) -> Path:
    p = repo_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {p}")
    return p


def read_csv(path: str | Path) -> List[Dict[str, str]]:
    p = require_file(path)
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def import_v0142(script_path: str | Path):
    p = require_file(script_path)
    spec = importlib.util.spec_from_file_location("v0142_pid_sweep", str(p))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {p}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finite_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def flatten_numbers(obj: Any, prefix: str = "") -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            name = f"{prefix}.{k}" if prefix else str(k)
            rows.extend(flatten_numbers(v, name))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            rows.extend(flatten_numbers(v, f"{prefix}[{i}]"))
    else:
        f = finite_float(obj)
        if f is not None:
            rows.append((prefix, f))
    return rows


def extract_linear_model(model: Dict[str, Any]) -> Dict[str, float]:
    nums = flatten_numbers(model)

    def score(path: str, groups: List[str]) -> int:
        p = path.lower().replace("-", "_")
        return sum(1 for g in groups if g in p)

    c_candidates = []
    a_candidates = []
    b_candidates = []
    delay_candidates = []

    for path, value in nums:
        p = path.lower().replace("-", "_")
        if any(token in p for token in ["intercept", "bias", ".c", "constant"]):
            c_candidates.append((score(path, ["intercept", "bias", ".c", "constant"]), path, value))
        if any(token in p for token in ["a_y", "ay", "y_lag", "lag_y", "coef_y", "coefficient_y"]):
            a_candidates.append((score(path, ["a_y", "y_lag", "coef_y", "coefficient_y"]), path, value))
        if any(token in p for token in ["b_u", "bu", "u_lag", "lag_u", "coef_u", "coefficient_u", "action"]):
            if "action_min" not in p and "action_max" not in p and "max_step" not in p:
                b_candidates.append((score(path, ["b_u", "u_lag", "coef_u", "coefficient_u"]), path, value))
        if "delay" in p and value >= 0:
            delay_candidates.append((score(path, ["delay"]), path, value))

    c = sorted(c_candidates, reverse=True)[0][2] if c_candidates else 0.0
    a = sorted(a_candidates, reverse=True)[0][2] if a_candidates else 0.0
    b = sorted(b_candidates, reverse=True)[0][2] if b_candidates else 1.0
    delay = int(round(sorted(delay_candidates, reverse=True)[0][2])) if delay_candidates else 1

    return {
        "c": c,
        "a_y": a,
        "b_u": b,
        "delay_steps": max(0, delay)
    }


def target_at_step(module, profile: Dict[str, Any], step: int) -> float:
    return float(module.target_at_step(profile, step))


def equilibrium_command(module, model: Dict[str, Any], target: float, safety: Dict[str, Any]) -> float:
    try:
        u = float(module.equilibrium_command(model, target))
    except Exception:
        u = target

    return min(max(u, float(safety.get("action_min", 0.0))), float(safety.get("action_max", 160.0)))


def apply_action_limits(raw_u: float, previous_u: float, safety: Dict[str, Any]) -> Tuple[float, bool, bool]:
    action_min = float(safety.get("action_min", 0.0))
    action_max = float(safety.get("action_max", 160.0))
    max_step = float(safety.get("max_step_change", action_max - action_min))

    limited = min(max(raw_u, previous_u - max_step), previous_u + max_step)
    rate_limited = abs(limited - raw_u) > 1e-12

    saturated_value = min(max(limited, action_min), action_max)
    saturated = abs(saturated_value - limited) > 1e-12 or saturated_value in (action_min, action_max)

    return saturated_value, rate_limited, saturated


def predict_next(y: float, plant_u: float, lm: Dict[str, float]) -> float:
    return lm["c"] + lm["a_y"] * y + lm["b_u"] * plant_u


def candidate_command_grid(previous_u: float, u_eq: float, safety: Dict[str, Any], grid_points: int) -> List[float]:
    action_min = float(safety.get("action_min", 0.0))
    action_max = float(safety.get("action_max", 160.0))
    max_step = float(safety.get("max_step_change", action_max - action_min))

    lo = max(action_min, previous_u - max_step)
    hi = min(action_max, previous_u + max_step)

    if grid_points <= 1 or hi <= lo:
        values = [previous_u, u_eq]
    else:
        step = (hi - lo) / float(grid_points - 1)
        values = [lo + i * step for i in range(grid_points)]
        values.extend([previous_u, u_eq])

    unique = []
    seen = set()
    for value in values:
        rounded = round(float(value), 9)
        if rounded not in seen:
            seen.add(rounded)
            unique.append(float(value))
    return unique


def score_plan(
    module,
    profile: Dict[str, Any],
    start_step: int,
    y0: float,
    u0: float,
    previous_u: float,
    candidate: Dict[str, Any],
    safety: Dict[str, Any],
    lm: Dict[str, float]
) -> float:
    ph = int(candidate["prediction_horizon"])
    q = float(candidate["tracking_error_weight"])
    r = float(candidate["control_effort_weight"])
    du = float(candidate["control_delta_weight"])
    soft = float(candidate["soft_constraint_weight"])

    action_max = float(safety.get("action_max", 160.0))
    action_min = float(safety.get("action_min", 0.0))
    scale = max(1.0, action_max - action_min)

    y = y0
    cost = du * ((u0 - previous_u) / scale) ** 2

    for h in range(ph):
        step = start_step + h
        target = target_at_step(module, profile, step)
        y = predict_next(y, u0, lm)
        error = y - target

        violation = 0.0
        if not math.isfinite(y):
            violation += 1e6

        cost += q * error * error
        cost += r * ((u0 - action_min) / scale) ** 2
        cost += soft * violation

    return cost


def simulate_mpc_candidate_on_profile(
    module,
    model: Dict[str, Any],
    candidate: Dict[str, Any],
    profile: Dict[str, Any],
    simulation_policy: Dict[str, Any],
    safety: Dict[str, Any],
    lm: Dict[str, float],
    grid_points: int
) -> List[Dict[str, Any]]:
    steps = int(simulation_policy.get("steps_per_profile", 80))
    y = float(profile.get("initial_y", target_at_step(module, profile, 0)))
    u_prev = equilibrium_command(module, model, target_at_step(module, profile, 0), safety)

    delay = int(lm.get("delay_steps", 1))
    u_buffer = [u_prev for _ in range(delay + 1)]

    rows = []

    for k in range(steps):
        target = target_at_step(module, profile, k)
        u_eq = equilibrium_command(module, model, target, safety)
        command_grid = candidate_command_grid(u_prev, u_eq, safety, grid_points)

        scored = [
            (
                score_plan(module, profile, k, y, raw_u, u_prev, candidate, safety, lm),
                raw_u
            )
            for raw_u in command_grid
        ]
        _, raw_u = min(scored, key=lambda item: item[0])
        u, rate_limited, saturated = apply_action_limits(raw_u, u_prev, safety)

        if delay > 0:
            plant_u = u_buffer.pop(0)
            u_buffer.append(u)
        else:
            plant_u = u

        y_next = predict_next(y, plant_u, lm)
        error = y - target

        rows.append({
            "step": k,
            "profile": profile.get("name", "profile"),
            "target": target,
            "y": y,
            "error": error,
            "abs_error": abs(error),
            "raw_u": raw_u,
            "u": u,
            "plant_u": plant_u,
            "rate_limited": rate_limited,
            "saturated": saturated,
            "candidate_id": candidate["candidate_id"]
        })

        y = y_next
        u_prev = u

    return rows


def find_target_changes(rows: List[Dict[str, Any]]) -> List[int]:
    changes = []
    previous = None
    for row in rows:
        target = float(row["target"])
        if previous is not None and abs(target - previous) > 1e-9:
            changes.append(int(row["step"]))
        previous = target
    return changes


def is_transient_step(step: int, changes: List[int], window: int) -> bool:
    return any(change <= step < change + window for change in changes)


def metrics_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors = [float(row["error"]) for row in rows]
    abs_errors = [abs(e) for e in errors]

    return {
        "rmse": math.sqrt(statistics.mean([e * e for e in errors])) if errors else None,
        "mae": statistics.mean(abs_errors) if abs_errors else None,
        "max_abs_error": max(abs_errors) if abs_errors else None
    }


def classify_case(
    full_metrics: Dict[str, Any],
    settled_metrics: Dict[str, Any],
    rate_limit_fraction: float,
    saturation_fraction: float,
    thresholds: Dict[str, float],
    has_target_change: bool
) -> str:
    settled_rmse = float(settled_metrics["rmse"])
    settled_max = float(settled_metrics["max_abs_error"])
    full_max = float(full_metrics["max_abs_error"])

    if saturation_fraction > float(thresholds.get("maximum_saturation_fraction_for_calibrated_pass", 0.2)):
        return "UNEXPLAINED_FAIL"

    if (
        settled_rmse > float(thresholds.get("settled_fail_rmse", 8.0))
        or settled_max > float(thresholds.get("settled_fail_max_abs_error", 24.0))
    ):
        return "UNEXPLAINED_FAIL"

    if (
        settled_rmse > float(thresholds.get("settled_warn_rmse", 4.0))
        or settled_max > float(thresholds.get("settled_warn_max_abs_error", 12.0))
    ):
        return "SETTLED_WARN"

    if has_target_change and full_max > float(thresholds.get("settled_warn_max_abs_error", 12.0)):
        return "EXPLAINED_TRANSIENT"

    return "PASS"


def case_metrics_for_profile(
    module,
    model: Dict[str, Any],
    candidate: Dict[str, Any],
    profile: Dict[str, Any],
    simulation_policy: Dict[str, Any],
    safety: Dict[str, Any],
    lm: Dict[str, float],
    thresholds: Dict[str, float],
    transient_window: int,
    grid_points: int
) -> Dict[str, Any]:
    rows = simulate_mpc_candidate_on_profile(
        module, model, candidate, profile, simulation_policy, safety, lm, grid_points
    )

    changes = find_target_changes(rows)
    settled_rows = [
        row for row in rows
        if not is_transient_step(int(row["step"]), changes, transient_window)
    ]
    if not settled_rows:
        settled_rows = rows

    full = metrics_from_rows(rows)
    settled = metrics_from_rows(settled_rows)

    rate_limit_fraction = sum(1 for r in rows if r["rate_limited"]) / float(len(rows))
    saturation_fraction = sum(1 for r in rows if r["saturated"]) / float(len(rows))

    errors = [float(r["error"]) for r in rows]
    overshoot = max([e for e in errors if e > 0.0], default=0.0)
    undershoot = abs(min([e for e in errors if e < 0.0], default=0.0))
    final_error = errors[-1]
    final_abs_error = abs(final_error)

    status = classify_case(
        full, settled, rate_limit_fraction, saturation_fraction, thresholds, bool(changes)
    )

    return {
        "candidate_id": candidate["candidate_id"],
        "prediction_horizon": candidate["prediction_horizon"],
        "control_horizon": candidate["control_horizon"],
        "tracking_error_weight": candidate["tracking_error_weight"],
        "control_effort_weight": candidate["control_effort_weight"],
        "control_delta_weight": candidate["control_delta_weight"],
        "soft_constraint_weight": candidate["soft_constraint_weight"],
        "profile": profile.get("name", "profile"),
        "calibrated_status": status,
        "full_rmse": full["rmse"],
        "full_mae": full["mae"],
        "full_max_abs_error": full["max_abs_error"],
        "settled_rmse": settled["rmse"],
        "settled_mae": settled["mae"],
        "settled_max_abs_error": settled["max_abs_error"],
        "final_error": final_error,
        "final_abs_error": final_abs_error,
        "overshoot": overshoot,
        "undershoot": undershoot,
        "rate_limit_fraction": rate_limit_fraction,
        "saturation_fraction": saturation_fraction,
        "target_change_count": len(changes),
        "closed_loop_simulated": True,
        "performance_claim": False
    }


def summarize_candidate(candidate: Dict[str, Any], rows: List[Dict[str, Any]], baseline_avg_settled_rmse: float) -> Dict[str, Any]:
    def avg(key: str) -> float:
        values = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
        return statistics.mean(values) if values else float("nan")

    statuses = [str(r["calibrated_status"]) for r in rows]
    average_settled_rmse = avg("settled_rmse")
    ratio = average_settled_rmse / baseline_avg_settled_rmse if baseline_avg_settled_rmse > 0 else float("inf")

    return {
        "candidate_id": candidate["candidate_id"],
        "prediction_horizon": candidate["prediction_horizon"],
        "control_horizon": candidate["control_horizon"],
        "tracking_error_weight": candidate["tracking_error_weight"],
        "control_effort_weight": candidate["control_effort_weight"],
        "control_delta_weight": candidate["control_delta_weight"],
        "soft_constraint_weight": candidate["soft_constraint_weight"],
        "case_count": len(rows),
        "pass_count": statuses.count("PASS"),
        "settled_warn_count": statuses.count("SETTLED_WARN"),
        "explained_transient_count": statuses.count("EXPLAINED_TRANSIENT"),
        "unexplained_fail_count": statuses.count("UNEXPLAINED_FAIL"),
        "average_full_rmse": avg("full_rmse"),
        "average_full_mae": avg("full_mae"),
        "average_full_max_abs_error": avg("full_max_abs_error"),
        "average_settled_rmse": average_settled_rmse,
        "average_settled_mae": avg("settled_mae"),
        "average_settled_max_abs_error": avg("settled_max_abs_error"),
        "worst_settled_max_abs_error": max(float(r["settled_max_abs_error"]) for r in rows),
        "average_rate_limit_fraction": avg("rate_limit_fraction"),
        "average_saturation_fraction": avg("saturation_fraction"),
        "settled_rmse_ratio_vs_baseline": ratio,
        "closed_loop_simulated": True,
        "performance_claim": False
    }


def summarize_profiles(case_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    profiles = sorted({r["profile"] for r in case_rows})
    out = []

    for profile in profiles:
        rows = [r for r in case_rows if r["profile"] == profile]
        statuses = [r["calibrated_status"] for r in rows]
        best = min(rows, key=lambda r: float(r["settled_rmse"]))
        out.append({
            "profile": profile,
            "candidate_count": len(rows),
            "pass_count": statuses.count("PASS"),
            "settled_warn_count": statuses.count("SETTLED_WARN"),
            "explained_transient_count": statuses.count("EXPLAINED_TRANSIENT"),
            "unexplained_fail_count": statuses.count("UNEXPLAINED_FAIL"),
            "best_candidate_id": best["candidate_id"],
            "best_settled_rmse": best["settled_rmse"],
            "best_full_rmse": best["full_rmse"]
        })

    return out


def rank_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda r: (
            int(r["unexplained_fail_count"]),
            int(r["settled_warn_count"]),
            float(r["settled_rmse_ratio_vs_baseline"]),
            float(r["average_settled_rmse"]),
            float(r["average_rate_limit_fraction"]),
            float(r["average_saturation_fraction"])
        )
    )
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


def decision_from_best(best: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    pass_policy = config["decision_policy"]["pass"]
    conditional_policy = config["decision_policy"]["conditional_pass"]

    unexplained = int(best["unexplained_fail_count"])
    warn = int(best["settled_warn_count"])
    saturation = float(best["average_saturation_fraction"])
    ratio = float(best["settled_rmse_ratio_vs_baseline"])

    if (
        unexplained <= int(pass_policy["maximum_unexplained_fail_count"])
        and warn <= int(pass_policy["maximum_settled_warn_count"])
        and saturation <= float(pass_policy["maximum_average_saturation_fraction"])
        and ratio <= float(pass_policy["maximum_settled_rmse_ratio_vs_baseline"])
    ):
        return {
            "status": "pass",
            "selected_mpc_candidate_id": best["candidate_id"],
            "usable_offline_tradeoff_vs_baseline": True,
            "reason": "Best MPC candidate satisfies calibrated offline safety checks and settled RMSE ratio threshold versus the fixed v0.14.3 baseline."
        }

    if (
        unexplained <= int(conditional_policy["maximum_unexplained_fail_count"])
        and saturation <= float(conditional_policy["maximum_average_saturation_fraction"])
    ):
        return {
            "status": "conditional_pass",
            "selected_mpc_candidate_id": best["candidate_id"],
            "usable_offline_tradeoff_vs_baseline": True,
            "reason": "Best MPC candidate is usable for further offline comparison, but it has documented metric trade-offs versus the fixed baseline."
        }

    return {
        "status": "fail",
        "selected_mpc_candidate_id": best["candidate_id"],
        "usable_offline_tradeoff_vs_baseline": False,
        "reason": "MPC candidates are not yet suitable as baseline competitors under the offline comparison policy."
    }


def transient_window_from_summary(summary: Dict[str, Any]) -> int:
    for key in [
        "transient_window_steps_after_target_change",
        "transient_window_steps",
        "calibrated_transient_window_steps"
    ]:
        value = summary.get(key)
        if isinstance(value, int):
            return value
    return 5


def baseline_average_settled_rmse(baseline_summary: Dict[str, Any]) -> float:
    metrics = baseline_summary.get("baseline_metrics", {})
    value = finite_float(metrics.get("average_settled_rmse"))
    if value is not None:
        return value

    top = baseline_summary.get("top_candidates", [{}])[0]
    value = finite_float(top.get("average_settled_rmse"))
    if value is not None:
        return value

    raise RuntimeError("Could not locate baseline average_settled_rmse")


def write_readme(path: str | Path, summary: Dict[str, Any]) -> None:
    decision = summary["decision"]
    best = summary["selected_mpc_candidate"]
    text = f"""# v0.15.2 offline MPC closed-loop simulation comparison

## Purpose

This stage evaluates deterministic MPC skeleton candidates from v0.15.1 in offline closed-loop simulation.

It compares them against the fixed v0.14.3 P-only baseline.

This is not a live controller stage and it does not claim production readiness.

## Reference baseline

- Source stage: v0.14.3
- Candidate: {summary["reference_baseline"]["candidate_id"]}
- Effective controller: {summary["reference_baseline"]["effective_controller"]}
- Baseline average settled RMSE: {summary["baseline_average_settled_rmse"]}

## MPC candidates

- Candidate source: v0.15.1 deterministic MPC skeleton
- Candidate count: {summary["candidate_count"]}
- Profile count: {summary["profile_count"]}
- Case count: {summary["case_count"]}

## Selected offline MPC candidate

- Candidate: {best["candidate_id"]}
- Prediction horizon: {best["prediction_horizon"]}
- Control horizon: {best["control_horizon"]}
- Average settled RMSE: {best["average_settled_rmse"]}
- Settled RMSE ratio vs baseline: {best["settled_rmse_ratio_vs_baseline"]}
- Average saturation fraction: {best["average_saturation_fraction"]}
- Average rate-limit fraction: {best["average_rate_limit_fraction"]}
- Unexplained failure count: {best["unexplained_fail_count"]}
- Settled warning count: {best["settled_warn_count"]}

## Decision

- Status: {decision["status"]}
- Usable offline trade-off vs baseline: {decision["usable_offline_tradeoff_vs_baseline"]}

Reason: {decision["reason"]}

## Interpretation

This stage provides an offline comparison only. It should be interpreted as evidence for or against continuing MPC development, not as proof of live-controller safety or production superiority.
"""
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def write_experiment_doc(path: str | Path, summary: Dict[str, Any]) -> None:
    decision = summary["decision"]
    best = summary["selected_mpc_candidate"]
    text = f"""# v0.15.2 offline MPC closed-loop simulation comparison

## Purpose

v0.15.2 is the first offline closed-loop comparison stage for MPC candidates.

It evaluates deterministic MPC skeleton candidates from v0.15.1 and compares them against the fixed v0.14.3 P-only baseline.

## Scientific rationale

The project should not compare MPC against an abstract PID family. It should compare MPC against the fixed validated baseline:

    {summary["reference_baseline"]["candidate_id"]}

This baseline was accepted in v0.14.3 as the reference controller before MPC.

## Simulation scope

This is an offline-only simulation.

No live Kubernetes controller is executed.

The comparison uses a receding-horizon offline surrogate over the selected recursive plant model and the v0.14.x safety/calibration context.

## Candidate set

The input candidate set comes from v0.15.1.

Candidate count:

    {summary["candidate_count"]}

Case count:

    {summary["case_count"]}

Profile count:

    {summary["profile_count"]}

## Selected candidate

Selected candidate:

    {best["candidate_id"]}

Settled RMSE ratio vs baseline:

    {best["settled_rmse_ratio_vs_baseline"]}

Average settled RMSE:

    {best["average_settled_rmse"]}

Average saturation fraction:

    {best["average_saturation_fraction"]}

Average rate-limit fraction:

    {best["average_rate_limit_fraction"]}

## Decision

Status:

    {decision["status"]}

Reason:

    {decision["reason"]}

## Interpretation

The result must be read as an offline trade-off assessment. A pass does not mean production readiness. A conditional pass does not mean failure. It means that MPC behaviour is potentially useful but requires further analysis.

## Recommended next step

Use the selected candidate and case-level diagnostics to decide whether to refine the MPC optimiser, adjust objective weights, or proceed to a more faithful offline MPC implementation.
"""
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    config = load_json(args.config)
    sources = config["source_artifacts"]
    outputs = config["outputs"]

    for path in sources.values():
        require_file(path)

    v0142 = import_v0142(sources["v0_14_2_script_path"])
    v0142_config = load_json(sources["v0_14_2_config_path"])
    v0140_config = load_json(sources["v0_14_0_config_path"])
    v0141_summary = load_json(sources["v0_14_1_calibration_summary_path"])
    v0151_summary = load_json(sources["v0_15_1_summary_path"])
    baseline_summary = load_json(sources["v0_14_3_baseline_summary_path"])
    model = load_json(sources["selected_recursive_model_path"])

    profiles = v0140_config["profiles"]
    simulation_policy = v0140_config["simulation_policy"]
    safety = v0140_config["safety_policy"]
    thresholds = v0142_config["settled_metric_thresholds"]
    transient_window = transient_window_from_summary(v0141_summary)
    baseline_rmse = baseline_average_settled_rmse(baseline_summary)
    lm = extract_linear_model(model)

    candidates = read_csv(sources["v0_15_1_candidate_specs_csv"])
    grid_points = int(config["mpc_simulation_policy"]["command_grid_points"])

    case_rows = []
    candidate_summaries = []

    for candidate in candidates:
        per_candidate = []
        for profile in profiles:
            row = case_metrics_for_profile(
                v0142, model, candidate, profile, simulation_policy,
                safety, lm, thresholds, transient_window, grid_points
            )
            per_candidate.append(row)
            case_rows.append(row)

        candidate_summaries.append(
            summarize_candidate(candidate, per_candidate, baseline_rmse)
        )

    ranking = rank_candidates(candidate_summaries)
    profile_rows = summarize_profiles(case_rows)
    decision = decision_from_best(ranking[0], config)

    summary = {
        "stage": config["stage"],
        "experiment": config["experiment"],
        "title": config["title"],
        "offline_only": True,
        "purpose": config["purpose"],
        "simulation_mode": config["mpc_simulation_policy"]["mode"],
        "v0_15_1_decision": v0151_summary.get("decision"),
        "reference_baseline": config["reference_baseline"],
        "baseline_average_settled_rmse": baseline_rmse,
        "linear_model_used": lm,
        "candidate_count": len(candidates),
        "profile_count": len(profiles),
        "case_count": len(case_rows),
        "selected_mpc_candidate": ranking[0],
        "decision": decision,
        "performance_claim": False,
        "live_controller_claim": False,
        "outputs": outputs
    }

    write_json(outputs["summary_json"], summary)

    candidate_fields = [
        "rank", "candidate_id", "prediction_horizon", "control_horizon",
        "tracking_error_weight", "control_effort_weight", "control_delta_weight",
        "soft_constraint_weight", "case_count", "pass_count", "settled_warn_count",
        "explained_transient_count", "unexplained_fail_count", "average_full_rmse",
        "average_full_mae", "average_full_max_abs_error", "average_settled_rmse",
        "average_settled_mae", "average_settled_max_abs_error",
        "worst_settled_max_abs_error", "average_rate_limit_fraction",
        "average_saturation_fraction", "settled_rmse_ratio_vs_baseline",
        "closed_loop_simulated", "performance_claim"
    ]
    case_fields = [
        "candidate_id", "prediction_horizon", "control_horizon",
        "tracking_error_weight", "control_effort_weight", "control_delta_weight",
        "soft_constraint_weight", "profile", "calibrated_status", "full_rmse",
        "full_mae", "full_max_abs_error", "settled_rmse", "settled_mae",
        "settled_max_abs_error", "final_error", "final_abs_error", "overshoot",
        "undershoot", "rate_limit_fraction", "saturation_fraction",
        "target_change_count", "closed_loop_simulated", "performance_claim"
    ]
    profile_fields = [
        "profile", "candidate_count", "pass_count", "settled_warn_count",
        "explained_transient_count", "unexplained_fail_count",
        "best_candidate_id", "best_settled_rmse", "best_full_rmse"
    ]

    write_csv(outputs["candidate_ranking_csv"], ranking, candidate_fields)
    write_csv(outputs["case_metrics_csv"], case_rows, case_fields)
    write_csv(outputs["profile_metrics_csv"], profile_rows, profile_fields)
    write_readme(outputs["readme_md"], summary)
    write_experiment_doc(outputs["experiment_doc"], summary)

    print(json.dumps({
        "stage": summary["stage"],
        "decision": decision["status"],
        "selected_mpc_candidate": ranking[0]["candidate_id"],
        "candidate_count": len(candidates),
        "case_count": len(case_rows),
        "baseline": config["reference_baseline"]["candidate_id"],
        "performance_claim": False,
        "live_controller_claim": False
    }, indent=2))


if __name__ == "__main__":
    main()
