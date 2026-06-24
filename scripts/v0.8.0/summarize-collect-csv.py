#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
import statistics
import sys
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


def series_stats(values):
    xs = [x for x in values if x is not None]
    if not xs:
        return {
            "count": 0,
            "missing": len(values),
            "mean": None,
            "std": None,
            "min": None,
            "max": None,
        }

    return {
        "count": len(xs),
        "missing": len(values) - len(xs),
        "mean": sum(xs) / len(xs),
        "std": statistics.stdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "max": max(xs),
    }


def expected_rate_from_run_id(run_id):
    m = re.search(r"M0-L(\d+)", run_id)
    if not m:
        return None
    return float(m.group(1))


def compute_window(rows, columns, window_name, warmup_exclusion_seconds):
    t_values = [to_float(r.get("t_sec")) for r in rows]
    t_valid = [x for x in t_values if x is not None]

    intervals = []
    for a, b in zip(t_valid, t_valid[1:]):
        intervals.append(b - a)

    metrics = {}
    for name in ["u_cmd", "sent_total", "u_ach", "lat_p99", "inflight", "err_per_sec"]:
        if name in columns:
            metrics[name] = series_stats([to_float(r.get(name)) for r in rows])

    return {
        "window_name": window_name,
        "warmup_exclusion_seconds": warmup_exclusion_seconds,
        "rows": len(rows),
        "time": {
            "t_sec_first": min(t_valid) if t_valid else None,
            "t_sec_last": max(t_valid) if t_valid else None,
            "duration_seconds": (max(t_valid) - min(t_valid)) if t_valid else None,
            "interval_count": len(intervals),
            "interval_mean_seconds": sum(intervals) / len(intervals) if intervals else None,
            "interval_min_seconds": min(intervals) if intervals else None,
            "interval_max_seconds": max(intervals) if intervals else None,
        },
        "metrics": metrics,
    }


def quality_verdict(run_id, analysis_window):
    expected_rate = expected_rate_from_run_id(run_id)
    metrics = analysis_window["metrics"]
    warnings = []
    status = "PASS"

    rows = analysis_window["rows"]
    if rows < 100:
        status = "WARN"
        warnings.append("low analysis-window row count")

    u_cmd_mean = metrics.get("u_cmd", {}).get("mean")
    u_ach_mean = metrics.get("u_ach", {}).get("mean")
    err_mean = metrics.get("err_per_sec", {}).get("mean")
    err_max = metrics.get("err_per_sec", {}).get("max")
    inflight_max = metrics.get("inflight", {}).get("max")
    lat_count = metrics.get("lat_p99", {}).get("count")

    if expected_rate is not None and u_cmd_mean is not None:
        if abs(u_cmd_mean - expected_rate) > 0.5:
            status = "WARN"
            warnings.append("u_cmd mean differs from expected rate")

    if expected_rate is not None and u_ach_mean is not None:
        if abs(u_ach_mean - expected_rate) > 2.0:
            status = "WARN"
            warnings.append("u_ach mean differs from expected rate by more than 2 TPS")

    if err_mean is not None and err_mean > 0.01:
        status = "WARN"
        warnings.append("non-negligible mean err_per_sec")

    if err_max is not None and err_max > 0.1:
        status = "WARN"
        warnings.append("err_per_sec spike detected")

    if inflight_max is not None and inflight_max > 0:
        warnings.append("non-zero inflight observed")

    if lat_count == 0:
        warnings.append("lat_p99 missing in collect_csv output")

    return {
        "status": status,
        "warnings": warnings,
    }


def write_markdown(path, summary):
    analysis = summary["analysis_window"]
    metrics = analysis["metrics"]
    verdict = summary["quality_verdict"]

    lines = []
    lines.append(f"# v0.8.0 quality summary: {summary['run_id']}")
    lines.append("")
    lines.append(f"- total_rows: {summary['rows']}")
    lines.append(f"- analysis_warmup_exclusion_seconds: {analysis['warmup_exclusion_seconds']}")
    lines.append(f"- analysis_rows: {analysis['rows']}")
    lines.append(f"- analysis_duration_seconds: {analysis['time']['duration_seconds']}")
    lines.append(f"- analysis_interval_mean_seconds: {analysis['time']['interval_mean_seconds']}")
    lines.append(f"- verdict: {verdict['status']}")
    lines.append("")
    lines.append("## Analysis-window metrics")
    lines.append("")
    lines.append("| metric | count | missing | mean | std | min | max |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for name, st in metrics.items():
        lines.append(
            f"| {name} | {st['count']} | {st['missing']} | "
            f"{st['mean']} | {st['std']} | {st['min']} | {st['max']} |"
        )

    lines.append("")
    lines.append("## Warnings")
    lines.append("")
    if verdict["warnings"]:
        for warning in verdict["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("collect_csv_path")
    parser.add_argument("--warmup", type=float, default=30.0)
    args = parser.parse_args()

    run_id = args.run_id
    csv_path = Path(args.collect_csv_path)

    if not csv_path.exists():
        print(f"ERROR: missing CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        columns = reader.fieldnames or []

    if not rows:
        print(f"ERROR: no data rows in {csv_path}", file=sys.stderr)
        sys.exit(1)

    full_rows = rows
    analysis_rows = [
        r for r in rows
        if to_float(r.get("t_sec")) is not None and to_float(r.get("t_sec")) >= args.warmup
    ]

    if not analysis_rows:
        print("ERROR: no rows remain after warmup exclusion", file=sys.stderr)
        sys.exit(1)

    full_window = compute_window(
        full_rows,
        columns,
        "full_window",
        0.0,
    )

    analysis_window = compute_window(
        analysis_rows,
        columns,
        "analysis_window",
        args.warmup,
    )

    summary = {
        "run_id": run_id,
        "csv_path": str(csv_path),
        "columns": columns,
        "rows": len(rows),
        "full_window": full_window,
        "analysis_window": analysis_window,
    }

    summary["quality_verdict"] = quality_verdict(run_id, analysis_window)

    out_dir = Path("results/v0.8.0/runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "quality-summary.json"
    out_md = out_dir / "quality-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(out_md, summary)

    print(f"quality_json: {out_json}")
    print(f"quality_md: {out_md}")
    print(json.dumps(summary["quality_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
