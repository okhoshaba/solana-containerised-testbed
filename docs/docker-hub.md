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
