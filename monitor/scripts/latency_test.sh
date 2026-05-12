#!/usr/bin/env bash
# Quickly run the latency monitor; useful for validating builds in CI.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/configs/config.example.yaml}"

echo "Starting the latency monitor with config ${CONFIG_PATH} in simulation mode"
cd "${ROOT_DIR}"

if [[ -n "${GRPC_ENDPOINT:-}" ]]; then
  EXTRA_FLAGS=(--grpc-endpoint "${GRPC_ENDPOINT}")
else
  EXTRA_FLAGS=()
fi

go run main.go --config "${CONFIG_PATH}" "${EXTRA_FLAGS[@]}"
