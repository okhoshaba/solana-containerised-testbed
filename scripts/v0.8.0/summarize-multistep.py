#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path


def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
        }
    mean = sum(values) / len(values)
    if len(values) > 1:
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    return {
        "count": len(values),
        "mean": mean,
        "std": std,
        "min": min(values),
        "max": max(values),
    }


def load_rows(path):
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row = dict(r)
            for key in ["t_sec", "u_cmd", "sent_total", "u_ach", "lat_p99", "inflight", "err_per_sec"]:
                row[key] = to_float(row.get(key))
            rows.append(row)
    if not rows:
        raise SystemExit(f"ERROR: no rows found in {path}")
    return rows


def segment_by_u_cmd(rows):
    segments = []
    current = None

    for idx, row in enumerate(rows):
        u_cmd = row["u_cmd"]
        if current is None or u_cmd != current["u_cmd"]:
            if current is not None:
                current["end_index"] = idx - 1
                current["end_t_sec"] = rows[idx - 1]["t_sec"]
                current["rows"] = rows[current["start_index"]:idx]
                segments.append(current)

            current = {
                "segment_index": len(segments),
                "u_cmd": u_cmd,
                "start_index": idx,
                "start_t_sec": row["t_sec"],
            }

    current["end_index"] = len(rows) - 1
    current["end_t_sec"] = rows[-1]["t_sec"]
    current["rows"] = rows[current["start_index"]:]
    segments.append(current)

    return segments


def first_settling_time(segment_rows, target, tolerance_abs, consecutive):
    for i in range(len(segment_rows)):
        window = segment_rows[i:i + consecutive]
        if len(window) < consecutive:
            return None
        ok = True
        for r in window:
            u_ach = r["u_ach"]
            if u_ach is None or abs(u_ach - target) > tolerance_abs:
                ok = False
                break
        if ok:
            return segment_rows[i]["t_sec"] - segment_rows[0]["t_sec"]
    return None


def analyse_segment(seg, tolerance_abs, consecutive, final_window_samples):
    rows = seg["rows"]
    target = seg["u_cmd"]
    u_ach_values = [r["u_ach"] for r in rows]
    err_values = [r["err_per_sec"] for r in rows]
    inflight_values = [r["inflight"] for r in rows]
    lat_values = [r["lat_p99"] for r in rows]

    final_rows = rows[-final_window_samples:] if len(rows) >= final_window_samples else rows
    final_u_ach_values = [r["u_ach"] for r in final_rows]
    final_stats = stats(final_u_ach_values)

    settling = first_settling_time(rows, target, tolerance_abs, consecutive)

    first_u_ach = rows[0]["u_ach"]
    if first_u_ach is None:
        initial_error = None
    else:
        initial_error = target - first_u_ach

    if final_stats["mean"] is None:
        final_error = None
    else:
        final_error = target - final_stats["mean"]

    if u_ach_values:
        valid = [v for v in u_ach_values if v is not None]
    else:
        valid = []

    if valid:
        max_u = max(valid)
        min_u = min(valid)
        if target >= first_u_ach if first_u_ach is not None else True:
            overshoot_abs = max(0.0, max_u - target)
            undershoot_abs = max(0.0, target - min_u)
        else:
            overshoot_abs = max(0.0, max_u - target)
            undershoot_abs = max(0.0, target - min_u)
    else:
        overshoot_abs = None
        undershoot_abs = None

    return {
        "segment_index": seg["segment_index"],
        "u_cmd": target,
        "start_index": seg["start_index"],
        "end_index": seg["end_index"],
        "start_t_sec": seg["start_t_sec"],
        "end_t_sec": seg["end_t_sec"],
        "duration_seconds": seg["end_t_sec"] - seg["start_t_sec"] if seg["end_t_sec"] is not None and seg["start_t_sec"] is not None else None,
        "rows": len(rows),
        "first_u_ach": first_u_ach,
        "initial_tracking_error": initial_error,
        "settling_time_seconds": settling,
        "final_tracking_error": final_error,
        "u_ach": stats(u_ach_values),
        "final_window_u_ach": final_stats,
        "err_per_sec": stats(err_values),
        "inflight": stats(inflight_values),
        "lat_p99": stats(lat_values),
        "overshoot_abs": overshoot_abs,
        "undershoot_abs": undershoot_abs,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("collect_csv")
    parser.add_argument("--tolerance-abs", type=float, default=1.0)
    parser.add_argument("--consecutive", type=int, default=3)
    parser.add_argument("--post-final-window-samples", type=int, default=10)
    args = parser.parse_args()

    rows = load_rows(args.collect_csv)
    segments = segment_by_u_cmd(rows)
    segment_summaries = [
        analyse_segment(seg, args.tolerance_abs, args.consecutive, args.post_final_window_samples)
        for seg in segments
    ]

    err_max_values = [
        s["err_per_sec"]["max"]
        for s in segment_summaries
        if s["err_per_sec"]["max"] is not None
    ]
    inflight_max_values = [
        s["inflight"]["max"]
        for s in segment_summaries
        if s["inflight"]["max"] is not None
    ]

    warnings = []
    if any(s["lat_p99"]["count"] == 0 for s in segment_summaries):
        warnings.append("lat_p99 missing in collect_csv output")
    if any(s["settling_time_seconds"] is None for s in segment_summaries):
        warnings.append("one or more segments did not settle within tolerance")
    if err_max_values and max(err_max_values) != 0.0:
        warnings.append("non-zero err_per_sec observed")
    if inflight_max_values and max(inflight_max_values) > 1.0:
        warnings.append("inflight exceeded 1")

    expected_segments = len(segments)
    status = "PASS"
    if expected_segments < 2:
        status = "FAIL"
    if err_max_values and max(err_max_values) != 0.0:
        status = "WARN"
    if any(s["settling_time_seconds"] is None for s in segment_summaries):
        status = "WARN"

    out_dir = Path(f"results/v0.8.0/runs/{args.run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_id": args.run_id,
        "csv_path": args.collect_csv,
        "rows": len(rows),
        "segment_count": len(segments),
        "levels": [s["u_cmd"] for s in segment_summaries],
        "tolerance_abs": args.tolerance_abs,
        "consecutive_samples_required": args.consecutive,
        "final_window_samples": args.post_final_window_samples,
        "segments": segment_summaries,
        "global_metrics": {
            "err_per_sec_max": max(err_max_values) if err_max_values else None,
            "inflight_max": max(inflight_max_values) if inflight_max_values else None,
            "lat_p99_count": sum(s["lat_p99"]["count"] for s in segment_summaries),
        },
        "quality_verdict": {
            "status": status,
            "warnings": warnings,
        },
    }

    out_json = out_dir / "multistep-summary.json"
    out_md = out_dir / "multistep-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append(f"# v0.8.0 multi-step summary: {args.run_id}")
    md.append("")
    md.append(f"- rows: {summary['rows']}")
    md.append(f"- segment_count: {summary['segment_count']}")
    md.append(f"- levels: {' -> '.join(str(int(x)) if float(x).is_integer() else str(x) for x in summary['levels'])}")
    md.append(f"- verdict: {status}")
    md.append(f"- err_per_sec max: {summary['global_metrics']['err_per_sec_max']}")
    md.append(f"- inflight max: {summary['global_metrics']['inflight_max']}")
    md.append(f"- lat_p99 count: {summary['global_metrics']['lat_p99_count']}")
    md.append("")
    md.append("## Segment summary")
    md.append("")
    md.append("| segment | u_cmd | rows | first u_ach | settling s | final error | final mean | err max | inflight max |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in segment_summaries:
        def f(x):
            if x is None:
                return "NA"
            if isinstance(x, float):
                return f"{x:.6f}"
            return str(x)

        md.append(
            f"| {s['segment_index']} | {f(s['u_cmd'])} | {s['rows']} | "
            f"{f(s['first_u_ach'])} | {f(s['settling_time_seconds'])} | "
            f"{f(s['final_tracking_error'])} | {f(s['final_window_u_ach']['mean'])} | "
            f"{f(s['err_per_sec']['max'])} | {f(s['inflight']['max'])} |"
        )
    md.append("")

    if warnings:
        md.append("## Warnings")
        md.append("")
        for w in warnings:
            md.append(f"- {w}")
        md.append("")

    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"multistep_json: {out_json}")
    print(f"multistep_md: {out_md}")
    print(json.dumps(summary["quality_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
