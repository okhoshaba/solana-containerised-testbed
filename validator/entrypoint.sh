#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/solana/bin:$PATH"

LEDGER_PATH="${LEDGER_PATH:-/var/lib/solana/ledger}"
RESET_LEDGER="${RESET_LEDGER:-true}"
VALIDATOR_BIND_ADDRESS="${VALIDATOR_BIND_ADDRESS:-0.0.0.0}"
RPC_PORT="${RPC_PORT:-8899}"
ENABLE_GEYSER="${ENABLE_GEYSER:-false}"
GEYSER_CONFIG="${GEYSER_CONFIG:-/etc/solana/yellowstone-geyser.json}"

mkdir -p "$LEDGER_PATH"

RESET_ARGS=()
if [ "$RESET_LEDGER" = "true" ]; then
  RESET_ARGS=(--reset)
fi

GEYSER_ARGS=()
if [ "$ENABLE_GEYSER" = "true" ]; then
  if [ ! -f "$GEYSER_CONFIG" ]; then
    echo "ERROR: ENABLE_GEYSER=true but config file does not exist: $GEYSER_CONFIG"
    exit 1
  fi

  GEYSER_ARGS=(--geyser-plugin-config "$GEYSER_CONFIG")
fi

echo "Starting solana-test-validator"
echo "Ledger path: $LEDGER_PATH"
echo "Reset ledger: $RESET_LEDGER"
echo "RPC bind address: $VALIDATOR_BIND_ADDRESS"
echo "RPC port: $RPC_PORT"
echo "Geyser enabled: $ENABLE_GEYSER"

exec solana-test-validator \
  --ledger "$LEDGER_PATH" \
  "${RESET_ARGS[@]}" \
  --bind-address "$VALIDATOR_BIND_ADDRESS" \
  --rpc-port "$RPC_PORT" \
  "${GEYSER_ARGS[@]}" \
  "$@"
