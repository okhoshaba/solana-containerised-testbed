# Yellowstone / Geyser Integration Plan

## Goal

Integrate Yellowstone gRPC Geyser plugin into the local Solana v1.18.25 validator container.

The expected final architecture is:

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

Not yet implemented:

    Yellowstone plugin library
    validator image with libyellowstone_grpc_geyser.so
    ENABLE_GEYSER=true runtime path
    live monitor subscription through validator:10000

## Compatibility constraints

The current Solana validator version is:

    Solana v1.18.25

The host compatibility target is:

    legacy x86_64 without AVX2
    validated on Intel Core i7-3667U

Therefore, the Yellowstone plugin should be built with CPU compatibility in mind.

The plugin version must be compatible with Solana 1.18.x.

## Candidate Yellowstone sources

Primary repository:

    https://github.com/rpcpool/yellowstone-grpc

Candidate legacy branch / fork for Solana 1.18.x compatibility:

    https://github.com/rpcpool/yellowstone-grpc-gamma
    branch: v1.18-gamma

## Integration steps

1. Identify a Yellowstone version compatible with Solana v1.18.x.
2. Build libyellowstone_grpc_geyser.so.
3. Prefer source build with no-AVX2 flags.
4. Copy libyellowstone_grpc_geyser.so into validator image.
5. Update yellowstone-geyser.json.template.
6. Enable ENABLE_GEYSER=true.
7. Start validator with --geyser-plugin-config.
8. Confirm that port 10000 is listening.
9. Confirm monitor connects to validator:10000.
10. Confirm /metrics exposes live subscription data.

## Success criteria

Validator logs show that the Geyser plugin was loaded.

    podman logs solana-localnet-validator | grep -i geyser

Port 10000 is listening inside validator container.

    podman exec -it solana-localnet-validator ss -ltnp | grep 10000

Monitor logs show successful connection.

    podman logs solana-latency-monitor

Prometheus metrics endpoint is available.

    curl -s http://127.0.0.1:9464/metrics | head -n 40

## Risks

- Yellowstone plugin ABI mismatch with Solana v1.18.25.
- Prebuilt Yellowstone binaries may require AVX2.
- Source build may be long and memory-intensive.
- Yellowstone license must be reviewed before publishing a derived image.
- Monitor may need config adjustment after the plugin is enabled.

