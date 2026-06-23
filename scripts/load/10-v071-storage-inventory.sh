#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-solana-observability}"
VALIDATOR_NODE="${VALIDATOR_NODE:-k8s-worker-01}"
SSH_USER="${SSH_USER:-khoshaba}"
OUT_ROOT="${OUT_ROOT:-results/v0.7.1/storage-inventory}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_ROOT}/${TS}_${VALIDATOR_NODE}"

mkdir -p "$OUT_DIR"

echo "=== v0.7.1 storage inventory ==="
echo "NAMESPACE=$NAMESPACE"
echo "VALIDATOR_NODE=$VALIDATOR_NODE"
echo "SSH_USER=$SSH_USER"
echo "OUT_DIR=$OUT_DIR"

echo
echo "=== cluster-side inventory ==="

kubectl get nodes -o wide | tee "$OUT_DIR/k8s-nodes.txt"

kubectl describe node "$VALIDATOR_NODE" \
  > "$OUT_DIR/k8s-describe-validator-node.txt" 2>&1

kubectl get node "$VALIDATOR_NODE" -o yaml \
  > "$OUT_DIR/k8s-validator-node.yaml" 2>&1

kubectl -n "$NAMESPACE" get pods -o wide \
  | tee "$OUT_DIR/k8s-pods.txt"

kubectl -n "$NAMESPACE" get pvc,pv -o wide \
  > "$OUT_DIR/k8s-pvc-pv.txt" 2>&1

kubectl -n "$NAMESPACE" get svc,endpoints,endpointslices -o wide \
  > "$OUT_DIR/k8s-services-endpoints.txt" 2>&1

kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp \
  > "$OUT_DIR/k8s-events.txt" 2>&1

kubectl -n "$NAMESPACE" describe pod solana-validator-0 \
  > "$OUT_DIR/k8s-describe-solana-validator-0.txt" 2>&1 || true

kubectl -n "$NAMESPACE" get pod solana-validator-0 -o yaml \
  > "$OUT_DIR/k8s-solana-validator-0.yaml" 2>&1 || true

WORKER_IP="$(
  kubectl get node "$VALIDATOR_NODE" \
    -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'
)"

echo "$WORKER_IP" > "$OUT_DIR/validator-node-ip.txt"

echo
echo "=== validator node ssh inventory ==="
echo "WORKER_IP=$WORKER_IP"

ssh "$SSH_USER@$WORKER_IP" '
  set -e

  echo "=== identity ==="
  hostname
  date -u
  uname -a

  echo
  echo "=== block devices ==="
  lsblk -f

  echo
  echo "=== mounts ==="
  findmnt

  echo
  echo "=== df -hT ==="
  df -hT

  echo
  echo "=== df -ih ==="
  df -ih

  echo
  echo "=== root filesystem ==="
  df -hT /

  echo
  echo "=== top-level disk usage ==="
  sudo du -xh -d1 / 2>/dev/null | sort -h

  echo
  echo "=== /opt disk usage ==="
  sudo du -xh -d2 /opt 2>/dev/null | sort -h | tail -n 120

  echo
  echo "=== /var/lib disk usage ==="
  sudo du -xh -d2 /var/lib 2>/dev/null | sort -h | tail -n 160

  echo
  echo "=== /var/lib/containerd disk usage ==="
  sudo du -xh -d2 /var/lib/containerd 2>/dev/null | sort -h | tail -n 160

  echo
  echo "=== /var/lib/kubelet disk usage ==="
  sudo du -xh -d3 /var/lib/kubelet 2>/dev/null | sort -h | tail -n 160

  echo
  echo "=== local-path provisioner storage ==="
  sudo du -xh -d3 /opt/local-path-provisioner 2>/dev/null | sort -h | tail -n 160

  echo
  echo "=== largest files under /opt ==="
  sudo find /opt -xdev -type f -printf "%s %p\n" 2>/dev/null | sort -n | tail -n 80

  echo
  echo "=== largest files under /var/lib ==="
  sudo find /var/lib -xdev -type f -printf "%s %p\n" 2>/dev/null | sort -n | tail -n 80

  echo
  echo "=== largest files under /var/log ==="
  sudo find /var/log -xdev -type f -printf "%s %p\n" 2>/dev/null | sort -n | tail -n 80

  echo
  echo "=== container runtime images ==="
  sudo crictl images 2>/dev/null || true

  echo
  echo "=== container runtime containers ==="
  sudo crictl ps -a 2>/dev/null || true

  echo
  echo "=== kubelet disk-pressure logs, recent ==="
  sudo journalctl -u kubelet --since "24 hours ago" --no-pager \
    | grep -Ei "diskpressure|evict|image garbage|ephemeral|storage|threshold" \
    | tail -n 300 || true
' > "$OUT_DIR/validator-node-storage.txt" 2>&1

echo
echo "=== inventory completed ==="
echo "OUT_DIR=$OUT_DIR"

echo "$OUT_DIR" > "$OUT_ROOT/latest.txt"

echo
echo "=== short summary ==="
grep -A8 '=== root filesystem ===' "$OUT_DIR/validator-node-storage.txt" || true
grep -A20 '=== local-path provisioner storage ===' "$OUT_DIR/validator-node-storage.txt" | tail -n 30 || true
