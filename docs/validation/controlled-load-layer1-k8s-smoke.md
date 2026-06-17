# Controlled Load Layer 1 Kubernetes Smoke Validation

This note records the Kubernetes smoke validation of Controlled Load Layer 1.

## Environment

The validation was performed on the dedicated KVM-based multi-node Kubernetes cluster used by the Solana Kubernetes Observability Core.

The controlled-load components were deployed into the existing `solana-observability` namespace.

## Components validated

The following Kubernetes resources were validated:

- `solana-loadgen2` Deployment;
- `solana-loadgen2` ClusterIP Service on port `7070`;
- `controlled-load-results-pvc`;
- `controlled-load-knee-step` Job;
- `solana-payer-keypair` runtime Secret, created manually outside Git.

The Job used the existing in-cluster services:

- `solana-rpc:8899`;
- `solana-metrics:9464`.

## Result

The controlled-load Job completed successfully.

Observed runtime state after the run:

target_lambda: 0
sent_total: 373
ok_total: 373
err_total: 0
inflight: 0
last_err: ""

The generated CSV was copied from the Kubernetes PVC to a local ignored directory for inspection.

## CSV header:

t_iso,t_sec,u_cmd,sent_total,u_ach,lat_p99,inflight,err_per_sec

The first observed levels were u_cmd=1.000 followed by u_cmd=2.000, confirming that the Kubernetes Job was able to control loadgen2 through the in-cluster Service.

## Repository policy

The generated Kubernetes smoke CSV is treated as local runtime evidence and is not committed to Git.

The payer keypair is not stored in Git. It is provided to Kubernetes through a manually created Secret.

