#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="solana-containerised-testbed"

if [ ! -d ".git" ]; then
  echo "ERROR: Run this script from the root of the Git repository."
  exit 1
fi

CURRENT_DIR="$(basename "$(pwd)")"
if [ "$CURRENT_DIR" != "$REPO_NAME" ]; then
  echo "WARNING: current directory is '$CURRENT_DIR', expected '$REPO_NAME'."
fi

BACKUP_DIR=".local-backup/stage-a-$(date +%Y%m%d-%H%M%S)"

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

mkdir -p docs scripts

write_file "docs/compatibility.md" <<'EOF'
# Compatibility

## Purpose

This project provides a containerised local Solana testbed for dataset generation and latency/performance research.

The first implementation target is a local single-machine Solana testbed based on:

    Solana Labs v1.18.25
    solana-test-validator
    Podman / Docker Compose

## CPU compatibility problem

Some prebuilt Solana binaries may fail on older x86_64 CPUs that do not support AVX2.

Typical symptoms:

    Illegal instruction
    Aborted
    solana-test-validator exited with code 139
    general protection fault

This was observed on:

    CPU: Intel Core i7-3667U
    Architecture: x86_64
    AVX: yes
    AVX2: no
    SSE4.1: yes
    SSE4.2: yes

The standard prebuilt Solana v1.18.25 binaries and the official solanalabs/solana:v1.18.25 container image are not suitable for this host.

## no-AVX2 source-built compatibility image

To support older x86_64 CPUs without AVX2, this repository provides a source-built compatibility image.

Local image name used during development:

    localhost/solana-source-noavx2:v1.18.25

Runtime images:

    localhost/solana-localnet-validator:v1.18.25-noavx2
    localhost/solana-wallet-init:v1.18.25-noavx2

## Important limitation

The current no-AVX2 image was built on an Ivy Bridge CPU using a native source build.

Therefore, until tested on more machines, it should be treated as:

    v1.18.25-noavx2-ivybridge

not as a universal image for every x86_64 system.

A more portable future build may use more conservative compiler settings and be published as:

    v1.18.25-noavx2-generic

## Recommended Docker Hub image tags

Recommended tags for publication:

    docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge
    docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge
    docker.io/khoshaba/solana-source-noavx2:v1.18.25-noavx2-ivybridge

## Intended use

This compatibility image is intended for:

    local testbed
    dataset generation
    research experiments
    legacy x86_64 hardware
    controlled private Solana environment

It is not intended for production validator operation.
EOF

write_file "docs/troubleshooting.md" <<'EOF'
# Troubleshooting

## solana-test-validator exits with code 139

Exit code 139 usually means that the process terminated with a segmentation fault.

In this project, this may happen when the prebuilt Solana binaries are not compatible with the host CPU instruction set.

Typical symptoms:

    solana-test-validator exited with code 139
    Aborted
    Illegal instruction
    general protection fault

## Check host CPU features

Run:

    ./scripts/check-host-cpu.sh

The most important feature to check is:

    avx2

If avx2 is missing, standard prebuilt Solana validator binaries may fail.

## Confirmed legacy CPU example

The following CPU does not support AVX2:

    Intel Core i7-3667U

It supports:

    avx
    sse4_1
    sse4_2

but does not support:

    avx2

## Recommended solution for older CPUs

Use the source-built no-AVX2 compatibility image:

    localhost/solana-source-noavx2:v1.18.25

and runtime images:

    localhost/solana-localnet-validator:v1.18.25-noavx2
    localhost/solana-wallet-init:v1.18.25-noavx2

## Check that the validator is healthy

After starting the testbed, run:

    curl -s http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

Expected result:

    {"jsonrpc":"2.0","result":"ok","id":1}

## Check payer balance

Run:

    podman exec -it solana-localnet-validator \
      solana --url http://127.0.0.1:8899 \
      balance 6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb

Expected result after wallet-init:

    10000 SOL

## podman compose down says no configuration file found

This happens when the command is executed outside the repository directory.

Incorrect:

    cd ~
    podman compose down

Correct:

    cd ~/project/solana-containerised-testbed
    podman compose down

Alternatively, stop the container directly from any directory:

    podman stop solana-localnet-validator

## wallet-init says PAYER is not set

The wallet-init image has an entrypoint script that expects environment variables.

Correct direct invocation:

    podman run --rm -it \
      --network solana-containerised-testbed_default \
      -e SOLANA_URL=http://validator:8899 \
      -e PAYER=6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb \
      -e AIRDROP_SOL=10000 \
      localhost/solana-wallet-init:v1.18.25-noavx2

For manual CLI commands, override the entrypoint:

    podman run --rm -it \
      --network solana-containerised-testbed_default \
      --entrypoint /bin/bash \
      localhost/solana-wallet-init:v1.18.25-noavx2 \
      -c 'solana --url http://validator:8899 balance 6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb'
EOF

write_file "docs/test-matrix.md" <<'EOF'
# Test Matrix

This document records validation results across different machines.

## Required checks

For each machine, run:

    ./scripts/check-host-cpu.sh

Start the testbed:

    podman compose -f compose.release.yaml up

Check RPC health:

    curl -s http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

Check payer balance:

    podman exec -it solana-localnet-validator \
      solana --url http://127.0.0.1:8899 \
      balance 6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb

Expected payer balance:

    10000 SOL

## Results

| Machine | CPU | OS | Podman/Docker | AVX | AVX2 | Image tag | Health check | Payer balance | Result | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| think | Intel Core i7-3667U | Zorin / Ubuntu-based Linux | Podman | yes | no | v1.18.25-noavx2 | ok | 10000 SOL | pass | Source-built no-AVX2 image works |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
EOF

write_file "docs/docker-hub.md" <<'EOF'
# Docker Hub Publication

Docker Hub username:

    khoshaba

## Recommended repositories

    khoshaba/solana-localnet-validator
    khoshaba/solana-wallet-init
    khoshaba/solana-source-noavx2

## Recommended tag

    v1.18.25-noavx2-ivybridge

## Login

Use a Docker Hub access token rather than the main account password.

    podman login docker.io -u khoshaba

## Tag local images

Validator:

    podman tag \
      localhost/solana-localnet-validator:v1.18.25-noavx2 \
      docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge

Wallet init:

    podman tag \
      localhost/solana-wallet-init:v1.18.25-noavx2 \
      docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge

Base source-built image:

    podman tag \
      localhost/solana-source-noavx2:v1.18.25 \
      docker.io/khoshaba/solana-source-noavx2:v1.18.25-noavx2-ivybridge

## Push images

Validator:

    podman push docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge

Wallet init:

    podman push docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge

Base source-built image:

    podman push docker.io/khoshaba/solana-source-noavx2:v1.18.25-noavx2-ivybridge

## Pull test

After publishing, test pulling the images:

    podman pull docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge
    podman pull docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge
EOF

write_file "compose.release.yaml" <<'EOF'
services:
  validator:
    image: docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge
    container_name: solana-localnet-validator
    environment:
      LEDGER_PATH: /var/lib/solana/ledger
      RESET_LEDGER: "true"
      VALIDATOR_BIND_ADDRESS: 0.0.0.0
      RPC_PORT: "8899"
      ENABLE_GEYSER: "false"
      GEYSER_CONFIG: /etc/solana/yellowstone-geyser.json
    ports:
      - "127.0.0.1:8899:8899"
      - "127.0.0.1:10000:10000"
    volumes:
      - solana-ledger:/var/lib/solana/ledger
      - ./validator/yellowstone-geyser.json.template:/etc/solana/yellowstone-geyser.json:ro
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

volumes:
  solana-ledger:
EOF

write_file "CITATION.cff" <<'EOF'
cff-version: 1.2.0
title: "Solana Containerised Testbed"
message: "If you use this software, please cite it using the metadata from this file."
type: software
authors:
  - family-names: "Khoshaba"
    given-names: "TODO"
repository-code: "https://github.com/TODO/solana-containerised-testbed"
abstract: "A containerised local Solana testbed for dataset generation and latency/performance research, including a source-built no-AVX2 compatibility image for older x86_64 CPUs."
license: "Apache-2.0"
version: "0.1.0"
date-released: "2026-05-08"
keywords:
  - Solana
  - testbed
  - Docker
  - Podman
  - containerisation
  - no-AVX2
  - dataset generation
EOF

write_file ".zenodo.json" <<'EOF'
{
  "title": "Solana Containerised Testbed",
  "description": "A containerised local Solana testbed for dataset generation and latency/performance research, including a source-built no-AVX2 compatibility image for older x86_64 CPUs.",
  "creators": [
    {
      "name": "Khoshaba, TODO",
      "orcid": "0000-0000-0000-0000"
    }
  ],
  "license": "Apache-2.0",
  "keywords": [
    "Solana",
    "testbed",
    "Docker",
    "Podman",
    "containerisation",
    "dataset generation",
    "no-AVX2"
  ],
  "upload_type": "software",
  "version": "0.1.0"
}
EOF

write_file "README.md" <<'EOF'
# Solana Containerised Testbed

Containerised local Solana testbed for dataset generation and latency/performance research.

This repository implements the first stage of moving a VM-based Solana local testbed into a reproducible Podman/Docker Compose architecture.

## Current status

Implemented:

- local solana-test-validator container;
- one-shot wallet-init container;
- no-AVX2 source-built compatibility image for older x86_64 CPUs;
- local RPC access on 127.0.0.1:8899;
- local payer funding through solana airdrop.

Not yet implemented:

- Yellowstone/Geyser plugin runtime integration;
- solana-latency-research monitoring container;
- Docker Hub publication;
- Zenodo DOI release.

## Repository structure

    .
    ├── compose.yaml
    ├── compose.release.yaml
    ├── docs
    │   ├── architecture.md
    │   ├── compatibility.md
    │   ├── docker-hub.md
    │   ├── ports.md
    │   ├── reproducibility.md
    │   ├── test-matrix.md
    │   ├── troubleshooting.md
    │   └── zenodo.md
    ├── monitor
    ├── scripts
    ├── solana-source
    ├── validator
    └── wallet-init

## Local development images

    localhost/solana-source-noavx2:v1.18.25
    localhost/solana-localnet-validator:v1.18.25-noavx2
    localhost/solana-wallet-init:v1.18.25-noavx2

## Why no-AVX2?

Some older x86_64 CPUs do not support AVX2. On such machines, standard prebuilt Solana validator binaries may fail with:

    Illegal instruction
    Aborted
    exit code 139

For this reason, this repository includes a source-built no-AVX2 compatibility workflow.

See:

    docs/compatibility.md
    docs/troubleshooting.md

## Start local development testbed

Copy environment file:

    cp .env.example .env

Start validator and wallet bootstrap:

    podman compose up validator wallet-init

Check RPC health:

    curl -s http://127.0.0.1:8899 \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

Expected result:

    {"jsonrpc":"2.0","result":"ok","id":1}

Check payer balance:

    podman exec -it solana-localnet-validator \
      solana --url http://127.0.0.1:8899 \
      balance 6avCzMrjUDebRYtSoQ6GPQENjoxDaD2Udik8JzRnKbtb

Expected result:

    10000 SOL

## Stop testbed

Run this from the repository root:

    podman compose down

To remove the local ledger volume:

    podman compose down -v

## Release-mode usage

After Docker Hub publication, users should run:

    podman compose -f compose.release.yaml up

See:

    docs/docker-hub.md

## Citation

Citation metadata is provided in:

    CITATION.cff
    .zenodo.json

The first citable software release is planned as:

    v0.1.0

## License

See LICENSE.
EOF

echo
echo "Stage A repository cleanup completed."
echo
echo "Next commands:"
echo "  git status"
echo "  git diff"
echo
echo "IMPORTANT:"
echo "  Edit CITATION.cff and .zenodo.json before DOI release."
echo "  Replace TODO values with your real name, GitHub URL, and ORCID."
