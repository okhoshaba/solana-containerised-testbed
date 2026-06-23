#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_BRANCH="v0.8.0-dynamic-load-system-identification"

RUN_ID="${1:-}"
RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
OUT_ROOT="${OUT_ROOT:-results/v0.8.0/preflight}"
LOCAL_PATH_DIR="${LOCAL_PATH_DIR:-/opt/local-path-provisioner}"
CONTAINERD_DIR="${CONTAINERD_DIR:-/var/lib/containerd}"

if [ -z "$RUN_ID" ]; then
  echo "Usage: $0 <run_id>"
  echo "Example: $0 v0.8.0-M0-L32"
  exit 2
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]; then
  echo "ERROR: wrong branch: $CURRENT_BRANCH"
  echo "Expected: $EXPECTED_BRANCH"
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl not found"
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl not found"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

OUT_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "$OUT_DIR"

REPORT_TXT="${OUT_DIR}/preflight-report.txt"
SUMMARY_JSON="${OUT_DIR}/preflight-summary.json"

START_TIME_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMIT_SHA="$(git rev-parse --short=12 HEAD)"

if [ -z "$(git status --porcelain)" ]; then
  WORKING_TREE_CLEAN="true"
else
  WORKING_TREE_CLEAN="false"
fi

ROOT_USED_PERCENT="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"

if [ -d "$LOCAL_PATH_DIR" ]; then
  LOCAL_PATH_USED_PERCENT="$(df -P "$LOCAL_PATH_DIR" | awk 'NR==2 {gsub("%","",$5); print $5}')"
else
  LOCAL_PATH_USED_PERCENT="null"
fi

if [ -d "$CONTAINERD_DIR" ]; then
  CONTAINERD_USED_PERCENT="$(df -P "$CONTAINERD_DIR" | awk 'NR==2 {gsub("%","",$5); print $5}')"
else
  CONTAINERD_USED_PERCENT="null"
fi

NODE_DISK_PRESSURE="$(kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}={range .status.conditions[?(@.type=="DiskPressure")]}{.status}{end}{";"}{end}' 2>/dev/null || true)"

if printf '%s\n' "$NODE_DISK_PRESSURE" | grep -q '=True'; then
  DISK_PRESSURE="true"
elif printf '%s\n' "$NODE_DISK_PRESSURE" | grep -q '=False'; then
  DISK_PRESSURE="false"
else
  DISK_PRESSURE="null"
fi

VALIDATOR_PODS="$(kubectl get pods -A --no-headers 2>/dev/null | awk '/solana-validator/ {print}' || true)"

VALIDATOR_POD_READY="false"
if printf '%s\n' "$VALIDATOR_PODS" | awk '
  NF >= 5 {
    split($3, ready, "/")
    if ($4 == "Running" && ready[1] == ready[2] && ready[2] > 0) {
      found = 1
    }
  }
  END { exit found ? 0 : 1 }
'; then
  VALIDATOR_POD_READY="true"
fi

RPC_RESPONSE="$(curl -sS --max-time 5 "$RPC_URL" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' 2>/dev/null || true)"

RPC_HEALTHY="false"
if printf '%s\n' "$RPC_RESPONSE" | grep -q '"result"[[:space:]]*:[[:space:]]*"ok"'; then
  RPC_HEALTHY="true"
fi

RECENT_EVENTS="$(kubectl get events -A --sort-by='.lastTimestamp' 2>/dev/null | tail -n 100 || true)"

RECENT_POD_EVICTIONS="$(printf '%s\n' "$RECENT_EVENTS" | grep -Eci 'evict|evicted' || true)"
RECENT_KUBELET_STORAGE_WARNINGS="$(printf '%s\n' "$RECENT_EVENTS" | grep -Eci 'DiskPressure|ephemeral|storage|pressure' || true)"
RECENT_CONTAINER_RESTARTS="$(kubectl get pods -A --no-headers 2>/dev/null | awk '{sum += $5} END {print sum + 0}' || echo 0)"

PREFLIGHT_PASSED="true"

if [ "$DISK_PRESSURE" != "false" ]; then
  PREFLIGHT_PASSED="false"
fi

if [ "$VALIDATOR_POD_READY" != "true" ]; then
  PREFLIGHT_PASSED="false"
fi

if [ "$RPC_HEALTHY" != "true" ]; then
  PREFLIGHT_PASSED="false"
fi

{
  echo "# v0.8.0 preflight report"
  echo
  echo "run_id: $RUN_ID"
  echo "timestamp_utc: $START_TIME_UTC"
  echo "branch: $CURRENT_BRANCH"
  echo "commit_sha: $COMMIT_SHA"
  echo "working_tree_clean: $WORKING_TREE_CLEAN"
  echo "rpc_url: $RPC_URL"
  echo "local_path_dir: $LOCAL_PATH_DIR"
  echo "containerd_dir: $CONTAINERD_DIR"
  echo
  echo "## Summary"
  echo "disk_pressure: $DISK_PRESSURE"
  echo "validator_pod_ready: $VALIDATOR_POD_READY"
  echo "rpc_healthy: $RPC_HEALTHY"
  echo "root_filesystem_used_percent: $ROOT_USED_PERCENT"
  echo "local_path_used_percent: $LOCAL_PATH_USED_PERCENT"
  echo "containerd_used_percent: $CONTAINERD_USED_PERCENT"
  echo "recent_pod_evictions: $RECENT_POD_EVICTIONS"
  echo "recent_container_restarts: $RECENT_CONTAINER_RESTARTS"
  echo "recent_kubelet_storage_warnings: $RECENT_KUBELET_STORAGE_WARNINGS"
  echo "preflight_passed: $PREFLIGHT_PASSED"
  echo
  echo "## Kubernetes nodes"
  kubectl get nodes -o wide || true
  echo
  echo "## Node conditions"
  kubectl describe nodes | grep -E 'Name:|DiskPressure|MemoryPressure|PIDPressure|Ready' || true
  echo
  echo "## Validator pods"
  if [ -n "$VALIDATOR_PODS" ]; then
    printf '%s\n' "$VALIDATOR_PODS"
  else
    echo "No solana-validator pod found by name search."
  fi
  echo
  echo "## Pods overview"
  kubectl get pods -A -o wide || true
  echo
  echo "## Filesystem usage"
  df -h / || true
  if [ -d "$LOCAL_PATH_DIR" ]; then
    df -h "$LOCAL_PATH_DIR" || true
    du -sh "$LOCAL_PATH_DIR" 2>/dev/null || true
  else
    echo "$LOCAL_PATH_DIR not found"
  fi
  if [ -d "$CONTAINERD_DIR" ]; then
    df -h "$CONTAINERD_DIR" || true
    du -sh "$CONTAINERD_DIR" 2>/dev/null || true
  else
    echo "$CONTAINERD_DIR not found"
  fi
  echo
  echo "## RPC getHealth response"
  printf '%s\n' "$RPC_RESPONSE"
  echo
  echo "## Recent Kubernetes events"
  printf '%s\n' "$RECENT_EVENTS"
} > "$REPORT_TXT" 2>&1

export RUN_ID
export START_TIME_UTC
export CURRENT_BRANCH
export COMMIT_SHA
export WORKING_TREE_CLEAN
export RPC_URL
export DISK_PRESSURE
export VALIDATOR_POD_READY
export RPC_HEALTHY
export ROOT_USED_PERCENT
export LOCAL_PATH_USED_PERCENT
export CONTAINERD_USED_PERCENT
export RECENT_POD_EVICTIONS
export RECENT_CONTAINER_RESTARTS
export RECENT_KUBELET_STORAGE_WARNINGS
export PREFLIGHT_PASSED
export REPORT_TXT

python3 - <<'PY' > "$SUMMARY_JSON"
import json
import os

def parse_bool(value):
    if value == "true":
        return True
    if value == "false":
        return False
    return None

def parse_number_or_null(value):
    if value in ("", "null", None):
        return None
    try:
        return float(value)
    except ValueError:
        return None

def parse_int(value):
    try:
        return int(value)
    except ValueError:
        return 0

payload = {
    "run_id": os.environ["RUN_ID"],
    "timestamp_utc": os.environ["START_TIME_UTC"],
    "git": {
        "branch": os.environ["CURRENT_BRANCH"],
        "commit_sha": os.environ["COMMIT_SHA"],
        "working_tree_clean": parse_bool(os.environ["WORKING_TREE_CLEAN"])
    },
    "rpc_url": os.environ["RPC_URL"],
    "safety_preflight": {
        "disk_pressure": parse_bool(os.environ["DISK_PRESSURE"]),
        "validator_pod_ready": parse_bool(os.environ["VALIDATOR_POD_READY"]),
        "rpc_healthy": parse_bool(os.environ["RPC_HEALTHY"]),
        "root_filesystem_used_percent": parse_number_or_null(os.environ["ROOT_USED_PERCENT"]),
        "local_path_used_percent": parse_number_or_null(os.environ["LOCAL_PATH_USED_PERCENT"]),
        "containerd_used_percent": parse_number_or_null(os.environ["CONTAINERD_USED_PERCENT"]),
        "recent_pod_evictions": parse_int(os.environ["RECENT_POD_EVICTIONS"]),
        "recent_container_restarts": parse_int(os.environ["RECENT_CONTAINER_RESTARTS"]),
        "recent_kubelet_storage_warnings": parse_int(os.environ["RECENT_KUBELET_STORAGE_WARNINGS"]),
        "preflight_passed": parse_bool(os.environ["PREFLIGHT_PASSED"])
    },
    "artifacts": {
        "report_txt": os.environ["REPORT_TXT"]
    }
}

print(json.dumps(payload, indent=2, sort_keys=True))
PY

echo "Preflight report: $REPORT_TXT"
echo "Preflight summary: $SUMMARY_JSON"

if [ "$PREFLIGHT_PASSED" != "true" ]; then
  echo "PREFLIGHT FAILED"
  exit 1
fi

echo "PREFLIGHT PASSED"
