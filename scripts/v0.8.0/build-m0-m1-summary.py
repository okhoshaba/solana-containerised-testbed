#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path


M0_RUNS = [
    ("v0.8.0-M0-L32-R2", 32.0),
    ("v0.8.0-M0-L64", 64.0),
    ("v0.8.0-M0-L128", 128.0),
]

M1_RUNS = [
    "v0.8.0-M1-S32-64",
    "v0.8.0-M1-S64-128",
    "v0.8.0-M1-S32-128",
]


def load_json(path):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"ERROR: missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def metric(window, name):
    return window["metrics"].get(name, {})


def fmt(x, digits=6):
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def main():
    out_dir = Path("results/v0.8.0/summary")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "stage": "v0.8.0 dynamic load system identification",
        "scope": "M0 steady-state baselines and M1 upward step-response experiments",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "m0": [],
        "m1": [],
        "limitations": [
            "lat_p99 is missing in collect_csv outputs; current analysis is throughput-oriented.",
            "M1 settling-time estimates are limited by 5-second sampling resolution.",
            "Only upward step responses are included; downward/recovery dynamics require M2.",
        ],
    }

    for run_id, expected_rate in M0_RUNS:
        q = load_json(f"results/v0.8.0/runs/{run_id}/quality-summary.json")
        aw = q["analysis_window"]
        metrics = aw["metrics"]

        item = {
            "run_id": run_id,
            "expected_rate": expected_rate,
            "status": q["quality_verdict"]["status"],
            "warnings": q["quality_verdict"]["warnings"],
            "analysis_rows": aw["rows"],
            "analysis_duration_seconds": aw["time"]["duration_seconds"],
            "u_cmd_mean": metric(aw, "u_cmd").get("mean"),
            "u_ach_mean": metric(aw, "u_ach").get("mean"),
            "u_ach_std": metric(aw, "u_ach").get("std"),
            "u_ach_min": metric(aw, "u_ach").get("min"),
            "u_ach_max": metric(aw, "u_ach").get("max"),
            "err_per_sec_mean": metric(aw, "err_per_sec").get("mean"),
            "err_per_sec_max": metric(aw, "err_per_sec").get("max"),
            "inflight_mean": metric(aw, "inflight").get("mean"),
            "inflight_max": metric(aw, "inflight").get("max"),
            "lat_p99_count": metric(aw, "lat_p99").get("count"),
            "lat_p99_missing": metric(aw, "lat_p99").get("missing"),
        }
        summary["m0"].append(item)

    for run_id in M1_RUNS:
        s = load_json(f"results/v0.8.0/runs/{run_id}/step-response-summary.json")
        step = s["step"]
        response = s["response_metrics"]
        pre = s["pre_step"]["u_ach"]
        post_final = s["post_step"]["final_window_u_ach"]
        global_metrics = s["global_metrics"]

        item = {
            "run_id": run_id,
            "status": s["quality_verdict"]["status"],
            "warnings": s["quality_verdict"]["warnings"],
            "old_level": step["old_level"],
            "new_level": step["new_level"],
            "step_time_seconds": step["step_time_seconds"],
            "first_post_step_u_ach": step["first_post_step_u_ach"],
            "initial_post_step_error": step["initial_post_step_error"],
            "pre_step_u_ach_mean": pre["mean"],
            "pre_step_u_ach_std": pre["std"],
            "final_window_u_ach_mean": post_final["mean"],
            "final_window_u_ach_std": post_final["std"],
            "final_tracking_error": response["final_tracking_error"],
            "settling_time_seconds": response["settling_time_seconds"],
            "overshoot_abs": response["overshoot_abs"],
            "undershoot_abs": response["undershoot_abs"],
            "err_per_sec_mean": global_metrics["err_per_sec"]["mean"],
            "err_per_sec_max": global_metrics["err_per_sec"]["max"],
            "inflight_mean": global_metrics["inflight"]["mean"],
            "inflight_max": global_metrics["inflight"]["max"],
            "lat_p99_count": global_metrics["lat_p99"]["count"],
        }
        summary["m1"].append(item)

    all_m0_pass = all(x["status"] == "PASS" for x in summary["m0"])
    all_m1_pass = all(x["status"] == "PASS" for x in summary["m1"])
    all_err_zero = (
        all(x["err_per_sec_max"] == 0.0 for x in summary["m0"]) and
        all(x["err_per_sec_max"] == 0.0 for x in summary["m1"])
    )
    all_latency_missing = (
        all(x["lat_p99_count"] == 0 for x in summary["m0"]) and
        all(x["lat_p99_count"] == 0 for x in summary["m1"])
    )

    summary["overall_verdict"] = {
        "m0_complete": all_m0_pass,
        "m1_complete": all_m1_pass,
        "all_observed_err_per_sec_zero": all_err_zero,
        "latency_telemetry_missing": all_latency_missing,
        "status": "PASS" if all_m0_pass and all_m1_pass and all_err_zero else "WARN",
        "scientific_use": [
            "usable for throughput tracking and step-response analysis",
            "not yet sufficient for latency-response modelling",
            "M2 step-down/recovery is the next required experiment class",
        ],
    }

    out_json = out_dir / "v0.8.0-m0-m1-summary.json"
    out_md = out_dir / "v0.8.0-m0-m1-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append("# v0.8.0 M0+M1 summary")
    md.append("")
    md.append(f"- generated_at_utc: {summary['generated_at_utc']}")
    md.append(f"- overall_status: {summary['overall_verdict']['status']}")
    md.append(f"- M0 complete: {summary['overall_verdict']['m0_complete']}")
    md.append(f"- M1 complete: {summary['overall_verdict']['m1_complete']}")
    md.append(f"- all observed err_per_sec zero: {summary['overall_verdict']['all_observed_err_per_sec_zero']}")
    md.append(f"- latency telemetry missing: {summary['overall_verdict']['latency_telemetry_missing']}")
    md.append("")

    md.append("## M0 steady-state baselines")
    md.append("")
    md.append("| run | status | target | u_ach mean | u_ach std | err max | inflight max | lat_p99 count |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for x in summary["m0"]:
        md.append(
            f"| {x['run_id']} | {x['status']} | {fmt(x['expected_rate'], 0)} | "
            f"{fmt(x['u_ach_mean'])} | {fmt(x['u_ach_std'])} | "
            f"{fmt(x['err_per_sec_max'])} | {fmt(x['inflight_max'])} | {x['lat_p99_count']} |"
        )
    md.append("")

    md.append("## M1 upward step responses")
    md.append("")
    md.append("| run | status | step | first post-step u_ach | settling s | final error | overshoot | undershoot | err max |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for x in summary["m1"]:
        step_label = f"{fmt(x['old_level'], 0)}->{fmt(x['new_level'], 0)}"
        md.append(
            f"| {x['run_id']} | {x['status']} | {step_label} | "
            f"{fmt(x['first_post_step_u_ach'])} | {fmt(x['settling_time_seconds'])} | "
            f"{fmt(x['final_tracking_error'])} | {fmt(x['overshoot_abs'])} | "
            f"{fmt(x['undershoot_abs'])} | {fmt(x['err_per_sec_max'])} |"
        )
    md.append("")

    md.append("## Main conclusion")
    md.append("")
    md.append(
        "Within the confirmed safe range `lambda=32..128`, achieved throughput tracks "
        "the commanded steady-state and upward step profiles accurately. For all analysed "
        "M0 and M1 runs, `err_per_sec` remained zero and `inflight` stayed small. "
        "The observed settling time is one 5-second sampling interval, so finer sampling "
        "will be required later if sub-5-second transient dynamics are needed."
    )
    md.append("")
    md.append("## Limitations")
    md.append("")
    for item in summary["limitations"]:
        md.append(f"- {item}")
    md.append("")

    md.append("## Next experiment class")
    md.append("")
    md.append("`M2 step-down/recovery`: `128->64`, `64->32`, and `128->32`.")
    md.append("")

    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"summary_json: {out_json}")
    print(f"summary_md: {out_md}")
    print(json.dumps(summary["overall_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
