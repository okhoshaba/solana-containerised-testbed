#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-solana-observability}"
VALIDATOR_NODE="${VALIDATOR_NODE:-k8s-worker-01}"
MIN_ROOT_AVAILABLE_GB="${MIN_ROOT_AVAILABLE_GB:-10}"
MAX_ROOT_USE_PERCENT="${MAX_ROOT_USE_PERCENT:-80}"

echo "=== v0.7.0 storage preflight ==="
echo "VALIDATOR_NODE=$VALIDATOR_NODE"
echo "MIN_ROOT_AVAILABLE_GB=$MIN_ROOT_AVAILABLE_GB"
echo "MAX_ROOT_USE_PERCENT=$MAX_ROOT_USE_PERCENT"

echo
echo "=== node status ==="
kubectl get node "$VALIDATOR_NODE" -o wide

echo
echo "=== node disk-pressure condition ==="
DISK_PRESSURE_STATUS="$(
  kubectl get node "$VALIDATOR_NODE" \
    -o jsonpath='{range .status.conditions[?(@.type=="DiskPressure")]}{.status}{end}'
)"

echo "DiskPressure=$DISK_PRESSURE_STATUS"

if [ "$DISK_PRESSURE_STATUS" != "False" ]; then
  echo "ERROR: DiskPressure is not False on $VALIDATOR_NODE"
  exit 10
fi

echo
echo "=== node taints ==="
TAINTS="$(kubectl get node "$VALIDATOR_NODE" -o jsonpath='{.spec.taints}' || true)"
echo "$TAINTS"

if echo "$TAINTS" | grep -q 'disk-pressure'; then
  echo "ERROR: disk-pressure taint is present on $VALIDATOR_NODE"
  exit 11
fi

echo
echo "=== validator pod ==="
kubectl -n "$NAMESPACE" get pod solana-validator-0 -o wide

VALIDATOR_READY="$(
  kubectl -n "$NAMESPACE" get pod solana-validator-0 \
    -o jsonpath='{.status.containerStatuses[0].ready}'
)"

if [ "$VALIDATOR_READY" != "true" ]; then
  echo "ERROR: solana-validator-0 is not ready"
  exit 12
fi

WORKER_IP="$(
  kubectl get node "$VALIDATOR_NODE" \
    -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'
)"

SSH_USER="${SSH_USER:-khoshaba}"

echo
echo "=== filesystem check via ssh ==="
echo "WORKER_IP=$WORKER_IP"
echo "SSH_USER=$SSH_USER"

SSH_OUTPUT="$(
  ssh "$SSH_USER@$WORKER_IP" '
    use_pct="$(df -P / | awk "NR==2 {gsub(\"%\", \"\", \$5); print \$5}")"
    avail_kb="$(df -Pk / | awk "NR==2 {print \$4}")"
    avail_gb="$((avail_kb / 1024 / 1024))"

    echo "root_use_percent=${use_pct}"
    echo "root_available_gb=${avail_gb}"

    echo
    echo "top_storage_consumers:"
    sudo du -xh -d1 /opt /var/lib 2>/dev/null | sort -h | tail -n 30
  '
)"

echo "$SSH_OUTPUT"

ROOT_USE_PERCENT="$(echo "$SSH_OUTPUT" | awk -F= '/^root_use_percent=/{print $2}')"
ROOT_AVAILABLE_GB="$(echo "$SSH_OUTPUT" | awk -F= '/^root_available_gb=/{print $2}')"

if [ "${ROOT_USE_PERCENT:-999}" -gt "$MAX_ROOT_USE_PERCENT" ]; then
  echo "ERROR: root filesystem use percent is too high: $ROOT_USE_PERCENT"
  exit 13
fi

if [ "${ROOT_AVAILABLE_GB:-0}" -lt "$MIN_ROOT_AVAILABLE_GB" ]; then
  echo "ERROR: root available GB is too low: $ROOT_AVAILABLE_GB"
  exit 14
fi

echo
echo "Storage preflight OK"
