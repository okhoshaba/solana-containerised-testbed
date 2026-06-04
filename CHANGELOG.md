# Changelog

All notable changes to the Solana Containerised Testbed are documented in this file.

## v0.4.0 - Dedicated KVM Multi-Node Kubernetes Deployment

This release validates the Solana Kubernetes Observability Core on a dedicated KVM-based multi-node Kubernetes cluster.

### Added

- Added Ansible automation for a kubeadm-based Kubernetes cluster under `infra/ansible/kvm-kubeadm`.
- Added a dedicated KVM multi-node Kubernetes deployment overlay under `k8s/overlays/kvm-multinode`.
- Added validator and observability node placement through Kubernetes node labels:
  - `testbed-role=validator`;
  - `testbed-role=observability`;
  - `testbed-role=control-plane`.
- Added local-path storage support for the validator ledger PVC.
- Added Kubernetes cluster evidence under `results/kvm-kubeadm-cluster`.
- Added Solana Observability Core deployment evidence under `results/kvm-multinode-observability-core`.
- Added wallet transfer validation evidence for the dedicated KVM multi-node deployment.

### Validated

- Kubernetes control-plane and two worker nodes reached `Ready` state.
- The Solana validator StatefulSet was scheduled on the validator worker node.
- The latency monitor Deployment was scheduled on the observability worker node.
- The validator ledger PVC reached `Bound` state using the `local-path` StorageClass.
- The wallet-init Job completed successfully.
- RPC `getHealth` returned `ok`.
- Yellowstone/Geyser slot observability was validated through the monitor logs.
- Prometheus-format metrics were exposed by the monitor.
- Wallet transfer validation completed successfully.
- Transaction latency telemetry was observed after the validation transfer.

### Scope

This release remains focused on infrastructure and observability.

The following are intentionally out of scope:

- load generation;
- dashboard integration;
- Prometheus/Grafana stack;
- MPC;
- single-agent RL;
- MARL;
- Agave.


