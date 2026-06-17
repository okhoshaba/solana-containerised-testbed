# Controlled Load Layer 1 Candidate Run

This note records the first candidate reproducible Kubernetes run for Controlled Load Layer 1.

## Context

The run was performed after merging Controlled Load Layer 1 into `main`.

The experiment extends the validated Solana Kubernetes Observability Core with controlled transaction load generation.

The methodological sequence remains:

infrastructure -> observability -> controlled load

This stage does not introduce MPC, reinforcement learning, MARL, Agave migration, or adaptive control logic.

## Kubernetes environment

The controlled-load components ran in the existing solana-observability namespace.

Validated runtime components:

- solana-loadgen2 Deployment;
- solana-loadgen2 ClusterIP Service on port 7070;
- controlled-load-results-pvc;
- manually created solana-payer-keypair Kubernetes Secret;
- existing solana-rpc:8899 Service;
- existing solana-metrics:9464 Service.

## Experiment configuration

The candidate run used the following controlled-load configuration:

- experiment_id: controlled-load-layer1-candidate
- levels: 1 2 4 8
- hold: 60 seconds per level
- sample: 5 seconds
- rate_key: lambda

The generated raw CSV file is stored at:

data/raw/controlled-load-layer1/20260617T223738Z/knee_step_candidate_20260617T223738Z.csv

The derived per-level summary is stored at:

results/controlled-load-layer1/20260617T223738Z/summary_by_level.csv

## Runtime result

After the run, loadgen2 reported:

- target_lambda: 0
- sent_total: 1401
- ok_total: 1401
- err_total: 0
- inflight: 0
- last_err: ""

The Kubernetes Job completed successfully and wrote the candidate CSV to the controlled-load results PVC.

## Interpretation

The run confirms that the Kubernetes controlled-load layer can:

- control loadgen2 through the in-cluster Service;
- execute a multi-level load schedule;
- collect CSV telemetry from loadgen2 and Prometheus-compatible metrics;
- persist experiment output through a Kubernetes PVC;
- return to a safe idle state with target_lambda=0.

This run is treated as candidate validation evidence for the planned v0.5.0-controlled-load-layer1 software release and the associated preprint.
