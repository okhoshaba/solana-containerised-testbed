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
