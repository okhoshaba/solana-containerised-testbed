#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v0.13.2"
DECISION_COMPLETE = "REAL_REPLAY_SHADOW_MODE_VALIDATION_COMPLETE"


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
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def choose_time_column(fieldnames: list[str], candidates: list[str]) -> str | None:
    lookup = {name.strip().lower(): name for name in fieldnames}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lookup:
            return lookup[key]
    return None


def derive_timebase(rows: list[dict[str, str]], time_column: str | None) -> dict[str, Any]:
    if time_column is None:
        return {
            "time_column": None,
            "time_values_count": 0,
            "time_min": None,
            "time_max": None,
            "median_dt_seconds": None,
            "min_dt_seconds": None,
            "max_dt_seconds": None,
            "strictly_increasing": None,
            "sample_time_seconds_selected": 1.0,
            "sample_time_selection_reason": "no time column detected; fallback to 1.0 second row-index timebase"
        }

    values: list[float] = []
    for row in rows:
        value = parse_float(row.get(time_column))
        if value is not None:
            values.append(value)

    deltas = [
        values[index] - values[index - 1]
        for index in range(1, len(values))
        if values[index] - values[index - 1] > 0
    ]

    if deltas:
        median_dt = statistics.median(deltas)
        selected = median_dt
        reason = "median positive delta from real replay time column"
    else:
        median_dt = None
        selected = 1.0
        reason = "time column found but no positive deltas; fallback to 1.0 second row-index timebase"

    return {
        "time_column": time_column,
        "time_values_count": len(values),
        "time_min": min(values) if values else None,
        "time_max": max(values) if values else None,
        "median_dt_seconds": median_dt,
        "min_dt_seconds": min(deltas) if deltas else None,
        "max_dt_seconds": max(deltas) if deltas else None,
        "strictly_increasing": all(values[index] > values[index - 1] for index in range(1, len(values))) if len(values) > 1 else None,
        "sample_time_seconds_selected": selected,
        "sample_time_selection_reason": reason
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def annotate_runner_timeseries(
    runner_csv: Path,
    source_rows: list[dict[str, str]],
    dataset_path: str,
    time_column: str | None,
) -> list[dict[str, Any]]:
    _, runner_rows = read_csv_rows(runner_csv)

    annotated: list[dict[str, Any]] = []
    for index, runner_row in enumerate(runner_rows):
        source_row = source_rows[index] if index < len(source_rows) else {}

        source_time = parse_float(source_row.get(time_column)) if time_column else None
        merged: dict[str, Any] = dict(runner_row)
        merged["real_replay_dataset_path"] = dataset_path
        merged["source_row_index"] = index
        merged["source_time_column"] = time_column
        merged["source_time_seconds"] = source_time
        merged["source_t_sec"] = source_row.get("t_sec")
        merged["source_t_rel_sec"] = source_row.get("t_rel_sec")
        merged["source_u_cmd"] = source_row.get("u_cmd")
        merged["source_u_ach"] = source_row.get("u_ach")
        merged["timebase_note"] = "v0.13.0 runner time_seconds is row-index based; source_time_seconds preserves real replay time when available"
        annotated.append(merged)

    return annotated


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
        raise ValueError("v0.13.2 config must set offline_only=true")

    binding_path = root / cfg["real_replay_binding_summary"]
    binding = read_json(binding_path)

    if binding.get("decision") != "REAL_REPLAY_BINDING_CANDIDATE_FOUND":
        raise ValueError("v0.13.1 did not find a real replay binding candidate")

    recommended = binding.get("recommended_binding")
    if not recommended:
        raise ValueError("v0.13.1 summary has no recommended_binding")

    dataset_path_text = cfg.get("dataset_path") or recommended["dataset_path"]
    command_column = cfg.get("command_column") or recommended["command_column"]
    achieved_column = cfg.get("achieved_column") or recommended["achieved_column"]

    dataset_path = root / dataset_path_text
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)

    fieldnames, source_rows = read_csv_rows(dataset_path)

    missing_columns = [
        column for column in [command_column, achieved_column]
        if column and column not in fieldnames
    ]
    if missing_columns:
        raise ValueError(f"Missing required replay columns: {missing_columns}")

    time_column = choose_time_column(fieldnames, cfg.get("time_column_candidates", []))
    timebase = derive_timebase(source_rows, time_column)

    sample_time = cfg.get("sample_time_seconds")
    if sample_time is None:
        sample_time = timebase["sample_time_seconds_selected"]

    output_dir = root / cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    base_runner_config = read_json(root / cfg["base_runner_config"])
    runtime_config = deepcopy(base_runner_config)

    runtime_config["input"]["replay_search_globs"] = [dataset_path_text]
    runtime_config["input"]["max_rows"] = min(int(cfg.get("max_rows", 600)), len(source_rows))
    runtime_config["input"]["command_column_candidates"] = [command_column]
    runtime_config["input"]["achieved_column_candidates"] = [achieved_column]

    runtime_config["simulation"]["sample_time_seconds"] = float(sample_time)

    runtime_config["output"]["output_dir"] = cfg["output_dir"]
    runtime_config["output"]["timeseries_csv"] = cfg["outputs"]["runner_timeseries_csv"]
    runtime_config["output"]["summary_json"] = cfg["outputs"]["runner_summary_json"]

    runtime_config["v0.13.2_binding"] = {
        "real_replay_dataset_path": dataset_path_text,
        "command_column": command_column,
        "achieved_column": achieved_column,
        "time_column": time_column,
        "timebase_policy": cfg["timebase_policy"],
        "source_binding_summary": cfg["real_replay_binding_summary"]
    }

    runtime_config_path = output_dir / cfg["outputs"]["resolved_runner_config"]
    write_json(runtime_config_path, runtime_config)

    runner_script = root / cfg["base_runner_script"]
    subprocess.run(
        [sys.executable, str(runner_script), "--config", str(runtime_config_path.relative_to(root))],
        cwd=root,
        check=True,
    )

    runner_timeseries_path = output_dir / cfg["outputs"]["runner_timeseries_csv"]
    runner_summary_path = output_dir / cfg["outputs"]["runner_summary_json"]

    runner_summary = read_json(runner_summary_path)

    annotated_rows = annotate_runner_timeseries(
        runner_timeseries_path,
        source_rows,
        dataset_path_text,
        time_column,
    )
    annotated_timeseries_path = output_dir / cfg["outputs"]["annotated_timeseries_csv"]
    write_csv(annotated_timeseries_path, annotated_rows)

    summary = {
        "version": VERSION,
        "stage": cfg["stage"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": DECISION_COMPLETE,
        "offline_only": True,
        "real_replay_dataset": {
            "path": dataset_path_text,
            "fieldnames": fieldnames,
            "row_count": len(source_rows),
            "command_column": command_column,
            "achieved_column": achieved_column,
            "time_column": time_column
        },
        "timebase": timebase,
        "runner": {
            "base_runner_script": cfg["base_runner_script"],
            "base_runner_config": cfg["base_runner_config"],
            "resolved_runner_config": str(runtime_config_path.relative_to(root)),
            "runner_summary": str(runner_summary_path.relative_to(root)),
            "runner_timeseries": str(runner_timeseries_path.relative_to(root)),
            "runner_version": runner_summary.get("version"),
            "runner_decision": runner_summary.get("decision"),
            "runner_input": runner_summary.get("input"),
            "runner_rows": runner_summary.get("rows"),
            "runner_metrics": runner_summary.get("metrics")
        },
        "outputs": {
            "summary_json": str((output_dir / cfg["outputs"]["summary_json"]).relative_to(root)),
            "annotated_timeseries_csv": str(annotated_timeseries_path.relative_to(root)),
            "runner_summary_json": str(runner_summary_path.relative_to(root)),
            "runner_timeseries_csv": str(runner_timeseries_path.relative_to(root)),
            "resolved_runner_config": str(runtime_config_path.relative_to(root))
        },
        "safety_constraints": {
            "kubectl_invoked": False,
            "kubernetes_modified": False,
            "live_controller_started": False,
            "transaction_load_generated": False,
            "controller_recommendations_applied": False,
            "closed_loop_control_executed": False,
            "offline_only": True
        },
        "interpretation": {
            "what_this_validates": "The v0.13.0 offline shadow-mode runner can be bound to and executed against a real v0.8.0 replay CSV.",
            "what_this_does_not_validate": "This does not validate live telemetry, Kubernetes actuation, production controller behavior, or closed-loop control.",
            "timebase_note": "The annotated timeseries preserves the real replay time column when available. The inherited v0.13.0 runner still writes its internal time_seconds as row index."
        }
    }

    summary_path = output_dir / cfg["outputs"]["summary_json"]
    write_json(summary_path, summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
