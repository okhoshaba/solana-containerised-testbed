# ADR-0004: Treat Agave as a Separate Research Branch

## Status

Accepted

## Context

The current baseline is Solana v1.18.25 with a no-AVX2 compatibility image.

Agave has different release dynamics and operational assumptions.

## Decision

Agave will be treated as a separate research branch and not introduced into the current baseline until the observability and controlled-load layers are established.

## Consequences

This reduces risk and preserves comparability between the current Solana baseline and future Agave experiments.
