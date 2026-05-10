#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

podman compose -f compose.yellowstone.yaml down -v || true
podman rm -f solana-localnet-validator solana-wallet-init solana-latency-monitor 2>/dev/null || true

echo "Starting Yellowstone/Geyser testbed..."
podman compose -f compose.yellowstone.yaml up --build validator wallet-init monitor
