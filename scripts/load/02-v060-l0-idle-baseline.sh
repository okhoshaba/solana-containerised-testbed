#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

STAGE="v0.6.0"
LOAD_LEVEL="L0"
RUN_KIND="idle-baseline"

NAMESPACE="${NAMESPACE:-solana-observability}"
RPC_SERVICE="${RPC_SERVICE:-solana-rpc}"
LOCAL_PORT="${LOCAL_PORT:-18899}"
REMOTE_PORT="${REMOTE_PORT:-8899}"

DURATION_SECONDS="${DURATION_SECONDS:-120}"
SAMPLE_INTERVAL="${SAMPLE_INTERVAL:-10}"

HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown-branch)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown-sha)"

RUN_ID="${STAGE}_${HOST_SHORT}_${TS_UTC}_${LOAD_LEVEL}-${RUN_KIND}_${GIT_SHA}"
OUT_DIR="${ROOT_DIR}/results/${STAGE}/raw/${RUN_ID}"

mkdir -p "$OUT_DIR"/{repo,host,k8s,rpc,samples,logs,summary}

exec > >(tee "$OUT_DIR/logs/l0-idle-baseline.stdout.log") 2> >(tee "$OUT_DIR/logs/l0-idle-baseline.stderr.log" >&2)

echo "=== v0.6.0 L0 idle baseline ==="
echo "ROOT_DIR=$ROOT_DIR"
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "NAMESPACE=$NAMESPACE"
echo "RPC_SERVICE=$RPC_SERVICE"
echo "LOCAL_PORT=$LOCAL_PORT"
echo "REMOTE_PORT=$REMOTE_PORT"
echo "DURATION_SECONDS=$DURATION_SECONDS"
echo "SAMPLE_INTERVAL=$SAMPLE_INTERVAL"
echo

cat > "$OUT_DIR/metadata.env" <<META
stage=$STAGE
run_id=$RUN_ID
timestamp_utc=$TS_UTC
host_short=$HOST_SHORT
hostname=$(hostname 2>/dev/null || echo unknown)
git_branch=$GIT_BRANCH
git_sha=$GIT_SHA
load_level=$LOAD_LEVEL
run_kind=$RUN_KIND
offered_load=0
target_transaction_rate=0
duration_seconds=$DURATION_SECONDS
sample_interval_seconds=$SAMPLE_INTERVAL
namespace=$NAMESPACE
rpc_service=$RPC_SERVICE
local_port=$LOCAL_PORT
remote_port=$REMOTE_PORT
root_dir=$ROOT_DIR
META

run_cmd() {
  local name="$1"
  shift
  local outfile="$1"
  shift

  echo ">>> $name"
  {
    echo "# command: $*"
    echo "# started_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    "$@"
    local rc=$?
    echo "# finished_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "# exit_code: $rc"
    return $rc
  } > "$outfile" 2>&1 || true
}

rpc_call() {
  local method="$1"
  local outfile="$2"

  curl -sS -m 5 "http://127.0.0.1:${LOCAL_PORT}" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\"}" \
    > "$outfile" 2>&1 || true
}

capture_rpc_set() {
  local dir="$1"
  mkdir -p "$dir"

  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/timestamp_utc.txt"
  rpc_call getHealth "$dir/getHealth.json"
  rpc_call getVersion "$dir/getVersion.json"
  rpc_call getEpochInfo "$dir/getEpochInfo.json"
  rpc_call getSlot "$dir/getSlot.json"
  rpc_call getBlockHeight "$dir/getBlockHeight.json"
  rpc_call getTransactionCount "$dir/getTransactionCount.json"
}

capture_host_set() {
  local dir="$1"
  mkdir -p "$dir"

  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/timestamp_utc.txt"
  cat /proc/loadavg > "$dir/proc-loadavg.txt" 2>&1 || true
  cat /proc/meminfo > "$dir/proc-meminfo.txt" 2>&1 || true
  cat /proc/net/dev > "$dir/proc-net-dev.txt" 2>&1 || true
  free -h > "$dir/free-h.txt" 2>&1 || true
  df -hT > "$dir/df-hT.txt" 2>&1 || true
  ss -lntup > "$dir/ss-listening.txt" 2>&1 || true
}

capture_k8s_set() {
  local dir="$1"
  mkdir -p "$dir"

  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/timestamp_utc.txt"
  kubectl get nodes -o wide > "$dir/nodes-wide.txt" 2>&1 || true
  kubectl get pods -A -o wide > "$dir/pods-all-namespaces-wide.txt" 2>&1 || true
  kubectl -n "$NAMESPACE" get pods -o wide > "$dir/pods-namespace-wide.txt" 2>&1 || true
  kubectl -n "$NAMESPACE" get svc -o wide > "$dir/services-namespace-wide.txt" 2>&1 || true
  kubectl -n "$NAMESPACE" get endpoints -o wide > "$dir/endpoints-namespace-wide.txt" 2>&1 || true
}

run_cmd "git status" "$OUT_DIR/repo/git-status.txt" git status --short
run_cmd "git branch" "$OUT_DIR/repo/git-branch.txt" git branch --show-current
run_cmd "git last commit" "$OUT_DIR/repo/git-last-commit.txt" git log -1 --oneline

capture_host_set "$OUT_DIR/host/initial"
capture_k8s_set "$OUT_DIR/k8s/initial"

PF_LOG="$OUT_DIR/logs/port-forward.log"

echo "Starting RPC port-forward..."
kubectl -n "$NAMESPACE" port-forward "svc/${RPC_SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}" >"$PF_LOG" 2>&1 &
PF_PID="$!"

cleanup() {
  kill "$PF_PID" 2>/dev/null || true
  wait "$PF_PID" 2>/dev/null || true
}
trap cleanup EXIT

sleep 3

echo "PORT_FORWARD_PID=$PF_PID"
echo "--- port-forward log ---"
cat "$PF_LOG" || true
echo "------------------------"

if ! kill -0 "$PF_PID" 2>/dev/null; then
  echo "ERROR: port-forward process is not running"
  exit 1
fi

capture_rpc_set "$OUT_DIR/rpc/initial"

START_EPOCH="$(date +%s)"
END_EPOCH="$((START_EPOCH + DURATION_SECONDS))"
SAMPLE_INDEX=0

echo
echo "Starting idle sampling loop..."
echo "Start UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

while true; do
  NOW_EPOCH="$(date +%s)"
  if [ "$NOW_EPOCH" -gt "$END_EPOCH" ]; then
    break
  fi

  SAMPLE_DIR="$OUT_DIR/samples/sample-$(printf '%04d' "$SAMPLE_INDEX")"
  mkdir -p "$SAMPLE_DIR"

  echo "sample_index=$SAMPLE_INDEX" > "$SAMPLE_DIR/sample.env"
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SAMPLE_DIR/sample.env"
  echo "elapsed_seconds=$((NOW_EPOCH - START_EPOCH))" >> "$SAMPLE_DIR/sample.env"

  capture_rpc_set "$SAMPLE_DIR/rpc"
  capture_host_set "$SAMPLE_DIR/host"
  capture_k8s_set "$SAMPLE_DIR/k8s"

  SAMPLE_INDEX="$((SAMPLE_INDEX + 1))"
  sleep "$SAMPLE_INTERVAL"
done

echo "End UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

capture_rpc_set "$OUT_DIR/rpc/final"
capture_host_set "$OUT_DIR/host/final"
capture_k8s_set "$OUT_DIR/k8s/final"

cat > "$OUT_DIR/summary/summary.env" <<SUMMARY
stage=$STAGE
run_id=$RUN_ID
load_level=$LOAD_LEVEL
run_kind=$RUN_KIND
offered_load=0
target_transaction_rate=0
duration_seconds=$DURATION_SECONDS
sample_interval_seconds=$SAMPLE_INTERVAL
sample_count=$SAMPLE_INDEX
completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SUMMARY

echo
echo "=== L0 idle baseline completed ==="
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "SAMPLE_COUNT=$SAMPLE_INDEX"
