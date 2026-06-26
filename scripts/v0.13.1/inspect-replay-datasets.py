#!/usr/bin/env python3

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


DECISION_FOUND = "REAL_REPLAY_BINDING_CANDIDATE_FOUND"
DECISION_NOT_AVAILABLE = "REAL_REPLAY_BINDING_NOT_AVAILABLE"


def read_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def norm(value):
    return value.strip().lstrip("\ufeff").lower()


def find_column(header, candidates):
    lookup = {}
    for col in header:
        n = norm(col)
        if n and n not in lookup:
            lookup[n] = col.strip().lstrip("\ufeff")
    for cand in candidates:
        if norm(cand) in lookup:
            return lookup[norm(cand)]
    return None


def read_header_and_count_rows(path):
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return [], 0, None
            rows = sum(1 for _ in reader)
            return [c.strip() for c in header], rows, None
    except Exception as exc:
        return [], 0, f"{type(exc).__name__}: {exc}"


def inspect_file(path, root, command_candidates, achieved_candidates, time_candidates):
    header, row_count, read_error = read_header_and_count_rows(path)

    command_col = find_column(header, command_candidates)
    achieved_col = find_column(header, achieved_candidates)
    time_col = find_column(header, time_candidates)

    suitable = (
        read_error is None
        and row_count > 0
        and command_col is not None
        and achieved_col is not None
    )

    if suitable and time_col is not None:
        confidence = "high"
    elif suitable:
        confidence = "medium"
    else:
        confidence = "none"

    missing = []
    if read_error is not None:
        missing.append("readable_csv")
    if row_count <= 0:
        missing.append("non_empty_rows")
    if command_col is None:
        missing.append("command_column")
    if achieved_col is None:
        missing.append("achieved_column")

    return {
        "path": path.as_posix(),
        "dataset_version": root["dataset_version"],
        "role": root["role"],
        "header": header,
        "column_count": len(header),
        "row_count": row_count,
        "read_error": read_error,
        "matched_columns": {
            "command": command_col,
            "achieved": achieved_col,
            "time": time_col
        },
        "has_command_column": command_col is not None,
        "has_achieved_column": achieved_col is not None,
        "has_time_column": time_col is not None,
        "suitable_for_shadow_replay": suitable,
        "binding_confidence": confidence,
        "missing_requirements": missing
    }


def binding_from_dataset(dataset):
    return {
        "dataset_path": dataset["path"],
        "dataset_version": dataset["dataset_version"],
        "command_column": dataset["matched_columns"]["command"],
        "achieved_column": dataset["matched_columns"]["achieved"],
        "time_column": dataset["matched_columns"]["time"],
        "row_count": dataset["row_count"],
        "binding_confidence": dataset["binding_confidence"],
        "offline_only": True,
        "controller_recommendations_applied": False,
        "live_telemetry_used": False,
        "kubernetes_invoked": False
    }


def sort_key(dataset):
    conf = {"high": 2, "medium": 1, "none": 0}.get(dataset["binding_confidence"], 0)
    return (conf, dataset["row_count"], dataset["column_count"], dataset["path"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    config = read_json(config_path)

    if config.get("offline_only") is not True:
        raise ValueError("offline_only must be true")

    output_dir = Path(config["output_directory"])
    preferred_version = config["preferred_dataset_version"]
    generated_at = datetime.now(timezone.utc).isoformat()

    inspected = []
    scanned_roots = []

    for root in config["search_roots"]:
        root_path = Path(root["path"])
        csv_files = sorted(root_path.rglob("*.csv")) if root_path.exists() else []

        scanned_roots.append({
            "path": root_path.as_posix(),
            "dataset_version": root["dataset_version"],
            "role": root["role"],
            "exists": root_path.exists(),
            "csv_file_count": len(csv_files)
        })

        for csv_path in csv_files:
            inspected.append(inspect_file(
                csv_path,
                root,
                config["command_column_candidates"],
                config["achieved_column_candidates"],
                config["time_column_candidates"]
            ))

    preferred = [
        d for d in inspected
        if d["dataset_version"] == preferred_version
        and d["suitable_for_shadow_replay"]
    ]

    secondary = [
        d for d in inspected
        if d["dataset_version"] != preferred_version
        and d["suitable_for_shadow_replay"]
    ]

    preferred_sorted = sorted(preferred, key=sort_key, reverse=True)
    secondary_sorted = sorted(secondary, key=sort_key, reverse=True)

    if preferred_sorted:
        decision = DECISION_FOUND
        recommended_binding = binding_from_dataset(preferred_sorted[0])
        reason = "A suitable real replay CSV was found under the preferred v0.8.0 dataset root."
    else:
        decision = DECISION_NOT_AVAILABLE
        recommended_binding = None
        reason = "No suitable v0.8.0 CSV was found with non-empty rows plus command and achieved columns."

    inventory = {
        "version": config["version"],
        "generated_at": generated_at,
        "generated_by": "scripts/v0.13.1/inspect-replay-datasets.py",
        "config_path": config_path.as_posix(),
        "offline_only": True,
        "preferred_dataset_version": preferred_version,
        "search_roots": scanned_roots,
        "column_candidates": {
            "command": config["command_column_candidates"],
            "achieved": config["achieved_column_candidates"],
            "time": config["time_column_candidates"]
        },
        "totals": {
            "csv_files_inspected": len(inspected),
            "preferred_suitable_candidates": len(preferred),
            "secondary_suitable_candidates": len(secondary),
            "all_suitable_candidates": len(preferred) + len(secondary)
        },
        "datasets": inspected
    }

    summary = {
        "version": config["version"],
        "generated_at": generated_at,
        "offline_only": True,
        "decision": decision,
        "decision_reason": reason,
        "preferred_dataset_version": preferred_version,
        "recommended_binding": recommended_binding,
        "preferred_candidate_count": len(preferred),
        "secondary_candidate_count": len(secondary),
        "secondary_candidates_are_advisory_only": True,
        "top_preferred_candidates": [binding_from_dataset(d) for d in preferred_sorted[:5]],
        "top_secondary_candidates": [binding_from_dataset(d) for d in secondary_sorted[:5]],
        "safety_constraints": {
            "offline_only": True,
            "kubectl_invoked": False,
            "kubernetes_modified": False,
            "live_controller_started": False,
            "transaction_load_generated": False,
            "controller_recommendations_applied": False,
            "closed_loop_control_executed": False
        },
        "outputs": {
            "inventory": str(output_dir / "replay-dataset-inventory.json"),
            "summary": str(output_dir / "replay-binding-summary.json")
        }
    }

    write_json(output_dir / "replay-dataset-inventory.json", inventory)
    write_json(output_dir / "replay-binding-summary.json", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
