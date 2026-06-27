#!/usr/bin/env python3

import argparse
import csv
import itertools
import json
import math
from pathlib import Path


def load_json(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required JSON file is missing: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
        f.write("\n")


def require_file(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {path}")
    return p


def ensure_parent(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def finite_float(value, default=None):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return x


def target_at_step(profile, k):
    ptype = profile["type"]

    if ptype == "constant":
        return float(profile["target"])

    if ptype == "step":
        if k < int(profile["change_step"]):
            return float(profile["initial_target"])
        return float(profile["target"])

    if ptype == "multistep":
        current = float(profile["segments"][0]["target"])
        for segment in profile["segments"]:
            if k >= int(segment["start"]):
                current = float(segment["target"])
            else:
                break
        return current

    if ptype == "sine":
        base = float(profile["base"])
        amplitude = float(profile["amplitude"])
        period_steps = float(profile["period_steps"])
        return base + amplitude * math.sin(2.0 * math.pi * float(k) / period_steps)

    raise ValueError(f"Unsupported profile type: {ptype}")


def equilibrium_command(model, target):
    a_y = float(model["a_y"])
    b_u = float(model["b_u"])
    c = float(model.get("c", 0.0))
    denom = a_y + b_u

    if abs(denom) > 1e-12:
        return (target - c) / denom

    if abs(b_u) > 1e-12:
        return (target - c) / b_u

    return float(model.get("u_eq", target))


def apply_limits(raw_u, previous_u, safety):
    action_min = float(safety["action_min"])
    action_max = float(safety["action_max"])
    max_step_change = safety.get("max_step_change")

    u = float(raw_u)
    limited_by_rate = False
    limited_by_bounds = False

    if max_step_change is not None and previous_u is not None:
        max_delta = abs(float(max_step_change))
        delta = u - previous_u

        if delta > max_delta:
            u = previous_u + max_delta
            limited_by_rate = True
        elif delta < -max_delta:
            u = previous_u - max_delta
            limited_by_rate = True

    if u < action_min:
        u = action_min
        limited_by_bounds = True
    elif u > action_max:
        u = action_max
        limited_by_bounds = True

    return u, limited_by_rate, limited_by_bounds


def generate_pid_candidates(gain_grid):
    candidates = []

    for family_name, grid in gain_grid.items():
        kp_values = grid.get("kp", [0.0])
        ki_values = grid.get("ki", [0.0])
        kd_values = grid.get("kd", [0.0])

        for kp, ki, kd in itertools.product(kp_values, ki_values, kd_values):
            candidate_id = f"{family_name}_kp{kp:.3f}_ki{ki:.3f}_kd{kd:.3f}"
            candidates.append({
                "candidate_id": candidate_id,
                "family": family_name,
                "kp": float(kp),
                "ki": float(ki),
                "kd": float(kd),
                "anti_windup": bool(float(ki) != 0.0)
            })

    return candidates


def controller_command(model, candidate, target, y, error, prev_error, integral):
    kp = float(candidate["kp"])
    ki = float(candidate["ki"])
    kd = float(candidate["kd"])

    base = equilibrium_command(model, target)

    derivative = 0.0
    if prev_error is not None:
        derivative = error - prev_error

    return base + kp * error + ki * integral + kd * derivative



def simulate_candidate_on_profile(model, candidate, profile, simulation_policy, safety):
    steps = int(simulation_policy["steps_per_profile"])
    dt = float(simulation_policy["dt_seconds"])

    a_y = float(model["a_y"])
    b_u = float(model["b_u"])
    c = float(model.get("c", 0.0))
    delay_steps = int(model.get("delay_steps", 0))

    y = finite_float(profile.get("initial_y"), None)
    if y is None:
        y = finite_float(model.get("y_eq"), 0.0)

    previous_u = equilibrium_command(model, target_at_step(profile, 0))
    prev_error = None
    integral = 0.0
    command_history = []

    rows = []
    full_errors = []
    command_changes = []

    rate_limit_count = 0
    saturation_count = 0
    anti_windup_freeze_count = 0
    non_finite_count = 0

    for k in range(steps):
        target = target_at_step(profile, k)
        error_before = target - y
        candidate_integral = integral + error_before * dt

        raw_u = controller_command(
            model=model,
            candidate=candidate,
            target=target,
            y=y,
            error=error_before,
            prev_error=prev_error,
            integral=candidate_integral
        )

        u_cmd, limited_by_rate, limited_by_bounds = apply_limits(raw_u, previous_u, safety)

        if limited_by_rate:
            rate_limit_count += 1

        if limited_by_bounds:
            saturation_count += 1

        if candidate["anti_windup"] and limited_by_bounds:
            anti_windup_freeze_count += 1
        else:
            integral = candidate_integral

        command_history.append(u_cmd)

        if delay_steps <= 0:
            delayed_u = u_cmd
        else:
            delayed_index = len(command_history) - 1 - delay_steps
            delayed_u = command_history[0] if delayed_index < 0 else command_history[delayed_index]

        y_after = c + a_y * y + b_u * delayed_u

        if not math.isfinite(y_after):
            non_finite_count += 1
            y_after = y

        error_after = target - y_after
        full_errors.append(error_after)
        command_changes.append(abs(u_cmd - previous_u))

        rows.append({
            "profile": profile["name"],
            "candidate_id": candidate["candidate_id"],
            "family": candidate["family"],
            "kp": candidate["kp"],
            "ki": candidate["ki"],
            "kd": candidate["kd"],
            "step": k,
            "time_seconds": k * dt,
            "target": target,
            "y_before": y,
            "error_before": error_before,
            "raw_u": raw_u,
            "u_cmd": u_cmd,
            "delayed_u": delayed_u,
            "y_after": y_after,
            "error_after": error_after,
            "limited_by_rate": limited_by_rate,
            "limited_by_bounds": limited_by_bounds,
            "anti_windup_frozen": bool(candidate["anti_windup"] and limited_by_bounds),
            "actuator_applied": False
        })

        previous_u = u_cmd
        prev_error = error_before
        y = y_after

    return rows


def find_target_changes(rows):
    changes = []

    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        delta = cur["target"] - prev["target"]

        if abs(delta) > 1e-12:
            changes.append({
                "step": cur["step"],
                "target_before": prev["target"],
                "target_after": cur["target"],
                "target_delta": delta,
                "abs_target_delta": abs(delta)
            })

    return changes


def transient_steps(changes, window):
    out = set()

    for change in changes:
        start = int(change["step"])
        for step in range(start, start + int(window)):
            out.add(step)

    return out


def nearest_change_for_step(step, changes, window):
    for change in changes:
        start = int(change["step"])
        if start <= step < start + int(window):
            return change
    return None


def metrics_from_rows(rows):
    if not rows:
        return {
            "count": 0,
            "rmse": None,
            "mae": None,
            "mean_error": None,
            "max_abs_error": None,
            "final_error": None
        }

    errors = [float(r["error_after"]) for r in rows]
    abs_errors = [abs(e) for e in errors]

    return {
        "count": len(rows),
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "mae": sum(abs_errors) / len(abs_errors),
        "mean_error": sum(errors) / len(errors),
        "max_abs_error": max(abs_errors),
        "final_error": errors[-1]
    }


def classify_calibrated_case(rows, full_metrics, settled_metrics, thresholds, transient_window):
    changes = find_target_changes(rows)
    t_steps = transient_steps(changes, transient_window)
    max_row = max(rows, key=lambda r: abs(float(r["error_after"])))
    nearest_change = nearest_change_for_step(max_row["step"], changes, transient_window)

    rate_limited_max_error = bool(nearest_change is not None and max_row["limited_by_rate"])

    saturation_fraction = sum(1 for r in rows if r["limited_by_bounds"]) / len(rows)
    rate_limit_fraction = sum(1 for r in rows if r["limited_by_rate"]) / len(rows)
    non_finite_count = 0

    reasons = []

    if non_finite_count > 0:
        reasons.append("non_finite_count > 0")

    if saturation_fraction > float(thresholds["maximum_saturation_fraction_for_calibrated_pass"]):
        reasons.append("saturation_fraction above calibrated limit")

    if settled_metrics["rmse"] is not None and settled_metrics["rmse"] > float(thresholds["settled_fail_rmse"]):
        reasons.append("settled_rmse > settled_fail_rmse")

    if settled_metrics["max_abs_error"] is not None and settled_metrics["max_abs_error"] > float(thresholds["settled_fail_max_abs_error"]):
        reasons.append("settled_max_abs_error > settled_fail_max_abs_error")

    if reasons:
        status = "UNEXPLAINED_FAIL"
    else:
        warn_reasons = []

        if settled_metrics["rmse"] is not None and settled_metrics["rmse"] > float(thresholds["settled_warn_rmse"]):
            warn_reasons.append("settled_rmse > settled_warn_rmse")

        if settled_metrics["max_abs_error"] is not None and settled_metrics["max_abs_error"] > float(thresholds["settled_warn_max_abs_error"]):
            warn_reasons.append("settled_max_abs_error > settled_warn_max_abs_error")

        if warn_reasons:
            status = "SETTLED_WARN"
            reasons = warn_reasons
        elif rate_limited_max_error and full_metrics["max_abs_error"] > float(thresholds["settled_fail_max_abs_error"]):
            status = "EXPLAINED_TRANSIENT"
            reasons = ["max full-window error is explained by rate-limited target-change transient"]
        else:
            status = "PASS"
            reasons = ["calibrated case passed"]

    if nearest_change is None:
        target_change_step = None
        target_before = None
        target_after = None
        abs_target_delta = 0.0
    else:
        target_change_step = nearest_change["step"]
        target_before = nearest_change["target_before"]
        target_after = nearest_change["target_after"]
        abs_target_delta = nearest_change["abs_target_delta"]

    return {
        "calibrated_status": status,
        "calibration_reasons": "; ".join(reasons),
        "max_abs_error_step": max_row["step"],
        "max_abs_error_value": abs(float(max_row["error_after"])),
        "max_abs_error_is_rate_limited_transition": rate_limited_max_error,
        "target_change_step": target_change_step,
        "target_before": target_before,
        "target_after": target_after,
        "abs_target_delta": abs_target_delta,
        "rate_limit_fraction": rate_limit_fraction,
        "saturation_fraction": saturation_fraction,
        "non_finite_count": non_finite_count,
        "transient_step_count": len(t_steps)
    }



def evaluate_candidate(model, candidate, profiles, simulation_policy, safety, thresholds, transient_window):
    case_rows = []
    profile_rows = []

    for profile in profiles:
        rows = simulate_candidate_on_profile(
            model=model,
            candidate=candidate,
            profile=profile,
            simulation_policy=simulation_policy,
            safety=safety
        )

        changes = find_target_changes(rows)
        t_steps = transient_steps(changes, transient_window)
        settled_rows = [r for r in rows if r["step"] not in t_steps]

        full_metrics = metrics_from_rows(rows)
        settled_metrics = metrics_from_rows(settled_rows)
        classification = classify_calibrated_case(
            rows=rows,
            full_metrics=full_metrics,
            settled_metrics=settled_metrics,
            thresholds=thresholds,
            transient_window=transient_window
        )

        case_rows.append({
            "candidate_id": candidate["candidate_id"],
            "family": candidate["family"],
            "kp": candidate["kp"],
            "ki": candidate["ki"],
            "kd": candidate["kd"],
            "profile": profile["name"],
            "calibrated_status": classification["calibrated_status"],
            "full_rmse": full_metrics["rmse"],
            "full_mae": full_metrics["mae"],
            "full_max_abs_error": full_metrics["max_abs_error"],
            "settled_rmse": settled_metrics["rmse"],
            "settled_mae": settled_metrics["mae"],
            "settled_max_abs_error": settled_metrics["max_abs_error"],
            "rate_limit_fraction": classification["rate_limit_fraction"],
            "saturation_fraction": classification["saturation_fraction"],
            "max_abs_error_step": classification["max_abs_error_step"],
            "max_abs_error_is_rate_limited_transition": classification["max_abs_error_is_rate_limited_transition"],
            "abs_target_delta": classification["abs_target_delta"],
            "calibration_reasons": classification["calibration_reasons"]
        })

    return case_rows


def summarize_candidate(candidate, case_rows):
    n = len(case_rows)

    status_counts = {
        "PASS": 0,
        "SETTLED_WARN": 0,
        "EXPLAINED_TRANSIENT": 0,
        "REVIEW": 0,
        "UNEXPLAINED_FAIL": 0
    }

    for row in case_rows:
        status_counts[row["calibrated_status"]] = status_counts.get(row["calibrated_status"], 0) + 1

    def avg(key):
        vals = [float(r[key]) for r in case_rows if r[key] is not None]
        return sum(vals) / len(vals) if vals else None

    def maxv(key):
        vals = [float(r[key]) for r in case_rows if r[key] is not None]
        return max(vals) if vals else None

    return {
        "candidate_id": candidate["candidate_id"],
        "family": candidate["family"],
        "kp": candidate["kp"],
        "ki": candidate["ki"],
        "kd": candidate["kd"],
        "case_count": n,
        "pass_count": status_counts["PASS"],
        "settled_warn_count": status_counts["SETTLED_WARN"],
        "explained_transient_count": status_counts["EXPLAINED_TRANSIENT"],
        "review_count": status_counts["REVIEW"],
        "unexplained_fail_count": status_counts["UNEXPLAINED_FAIL"],
        "average_full_rmse": avg("full_rmse"),
        "average_full_mae": avg("full_mae"),
        "average_full_max_abs_error": avg("full_max_abs_error"),
        "average_settled_rmse": avg("settled_rmse"),
        "average_settled_mae": avg("settled_mae"),
        "average_settled_max_abs_error": avg("settled_max_abs_error"),
        "worst_settled_max_abs_error": maxv("settled_max_abs_error"),
        "average_rate_limit_fraction": avg("rate_limit_fraction"),
        "average_saturation_fraction": avg("saturation_fraction")
    }


def rank_candidates(candidate_summaries):
    ranked = list(candidate_summaries)

    ranked.sort(key=lambda r: (
        r["unexplained_fail_count"],
        r["settled_warn_count"],
        r["review_count"],
        r["explained_transient_count"],
        r["average_settled_rmse"] if r["average_settled_rmse"] is not None else float("inf"),
        r["average_full_rmse"] if r["average_full_rmse"] is not None else float("inf"),
        r["average_rate_limit_fraction"] if r["average_rate_limit_fraction"] is not None else float("inf"),
        r["family"],
        r["kp"],
        r["ki"],
        r["kd"]
    ))

    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx

    return ranked


def summarize_profiles(case_rows):
    by_profile = {}

    for row in case_rows:
        profile = row["profile"]
        item = by_profile.setdefault(profile, {
            "profile": profile,
            "case_count": 0,
            "pass_count": 0,
            "settled_warn_count": 0,
            "explained_transient_count": 0,
            "review_count": 0,
            "unexplained_fail_count": 0,
            "best_settled_rmse": None,
            "best_candidate_id": None,
            "max_abs_target_delta": 0.0
        })

        item["case_count"] += 1
        key = row["calibrated_status"].lower() + "_count"
        if key in item:
            item[key] += 1

        if row["abs_target_delta"] is not None:
            item["max_abs_target_delta"] = max(item["max_abs_target_delta"], float(row["abs_target_delta"]))

        settled_rmse = row["settled_rmse"]
        if settled_rmse is not None:
            if item["best_settled_rmse"] is None or settled_rmse < item["best_settled_rmse"]:
                item["best_settled_rmse"] = settled_rmse
                item["best_candidate_id"] = row["candidate_id"]

    out = list(by_profile.values())
    out.sort(key=lambda x: x["profile"])
    return out


def write_csv(path, rows, fieldnames):
    ensure_parent(path)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_readme(path, summary, ranking):
    lines = []
    lines.append("# v0.14.2 offline PID gain sweep with calibrated metrics")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This stage performs an offline gain sweep for P, PI, and PID candidates using the selected recursive plant model and v0.14.1 calibrated metrics.")
    lines.append("")
    lines.append("No actuator is applied to a live system.")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- selected candidate: `{decision['selected_candidate_id']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append("| rank | candidate | family | kp | ki | kd | unexplained fail | settled warn | explained transient | avg settled RMSE | avg full RMSE |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in ranking[:10]:
        lines.append(
            f"| {row['rank']} | {row['candidate_id']} | {row['family']} | "
            f"{row['kp']:.3f} | {row['ki']:.3f} | {row['kd']:.3f} | "
            f"{row['unexplained_fail_count']} | {row['settled_warn_count']} | "
            f"{row['explained_transient_count']} | {row['average_settled_rmse']:.6f} | "
            f"{row['average_full_rmse']:.6f} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("Candidates are ranked by calibrated safety first, then by settled-window performance.")
    lines.append("The v0.14.0 fail result remains unchanged; v0.14.2 uses the v0.14.1 transient-aware interpretation for controller comparison.")
    lines.append("")

    ensure_parent(path)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_experiment_doc(path, summary, ranking):
    lines = []
    lines.append("# v0.14.2 offline PID gain sweep with calibrated metrics")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("v0.14.2 performs a controlled offline sweep over P, PI, and PID gain candidates.")
    lines.append("")
    lines.append("The sweep uses the v0.13.6 selected recursive plant model, the v0.14.0 offline simulator protocol, and the v0.14.1 calibrated transient-aware metrics.")
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    for key, value in summary["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Candidate selection")
    lines.append("")
    lines.append("Candidate ranking prioritizes calibrated safety before performance:")
    lines.append("")
    for item in summary["candidate_selection_basis"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- selected candidate: `{decision['selected_candidate_id']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Top 5 candidates")
    lines.append("")
    lines.append("| rank | candidate | family | kp | ki | kd | avg settled RMSE | avg full RMSE |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|")
    for row in ranking[:5]:
        lines.append(
            f"| {row['rank']} | {row['candidate_id']} | {row['family']} | "
            f"{row['kp']:.3f} | {row['ki']:.3f} | {row['kd']:.3f} | "
            f"{row['average_settled_rmse']:.6f} | {row['average_full_rmse']:.6f} |"
        )
    lines.append("")
    lines.append("## Next step")
    lines.append("")
    lines.append("Use the selected candidate as the baseline PID-style controller for the next offline comparison or MPC-readiness stage.")
    lines.append("")

    ensure_parent(path)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def decide(ranking, config):
    best = ranking[0]
    thresholds = config["decision_thresholds"]

    if best["unexplained_fail_count"] > int(thresholds["maximum_unexplained_failures_for_selected_candidate"]):
        status = "fail"
        accepted = False
        reason = "Best-ranked candidate still has unexplained calibrated failures."
    elif best["settled_warn_count"] > int(thresholds["maximum_settled_warn_cases_for_selected_candidate"]):
        status = "caution"
        accepted = True
        reason = "Best-ranked candidate has settled warnings but no unexplained failures."
    elif best["average_settled_rmse"] > float(thresholds["maximum_candidate_average_settled_rmse_for_pass"]):
        status = "caution"
        accepted = True
        reason = "Best-ranked candidate is safe but average settled RMSE exceeds pass threshold."
    else:
        status = "pass"
        accepted = True
        reason = "Best-ranked candidate has no unexplained failures, no settled warnings, and acceptable settled RMSE."

    return {
        "status": status,
        "accepted_selected_pid_candidate_for_followup": accepted,
        "selected_candidate_id": best["candidate_id"],
        "selected_family": best["family"],
        "selected_kp": best["kp"],
        "selected_ki": best["ki"],
        "selected_kd": best["kd"],
        "reason": reason,
        "recommended_next_step": "Use selected candidate as baseline offline PID-style controller before MPC comparison."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_json(args.config)

    for path in config["source_artifacts"].values():
        require_file(path)

    v0140_summary = load_json(config["source_artifacts"]["v0_14_0_summary_path"])
    v0141_summary = load_json(config["source_artifacts"]["v0_14_1_summary_path"])
    model = load_json(config["source_artifacts"]["selected_recursive_model_path"])

    profiles = v0140_summary["profiles"]
    simulation_policy = v0140_summary["simulation_policy"]
    safety = v0140_summary["safety_policy"]
    transient_window = int(v0141_summary["calibration_policy"]["transient_window_steps_after_target_change"])
    thresholds = config["settled_metric_thresholds"]

    candidates = generate_pid_candidates(config["gain_grid"])

    all_case_rows = []
    candidate_summaries = []

    for candidate in candidates:
        case_rows = evaluate_candidate(
            model=model,
            candidate=candidate,
            profiles=profiles,
            simulation_policy=simulation_policy,
            safety=safety,
            thresholds=thresholds,
            transient_window=transient_window
        )

        all_case_rows.extend(case_rows)
        candidate_summaries.append(summarize_candidate(candidate, case_rows))

    ranking = rank_candidates(candidate_summaries)
    profile_metrics = summarize_profiles(all_case_rows)
    decision = decide(ranking, config)

    summary = {
        "stage": config["stage"],
        "title": config["title"],
        "offline_only": config["offline_only"],
        "inputs": {
            "config_path": args.config,
            "v0_14_0_summary_path": config["source_artifacts"]["v0_14_0_summary_path"],
            "v0_14_1_summary_path": config["source_artifacts"]["v0_14_1_summary_path"],
            "selected_recursive_model_path": config["source_artifacts"]["selected_recursive_model_path"]
        },
        "candidate_count": len(candidates),
        "profile_count": len(profiles),
        "case_count": len(all_case_rows),
        "candidate_selection_basis": config["sweep_policy"]["candidate_selection_basis"],
        "transient_window_steps_after_target_change": transient_window,
        "settled_metric_thresholds": thresholds,
        "decision": decision,
        "top_candidates": ranking[:10],
        "outputs": config["outputs"]
    }

    write_json(config["outputs"]["summary_json"], summary)

    write_csv(
        config["outputs"]["candidate_ranking_csv"],
        ranking,
        [
            "rank",
            "candidate_id",
            "family",
            "kp",
            "ki",
            "kd",
            "case_count",
            "pass_count",
            "settled_warn_count",
            "explained_transient_count",
            "review_count",
            "unexplained_fail_count",
            "average_full_rmse",
            "average_full_mae",
            "average_full_max_abs_error",
            "average_settled_rmse",
            "average_settled_mae",
            "average_settled_max_abs_error",
            "worst_settled_max_abs_error",
            "average_rate_limit_fraction",
            "average_saturation_fraction"
        ]
    )

    write_csv(
        config["outputs"]["case_metrics_csv"],
        all_case_rows,
        [
            "candidate_id",
            "family",
            "kp",
            "ki",
            "kd",
            "profile",
            "calibrated_status",
            "full_rmse",
            "full_mae",
            "full_max_abs_error",
            "settled_rmse",
            "settled_mae",
            "settled_max_abs_error",
            "rate_limit_fraction",
            "saturation_fraction",
            "max_abs_error_step",
            "max_abs_error_is_rate_limited_transition",
            "abs_target_delta",
            "calibration_reasons"
        ]
    )

    write_csv(
        config["outputs"]["profile_metrics_csv"],
        profile_metrics,
        [
            "profile",
            "case_count",
            "pass_count",
            "settled_warn_count",
            "explained_transient_count",
            "review_count",
            "unexplained_fail_count",
            "best_settled_rmse",
            "best_candidate_id",
            "max_abs_target_delta"
        ]
    )

    write_readme(config["outputs"]["readme_md"], summary, ranking)
    write_experiment_doc(config["outputs"]["experiment_doc"], summary, ranking)

    print(f"Wrote {config['outputs']['summary_json']}")
    print(f"Wrote {config['outputs']['candidate_ranking_csv']}")
    print(f"Wrote {config['outputs']['case_metrics_csv']}")
    print(f"Wrote {config['outputs']['profile_metrics_csv']}")
    print(f"Wrote {config['outputs']['readme_md']}")
    print(f"Wrote {config['outputs']['experiment_doc']}")
    print(f"Decision: {decision['status']}")
    print(f"Selected candidate: {decision['selected_candidate_id']}")
    print(f"Accepted selected PID candidate for follow-up: {decision['accepted_selected_pid_candidate_for_followup']}")


if __name__ == "__main__":
    main()
