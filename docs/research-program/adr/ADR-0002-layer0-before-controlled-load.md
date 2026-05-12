# ADR-0002: Complete Dataset Layer 0 Before Controlled Load

## Status

Accepted

## Context

The project already has a controlled load business process, including load generation, dashboarding, and CSV analysis.

However, controlled load datasets depend on a trustworthy observability pipeline.

## Decision

Dataset layer 0 will be created before integrating the controlled load workflow.

## Consequences

The controlled load workflow will be introduced only after the observability core is validated.
