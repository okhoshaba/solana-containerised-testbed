from __future__ import annotations

from typing import Any, Dict, List


def build_scenarios(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    simulation_config = config["simulation"]
    target = float(simulation_config["target_throughput"])
    initial_replicas = int(simulation_config["initial_replicas"])

    nominal_throughput_per_replica = target / max(float(initial_replicas), 1.0)

    return [
        {
            "profile_id": "nominal_profile",
            "case_id": "nominal_step_up",
            "target_throughput": target,
            "initial_throughput": target * 0.70,
            "load_demand": target * 1.35,
            "throughput_per_replica": nominal_throughput_per_replica,
            "response_alpha": 0.35
        },
        {
            "profile_id": "elevated_profile",
            "case_id": "elevated_step_up",
            "target_throughput": target * 1.20,
            "initial_throughput": target * 0.75,
            "load_demand": target * 1.60,
            "throughput_per_replica": nominal_throughput_per_replica,
            "response_alpha": 0.30
        },
        {
            "profile_id": "conservative_profile",
            "case_id": "conservative_step_down",
            "target_throughput": target * 0.80,
            "initial_throughput": target * 0.95,
            "load_demand": target,
            "throughput_per_replica": nominal_throughput_per_replica,
            "response_alpha": 0.40
        }
    ]
