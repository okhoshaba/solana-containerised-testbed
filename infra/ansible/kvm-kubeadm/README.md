# KVM kubeadm Kubernetes cluster automation

This directory contains the Ansible automation used to prepare, create, validate, and reset the dedicated KVM-based multi-node Kubernetes cluster for the Solana Containerised Testbed.

## Target cluster

| Node | Role | IP address | Testbed label |
|---|---|---:|---|
| k8s-cp-01 | Kubernetes control-plane | 192.168.122.101 | testbed-role=control-plane |
| k8s-worker-01 | Validator worker | 192.168.122.102 | testbed-role=validator |
| k8s-worker-02 | Observability worker | 192.168.122.103 | testbed-role=observability |

## Baseline stack

- Host platform: CentOS Stream 9 with KVM/libvirt.
- Guest OS: Ubuntu Server 24.04 LTS.
- Kubernetes bootstrap: kubeadm.
- Container runtime: containerd.
- CNI: Calico direct manifest.
- Storage: Rancher local-path-provisioner.
- Default StorageClass: local-path.

## Inventory

The inventory file is:

inventory.ini

The main inventory groups are:

k8s_control_plane
k8s_workers
k8s
Main playbooks

## Prepare the nodes:

ansible-playbook site-prepare-nodes.yml

Create the Kubernetes cluster:

ansible-playbook site-create-cluster.yml

Validate the running cluster:

ansible-playbook validate-cluster.yml

## Collect evidence into the repository results directory:

./scripts/collect-evidence.sh

Reset the Kubernetes cluster state:

ansible-playbook reset-kubeadm-cluster.yml

Warning: reset-kubeadm-cluster.yml destroys the current Kubernetes cluster state and should only be used when the cluster is intentionally being rebuilt.

## Rebuild sequence

A full reproducibility test should use this order:

ansible-playbook reset-kubeadm-cluster.yml
ansible-playbook site-prepare-nodes.yml
ansible-playbook site-create-cluster.yml
ansible-playbook validate-cluster.yml
./scripts/collect-evidence.sh

## Current validated state

The current cluster evidence is stored under:

results/kvm-kubeadm-cluster/

The validated state includes:

- three Kubernetes nodes in Ready state;
- node labels for control-plane, validator and observability placement;
- Calico networking;
- CoreDNS;
- local-path default StorageClass;
- local-path PVC provisioning validated on the validator worker node.

## Scope

This automation covers the Kubernetes infrastructure layer only.

It does not deploy:

- Solana validator workload;
- wallet-init Job;
- latency monitor;
- load generator;
- dashboard;
- Prometheus/Grafana;
- MPC;
- RL/MARL;
- Agave.

The next project stage is the deployment of the Solana Kubernetes Observability Core through k8s/overlays/kvm-multinode.


