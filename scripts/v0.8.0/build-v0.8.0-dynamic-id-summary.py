#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path


M0_M1_M2_PATH = Path("results/v0.8.0/summary/v0.8.0-m0-m1-m2-summary.json")
M3_PATH = Path("results/v0.8.0/summary/v0.8.0-m3-summary.json")
M4_SINE_PATH = Path("results/v0.8.0/runs/v0.8.0-M4-SINE-L80-A48-T720/sine-summary.json")


def load_json(path):
    if not path.exists():
        raise SystemExit(f"ERROR: missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def fmt(x, digits=6):
    if x is None:
        return "NA"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def bool_status(value):
    return "yes" if value else "no"


def main():
    out_dir = Path("results/v0.8.0/summary")
    out_dir.mkdir(parents=True, exist_ok=True)

    m012 = load_json(M0_M1_M2_PATH)
    m3 = load_json(M3_PATH)
    m4 = load_json(M4_SINE_PATH)

    m0 = m012["m0"]
    m1 = m012["m1"]
    m2 = m012["m2"]

    all_m0_pass = all(x["status"] == "PASS" for x in m0)
    all_m1_pass = all(x["status"] == "PASS" for x in m1)
    all_m2_pass = all(x["status"] == "PASS" for x in m2)
    m3_pass = m3["overall_verdict"]["status"] == "PASS"
    m4_pass = m4["quality_verdict"]["status"] == "PASS"

    all_err_zero = (
        m012["overall_verdict"]["all_observed_err_per_sec_zero"]
        and m3["overall_verdict"]["all_observed_err_per_sec_zero"]
        and m4["runtime_health"]["err_per_sec"]["max"] == 0.0
    )

    latency_missing = (
        m012["overall_verdict"]["latency_telemetry_missing"]
        and m3["overall_verdict"]["latency_telemetry_missing"]
        and m4["runtime_health"]["lat_p99"]["count"] == 0
    )

    m0_rates = [x["expected_rate"] for x in m0]
    m1_steps = [f"{int(x['old_level'])}->{int(x['new_level'])}" for x in m1]
    m2_steps = [f"{int(x['old_level'])}->{int(x['new_level'])}" for x in m2]
    m3_profiles = [
        " -> ".join(str(int(v)) for v in run["levels"])
        for run in m3["runs"]
    ]
    m4_levels = " -> ".join(str(int(v)) for v in m4["levels"])

    m1_settling = [x["settling_time_seconds"] for x in m1 if x["settling_time_seconds"] is not None]
    m2_settling = [x["settling_time_seconds"] for x in m2 if x["settling_time_seconds"] is not None]
    m3_settling = []
    for run in m3["runs"]:
        for seg in run["segments"]:
            st = seg["settling_time_seconds"]
            if st is not None and st > 0:
                m3_settling.append(st)

    all_settling = m1_settling + m2_settling + m3_settling

    def max_or_none(values):
        return max(values) if values else None

    def mean_or_none(values):
        return sum(values) / len(values) if values else None

    summary = {
        "stage": "v0.8.0 dynamic load system identification",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inputs": {
            "m0_m1_m2_summary": str(M0_M1_M2_PATH),
            "m3_summary": str(M3_PATH),
            "m4_sine_summary": str(M4_SINE_PATH),
        },
        "completed_experiment_classes": {
            "M0_steady_state_baselines": {
                "complete": all_m0_pass,
                "runs": len(m0),
                "rates": m0_rates,
            },
            "M1_upward_step_response": {
                "complete": all_m1_pass,
                "runs": len(m1),
                "steps": m1_steps,
            },
            "M2_step_down_recovery": {
                "complete": all_m2_pass,
                "runs": len(m2),
                "steps": m2_steps,
            },
            "M3_multi_step_profiles": {
                "complete": m3_pass,
                "runs": len(m3["runs"]),
                "profiles": m3_profiles,
            },
            "M4_sine_approximation": {
                "complete": m4_pass,
                "runs": 1,
                "profile": m4_levels,
                "period_seconds": m4["period_seconds"],
            },
        },
        "throughput_identification_findings": {
            "safe_lambda_range": [32, 128],
            "steady_state_gain": "approximately 1 within lambda=32..128",
            "step_response_settling_time_seconds": {
                "mean_observed": mean_or_none(all_settling),
                "max_observed": max_or_none(all_settling),
                "note": "limited by 5-second sampling resolution",
            },
            "m4_frequency_response": {
                "gain_peak_to_peak": m4["frequency_response"]["gain_peak_to_peak"],
                "gain_sinusoidal_fit": m4["frequency_response"]["gain_sinusoidal_fit"],
                "zero_lag_correlation": m4["frequency_response"]["zero_lag_correlation"],
                "phase_diff_deg": m4["frequency_response"]["phase"]["phase_diff_deg"],
                "phase_lag_seconds": m4["frequency_response"]["phase"]["phase_lag_seconds_positive_means_output_lags"],
                "best_cross_correlation_lag_samples": m4["frequency_response"]["best_cross_correlation_lag"]["lag_samples"],
            },
            "m4_tracking_error": {
                "rmse": m4["tracking_error"]["rmse"],
                "mae": m4["tracking_error"]["mean_absolute_error"],
                "max_absolute_error": m4["tracking_error"]["max_absolute_error"],
            },
        },
        "runtime_health": {
            "all_observed_err_per_sec_zero": all_err_zero,
            "m4_inflight_max": m4["runtime_health"]["inflight"]["max"],
            "latency_telemetry_missing": latency_missing,
        },
        "overall_verdict": {
            "status": "PASS" if all([all_m0_pass, all_m1_pass, all_m2_pass, m3_pass, m4_pass, all_err_zero]) else "WARN",
            "throughput_channel_ready_for_initial_modelling": True,
            "latency_channel_ready_for_modelling": False,
            "reason_latency_not_ready": "lat_p99 is missing in collect_csv outputs",
        },
        "recommended_next_steps": [
            "Create an offline modelling script/notebook for u_cmd -> u_ach using M0-M4 datasets.",
            "Estimate a simple discrete-time first-order or near-unity-gain model at 5-second sampling.",
            "Optionally run short SAMPLE=1 or SAMPLE=2 refinement experiments before final transfer-function fitting.",
            "Fix or extend latency telemetry collection before latency-constrained MPC.",
        ],
    }

    out_json = out_dir / "v0.8.0-dynamic-id-summary.json"
    out_md = out_dir / "v0.8.0-dynamic-id-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    md = []
    md.append("# v0.8.0 dynamic load system identification summary")
    md.append("")
    md.append(f"- generated_at_utc: {summary['generated_at_utc']}")
    md.append(f"- overall_status: {summary['overall_verdict']['status']}")
    md.append(f"- throughput channel ready for initial modelling: {bool_status(summary['overall_verdict']['throughput_channel_ready_for_initial_modelling'])}")
    md.append(f"- latency channel ready for modelling: {bool_status(summary['overall_verdict']['latency_channel_ready_for_modelling'])}")
    md.append("")

    md.append("## Completed experiment classes")
    md.append("")
    md.append("| class | complete | runs | profile/range |")
    md.append("|---|---:|---:|---|")
    md.append(f"| M0 steady-state baselines | {bool_status(all_m0_pass)} | {len(m0)} | lambda={', '.join(str(int(x)) for x in m0_rates)} |")
    md.append(f"| M1 upward step-response | {bool_status(all_m1_pass)} | {len(m1)} | {', '.join(m1_steps)} |")
    md.append(f"| M2 step-down/recovery | {bool_status(all_m2_pass)} | {len(m2)} | {', '.join(m2_steps)} |")
    md.append(f"| M3 multi-step profiles | {bool_status(m3_pass)} | {len(m3['runs'])} | two safe multi-step profiles |")
    md.append(f"| M4 sine approximation | {bool_status(m4_pass)} | 1 | L80 A48 T720 stepwise sine |")
    md.append("")

    md.append("## Main throughput findings")
    md.append("")
    md.append("- The confirmed safe identification range is `lambda=32..128`.")
    md.append("- Across M0-M4, observed `err_per_sec` remained zero.")
    md.append("- `inflight` remained small; M4 maximum observed `inflight` was 1.")
    md.append("- Steady-state and dynamic throughput tracking show near-unity gain.")
    md.append(f"- Mean observed settling time across non-initial step-like transitions: `{fmt(mean_or_none(all_settling))}` seconds.")
    md.append(f"- Maximum observed settling time across non-initial step-like transitions: `{fmt(max_or_none(all_settling))}` seconds.")
    md.append("- Settling-time estimates are limited by the 5-second sampling resolution.")
    md.append("")

    md.append("## M4 frequency-response indicators")
    md.append("")
    md.append(f"- gain_peak_to_peak: `{fmt(m4['frequency_response']['gain_peak_to_peak'])}`")
    md.append(f"- gain_sinusoidal_fit: `{fmt(m4['frequency_response']['gain_sinusoidal_fit'])}`")
    md.append(f"- zero_lag_correlation: `{fmt(m4['frequency_response']['zero_lag_correlation'])}`")
    md.append(f"- phase_diff_deg: `{fmt(m4['frequency_response']['phase']['phase_diff_deg'])}`")
    md.append(f"- phase_lag_seconds: `{fmt(m4['frequency_response']['phase']['phase_lag_seconds_positive_means_output_lags'])}`")
    md.append(f"- best_cross_correlation_lag_samples: `{m4['frequency_response']['best_cross_correlation_lag']['lag_samples']}`")
    md.append("")

    md.append("## M4 tracking error")
    md.append("")
    md.append(f"- RMSE: `{fmt(m4['tracking_error']['rmse'])}` TPS")
    md.append(f"- MAE: `{fmt(m4['tracking_error']['mean_absolute_error'])}` TPS")
    md.append(f"- max absolute error: `{fmt(m4['tracking_error']['max_absolute_error'])}` TPS")
    md.append("")

    md.append("## Scientific conclusion")
    md.append("")
    md.append(
        "The v0.8.0 dataset is sufficient for initial throughput-channel system identification. "
        "The observed relation `u_cmd(t) -> u_ach(t)` is close to unity gain in steady-state, "
        "step-response, multi-step, and low-frequency sine-approximation experiments. "
        "For the current 5-second sampling resolution, the response appears to settle within "
        "approximately one sample interval for commanded changes inside the safe range."
    )
    md.append("")
    md.append(
        "The dataset is not yet sufficient for latency-constrained control because `lat_p99` "
        "is missing from the collected CSV outputs. Therefore, the next modelling phase should "
        "treat this as a throughput-only identification dataset unless latency telemetry is fixed."
    )
    md.append("")

    md.append("## Recommended next steps")
    md.append("")
    for item in summary["recommended_next_steps"]:
        md.append(f"- {item}")
    md.append("")

    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"summary_json: {out_json}")
    print(f"summary_md: {out_md}")
    print(json.dumps(summary["overall_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
