# Controlled Load Layer 1

## Purpose

This document defines the next research stage after the validated `v0.4.0` dedicated KVM multi-node Kubernetes deployment of the Solana Kubernetes Observability Core.

The purpose of this stage is to introduce controlled, reproducible transaction load into the already validated observability environment.

The current methodological position is:

infrastructure -> observability -> controlled load

This stage must not introduce MPC, single-agent reinforcement learning, MARL, or Agave. Those remain later or separate research branches.

## Starting point

The starting point is the validated v0.4.0 baseline:

- dedicated KVM-based multi-node Kubernetes cluster;
- kubeadm-based Kubernetes deployment;
- validator workload scheduled on testbed-role=validator;
- monitor workload scheduled on testbed-role=observability;
- validator ledger PVC using local-path;
- RPC Service on port 8899;
- Yellowstone/Geyser gRPC Service on port 10000;
- metrics Service on port 9464;
- wallet transfer validation completed successfully;
- transaction latency telemetry observed.

The associated software release is:

Solana Containerised Testbed v0.4.0
DOI: 10.5281/zenodo.20551170

The associated technical report is:

Dedicated KVM Multi-Node Kubernetes Deployment of the Solana Kubernetes Observability Core
DOI: 10.5281/zenodo.20561100
Main objective

The main objective of Layer 1 is to create a controlled transaction workload that can be repeated, measured, and compared across runs.

The workload should remain simple and transparent at first:

- native SOL transfers;
- fixed sender and receiver structure;
- configurable transaction count;
- configurable delay between transactions;
- configurable batch size;
- clear run identifier;
- timestamped output files;
- compatibility with the existing Kubernetes RPC endpoint.

## Initial workload design

The first workload generator should be intentionally minimal.

It should support:

- N transactions
- fixed transfer amount
- fixed or configurable inter-transaction delay
- single sender or small controlled sender set
- single receiver or small controlled receiver set
- RPC endpoint: http://solana-rpc:8899

The workload generator may initially run as a Kubernetes Job.

A later refinement may convert it into a more configurable Kubernetes workload, but the first implementation should remain simple enough to audit.

## Expected Kubernetes components

The initial controlled-load extension may add:

- load generation Job;
- ConfigMap for load parameters;
- optional output PVC or mounted results directory;
- validation script for load run completion;
- evidence collection script.

The first implementation should not add:

- dashboard;
- Prometheus/Grafana stack;
- MPC;
- reinforcement learning;
- MARL;
- Agave.

## Metrics of interest

The first controlled-load runs should focus on observable metrics already available from the current system:

- slot interval observations;
- transaction latency observations;
- successful transfer count;
- failed transfer count;
- transaction signatures;
- start and end timestamps;
- RPC health before and after the run;
- validator and monitor logs around the run window.

The main success criterion is not maximum throughput. The first success criterion is reproducibility.

## Evidence to collect

Each controlled-load run should produce an evidence directory such as:

results/controlled-load-layer1/<run-id>/

The evidence should include:

- load parameters;
- generated transaction signatures;
- transaction success/failure summary;
- RPC health output;
- metrics snapshot before the run;
- metrics snapshot after the run;
- validator logs;
- monitor logs;
- Kubernetes Job status;
- pod placement information;
- timestamp of the run.

## Minimal validation criteria

The first controlled-load experiment is successful if:

- the load generation Job completes;
- the requested number of transactions is submitted;
- transaction signatures are recorded;
- RPC health remains available;
- the monitor continues to expose metrics;
- solana_transaction_latency_seconds_count increases after the run;
- evidence files are stored under a run-specific results directory.

## Methodological constraints

This stage must remain an observation and controlled-load stage.

It should not optimise validator behaviour, tune policies, or introduce adaptive decision-making.

The correct methodological sequence remains:

observation -> controlled load -> model -> MPC -> single-agent RL -> MARL

Kubernetes is the execution and observability environment. It is not the agent.

## Proposed implementation order
Define the minimal controlled-load workload.
Implement a simple Kubernetes Job for native SOL transfers.
Add a ConfigMap for run parameters.
Add a validation script for one controlled run.
Add evidence collection for each run.
Run a small baseline experiment.
Commit manifests, scripts, and evidence.
Document the first controlled-load result.
Only then consider larger or repeated experiments.
Out of scope for the first Layer 1 implementation

The following are intentionally excluded from the first controlled-load implementation:

- high-throughput stress testing;
- distributed load generation;
- dashboard development;
- Prometheus/Grafana deployment;
- automatic control;
- MPC;
- single-agent RL;
- MARL;
- Agave migration.

## Expected next artefacts

The expected artefacts of this stage are:

- Kubernetes manifests for the controlled-load Job;
- load generation script;
- validation script;
- run evidence under results/controlled-load-layer1/;
- documentation update;
- possible software release after successful validation.

