# ADR-0005: Separate Kubernetes, Single-Agent RL, and MARL

## Status

Accepted

## Context

One proposed structure placed single-agent RL inside the Kubernetes observability prompt.

This was rejected because Kubernetes is an infrastructure layer hosting the environment, while single-agent RL is a controller acting on the environment.

## Decision

The project will keep these concerns separate:

```text
Prompt 02 - Kubernetes observability core
Prompt 05 - MPC adaptive control
Prompt 06 - Single-agent RL
Prompt 07 - MARL
```

Kubernetes should be future-controller-ready, but it must not include a learning policy at the observability stage.

## Rationale

This preserves the sequence:

```text
observation -> controlled load -> model -> MPC -> single-agent RL -> MARL
```

## Consequences

- Dataset layer 0 remains a clean observability validation dataset.
- Kubernetes validates infrastructure portability.
- Dataset layer 1 captures controlled load response.
- MPC is introduced before RL as an interpretable baseline.
- Single-agent RL is separated from MARL.
- MARL remains a later extension.
