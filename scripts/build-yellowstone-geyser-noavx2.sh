#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

YELLOWSTONE_REPO="${YELLOWSTONE_REPO:-https://github.com/rpcpool/yellowstone-grpc-gamma.git}"
YELLOWSTONE_REF="${YELLOWSTONE_REF:-v1.18-gamma}"
SOLANA_BASE_IMAGE="${SOLANA_BASE_IMAGE:-docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge}"
CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
IMAGE_TAG="${IMAGE_TAG:-localhost/solana-localnet-validator:v1.18.25-noavx2-yellowstone}"

echo "Building Yellowstone/Geyser validator image"
echo "  YELLOWSTONE_REPO=$YELLOWSTONE_REPO"
echo "  YELLOWSTONE_REF=$YELLOWSTONE_REF"
echo "  SOLANA_BASE_IMAGE=$SOLANA_BASE_IMAGE"
echo "  CARGO_BUILD_JOBS=$CARGO_BUILD_JOBS"
echo "  IMAGE_TAG=$IMAGE_TAG"

podman build --format docker   --build-arg YELLOWSTONE_REPO="$YELLOWSTONE_REPO"   --build-arg YELLOWSTONE_REF="$YELLOWSTONE_REF"   --build-arg SOLANA_BASE_IMAGE="$SOLANA_BASE_IMAGE"   --build-arg CARGO_BUILD_JOBS="$CARGO_BUILD_JOBS"   -t "$IMAGE_TAG"   -f validator/Dockerfile.geyser-noavx2   validator

echo
echo "Built: $IMAGE_TAG"
