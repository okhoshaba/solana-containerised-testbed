#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="solana-containerised-testbed"

if [ ! -d ".git" ]; then
  echo "ERROR: run this script from the root of the Git repository."
  exit 1
fi

CURRENT_DIR="$(basename "$(pwd)")"
if [ "$CURRENT_DIR" != "$REPO_NAME" ]; then
  echo "WARNING: current directory is '$CURRENT_DIR', expected '$REPO_NAME'."
fi

BACKUP_DIR=".local-backup/yellowstone-$(date +%Y%m%d-%H%M%S)"

backup_file() {
  local file_path="$1"
  if [ -f "$file_path" ] && [ -s "$file_path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file_path")"
    cp "$file_path" "$BACKUP_DIR/$file_path"
    echo "Backed up: $file_path"
  fi
}

write_file() {
  local file_path="$1"
  backup_file "$file_path"
  mkdir -p "$(dirname "$file_path")"
  cat > "$file_path"
  echo "Wrote: $file_path"
}

mkdir -p docs validator scripts

write_file "docs/yellowstone-geyser.md" <<'EOF'
# Yellowstone / Geyser Integration

## Goal

Integrate Yellowstone gRPC Geyser plugin into the local Solana v1.18.25 validator container.

Expected architecture:

    validator container:
      solana-test-validator
      libyellowstone_grpc_geyser.so
      yellowstone-geyser.json
      gRPC endpoint on 0.0.0.0:10000

    monitor container:
      connects to validator:10000
      exposes Prometheus metrics on 0.0.0.0:9464

## Current status

Implemented:

    validator container
    wallet-init container
    monitor container
    Docker Hub images
    no-AVX2 Solana v1.18.25 build

Not yet implemented in main:

    Yellowstone plugin library inside validator image
    ENABLE_GEYSER=true release workflow
    live monitor subscription through validator:10000

## Compatibility constraints

Current Solana validator version:

    Solana v1.18.25

Primary legacy CPU target:

    Intel Core i7-3667U
    AVX: yes
    AVX2: no

Therefore, the Yellowstone plugin should be built with AVX2 disabled.

## Candidate source

Initial candidate:

    Repository: https://github.com/rpcpool/yellowstone-grpc-gamma
    Branch: v1.18-gamma

This branch is selected as an initial compatibility candidate for Solana 1.18.x.

## Build policy

The no-AVX2 build uses:

    RUSTFLAGS="-C target-cpu=x86-64 -C target-feature=-avx2"
    CFLAGS="-march=x86-64 -mno-avx2"
    CXXFLAGS="-march=x86-64 -mno-avx2"

The resulting image must still be validated on a no-AVX2 host.

## Files

    validator/Dockerfile.geyser-noavx2
    compose.yellowstone.yaml
    scripts/build-yellowstone-geyser-noavx2.sh
    scripts/test-yellowstone-geyser.sh

## Success criteria

Validator starts with Geyser enabled:

    podman logs solana-localnet-validator | grep -i geyser

Port 10000 is listening:

    podman exec -it solana-localnet-validator ss -ltnp | grep 10000

Monitor starts and exposes metrics:

    curl -s http://127.0.0.1:9464/metrics | head -n 40

Monitor logs do not continuously report connection refused for validator:10000.

## Risks

- Yellowstone plugin ABI mismatch with Solana v1.18.25.
- Build may fail if the selected branch is not compatible with the Rust/Solana dependency set.
- Prebuilt binaries are intentionally avoided for no-AVX2 compatibility.
- Source build may be long and memory-intensive.
- License and redistribution terms must be checked before publishing a derived image.
EOF

write_file "validator/Dockerfile.geyser-noavx2" <<'EOF'
FROM debian:bookworm AS yellowstone-builder

ARG YELLOWSTONE_REPO=https://github.com/rpcpool/yellowstone-grpc-gamma.git
ARG YELLOWSTONE_REF=v1.18-gamma
ARG CARGO_BUILD_JOBS=1

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/.cargo/bin:${PATH}"
ENV RUSTFLAGS="-C target-cpu=x86-64 -C target-feature=-avx2"
ENV CFLAGS="-march=x86-64 -mno-avx2"
ENV CXXFLAGS="-march=x86-64 -mno-avx2"
ENV CARGO_BUILD_JOBS=${CARGO_BUILD_JOBS}

RUN apt-get update     && apt-get install -y --no-install-recommends        ca-certificates curl git bash build-essential clang cmake pkg-config        libssl-dev libudev-dev libclang-dev llvm protobuf-compiler python3        bzip2 xz-utils perl m4 make     && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs     | bash -s -- -y --profile minimal

WORKDIR /src

RUN git clone --depth 1 --branch "${YELLOWSTONE_REF}" "${YELLOWSTONE_REPO}" /src/yellowstone-grpc

WORKDIR /src/yellowstone-grpc

RUN cargo build --release -p yellowstone-grpc-geyser

RUN test -f /src/yellowstone-grpc/target/release/libyellowstone_grpc_geyser.so     && ls -lh /src/yellowstone-grpc/target/release/libyellowstone_grpc_geyser.so

ARG SOLANA_BASE_IMAGE=docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge
FROM ${SOLANA_BASE_IMAGE}

USER root

RUN apt-get update     && apt-get install -y --no-install-recommends        ca-certificates libssl3 libgcc-s1 libstdc++6 procps iproute2     && rm -rf /var/lib/apt/lists/*

COPY --from=yellowstone-builder   /src/yellowstone-grpc/target/release/libyellowstone_grpc_geyser.so   /usr/local/lib/libyellowstone_grpc_geyser.so

COPY yellowstone-geyser.json.template /etc/solana/yellowstone-geyser.json

RUN ls -lh /usr/local/lib/libyellowstone_grpc_geyser.so     && ldd /usr/local/lib/libyellowstone_grpc_geyser.so || true

EXPOSE 8899 10000

ENTRYPOINT ["/usr/local/bin/validator-entrypoint.sh"]
EOF

write_file "compose.yellowstone.yaml" <<'EOF'
services:
  validator:
    image: localhost/solana-localnet-validator:v1.18.25-noavx2-yellowstone
    container_name: solana-localnet-validator
    environment:
      LEDGER_PATH: /var/lib/solana/ledger
      RESET_LEDGER: "true"
      VALIDATOR_BIND_ADDRESS: 0.0.0.0
      RPC_PORT: "8899"
      ENABLE_GEYSER: "true"
      GEYSER_CONFIG: /etc/solana/yellowstone-geyser.json
    ports:
      - "127.0.0.1:8899:8899"
      - "127.0.0.1:10000:10000"
    volumes:
      - solana-ledger:/var/lib/solana/ledger
    healthcheck:
      test: ["CMD-SHELL", "solana --url http://127.0.0.1:8899 cluster-version >/dev/null 2>&1"]
      interval: 5s
      timeout: 3s
      retries: 30
    restart: unless-stopped

  wallet-init:
    image: docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge
    container_name: solana-wallet-init
    depends_on:
      validator:
        condition: service_healthy
    environment:
      SOLANA_URL: http://validator:8899
      PAYER: 6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb
      AIRDROP_SOL: "10000"
    restart: "no"

  monitor:
    image: localhost/solana-latency-monitor:local
    build:
      context: ./monitor
    container_name: solana-latency-monitor
    depends_on:
      validator:
        condition: service_healthy
    command:
      - --config
      - /app/configs/config.local.yaml
    ports:
      - "127.0.0.1:9464:9464"
    volumes:
      - ./monitor/configs/config.local.yaml:/app/configs/config.local.yaml:ro
      - monitor-output:/app/output
    restart: unless-stopped

volumes:
  solana-ledger:
  monitor-output:
EOF

write_file "scripts/build-yellowstone-geyser-noavx2.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

YELLOWSTONE_REPO="${YELLOWSTONE_REPO:-https://github.com/rpcpool/yellowstone-grpc-gamma.git}"
YELLOWSTONE_REF="${YELLOWSTONE_REF:-v1.18-gamma}"
SOLANA_BASE_IMAGE="${SOLANA_BASE_IMAGE:-docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge}"
CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
IMAGE_TAG="${IMAGE_TAG:-localhost/solana-localnet-validator:v1.18.25-noavx2-yellowstone}"

echo "Building Yellowstone/Geyser validator image"
echo "  YELLOWSTONE_REPO=$YELLOWSTONE_REPO"
echo "  YELLOWSTONE_REF=$YELLOWSTONE_REF"
echo "  SOLANA_BASE_IMAGE=$SOLANA_BASE_IMAGE"
echo "  CARGO_BUILD_JOBS=$CARGO_BUILD_JOBS"
echo "  IMAGE_TAG=$IMAGE_TAG"

podman build --format docker --no-cache   --build-arg YELLOWSTONE_REPO="$YELLOWSTONE_REPO"   --build-arg YELLOWSTONE_REF="$YELLOWSTONE_REF"   --build-arg SOLANA_BASE_IMAGE="$SOLANA_BASE_IMAGE"   --build-arg CARGO_BUILD_JOBS="$CARGO_BUILD_JOBS"   -t "$IMAGE_TAG"   -f validator/Dockerfile.geyser-noavx2   validator

echo
echo "Built: $IMAGE_TAG"
EOF

write_file "scripts/test-yellowstone-geyser.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

podman compose -f compose.yellowstone.yaml down -v || true
podman rm -f solana-localnet-validator solana-wallet-init solana-latency-monitor 2>/dev/null || true

echo "Starting Yellowstone/Geyser testbed..."
podman compose -f compose.yellowstone.yaml up --build validator wallet-init monitor
EOF

chmod +x scripts/build-yellowstone-geyser-noavx2.sh
chmod +x scripts/test-yellowstone-geyser.sh

echo
echo "Yellowstone/Geyser no-AVX2 scaffold created."
echo
echo "Next commands:"
echo "  git status"
echo "  git add docs/yellowstone-geyser.md validator/Dockerfile.geyser-noavx2 compose.yellowstone.yaml scripts/build-yellowstone-geyser-noavx2.sh scripts/test-yellowstone-geyser.sh"
echo "  git commit -m "Add Yellowstone Geyser no-AVX2 build scaffold""
echo
echo "Build command:"
echo "  ./scripts/build-yellowstone-geyser-noavx2.sh"
