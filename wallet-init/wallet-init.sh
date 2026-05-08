#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/solana/bin:$PATH"

SOLANA_URL="${SOLANA_URL:-http://validator:8899}"
PAYER="${PAYER:-}"
AIRDROP_SOL="${AIRDROP_SOL:-10000}"

if [ -z "$PAYER" ]; then
  echo "ERROR: PAYER is not set."
  exit 1
fi

echo "Configuring Solana CLI URL: $SOLANA_URL"
solana config set --url "$SOLANA_URL"

echo "Waiting for validator RPC to become available..."

for attempt in $(seq 1 60); do
  if solana --url "$SOLANA_URL" cluster-version >/dev/null 2>&1; then
    echo "Validator RPC is ready."
    break
  fi

  if [ "$attempt" -eq 60 ]; then
    echo "ERROR: Validator RPC is not ready after 60 attempts."
    exit 1
  fi

  sleep 2
done

echo "Payer address: $PAYER"

echo "Balance before airdrop:"
solana --url "$SOLANA_URL" balance "$PAYER" || true

echo "Requesting airdrop: $AIRDROP_SOL SOL"
solana --url "$SOLANA_URL" airdrop "$AIRDROP_SOL" "$PAYER"

echo "Balance after airdrop:"
solana --url "$SOLANA_URL" balance "$PAYER"
