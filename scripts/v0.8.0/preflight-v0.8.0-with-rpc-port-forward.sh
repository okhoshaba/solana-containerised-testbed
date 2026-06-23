#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_BRANCH="v0.8.0-dynamic-load-system-identification"

RUN_ID="${1:-}"
NAMESPACE="${NAMESPACE:-solana-observability}"
RPC_SERVICE="${RPC_SERVICE:-solana-rpc}"
LOCAL_PORT="${LOCAL_PORT:-18899}"
REMOTE_PORT="${REMOTE_PORT:-8899}"
LOG_FILE="${LOG_FILE:-/tmp/v080-rpc-port-forward.log}"

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

if [ ! -x scripts/v0.8.0/preflight-v0.8.0.sh ]; then
  echo "ERROR: scripts/v0.8.0/preflight-v0.8.0.sh not found or not executable"
  exit 1
fi

PF_PID=""

cleanup() {
  if [ -n "$PF_PID" ] && kill -0 "$PF_PID" >/dev/null 2>&1; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting RPC port-forward:"
echo "  namespace: $NAMESPACE"
echo "  service:   $RPC_SERVICE"
echo "  local:     127.0.0.1:$LOCAL_PORT"
echo "  remote:    $REMOTE_PORT"
echo "  log:       $LOG_FILE"

kubectl -n "$NAMESPACE" port-forward "svc/${RPC_SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}" \
  > "$LOG_FILE" 2>&1 &

PF_PID="$!"

sleep 3

if ! kill -0 "$PF_PID" >/dev/null 2>&1; then
  echo "ERROR: port-forward process exited early"
  echo "Port-forward log:"
  cat "$LOG_FILE" || true
  exit 1
fi

RPC_URL="http://127.0.0.1:${LOCAL_PORT}" \
  scripts/v0.8.0/preflight-v0.8.0.sh "$RUN_ID"

STATUS="$?"

echo "preflight status: $STATUS"

exit "$STATUS"
