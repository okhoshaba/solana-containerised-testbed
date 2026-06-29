from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimpleThroughputPlant:
    current_throughput: float
    throughput_per_replica: float
    response_alpha: float

    def step(self, replicas: int, load_demand: float) -> float:
        capacity = self.throughput_per_replica * float(replicas)
        steady_state_throughput = min(float(load_demand), capacity)

        alpha = max(0.0, min(1.0, float(self.response_alpha)))
        self.current_throughput = (
            alpha * steady_state_throughput
            + (1.0 - alpha) * self.current_throughput
        )
        return self.current_throughput
