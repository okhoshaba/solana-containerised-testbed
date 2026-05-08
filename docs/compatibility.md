# Compatibility

## Purpose

This project provides a containerised local Solana testbed for dataset generation and latency/performance research.

The first implementation target is a local single-machine Solana testbed based on:

    Solana Labs v1.18.25
    solana-test-validator
    Podman / Docker Compose

## CPU compatibility problem

Some prebuilt Solana binaries may fail on older x86_64 CPUs that do not support AVX2.

Typical symptoms:

    Illegal instruction
    Aborted
    solana-test-validator exited with code 139
    general protection fault

This was observed on:

    CPU: Intel Core i7-3667U
    Architecture: x86_64
    AVX: yes
    AVX2: no
    SSE4.1: yes
    SSE4.2: yes

The standard prebuilt Solana v1.18.25 binaries and the official solanalabs/solana:v1.18.25 container image are not suitable for this host.

## no-AVX2 source-built compatibility image

To support older x86_64 CPUs without AVX2, this repository provides a source-built compatibility image.

Local image name used during development:

    localhost/solana-source-noavx2:v1.18.25

Runtime images:

    localhost/solana-localnet-validator:v1.18.25-noavx2
    localhost/solana-wallet-init:v1.18.25-noavx2

## Important limitation

The current no-AVX2 image was built on an Ivy Bridge CPU using a native source build.

Therefore, until tested on more machines, it should be treated as:

    v1.18.25-noavx2-ivybridge

not as a universal image for every x86_64 system.

A more portable future build may use more conservative compiler settings and be published as:

    v1.18.25-noavx2-generic

## Recommended Docker Hub image tags

Recommended tags for publication:

    docker.io/khoshaba/solana-localnet-validator:v1.18.25-noavx2-ivybridge
    docker.io/khoshaba/solana-wallet-init:v1.18.25-noavx2-ivybridge
    docker.io/khoshaba/solana-source-noavx2:v1.18.25-noavx2-ivybridge

## Intended use

This compatibility image is intended for:

    local testbed
    dataset generation
    research experiments
    legacy x86_64 hardware
    controlled private Solana environment

It is not intended for production validator operation.
