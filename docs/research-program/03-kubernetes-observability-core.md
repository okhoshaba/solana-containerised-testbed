# Kubernetes Observability Core

## Goal

Move the Level 1 observability core to Kubernetes without introducing load generation or adaptive control.

The target system is:

```text
validator + wallet-init job + monitor
```

## Initial Kubernetes components

Recommended structure:

```text
k8s/
  base/
    namespace.yaml
    configmap.yaml
    pvc.yaml
    validator-statefulset.yaml
    validator-service.yaml
    wallet-init-job.yaml
    monitor-deployment.yaml
    monitor-service.yaml
  overlays/
    local-single-node/
    kind/
    minikube/
```

## Scope

Included:

- validator with Yellowstone/Geyser enabled
- wallet-init job
- monitor
- persistent volume claim for validator ledger
- service for RPC
- service for gRPC
- service for metrics

Excluded:

- loadgen
- dashboard
- MPC
- RL/MARL
- Agave
