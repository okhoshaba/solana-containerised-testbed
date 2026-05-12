# Current State: v0.2.0

## Implemented

Solana Containerised Testbed v0.2.0 provides:

- Solana v1.18.25 local test validator container
- no-AVX2 compatibility validator build
- wallet bootstrap container
- Yellowstone/Geyser-enabled validator image
- containerised Solana latency monitor
- Prometheus metrics endpoint on `127.0.0.1:9464`
- Solana JSON-RPC endpoint on `127.0.0.1:8899`
- Yellowstone/Geyser gRPC endpoint on `127.0.0.1:10000`
- Docker Hub images
- GitHub release and Zenodo archive

## Main Docker Hub images

```text
docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge-yellowstone
docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge
docker.io/khoshaba/solana-latency-monitor:v0.2.0
```

## Release workflow

Run:

```bash
podman compose -f compose.yellowstone.release.yaml up
```

Check validator health:

```bash
curl -s http://127.0.0.1:8899 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

Check metrics:

```bash
curl -s http://127.0.0.1:9464/metrics | head -n 40
```

## Scope

v0.2.0 closes the first engineering milestone: a reproducible local observability core.

It does not yet include:

- controlled load generator
- dashboard
- MPC controller
- Kubernetes manifests
- Agave deployment
- RL/MARL components
