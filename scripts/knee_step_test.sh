#!/usr/bin/env bash
set -euo pipefail

HOLD="${HOLD:-60}"
SAMPLE="${SAMPLE:-2}"
WARMUP="${WARMUP:-0}"
RATE_KEY="${RATE_KEY:-lambda}"
LOADGEN_URL="${LOADGEN_URL:-http://127.0.0.1:7070}"
PROM_URL="${PROM_URL:-http://127.0.0.1:9464}"
RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
LAT_METRIC="${LAT_METRIC:-solana_transaction_latency_seconds}"
SLOT_METRIC="${SLOT_METRIC:-solana_slot_interval_seconds}"
SUBSCRIPTION_ERRORS_METRIC="${SUBSCRIPTION_ERRORS_METRIC:-solana_subscription_errors_total}"
WORKERS="${WORKERS:-}"
BURST="${BURST:-}"
CONTROLLER_MODE="${CONTROLLER_MODE:-open_loop_step}"
EXPERIMENT_ID="${EXPERIMENT_ID:-knee_step_$(date -u +%Y%m%dT%H%M%SZ)}"
LEVELS_STR="${LEVELS_STR:-50 150 300 450 600 800 1000 1200 1300 1450 1650 1850 1650 1450 1300 1200 1000 800 600 450 300 150 50}"
OUT="${OUT:-data/raw/${EXPERIMENT_ID}.csv}"

mkdir -p "$(dirname "$OUT")"

echo "[knee_step_test] experiment_id=${EXPERIMENT_ID}" >&2
echo "[knee_step_test] out=${OUT}" >&2
echo "[knee_step_test] levels=${LEVELS_STR}" >&2

python3 scripts/collect_csv.py \
  --loadgen-url "${LOADGEN_URL}" \
  --prom-url "${PROM_URL}" \
  --rpc-url "${RPC_URL}" \
  --lat-metric "${LAT_METRIC}" \
  --slot-metric "${SLOT_METRIC}" \
  --subscription-errors-metric "${SUBSCRIPTION_ERRORS_METRIC}" \
  --rate-key "${RATE_KEY}" \
  --sample "${SAMPLE}" \
  --experiment-id "${EXPERIMENT_ID}" \
  --workers "${WORKERS}" \
  --burst "${BURST}" \
  --controller-mode "${CONTROLLER_MODE}" \
  step \
    --levels "${LEVELS_STR}" \
    --hold "${HOLD}" \
    --warmup "${WARMUP}" \
  | tee "${OUT}"

echo "[knee_step_test] wrote ${OUT}" >&2
