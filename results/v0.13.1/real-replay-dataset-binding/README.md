# v0.13.1 real replay dataset binding results

This directory contains the offline-only dataset inspection outputs for v0.13.1.

## Purpose

The goal is to determine whether real v0.8.0 replay datasets exist in the repository and whether they can be bound to the config-driven shadow-mode controller runner introduced in v0.13.0.

## Files

- replay-dataset-inventory.json: full CSV inventory across preferred and secondary search roots.
- replay-binding-summary.json: decision summary and optional recommended binding.

## Search roots

Preferred real replay candidates:

- results/v0.8.0/**/*.csv

Secondary candidates:

- results/v0.6.0/**/*.csv
- results/v0.7.0/**/*.csv

Secondary candidates are reported for evidence only. They are not promoted to recommended_binding.

## Decision interpretation

REAL_REPLAY_BINDING_CANDIDATE_FOUND means that at least one suitable v0.8.0 CSV file was found.

REAL_REPLAY_BINDING_NOT_AVAILABLE means that no suitable v0.8.0 CSV file was found. This is not a controller failure.

## Safety scope

This stage is offline-only.

It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.

## Reproduction

    python3 scripts/v0.13.1/inspect-replay-datasets.py --config configs/v0.13.1/real-replay-binding.json
