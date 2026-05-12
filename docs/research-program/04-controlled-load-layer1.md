# Dataset Layer 1: Controlled Load Response

## Goal

Dataset layer 1 captures the response of the Solana/Agave testbed under controlled synthetic load.

This layer belongs after:

1. Dataset layer 0
2. Kubernetes observability core

## Existing business process

The existing workflow includes:

```text
loadgen2_bin
knee_step_test.sh
knee_probe_adaptive.sh
mpc_dashboard_v2.py
CSV output
analysis scripts
```

## Candidate parameters

```text
lambda
workers
burst
inflight
sample
duration_seconds
level_index
phase
```

## Candidate response fields

```text
submitted_tps
accepted_tps
error_rate
slot_interval_p50
slot_interval_p90
slot_interval_p99
tx_latency_p50
tx_latency_p95
tx_latency_p99
subscription_errors_total
saturation_score
validator_health
```

## Important rule

Private key material such as `payer.json` must never be committed to Git.
