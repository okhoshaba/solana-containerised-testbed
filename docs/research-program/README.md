# Research Program

This directory documents the research roadmap built around the Solana Containerised Testbed.

The current software baseline is:

- Solana Containerised Testbed v0.2.0
- Solana v1.18.25 local validator
- no-AVX2 compatibility build
- Yellowstone/Geyser-enabled validator image
- containerised Solana latency monitor
- Prometheus metrics endpoint

## Publications and identifiers

Software concept DOI:

- https://doi.org/10.5281/zenodo.20095383

Software v0.2.0 DOI:

- https://doi.org/10.5281/zenodo.20132465

Technical report DOI:

- https://doi.org/10.5281/zenodo.20098291

## Research levels

1. Observability Core
2. Dataset layer 0: observability validation
3. Kubernetes deployment of the observability core
4. Dataset layer 1: controlled load response
5. MPC adaptive control
6. RL and MARL extensions
7. Agave research branch

The key principle is to avoid mixing research levels too early. Each layer must be independently reproducible before moving to the next layer.
