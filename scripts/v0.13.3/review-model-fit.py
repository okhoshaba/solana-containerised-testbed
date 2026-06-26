#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v0.13.3"


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def mae(errors: list[float]) -> float | None:
    if not errors:
        return None
    return sum(abs(e) for e in errors) / len(errors)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]

    denom_x = math.sqrt(sum(v * v for v in dx))
    denom_y = math.sqrt(sum(v * v for v in dy))
    if denom_x == 0.0 or denom_y == 0.0:
        return None

    return sum(a * b for a, b in zip(dx, dy)) / (denom_x * denom_y)


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float | None]:
    if len(xs) != len(ys) or len(xs) < 2:
        return {"slope": None, "intercept": None}

    mx = statistics.mean(xs)
    my = statistics.mean(ys)

    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0.0:
        return {"slope": None, "intercept": None}

    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    intercept = my - slope * mx
    return {"slope": slope, "intercept": intercept}


def metrics_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [
        row for row in rows
        if row.get("model_fit_u_ach") is not None
        and row.get("model_fit_y_hat") is not None
        and row.get("model_fit_error_u_ach_minus_y_hat") is not None
    ]

    errors = [float(row["model_fit_error_u_ach_minus_y_hat"]) for row in valid]
    abs_errors = [abs(value) for value in errors]
    achieved = [float(row["model_fit_u_ach"]) for row in valid]
    predicted = [float(row["model_fit_y_hat"]) for row in valid]

    signal_range = (max(achieved) - min(achieved)) if achieved else None
    mean_abs_achieved = statistics.mean(abs(value) for value in achieved) if achieved else None
    bias = statistics.mean(errors) if errors else None

    result = {
        "rows": len(rows),
        "valid_prediction_rows": len(valid),
        "mae": mae(errors),
        "rmse": rmse(errors),
        "bias": bias,
        "error_stddev": stdev(errors),
        "mean_abs_error": mean(abs_errors),
        "max_abs_error": max(abs_errors) if abs_errors else None,
        "underestimate_count": sum(1 for error in errors if error > 0),
        "overestimate_count": sum(1 for error in errors if error < 0),
        "zero_error_count": sum(1 for error in errors if error == 0),
        "underestimate_fraction": (sum(1 for error in errors if error > 0) / len(errors)) if errors else None,
        "achieved_min": min(achieved) if achieved else None,
        "achieved_max": max(achieved) if achieved else None,
        "achieved_mean": mean(achieved),
        "predicted_min": min(predicted) if predicted else None,
        "predicted_max": max(predicted) if predicted else None,
        "predicted_mean": mean(predicted),
        "signal_range": signal_range,
        "mean_abs_achieved": mean_abs_achieved,
        "rmse_to_signal_range": (rmse(errors) / signal_range) if errors and signal_range and signal_range > 0 else None,
        "mae_to_mean_abs_achieved": (mae(errors) / mean_abs_achieved) if errors and mean_abs_achieved and mean_abs_achieved > 0 else None,
        "abs_bias_to_mean_abs_achieved": (abs(bias) / mean_abs_achieved) if bias is not None and mean_abs_achieved and mean_abs_achieved > 0 else None,
        "pearson_correlation_predicted_vs_achieved": pearson(predicted, achieved),
        "linear_calibration_achieved_from_predicted": linear_fit(predicted, achieved),
    }

    return result


def classify_error(error: float | None) -> str:
    if error is None:
        return "missing"
    if error > 0:
        return "underestimate"
    if error < 0:
        return "overestimate"
    return "exact"


def enriched_timeseries(
    rows: list[dict[str, str]],
    achieved_column: str,
    predicted_column: str,
    command_column: str,
    source_time_column: str,
    early_rows: int,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        u_ach = parse_float(row.get(achieved_column))
        y_hat = parse_float(row.get(predicted_column))
        u_cmd = parse_float(row.get(command_column))
        source_time = parse_float(row.get(source_time_column))

        error = None
        abs_error = None
        squared_error = None

        if u_ach is not None and y_hat is not None:
            error = u_ach - y_hat
            abs_error = abs(error)
            squared_error = error * error

        phase = "early_transient" if index < early_rows else "later_replay"

        enriched = dict(row)
        enriched.update(
            {
                "model_fit_row_index": index,
                "model_fit_phase": phase,
                "model_fit_u_cmd": u_cmd,
                "model_fit_u_ach": u_ach,
                "model_fit_y_hat": y_hat,
                "model_fit_source_time_seconds": source_time,
                "model_fit_error_u_ach_minus_y_hat": error,
                "model_fit_abs_error": abs_error,
                "model_fit_squared_error": squared_error,
                "model_fit_error_class": classify_error(error),
                "model_fit_controller_claim_safe": False,
            }
        )
        output.append(enriched)

    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_pass(metric_value: float | None, threshold: float, mode: str) -> bool:
    if metric_value is None:
        return False
    if mode == "le":
        return metric_value <= threshold
    if mode == "ge_abs":
        return abs(metric_value) >= threshold
    raise ValueError(mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    root = repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path

    cfg = read_json(config_path)
    if cfg.get("offline_only") is not True:
        raise ValueError("v0.13.3 config must set offline_only=true")

    input_cfg = cfg["input"]
    analysis_cfg = cfg["analysis"]

    shadow_summary_path = root / input_cfg["real_replay_shadow_summary"]
    shadow_timeseries_path = root / input_cfg["real_replay_shadow_timeseries"]

    shadow_summary = read_json(shadow_summary_path)
    fieldnames, raw_rows = read_csv_rows(shadow_timeseries_path)

    achieved_column = input_cfg["achieved_column"]
    predicted_column = input_cfg["predicted_column"]
    command_column = input_cfg["command_column"]
    source_time_column = input_cfg["source_time_column"]

    required_columns = [achieved_column, predicted_column, command_column]
    missing_columns = [name for name in required_columns if name not in fieldnames]
    if missing_columns:
        raise ValueError(f"Missing required columns in input timeseries: {missing_columns}")

    early_rows = max(1, int(math.ceil(len(raw_rows) * float(analysis_cfg["early_fraction"])))) if raw_rows else 0

    enriched = enriched_timeseries(
        raw_rows,
        achieved_column,
        predicted_column,
        command_column,
        source_time_column,
        early_rows,
    )

    overall = metrics_for_rows(enriched)
    early = metrics_for_rows(enriched[:early_rows])
    later = metrics_for_rows(enriched[early_rows:])

    checks = {
        "minimum_rows": overall["valid_prediction_rows"] >= int(analysis_cfg["minimum_rows"]),
        "rmse_to_signal_range": is_pass(
            overall["rmse_to_signal_range"],
            float(analysis_cfg["acceptable_rmse_to_signal_range"]),
            "le",
        ),
        "mae_to_mean_abs_achieved": is_pass(
            overall["mae_to_mean_abs_achieved"],
            float(analysis_cfg["acceptable_mae_to_mean_abs_achieved"]),
            "le",
        ),
        "abs_correlation": is_pass(
            overall["pearson_correlation_predicted_vs_achieved"],
            float(analysis_cfg["minimum_abs_correlation"]),
            "ge_abs",
        ),
        "abs_bias_to_mean_abs_achieved": is_pass(
            overall["abs_bias_to_mean_abs_achieved"],
            float(analysis_cfg["maximum_abs_bias_to_mean_abs_achieved"]),
            "le",
        ),
    }

    fit_quality_pass = all(checks.values())

    if overall["valid_prediction_rows"] < int(analysis_cfg["minimum_rows"]):
        decision = "MODEL_FIT_SANITY_REVIEW_INSUFFICIENT_DATA"
        controller_claim_readiness = "NOT_READY_FOR_CONTROLLER_CLAIMS"
        decision_reason = "Not enough valid prediction rows were available for model-fit review."
    elif fit_quality_pass:
        decision = "MODEL_FIT_SANITY_REVIEW_COMPLETE"
        controller_claim_readiness = "MODEL_FIT_PASSES_BASIC_SANITY_THRESHOLDS"
        decision_reason = "The current model passed the configured basic sanity thresholds."
    else:
        decision = "MODEL_FIT_WEAK_BUT_PIPELINE_VALID"
        controller_claim_readiness = "NOT_READY_FOR_CONTROLLER_CLAIMS"
        decision_reason = "The real replay pipeline is valid, but the current plant model does not pass all configured fit-quality thresholds."

    output_dir = root / cfg["output"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    timeseries_path = output_dir / cfg["output"]["timeseries_csv"]
    summary_path = output_dir / cfg["output"]["summary_json"]

    write_csv(timeseries_path, enriched)

    summary = {
        "version": VERSION,
        "stage": cfg["stage"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "decision_reason": decision_reason,
        "controller_claim_readiness": controller_claim_readiness,
        "offline_only": True,
        "input": {
            "shadow_summary": str(shadow_summary_path.relative_to(root)),
            "shadow_timeseries": str(shadow_timeseries_path.relative_to(root)),
            "input_fieldnames": fieldnames,
            "rows": len(raw_rows),
            "achieved_column": achieved_column,
            "predicted_column": predicted_column,
            "command_column": command_column,
            "source_time_column": source_time_column,
            "v0.13.2_decision": shadow_summary.get("decision"),
            "v0.13.2_dataset": shadow_summary.get("real_replay_dataset"),
            "v0.13.2_timebase": shadow_summary.get("timebase"),
        },
        "thresholds": analysis_cfg,
        "checks": checks,
        "metrics": {
            "overall": overall,
            "early_transient": early,
            "later_replay": later,
        },
        "model_interpretation": {
            "positive_prediction_error_means": "u_ach_replay is greater than y_hat, so the model underestimates achieved output.",
            "negative_prediction_error_means": "u_ach_replay is less than y_hat, so the model overestimates achieved output.",
            "current_model_status": "placeholder_or_preliminary_plant_coefficients" if not fit_quality_pass else "passes_basic_sanity_thresholds",
            "controller_claim_warning": "Do not claim PID or MPC controller validity from this model fit." if not fit_quality_pass else "Basic fit sanity passed, but this is still offline-only evidence.",
        },
        "safety_constraints": {
            "kubectl_invoked": False,
            "kubernetes_modified": False,
            "live_controller_started": False,
            "transaction_load_generated": False,
            "controller_recommendations_applied": False,
            "closed_loop_control_executed": False,
            "offline_only": True,
        },
        "outputs": {
            "summary_json": str(summary_path.relative_to(root)),
            "timeseries_csv": str(timeseries_path.relative_to(root)),
        },
        "recommended_next_step": "Identify or refit a discrete-time plant model from the real v0.8.0 replay data before making controller-quality claims.",
    }

    write_json(summary_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
