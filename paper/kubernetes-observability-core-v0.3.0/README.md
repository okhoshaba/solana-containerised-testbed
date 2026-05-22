# Kubernetes Observability Core Preprint

This directory contains the LaTeX source for the preprint:

```text
Kubernetes Observability Core for the Solana Containerised Testbed v0.3.0

Associated software release
Solana Containerised Testbed v0.3.0: Kubernetes Observability Core
DOI: 10.5281/zenodo.20337744

# Build

Recommended build command:
latexmk -pdf main.tex

Alternative manual build:
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
Expected output

The build should produce:

main.pdf

# Scope
This preprint documents the Kubernetes Observability Core migration and validation.

It covers:
validator StatefulSet;
validator ledger PersistentVolumeClaim;
wallet-init Job;
monitor Deployment;
RPC Service;
Yellowstone/Geyser gRPC Service;
metrics Service;
wallet transfer validation through the Kubernetes RPC endpoint.

It does not introduce:
load generation;
dashboard;
Prometheus/Grafana stack;
MPC controller;
single-agent reinforcement learning;
MARL;
Agave research branch.

## Zenodo preprint DOI

The published Zenodo preprint is:

```text
Khoshaba, O. (2026). Kubernetes Observability Core for the Solana Containerised Testbed v0.3.0 (0.3.0). Zenodo. https://doi.org/10.5281/zenodo.20340310
