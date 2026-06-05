# Dedicated KVM Multi-Node Deployment of the Solana Kubernetes Observability Core

This document records the deployment and validation of the Solana Kubernetes Observability Core on a dedicated KVM-based multi-node Kubernetes cluster.

## Technical report DOI

The technical report associated with this deployment stage is:

    Khoshaba, O. (2026). Dedicated KVM Multi-Node Kubernetes Deployment of the Solana Kubernetes Observability Core (0.4.0). Zenodo. https://doi.org/10.5281/zenodo.20561100


## Software DOI

The software release associated with this deployment stage is:

    Solana Containerised Testbed v0.4.0
    DOI: 10.5281/zenodo.20551170
    URL: https://doi.org/10.5281/zenodo.20551170


## Deployment target

The deployment target was a kubeadm-based Kubernetes cluster running on KVM virtual machines:

| Node | Role | Label |
|---|---|---|
| k8s-cp-01 | Kubernetes control-plane | testbed-role=control-plane |
| k8s-worker-01 | Solana validator workload | testbed-role=validator |
| k8s-worker-02 | Observability workload | testbed-role=observability |

The cluster used:

- Ubuntu Server 24.04 LTS guest nodes;
- containerd runtime;
- Calico CNI;
- local-path-provisioner as the default StorageClass.

## Kubernetes overlay

The deployment used:

k8s/overlays/kvm-multinode

The overlay extends the portable Kubernetes base by adding dedicated multi-node placement:

- the validator StatefulSet is scheduled on testbed-role=validator;
- the monitor Deployment is scheduled on testbed-role=observability;
- the validator ledger PVC uses the local-path StorageClass.

## Deployed components

The deployed Solana Observability Core includes:

- Solana validator StatefulSet;
- validator ledger PersistentVolumeClaim;
- wallet-init Job;
- latency monitor Deployment;
- RPC Service on port 8899;
- Yellowstone/Geyser gRPC Service on port 10000;
- metrics Service on port 9464.

## Validation summary

The deployment was validated through the following checks:

- validator pod reached Running state on k8s-worker-01;
- monitor pod reached Running state on k8s-worker-02;
- validator ledger PVC reached Bound state;
- wallet-init Job completed successfully;
- RPC getHealth returned ok;
- metrics endpoint exposed Prometheus-format metrics;
- wallet transfer validation Job completed successfully;
- transaction latency metric was observed after the transfer validation.

## The final transaction latency evidence showed:

solana_transaction_latency_seconds_count 1

This confirms that the monitor observed at least one transaction latency sample in the dedicated KVM multi-node deployment.

## Evidence

Validation outputs are stored under:

results/kvm-multinode-observability-core/

Key files include:

- resources-all-pvc.txt;
- pods-wide.txt;
- services.txt;
- endpointslices.txt;
- wallet-init.log;
- wallet-transfer-validation.log;
- wallet-transfer-validation-job.txt;
- wallet-transfer-validation-pod.txt;
- rpc-getHealth-clean.json;
- metrics-head-clean.txt;
- metrics-after-wallet-transfer.txt;
- validator.log;
- monitor.log;
- kvm-multinode-rendered.yaml.

## Scope

This stage validates infrastructure and observability deployment only.

The following remain out of scope for this stage:

- load generation;
- dashboard;
- Prometheus/Grafana stack;
- MPC;
- single-agent RL;
- MARL;
- Agave.

