#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from offline_simulation.artefacts import write_artefacts
from offline_simulation.engine import run_simulation_platform


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the v0.16.0 modular offline simulation platform."
    )
    parser.add_argument(
        "--config",
        default="configs/v0.16.0/modular-offline-simulation-platform.json",
        help="Path to the v0.16.0 platform config JSON."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    simulation_result = run_simulation_platform(config)
    write_artefacts(config, simulation_result)

    summary = simulation_result["summary"]
    print(f"stage: {summary['stage']}")
    print(f"decision: {summary['decision']}")
    print(f"platform_status: {summary['platform_status']}")
    print(f"reference_controller: {summary['reference_controller']}")
    print(f"case_count: {summary['case_count']}")
    print(f"controller_count: {summary['controller_count']}")
    print("OK: v0.16.0 modular offline simulation platform run completed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
