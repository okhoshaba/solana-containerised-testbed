# Controlled Load Layer 1 for the Solana Kubernetes Observability Core

## Working title

Controlled Load Layer 1 for the Solana Kubernetes Observability Core

## Abstract draft

This preprint describes Controlled Load Layer 1 for the Solana Containerised Testbed. The work extends a validated KVM-based multi-node Kubernetes observability baseline with controlled, reproducible transaction load generation. The methodological sequence is infrastructure, observability, and then controlled load.

The implementation introduces a containerised transaction load generator, CSV collection tooling, Kubernetes manifests, PVC-backed result persistence, and validation procedures for local and in-cluster controlled-load execution. A candidate Kubernetes run using load levels `1 2 4 8` demonstrates that the controlled-load layer can drive transaction submission through an in-cluster Service, collect telemetry, persist results, and return to a safe idle state.

This stage is intentionally limited to controlled load generation and observability integration. It does not introduce MPC, reinforcement learning, MARL, adaptive policy learning, or Agave migration. The result is a reproducible experimental layer for later research into saturation analysis, control strategies, and high-load behaviour of Solana-oriented Kubernetes testbeds.

## Keywords

Solana; Kubernetes; observability; controlled load; transaction generation; reproducible experiments; KVM; blockchain infrastructure; containerised testbed.

## Introduction

- Motivation for reproducible Solana infrastructure experiments.
- Need for a staged research methodology.
- Existing baseline: Kubernetes Observability Core.
- New stage: Controlled Load Layer 1.
- Scope boundary: no MPC, no reinforcement learning, no MARL, no Agave migration.

## Baseline environment

Describe the validated baseline:

- dedicated KVM-based multi-node Kubernetes cluster;
- kubeadm deployment;
- validator node scheduling;
- observability node scheduling;
- validator RPC Service;
- metrics Service;
- Yellowstone/Geyser gRPC Service;
- wallet transfer validation;
- transaction latency telemetry.

## Controlled Load Layer 1 design

Describe:

- purpose of controlled transaction load;
- `loadgen2` role;
- control endpoint on port `7070`;
- `lambda` as target transaction rate;
- CSV collector role;
- Prometheus-compatible metrics endpoint;
- Kubernetes PVC result persistence.

## Repository implementation

Describe repository additions:

- `loadgen2/`;
- `scripts/collect_csv.py`;
- knee-step and probe scripts;
- `dashboard/`;
- `containers/`;
- `k8s/controlled-load/`;
- validation notes;
- raw and derived candidate run outputs.

## Kubernetes deployment model

Describe:

- existing `solana-observability` namespace;
- `solana-loadgen2` Deployment;
- `solana-loadgen2` Service;
- `controlled-load-results-pvc`;
- `controlled-load-knee-step` Job;
- runtime Secret for payer keypair;
- no key material committed to Git.

## Validation procedure

Describe:

- local smoke-test;
- Kubernetes smoke-test;
- candidate reproducible run;
- post-run safe idle check.

Candidate run configuration:

- levels: 1 2 4 8
- hold: 60 seconds per level
- sample: 5 seconds
- rate_key: lambda

Observed post-run state:

- target_lambda: 0
- sent_total: 1401
- ok_total: 1401
- err_total: 0
- inflight: 0
- last_err: ""

## Results

Planned content:

- table from summary_by_level.csv;
- discussion of submitted versus achieved throughput;
- error rate;
- inflight behaviour;
- limitations of the current latency quantile collection;
- interpretation of the candidate run as validation evidence rather than final benchmarking.

## Reproducibility

Describe:

- Git branch and release tag;
- container images;
- Kubernetes manifests;
- runtime Secret creation;
- commands required to apply manifests;
- commands required to run the Job;
- location of raw and derived outputs.


## Limitations

Current limitations:

- no formal saturation model yet;
- no validated knee-point detector yet;
- no control feedback loop;
- no MPC;
- no reinforcement learning or MARL;
- candidate run is a validation run, not a general performance benchmark;
- results depend on the specific KVM, Kubernetes, storage, network, and validator configuration.

## Future work

Potential next stages:

- longer controlled-load experiments;
- wider load schedules;
- repeated-run variance analysis;
- saturation/knee-point estimation;
- controller design;
- MPC as a later branch;
- comparison across Kubernetes placements;
- dataset publication as a separate Zenodo record.

## Data and software availability

Software:

- GitHub repository: https://github.com/okhoshaba/solana-containerised-testbed
- Planned software release: v0.5.0-controlled-load-layer1
- Zenodo DOI: 10.5281/zenodo.20742321.

Data:

Candidate raw CSV:
data/raw/controlled-load-layer1/20260617T223738Z/knee_step_candidate_20260617T223738Z.csv

## Derived summary:
results/controlled-load-layer1/20260617T223738Z/summary_by_level.csv

## Citation placeholder

To be added after Zenodo Software and Preprint publication.
