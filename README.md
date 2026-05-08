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
