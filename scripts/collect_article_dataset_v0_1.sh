#!/usr/bin/env bash
set -Eeuo pipefail

PROFILE="${1:-baseline}"
DURATION_SECONDS="${2:-300}"
INTERVAL_SECONDS="${3:-5}"
RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
PROM_URL="${PROM_URL:-}"

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
HOST="$(hostname | tr -c 'A-Za-z0-9._-' '_')"
GIT_SHORT="$(git rev-parse --short HEAD 2>/dev/null || echo nogit)"
GIT_BRANCH="$(git branch --show-current 2>/dev/null || echo unknown)"
RUN_ID="${TS}_${HOST}_${PROFILE}_${DURATION_SECONDS}s_${GIT_SHORT}"

OUT_DIR="data/article-runs/${RUN_ID}"
mkdir -p "$OUT_DIR/prometheus-scrapes" "$OUT_DIR/logs"

echo "[INFO] Repository: $ROOT_DIR"
echo "[INFO] Run ID: $RUN_ID"
echo "[INFO] Output directory: $OUT_DIR"
echo "[INFO] RPC URL: $RPC_URL"

cat > "$OUT_DIR/metadata.json" <<EOF
{
  "run_id": "$RUN_ID",
  "timestamp_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "hostname": "$HOST",
  "profile": "$PROFILE",
  "duration_seconds": $DURATION_SECONDS,
  "interval_seconds": $INTERVAL_SECONDS,
  "rpc_url": "$RPC_URL",
  "prometheus_url": "$PROM_URL",
  "git_branch": "$GIT_BRANCH",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo unknown)",
  "git_short_commit": "$GIT_SHORT",
  "working_tree_dirty": "$(if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then echo false; else echo true; fi)"
}
EOF

cat > "$OUT_DIR/workload-profile.yaml" <<EOF
profile: "$PROFILE"
duration_seconds: $DURATION_SECONDS
interval_seconds: $INTERVAL_SECONDS
rpc_url: "$RPC_URL"
notes: "Dataset collected for the synthetic benchmarking Solana article."
EOF

{
  echo "{"
  echo "  \"hostname\": \"$HOST\","
  echo "  \"timestamp_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"kernel\": \"$(uname -srmo 2>/dev/null | sed 's/\"//g')\","
  echo "  \"os_release\": \"$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '\"' | sed 's/\"//g')\","
  echo "  \"cpu_model\": \"$(lscpu 2>/dev/null | awk -F: '/Model name/ {gsub(/^ +/, \"\", $2); print $2; exit}' | sed 's/\"//g')\","
  echo "  \"cpu_count\": \"$(nproc 2>/dev/null || echo unknown)\","
  echo "  \"memory_bytes\": \"$(free -b 2>/dev/null | awk '/Mem:/ {print $2}' || echo unknown)\","
  echo "  \"podman_version\": \"$(podman --version 2>/dev/null | sed 's/\"//g' || echo unavailable)\","
  echo "  \"docker_version\": \"$(docker --version 2>/dev/null | sed 's/\"//g' || echo unavailable)\","
  echo "  \"solana_version\": \"$(solana --version 2>/dev/null | sed 's/\"//g' || echo unavailable)\""
  echo "}"
} > "$OUT_DIR/host.json"

if command -v podman >/dev/null 2>&1; then
  podman ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" > "$OUT_DIR/container_ps.txt" || true
elif command -v docker >/dev/null 2>&1; then
  docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" > "$OUT_DIR/container_ps.txt" || true
else
  echo "No podman or docker command found." > "$OUT_DIR/container_ps.txt"
fi

cp compose*.yaml "$OUT_DIR/" 2>/dev/null || true
git status --short > "$OUT_DIR/git_status_short.txt" 2>/dev/null || true
git diff --stat > "$OUT_DIR/git_diff_stat.txt" 2>/dev/null || true

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

raw = sys.argv[1]
field = sys.argv[2]

try:
    obj = json.loads(raw)
    value = obj
    for part in field.split("."):
        value = value[part]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":")))
    else:
        print(value)
except Exception:
    print("")
PY
}

rpc_call() {
  local method="$1"
  curl -sS "$RPC_URL" \
    -H "Content-Type: application/json" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\"}" \
    --max-time 5 2>/dev/null || true
}

echo "timestamp_utc,hostname,profile,sample,health_ok,health_raw,slot,block_height,transaction_count,error" > "$OUT_DIR/rpc_metrics.csv"
echo "timestamp_utc,engine,raw" > "$OUT_DIR/container_stats.csv"

SAMPLES=$(( DURATION_SECONDS / INTERVAL_SECONDS ))
if [ "$SAMPLES" -lt 1 ]; then
  SAMPLES=1
fi

for i in $(seq 1 "$SAMPLES"); do
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ERROR=""

  HEALTH_RAW="$(rpc_call getHealth)"
  SLOT_RAW="$(rpc_call getSlot)"
  HEIGHT_RAW="$(rpc_call getBlockHeight)"
  TX_RAW="$(rpc_call getTransactionCount)"

  HEALTH_RESULT="$(json_field "$HEALTH_RAW" result)"
  SLOT="$(json_field "$SLOT_RAW" result)"
  BLOCK_HEIGHT="$(json_field "$HEIGHT_RAW" result)"
  TX_COUNT="$(json_field "$TX_RAW" result)"

  if [ "$HEALTH_RESULT" = "ok" ]; then
    HEALTH_OK="true"
  else
    HEALTH_OK="false"
    ERROR="health_not_ok"
  fi

  echo "$NOW,$HOST,$PROFILE,$i,$HEALTH_OK,\"$HEALTH_RESULT\",$SLOT,$BLOCK_HEIGHT,$TX_COUNT,\"$ERROR\"" >> "$OUT_DIR/rpc_metrics.csv"

  if command -v podman >/dev/null 2>&1; then
    podman stats --no-stream --format "{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.NetIO}} {{.BlockIO}}" 2>/dev/null \
      | sed "s/^/$NOW,podman,\"/; s/$/\"/" >> "$OUT_DIR/container_stats.csv" || true
  elif command -v docker >/dev/null 2>&1; then
    docker stats --no-stream --format "{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.NetIO}} {{.BlockIO}}" 2>/dev/null \
      | sed "s/^/$NOW,docker,\"/; s/$/\"/" >> "$OUT_DIR/container_stats.csv" || true
  fi

  if [ -n "$PROM_URL" ]; then
    curl -sS "$PROM_URL" --max-time 5 > "$OUT_DIR/prometheus-scrapes/${NOW}.prom" 2>/dev/null || true
  fi

  sleep "$INTERVAL_SECONDS"
done

if command -v podman >/dev/null 2>&1; then
  podman ps --format "{{.Names}}" | grep -Ei "validator|solana" | while read -r c; do
    podman logs "$c" > "$OUT_DIR/logs/${c}.log" 2>&1 || true
  done
  podman ps --format "{{.Names}}" | grep -Ei "monitor|geyser|yellowstone|prometheus" | while read -r c; do
    podman logs "$c" > "$OUT_DIR/logs/${c}.log" 2>&1 || true
  done
elif command -v docker >/dev/null 2>&1; then
  docker ps --format "{{.Names}}" | grep -Ei "validator|solana" | while read -r c; do
    docker logs "$c" > "$OUT_DIR/logs/${c}.log" 2>&1 || true
  done
  docker ps --format "{{.Names}}" | grep -Ei "monitor|geyser|yellowstone|prometheus" | while read -r c; do
    docker logs "$c" > "$OUT_DIR/logs/${c}.log" 2>&1 || true
  done
fi

find "$OUT_DIR" -type f -exec sha256sum {} \; | sort > "$OUT_DIR/SHA256SUMS.txt"

echo "[OK] Dataset run collected:"
echo "$OUT_DIR"
echo
echo "[NEXT] Create archive with:"
echo "tar -czf ${RUN_ID}.tar.gz -C data/article-runs ${RUN_ID}"

