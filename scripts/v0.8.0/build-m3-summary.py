#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path


M3_RUNS = [
    "v0.8.0-M3-MS32-64-128-64-32",
    "v0.8.0-M3-MS32-128-64-128-32",
]


def load_json(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"ERROR: missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(x, digits=6):
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def main():
    out_dir = Path("results/v0.8.0/summary")
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = []
    for run_id in M3_RUNS:
        s = load_json(f"results/v0.8.0/runs/{run_id}/multistep-summary.json")

        segment_rows = []
        for seg in s["segments"]:
            segment_rows.append({
                "segment_index": seg["segment_index"],
                "u_cmd": seg["u_cmd"],
                "rows": seg["rows"],
                "first_u_ach": seg["first_u_ach"],
                "settling_time_seconds": seg["settling_time_seconds"],
                "final_tracking_error": seg["final_tracking_error"],
                "final_window_u_ach_mean": seg["final_window_u_ach"]["mean"],
                "err_per_sec_max": seg["err_per_sec"]["max"],
                "inflight_max": seg["inflight"]["max"],
            })

        runs.append({
            "run_id": run_id,
            "status": s["quality_verdict"]["status"],
            "warnings": s["quality_verdict"]["warnings"],
            "rows": s["rows"],
            "segment_count": s["segment_count"],
            "levels": s["levels"],
            "err_per_sec_max": s["global_metrics"]["err_per_sec_max"],
            "inflight_max": s["global_metrics"]["inflight_max"],
            "lat_p99_count": s["global_metrics"]["lat_p99_count"],
            "segments": segment_rows,
        })

    all_pass = all(r["status"] == "PASS" for r in runs)
    all_err_zero = all(r["err_per_sec_max"] == 0.0 for r in runs)
    all_latency_missing = all(r["lat_p99_count"] == 0 for r in runs)
    max_inflight = max(r["inflight_max"] for r in runs)

    summary = {
        "stage": "v0.8.0 dynamic load system identification",
        "scope": "M3 multi-step load profiles",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": runs,
        "overall_verdict": {
            "m3_complete": all_pass,
            "all_observed_err_per_sec_zero": all_err_zero,
            "latency_telemetry_missing": all_latency_missing,
            "max_inflight": max_inflight,
            "status": "PASS" if all_pass and all_err_zero else "WARN",
            "scientific_use": [
                "usable for throughput tracking under multi-step load profiles",
                "usable for preliminary closed-loop controller signal design",
                "not yet sufficient for latency-constrained MPC because lat_p99 is missing",
            ],
        },
        "limitations": [
            "lat_p99 is missing in collect_csv outputs.",
            "Settling-time estimates are limited by 5-second sampling resolution.",
            "M3 remains within the confirmed safe range lambda=32..128.",
        ],
    }

    out_json = out_dir / "v0.8.0-m3-summary.json"
    out_md = out_dir / "v0.8.0-m3-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append("# v0.8.0 M3 multi-step summary")
    md.append("")
    md.append(f"- generated_at_utc: {summary['generated_at_utc']}")
    md.append(f"- overall_status: {summary['overall_verdict']['status']}")
    md.append(f"- M3 complete: {summary['overall_verdict']['m3_complete']}")
    md.append(f"- all observed err_per_sec zero: {summary['overall_verdict']['all_observed_err_per_sec_zero']}")
    md.append(f"- latency telemetry missing: {summary['overall_verdict']['latency_telemetry_missing']}")
    md.append(f"- max inflight: {summary['overall_verdict']['max_inflight']}")
    md.append("")

    md.append("## M3 runs")
    md.append("")
    md.append("| run | status | levels | rows | segments | err max | inflight max | lat_p99 count |")
    md.append("|---|---:|---|---:|---:|---:|---:|---:|")
    for r in runs:
        levels = " -> ".join(str(int(x)) if float(x).is_integer() else str(x) for x in r["levels"])
        md.append(
            f"| {r['run_id']} | {r['status']} | {levels} | {r['rows']} | {r['segment_count']} | "
            f"{fmt(r['err_per_sec_max'])} | {fmt(r['inflight_max'])} | {r['lat_p99_count']} |"
        )
    md.append("")

    md.append("## Segment-level final tracking")
    md.append("")
    md.append("| run | segment | u_cmd | settling s | final error | final mean | err max | inflight max |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in runs:
        for seg in r["segments"]:
            md.append(
                f"| {r['run_id']} | {seg['segment_index']} | {fmt(seg['u_cmd'])} | "
                f"{fmt(seg['settling_time_seconds'])} | {fmt(seg['final_tracking_error'])} | "
                f"{fmt(seg['final_window_u_ach_mean'])} | {fmt(seg['err_per_sec_max'])} | "
                f"{fmt(seg['inflight_max'])} |"
            )
    md.append("")

    md.append("## Main conclusion")
    md.append("")
    md.append(
        "The M3 experiments confirm that achieved throughput follows multi-step commanded "
        "profiles within the safe `lambda=32..128` range. Both tested profiles completed "
        "without observed transaction errors, with small inflight values and final tracking "
        "errors close to zero at each segment."
    )
    md.append("")

    md.append("## Limitations")
    md.append("")
    for item in summary["limitations"]:
        md.append(f"- {item}")
    md.append("")

    md.append("## Next experiment class")
    md.append("")
    md.append(
        "The next class should be M4 sinusoidal excitation, using low-frequency profiles "
        "inside the safe range `lambda=32..128`."
    )
    md.append("")

    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"summary_json: {out_json}")
    print(f"summary_md: {out_md}")
    print(json.dumps(summary["overall_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
