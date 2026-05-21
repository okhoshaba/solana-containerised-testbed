# Kubernetes Observability Core Validation

## Purpose

This document records the successful validation of the Kubernetes Observability Core for the Solana Containerised Testbed.

The purpose of this stage is to confirm that the existing Yellowstone/Geyser-enabled Compose-based Observability Core can be migrated to Kubernetes while preserving the functional Solana localnet behaviour.

This validation does not introduce load generation, MPC, single-agent reinforcement learning, MARL, or the Agave research branch.

## Infrastructure context

The validation was performed on the following infrastructure path:

```text
CentOS 9 host
  -> KVM
  -> Minikube VM
  -> single-node Kubernetes cluster
  -> Solana Observability Core

The host machine is a legacy no-AVX2 x86_64 server. This confirms the continued relevance of the no-AVX2 Solana compatibility images used by the project.

## Kubernetes workload

The Kubernetes Observability Core consists of the following resources:

validator StatefulSet
validator ledger PersistentVolumeClaim
wallet-init Job
monitor Deployment
RPC Service
Yellowstone/Geyser gRPC Service
metrics Service

The stable Kubernetes service endpoints are:

solana-rpc:8899
solana-geyser-grpc:10000
solana-metrics:9464
Validator validation

The validator was successfully deployed as a Kubernetes StatefulSet:
statefulset.apps/solana-validator

The validator pod reached the ready state:
pod/solana-validator-0   1/1   Running

The validator ledger PVC was successfully created and bound:
validator-ledger-pvc   Bound   20Gi   RWO   standard

The validator reported Solana version:
solana-core: 1.18.25

The RPC health check returned:

{"jsonrpc":"2.0","result":"ok","id":1}

## Geyser gRPC validation

The Yellowstone/Geyser gRPC service was created as:
service/solana-geyser-grpc

The service exposes port:
10000/TCP

The service endpoint was observed as:
10.244.0.x:10000

This confirms that the Kubernetes Service was correctly connected to the validator pod.

## Wallet initialisation validation

The wallet initialisation stage was deployed as a Kubernetes Job:
job.batch/wallet-init

The Job completed successfully:
wallet-init   Complete   1/1

This confirms that the wallet initialisation container was able to reach the validator through the Kubernetes RPC Service:
http://solana-rpc:8899
Monitor and metrics validation

The monitor was deployed as a Kubernetes Deployment:
deployment.apps/solana-monitor

The monitor pod reached the ready state:
pod/solana-monitor-*   1/1   Running

The metrics service was created as:
service/solana-metrics

The metrics endpoint was exposed on:
9464/TCP

The Prometheus-compatible metrics endpoint returned slot interval metrics, including:
solana_slot_interval_seconds

This confirms that the monitor was running and exporting observability data.

## Wallet transfer validation

A dedicated Kubernetes validation Job was executed:

wallet-transfer-validation-20260521174219

The validation Job completed successfully:
job.batch/wallet-transfer-validation-20260521174219 condition met

The Job used the Solana CLI from the no-AVX2 Yellowstone validator image:
solana-cli 1.18.25
solana-keygen 1.18.25

The Job confirmed the cluster version:
1.18.25

A temporary sender wallet was created:

Sender:
6XVhK3FrUyU8YUFibY2wLNhJBzKcZqAffipu6vyNNTV7

The monitored receiver wallet was:

Receiver:
6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb

The sender received an airdrop of 2 SOL.

Airdrop signature:
KKDNCQgp7YefkNNCtiQ7P7DA6P6g6mqd4qTw1E3GPyLs9WNzZ69Vn2sE4Zqwwftpxnw5xdaGEY7sGih2coHi3LH

A transfer of 0.5 SOL was then sent from the temporary sender wallet to the monitored receiver wallet.

Transfer signature:
518up1tSAe3cATE2p8CWYs1sfXf7F5mzkYGT8VZY5Us4Y6jyDxnMahLneHsCNLxSd23gm1vJbbiPy9Yb76TRVhuz

The transaction was confirmed:
Confirmed

The final balances were:

Sender balance after transfer:
1.499995 SOL

Receiver balance after transfer:
0.5 SOL

This confirms that a simple SOL transfer can be executed successfully through the Kubernetes RPC endpoint.

## Validation conclusion

The Kubernetes Observability Core validation was successful.

The following properties were confirmed:

1. Kubernetes namespace creation works.
2. Validator StatefulSet runs successfully.
3. Validator ledger PVC is bound.
4. RPC Service is reachable.
5. Geyser gRPC Service is connected to the validator pod.
6. Wallet initialisation Job completes.
7. Monitor Deployment runs successfully.
8. Metrics Service exposes Prometheus-compatible metrics.
9. A dedicated wallet transfer validation Job completes successfully.
10. A simple SOL transfer is confirmed through the Kubernetes RPC endpoint.

Therefore, the Compose-based Yellowstone/Geyser Observability Core has been successfully migrated to a Kubernetes-based Observability Core for the current validation stage.

## Out of scope

The following components remain intentionally out of scope for this stage:
load generator
dashboard
Prometheus stack
Grafana
MPC controller
single-agent reinforcement learning
MARL
Agave research branch

Kubernetes is used here only as the hosting substrate for the observable Solana localnet system. It is not yet used as an adaptive controller, learning agent, or load-generation environment.

## Methodological position

This stage belongs to the observation part of the project roadmap.

The accepted methodological chain remains:

observation -> controlled load -> model -> MPC -> single-agent RL -> MARL

The next stage should document the Kubernetes Observability Core in the public repository and prepare the project for a future GitHub release, Zenodo archival record, and ORCID update.

