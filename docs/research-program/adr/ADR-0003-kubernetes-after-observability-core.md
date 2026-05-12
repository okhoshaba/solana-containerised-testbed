# ADR-0003: Introduce Kubernetes After Observability Core Validation

## Status

Accepted

## Context

Kubernetes is a logical infrastructure target for the project, but it adds operational complexity.

## Decision

Kubernetes will be introduced after Dataset layer 0 validates the Compose-based observability core.

The initial Kubernetes deployment will include only:

- validator
- wallet-init job
- monitor
- services
- persistent volume

## Consequences

Kubernetes will validate infrastructure portability without mixing in controlled load or adaptive control complexity.
