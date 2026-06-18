# Controlled Load Layer 1 for the Solana Kubernetes Observability Core

## Abstract

This preprint describes Controlled Load Layer 1 for the Solana Containerised Testbed. The work extends a validated KVM-based multi-node Kubernetes observability baseline with controlled, reproducible transaction load generation. The methodological sequence is infrastructure, observability, and then controlled load.

The implementation introduces a containerised transaction load generator, CSV collection tooling, Kubernetes manifests, PVC-backed result persistence, and validation procedures for local and in-cluster controlled-load execution. The controlled-load layer is deployed into the existing `solana-observability` namespace and uses the in-cluster `solana-rpc:8899` and `solana-metrics:9464` Services.

A candidate Kubernetes run using load levels `1 2 4 8`, 60 seconds per level, and 5 second sampling demonstrates that the layer can control transaction submission through an in-cluster Service, collect telemetry, persist results, and return to a safe idle state. The post-run state reported `sent_total=1401`, `ok_total=1401`, `err_total=0`, and an empty `last_err`.

This stage is intentionally limited to controlled load generation and observability integration. It does not introduce MPC, reinforcement learning, MARL, adaptive policy learning, or Agave migration. The result is a reproducible experimental layer for later research into saturation analysis, control strategies, and high-load behaviour of Solana-oriented Kubernetes testbeds.

## Keywords

Solana; Kubernetes; observability; controlled load; transaction generation; reproducible experiments; KVM; blockchain infrastructure; containerised testbed; distributed systems.

## 1. Introduction

Reproducible infrastructure experiments require a clear separation between infrastructure construction, observability validation, and load generation. The Solana Containerised Testbed follows this staged methodology in order to avoid mixing cluster deployment, telemetry collection, and workload injection into a single uncontrolled experimental step.

The baseline preceding this work established a dedicated KVM-based multi-node Kubernetes environment for Solana-oriented observability. That baseline validated the ability to run the validator workload, expose RPC and telemetry services, perform wallet-transfer validation, and observe transaction-latency telemetry.

Controlled Load Layer 1 adds the next methodological layer: reproducible transaction load generation. Its purpose is not to claim production benchmarking performance. Instead, it provides a controlled experimental mechanism for submitting transaction load at defined target rates, collecting CSV telemetry, and persisting output in a Kubernetes-native way.

The contribution of this stage is a working controlled-load layer that can be executed locally and inside Kubernetes while preserving repository hygiene and avoiding private key material in Git.

## 2. Baseline environment

The controlled-load layer builds on the previously validated Kubernetes Observability Core baseline. The relevant baseline properties are:

- a dedicated KVM-based multi-node Kubernetes cluster;
- kubeadm-based Kubernetes deployment;
- validator workload scheduled on nodes labelled `testbed-role=validator`;
- observability workload scheduled on nodes labelled `testbed-role=observability`;
- validator RPC Service on port `8899`;
- metrics Service on port `9464`;
- Yellowstone/Geyser gRPC Service on port `10000`;
- successful wallet-transfer validation;
- observed transaction-latency telemetry.

The controlled-load work deliberately reuses this validated environment instead of creating a separate cluster. This keeps the experimental sequence explicit:

```text
infrastructure -> observability -> controlled load
```

## 3. Controlled Load Layer 1 design

Controlled Load Layer 1 introduces transaction load generation at a defined target rate. The central runtime component is `loadgen2`, a transaction load generator with an HTTP control interface.

The control model is intentionally simple. A target transaction rate is expressed through `lambda`, and the load generator exposes a control endpoint on port `7070`. Supporting scripts and CSV collection tooling are used to execute step-based load schedules and record runtime telemetry.

The layer includes:

- `loadgen2`, the controlled transaction load generator;
- `scripts/collect_csv.py`, the CSV collection tool;
- knee-step and probe execution scripts;
- a controlled-load dashboard script;
- container definitions for the load generator and tools image;
- Kubernetes manifests for in-cluster execution;
- PVC-backed result persistence.

The payer keypair is treated as runtime secret material. It is not stored in the repository. For Kubernetes execution it is provided through a manually created Secret named `solana-payer-keypair`.

## 4. Kubernetes implementation

The Kubernetes implementation runs in the existing `solana-observability` namespace. This namespace already contains the Solana observability baseline services required by the controlled-load layer.

The controlled-load manifests add:

- `solana-loadgen2` Deployment;
- `solana-loadgen2` ClusterIP Service on port `7070`;
- `controlled-load-results-pvc`;
- `controlled-load-knee-step` Job;
- runtime use of the manually created `solana-payer-keypair` Secret.

The Deployment runs the load generator with `lambda=0` by default, which means that the controlled-load endpoint is available but not actively generating transaction load until a Job or operator changes the target rate.

The Job controls `loadgen2` through the in-cluster Service:

```text
http://solana-loadgen2:7070
```

The Job reads metrics from:

```text
http://solana-metrics:9464
```

and submits transactions through the existing Solana RPC Service:

```text
http://solana-rpc:8899
```

The experiment output is written into the `controlled-load-results-pvc` PVC and can be copied out after completion for archival or analysis.

## 5. Validation methodology

Validation was performed in three stages.

First, a local container smoke test confirmed that the containerised load generator could start, read the payer keypair from outside the repository, reach RPC and metrics endpoints through local port-forwarding, and generate CSV output at a small target load.

Second, a Kubernetes smoke test confirmed that the Deployment, Service, PVC, Secret mount, and Job execution path worked inside the cluster. The Job completed successfully, wrote a CSV file to the PVC, and returned the load generator to `target_lambda=0`.

Third, a candidate reproducible Kubernetes run was executed with a multi-level load schedule:

```text
levels: 1 2 4 8
hold: 60 seconds per level
sample: 5 seconds
rate_key: lambda
```

The objective of this candidate run was to validate controlled-load operation and data collection, not to establish a final saturation model.

## 6. Candidate run results

The candidate run generated the raw CSV file:

```text
data/raw/controlled-load-layer1/20260617T223738Z/knee_step_candidate_20260617T223738Z.csv
```

A derived per-level summary was created at:

```text
results/controlled-load-layer1/20260617T223738Z/summary_by_level.csv
```

The post-run `loadgen2` state was:

```text
target_lambda: 0
sent_total: 1401
ok_total: 1401
err_total: 0
inflight: 0
last_err: ""
```

The per-level summary is shown below.

| Target `lambda` | Samples | Sent delta | Mean achieved tx/s | Mean error rate | Max inflight | Latency p99 samples |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 12 | 56  | 1.015567 | 0.000000 | 0 | 0 |
| 2 | 12 | 109 | 1.895051 | 0.000000 | 0 | 0 |
| 4 | 12 | 220 | 3.822429 | 0.000000 | 0 | 0 |
| 8 | 12 | 441 | 7.664078 | 0.000000 | 0 | 0 |

The achieved throughput follows the configured target load levels closely. The run reports zero error rate at each level, and the final state confirms that all submitted transactions were accepted according to the load generator counters.

The `lat_p99_observed_samples` value is zero in this candidate summary. This is treated as a limitation of the candidate run rather than as evidence of zero latency. The run validates the throughput-control and data-persistence path, while latency quantile collection requires further instrumentation review and repeated experiments.

## 7. Reproducibility

The software release associated with this work is:

```text
Solana Containerised Testbed v0.5.0-controlled-load-layer1
DOI: 10.5281/zenodo.20742321
```

The repository release tag is:

```text
v0.5.0-controlled-load-layer1
```

The Kubernetes manifests are stored under:

```text
k8s/controlled-load/
```

The container images referenced by the manifests are:

```text
docker.io/khoshaba/solana-loadgen2:layer1
docker.io/khoshaba/solana-controlled-load-tools:layer1
```

The payer keypair is not stored in Git. For Kubernetes execution, it is created manually as a runtime Secret:

```bash
kubectl -n solana-observability create secret generic solana-payer-keypair \
  --from-file=payer.json=/home/khoshaba/solana-secrets/payer.json
```

The controlled-load manifests can be rendered with:

```bash
kubectl kustomize k8s/controlled-load
```

and applied with:

```bash
kubectl apply -k k8s/controlled-load
```

Generated smoke-test extraction directories are ignored by Git. Candidate run evidence intended for archival is stored explicitly under `data/raw/` and `results/`.

## 8. Limitations

This work has several limitations.

First, the candidate run is a validation run rather than a final performance benchmark. It demonstrates that controlled transaction load can be generated and observed, but it does not establish general Solana performance claims.

Second, the current stage does not define a formal saturation model or validated knee-point detector. The knee-step execution path exists, but saturation analysis remains future work.

Third, latency quantile data were not observed in the candidate run summary. This requires additional validation of metric naming, quantile availability, and collection timing.

Fourth, the experiment depends on the specific KVM, Kubernetes, storage, network, and validator configuration used in the testbed.

Finally, this stage deliberately excludes MPC, reinforcement learning, MARL, adaptive policy learning, and Agave migration.

## 9. Future work

Future work will extend this layer through:

- longer controlled-load experiments;
- repeated runs for variance analysis;
- wider load schedules;
- latency quantile instrumentation review;
- saturation and knee-point estimation;
- controller design as a later research branch;
- comparison across node placements and resource allocations;
- publication of larger controlled-load datasets as separate archival records.

## Data and software availability

Software release:

```text
Solana Containerised Testbed v0.5.0-controlled-load-layer1
DOI: 10.5281/zenodo.20742321
```

Repository:

```text
https://github.com/okhoshaba/solana-containerised-testbed
```

Candidate raw CSV:

```text
data/raw/controlled-load-layer1/20260617T223738Z/knee_step_candidate_20260617T223738Z.csv
```

Derived summary:

```text
results/controlled-load-layer1/20260617T223738Z/summary_by_level.csv
```

## Citation

Khoshaba, O. Solana Containerised Testbed v0.5.0-controlled-load-layer1. Zenodo. https://doi.org/10.5281/zenodo.20742321
