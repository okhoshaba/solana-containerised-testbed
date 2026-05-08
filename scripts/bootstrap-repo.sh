#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="solana-containerised-testbed"

if [ ! -d ".git" ]; then
  echo "ERROR: Run this script from the root of the Git repository."
  exit 1
fi

CURRENT_DIR="$(basename "$(pwd)")"

if [ "$CURRENT_DIR" != "$REPO_NAME" ]; then
  echo "WARNING: Current directory is '$CURRENT_DIR', expected '$REPO_NAME'."
  echo "Continue only if this is intentional."
fi

BACKUP_DIR=".local-backup/$(date +%Y%m%d-%H%M%S)"

backup_file() {
  file_path="$1"

  if [ -f "$file_path" ] && [ -s "$file_path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file_path")"
    cp "$file_path" "$BACKUP_DIR/$file_path"
    echo "Backed up existing file: $file_path"
  fi
}

write_file() {
  file_path="$1"
  backup_file "$file_path"
  mkdir -p "$(dirname "$file_path")"
  cat > "$file_path"
  echo "Wrote: $file_path"
}

mkdir -p validator wallet-init monitor/configs docs scripts

write_file ".env.example" <<'EOF'
# Project
PROJECT_NAME=solana-containerised-testbed

# Solana Labs testbed version.
# v1.18.x is used intentionally for the first local testbed stage.
SOLANA_VERSION=v1.18.25

# Local container image names.
# For Podman local builds, localhost/... is a convenient local image namespace.
VALIDATOR_IMAGE=localhost/solana-localnet-validator:v1.18.25
WALLET_INIT_IMAGE=localhost/solana-wallet-init:v1.18.25
MONITOR_IMAGE=localhost/solana-latency-monitor:local

# Validator settings
LEDGER_PATH=/var/lib/solana/ledger
RESET_LEDGER=true
VALIDATOR_BIND_ADDRESS=0.0.0.0
RPC_PORT=8899

# Geyser / Yellowstone.
# Keep this false until the plugin shared library is actually added to the image.
ENABLE_GEYSER=false
GEYSER_CONFIG=/etc/solana/yellowstone-geyser.json
GEYSER_GRPC_PORT=10000

# Wallet bootstrap
PAYER=6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb
AIRDROP_SOL=10000

# Monitoring
METRICS_PORT=9464
EOF

write_file "compose.yaml" <<'EOF'
services:
  validator:
    image: ${VALIDATOR_IMAGE}
    build:
      context: ./validator
      args:
        SOLANA_VERSION: ${SOLANA_VERSION}
    container_name: solana-localnet-validator
    environment:
      LEDGER_PATH: ${LEDGER_PATH}
      RESET_LEDGER: ${RESET_LEDGER}
      VALIDATOR_BIND_ADDRESS: ${VALIDATOR_BIND_ADDRESS}
      RPC_PORT: ${RPC_PORT}
      ENABLE_GEYSER: ${ENABLE_GEYSER}
      GEYSER_CONFIG: ${GEYSER_CONFIG}
    ports:
      - "127.0.0.1:${RPC_PORT}:${RPC_PORT}"
      - "127.0.0.1:${GEYSER_GRPC_PORT}:${GEYSER_GRPC_PORT}"
    volumes:
      - solana-ledger:${LEDGER_PATH}
      - ./validator/yellowstone-geyser.json.template:${GEYSER_CONFIG}:ro
    healthcheck:
      test: ["CMD-SHELL", "solana --url http://127.0.0.1:${RPC_PORT} cluster-version >/dev/null 2>&1"]
      interval: 5s
      timeout: 3s
      retries: 30
    restart: unless-stopped

  wallet-init:
    image: ${WALLET_INIT_IMAGE}
    build:
      context: ./wallet-init
      args:
        SOLANA_VERSION: ${SOLANA_VERSION}
    container_name: solana-wallet-init
    depends_on:
      validator:
        condition: service_healthy
    environment:
      SOLANA_URL: http://validator:${RPC_PORT}
      PAYER: ${PAYER}
      AIRDROP_SOL: ${AIRDROP_SOL}
    restart: "no"

  monitor:
    image: ${MONITOR_IMAGE}
    build:
      context: ./monitor
    container_name: solana-latency-monitor
    profiles:
      - monitor
    depends_on:
      validator:
        condition: service_healthy
    environment:
      RPC_URL: http://validator:${RPC_PORT}
      GEYSER_GRPC_URL: http://validator:${GEYSER_GRPC_PORT}
      METRICS_PORT: ${METRICS_PORT}
    ports:
      - "127.0.0.1:${METRICS_PORT}:${METRICS_PORT}"
    volumes:
      - ./monitor/configs/config.local.yaml:/app/configs/config.local.yaml:ro
      - monitor-output:/app/output
    restart: unless-stopped

volumes:
  solana-ledger:
  monitor-output:
EOF

write_file "validator/Dockerfile" <<'EOF'
FROM debian:bookworm-slim

ARG SOLANA_VERSION=v1.18.25

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       bzip2 \
       bash \
       procps \
    && rm -rf /var/lib/apt/lists/*

RUN sh -c "$(curl -sSfL https://release.solana.com/${SOLANA_VERSION}/install)"

RUN solana --version && solana-test-validator --version

COPY entrypoint.sh /usr/local/bin/validator-entrypoint.sh
RUN chmod +x /usr/local/bin/validator-entrypoint.sh

EXPOSE 8899 10000

ENTRYPOINT ["/usr/local/bin/validator-entrypoint.sh"]
EOF

write_file "validator/entrypoint.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

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
EOF

write_file "validator/yellowstone-geyser.json.template" <<'EOF'
{
  "libpath": "/usr/local/lib/libyellowstone_grpc_geyser.so",
  "log": {
    "level": "info"
  },
  "grpc": {
    "address": "0.0.0.0:10000"
  }
}
EOF

write_file "wallet-init/Dockerfile" <<'EOF'
FROM debian:bookworm-slim

ARG SOLANA_VERSION=v1.18.25

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       bzip2 \
       bash \
    && rm -rf /var/lib/apt/lists/*

RUN sh -c "$(curl -sSfL https://release.solana.com/${SOLANA_VERSION}/install)"

RUN solana --version

COPY wallet-init.sh /usr/local/bin/wallet-init.sh
RUN chmod +x /usr/local/bin/wallet-init.sh

ENTRYPOINT ["/usr/local/bin/wallet-init.sh"]
EOF

write_file "wallet-init/wallet-init.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

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
EOF

write_file "monitor/Dockerfile" <<'EOF'
FROM golang:1.23-bookworm AS builder

WORKDIR /src

COPY . .

RUN if [ -f go.mod ]; then \
      go mod download && go build -o /out/solana-latency-monitor . ; \
    else \
      echo "monitor/go.mod not found. Add the monitoring source code later." && exit 1 ; \
    fi

FROM debian:bookworm-slim

WORKDIR /app

COPY --from=builder /out/solana-latency-monitor /usr/local/bin/solana-latency-monitor
COPY configs /app/configs

EXPOSE 9464

ENTRYPOINT ["solana-latency-monitor"]
CMD ["--config", "/app/configs/config.local.yaml"]
EOF

write_file "monitor/configs/config.local.yaml" <<'EOF'
rpc_url: "http://validator:8899"
geyser_grpc_url: "http://validator:10000"
metrics_address: "0.0.0.0:9464"
output_dir: "/app/output"
EOF

write_file "README.md" <<'EOF'
# solana-containerised-testbed

Containerised local Solana testbed for dataset generation and latency/performance research.

This repository is the first stage of moving an existing VM-based Solana local testbed into a reproducible Docker/Podman Compose architecture.

## Components

- `validator` - local `solana-test-validator`.
- `wallet-init` - one-shot bootstrap container for Solana CLI configuration and payer funding.
- `monitor` - placeholder for the Solana latency monitoring framework.

## First-stage goal

The first stage reproduces the original VM workflow:

1. Start `solana-test-validator`.
2. Configure Solana CLI and fund the payer wallet.
3. Prepare a place for the monitoring framework.
4. Expose local ports for controlled access.

## Quick start

Copy the example environment file:

```bash
cp .env.example .env
