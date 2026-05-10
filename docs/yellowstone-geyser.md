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
