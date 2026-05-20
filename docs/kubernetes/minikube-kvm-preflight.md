# Minikube KVM Preflight Validation

## Purpose

This document records the initial Kubernetes preflight validation for the Solana Containerised Testbed Kubernetes migration.

The purpose of this step is not to deploy the Solana validator yet, but to confirm that the current CentOS/KVM host can run a working Kubernetes environment suitable for the first Observability Core migration tests.

## Host context

The current host is a CentOS 9 system with KVM already deployed.

The host CPU is a dual-socket Intel Xeon E5-2690 system with 32 logical CPUs and Intel VT-x support.

The host does not provide AVX2. This confirms the continued relevance of the repository's no-AVX2 Solana validator compatibility workflow.

## Minikube context

The first Kubernetes validation was performed using Minikube with the KVM2 driver.

The resulting environment is:

```text
CentOS 9 host
  -> KVM
  -> Minikube VM
  -> single-node Kubernetes cluster

This is not the final multi-node Kubernetes platform. It is a first Kubernetes validation layer before moving to a dedicated multi-node KVM-based cluster.

## Verified components

The following checks were completed successfully:

minikube status
minikube kubectl -- get nodes -o wide
minikube kubectl -- get pods -A
minikube kubectl -- get storageclass

The Kubernetes node reached the Ready state.
The Kubernetes system pods were running.
The default Minikube storage class was available:
- standard
- with the Minikube hostpath provisioner.

## Preflight smoke tests

The following smoke-test categories were validated:

- Kubernetes API access through Minikube.
- Cluster node readiness.
- System pod readiness.
- Default storage class availability.
- Project namespace creation.
- Basic pod creation and deletion.
- PersistentVolumeClaim creation and binding.

These checks confirm that the environment is ready for the next step: adding the Kubernetes Observability Core manifests to the repository.

## Current scope

This stage only validates the Kubernetes substrate.

It does not deploy:

- Solana validator;
- Yellowstone/Geyser configuration;
- wallet-init Job;
- monitor Deployment;
- RPC Service;
- Geyser gRPC Service;
- metrics Service.

These components will be added in the next implementation stage.

## Next implementation target

The next Kubernetes implementation target is the Observability Core:

- validator StatefulSet
- ledger PersistentVolumeClaim
- wallet-init Job
- monitor Deployment
- Service for RPC on 8899
- Service for Yellowstone/Geyser gRPC on 10000
- Service for metrics on 9464

This stage must not include load generation, dashboard, MPC, single-agent reinforcement learning, MARL, or the Agave research branch.


