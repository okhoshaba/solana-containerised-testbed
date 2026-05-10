#!/usr/bin/env bash
# 快速执行延迟监测主程序，可在 CI 中使用快速模式验证构建。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-${ROOT_DIR}/configs/config.example.yaml}"

echo "使用配置 ${CONFIG_PATH} 启动延迟监测主程序（模拟模式）"
cd "${ROOT_DIR}"

if [[ -n "${GRPC_ENDPOINT:-}" ]]; then
  EXTRA_FLAGS=(--grpc-endpoint "${GRPC_ENDPOINT}")
else
  EXTRA_FLAGS=()
fi

go run main.go --config "${CONFIG_PATH}" "${EXTRA_FLAGS[@]}"
