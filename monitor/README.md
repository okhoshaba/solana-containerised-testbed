# Solana Latency Monitor

Containerised Solana latency monitoring component for the Solana Containerised Testbed.

## Purpose

This component connects to a Solana validator through Yellowstone gRPC and exposes Prometheus-compatible metrics.

In the containerised testbed, the monitor is expected to connect to:

    validator:10000

and expose metrics on:

    0.0.0.0:9464

The host can access metrics through:

    http://127.0.0.1:9464/metrics

## Main goals

- Measure slot interval stability.
- Measure transaction broadcast-to-confirmation latency.
- Expose Prometheus metrics for later collection and visualisation.
- Support reproducible local testbed experiments.
- Integrate with the containerised Solana validator and wallet bootstrap services.

## Configuration

The container-oriented configuration is:

    configs/config.local.yaml

Expected Compose-network endpoints:

    rpc: http://validator:8899
    grpc: validator:10000

## Build

From the repository root:

    podman build --format docker \
      -t localhost/solana-latency-monitor:local \
      ./monitor

## Run through Compose

From the repository root:

    podman compose -f compose.yellowstone.yaml up validator wallet-init monitor

## Metrics check

After the monitor starts:

    curl -s http://127.0.0.1:9464/metrics | head -n 40

Expected metric names include:

    solana_slot_interval_seconds
    solana_transaction_latency_seconds
    solana_subscription_errors_total

## Notes

This monitor requires a validator image with Yellowstone/Geyser enabled.
The basic validator-only release does not provide a live gRPC endpoint on port 10000.

## License

See LICENSE.
