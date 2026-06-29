from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


def write_artefacts(config: Dict[str, Any], simulation_result: Dict[str, Any]) -> None:
    output_dir = Path(config["outputs"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json(output_dir / "simulation-summary.json", simulation_result["summary"])
    _write_json(
        output_dir / "reference-controller-metrics.json",
        simulation_result["controller_comparison"][0]
    )

    _write_csv(output_dir / "controller-comparison.csv", simulation_result["controller_comparison"])
    _write_csv(output_dir / "case-metrics.csv", simulation_result["case_metrics"])
    _write_csv(output_dir / "profile-metrics.csv", simulation_result["profile_metrics"])

    _write_readme(output_dir, simulation_result)
    validate_expected_outputs(config)


def validate_expected_outputs(config: Dict[str, Any]) -> None:
    output_dir = Path(config["outputs"]["directory"])
    missing = []
    empty = []

    for filename in config["outputs"]["expected_files"]:
        path = output_dir / filename
        if not path.exists():
            missing.append(str(path))
        elif path.stat().st_size == 0:
            empty.append(str(path))

    if missing or empty:
        raise RuntimeError(
            "Output integrity check failed. "
            f"Missing files: {missing}. Empty files: {empty}."
        )


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8"
    )


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_readme(output_dir: Path, simulation_result: Dict[str, Any]) -> None:
    summary = simulation_result["summary"]

    lines = [
        "# v0.16.0 modular offline simulation platform",
        "",
        "## Purpose",
        "",
        "This directory contains the first generated artefacts from the v0.16.0 modular offline controller simulation platform.",
        "",
        "## Controller",
        "",
        f"Reference controller: {summary['reference_controller']}",
        "",
        "## Status",
        "",
        f"Platform status: {summary['platform_status']}",
        "",
        f"Decision: {summary['decision']}",
        "",
        "## Scope",
        "",
        "This run validates the initial platform architecture with a replaceable controller interface and the v0.14.3 P-only baseline as the reference controller.",
        "",
        "It does not attempt to improve MPC or introduce strict MPC optimization.",
        "",
        "## Generated artefacts",
        "",
        "- simulation-summary.json",
        "- controller-comparison.csv",
        "- case-metrics.csv",
        "- profile-metrics.csv",
        "- reference-controller-metrics.json",
        "",
        "## Reproduction",
        "",
        "Run from repository root:",
        "",
        "```bash",
        "python3 scripts/v0.16.0/run-modular-offline-simulation-platform.py --config configs/v0.16.0/modular-offline-simulation-platform.json",
        "```",
        ""
    ]

    content = "\n".join(lines)
    (output_dir / "README.md").write_text(content, encoding="utf-8")
