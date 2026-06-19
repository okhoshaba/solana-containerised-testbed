#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

STAGE="v0.6.0"
NAMESPACE="${NAMESPACE:-solana-observability}"
RPC_SERVICE="${RPC_SERVICE:-solana-rpc}"
LOCAL_PORT="${LOCAL_PORT:-18899}"
REMOTE_PORT="${REMOTE_PORT:-8899}"

HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown-branch)"
GIT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown-sha)"

RUN_ID="${STAGE}_${HOST_SHORT}_${TS_UTC}_rpc-preflight_${GIT_SHA}"
OUT_DIR="${ROOT_DIR}/results/${STAGE}/raw/${RUN_ID}"

mkdir -p "$OUT_DIR"
mkdir -p "$OUT_DIR/rpc"
mkdir -p "$OUT_DIR/k8s"
mkdir -p "$OUT_DIR/logs"

exec > >(tee "$OUT_DIR/logs/rpc-preflight.stdout.log") 2> >(tee "$OUT_DIR/logs/rpc-preflight.stderr.log" >&2)

echo "=== v0.6.0 RPC preflight via kubectl port-forward ==="
echo "ROOT_DIR=$ROOT_DIR"
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
echo "NAMESPACE=$NAMESPACE"
echo "RPC_SERVICE=$RPC_SERVICE"
echo "LOCAL_PORT=$LOCAL_PORT"
echo "REMOTE_PORT=$REMOTE_PORT"
echo

cat > "$OUT_DIR/metadata.env" <<META
stage=$STAGE
run_id=$RUN_ID
timestamp_utc=$TS_UTC
host_short=$HOST_SHORT
hostname=$(hostname 2>/dev/null || echo unknown)
git_branch=$GIT_BRANCH
git_sha=$GIT_SHA
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

run_cmd "kubectl service state" "$OUT_DIR/k8s/services.txt" \
  kubectl -n "$NAMESPACE" get svc "$RPC_SERVICE" -o wide

run_cmd "kubectl endpoints state" "$OUT_DIR/k8s/endpoints.txt" \
  kubectl -n "$NAMESPACE" get endpoints "$RPC_SERVICE" -o wide

PF_LOG="$OUT_DIR/logs/port-forward.log"

echo "Starting port-forward..."
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

RPC_URL="http://127.0.0.1:${LOCAL_PORT}"

run_cmd "solana rpc getHealth" "$OUT_DIR/rpc/getHealth.json" \
  curl -sS -m 5 "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

run_cmd "solana rpc getVersion" "$OUT_DIR/rpc/getVersion.json" \
  curl -sS -m 5 "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"getVersion"}'

run_cmd "solana rpc getEpochInfo" "$OUT_DIR/rpc/getEpochInfo.json" \
  curl -sS -m 5 "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"getEpochInfo"}'

run_cmd "solana rpc getSlot" "$OUT_DIR/rpc/getSlot.json" \
  curl -sS -m 5 "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'

echo
echo "=== RPC preflight completed ==="
echo "RUN_ID=$RUN_ID"
echo "OUT_DIR=$OUT_DIR"
