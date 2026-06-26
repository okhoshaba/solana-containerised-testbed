#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import statistics
from typing import Any, Dict, Iterable, List, Optional, Tuple


def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def first_present_column(headers: Iterable[str], candidates: List[str], purpose: str) -> str:
    header_set = set(headers)
    for c in candidates:
        if c in header_set:
            return c
    raise ValueError(f"No {purpose} column found. Candidates={candidates}, headers={sorted(header_set)}")


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required CSV file not found: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def solve_two_parameter_no_intercept(samples: List[Tuple[float, float, float]]) -> Tuple[float, float]:
    # Least squares for y_next = a_y * y_current + b_u * u_delayed.
    s_x1x1 = 0.0
    s_x1x2 = 0.0
    s_x2x2 = 0.0
    s_x1y = 0.0
    s_x2y = 0.0

    for y_current, u_delayed, y_next in samples:
        s_x1x1 += y_current * y_current
        s_x1x2 += y_current * u_delayed
        s_x2x2 += u_delayed * u_delayed
        s_x1y += y_current * y_next
        s_x2y += u_delayed * y_next

    det = s_x1x1 * s_x2x2 - s_x1x2 * s_x1x2
    if abs(det) < 1e-12:
        raise RuntimeError("Singular normal equation matrix during two-parameter fit.")

    a_y = (s_x1y * s_x2x2 - s_x2y * s_x1x2) / det
    b_u = (s_x1x1 * s_x2y - s_x1x2 * s_x1y) / det
    return a_y, b_u


def metrics(predicted: List[float], observed: List[float]) -> Dict[str, Any]:
    errors = [p - y for p, y in zip(predicted, observed)]
    abs_errors = [abs(e) for e in errors]
    sq_errors = [e * e for e in errors]

    mae = statistics.mean(abs_errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    bias = statistics.mean(errors)

    pct_errors = [abs((p - y) / y) for p, y in zip(predicted, observed) if y != 0]
    mape = statistics.mean(pct_errors) * 100.0 if pct_errors else None

    y_mean = statistics.mean(observed)
    ss_tot = sum((y - y_mean) ** 2 for y in observed)
    ss_res = sum((p - y) ** 2 for p, y in zip(predicted, observed))
    r2 = None if ss_tot == 0 else 1.0 - ss_res / ss_tot

    return {
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "mape": mape,
        "r2": r2
    }


def fit_for_delay(commands: List[float], observed: List[float], delay: int) -> Dict[str, Any]:
    samples = []
    for k in range(0, len(observed) - 1):
        delayed_index = k - delay
        if delayed_index < 0:
            continue
        samples.append((observed[k], commands[delayed_index], observed[k + 1]))

    if len(samples) < 3:
        raise RuntimeError(f"Not enough samples for delay={delay}: {len(samples)}")

    a_y, b_u = solve_two_parameter_no_intercept(samples)

    predicted = []
    actual = []
    for y_current, u_delayed, y_next in samples:
        y_hat_next = a_y * y_current + b_u * u_delayed
        predicted.append(y_hat_next)
        actual.append(y_next)

    m = metrics(predicted, actual)

    return {
        "delay_steps": delay,
        "a_y": a_y,
        "b_u": b_u,
        "sample_count": len(samples),
        "metrics": m,
        "predicted": predicted,
        "actual": actual
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    config = load_json(args.config)
    if not config.get("offline_only", False):
        raise RuntimeError("Config must explicitly set offline_only=true")

    os.makedirs(args.output_dir, exist_ok=True)

    replay_path = config["source_artifacts"]["real_replay_timeseries_path"]
    rows = read_csv_rows(replay_path)
    if not rows:
        raise RuntimeError(f"Replay CSV is empty: {replay_path}")

    columns = config["replay_columns"]
    headers = rows[0].keys()
    time_col = first_present_column(headers, columns["time_candidates"], "time")
    command_col = first_present_column(headers, columns["command_candidates"], "command")
    observed_col = first_present_column(headers, columns["observed_candidates"], "observed")

    clean = []
    for idx, row in enumerate(rows):
        t = to_float(row.get(time_col))
        u = to_float(row.get(command_col))
        y = to_float(row.get(observed_col))
        if u is None or y is None:
            continue
        clean.append({
            "row_index": idx,
            "time": float(idx) if t is None else t,
            "u": u,
            "y": y
        })

    if len(clean) < 10:
        raise RuntimeError(f"Not enough valid rows for model refit: {len(clean)}")

    commands = [r["u"] for r in clean]
    observed = [r["y"] for r in clean]

    delay_candidates = config["model_structure"]["delay_candidates"]
    fit_results = []
    failures = []

    for delay in delay_candidates:
        try:
            fit_results.append(fit_for_delay(commands, observed, int(delay)))
        except Exception as exc:
            failures.append({
                "delay_steps": int(delay),
                "error": str(exc)
            })

    if not fit_results:
        raise RuntimeError(f"No delay candidate could be fitted. Failures={failures}")

    fit_results.sort(key=lambda r: r["metrics"]["rmse"])
    best = fit_results[0]

    coefficients = {
        "stage": config["stage"],
        "title": config["title"],
        "offline_only": True,
        "model_type": "discrete_first_order_no_intercept",
        "equation": config["model_structure"]["equation"],
        "source_replay_path": replay_path,
        "time_column": time_col,
        "command_column": command_col,
        "observed_column": observed_col,
        "a_y": best["a_y"],
        "b_u": best["b_u"],
        "delay_steps": best["delay_steps"],
        "y0": observed[0],
        "sample_count": best["sample_count"],
        "metrics": best["metrics"],
        "all_delay_candidates": [
            {
                "delay_steps": r["delay_steps"],
                "a_y": r["a_y"],
                "b_u": r["b_u"],
                "sample_count": r["sample_count"],
                "metrics": r["metrics"]
            }
            for r in fit_results
        ],
        "failed_delay_candidates": failures
    }

    coefficients_path = os.path.join(args.output_dir, "refit-coefficients.json")
    summary_path = os.path.join(args.output_dir, "refit-summary.json")
    timeseries_path = os.path.join(args.output_dir, "refit-timeseries.csv")

    write_json(coefficients_path, coefficients)

    summary = {
        "stage": config["stage"],
        "decision": "REAL_REPLAY_MODEL_REFIT_COMPLETE",
        "offline_only": True,
        "actuator_applied": False,
        "source_replay_path": replay_path,
        "selected_model": {
            "a_y": best["a_y"],
            "b_u": best["b_u"],
            "delay_steps": best["delay_steps"],
            "y0": observed[0]
        },
        "metrics": best["metrics"],
        "outputs": {
            "coefficients_json": coefficients_path,
            "summary_json": summary_path,
            "timeseries_csv": timeseries_path
        }
    }
    write_json(summary_path, summary)

    # Write one-step fitted prediction series for the selected delay.
    delay = best["delay_steps"]
    a_y = best["a_y"]
    b_u = best["b_u"]

    with open(timeseries_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "row_index",
            "time_seconds",
            "u_cmd",
            "observed_y",
            "predicted_next_y",
            "actual_next_y",
            "one_step_error",
            "delay_steps",
            "actuator_applied"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for k in range(0, len(observed) - 1):
            delayed_index = k - delay
            if delayed_index < 0:
                continue
            pred = a_y * observed[k] + b_u * commands[delayed_index]
            actual = observed[k + 1]
            writer.writerow({
                "row_index": clean[k]["row_index"],
                "time_seconds": clean[k]["time"],
                "u_cmd": commands[delayed_index],
                "observed_y": observed[k],
                "predicted_next_y": pred,
                "actual_next_y": actual,
                "one_step_error": pred - actual,
                "delay_steps": delay,
                "actuator_applied": False
            })

    print(json.dumps({
        "stage": config["stage"],
        "decision": "REAL_REPLAY_MODEL_REFIT_COMPLETE",
        "coefficients_path": coefficients_path,
        "summary_path": summary_path,
        "timeseries_path": timeseries_path,
        "a_y": best["a_y"],
        "b_u": best["b_u"],
        "delay_steps": best["delay_steps"],
        "rmse": best["metrics"]["rmse"]
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
