# Dataset Layer 0: Observability Validation

## Goal

Dataset layer 0 validates that the following pipeline works reproducibly:

```text
Solana validator
Yellowstone/Geyser
Solana latency monitor
Prometheus metrics
```

This dataset is a validation artifact, not a throughput benchmark.

## Runtime

The expected runtime is:

```bash
podman compose -f compose.yellowstone.release.yaml up
```

Endpoints:

```text
RPC:     http://127.0.0.1:8899
Metrics: http://127.0.0.1:9464/metrics
gRPC:    127.0.0.1:10000
```

## Output structure

Recommended output layout:

```text
output/datasets/layer0-observability/<run_id>/
  metadata.json
  samples.csv
  samples.jsonl
  raw-metrics.prom
```

## Candidate schema

```text
timestamp_utc
run_id
host_id
cpu_model
avx2_present
git_commit
testbed_version
validator_image
monitor_image
validator_health
payer_balance_sol
metrics_scrape_ok
slot_interval_p50
slot_interval_p90
slot_interval_p99
slot_interval_sum
slot_interval_count
transaction_latency_p50
transaction_latency_p95
transaction_latency_p99
transaction_latency_sum
transaction_latency_count
subscription_errors_total
```

## Default run profile

```text
duration: 60 seconds
sample interval: 2 seconds
```

## Success criteria

The run is successful if:

- validator health returns `ok`
- payer balance is available
- `/metrics` is reachable
- CSV and JSONL files are produced
- metadata is recorded
- the run is reproducible on at least two hosts
