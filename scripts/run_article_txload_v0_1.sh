#!/usr/bin/env bash
set -Eeuo pipefail

PROFILE="${1:-low}"
DURATION_SECONDS="${2:-300}"
RATE_PER_SECOND="${3:-1}"
OUT_DIR="${4:-}"
RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
AMOUNT_SOL="${AMOUNT_SOL:-0.000001}"
AIRDROP_SOL="${AIRDROP_SOL:-10}"
ALLOW_NON_LOCALNET="${ALLOW_NON_LOCALNET:-false}"
TRANSFER_TIMEOUT_SECONDS="${TRANSFER_TIMEOUT_SECONDS:-25}"

case "$RPC_URL" in
  http://127.0.0.1:*|http://localhost:*)
    ;;
  *)
    if [ "$ALLOW_NON_LOCALNET" != "true" ]; then
      echo "[ERROR] RPC_URL is not localhost: $RPC_URL" >&2
      echo "[ERROR] Refusing to run transaction workload outside localnet." >&2
      echo "[ERROR] Set ALLOW_NON_LOCALNET=true only if you intentionally use a private test network." >&2
      exit 1
    fi
    ;;
esac

if ! command -v solana >/dev/null 2>&1; then
  echo "[ERROR] solana CLI not found in PATH." >&2
  echo "[ERROR] Install Solana CLI or run this script in an environment where solana is available." >&2
  exit 1
fi

if ! command -v solana-keygen >/dev/null 2>&1; then
  echo "[ERROR] solana-keygen not found in PATH." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found in PATH." >&2
  exit 1
fi

if ! [[ "$DURATION_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] DURATION_SECONDS must be an integer." >&2
  exit 1
fi

if ! [[ "$RATE_PER_SECOND" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] RATE_PER_SECOND must be an integer." >&2
  exit 1
fi

if [ "$RATE_PER_SECOND" -lt 1 ]; then
  echo "[ERROR] RATE_PER_SECOND must be at least 1." >&2
  exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOST="$(hostname | tr -c 'A-Za-z0-9._-' '_')"
GIT_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"

if [ -z "$OUT_DIR" ]; then
  RUN_ID="${TS}_${HOST}_txload-${PROFILE}_${DURATION_SECONDS}s_${GIT_SHORT}"
  OUT_DIR="data/article-workloads/${RUN_ID}"
fi

mkdir -p "$OUT_DIR" "$OUT_DIR/logs" "$OUT_DIR/keypairs"

PAYER_KEYPAIR="$OUT_DIR/keypairs/txload-payer.json"
RECIPIENT_KEYPAIR="$OUT_DIR/keypairs/txload-recipient.json"
PAYER_PUBKEY_FILE="$OUT_DIR/payer.pubkey"
RECIPIENT_PUBKEY_FILE="$OUT_DIR/recipient.pubkey"
METRICS_CSV="$OUT_DIR/txload_metrics.csv"
SUMMARY_JSON="$OUT_DIR/txload_summary.json"
CONFIG_JSON="$OUT_DIR/txload_config.json"

cleanup_note() {
  echo "[INFO] Workload output directory: $OUT_DIR"
  echo "[INFO] Keypairs are localnet-only and stored under: $OUT_DIR/keypairs"
  echo "[INFO] Do not publish keypair JSON files to public repositories."
}
trap cleanup_note EXIT

echo "[INFO] Root directory: $ROOT_DIR"
echo "[INFO] RPC URL: $RPC_URL"
echo "[INFO] Profile: $PROFILE"
echo "[INFO] Duration: ${DURATION_SECONDS}s"
echo "[INFO] Target rate: ${RATE_PER_SECOND} tx/s"
echo "[INFO] Output directory: $OUT_DIR"

HEALTH_RAW="$(curl -sS "$RPC_URL" -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}' --max-time 5 2>/dev/null || true)"
HEALTH_RESULT="$(python3 - <<PY
import json
raw = '''$HEALTH_RAW'''
try:
    print(json.loads(raw).get('result', ''))
except Exception:
    print('')
PY
)"

if [ "$HEALTH_RESULT" != "ok" ]; then
  echo "[ERROR] RPC health check failed." >&2
  echo "[ERROR] Response: $HEALTH_RAW" >&2
  exit 1
fi

solana-keygen new --no-bip39-passphrase --force -o "$PAYER_KEYPAIR" >/dev/null
solana-keygen new --no-bip39-passphrase --force -o "$RECIPIENT_KEYPAIR" >/dev/null

PAYER_PUBKEY="$(solana-keygen pubkey "$PAYER_KEYPAIR")"
RECIPIENT_PUBKEY="$(solana-keygen pubkey "$RECIPIENT_KEYPAIR")"
printf '%s\n' "$PAYER_PUBKEY" > "$PAYER_PUBKEY_FILE"
printf '%s\n' "$RECIPIENT_PUBKEY" > "$RECIPIENT_PUBKEY_FILE"

cat > "$CONFIG_JSON" <<JSON
{
  "profile": "$PROFILE",
  "duration_seconds": $DURATION_SECONDS,
  "rate_per_second": $RATE_PER_SECOND,
  "rpc_url": "$RPC_URL",
  "amount_sol": "$AMOUNT_SOL",
  "airdrop_sol": "$AIRDROP_SOL",
  "payer_pubkey": "$PAYER_PUBKEY",
  "recipient_pubkey": "$RECIPIENT_PUBKEY",
  "timestamp_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$HOST",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo unknown)",
  "git_short_commit": "$GIT_SHORT"
}
JSON

echo "[INFO] Funding local payer via airdrop..."
if ! solana airdrop "$AIRDROP_SOL" "$PAYER_PUBKEY" --url "$RPC_URL" > "$OUT_DIR/logs/airdrop.log" 2>&1; then
  echo "[ERROR] Airdrop failed. See: $OUT_DIR/logs/airdrop.log" >&2
  exit 1
fi

solana balance "$PAYER_PUBKEY" --url "$RPC_URL" > "$OUT_DIR/logs/payer_balance_before.log" 2>&1 || true

echo "timestamp_utc,seq,profile,target_rate_per_second,exit_code,duration_ms,signature,log_file" > "$METRICS_CSV"

START_EPOCH="$(date +%s)"
END_EPOCH=$(( START_EPOCH + DURATION_SECONDS ))
SEQ=0
OK_COUNT=0
FAIL_COUNT=0

run_one_transfer() {
  local seq="$1"
  local now start_ms end_ms duration_ms log_file rc signature
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  start_ms="$(date +%s%3N)"
  log_file="$OUT_DIR/logs/transfer_${seq}.log"

  set +e
  timeout "$TRANSFER_TIMEOUT_SECONDS" \
    solana transfer "$RECIPIENT_PUBKEY" "$AMOUNT_SOL" \
      --from "$PAYER_KEYPAIR" \
      --allow-unfunded-recipient \
      --url "$RPC_URL" \
      > "$log_file" 2>&1
  rc="$?"
  set -e

  end_ms="$(date +%s%3N)"
  duration_ms=$(( end_ms - start_ms ))
  signature="$(sed -n 's/^Signature: //p' "$log_file" | tail -n 1 | tr -d '\r')"

  printf '%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$now" "$seq" "$PROFILE" "$RATE_PER_SECOND" "$rc" "$duration_ms" "$signature" "$log_file" \
    >> "$METRICS_CSV"

  return "$rc"
}

echo "[INFO] Starting workload..."
while [ "$(date +%s)" -lt "$END_EPOCH" ]; do
  SECOND_START_MS="$(date +%s%3N)"

  for _ in $(seq 1 "$RATE_PER_SECOND"); do
    SEQ=$(( SEQ + 1 ))
    if run_one_transfer "$SEQ"; then
      OK_COUNT=$(( OK_COUNT + 1 ))
    else
      FAIL_COUNT=$(( FAIL_COUNT + 1 ))
    fi
  done

  SECOND_END_MS="$(date +%s%3N)"
  ELAPSED_MS=$(( SECOND_END_MS - SECOND_START_MS ))
  SLEEP_MS=$(( 1000 - ELAPSED_MS ))
  if [ "$SLEEP_MS" -gt 0 ]; then
    python3 - <<PY
import time
time.sleep($SLEEP_MS / 1000.0)
PY
  fi

  if [ $(( SEQ % 10 )) -eq 0 ]; then
    echo "[INFO] seq=$SEQ ok=$OK_COUNT fail=$FAIL_COUNT"
  fi
done

solana balance "$PAYER_PUBKEY" --url "$RPC_URL" > "$OUT_DIR/logs/payer_balance_after.log" 2>&1 || true
solana balance "$RECIPIENT_PUBKEY" --url "$RPC_URL" > "$OUT_DIR/logs/recipient_balance_after.log" 2>&1 || true

cat > "$SUMMARY_JSON" <<JSON
{
  "profile": "$PROFILE",
  "duration_seconds": $DURATION_SECONDS,
  "target_rate_per_second": $RATE_PER_SECOND,
  "attempted_transactions": $SEQ,
  "successful_transactions": $OK_COUNT,
  "failed_transactions": $FAIL_COUNT,
  "output_directory": "$OUT_DIR",
  "metrics_csv": "$METRICS_CSV",
  "completed_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

sha256sum "$CONFIG_JSON" "$METRICS_CSV" "$SUMMARY_JSON" > "$OUT_DIR/txload_SHA256SUMS.txt"

echo "[OK] Workload completed."
echo "[OK] Attempted: $SEQ"
echo "[OK] Successful: $OK_COUNT"
echo "[OK] Failed: $FAIL_COUNT"
echo "[OK] Metrics: $METRICS_CSV"
echo "[OK] Summary: $SUMMARY_JSON"
