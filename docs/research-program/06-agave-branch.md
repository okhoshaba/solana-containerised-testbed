# Agave Research Branch

## Motivation

Agave should be treated as a separate research branch, not as an immediate replacement for the current Solana v1.18.25 local testbed.

## Rationale

The current project baseline is based on:

- Solana v1.18.25
- no-AVX2 compatibility
- Yellowstone/Geyser
- monitor
- Prometheus metrics

Agave introduces a different validator implementation line and likely different operational assumptions.

## Recommended approach

Agave work should start only after:

1. Dataset layer 0 is validated.
2. Kubernetes observability core is available.
3. Controlled load response workflow is specified.

## Agave branch goals

The Agave research branch should define:

- exact Agave version
- compatible Geyser/Yellowstone path
- deployment topology
- resource requirements
- observability model
- comparison baseline against the existing Solana v1.18.25 testbed
