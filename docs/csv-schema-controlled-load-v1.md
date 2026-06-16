# Controlled Load CSV Schema v1

## Purpose

This document defines the CSV schema used by Controlled Load Layer 1.

Controlled Load Layer 1 is responsible for producing reproducible CSV datasets from controlled transaction-load experiments executed against the validated Solana Kubernetes observability environment.

The current implementation starts from the existing `collect_csv.py` workflow and will be extended toward the full Layer 1 dataset schema.

## Current collector output

The current `scripts/collect_csv.py` collector supports two modes:

- `steady`;
- `step`.

At this stage, the collector writes the following compatibility CSV header:

```text
t_iso,t_sec,u_cmd,sent_total,u_ach,lat_p99,inflight,err_per_sec

## Current fields
Field	Meaning
t_iso	Local timestamp of the sample.
t_sec	Seconds elapsed since collector start.
u_cmd	Commanded transaction rate sent to the load generator.
sent_total	Total submitted transaction count reported by the load generator.
u_ach	Achieved submitted throughput, usually computed as delta submitted count divided by delta time.
lat_p99	p99 transaction latency extracted from the configured Prometheus metric.
inflight	In-flight, pending or outstanding transaction count reported by the load generator.
err_per_sec	Error rate per second reported by the load generator, where available.
Target Layer 1 schema

## The target Controlled Load Layer 1 schema is:

timestamp_utc, experiment_id, phase, level_index, lambda_target, workers, burst,
inflight, sample, duration_seconds, submitted_tps, accepted_tps, error_rate,
saturation_score, slot_interval_p50, slot_interval_p90, slot_interval_p99,
tx_latency_p50, tx_latency_p95, tx_latency_p99, subscription_errors_total,
validator_health, controller_mode

Target field groups

The target schema separates the dataset into the following groups:

experiment identity: timestamp_utc, experiment_id, phase, level_index;
commanded workload: lambda_target, workers, burst;
load-generator state: inflight, sample, duration_seconds;
throughput response: submitted_tps, accepted_tps;
error response: error_rate, subscription_errors_total;
saturation response: saturation_score;
validator timing response: slot_interval_p50, slot_interval_p90, slot_interval_p99;
transaction latency response: tx_latency_p50, tx_latency_p95, tx_latency_p99;
health and execution mode: validator_health, controller_mode.

Compatibility rule

The current legacy output is retained temporarily because it matches the existing knee_step_test.sh and knee_probe_adaptive.sh workflow.

The next implementation step is to extend scripts/collect_csv.py so that it can emit:

--schema legacy
--schema layer1

# The legacy schema preserves the current workflow.

The layer1 schema emits the target Controlled Load Layer 1 fields.

Security rule

CSV output must not contain:

payer.json;
Solana private key material;
private SSH key material;
kubeconfig credentials;
Kubernetes tokens;
machine-local secret paths.

Generated CSV files may be committed only after manual inspection.

