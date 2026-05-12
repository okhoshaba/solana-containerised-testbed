# Research Roadmap

## Level 1: Observability Core

The first level establishes:

```text
validator + Yellowstone/Geyser + monitor + Prometheus metrics
```

## Dataset layer 0

Dataset layer 0 validates observability. It is not a throughput benchmark.

## Kubernetes Observability Core

Kubernetes should initially deploy only the same observability core:

- validator
- wallet-init job
- monitor
- services
- PVC

It should not include loadgen, dashboard, MPC, single-agent RL, MARL or Agave.

Kubernetes should be future-controller-ready, but it is not the controller and not the learning policy.

## Dataset layer 1

Dataset layer 1 introduces controlled load and response measurement.

## MPC

MPC comes after Dataset layer 1, when controlled response data exists.

## Single-Agent RL

Single-agent RL comes after Dataset layer 1 and after an MPC baseline.

## MARL

MARL is a later extension after single-agent RL.

## Agave

Agave is a separate research branch.
