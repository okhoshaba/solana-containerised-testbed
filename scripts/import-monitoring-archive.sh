#!/usr/bin/env bash
set -euo pipefail

# Import a working solana-latency-research archive into the monitor/ directory
# of solana-containerised-testbed.
#
# Usage:
#   ./scripts/import-monitoring-archive.sh /path/to/solana-latency-research-working.tar.gz
#
# The script:
#   - backs up the existing monitor/ directory;
#   - extracts the archive into a temporary directory;
#   - copies source files into monitor/ while excluding .git and runtime artifacts;
#   - creates a container-oriented monitor/Dockerfile;
#   - writes monitor/configs/config.local.yaml for Compose networking;
#   - patches Prometheus bind address from 127.0.0.1 to 0.0.0.0 if needed.

if [ $# -ne 1 ]; then
  echo "Usage: $0 /path/to/solana-latency-research-working.tar.gz"
  exit 1
fi

ARCHIVE_PATH="$1"
REPO_NAME="solana-containerised-testbed"

if [ ! -f "$ARCHIVE_PATH" ]; then
  echo "ERROR: archive does not exist: $ARCHIVE_PATH"
  exit 1
fi

if [ ! -d ".git" ]; then
  echo "ERROR: run this script from the root of the solana-containerised-testbed repository."
  exit 1
fi

CURRENT_DIR="$(basename "$(pwd)")"
if [ "$CURRENT_DIR" != "$REPO_NAME" ]; then
  echo "WARNING: current directory is '$CURRENT_DIR', expected '$REPO_NAME'."
fi

BACKUP_DIR=".local-backup/monitor-$(date +%Y%m%d-%H%M%S)"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Extracting archive: $ARCHIVE_PATH"
tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"

SRC_DIR="$(find "$TMP_DIR" -maxdepth 2 -type f -name go.mod -printf '%h\n' | head -n 1)"

if [ -z "${SRC_DIR:-}" ] || [ ! -d "$SRC_DIR" ]; then
  echo "ERROR: could not find Go module root with go.mod inside archive."
  exit 1
fi

echo "Detected monitor source directory: $SRC_DIR"

if [ -d "monitor" ]; then
  mkdir -p "$BACKUP_DIR"
  cp -a monitor "$BACKUP_DIR/"
  echo "Backed up existing monitor/ to $BACKUP_DIR/monitor"
fi

mkdir -p monitor

echo "Copying monitor source into monitor/ ..."
rsync -a --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.env' \
  --exclude 'ledger' \
  --exclude 'output' \
  --exclude '*.log' \
  "$SRC_DIR"/ monitor/

cat > monitor/Dockerfile <<'EOF'
FROM golang:1.24-bookworm AS builder

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/solana-latency-monitor .

FROM debian:bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/solana-latency-monitor /usr/local/bin/solana-latency-monitor
COPY configs /app/configs

EXPOSE 9464

ENTRYPOINT ["solana-latency-monitor"]
CMD ["--config", "/app/configs/config.local.yaml"]
EOF

mkdir -p monitor/configs

cat > monitor/configs/config.local.yaml <<'EOF'
# Container-oriented configuration for solana-containerised-testbed.
#
# RPC is available immediately when the validator container is running.
# Yellowstone gRPC on validator:10000 requires the Geyser/Yellowstone plugin
# to be integrated and enabled in the validator image.

rpc: http://validator:8899
grpc: validator:10000
interval: 5s
log_level: info

metrics:
  prometheus_port: 9464

filters:
  accounts:
    - "6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb"

reconnect:
  retries: -1
  backoff: 2s
EOF

if [ -f monitor/main.go ]; then
  python3 - <<'PY'
from pathlib import Path
p = Path("monitor/main.go")
s = p.read_text()
old = 'addr := fmt.Sprintf("127.0.0.1:%d", port)'
new = 'addr := fmt.Sprintf("0.0.0.0:%d", port)'
if old in s:
    p.write_text(s.replace(old, new))
    print("Patched monitor/main.go: Prometheus bind address 127.0.0.1 -> 0.0.0.0")
else:
    print("No Prometheus bind-address patch applied; expected pattern not found.")
PY
fi

echo
echo "Monitor import completed."
echo
echo "Next suggested commands:"
echo "  git status"
echo "  podman build --format docker --no-cache -t localhost/solana-latency-monitor:local ./monitor"
echo
echo "Important:"
echo "  The monitor requires Yellowstone gRPC at validator:10000."
echo "  Current validator release has ENABLE_GEYSER=false, so the monitor may build successfully"
echo "  but will not collect live gRPC data until Yellowstone/Geyser is integrated."
