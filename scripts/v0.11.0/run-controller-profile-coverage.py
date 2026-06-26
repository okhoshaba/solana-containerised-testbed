#!/usr/bin/env python3
"""
v0.11.0 offline controller profile-coverage runner.

Runs the offline simulator across multiple safe reference profiles and
controller modes.

This is offline-only:
- no Kubernetes access;
- no live load-generator commands;
- no closed-loop control.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


CONFIG_DIR = Path("configs/v0.11.0/controller-sim")
OUT_DIR = Path("results/v0.11.0/controller-prototype")
SIM = Path("scripts/v0.11.0/offline-throughput-controller-sim.py")

PROFILE_ORDER = [
    "constant64",
    "step64-96",
    "multistep",
    "lower-range",
    "sine-approx",
]

CONTROLLER_ORDER = [
    "feedforward",
    "p",
    "pi",
]


def config_path(profile: str, controller: str) -> Path:
    return CONFIG_DIR / f"{profile}-{controller}.json"


def run_config(path: Path) -> Dict[str, Any]:
    subprocess.run([str(SIM), "--config", str(path)], check=True)

    summary_path = OUT_DIR / "offline-controller-summary.json"
    summary = json.loads(summary_path.read_text())

    metrics = summary["metrics"]

    return {
        "config": str(path),
        "simulation_name": summary.get("simulation_name"),
        "profile": path.name.replace(".json", "").rsplit("-", 1)[0],
        "controller_case": path.name.replace(".json", "").rsplit("-", 1)[1],
        "controller": summary["controller"],
        "plant": summary["plant"],
        "sample_count": summary["sample_count"],
        "safe_bounds": summary["safe_bounds"],
        "controller_parameters": summary["controller_parameters"],
        "metrics": {
            "rmse": metrics["rmse"],
            "mae": metrics["mae"],
            "max_abs_error": metrics["max_abs_error"],
            "mean_error": metrics["mean_error"],
            "final_error": metrics["final_error"],
            "saturation_count": metrics["saturation_count"],
            "saturation_fraction": metrics["saturation_fraction"],
            "anti_windup_freeze_count": metrics.get("anti_windup_freeze_count", 0),
            "anti_windup_freeze_fraction": metrics.get("anti_windup_freeze_fraction", 0.0),
            "mean_abs_command_change": metrics["mean_abs_command_change"],
            "max_abs_command_change": metrics["max_abs_command_change"],
        },
    }


def best_by(results: List[Dict[str, Any]], profile: str, metric: str) -> Dict[str, Any]:
    candidates = [r for r in results if r["profile"] == profile]
    return sorted(candidates, key=lambda r: float(r["metrics"][metric]))[0]


def write_json(results: List[Dict[str, Any]]) -> None:
    best = {}

    for profile in PROFILE_ORDER:
        profile_results = [r for r in results if r["profile"] == profile]
        if not profile_results:
            continue

        best[profile] = {
            "best_by_mae": best_by(results, profile, "mae")["controller_case"],
            "best_by_rmse": best_by(results, profile, "rmse")["controller_case"],
        }

    payload = {
        "stage": "v0.11.0-throughput-controller-prototype",
        "comparison": "offline-controller-profile-coverage",
        "plant": "transition",
        "profiles": PROFILE_ORDER,
        "controllers": CONTROLLER_ORDER,
        "results": results,
        "best": best,
    }

    path = OUT_DIR / "offline-controller-profile-coverage.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"profile_coverage_json: {path}")


def write_markdown(results: List[Dict[str, Any]]) -> None:
    lines = [
        "# v0.11.0 offline controller profile coverage",
        "",
        "## Purpose",
        "",
        "This file summarises offline controller behaviour across multiple safe reference profiles.",
        "",
        "The comparison is offline only. It does not access Kubernetes and does not send live testbed commands.",
        "",
        "## Results",
        "",
        "| Profile | Controller case | RMSE | MAE | Max abs error | Saturation count | Anti-windup freeze count |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    for profile in PROFILE_ORDER:
        for controller in CONTROLLER_ORDER:
            matches = [
                r for r in results
                if r["profile"] == profile and r["controller_case"] == controller
            ]
            if not matches:
                continue

            r = matches[0]
            m = r["metrics"]
            lines.append(
                f"| `{profile}` | `{controller}` | "
                f"{m['rmse']:.6f} | {m['mae']:.6f} | {m['max_abs_error']:.6f} | "
                f"{m['saturation_count']} | {m['anti_windup_freeze_count']} |"
            )

    lines.extend([
        "",
        "## Per-profile ranking",
        "",
    ])

    for profile in PROFILE_ORDER:
        profile_results = [r for r in results if r["profile"] == profile]
        if not profile_results:
            continue

        lines.append(
            f"- `{profile}`: best by MAE = "
            f"`{best_by(results, profile, 'mae')['controller_case']}`, "
            f"best by RMSE = `{best_by(results, profile, 'rmse')['controller_case']}`"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "This profile-coverage run broadens offline testing beyond the original multistep profile.",
        "",
        "It is still not a live-control readiness decision. The results should be used to identify controller candidates that remain safe and stable across several reference profiles before any closed-loop Kubernetes experiment is considered.",
        "",
    ])

    path = OUT_DIR / "offline-controller-profile-coverage.md"
    path.write_text("\n".join(lines))
    print(f"profile_coverage_md:   {path}")


def main() -> int:
    results = []

    for profile in PROFILE_ORDER:
        for controller in CONTROLLER_ORDER:
            path = config_path(profile, controller)

            if not path.exists():
                raise FileNotFoundError(path)

            print(f"=== profile={profile} controller={controller} ===")
            results.append(run_config(path))

    write_json(results)
    write_markdown(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
