# Research Program

This directory documents the research roadmap built around the Solana Containerised Testbed.

## Baseline

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

Original technical report DOI:
- https://doi.org/10.5281/zenodo.20098291

Yellowstone/Geyser v0.2.0 technical note DOI:
- https://doi.org/10.5281/zenodo.20167936

## Technical note citation

Khoshaba, O. (2026). *Yellowstone/Geyser Observability Extension for the Solana Containerised Testbed v0.2.0* (0.2.0). Zenodo. https://doi.org/10.5281/zenodo.20167936

## Accepted roadmap

1. Observability Core
2. Dataset layer 0: observability validation
3. Kubernetes deployment of the observability core
4. Dataset layer 1: controlled load response
5. MPC adaptive control
6. Single-agent RL
7. MARL
8. Agave research branch

Each layer must be independently reproducible before moving to the next layer.
