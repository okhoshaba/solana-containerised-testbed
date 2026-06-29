from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


class Controller(Protocol):
    name: str

    def reset(self, initial_state: Dict[str, Any]) -> None:
        ...

    def step(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        ...


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass
class POnlyController:
    name: str
    kp: float
    min_replicas: int
    max_replicas: int
    replica_step_limit: int

    def reset(self, initial_state: Dict[str, Any]) -> None:
        return None

    def step(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        current_replicas = int(observation["current_replicas"])
        error = float(observation["target_throughput"]) - float(observation["current_throughput"])

        raw_delta = self.kp * error
        clipped_delta = _clip(raw_delta, -self.replica_step_limit, self.replica_step_limit)

        desired_replicas = int(round(current_replicas + clipped_delta))
        desired_replicas = int(_clip(desired_replicas, self.min_replicas, self.max_replicas))

        return {
            "desired_replicas": desired_replicas,
            "replica_delta": desired_replicas - current_replicas,
            "raw_control_signal": raw_delta,
            "clipped_control_signal": clipped_delta,
            "controller_metadata": {
                "type": "p_only",
                "kp": self.kp
            }
        }


def build_controller(controller_config: Dict[str, Any], platform_config: Dict[str, Any]) -> Controller:
    simulation_config = platform_config["simulation"]
    reference_config = platform_config["reference_controller"]

    controller_type = controller_config["type"]
    if controller_type != "p_only":
        raise ValueError(f"Unsupported controller type: {controller_type}")

    parameters = reference_config.get("parameters", {})
    return POnlyController(
        name=controller_config["name"],
        kp=float(parameters.get("kp", 0.35)),
        min_replicas=int(simulation_config["min_replicas"]),
        max_replicas=int(simulation_config["max_replicas"]),
        replica_step_limit=int(simulation_config["replica_step_limit"])
    )
