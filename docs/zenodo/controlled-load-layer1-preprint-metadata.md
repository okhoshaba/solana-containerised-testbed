# Zenodo Preprint Metadata Draft

## Record type

Preprint

## Working title

Controlled Load Layer 1 for the Solana Kubernetes Observability Core

## Creators

- Oleksandr Khoshaba
  - ORCID: to be confirmed
  - Affiliation: to be confirmed

## Abstract

This preprint describes Controlled Load Layer 1 for the Solana Containerised Testbed. The work extends a validated KVM-based multi-node Kubernetes observability baseline with controlled, reproducible transaction load generation.

The methodological sequence is:

```text
infrastructure -> observability -> controlled load
```

The implementation introduces a containerised transaction load generator, CSV collection tooling, Kubernetes manifests, PVC-backed result persistence, and validation procedures for local and in-cluster controlled-load execution.

The controlled-load layer was validated through a Kubernetes Deployment, ClusterIP Service, PVC, and Job running in the existing `solana-observability` namespace. A candidate Kubernetes run using load levels `1 2 4 8`, 60 seconds per level, and 5 second sampling demonstrated that the layer can control transaction submission through an in-cluster Service, collect telemetry, persist results, and return to a safe idle state.

The observed post-run state was:

```text
target_lambda: 0
sent_total: 1401
ok_total: 1401
err_total: 0
inflight: 0
last_err: ""
```

This stage is intentionally limited to controlled load generation and observability integration. It does not introduce MPC, reinforcement learning, MARL, adaptive policy learning, or Agave migration. The result is a reproducible experimental layer for later research into saturation analysis, control strategies, and high-load behaviour of Solana-oriented Kubernetes testbeds.

## Keywords

- Solana
- Kubernetes
- observability
- controlled load
- transaction load generation
- reproducible experiments
- KVM
- blockchain infrastructure
- containerised testbed
- distributed systems

## Related identifiers

### Software

- Title: Solana Containerised Testbed v0.5.0-controlled-load-layer1
- DOI: to be added after Zenodo Software publication

### Previous baseline

- Title: Solana Containerised Testbed v0.4.0
- DOI: to be added

### Repository

https://github.com/okhoshaba/solana-containerised-testbed

## Data availability

Candidate raw CSV:

```text
data/raw/controlled-load-layer1/20260617T223738Z/knee_step_candidate_20260617T223738Z.csv
```

Derived summary:

```text
results/controlled-load-layer1/20260617T223738Z/summary_by_level.csv
```

## Notes before publication

Before submitting the preprint record:

1. confirm the final software DOI;
2. confirm the previous v0.4.0 DOI;
3. confirm ORCID and affiliation;
4. convert the preprint outline into a full manuscript;
5. add the final software citation;
6. add the final repository release tag;
7. add figures or tables derived from `summary_by_level.csv`;
8. check that no private key material, kubeconfig, or runtime Secret data is included.
