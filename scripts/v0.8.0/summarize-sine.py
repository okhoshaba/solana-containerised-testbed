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
        return {"count": 0, "mean": None, "std": None, "min": None, "max": None}
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


def median(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return values[mid]
    return 0.5 * (values[mid - 1] + values[mid])


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


def solve_3x3(a, b):
    m = [a[i][:] + [b[i]] for i in range(3)]

    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]

        div = m[col][col]
        for j in range(col, 4):
            m[col][j] /= div

        for r in range(3):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, 4):
                m[r][j] -= factor * m[col][j]

    return [m[i][3] for i in range(3)]


def fit_sinusoid(times, values, period_seconds, t0):
    pairs = [(t, v) for t, v in zip(times, values) if v is not None]
    if len(pairs) < 6:
        return None

    omega = 2.0 * math.pi / period_seconds

    xtx = [[0.0 for _ in range(3)] for _ in range(3)]
    xty = [0.0, 0.0, 0.0]

    for t, y in pairs:
        theta = omega * (t - t0)
        x = [1.0, math.sin(theta), math.cos(theta)]
        for i in range(3):
            xty[i] += x[i] * y
            for j in range(3):
                xtx[i][j] += x[i] * x[j]

    beta = solve_3x3(xtx, xty)
    if beta is None:
        return None

    offset, sin_coef, cos_coef = beta
    amplitude = math.sqrt(sin_coef ** 2 + cos_coef ** 2)
    phase_rad = math.atan2(cos_coef, sin_coef)

    fitted = []
    residuals = []
    for t, y in pairs:
        theta = omega * (t - t0)
        y_hat = offset + sin_coef * math.sin(theta) + cos_coef * math.cos(theta)
        fitted.append(y_hat)
        residuals.append(y - y_hat)

    rmse = math.sqrt(sum(e * e for e in residuals) / len(residuals))

    return {
        "offset": offset,
        "sin_coef": sin_coef,
        "cos_coef": cos_coef,
        "amplitude": amplitude,
        "phase_rad": phase_rad,
        "phase_deg": phase_rad * 180.0 / math.pi,
        "rmse_to_fitted_sine": rmse,
        "sample_count": len(pairs),
    }


def wrap_phase_rad(x):
    while x <= -math.pi:
        x += 2.0 * math.pi
    while x > math.pi:
        x -= 2.0 * math.pi
    return x


def correlation(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xvals = [p[0] for p in pairs]
    yvals = [p[1] for p in pairs]
    mx = sum(xvals) / len(xvals)
    my = sum(yvals) / len(yvals)
    vx = sum((x - mx) ** 2 for x in xvals)
    vy = sum((y - my) ** 2 for y in yvals)
    if vx <= 0.0 or vy <= 0.0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in pairs)
    return cov / math.sqrt(vx * vy)


def best_cross_correlation_lag(xs, ys, median_dt, max_lag_samples):
    best = None

    for lag in range(-max_lag_samples, max_lag_samples + 1):
        if lag >= 0:
            xw = xs[:len(xs) - lag] if lag else xs[:]
            yw = ys[lag:]
        else:
            xw = xs[-lag:]
            yw = ys[:len(ys) + lag]

        if len(xw) < 3 or len(yw) < 3:
            continue

        c = correlation(xw, yw)
        if c is None:
            continue

        if best is None or c > best["correlation"]:
            best = {
                "lag_samples": lag,
                "lag_seconds": lag * median_dt if median_dt is not None else None,
                "correlation": c,
            }

    return best


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("collect_csv")
    parser.add_argument("--period-seconds", type=float, default=720.0)
    parser.add_argument("--max-lag-samples", type=int, default=6)
    args = parser.parse_args()

    rows = load_rows(args.collect_csv)

    times = [r["t_sec"] for r in rows]
    t0 = times[0]
    t_rel = [t - t0 for t in times]
    u_cmd = [r["u_cmd"] for r in rows]
    u_ach = [r["u_ach"] for r in rows]
    err_per_sec = [r["err_per_sec"] for r in rows]
    inflight = [r["inflight"] for r in rows]
    lat_p99 = [r["lat_p99"] for r in rows]

    diffs = [times[i] - times[i - 1] for i in range(1, len(times))]
    median_dt = median(diffs)

    tracking_errors = [
        y - x if x is not None and y is not None else None
        for x, y in zip(u_cmd, u_ach)
    ]
    abs_tracking_errors = [
        abs(e) for e in tracking_errors if e is not None
    ]

    cmd_stats = stats(u_cmd)
    ach_stats = stats(u_ach)
    err_stats = stats(tracking_errors)

    cmd_amplitude_pp = None
    ach_amplitude_pp = None
    gain_peak_to_peak = None
    if cmd_stats["min"] is not None and cmd_stats["max"] is not None:
        cmd_amplitude_pp = 0.5 * (cmd_stats["max"] - cmd_stats["min"])
    if ach_stats["min"] is not None and ach_stats["max"] is not None:
        ach_amplitude_pp = 0.5 * (ach_stats["max"] - ach_stats["min"])
    if cmd_amplitude_pp and cmd_amplitude_pp > 0 and ach_amplitude_pp is not None:
        gain_peak_to_peak = ach_amplitude_pp / cmd_amplitude_pp

    cmd_fit = fit_sinusoid(times, u_cmd, args.period_seconds, t0)
    ach_fit = fit_sinusoid(times, u_ach, args.period_seconds, t0)

    phase = None
    if cmd_fit is not None and ach_fit is not None and cmd_fit["amplitude"] > 0:
        phase_diff_rad = wrap_phase_rad(ach_fit["phase_rad"] - cmd_fit["phase_rad"])
        omega = 2.0 * math.pi / args.period_seconds
        phase_lag_seconds = -phase_diff_rad / omega
        phase = {
            "phase_diff_rad": phase_diff_rad,
            "phase_diff_deg": phase_diff_rad * 180.0 / math.pi,
            "phase_lag_seconds_positive_means_output_lags": phase_lag_seconds,
        }

    fit_gain = None
    if cmd_fit is not None and ach_fit is not None and cmd_fit["amplitude"] > 0:
        fit_gain = ach_fit["amplitude"] / cmd_fit["amplitude"]

    zero_lag_corr = correlation(u_cmd, u_ach)
    best_lag = best_cross_correlation_lag(
        u_cmd,
        u_ach,
        median_dt=median_dt,
        max_lag_samples=args.max_lag_samples,
    )

    segments = segment_by_u_cmd(rows)
    segment_overview = []
    for seg in segments:
        vals = [r["u_ach"] for r in seg["rows"]]
        final_vals = vals[-3:] if len(vals) >= 3 else vals
        segment_overview.append({
            "segment_index": seg["segment_index"],
            "u_cmd": seg["u_cmd"],
            "rows": len(seg["rows"]),
            "start_t_sec": seg["start_t_sec"],
            "end_t_sec": seg["end_t_sec"],
            "final_u_ach_mean_last3": stats(final_vals)["mean"],
        })

    warnings = []
    if stats(lat_p99)["count"] == 0:
        warnings.append("lat_p99 missing in collect_csv output")
    if stats(err_per_sec)["max"] not in (None, 0.0):
        warnings.append("non-zero err_per_sec observed")
    if stats(inflight)["max"] is not None and stats(inflight)["max"] > 1.0:
        warnings.append("inflight exceeded 1")
    if cmd_fit is None or ach_fit is None:
        warnings.append("sinusoidal fit failed")

    status = "PASS"
    if stats(err_per_sec)["max"] not in (None, 0.0):
        status = "WARN"
    if cmd_fit is None or ach_fit is None:
        status = "WARN"

    out_dir = Path(f"results/v0.8.0/runs/{args.run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    fft_csv = out_dir / "sine-timeseries.csv"
    cmd_mean = cmd_stats["mean"]
    ach_mean = ach_stats["mean"]

    with fft_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "t_sec",
                "t_rel_sec",
                "u_cmd",
                "u_ach",
                "tracking_error",
                "u_cmd_demeaned",
                "u_ach_demeaned",
                "err_per_sec",
                "inflight",
            ],
        )
        writer.writeheader()
        for r, tr, te in zip(rows, t_rel, tracking_errors):
            writer.writerow({
                "t_sec": r["t_sec"],
                "t_rel_sec": tr,
                "u_cmd": r["u_cmd"],
                "u_ach": r["u_ach"],
                "tracking_error": te,
                "u_cmd_demeaned": r["u_cmd"] - cmd_mean if r["u_cmd"] is not None and cmd_mean is not None else None,
                "u_ach_demeaned": r["u_ach"] - ach_mean if r["u_ach"] is not None and ach_mean is not None else None,
                "err_per_sec": r["err_per_sec"],
                "inflight": r["inflight"],
            })

    summary = {
        "run_id": args.run_id,
        "csv_path": args.collect_csv,
        "rows": len(rows),
        "period_seconds": args.period_seconds,
        "median_sample_interval_seconds": median_dt,
        "segment_count": len(segments),
        "levels": [s["u_cmd"] for s in segments],
        "u_cmd": {
            "stats": cmd_stats,
            "amplitude_peak_to_peak": cmd_amplitude_pp,
            "sinusoidal_fit": cmd_fit,
        },
        "u_ach": {
            "stats": ach_stats,
            "amplitude_peak_to_peak": ach_amplitude_pp,
            "sinusoidal_fit": ach_fit,
        },
        "frequency_response": {
            "gain_peak_to_peak": gain_peak_to_peak,
            "gain_sinusoidal_fit": fit_gain,
            "phase": phase,
            "zero_lag_correlation": zero_lag_corr,
            "best_cross_correlation_lag": best_lag,
        },
        "tracking_error": {
            "stats": err_stats,
            "rmse": math.sqrt(sum(e * e for e in tracking_errors if e is not None) / len(abs_tracking_errors)) if abs_tracking_errors else None,
            "mean_absolute_error": sum(abs_tracking_errors) / len(abs_tracking_errors) if abs_tracking_errors else None,
            "max_absolute_error": max(abs_tracking_errors) if abs_tracking_errors else None,
        },
        "runtime_health": {
            "err_per_sec": stats(err_per_sec),
            "inflight": stats(inflight),
            "lat_p99": stats(lat_p99),
        },
        "segments": segment_overview,
        "fft_ready_timeseries_csv": str(fft_csv),
        "quality_verdict": {
            "status": status,
            "warnings": warnings,
        },
    }

    out_json = out_dir / "sine-summary.json"
    out_md = out_dir / "sine-summary.md"

    out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    def f(x):
        if x is None:
            return "NA"
        if isinstance(x, float):
            return f"{x:.6f}"
        return str(x)

    md = []
    md.append(f"# v0.8.0 sine-approximation summary: {args.run_id}")
    md.append("")
    md.append(f"- rows: {summary['rows']}")
    md.append(f"- period_seconds: {f(args.period_seconds)}")
    md.append(f"- median_sample_interval_seconds: {f(median_dt)}")
    md.append(f"- segment_count: {summary['segment_count']}")
    md.append(f"- verdict: {status}")
    md.append("")
    md.append("## Frequency-response indicators")
    md.append("")
    md.append(f"- u_cmd amplitude, peak-to-peak/2: {f(cmd_amplitude_pp)}")
    md.append(f"- u_ach amplitude, peak-to-peak/2: {f(ach_amplitude_pp)}")
    md.append(f"- gain, peak-to-peak: {f(gain_peak_to_peak)}")
    md.append(f"- gain, sinusoidal fit: {f(fit_gain)}")
    md.append(f"- zero-lag correlation: {f(zero_lag_corr)}")
    if phase is not None:
        md.append(f"- phase difference, deg: {f(phase['phase_diff_deg'])}")
        md.append(f"- phase lag seconds, positive means output lags: {f(phase['phase_lag_seconds_positive_means_output_lags'])}")
    if best_lag is not None:
        md.append(f"- best cross-correlation lag samples: {best_lag['lag_samples']}")
        md.append(f"- best cross-correlation lag seconds: {f(best_lag['lag_seconds'])}")
        md.append(f"- best cross-correlation: {f(best_lag['correlation'])}")
    md.append("")
    md.append("## Tracking error")
    md.append("")
    md.append(f"- RMSE: {f(summary['tracking_error']['rmse'])}")
    md.append(f"- MAE: {f(summary['tracking_error']['mean_absolute_error'])}")
    md.append(f"- max absolute error: {f(summary['tracking_error']['max_absolute_error'])}")
    md.append("")
    md.append("## Runtime health")
    md.append("")
    md.append(f"- err_per_sec max: {f(summary['runtime_health']['err_per_sec']['max'])}")
    md.append(f"- inflight max: {f(summary['runtime_health']['inflight']['max'])}")
    md.append(f"- lat_p99 count: {summary['runtime_health']['lat_p99']['count']}")
    md.append("")
    md.append("## FFT-ready dataset")
    md.append("")
    md.append(f"- {fft_csv}")
    md.append("")
    if warnings:
        md.append("## Warnings")
        md.append("")
        for w in warnings:
            md.append(f"- {w}")
        md.append("")

    out_md.write_text("\n".join(md), encoding="utf-8")

    print(f"sine_json: {out_json}")
    print(f"sine_md: {out_md}")
    print(f"sine_timeseries_csv: {fft_csv}")
    print(json.dumps(summary["quality_verdict"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
