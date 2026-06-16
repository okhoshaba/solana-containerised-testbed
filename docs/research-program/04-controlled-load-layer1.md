# Controlled Load Layer 1

## Purpose

This document defines the next research stage after the validated `v0.4.0` dedicated KVM multi-node Kubernetes deployment of the Solana Kubernetes Observability Core.

The purpose of this stage is to introduce controlled, reproducible transaction load into the already validated observability environment and to produce a documented CSV dataset layer from the observed system response.

The current methodological position is:

```text
infrastructure -> observability -> controlled load -> dataset
```

This stage must not introduce MPC, single-agent reinforcement learning, MARL, or Agave. Those remain later or separate research branches.

## Starting point

The starting point is the validated `v0.4.0` baseline:

- dedicated KVM-based multi-node Kubernetes cluster;
- kubeadm-based Kubernetes deployment;
- validator workload scheduled on `testbed-role=validator`;
- monitor workload scheduled on `testbed-role=observability`;
- validator ledger PVC using `local-path`;
- RPC Service on port `8899`;
- Yellowstone/Geyser gRPC Service on port `10000`;
- metrics Service on port `9464`;
- wallet transfer validation completed successfully;
- transaction latency telemetry observed.

The associated software release is:

```text
Solana Containerised Testbed v0.4.0
DOI: 10.5281/zenodo.20551170
```

The associated technical report is:

```text
Dedicated KVM Multi-Node Kubernetes Deployment of the Solana Kubernetes Observability Core
DOI: 10.5281/zenodo.20561100
```

## Main objective

The main objective of Controlled Load Layer 1 is to containerise, execute, and document a controlled transaction workload that can be repeated, measured, compared, and preserved as a dataset.

The first success criterion is not maximum throughput.

The first success criterion is reproducibility.

This layer should make it possible to answer the following question:

```text
How does the validated Solana Kubernetes observability environment respond to controlled, reproducible transaction load?
```

## Existing controlled-load workflow

The current Layer 1 implementation is based on the existing controlled-load workflow prepared before this stage.

The workflow includes:

- `loadgen2`;
- `collect_csv.py`;
- `knee_step_test.sh`;
- `knee_probe_adaptive.sh`;
- CSV output;
- analysis scripts;
- controlled-load dashboard code.

This workflow should now be cleaned, containerised, documented, and integrated into the repository as a reproducible Dataset Layer 1 component.

## Scope

Controlled Load Layer 1 covers:

- containerisation of the `loadgen2` transaction load generator;
- containerisation of supporting scripts and analysis tools;
- execution of controlled step-load experiments;
- optional knee-probe execution to identify useful load ranges;
- CSV collection from load-generator, RPC, and metrics endpoints;
- documentation of the CSV schema;
- preservation of raw outputs suitable for later analysis;
- Kubernetes execution using Jobs, Services, ConfigMaps, Secrets, and PVCs where appropriate;
- explicit separation between runtime secrets and version-controlled artefacts.

## Out of scope

This layer does not introduce:

- MPC;
- reinforcement learning;
- multi-agent reinforcement learning;
- Agave migration;
- production-grade validator optimisation;
- autonomous control policies;
- closed-loop policy learning;
- economic modelling of validator behaviour.

Adaptive probing may be used only as an engineering tool to locate a useful load range. It is not treated as a control-system research contribution at this layer.

## Workload model

The controlled workload should remain transparent and reproducible.

The initial workload model is based on native SOL transfers submitted through the existing Kubernetes RPC endpoint.

The workload should support:

- configurable target transaction rate;
- configurable worker count;
- configurable burst or in-flight behaviour where supported by the generator;
- explicit experiment identifier;
- timestamped CSV output;
- controlled duration per load level;
- compatibility with the existing RPC endpoint;
- compatibility with the existing observability and metrics endpoints.

The default RPC endpoint inside Kubernetes remains:

```text
http://solana-rpc:8899
```

For local or port-forwarded execution, the RPC endpoint may be overridden by environment variables or command-line arguments.

## Dataset objective

The dataset should describe how the testbed responds to increasing controlled transaction load.

Candidate CSV fields include:

```text
timestamp_utc, experiment_id, phase, level_index, lambda_target, workers, burst,
inflight, sample, duration_seconds, submitted_tps, accepted_tps, error_rate,
saturation_score, slot_interval_p50, slot_interval_p90, slot_interval_p99,
tx_latency_p50, tx_latency_p95, tx_latency_p99, subscription_errors_total,
validator_health, controller_mode
```

The schema should distinguish between:

- commanded load;
- submitted throughput;
- accepted throughput;
- error behaviour;
- latency behaviour;
- slot interval behaviour;
- validator health;
- controller or execution mode.

## Collector design

The CSV collector should be based on the existing `collect_csv.py` script.

The script should preserve support for the existing modes:

- `steady`;
- `step`.

It should also be extended to support the Layer 1 CSV schema.

The collector should remain robust against small changes in the `/stats` JSON structure of the load generator. Recursive key search and fallback parsing are acceptable because they make the workflow more resilient during early-stage experimentation.

For the current `loadgen2` implementation, the default rate-control key should be compatible with the load generator API. If `loadgen2` expects `lambda`, the scripts should use:

```text
RATE_KEY=lambda
```

## Expected Kubernetes components

The controlled-load extension may add:

- load generator Deployment or Job;
- Service for the load generator control endpoint;
- ConfigMap for experiment parameters;
- Kubernetes Secret for runtime key material;
- PVC for generated CSV output;
- Job for step-load execution;
- optional dashboard Deployment;
- optional dashboard Service;
- validation script for load-run completion;
- evidence collection script.

The controlled-load workload should not be scheduled on the validator node unless explicitly required.

Preferred scheduling:

```text
validator workload      -> testbed-role=validator
controlled load tools   -> testbed-role=observability or testbed-role=loadgen
observability workload  -> testbed-role=observability
```

## Metrics of interest

The first controlled-load runs should focus on observable metrics already available from the current system:

- submitted transaction rate;
- accepted transaction rate;
- error rate;
- in-flight transaction count;
- slot interval observations;
- transaction latency observations;
- subscription errors;
- validator health;
- RPC health before, during, and after the run;
- validator and monitor logs around the run window.

The controlled-load experiment should not be interpreted as a public Solana benchmark.

It is an internal, reproducible testbed response dataset.

## Evidence to collect

Each controlled-load run should produce an evidence directory such as:

```text
results/controlled-load-layer1/<experiment-id>/
```

The evidence should include:

- experiment metadata;
- load parameters;
- CSV output;
- generated transaction signatures where available;
- transaction success/failure summary;
- RPC health output;
- metrics snapshot before the run;
- metrics snapshot after the run;
- validator logs;
- monitor logs;
- Kubernetes Job status;
- pod placement information;
- timestamp of the run;
- known limitations.

## Security rule

Private key material must never be committed.

The following artefacts are excluded from version control:

- `payer.json`;
- Solana keypair JSON files;
- private SSH keys;
- Kubernetes admin credentials;
- kubeconfig files containing embedded certificates or tokens;
- environment files containing secrets;
- temporary runtime secret files.

Runtime secrets must be mounted through local runtime configuration or Kubernetes Secrets.

Generated CSV files may be committed only after manual inspection and after confirming that they do not contain private key material, credentials, tokens, local absolute secret paths, or machine-local sensitive information.

## Minimal validation criteria

The first controlled-load experiment is successful if:

- the load generator starts successfully;
- the collector starts successfully;
- the requested controlled-load levels are executed;
- CSV output is produced;
- the CSV header matches the documented schema;
- submitted throughput is non-empty for at least one sample;
- transaction latency or a documented empty metric field is present;
- RPC health remains observable;
- the monitor continues to expose metrics;
- evidence files are stored under a run-specific results directory;
- no private key material is written to the repository.

## Repository artefacts

This layer is expected to add or update:

```text
loadgen2/
scripts/
dashboard/
containers/
k8s/controlled-load/
docs/
data/raw/.gitkeep
results/figures/.gitkeep
```

The expected scripts include:

```text
scripts/collect_csv.py
scripts/knee_step_test.sh
scripts/knee_probe_adaptive.sh
scripts/analyse_controlled_load.py
```

The expected container definitions include:

```text
containers/Dockerfile.loadgen2
containers/Dockerfile.tools
```

The expected Kubernetes directory is:

```text
k8s/controlled-load/
```

## Proposed implementation order

The implementation order for this stage is:

1. fix the methodological scope of Controlled Load Layer 1;
2. clean and document the repository layout;
3. integrate the existing `collect_csv.py`;
4. extend the collector to support the Layer 1 schema;
5. clean the step-load and knee-probe scripts;
6. add container definitions;
7. test the workflow locally on the Dell server;
8. add Kubernetes manifests;
9. execute a small controlled-load experiment in Kubernetes;
10. validate CSV output and evidence;
11. update documentation;
12. commit the reproducible workflow;
13. consider a later software release after successful validation.

## Completion criteria

Controlled Load Layer 1 is considered complete when:

1. the controlled load generator is containerised;
2. the CSV collector supports the Controlled Load Layer 1 schema;
3. a reproducible step-load experiment can be executed locally;
4. the same experiment can be executed as a Kubernetes Job;
5. raw CSV output is produced with documented fields;
6. analysis scripts can generate summary statistics or figures;
7. no private keys or payer files are committed;
8. the workflow is documented well enough to be repeated on the Dell server.
