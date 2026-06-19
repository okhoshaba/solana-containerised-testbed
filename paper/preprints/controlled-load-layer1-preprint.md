# Controlled Load Layer 1 for the Solana Kubernetes Observability Core

Preprint DOI: `10.5281/zenodo.20755604`.


## Abstract

This preprint describes Controlled Load Layer 1 for the Solana Containerised Testbed. The work extends a validated KVM-based multi-node Kubernetes observability baseline with controlled, reproducible transaction load generation. The methodological sequence is infrastructure, observability, and then controlled load.

The implementation introduces a containerised transaction load generator, CSV collection tooling, Kubernetes manifests, PVC-backed result persistence, and validation procedures for local and in-cluster controlled-load execution. The controlled-load layer runs inside the existing `solana-observability` namespace and uses the in-cluster Solana RPC and metrics Services already validated by the observability baseline.

A candidate Kubernetes run using commanded load levels of `1`, `2`, `4`, and `8` transactions per second demonstrates that the controlled-load layer can drive transaction submission through an in-cluster Service, collect telemetry, persist results, and return to a safe idle state. The achieved mean rates were `1.015567`, `1.895051`, `3.822429`, and `7.664078` transactions per second respectively, with zero observed error rate in the derived per-level summary. After the run, `loadgen2` reported `sent_total=1401`, `ok_total=1401`, `err_total=0`, `inflight=0`, and an empty `last_err`.

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

The candidate run used a four-level knee-step schedule with commanded load levels of `1`, `2`, `4`, and `8` transactions per second. Each level was held for 60 seconds, and the collector sampled every 5 seconds. The generated raw CSV and derived summary are stored in the repository; the exact paths are listed in the Data and software availability section.

The per-level summary is shown below.

| u_cmd | n | sent_delta | u_ach_mean | err/s | max_inflight | p99_n |
|---:|---:|---:|---:|---:|---:|---:|
| 1.000 | 12 | 56  | 1.015567 | 0.000000 | 0 | 0 |
| 2.000 | 12 | 109 | 1.895051 | 0.000000 | 0 | 0 |
| 4.000 | 12 | 220 | 3.822429 | 0.000000 | 0 | 0 |
| 8.000 | 12 | 441 | 7.664078 | 0.000000 | 0 | 0 |

In the table, `u_cmd` is the commanded transaction rate, `n` is the number of samples at that level, `u_ach_mean` is the mean achieved rate, `err/s` is the mean error rate, and `p99_n` is the number of latency-p99 samples observed in the derived summary.

The results show that the controlled-load layer was able to increase submitted transaction load according to the configured schedule. The achieved rates tracked the commanded levels closely enough for a first validation run: approximately `1.02`, `1.90`, `3.82`, and `7.66` transactions per second for commanded levels `1`, `2`, `4`, and `8`.

No errors were observed in the derived per-level summary. The post-run `loadgen2` state reported `sent_total=1401`, `ok_total=1401`, `err_total=0`, `inflight=0`, `target_lambda=0`, and an empty `last_err`. This confirms that the run completed, accepted transactions matched submitted transactions at the cumulative counter level, and the system returned to an idle state after the experiment.

The current candidate run should be interpreted as validation evidence rather than a general benchmark. It validates the experimental path from Kubernetes Job to `loadgen2`, Solana RPC, metrics collection, PVC persistence, and repository-level evidence capture. It does not yet establish saturation limits, knee points, or production performance claims.

A notable limitation of this candidate run is that the derived summary contains zero observed `lat_p99` samples. Therefore, the present result validates throughput control and error-free execution, but it should not be used to make latency-distribution claims. Later runs should improve latency quantile capture and include repeated trials for variance analysis.

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

This stage has several intentional limitations.

First, the candidate run is a validation run, not a full benchmark. It demonstrates that Controlled Load Layer 1 works end-to-end, but it does not claim to characterise the maximum capacity of the cluster or validator.

Second, the current run does not provide validated saturation or knee-point detection. The load levels were deliberately modest (`1`, `2`, `4`, and `8` transactions per second) so that the first candidate run could validate the control and measurement path before higher-load experiments.

Third, the derived summary contains no observed `lat_p99` samples. The current evidence is therefore suitable for validating transaction submission, success counters, error counters, and experiment persistence, but not for drawing latency distribution conclusions.

Fourth, the results depend on the specific KVM, Kubernetes, storage, network, validator, and container-image configuration used in this testbed. The experiment is reproducible as a testbed procedure, but the absolute numbers should not be generalised to other Solana deployments.

Finally, this work does not introduce MPC, reinforcement learning, MARL, adaptive policy learning, or Agave migration. These remain later or separate research branches.

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

Software release: Solana Containerised Testbed `v0.5.0-controlled-load-layer1`.

Software DOI: `10.5281/zenodo.20742321`.

Repository: `https://github.com/okhoshaba/solana-containerised-testbed`.

Candidate raw CSV:

- directory: `data/raw/controlled-load-layer1/20260617T223738Z/`
- file: `knee_step_candidate_20260617T223738Z.csv`

Derived summary:

- directory: `results/controlled-load-layer1/20260617T223738Z/`
- file: `summary_by_level.csv`

## Citation

The associated software release is archived on Zenodo:

Oleksandr Khoshaba. Solana Containerised Testbed `v0.5.0-controlled-load-layer1`. Zenodo. DOI: `10.5281/zenodo.20742321`. URL: `https://doi.org/10.5281/zenodo.20742321`.

Preprint DOI: `10.5281/zenodo.20755604`. Preprint URL: `https://doi.org/10.5281/zenodo.20755604`.

The preprint citation should use the Zenodo record DOI listed above.
