#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/project/solana-containerised-testbed}"
OUT_DIR="${REPO_DIR}/results/kvm-kubeadm-cluster"
CP_IP="${CP_IP:-192.168.122.101}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/k8s_ansible_ed25519}"
SSH_USER="${SSH_USER:-khoshaba}"

mkdir -p "${OUT_DIR}"

run_kubectl () {
  ssh -i "${SSH_KEY}" "${SSH_USER}@${CP_IP}" "$1"
}

echo "Collecting Kubernetes cluster evidence into: ${OUT_DIR}"

run_kubectl 'kubectl get nodes -o wide' \
  | tee "${OUT_DIR}/nodes-ready.txt"

run_kubectl 'kubectl get nodes -L testbed-role' \
  | tee "${OUT_DIR}/nodes-labels.txt"

run_kubectl 'kubectl get pods -A -o wide' \
  | tee "${OUT_DIR}/system-pods.txt"

run_kubectl 'kubectl get storageclass' \
  | tee "${OUT_DIR}/storageclass.txt"

run_kubectl 'kubectl get pv' \
  | tee "${OUT_DIR}/persistent-volumes.txt"

run_kubectl 'kubectl get pvc -A' \
  | tee "${OUT_DIR}/persistent-volume-claims.txt"

run_kubectl 'kubectl cluster-info' \
  | tee "${OUT_DIR}/cluster-info.txt"

run_kubectl 'kubectl get events -A --sort-by=.lastTimestamp' \
  | tee "${OUT_DIR}/events.txt"

run_kubectl 'kubectl get componentstatuses 2>/dev/null || true' \
  | tee "${OUT_DIR}/componentstatuses.txt"

date -u +"%Y-%m-%dT%H:%M:%SZ" \
  | tee "${OUT_DIR}/collected-at-utc.txt"

echo "Evidence collection completed."
