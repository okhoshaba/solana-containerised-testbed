#!/usr/bin/env python3
"""
v0.11.0 offline throughput controller simulator.

This simulator supports:
- safe reference profiles;
- JSON config-driven simulations;
- command saturation;
- unity plant;
- first-order transition plant;
- feed-forward baseline controller;
- P-only controller;
- PI controller with freeze anti-windup.

It does not access Kubernetes.
It does not send commands to the live testbed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


U_MIN_DEFAULT = 32.0
U_MAX_DEFAULT = 128.0

A_TRANSITION = 0.143846
B_TRANSITION = 0.856154


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=None,
                   help="Optional JSON config file for simulation parameters.")
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


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    return json.loads(Path(path).read_text())


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


def build_reference_from_config(cfg: Dict[str, Any], ts: float) -> Optional[List[float]]:
    ref_cfg = cfg.get("reference_profile")
    if not ref_cfg:
        return None

    if ref_cfg.get("type") != "piecewise_constant":
        raise ValueError("only reference_profile.type=piecewise_constant is supported")

    refs: List[float] = []
    segments = ref_cfg.get("segments", [])

    if not segments:
        raise ValueError("reference_profile.segments must not be empty")

    for seg in segments:
        value = float(seg["value"])

        if "duration_samples" in seg:
            n = int(seg["duration_samples"])
        elif "duration_seconds" in seg:
            n = int(round(float(seg["duration_seconds"]) / ts))
        else:
            raise ValueError("each segment must define duration_samples or duration_seconds")

        if n <= 0:
            raise ValueError(f"invalid segment duration for value={value}: {n}")

        refs.extend([value] * n)

    return refs


def apply_config(args: argparse.Namespace, cfg: Dict[str, Any]) -> argparse.Namespace:
    if not cfg:
        args.simulation_name = None
        args.reference_values = None
        args.u_min = U_MIN_DEFAULT
        args.u_max = U_MAX_DEFAULT
        return args

    sim_cfg = cfg.get("simulation", {})
    ctrl_cfg = cfg.get("controller", {})
    safety_cfg = cfg.get("safe_bounds", {})

    args.simulation_name = sim_cfg.get("name")

    args.plant = sim_cfg.get("plant", args.plant)
    args.profile = sim_cfg.get("profile", args.profile)
    args.hold = int(sim_cfg.get("hold", args.hold))

    if "time_step_seconds" in sim_cfg:
        args.ts = float(sim_cfg["time_step_seconds"])

    args.controller = ctrl_cfg.get("type", args.controller)
    args.kp = float(ctrl_cfg.get("kp", args.kp))
    args.ki = float(ctrl_cfg.get("ki", args.ki))
    args.ts = float(ctrl_cfg.get("ts", args.ts))

    args.u_min = float(safety_cfg.get("u_min", U_MIN_DEFAULT))
    args.u_max = float(safety_cfg.get("u_max", U_MAX_DEFAULT))

    args.reference_values = build_reference_from_config(cfg, args.ts)

    return args


def validate_refs(refs: List[float], u_min: float, u_max: float) -> None:
    for i, r in enumerate(refs):
        if r < u_min or r > u_max:
            raise ValueError(
                f"reference value outside safe bounds at index {i}: "
                f"r={r}, bounds=[{u_min}, {u_max}]"
            )


def saturate(u_raw: float, u_min: float, u_max: float) -> Dict[str, float | bool]:
    u_cmd = min(max(u_raw, u_min), u_max)
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

    saturation_count = sum(1 for x in saturation_flags if x)
    aw_count = sum(1 for x in anti_windup_flags if x)

    return {
        "n": n,
        "rmse": rmse,
        "mae": mae,
        "max_abs_error": max_abs_error,
        "mean_error": mean_error,
        "final_error": final_error,
        "saturation_count": saturation_count,
        "saturation_fraction": saturation_count / n,
        "anti_windup_freeze_count": aw_count,
        "anti_windup_freeze_fraction": aw_count / n,
        "mean_abs_command_change": sum(command_changes) / len(command_changes) if command_changes else 0.0,
        "max_abs_command_change": max(command_changes) if command_changes else 0.0,
    }


def run_sim(args: argparse.Namespace) -> Dict[str, object]:
    if args.reference_values is not None:
        refs = list(args.reference_values)
        profile_name = "config_piecewise_constant"
    else:
        levels = reference_levels(args.profile)
        refs = expand_profile(levels, args.hold)
        profile_name = args.profile

    validate_refs(refs, args.u_min, args.u_max)

    if not refs:
        raise RuntimeError("empty reference profile")

    y = refs[0]
    integral = 0.0
    rows: List[Dict[str, object]] = []

    for k, r in enumerate(refs):
        e_feedback = r - y
        anti_windup_freeze = False

        if args.controller == "feedforward":
            u_raw = r
        elif args.controller == "p":
            u_raw = r + args.kp * e_feedback
        elif args.controller == "pi":
            integral_candidate = integral + args.ts * e_feedback
            u_raw_candidate = r + args.kp * e_feedback + args.ki * integral_candidate

            candidate_sat = saturate(u_raw_candidate, args.u_min, args.u_max)
            if bool(candidate_sat["saturated"]):
                anti_windup_freeze = True
            else:
                integral = integral_candidate

            u_raw = r + args.kp * e_feedback + args.ki * integral
        else:
            raise ValueError(f"unknown controller: {args.controller}")

        sat = saturate(u_raw, args.u_min, args.u_max)
        u_cmd = float(sat["u_cmd"])
        saturated = bool(sat["saturated"])

        y = plant_step(args.plant, y, u_cmd)
        e = r - y

        rows.append({
            "k": k,
            "simulation_name": args.simulation_name or "",
            "profile": profile_name,
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
        "simulation_name": args.simulation_name,
        "controller": args.controller,
        "controller_parameters": {
            "kp": args.kp if args.controller in ("p", "pi") else None,
            "ki": args.ki if args.controller == "pi" else None,
            "ts": args.ts if args.controller == "pi" else args.ts,
        },
        "plant": args.plant,
        "profile": profile_name,
        "hold": args.hold if args.reference_values is None else None,
        "sample_count": len(refs),
        "safe_bounds": {
            "u_min": args.u_min,
            "u_max": args.u_max,
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
        "simulation_name",
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
    cfg = load_config(args.config)
    args = apply_config(args, cfg)

    result = run_sim(args)
    write_outputs(result, Path(args.out_dir))

    m = result["metrics"]
    print(f"simulation: {result['simulation_name']}")
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
