# v0.16.0 modular offline simulation platform

## Purpose

This directory contains the first generated artefacts from the v0.16.0 modular offline controller simulation platform.

## Controller

Reference controller: reference_p_only_v0.14.3

## Status

Platform status: usable_minimal_platform

Decision: pass

## Scope

This run validates the initial platform architecture with a replaceable controller interface and the v0.14.3 P-only baseline as the reference controller.

It does not attempt to improve MPC or introduce strict MPC optimization.

## Generated artefacts

- simulation-summary.json
- controller-comparison.csv
- case-metrics.csv
- profile-metrics.csv
- reference-controller-metrics.json
- timeseries.csv

## Reproduction

Run from repository root:

```bash
python3 scripts/v0.16.0/run-modular-offline-simulation-platform.py --config configs/v0.16.0/modular-offline-simulation-platform.json
```
