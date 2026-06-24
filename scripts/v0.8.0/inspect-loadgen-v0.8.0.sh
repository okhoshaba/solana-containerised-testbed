#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_BRANCH="v0.8.0-dynamic-load-system-identification"

NAMESPACE="${NAMESPACE:-solana-observability}"
LOADGEN_SERVICE="${LOADGEN_SERVICE:-solana-loadgen2}"
LOCAL_PORT="${LOCAL_PORT:-17070}"
REMOTE_PORT="${REMOTE_PORT:-7070}"
OUT_ROOT="${OUT_ROOT:-results/v0.8.0/loadgen-inspection}"

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

INSPECT_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_ROOT}/${INSPECT_ID}"
mkdir -p "$OUT_DIR"

REPORT="${OUT_DIR}/loadgen-inspection-report.txt"
PF_LOG="${OUT_DIR}/loadgen-port-forward.log"

PF_PID=""

cleanup() {
  if [ -n "$PF_PID" ] && kill -0 "$PF_PID" >/dev/null 2>&1; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

{
  echo "# v0.8.0 loadgen inspection"
  echo
  echo "timestamp_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "branch: $CURRENT_BRANCH"
  echo "commit_sha: $(git rev-parse --short=12 HEAD)"
  echo "namespace: $NAMESPACE"
  echo "loadgen_service: $LOADGEN_SERVICE"
  echo
  echo "## Service"
  kubectl -n "$NAMESPACE" get svc "$LOADGEN_SERVICE" -o wide || true
  echo
  echo "## Service YAML"
  kubectl -n "$NAMESPACE" get svc "$LOADGEN_SERVICE" -o yaml || true
  echo
  echo "## Endpoints"
  kubectl -n "$NAMESPACE" get endpoints "$LOADGEN_SERVICE" -o wide || true
  echo
  echo "## EndpointSlices"
  kubectl -n "$NAMESPACE" get endpointslices -l kubernetes.io/service-name="$LOADGEN_SERVICE" -o wide || true
  echo
  echo "## Loadgen pods by known label"
  kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name="$LOADGEN_SERVICE" -o wide || true
  echo
  echo "## Loadgen pod details"
  kubectl -n "$NAMESPACE" get pods -l app.kubernetes.io/name="$LOADGEN_SERVICE" -o yaml || true
  echo
  echo "## Recent loadgen logs"
  kubectl -n "$NAMESPACE" logs -l app.kubernetes.io/name="$LOADGEN_SERVICE" --tail=120 || true
} > "$REPORT" 2>&1

kubectl -n "$NAMESPACE" port-forward "svc/${LOADGEN_SERVICE}" "${LOCAL_PORT}:${REMOTE_PORT}" \
  > "$PF_LOG" 2>&1 &

PF_PID="$!"

sleep 3

{
  echo
  echo "## HTTP probing through port-forward"
  echo "local_url: http://127.0.0.1:${LOCAL_PORT}"
  echo

  for path in "/" "/health" "/status" "/metrics" "/ready" "/live"; do
    echo "### GET ${path}"
    curl -sS --max-time 5 "http://127.0.0.1:${LOCAL_PORT}${path}" || true
    echo
    echo
  done

  echo "## Port-forward log"
  cat "$PF_LOG" || true
} >> "$REPORT" 2>&1

echo "Loadgen inspection report: $REPORT"
