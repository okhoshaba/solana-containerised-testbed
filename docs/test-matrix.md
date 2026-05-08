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

| think | Intel Core i7-3667U | Zorin / Ubuntu-based Linux | Podman | yes | no | docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge | ok | 10000 SOL | pass | Pulled from Docker Hub and started through compose.release.yaml |

