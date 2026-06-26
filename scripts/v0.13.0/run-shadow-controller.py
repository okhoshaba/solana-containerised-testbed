#!/usr/bin/env python3
"""
v0.13.0 closed-loop shadow-mode controller validation.

This runner is intentionally offline-only.

It does not:
- call kubectl;
- modify Kubernetes;
- start a live controller;
- change transaction load;
- apply controller output.

It reads replay data when available, otherwise falls back to a deterministic
synthetic replay profile. It writes CSV and JSON outputs for reproducibility.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v0.13.0"
STAGE = "closed-loop shadow-mode controller validation"


def repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalise_name(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


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


def choose_column(fieldnames: list[str], candidates: list[str]) -> str | None:
    by_norm = {normalise_name(name): name for name in fieldnames}
    for candidate in candidates:
        key = normalise_name(candidate)
        if key in by_norm:
            return by_norm[key]
    return None


def load_replay_csv(root: Path, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    input_cfg = cfg["input"]
    command_candidates = input_cfg.get("command_column_candidates", [])
    achieved_candidates = input_cfg.get("achieved_column_candidates", [])
    max_rows = int(input_cfg.get("max_rows", 600))

    candidate_files: list[Path] = []
    for pattern in input_cfg.get("replay_search_globs", []):
        for match in glob.glob(str(root / pattern), recursive=True):
            path = Path(match)
            if path.is_file():
                candidate_files.append(path)

    candidate_files = sorted(set(candidate_files))

    for path in candidate_files:
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    continue

                u_col = choose_column(reader.fieldnames, command_candidates)
                y_col = choose_column(reader.fieldnames, achieved_candidates)

                if u_col is None:
                    continue

                rows: list[dict[str, Any]] = []
                for index, row in enumerate(reader):
                    if len(rows) >= max_rows:
                        break

                    u_cmd = parse_float(row.get(u_col))
                    if u_cmd is None:
                        continue

                    u_ach = parse_float(row.get(y_col)) if y_col else None

                    rows.append(
                        {
                            "step": len(rows),
                            "time_seconds": float(len(rows)),
                            "u_cmd": u_cmd,
                            "u_ach": u_ach,
                            "source_file": str(path.relative_to(root)),
                        }
                    )

                if rows:
                    meta = {
                        "input_mode": "replay_csv",
                        "source_file": str(path.relative_to(root)),
                        "command_column": u_col,
                        "achieved_column": y_col,
                        "candidate_files_checked": len(candidate_files),
                    }
                    return rows, meta
        except UnicodeDecodeError:
            continue
        except OSError:
            continue

    return [], {
        "input_mode": "none_found",
        "candidate_files_checked": len(candidate_files),
        "source_file": None,
        "command_column": None,
        "achieved_column": None,
    }


def synthetic_replay(max_rows: int = 240) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    levels = [0.0, 50.0, 100.0, 150.0, 100.0, 50.0]
    segment = max(1, max_rows // len(levels))

    rows: list[dict[str, Any]] = []
    y = 0.0

    for level in levels:
        for _ in range(segment):
            if len(rows) >= max_rows:
                break
            y = 0.90 * y + 0.10 * level
            rows.append(
                {
                    "step": len(rows),
                    "time_seconds": float(len(rows)),
                    "u_cmd": level,
                    "u_ach": y,
                    "source_file": "synthetic_profile",
                }
            )

    meta = {
        "input_mode": "synthetic_replay",
        "source_file": "synthetic_profile",
        "command_column": "u_cmd",
        "achieved_column": "u_ach",
        "candidate_files_checked": 0,
    }
    return rows, meta


def clamp(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


def rmse(errors: list[float]) -> float | None:
    if not errors:
        return None
    return math.sqrt(sum(e * e for e in errors) / len(errors))


def mae(errors: list[float]) -> float | None:
    if not errors:
        return None
    return sum(abs(e) for e in errors) / len(errors)


def run_shadow_simulation(rows: list[dict[str, Any]], cfg: dict[str, Any], input_meta: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sim_cfg = cfg["simulation"]
    plant = sim_cfg["plant"]
    ctrl = cfg["controller"]

    sample_time = float(sim_cfg["sample_time_seconds"])
    a_y = float(plant["a_y"])
    b_u = float(plant["b_u"])
    delay_steps = int(plant.get("delay_steps", 1))
    plant_min = float(plant.get("output_min", 0.0))
    plant_max = float(plant.get("output_max", 1000000000.0))

    mode = str(ctrl.get("mode", "P")).upper()
    setpoint = float(ctrl["setpoint"])
    kp = float(ctrl.get("kp", 0.0))
    ki = float(ctrl.get("ki", 0.0))
    kd = float(ctrl.get("kd", 0.0))
    output_min = float(ctrl.get("output_min", 0.0))
    output_max = float(ctrl.get("output_max", 1000.0))
    rate_limit = float(ctrl.get("rate_limit_per_step", output_max))
    u_recommended_prev = float(ctrl.get("initial_output", 0.0))

    y_hat = float(sim_cfg.get("initial_y_hat", 0.0))
    u_history = [0.0 for _ in range(max(delay_steps, 0) + 1)]

    integral = 0.0
    previous_error = 0.0
    output_rows: list[dict[str, Any]] = []
    prediction_errors: list[float] = []

    for row in rows:
        u_cmd = float(row["u_cmd"])
        u_history.append(u_cmd)

        delayed_index = -1 - max(delay_steps, 0)
        delayed_u = u_history[delayed_index]

        y_hat = a_y * y_hat + b_u * delayed_u
        y_hat = clamp(y_hat, plant_min, plant_max)

        error = setpoint - y_hat

        if mode == "P":
            controller_delta = kp * error
        elif mode == "PI":
            integral += error * sample_time
            controller_delta = kp * error + ki * integral
        elif mode == "PID":
            integral += error * sample_time
            derivative = (error - previous_error) / sample_time if sample_time > 0 else 0.0
            controller_delta = kp * error + ki * integral + kd * derivative
        else:
            controller_delta = 0.0

        raw_recommendation = u_recommended_prev + controller_delta

        limited_high = u_recommended_prev + rate_limit
        limited_low = u_recommended_prev - rate_limit
        rate_limited_recommendation = clamp(raw_recommendation, limited_low, limited_high)
        u_recommended = clamp(rate_limited_recommendation, output_min, output_max)

        recommendation_clamped = u_recommended != rate_limited_recommendation
        recommendation_rate_limited = rate_limited_recommendation != raw_recommendation

        previous_error = error
        u_recommended_prev = u_recommended

        u_ach = row.get("u_ach")
        prediction_error = None
        if u_ach is not None:
            prediction_error = float(u_ach) - y_hat
            prediction_errors.append(prediction_error)

        output_rows.append(
            {
                "step": int(row["step"]),
                "time_seconds": float(row["time_seconds"]),
                "input_mode": input_meta["input_mode"],
                "source_file": row.get("source_file"),
                "u_cmd_replay": u_cmd,
                "u_ach_replay": u_ach,
                "y_hat": y_hat,
                "prediction_error": prediction_error,
                "setpoint": setpoint,
                "controller_error": error,
                "controller_mode": mode,
                "u_recommended_shadow": u_recommended,
                "recommendation_clamped": recommendation_clamped,
                "recommendation_rate_limited": recommendation_rate_limited,
                "actuator_applied": False,
            }
        )

    y_values = [float(row["y_hat"]) for row in output_rows]
    u_rec_values = [float(row["u_recommended_shadow"]) for row in output_rows]

    summary = {
        "version": VERSION,
        "stage": STAGE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "offline_only": True,
        "live_controller_started": False,
        "kubernetes_modified": False,
        "actuator_applied": False,
        "decision": "SHADOW_MODE_REPLAY_VALIDATION_COMPLETE",
        "input": input_meta,
        "sample_time_seconds": sample_time,
        "plant": plant,
        "controller": ctrl,
        "rows": len(output_rows),
        "metrics": {
            "prediction_mae": mae(prediction_errors),
            "prediction_rmse": rmse(prediction_errors),
            "prediction_error_count": len(prediction_errors),
            "y_hat_min": min(y_values) if y_values else None,
            "y_hat_max": max(y_values) if y_values else None,
            "y_hat_mean": statistics.mean(y_values) if y_values else None,
            "u_recommended_min": min(u_rec_values) if u_rec_values else None,
            "u_recommended_max": max(u_rec_values) if u_rec_values else None,
            "u_recommended_mean": statistics.mean(u_rec_values) if u_rec_values else None
        },
        "safety_notes": [
            "Controller recommendations were not applied.",
            "Replay input, not controller output, drives the plant prediction.",
            "The runner does not call kubectl.",
            "The runner does not modify Kubernetes.",
            "The runner does not generate transaction load.",
            "The current controller mode is intentionally limited to P by default."
        ],
        "limitations": [
            "The default plant coefficients are config values and must be replaced by coefficients derived from the project model before scientific interpretation.",
            "One-second simulation is valid only when the discrete plant coefficients correspond to a one-second sample time.",
            "MPC is intentionally out of scope for this stage.",
            "Live telemetry read-only integration is not implemented in this MVP."
        ],
        "recommended_next_step": "Validate against real v0.8.0 replay columns when available, then introduce PI and PID modes gradually."
    }

    return output_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to v0.13.0 shadow controller config JSON.")
    args = parser.parse_args()

    root = repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path

    cfg = read_json(config_path)

    if not cfg.get("offline_only", False):
        raise SystemExit("Refusing to run: config offline_only must be true.")

    rows, input_meta = load_replay_csv(root, cfg)
    if not rows:
        max_rows = int(cfg.get("input", {}).get("max_rows", 240))
        rows, input_meta = synthetic_replay(max_rows=min(max_rows, 240))

    output_rows, summary = run_shadow_simulation(rows, cfg, input_meta)

    output_cfg = cfg["output"]
    out_dir = root / output_cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / output_cfg["timeseries_csv"]
    json_path = out_dir / output_cfg["summary_json"]

    write_csv(csv_path, output_rows)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {csv_path.relative_to(root)}")
    print(f"Wrote {json_path.relative_to(root)}")
    print(f"Input mode: {summary['input']['input_mode']}")
    print(f"Rows: {summary['rows']}")
    print(f"Decision: {summary['decision']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
