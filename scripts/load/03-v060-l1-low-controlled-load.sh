#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

STAGE="v0.6.0"
LOAD_LEVEL="${LOAD_LEVEL:-L1}"
RUN_KIND="${RUN_KIND:-low-controlled-load}"

NAMESPACE="${NAMESPACE:-solana-observability}"

RPC_SERVICE="${RPC_SERVICE:-solana-rpc}"
RPC_LOCAL_PORT="${RPC_LOCAL_PORT:-18899}"
RPC_REMOTE_PORT="${RPC_REMOTE_PORT:-8899}"

LOADGEN_SERVICE="${LOADGEN_SERVICE:-solana-loadgen2}"
LOADGEN_LOCAL_PORT="${LOADGEN_LOCAL_PORT:-17070}"
LOADGEN_REMOTE_PORT="${LOADGEN_REMOTE_PORT:-7070}"

TARGET_LAMBDA="${TARGET_LAMBDA:-1}"
DURATION_SECONDS="${DURATION_SECONDS:-60}"
SAMPLE_INTERVAL="${SAMPLE_INTERVAL:-5}"

HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown-branch)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown-sha)"

RUN_ID="${STAGE}_${HOST_SHORT}_${TS_UTC}_${LOAD_LEVEL}-${RUN_KIND}_lambda-${TARGET_LAMBDA}_${GIT_SHA}"
OUT_DIR="${ROOT_DIR}/results/${STAGE}/raw/${RUN_ID}"

mkdir -p "$OUT_DIR"/{repo,host,k8s,rpc,loadgen,samples,logs,summary}

exec > >(tee "$OUT_DIR/logs/l1-low-controlled-load.stdout.log") 2> >(tee "$OUT_DIR/logs/l1-low-controlled-load.stderr.log" >&2)

RPC_URL="http://127.0.0.1:${RPC_LOCAL_PORT}"
LOADGEN_URL="http://127.0.0.1:${LOADGEN_LOCAL_PORT}"

RPC_PF_PID=""
LOADGEN_PF_PID=""

echo "=== v0.6.0 L1 low controlled load ==="
echo "ROOT_DIR=$ROOT_DIR"
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "NAMESPACE=$NAMESPACE"
echo "RPC_SERVICE=$RPC_SERVICE"
echo "LOADGEN_SERVICE=$LOADGEN_SERVICE"
echo "TARGET_LAMBDA=$TARGET_LAMBDA"
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
offered_load=$TARGET_LAMBDA
target_lambda=$TARGET_LAMBDA
duration_seconds=$DURATION_SECONDS
sample_interval_seconds=$SAMPLE_INTERVAL
namespace=$NAMESPACE
rpc_service=$RPC_SERVICE
rpc_local_port=$RPC_LOCAL_PORT
rpc_remote_port=$RPC_REMOTE_PORT
loadgen_service=$LOADGEN_SERVICE
loadgen_local_port=$LOADGEN_LOCAL_PORT
loadgen_remote_port=$LOADGEN_REMOTE_PORT
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

  curl -sS -m 5 "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\"}" \
    > "$outfile" 2>&1 || true
}

loadgen_get_stats() {
  local outfile="$1"
  curl -sS -m 5 "${LOADGEN_URL}/stats" > "$outfile" 2>&1 || true
}

loadgen_set_lambda() {
  local value="$1"
  local outfile="$2"

  curl -sS -m 5 -X POST "${LOADGEN_URL}/rate" \
    -H "Content-Type: application/json" \
    -d "{\"lambda\":${value}}" \
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
}

capture_k8s_set() {
  local dir="$1"
  mkdir -p "$dir"

  date -u +%Y-%m-%dT%H:%M:%SZ > "$dir/timestamp_utc.txt"
  kubectl get nodes -o wide > "$dir/nodes-wide.txt" 2>&1 || true
  kubectl get pods -A -o wide > "$dir/pods-all-namespaces-wide.txt" 2>&1 || true
  kubectl -n "$NAMESPACE" get pods -o wide > "$dir/pods-namespace-wide.txt" 2>&1 || true
  kubectl -n "$NAMESPACE" get svc -o wide > "$dir/services-namespace-wide.txt" 2>&1 || true
}

write_stats_csv_header() {
  cat > "$OUT_DIR/loadgen/stats_samples.csv" <<CSV
timestamp_utc,elapsed_seconds,sample_index,target_lambda,sent_total,ok_total,err_total,inflight,inflight_max,sent_per_sec,err_per_sec,last_err
CSV
}

append_stats_csv() {
  local timestamp_utc="$1"
  local elapsed_seconds="$2"
  local sample_index="$3"
  local json_file="$4"

  python3 - "$timestamp_utc" "$elapsed_seconds" "$sample_index" "$json_file" "$OUT_DIR/loadgen/stats_samples.csv" <<'PY'
import csv
import json
import sys

timestamp_utc, elapsed_seconds, sample_index, json_file, csv_file = sys.argv[1:6]

try:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as exc:
    data = {
        "target_lambda": "",
        "sent_total": "",
        "ok_total": "",
        "err_total": "",
        "inflight": "",
        "inflight_max": "",
        "sent_per_sec": "",
        "err_per_sec": "",
        "last_err": f"parse_error:{exc}",
    }

row = {
    "timestamp_utc": timestamp_utc,
    "elapsed_seconds": elapsed_seconds,
    "sample_index": sample_index,
    "target_lambda": data.get("target_lambda", ""),
    "sent_total": data.get("sent_total", ""),
    "ok_total": data.get("ok_total", ""),
    "err_total": data.get("err_total", ""),
    "inflight": data.get("inflight", ""),
    "inflight_max": data.get("inflight_max", ""),
    "sent_per_sec": data.get("sent_per_sec", ""),
    "err_per_sec": data.get("err_per_sec", ""),
    "last_err": data.get("last_err", ""),
}

with open(csv_file, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(row.keys()))
    writer.writerow(row)
PY
}

cleanup() {
  echo
  echo "=== cleanup ==="

  if [ -n "${LOADGEN_PF_PID:-}" ] && kill -0 "$LOADGEN_PF_PID" 2>/dev/null; then
    echo "Returning loadgen lambda to 0..."
    mkdir -p "$OUT_DIR/loadgen/final"
    loadgen_set_lambda 0 "$OUT_DIR/loadgen/final/set-lambda-0.cleanup.txt" || true
    sleep 2
    loadgen_get_stats "$OUT_DIR/loadgen/final/stats-after-cleanup.json" || true
  fi

  if [ -n "${RPC_PF_PID:-}" ]; then
    kill "$RPC_PF_PID" 2>/dev/null || true
    wait "$RPC_PF_PID" 2>/dev/null || true
  fi

  if [ -n "${LOADGEN_PF_PID:-}" ]; then
    kill "$LOADGEN_PF_PID" 2>/dev/null || true
    wait "$LOADGEN_PF_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

run_cmd "git status" "$OUT_DIR/repo/git-status.txt" git status --short
run_cmd "git branch" "$OUT_DIR/repo/git-branch.txt" git branch --show-current
run_cmd "git last commit" "$OUT_DIR/repo/git-last-commit.txt" git log -1 --oneline

capture_host_set "$OUT_DIR/host/initial"
capture_k8s_set "$OUT_DIR/k8s/initial"

echo "Starting RPC port-forward..."
kubectl -n "$NAMESPACE" port-forward "svc/${RPC_SERVICE}" "${RPC_LOCAL_PORT}:${RPC_REMOTE_PORT}" > "$OUT_DIR/logs/rpc-port-forward.log" 2>&1 &
RPC_PF_PID="$!"
sleep 3

echo "RPC_PF_PID=$RPC_PF_PID"
cat "$OUT_DIR/logs/rpc-port-forward.log" || true

if ! kill -0 "$RPC_PF_PID" 2>/dev/null; then
  echo "ERROR: RPC port-forward process is not running"
  exit 1
fi

echo
echo "Starting loadgen port-forward..."
kubectl -n "$NAMESPACE" port-forward "svc/${LOADGEN_SERVICE}" "${LOADGEN_LOCAL_PORT}:${LOADGEN_REMOTE_PORT}" > "$OUT_DIR/logs/loadgen-port-forward.log" 2>&1 &
LOADGEN_PF_PID="$!"
sleep 3

echo "LOADGEN_PF_PID=$LOADGEN_PF_PID"
cat "$OUT_DIR/logs/loadgen-port-forward.log" || true

if ! kill -0 "$LOADGEN_PF_PID" 2>/dev/null; then
  echo "ERROR: loadgen port-forward process is not running"
  exit 1
fi

capture_rpc_set "$OUT_DIR/rpc/initial"
loadgen_get_stats "$OUT_DIR/loadgen/initial-stats.json"

echo
echo "Ensuring safe initial lambda=0..."
loadgen_set_lambda 0 "$OUT_DIR/loadgen/set-lambda-0-before.txt"
sleep 2
loadgen_get_stats "$OUT_DIR/loadgen/stats-after-initial-zero.json"

echo
echo "Setting target lambda=${TARGET_LAMBDA}..."
loadgen_set_lambda "$TARGET_LAMBDA" "$OUT_DIR/loadgen/set-lambda-${TARGET_LAMBDA}.txt"
sleep 2
loadgen_get_stats "$OUT_DIR/loadgen/stats-after-set-lambda-${TARGET_LAMBDA}.json"

write_stats_csv_header

START_EPOCH="$(date +%s)"
END_EPOCH="$((START_EPOCH + DURATION_SECONDS))"
SAMPLE_INDEX=0

echo
echo "Starting L1 sampling loop..."
echo "Start UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

while true; do
  NOW_EPOCH="$(date +%s)"
  if [ "$NOW_EPOCH" -gt "$END_EPOCH" ]; then
    break
  fi

  TS_NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ELAPSED="$((NOW_EPOCH - START_EPOCH))"

  SAMPLE_DIR="$OUT_DIR/samples/sample-$(printf '%04d' "$SAMPLE_INDEX")"
  mkdir -p "$SAMPLE_DIR"/{rpc,host,k8s,loadgen}

  echo "sample_index=$SAMPLE_INDEX" > "$SAMPLE_DIR/sample.env"
  echo "timestamp_utc=$TS_NOW" >> "$SAMPLE_DIR/sample.env"
  echo "elapsed_seconds=$ELAPSED" >> "$SAMPLE_DIR/sample.env"

  capture_rpc_set "$SAMPLE_DIR/rpc"
  capture_host_set "$SAMPLE_DIR/host"
  capture_k8s_set "$SAMPLE_DIR/k8s"
  loadgen_get_stats "$SAMPLE_DIR/loadgen/stats.json"

  append_stats_csv "$TS_NOW" "$ELAPSED" "$SAMPLE_INDEX" "$SAMPLE_DIR/loadgen/stats.json"

  SAMPLE_INDEX="$((SAMPLE_INDEX + 1))"
  sleep "$SAMPLE_INTERVAL"
done

echo "End UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo
echo "Returning lambda to 0..."
loadgen_set_lambda 0 "$OUT_DIR/loadgen/set-lambda-0-after.txt"
sleep 3
loadgen_get_stats "$OUT_DIR/loadgen/final-stats.json"

capture_rpc_set "$OUT_DIR/rpc/final"
capture_host_set "$OUT_DIR/host/final"
capture_k8s_set "$OUT_DIR/k8s/final"

python3 - "$OUT_DIR/loadgen/initial-stats.json" "$OUT_DIR/loadgen/final-stats.json" "$OUT_DIR/summary/summary.env" <<'PY'
import json
import sys

initial_path, final_path, summary_path = sys.argv[1:4]

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

initial = load_json(initial_path)
final = load_json(final_path)

sent_initial = int(initial.get("sent_total", 0) or 0)
sent_final = int(final.get("sent_total", 0) or 0)

ok_initial = int(initial.get("ok_total", 0) or 0)
ok_final = int(final.get("ok_total", 0) or 0)

err_initial = int(initial.get("err_total", 0) or 0)
err_final = int(final.get("err_total", 0) or 0)

sent_delta = sent_final - sent_initial
ok_delta = ok_final - ok_initial
err_delta = err_final - err_initial

with open(summary_path, "a", encoding="utf-8") as f:
    f.write(f"sent_initial={sent_initial}\n")
    f.write(f"sent_final={sent_final}\n")
    f.write(f"sent_delta={sent_delta}\n")
    f.write(f"ok_initial={ok_initial}\n")
    f.write(f"ok_final={ok_final}\n")
    f.write(f"ok_delta={ok_delta}\n")
    f.write(f"err_initial={err_initial}\n")
    f.write(f"err_final={err_final}\n")
    f.write(f"err_delta={err_delta}\n")
    f.write(f"final_target_lambda={final.get('target_lambda', '')}\n")
    f.write(f"final_inflight={final.get('inflight', '')}\n")
    f.write(f"final_last_err={final.get('last_err', '')}\n")
PY

cat > "$OUT_DIR/summary/run.env" <<SUMMARY
stage=$STAGE
run_id=$RUN_ID
load_level=$LOAD_LEVEL
run_kind=$RUN_KIND
target_lambda=$TARGET_LAMBDA
duration_seconds=$DURATION_SECONDS
sample_interval_seconds=$SAMPLE_INTERVAL
sample_count=$SAMPLE_INDEX
completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SUMMARY

cat "$OUT_DIR/summary/run.env" "$OUT_DIR/summary/summary.env" > "$OUT_DIR/summary/combined-summary.env"

echo
echo "=== L1 low controlled load completed ==="
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "SAMPLE_COUNT=$SAMPLE_INDEX"
echo
cat "$OUT_DIR/summary/combined-summary.env"
