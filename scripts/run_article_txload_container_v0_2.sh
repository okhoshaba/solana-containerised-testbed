#!/usr/bin/env bash
set -Eeuo pipefail

PROFILE="${1:-low}"
DURATION_SECONDS="${2:-280}"
RATE_PER_SECOND="${3:-1}"
OUT_DIR="${4:-data/article-workloads/manual-txload}"

RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
AMOUNT_SOL="${AMOUNT_SOL:-0.000001}"
AIRDROP_SOL="${AIRDROP_SOL:-10}"

VALIDATOR_CONTAINER="${VALIDATOR_CONTAINER:-solana-localnet-validator}"

mkdir -p "$OUT_DIR/logs"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
WORKDIR="/tmp/article-txload-${TS}"
PAYER_KEYPAIR="$WORKDIR/payer.json"
RECIPIENT_KEYPAIR="$WORKDIR/recipient.json"

METRICS="$OUT_DIR/txload_metrics.csv"
SUMMARY="$OUT_DIR/txload_summary.json"

echo "[INFO] Validator container: $VALIDATOR_CONTAINER"
echo "[INFO] Output directory: $OUT_DIR"
echo "[INFO] Duration: $DURATION_SECONDS seconds"
echo "[INFO] Rate: $RATE_PER_SECOND tx/s"

podman exec "$VALIDATOR_CONTAINER" sh -lc "mkdir -p '$WORKDIR'"

podman exec "$VALIDATOR_CONTAINER" sh -lc \
  "solana-keygen new --no-bip39-passphrase --force -o '$PAYER_KEYPAIR' >/dev/null"

podman exec "$VALIDATOR_CONTAINER" sh -lc \
  "solana-keygen new --no-bip39-passphrase --force -o '$RECIPIENT_KEYPAIR' >/dev/null"

PAYER="$(podman exec "$VALIDATOR_CONTAINER" sh -lc "solana-keygen pubkey '$PAYER_KEYPAIR'" | tr -d '\r')"
RECIPIENT="$(podman exec "$VALIDATOR_CONTAINER" sh -lc "solana-keygen pubkey '$RECIPIENT_KEYPAIR'" | tr -d '\r')"

echo "$PAYER" > "$OUT_DIR/payer.pubkey"
echo "$RECIPIENT" > "$OUT_DIR/recipient.pubkey"

echo "[INFO] Payer: $PAYER"
echo "[INFO] Recipient: $RECIPIENT"

echo "[INFO] Airdrop..."
podman exec "$VALIDATOR_CONTAINER" sh -lc \
  "solana airdrop '$AIRDROP_SOL' '$PAYER' --url '$RPC_URL'" \
  > "$OUT_DIR/logs/airdrop.log" 2>&1

echo "timestamp_utc,seq,profile,rate_per_second,exit_code,duration_ms,signature,log_file" > "$METRICS"

START="$(date +%s)"
END=$((START + DURATION_SECONDS))
SEQ=0
OK=0
FAIL=0

while [ "$(date +%s)" -lt "$END" ]; do
  SECOND_START_MS="$(date +%s%3N)"

  for _ in $(seq 1 "$RATE_PER_SECOND"); do
    SEQ=$((SEQ + 1))
    NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    LOG="$OUT_DIR/logs/transfer_${SEQ}.log"
    T0="$(date +%s%3N)"

    set +e
    podman exec "$VALIDATOR_CONTAINER" sh -lc \
      "solana transfer '$RECIPIENT' '$AMOUNT_SOL' --from '$PAYER_KEYPAIR' --allow-unfunded-recipient --url '$RPC_URL'" \
      > "$LOG" 2>&1
    RC="$?"
    set -e

    T1="$(date +%s%3N)"
    DURATION_MS=$((T1 - T0))
    SIG="$(sed -n 's/^Signature: //p' "$LOG" | tail -n 1 | tr -d '\r')"

    echo "$NOW,$SEQ,$PROFILE,$RATE_PER_SECOND,$RC,$DURATION_MS,$SIG,$LOG" >> "$METRICS"

    if [ "$RC" -eq 0 ]; then
      OK=$((OK + 1))
    else
      FAIL=$((FAIL + 1))
    fi
  done

  SECOND_END_MS="$(date +%s%3N)"
  ELAPSED_MS=$((SECOND_END_MS - SECOND_START_MS))
  SLEEP_MS=$((1000 - ELAPSED_MS))

  if [ "$SLEEP_MS" -gt 0 ]; then
    python3 -c "import time; time.sleep($SLEEP_MS / 1000.0)"
  fi

  if [ $((SEQ % 10)) -eq 0 ]; then
    echo "[INFO] seq=$SEQ ok=$OK fail=$FAIL"
  fi
done

podman exec "$VALIDATOR_CONTAINER" sh -lc \
  "solana balance '$PAYER' --url '$RPC_URL'" \
  > "$OUT_DIR/logs/payer_balance_after.log" 2>&1 || true

podman exec "$VALIDATOR_CONTAINER" sh -lc \
  "solana balance '$RECIPIENT' --url '$RPC_URL'" \
  > "$OUT_DIR/logs/recipient_balance_after.log" 2>&1 || true

podman exec "$VALIDATOR_CONTAINER" sh -lc "rm -rf '$WORKDIR'" || true

cat > "$SUMMARY" <<JSON
{
  "profile": "$PROFILE",
  "duration_seconds": $DURATION_SECONDS,
  "rate_per_second": $RATE_PER_SECOND,
  "attempted_transactions": $SEQ,
  "successful_transactions": $OK,
  "failed_transactions": $FAIL,
  "validator_container": "$VALIDATOR_CONTAINER",
  "metrics_csv": "$METRICS",
  "completed_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

echo "[OK] Workload completed"
echo "[OK] attempted=$SEQ ok=$OK failed=$FAIL"
echo "[OK] summary=$SUMMARY"
