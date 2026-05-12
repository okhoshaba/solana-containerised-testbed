# Research Roadmap

## Level 1: Observability Core

The first level establishes a reproducible local observability core:

```text
validator + Yellowstone/Geyser + monitor + Prometheus metrics
```

The purpose is to prove that the system can expose reproducible runtime observations before introducing external load.

## Dataset layer 0: Observability Validation

Dataset layer 0 validates the observability pipeline.

This dataset is not intended to measure maximum throughput.

## Kubernetes Observability Core

After Dataset layer 0 is validated, the same core should be deployed to Kubernetes.

The Kubernetes stage should initially include only:

- validator
- wallet-init job
- monitor
- services
- PVC for ledger data

It should not yet include loadgen, dashboard, MPC, or RL/MARL.

## Dataset layer 1: Controlled Load Response

The second dataset layer introduces controlled load generation.

## Adaptive control

The adaptive control line should progress through:

1. rule-based control
2. knee detection
3. MPC
4. single-agent RL
5. MARL

## Agave research branch

Agave should be treated as a separate research branch and not as a simple replacement for the current Solana v1.18.25 local testbed.
