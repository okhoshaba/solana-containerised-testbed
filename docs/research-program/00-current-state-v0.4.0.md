# Current State: v0.4.0

## Summary

Version `v0.4.0` of the Solana Containerised Testbed validates the Solana Kubernetes Observability Core on a dedicated KVM-based multi-node Kubernetes cluster.

This stage extends the previous Minikube-based Kubernetes validation by deploying the same observability-oriented Solana workload on a dedicated kubeadm cluster composed of one control-plane virtual machine and two worker virtual machines.

The goal of this stage is infrastructure and observability validation. It does not introduce controlled load generation, dashboarding, MPC, reinforcement learning, MARL, or Agave.

## Deployment environment

The validated deployment uses:

- a CentOS Stream 9 KVM/libvirt host;
- Ubuntu Server 24.04 LTS guest virtual machines;
- kubeadm for Kubernetes bootstrap;
- containerd as the container runtime;
- Calico as the CNI plugin;
- local-path-provisioner as the default StorageClass;
- Ansible automation for node preparation, Kubernetes bootstrap, validation, and reset support.

## Kubernetes topology

The dedicated Kubernetes cluster contains three nodes:

| Node | Role | Placement label |
|---|---|---|
| `k8s-cp-01` | Kubernetes control-plane | `testbed-role=control-plane` |
| `k8s-worker-01` | Solana validator workload | `testbed-role=validator` |
| `k8s-worker-02` | Observability workload | `testbed-role=observability` |

## Kubernetes Observability Core

The deployed observability core includes:

- Solana validator StatefulSet;
- validator ledger PersistentVolumeClaim;
- wallet-init Job;
- latency monitor Deployment;
- RPC Service on port `8899`;
- Yellowstone/Geyser gRPC Service on port `10000`;
- metrics Service on port `9464`.

The deployment uses the `k8s/overlays/kvm-multinode` Kustomize overlay. This overlay extends the portable Kubernetes base by adding:

- validator node placement on `testbed-role=validator`;
- monitor node placement on `testbed-role=observability`;
- explicit `local-path` storage for the validator ledger PVC.

## Validation evidence

The deployment was validated through:

- node readiness checks;
- namespace and workload deployment checks;
- PVC binding checks;
- service and EndpointSlice checks;
- Solana validator logs;
- wallet-init logs;
- monitor logs;
- RPC `getHealth` validation;
- metrics endpoint validation;
- wallet transfer validation.

The wallet transfer validation confirmed:

- creation of a temporary sender keypair;
- airdrop of `2 SOL` to the sender;
- transfer of `0.5 SOL` to the receiver;
- transaction confirmation;
- successful balance update after transfer.

The metrics endpoint also reported a transaction latency sample after the transfer validation.

## Evidence directories

The main evidence directories are:

results/kvm-kubeadm-cluster/
results/kvm-multinode-observability-core/

The main infrastructure automation directory is:

infra/ansible/kvm-kubeadm/

The main Kubernetes overlay directory is:

k8s/overlays/kvm-multinode/

## Methodological position

This stage belongs to the following methodological chain:

infrastructure -> observability

The later research chain remains:

observation -> controlled load -> model -> MPC -> single-agent RL -> MARL

This version does not move directly to RL or MARL. Kubernetes is used as the execution and observability environment, not as the learning agent.

## Out of scope

The following remain out of scope for v0.4.0:

- synthetic load generation;
- dashboard development;
- Prometheus/Grafana stack;
- MPC controller design;
- single-agent RL;
- MARL;
- Agave migration.

