#!/usr/bin/env python3
"""
v0.11.0 offline throughput controller simulator.

This first version implements:
- safe reference profiles;
- command saturation;
- unity plant;
- first-order transition plant;
- feed-forward baseline controller.

It does not access Kubernetes.
It does not send commands to the live testbed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List


U_MIN = 32.0
U_MAX = 128.0

A_TRANSITION = 0.143846
B_TRANSITION = 0.856154


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", default="multistep",
                   choices=["constant64", "step64-96", "multistep", "lower-range"])
    p.add_argument("--plant", default="transition",
                   choices=["unity", "transition"])
    p.add_argument("--controller", default="feedforward",
                   choices=["feedforward", "p", "pi"])
    p.add_argument("--kp", type=float, default=0.10,
                   help="Proportional gain for P-only and PI controllers.")
    p.add_argument("--ki", type=float, default=0.002,
                   help="Integral gain for PI controller.")
    p.add_argument("--ts", type=float, default=1.0,
                   help="Discrete simulation sampling interval.")
    p.add_argument("--hold", type=int, default=12,
                   help="Number of samples per reference segment.")
    p.add_argument("--out-dir", default="results/v0.11.0/controller-prototype")
    return p.parse_args()


def reference_levels(profile: str) -> List[float]:
    if profile == "constant64":
        return [64.0]
    if profile == "step64-96":
        return [64.0, 96.0]
    if profile == "multistep":
        return [64.0, 96.0, 128.0, 96.0, 64.0]
    if profile == "lower-range":
        return [32.0, 64.0, 32.0]
    raise ValueError(f"unknown profile: {profile}")


def expand_profile(levels: List[float], hold: int) -> List[float]:
    refs: List[float] = []
    for level in levels:
        refs.extend([level] * hold)
    return refs


def saturate(u_raw: float) -> Dict[str, float | bool]:
    u_cmd = min(max(u_raw, U_MIN), U_MAX)
    return {
        "u_cmd": u_cmd,
        "saturated": abs(u_cmd - u_raw) > 1e-12,
    }


def plant_step(plant: str, y_prev: float, u_cmd: float) -> float:
    if plant == "unity":
        return u_cmd
    if plant == "transition":
        return A_TRANSITION * y_prev + B_TRANSITION * u_cmd
    raise ValueError(f"unknown plant: {plant}")


def metrics(
    errors: List[float],
    u_cmds: List[float],
    saturation_flags: List[bool],
    anti_windup_flags: List[bool],
) -> Dict[str, float | int]:
    n = len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    mae = sum(abs(e) for e in errors) / n
    max_abs_error = max(abs(e) for e in errors)
    mean_error = sum(errors) / n
    final_error = errors[-1]

    command_changes = [
        abs(u_cmds[i] - u_cmds[i - 1])
        for i in range(1, len(u_cmds))
    ]

    return {
        "n": n,
        "rmse": rmse,
        "mae": mae,
        "max_abs_error": max_abs_error,
        "mean_error": mean_error,
        "final_error": final_error,
        "saturation_count": sum(1 for x in saturation_flags if x),
        "saturation_fraction": sum(1 for x in saturation_flags if x) / n,
        "anti_windup_freeze_count": sum(1 for x in anti_windup_flags if x),
        "anti_windup_freeze_fraction": sum(1 for x in anti_windup_flags if x) / n,
        "mean_abs_command_change": sum(command_changes) / len(command_changes) if command_changes else 0.0,
        "max_abs_command_change": max(command_changes) if command_changes else 0.0,
    }


def run_sim(args: argparse.Namespace) -> Dict[str, object]:
    levels = reference_levels(args.profile)
    refs = expand_profile(levels, args.hold)

    if not refs:
        raise RuntimeError("empty reference profile")

    y = refs[0]
    integral = 0.0
    rows: List[Dict[str, object]] = []

    for k, r in enumerate(refs):
        # Controller uses the previous simulated plant output as feedback.
        e_feedback = r - y
        anti_windup_freeze = False

        if args.controller == "feedforward":
            u_raw = r
        elif args.controller == "p":
            u_raw = r + args.kp * e_feedback
        elif args.controller == "pi":
            integral_candidate = integral + args.ts * e_feedback
            u_raw_candidate = r + args.kp * e_feedback + args.ki * integral_candidate

            candidate_sat = saturate(u_raw_candidate)
            if bool(candidate_sat["saturated"]):
                anti_windup_freeze = True
            else:
                integral = integral_candidate

            u_raw = r + args.kp * e_feedback + args.ki * integral
        else:
            raise ValueError(f"unknown controller: {args.controller}")

        sat = saturate(u_raw)
        u_cmd = float(sat["u_cmd"])
        saturated = bool(sat["saturated"])

        y = plant_step(args.plant, y, u_cmd)
        e = r - y

        rows.append({
            "k": k,
            "profile": args.profile,
            "plant": args.plant,
            "controller": args.controller,
            "r": r,
            "y": y,
            "e": e,
            "e_feedback": e_feedback,
            "integral": integral,
            "anti_windup_freeze": anti_windup_freeze,
            "u_raw": u_raw,
            "u_cmd": u_cmd,
            "saturated": saturated,
        })

    summary_metrics = metrics(
        [float(row["e"]) for row in rows],
        [float(row["u_cmd"]) for row in rows],
        [bool(row["saturated"]) for row in rows],
        [bool(row["anti_windup_freeze"]) for row in rows],
    )

    return {
        "stage": "v0.11.0-throughput-controller-prototype",
        "controller": args.controller,
        "plant": args.plant,
        "profile": args.profile,
        "hold": args.hold,
        "controller_parameters": {
            "kp": args.kp if args.controller in ("p", "pi") else None,
            "ki": args.ki if args.controller == "pi" else None,
            "ts": args.ts if args.controller == "pi" else None,
        },
        "safe_bounds": {
            "u_min": U_MIN,
            "u_max": U_MAX,
        },
        "plant_parameters": {
            "unity": args.plant == "unity",
            "a": A_TRANSITION if args.plant == "transition" else None,
            "b": B_TRANSITION if args.plant == "transition" else None,
        },
        "metrics": summary_metrics,
        "rows": rows,
    }


def write_outputs(result: Dict[str, object], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_json = out_dir / "offline-controller-summary.json"
    traces_csv = out_dir / "offline-controller-traces.csv"

    rows = result["rows"]

    summary_no_rows = dict(result)
    summary_no_rows.pop("rows")

    summary_json.write_text(json.dumps(summary_no_rows, indent=2, sort_keys=True) + "\n")

    fieldnames = [
        "k",
        "profile",
        "plant",
        "controller",
        "r",
        "y",
        "e",
        "e_feedback",
        "integral",
        "anti_windup_freeze",
        "u_raw",
        "u_cmd",
        "saturated",
    ]

    with traces_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"summary_json: {summary_json}")
    print(f"traces_csv:   {traces_csv}")


def main() -> int:
    args = parse_args()
    result = run_sim(args)
    write_outputs(result, Path(args.out_dir))

    m = result["metrics"]
    print(f"controller: {result['controller']}")
    print(f"plant:      {result['plant']}")
    print(f"profile:    {result['profile']}")
    if result["controller"] in ("p", "pi"):
        print(f"kp:         {result['controller_parameters']['kp']:.6f}")
    if result["controller"] == "pi":
        print(f"ki:         {result['controller_parameters']['ki']:.6f}")
        print(f"ts:         {result['controller_parameters']['ts']:.6f}")
    print(f"rmse:       {m['rmse']:.6f}")
    print(f"mae:        {m['mae']:.6f}")
    print(f"sat_count:  {m['saturation_count']}")
    print(f"aw_count:   {m['anti_windup_freeze_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
