# Kubernetes Observability Core

## Goal

Move the Level 1 observability core to Kubernetes without introducing load generation or adaptive control.

## Boundary

This stage is about the object/environment, not about an RL agent.

Kubernetes hosts the environment. It is not the controller and not the learning policy.

## Included

- validator with Yellowstone/Geyser enabled
- wallet-init job
- monitor
- PVC for validator ledger
- service for RPC
- service for gRPC
- service for metrics

## Excluded

- loadgen
- dashboard
- MPC
- single-agent RL
- MARL
- Agave

## Future-controller-ready requirements

The environment should provide stable service names, explicit RPC/gRPC/metrics endpoints,
resettable validator state, reproducible run IDs, configurable resource limits, and later actuator interfaces.
