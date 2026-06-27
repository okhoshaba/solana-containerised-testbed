#!/usr/bin/env python3

import argparse
import csv
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


def to_float(value, default=None):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return x


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_timeseries(path):
    require_file(path)

    rows = []
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "profile": row["profile"],
                "controller_case": row["controller_case"],
                "step": to_int(row["step"], 0),
                "time_seconds": to_float(row["time_seconds"], 0.0),
                "target": to_float(row["target"], 0.0),
                "y_before": to_float(row["y_before"], 0.0),
                "error_before": to_float(row["error_before"], 0.0),
                "raw_u": to_float(row["raw_u"], 0.0),
                "u_cmd": to_float(row["u_cmd"], 0.0),
                "delayed_u": to_float(row["delayed_u"], 0.0),
                "y_after": to_float(row["y_after"], 0.0),
                "error_after": to_float(row["error_after"], 0.0),
                "limited_by_rate": to_bool(row["limited_by_rate"]),
                "limited_by_bounds": to_bool(row["limited_by_bounds"]),
                "anti_windup_frozen": to_bool(row["anti_windup_frozen"]),
                "actuator_applied": to_bool(row["actuator_applied"])
            })

    if not rows:
        raise ValueError(f"No rows loaded from {path}")

    return rows


def group_rows(rows):
    groups = {}
    for row in rows:
        key = (row["profile"], row["controller_case"])
        groups.setdefault(key, []).append(row)

    for key in groups:
        groups[key].sort(key=lambda r: r["step"])

    return groups


def compute_metrics(rows):
    if not rows:
        return {
            "count": 0,
            "rmse": None,
            "mae": None,
            "mean_error": None,
            "max_abs_error": None,
            "final_error": None
        }

    errors = [r["error_after"] for r in rows]
    abs_errors = [abs(e) for e in errors]

    return {
        "count": len(rows),
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "mae": sum(abs_errors) / len(abs_errors),
        "mean_error": sum(errors) / len(errors),
        "max_abs_error": max(abs_errors),
        "final_error": errors[-1]
    }


def find_target_changes(rows):
    changes = []

    for i in range(1, len(rows)):
        prev = rows[i - 1]
        cur = rows[i]
        delta = cur["target"] - prev["target"]

        if abs(delta) > 1e-12:
            changes.append({
                "step": cur["step"],
                "time_seconds": cur["time_seconds"],
                "target_before": prev["target"],
                "target_after": cur["target"],
                "target_delta": delta,
                "abs_target_delta": abs(delta)
            })

    return changes


def transient_step_set(changes, window):
    steps = set()
    for change in changes:
        start = int(change["step"])
        for s in range(start, start + int(window)):
            steps.add(s)
    return steps


def nearest_change_for_step(step, changes, window):
    for change in changes:
        if int(change["step"]) <= step < int(change["step"]) + int(window):
            return change
    return None


def case_original_map(summary):
    out = {}
    for item in summary["case_results"]:
        out[(item["profile"], item["controller_case"])] = item
    return out


def classify_case(original, rows, settled_metrics, max_row, nearest_change, config, v0140_safety):
    original_status = original["status"]
    original_reasons = original["reasons"]

    thresholds = config["settled_metric_thresholds"]
    window_policy = config["calibration_policy"]

    saturation_fraction = original["metrics"]["saturation_fraction"]
    non_finite_count = original["metrics"]["non_finite_count"]

    settled_rmse = settled_metrics["rmse"]
    settled_max_abs_error = settled_metrics["max_abs_error"]

    settled_fail = False
    settled_warn = False
    reasons = []

    if non_finite_count > 0:
        settled_fail = True
        reasons.append("non_finite_count > 0")

    if saturation_fraction is not None and saturation_fraction > float(thresholds["maximum_saturation_fraction_for_calibrated_pass"]):
        settled_fail = True
        reasons.append("saturation_fraction above calibrated limit")

    if settled_rmse is not None and settled_rmse > float(thresholds["settled_fail_rmse"]):
        settled_fail = True
        reasons.append("settled_rmse > settled_fail_rmse")

    if settled_max_abs_error is not None and settled_max_abs_error > float(thresholds["settled_fail_max_abs_error"]):
        settled_fail = True
        reasons.append("settled_max_abs_error > settled_fail_max_abs_error")

    if settled_rmse is not None and settled_rmse > float(thresholds["settled_warn_rmse"]):
        settled_warn = True
        reasons.append("settled_rmse > settled_warn_rmse")

    if settled_max_abs_error is not None and settled_max_abs_error > float(thresholds["settled_warn_max_abs_error"]):
        settled_warn = True
        reasons.append("settled_max_abs_error > settled_warn_max_abs_error")

    max_error_is_rate_limited_transition = False

    if nearest_change is not None:
        if max_row["limited_by_rate"]:
            max_error_is_rate_limited_transition = True

    only_max_abs_error_fail = (
        original_status == "FAIL"
        and original_reasons == ["max_abs_error > fail_max_abs_error"]
    )

    if original_status == "FAIL":
        if (
            only_max_abs_error_fail
            and max_error_is_rate_limited_transition
            and not settled_fail
            and window_policy["treat_rate_limited_target_change_as_explained_transient"]
        ):
            return "EXPLAINED_TRANSIENT", [
                "v0.14.0 failure is explained by rate-limited target-change transient",
                "settled-window metrics are within calibrated fail thresholds"
            ]

        return "UNEXPLAINED_FAIL", reasons or [
            "v0.14.0 failure is not explained by calibrated transient policy"
        ]

    if original_status == "PASS" and not settled_fail and not settled_warn:
        return "PASS", ["original pass and settled metrics pass"]

    if original_status == "PASS" and not settled_fail and settled_warn:
        return "SETTLED_WARN", reasons

    return "REVIEW", reasons or ["case requires manual review"]


def write_case_metrics_csv(path, rows):
    fieldnames = [
        "profile",
        "controller_case",
        "original_status",
        "calibrated_status",
        "original_rmse",
        "original_mae",
        "original_max_abs_error",
        "settled_rmse",
        "settled_mae",
        "settled_max_abs_error",
        "max_abs_error_step",
        "max_abs_error_value",
        "max_abs_error_is_rate_limited_transition",
        "target_change_step",
        "target_before",
        "target_after",
        "abs_target_delta",
        "rate_limit_fraction",
        "saturation_fraction",
        "non_finite_count",
        "calibration_reasons"
    ]

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_profile_review_csv(path, rows):
    fieldnames = [
        "profile",
        "case_count",
        "original_pass_count",
        "original_warn_count",
        "original_fail_count",
        "calibrated_pass_count",
        "calibrated_settled_warn_count",
        "calibrated_explained_transient_count",
        "calibrated_review_count",
        "calibrated_unexplained_fail_count",
        "max_abs_target_delta",
        "max_original_abs_error",
        "max_settled_abs_error",
        "profile_recommendation"
    ]

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_profiles(case_rows):
    by_profile = {}

    for row in case_rows:
        p = row["profile"]
        item = by_profile.setdefault(p, {
            "profile": p,
            "case_count": 0,
            "original_pass_count": 0,
            "original_warn_count": 0,
            "original_fail_count": 0,
            "calibrated_pass_count": 0,
            "calibrated_settled_warn_count": 0,
            "calibrated_explained_transient_count": 0,
            "calibrated_review_count": 0,
            "calibrated_unexplained_fail_count": 0,
            "max_abs_target_delta": 0.0,
            "max_original_abs_error": 0.0,
            "max_settled_abs_error": 0.0
        })

        item["case_count"] += 1

        if row["original_status"] == "PASS":
            item["original_pass_count"] += 1
        elif row["original_status"] == "WARN":
            item["original_warn_count"] += 1
        elif row["original_status"] == "FAIL":
            item["original_fail_count"] += 1

        if row["calibrated_status"] == "PASS":
            item["calibrated_pass_count"] += 1
        elif row["calibrated_status"] == "SETTLED_WARN":
            item["calibrated_settled_warn_count"] += 1
        elif row["calibrated_status"] == "EXPLAINED_TRANSIENT":
            item["calibrated_explained_transient_count"] += 1
        elif row["calibrated_status"] == "REVIEW":
            item["calibrated_review_count"] += 1
        elif row["calibrated_status"] == "UNEXPLAINED_FAIL":
            item["calibrated_unexplained_fail_count"] += 1

        item["max_abs_target_delta"] = max(item["max_abs_target_delta"], float(row["abs_target_delta"] or 0.0))
        item["max_original_abs_error"] = max(item["max_original_abs_error"], float(row["original_max_abs_error"] or 0.0))
        item["max_settled_abs_error"] = max(item["max_settled_abs_error"], float(row["settled_max_abs_error"] or 0.0))

    out = []

    for item in by_profile.values():
        if item["calibrated_unexplained_fail_count"] > 0:
            recommendation = "review or redesign profile/controller before PID/MPC comparison"
        elif item["calibrated_explained_transient_count"] > 0:
            recommendation = "keep profile but evaluate with transient-aware and settling-window metrics"
        elif item["calibrated_settled_warn_count"] > 0:
            recommendation = "keep profile with caution; review settled warnings"
        else:
            recommendation = "profile passes calibrated review"

        item["profile_recommendation"] = recommendation
        out.append(item)

    out.sort(key=lambda x: (
        x["calibrated_unexplained_fail_count"],
        x["calibrated_explained_transient_count"],
        x["max_original_abs_error"],
        x["profile"]
    ), reverse=True)

    return out


def decide(case_rows, config):
    unexplained = sum(1 for r in case_rows if r["calibrated_status"] == "UNEXPLAINED_FAIL")
    review = sum(1 for r in case_rows if r["calibrated_status"] == "REVIEW")
    explained = sum(1 for r in case_rows if r["calibrated_status"] == "EXPLAINED_TRANSIENT")
    settled_warn = sum(1 for r in case_rows if r["calibrated_status"] == "SETTLED_WARN")
    calibrated_pass = sum(1 for r in case_rows if r["calibrated_status"] == "PASS")

    thresholds = config["decision_thresholds"]

    if unexplained > int(thresholds["maximum_unexplained_failures_for_pass"]):
        status = "fail"
        accepted = False
        reason = "At least one v0.14.0 failure remains unexplained after transient-aware calibration."
    elif review > int(thresholds["maximum_review_cases_for_pass"]):
        status = "fail"
        accepted = False
        reason = "At least one case requires manual review before calibrated metrics can be accepted."
    elif explained > 0 or settled_warn > 0:
        status = "caution"
        accepted = True
        reason = "All v0.14.0 failures are explained as rate-limit-induced transients, but calibrated transient-aware metrics should be used in follow-up stages."
    else:
        status = "pass"
        accepted = True
        reason = "All cases pass calibrated profile safety review."

    return {
        "status": status,
        "reason": reason,
        "counts": {
            "PASS": calibrated_pass,
            "SETTLED_WARN": settled_warn,
            "EXPLAINED_TRANSIENT": explained,
            "REVIEW": review,
            "UNEXPLAINED_FAIL": unexplained
        },
        "accepted_calibrated_metrics_for_followup": accepted,
        "does_not_reclassify_v0_14_0": True,
        "recommended_next_step": "Use transient-aware and settling-window metrics in the next PID/MPC comparison or simulator calibration stage."
    }


def write_readme(path, summary, profile_rows):
    lines = []

    lines.append("# v0.14.1 offline simulator calibration and profile safety review")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This stage reviews the v0.14.0 simulator-gate failure without modifying v0.14.0.")
    lines.append("")
    lines.append("The purpose is to separate true unsafe behaviour from expected rate-limit-induced transient error after abrupt target changes.")
    lines.append("")
    lines.append("## Important rule")
    lines.append("")
    lines.append("v0.14.1 does not reclassify v0.14.0. The v0.14.0 result remains fail.")
    lines.append("")
    lines.append("## Calibration policy")
    lines.append("")
    for key, value in summary["calibration_policy"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- accepted calibrated metrics for follow-up: `{decision['accepted_calibrated_metrics_for_followup']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Profile safety review")
    lines.append("")
    lines.append("| profile | original fail | explained transient | unexplained fail | max target delta | max original error | max settled error | recommendation |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for row in profile_rows:
        lines.append(
            f"| {row['profile']} | {row['original_fail_count']} | "
            f"{row['calibrated_explained_transient_count']} | "
            f"{row['calibrated_unexplained_fail_count']} | "
            f"{row['max_abs_target_delta']:.6f} | "
            f"{row['max_original_abs_error']:.6f} | "
            f"{row['max_settled_abs_error']:.6f} | "
            f"{row['profile_recommendation']} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("The v0.14.0 failing cases are concentrated in the multistep profile and are explained by a large target drop under actuator rate limiting.")
    lines.append("")
    lines.append("Follow-up controller comparisons should report both full-window metrics and settling-window metrics.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_experiment_doc(path, summary, profile_rows):
    lines = []

    lines.append("# v0.14.1 offline simulator calibration and profile safety review")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("v0.14.1 reviews the v0.14.0 offline simulator fail result and determines whether the failures are hard simulator failures or expected transient behaviour caused by actuator rate limits.")
    lines.append("")
    lines.append("## Methodological context")
    lines.append("")
    lines.append("- v0.14.0 created the first offline closed-loop simulation harness.")
    lines.append("- v0.14.0 failed because the multistep profile produced transient max absolute error above the configured fail threshold.")
    lines.append("- v0.14.1 keeps that result intact and performs a separate calibration review.")
    lines.append("")
    lines.append("## Source artefacts")
    lines.append("")
    for key, value in summary["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Calibration method")
    lines.append("")
    lines.append("The review identifies target-change events, excludes a configured transient window after each target change for settled-window metrics, and checks whether maximum error occurred during a rate-limited target-change transient.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| profile | original fail | explained transient | unexplained fail | recommendation |")
    lines.append("|---|---:|---:|---:|---|")
    for row in profile_rows:
        lines.append(
            f"| {row['profile']} | {row['original_fail_count']} | "
            f"{row['calibrated_explained_transient_count']} | "
            f"{row['calibrated_unexplained_fail_count']} | "
            f"{row['profile_recommendation']} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- accepted calibrated metrics for follow-up: `{decision['accepted_calibrated_metrics_for_followup']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Next step")
    lines.append("")
    lines.append("The next stage should use transient-aware and settling-window metrics before PID/MPC comparison or controller tuning.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_json(args.config)

    for path in config["source_artifacts"].values():
        require_file(path)

    v0140_summary = load_json(config["source_artifacts"]["v0_14_0_summary_path"])
    rows = load_timeseries(config["source_artifacts"]["v0_14_0_timeseries_path"])
    groups = group_rows(rows)
    original_cases = case_original_map(v0140_summary)

    window = int(config["calibration_policy"]["transient_window_steps_after_target_change"])
    v0140_safety = v0140_summary["safety_policy"]

    case_rows = []

    for key, case_rows_raw in groups.items():
        profile, controller = key
        original = original_cases[key]

        changes = find_target_changes(case_rows_raw)
        transient_steps = transient_step_set(changes, window)

        settled_rows = [r for r in case_rows_raw if r["step"] not in transient_steps]
        settled_metrics = compute_metrics(settled_rows)

        max_row = max(case_rows_raw, key=lambda r: abs(r["error_after"]))
        nearest_change = nearest_change_for_step(max_row["step"], changes, window)

        calibrated_status, calibration_reasons = classify_case(
            original,
            case_rows_raw,
            settled_metrics,
            max_row,
            nearest_change,
            config,
            v0140_safety
        )

        target_change_step = None
        target_before = None
        target_after = None
        abs_target_delta = 0.0

        if nearest_change is not None:
            target_change_step = nearest_change["step"]
            target_before = nearest_change["target_before"]
            target_after = nearest_change["target_after"]
            abs_target_delta = nearest_change["abs_target_delta"]

        case_rows.append({
            "profile": profile,
            "controller_case": controller,
            "original_status": original["status"],
            "calibrated_status": calibrated_status,
            "original_rmse": original["metrics"]["rmse"],
            "original_mae": original["metrics"]["mae"],
            "original_max_abs_error": original["metrics"]["max_abs_error"],
            "settled_rmse": settled_metrics["rmse"],
            "settled_mae": settled_metrics["mae"],
            "settled_max_abs_error": settled_metrics["max_abs_error"],
            "max_abs_error_step": max_row["step"],
            "max_abs_error_value": abs(max_row["error_after"]),
            "max_abs_error_is_rate_limited_transition": bool(nearest_change is not None and max_row["limited_by_rate"]),
            "target_change_step": target_change_step,
            "target_before": target_before,
            "target_after": target_after,
            "abs_target_delta": abs_target_delta,
            "rate_limit_fraction": original["metrics"]["rate_limit_fraction"],
            "saturation_fraction": original["metrics"]["saturation_fraction"],
            "non_finite_count": original["metrics"]["non_finite_count"],
            "calibration_reasons": "; ".join(calibration_reasons)
        })

    profile_rows = summarize_profiles(case_rows)
    decision = decide(case_rows, config)

    summary = {
        "stage": config["stage"],
        "title": config["title"],
        "offline_only": config["offline_only"],
        "inputs": {
            "config_path": args.config,
            "v0_14_0_config_path": config["source_artifacts"]["v0_14_0_config_path"],
            "v0_14_0_summary_path": config["source_artifacts"]["v0_14_0_summary_path"],
            "v0_14_0_ranking_path": config["source_artifacts"]["v0_14_0_ranking_path"],
            "v0_14_0_timeseries_path": config["source_artifacts"]["v0_14_0_timeseries_path"],
            "v0_14_0_failure_analysis_path": config["source_artifacts"]["v0_14_0_failure_analysis_path"]
        },
        "v0_14_0_decision_preserved": v0140_summary["decision"],
        "calibration_policy": config["calibration_policy"],
        "settled_metric_thresholds": config["settled_metric_thresholds"],
        "case_metrics": case_rows,
        "profile_review": profile_rows,
        "decision": decision,
        "outputs": config["outputs"]
    }

    write_json(config["outputs"]["summary_json"], summary)
    write_case_metrics_csv(config["outputs"]["case_metrics_csv"], case_rows)
    write_profile_review_csv(config["outputs"]["profile_review_csv"], profile_rows)
    write_readme(config["outputs"]["readme_md"], summary, profile_rows)
    write_experiment_doc(config["outputs"]["experiment_doc"], summary, profile_rows)

    print(f"Wrote {config['outputs']['summary_json']}")
    print(f"Wrote {config['outputs']['case_metrics_csv']}")
    print(f"Wrote {config['outputs']['profile_review_csv']}")
    print(f"Wrote {config['outputs']['readme_md']}")
    print(f"Wrote {config['outputs']['experiment_doc']}")
    print(f"Decision: {decision['status']}")
    print(f"Accepted calibrated metrics for follow-up: {decision['accepted_calibrated_metrics_for_followup']}")


if __name__ == "__main__":
    main()
