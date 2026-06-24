#!/usr/bin/env python3
import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def to_float(value):
    if value is None:
        return None
    value = str(value).strip()
    if value == "":
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(xs),
        "mean": sum(xs) / len(xs),
        "std": statistics.stdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "max": max(xs),
    }


def detect_transitions(rows):
    transitions = []
    prev = None
    for i, row in enumerate(rows):
        u = to_float(row.get("u_cmd"))
        if u != prev:
            transitions.append({
                "row_index": i,
                "t_sec": to_float(row.get("t_sec")),
                "u_cmd": u,
                "u_ach": to_float(row.get("u_ach")),
            })
            prev = u
    return transitions


def settling_time(post_rows, target, step_time, tolerance_abs, consecutive):
    ok_count = 0
    first_ok_time = None

    for row in post_rows:
        t = to_float(row.get("t_sec"))
        y = to_float(row.get("u_ach"))
        if t is None or y is None:
            ok_count = 0
            first_ok_time = None
            continue

        if abs(y - target) <= tolerance_abs:
            if ok_count == 0:
                first_ok_time = t
            ok_count += 1
            if ok_count >= consecutive:
                return first_ok_time - step_time
        else:
            ok_count = 0
            first_ok_time = None

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("collect_csv_path")
    parser.add_argument("--tolerance-abs", type=float, default=1.0)
    parser.add_argument("--consecutive", type=int, default=3)
    parser.add_argument("--post-final-window-samples", type=int, default=10)
    args = parser.parse_args()

    run_id = args.run_id
    csv_path = Path(args.collect_csv_path)

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit("ERROR: empty CSV")

    transitions = detect_transitions(rows)
    if len(transitions) < 2:
        raise SystemExit("ERROR: no step transition detected")

    step = transitions[1]
    step_index = step["row_index"]
    step_time = step["t_sec"]
    old_level = transitions[0]["u_cmd"]
    new_level = step["u_cmd"]

    pre_rows = rows[:step_index]
    post_rows = rows[step_index:]

    pre_y = [to_float(r.get("u_ach")) for r in pre_rows]
    post_y = [to_float(r.get("u_ach")) for r in post_rows]
    post_final_rows = post_rows[-args.post_final_window_samples:]
    post_final_y = [to_float(r.get("u_ach")) for r in post_final_rows]

    pre_stats = stats(pre_y)
    post_stats = stats(post_y)
    post_final_stats = stats(post_final_y)

    first_post = to_float(post_rows[0].get("u_ach")) if post_rows else None

    target = new_level
    response_min = post_stats["min"]
    response_max = post_stats["max"]

    overshoot = None
    undershoot = None
    if target is not None and response_max is not None:
        overshoot = response_max - target
    if target is not None and response_min is not None:
        undershoot = target - response_min

    settle = settling_time(
        post_rows=post_rows,
        target=target,
        step_time=step_time,
        tolerance_abs=args.tolerance_abs,
        consecutive=args.consecutive,
    )

    err_values = [to_float(r.get("err_per_sec")) for r in rows]
    inflight_values = [to_float(r.get("inflight")) for r in rows]
    lat_values = [to_float(r.get("lat_p99")) for r in rows]

    quality_warnings = []
    status = "PASS"

    if stats(err_values)["max"] not in (None, 0.0):
        status = "WARN"
        quality_warnings.append("non-zero err_per_sec observed")

    if stats(lat_values)["count"] == 0:
        quality_warnings.append("lat_p99 missing in collect_csv output")

    if settle is None:
        status = "WARN"
        quality_warnings.append("settling time not detected within tolerance")

    summary = {
        "run_id": run_id,
        "csv_path": str(csv_path),
        "rows": len(rows),
        "transitions": transitions,
        "step": {
            "old_level": old_level,
            "new_level": new_level,
            "step_row_index": step_index,
            "step_time_seconds": step_time,
            "first_post_step_u_ach": first_post,
            "initial_post_step_error": None if first_post is None else target - first_post,
        },
        "pre_step": {
            "rows": len(pre_rows),
            "u_ach": pre_stats,
        },
        "post_step": {
            "rows": len(post_rows),
            "u_ach": post_stats,
            "final_window_samples": args.post_final_window_samples,
            "final_window_u_ach": post_final_stats,
        },
        "response_metrics": {
            "tolerance_abs": args.tolerance_abs,
            "consecutive_samples_required": args.consecutive,
            "settling_time_seconds": settle,
            "overshoot_abs": overshoot,
            "undershoot_abs": undershoot,
            "final_tracking_error": None if post_final_stats["mean"] is None else target - post_final_stats["mean"],
        },
        "global_metrics": {
            "err_per_sec": stats(err_values),
            "inflight": stats(inflight_values),
            "lat_p99": stats(lat_values),
        },
        "quality_verdict": {
            "status": status,
            "warnings": quality_warnings,
        },
    }

    out_dir = Path("results/v0.8.0/runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "step-response-summary.json"
    out_md = out_dir / "step-response-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append(f"# v0.8.0 step-response summary: {run_id}")
    md.append("")
    md.append(f"- rows: {summary['rows']}")
    md.append(f"- step: {old_level} -> {new_level}")
    md.append(f"- step_time_seconds: {step_time}")
    md.append(f"- first_post_step_u_ach: {first_post}")
    md.append(f"- initial_post_step_error: {summary['step']['initial_post_step_error']}")
    md.append(f"- settling_time_seconds: {settle}")
    md.append(f"- final_tracking_error: {summary['response_metrics']['final_tracking_error']}")
    md.append(f"- overshoot_abs: {overshoot}")
    md.append(f"- undershoot_abs: {undershoot}")
    md.append(f"- verdict: {status}")
    md.append("")
    md.append("## Pre-step u_ach")
    md.append("")
    md.append(json.dumps(pre_stats, indent=2, sort_keys=True))
    md.append("")
    md.append("## Post-step u_ach")
    md.append("")
    md.append(json.dumps(post_stats, indent=2, sort_keys=True))
    md.append("")
    md.append("## Final-window u_ach")
    md.append("")
    md.append(json.dumps(post_final_stats, indent=2, sort_keys=True))
    md.append("")
    md.append("## Warnings")
    md.append("")
    if quality_warnings:
        for warning in quality_warnings:
            md.append(f"- {warning}")
    else:
        md.append("- none")

    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"step_response_json: {out_json}")
    print(f"step_response_md: {out_md}")
    print(json.dumps(summary["quality_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
