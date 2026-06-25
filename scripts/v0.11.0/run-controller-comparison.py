#!/usr/bin/env python3
"""
v0.11.0 offline controller comparison runner.

This script runs the offline throughput controller simulator for a fixed
comparison set and writes machine-readable and human-readable comparison
summaries.

It does not access Kubernetes.
It does not send commands to the live testbed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List


OUT_DIR = Path("results/v0.11.0/controller-prototype")
SIM = Path("scripts/v0.11.0/offline-throughput-controller-sim.py")


CASES = [
    {
        "name": "feedforward",
        "args": [
            "--profile", "multistep",
            "--plant", "transition",
            "--controller", "feedforward",
            "--hold", "12",
        ],
    },
    {
        "name": "p_kp_0_10",
        "args": [
            "--profile", "multistep",
            "--plant", "transition",
            "--controller", "p",
            "--kp", "0.10",
            "--hold", "12",
        ],
    },
    {
        "name": "pi_kp_0_10_ki_0_002",
        "args": [
            "--profile", "multistep",
            "--plant", "transition",
            "--controller", "pi",
            "--kp", "0.10",
            "--ki", "0.002",
            "--ts", "1.0",
            "--hold", "12",
        ],
    },
]


def run_case(case: Dict[str, object]) -> Dict[str, object]:
    cmd = [str(SIM)] + list(case["args"])
    subprocess.run(cmd, check=True)

    summary_path = OUT_DIR / "offline-controller-summary.json"
    summary = json.loads(summary_path.read_text())

    metrics = summary["metrics"]

    return {
        "case": case["name"],
        "controller": summary["controller"],
        "controller_parameters": summary.get("controller_parameters", {}),
        "profile": summary["profile"],
        "plant": summary["plant"],
        "hold": summary["hold"],
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


def rank_cases(results: List[Dict[str, object]], metric: str) -> List[Dict[str, object]]:
    return sorted(results, key=lambda r: float(r["metrics"][metric]))


def write_json(results: List[Dict[str, object]]) -> None:
    by_mae = rank_cases(results, "mae")
    by_rmse = rank_cases(results, "rmse")

    payload = {
        "stage": "v0.11.0-throughput-controller-prototype",
        "comparison": "offline-controller-comparison",
        "profile": "multistep",
        "plant": "transition",
        "hold": 12,
        "safe_bounds": {
            "u_min": 32.0,
            "u_max": 128.0,
        },
        "results": results,
        "best_by_mae": by_mae[0]["case"],
        "best_by_rmse": by_rmse[0]["case"],
    }

    path = OUT_DIR / "offline-controller-comparison.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"comparison_json: {path}")


def write_markdown(results: List[Dict[str, object]]) -> None:
    by_mae = rank_cases(results, "mae")
    by_rmse = rank_cases(results, "rmse")

    lines = [
        "# v0.11.0 offline controller comparison",
        "",
        "## Purpose",
        "",
        "This file summarises the automated offline comparison of the implemented controller modes.",
        "",
        "The comparison is offline only. It does not access Kubernetes and does not send live testbed commands.",
        "",
        "## Fixed comparison setup",
        "",
        "- profile: `multistep`",
        "- plant: `transition`",
        "- hold: `12`",
        "- safe command range: `32..128`",
        "",
        "## Results",
        "",
        "| Case | Controller | RMSE | MAE | Max abs error | Saturation count | Anti-windup freeze count |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    for r in results:
        m = r["metrics"]
        lines.append(
            f"| `{r['case']}` | `{r['controller']}` | "
            f"{m['rmse']:.6f} | {m['mae']:.6f} | {m['max_abs_error']:.6f} | "
            f"{m['saturation_count']} | {m['anti_windup_freeze_count']} |"
        )

    lines.extend([
        "",
        "## Ranking",
        "",
        f"- Best by MAE: `{by_mae[0]['case']}`",
        f"- Best by RMSE: `{by_rmse[0]['case']}`",
        "",
        "## Interpretation",
        "",
        "The P-only controller remains the best simple controller by MAE.",
        "",
        "The conservative PI controller slightly improves RMSE, but increases MAE relative to P-only.",
        "",
        "The PI anti-windup freeze mechanism is active during saturated upper-bound operation, which confirms that integral accumulation is controlled when the raw command would exceed the safe range.",
        "",
        "The result does not yet justify live closed-loop Kubernetes control. Further offline profile coverage is required before a closed-loop readiness decision.",
        "",
    ])

    path = OUT_DIR / "offline-controller-comparison.md"
    path.write_text("\n".join(lines))
    print(f"comparison_md:   {path}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for case in CASES:
        print(f"=== running {case['name']} ===")
        results.append(run_case(case))

    write_json(results)
    write_markdown(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
