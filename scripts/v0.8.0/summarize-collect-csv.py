#!/usr/bin/env python3
import csv
import json
import math
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
            "max": None
        }

    if len(xs) > 1:
        std = statistics.stdev(xs)
    else:
        std = 0.0

    return {
        "count": len(xs),
        "missing": len(values) - len(xs),
        "mean": sum(xs) / len(xs),
        "std": std,
        "min": min(xs),
        "max": max(xs)
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: summarize-collect-csv.py <run_id> <collect_csv_path>", file=sys.stderr)
        sys.exit(2)

    run_id = sys.argv[1]
    csv_path = Path(sys.argv[2])

    if not csv_path.exists():
        print(f"ERROR: missing CSV: {csv_path}", file=sys.stderr)
        sys.exit(1)

    rows = []
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print(f"ERROR: no data rows in {csv_path}", file=sys.stderr)
        sys.exit(1)

    fields = rows[0].keys()

    t_sec = [to_float(r.get("t_sec")) for r in rows]
    t_valid = [x for x in t_sec if x is not None]

    intervals = []
    for a, b in zip(t_valid, t_valid[1:]):
        intervals.append(b - a)

    metrics = {}
    for name in ["u_cmd", "sent_total", "u_ach", "lat_p99", "inflight", "err_per_sec"]:
        if name in fields:
            metrics[name] = series_stats([to_float(r.get(name)) for r in rows])

    duration = None
    if t_valid:
        duration = max(t_valid) - min(t_valid)

    summary = {
        "run_id": run_id,
        "csv_path": str(csv_path),
        "rows": len(rows),
        "columns": list(fields),
        "time": {
            "t_sec_first": min(t_valid) if t_valid else None,
            "t_sec_last": max(t_valid) if t_valid else None,
            "duration_seconds": duration,
            "interval_count": len(intervals),
            "interval_mean_seconds": sum(intervals) / len(intervals) if intervals else None,
            "interval_min_seconds": min(intervals) if intervals else None,
            "interval_max_seconds": max(intervals) if intervals else None
        },
        "metrics": metrics
    }

    u_cmd_mean = metrics.get("u_cmd", {}).get("mean")
    u_ach_mean = metrics.get("u_ach", {}).get("mean")
    err_mean = metrics.get("err_per_sec", {}).get("mean")
    err_max = metrics.get("err_per_sec", {}).get("max")
    inflight_max = metrics.get("inflight", {}).get("max")

    verdict = "PASS"
    warnings = []

    if len(rows) < 100:
        verdict = "WARN"
        warnings.append("low row count")

    if u_cmd_mean is not None and abs(u_cmd_mean - 32.0) > 0.5 and "M0-L32" in run_id:
        verdict = "WARN"
        warnings.append("u_cmd mean differs from expected lambda=32")

    if u_ach_mean is not None and "M0-L32" in run_id:
        if abs(u_ach_mean - 32.0) > 2.0:
            verdict = "WARN"
            warnings.append("u_ach mean differs from expected lambda=32 by more than 2 TPS")

    if err_mean is not None and err_mean > 0.01:
        verdict = "WARN"
        warnings.append("non-negligible mean err_per_sec")

    if err_max is not None and err_max > 0.1:
        verdict = "WARN"
        warnings.append("err_per_sec spike detected")

    if inflight_max is not None and inflight_max > 0:
        warnings.append("non-zero inflight observed")

    summary["quality_verdict"] = {
        "status": verdict,
        "warnings": warnings
    }

    out_dir = Path("results/v0.8.0/runs") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_json = out_dir / "quality-summary.json"
    out_md = out_dir / "quality-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append(f"# v0.8.0 quality summary: {run_id}")
    md.append("")
    md.append(f"- rows: {summary['rows']}")
    md.append(f"- duration_seconds: {summary['time']['duration_seconds']}")
    md.append(f"- interval_mean_seconds: {summary['time']['interval_mean_seconds']}")
    md.append(f"- verdict: {verdict}")
    md.append("")
    md.append("## Metrics")
    md.append("")
    md.append("| metric | count | missing | mean | std | min | max |")
    md.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, st in metrics.items():
        md.append(
            f"| {name} | {st['count']} | {st['missing']} | "
            f"{st['mean']} | {st['std']} | {st['min']} | {st['max']} |"
        )
    md.append("")
    md.append("## Warnings")
    md.append("")
    if warnings:
        for w in warnings:
            md.append(f"- {w}")
    else:
        md.append("- none")

    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"quality_json: {out_json}")
    print(f"quality_md: {out_md}")
    print(json.dumps(summary["quality_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
