# ADR-0001: Use a Layered Research Roadmap

## Status

Accepted

## Context

The project combines containerised Solana infrastructure, observability, controlled load generation, adaptive control, Kubernetes deployment, and future Agave/MARL research.

Mixing these stages too early would make results difficult to interpret.

## Decision

The project will follow a layered roadmap:

1. Observability Core
2. Dataset layer 0
3. Kubernetes observability core
4. Dataset layer 1 controlled load response
5. MPC adaptive control
6. RL/MARL
7. Agave research branch

## Consequences

Each layer must be independently reproducible before moving to the next layer.
