from __future__ import annotations

from typing import Any, Dict, List, Tuple

from offline_simulation.controllers import build_controller
from offline_simulation.metrics import aggregate_metrics, compute_case_metrics
from offline_simulation.plant import SimpleThroughputPlant
from offline_simulation.scenarios import build_scenarios


def run_simulation_platform(config: Dict[str, Any]) -> Dict[str, Any]:
    all_timeseries_rows: List[Dict[str, Any]] = []
    all_case_metrics: List[Dict[str, Any]] = []

    enabled_controllers = [
        controller_config
        for controller_config in config["controllers"]
        if controller_config.get("enabled", False)
    ]

    if not enabled_controllers:
        raise ValueError("No enabled controllers found in config.")

    scenarios = build_scenarios(config)

    for controller_config in enabled_controllers:
        controller = build_controller(controller_config, config)

        for scenario in scenarios:
            case_rows = run_single_case(config, controller, scenario)
            all_timeseries_rows.extend(case_rows)
            all_case_metrics.append(compute_case_metrics(case_rows))

    controller_comparison = aggregate_metrics(all_case_metrics, "controller")
    profile_metrics = aggregate_metrics(all_case_metrics, "profile_id")

    return {
        "timeseries_rows": all_timeseries_rows,
        "case_metrics": all_case_metrics,
        "controller_comparison": controller_comparison,
        "profile_metrics": profile_metrics,
        "summary": build_summary(config, all_case_metrics, controller_comparison)
    }


def run_single_case(config: Dict[str, Any], controller: Any, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
    simulation_config = config["simulation"]

    horizon_steps = int(simulation_config["horizon_steps"])
    current_replicas = int(simulation_config["initial_replicas"])

    min_replicas = int(simulation_config["min_replicas"])
    max_replicas = int(simulation_config["max_replicas"])
    replica_step_limit = int(simulation_config["replica_step_limit"])

    plant = SimpleThroughputPlant(
        current_throughput=float(scenario["initial_throughput"]),
        throughput_per_replica=float(scenario["throughput_per_replica"]),
        response_alpha=float(scenario["response_alpha"])
    )

    controller.reset(
        {
            "scenario": scenario,
            "initial_replicas": current_replicas,
            "initial_throughput": plant.current_throughput
        }
    )

    rows = []
    for time_step in range(horizon_steps):
        current_throughput = plant.current_throughput
        target_throughput = float(scenario["target_throughput"])
        error = target_throughput - current_throughput

        observation = {
            "time_step": time_step,
            "profile_id": scenario["profile_id"],
            "case_id": scenario["case_id"],
            "current_throughput": current_throughput,
            "target_throughput": target_throughput,
            "current_replicas": current_replicas,
            "error": error
        }

        action = controller.step(observation)
        desired_replicas = int(action["desired_replicas"])
        safe_replicas, constraint_violation = apply_safety_constraints(
            desired_replicas=desired_replicas,
            current_replicas=current_replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            replica_step_limit=replica_step_limit
        )

        applied_replica_delta = safe_replicas - current_replicas
        next_throughput = plant.step(
            replicas=safe_replicas,
            load_demand=float(scenario["load_demand"])
        )

        rows.append(
            {
                "controller": controller.name,
                "profile_id": scenario["profile_id"],
                "case_id": scenario["case_id"],
                "time_step": time_step,
                "target_throughput": target_throughput,
                "current_throughput": current_throughput,
                "error": error,
                "current_replicas": current_replicas,
                "desired_replicas": desired_replicas,
                "safe_replicas": safe_replicas,
                "applied_replica_delta": applied_replica_delta,
                "raw_control_signal": float(action["raw_control_signal"]),
                "clipped_control_signal": float(action["clipped_control_signal"]),
                "constraint_violation": int(constraint_violation),
                "next_throughput": next_throughput
            }
        )

        current_replicas = safe_replicas

    return rows


def apply_safety_constraints(
    desired_replicas: int,
    current_replicas: int,
    min_replicas: int,
    max_replicas: int,
    replica_step_limit: int
) -> Tuple[int, bool]:
    lower_step = current_replicas - replica_step_limit
    upper_step = current_replicas + replica_step_limit

    safe_replicas = max(lower_step, min(upper_step, desired_replicas))
    safe_replicas = max(min_replicas, min(max_replicas, safe_replicas))

    return int(safe_replicas), int(safe_replicas) != int(desired_replicas)


def build_summary(
    config: Dict[str, Any],
    case_metrics: List[Dict[str, Any]],
    controller_comparison: List[Dict[str, Any]]
) -> Dict[str, Any]:
    total_constraint_violations = sum(
        int(metric["constraint_violations"])
        for metric in case_metrics
    )

    return {
        "stage": config["stage"],
        "name": config["name"],
        "decision": "pass",
        "platform_status": "usable_minimal_platform",
        "reference_controller": config["reference_controller"]["name"],
        "controller_interface_status": "implemented",
        "replaceable_controller_architecture": True,
        "case_count": len(case_metrics),
        "controller_count": len(controller_comparison),
        "total_constraint_violations": total_constraint_violations
    }
