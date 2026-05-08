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
