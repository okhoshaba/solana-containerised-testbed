#!/usr/bin/env bash
set -euo pipefail

# Update private prompts and public research-program docs
# to the accepted modified first variant:
# Kubernetes is environment-only, MPC, single-agent RL and MARL are separate.

if [ ! -d ".git" ]; then
  echo "ERROR: run from repository root"
  exit 1
fi

BACKUP_DIR=".local-backup/research-prompts-v2-$(date +%Y%m%d-%H%M%S)"
mkdir -p .local-prompts docs/research-program/adr scripts "$BACKUP_DIR"

backup_if_exists() {
  local f="$1"
  if [ -f "$f" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$f")"
    cp "$f" "$BACKUP_DIR/$f"
  fi
}

write_file() {
  local f="$1"
  backup_if_exists "$f"
  mkdir -p "$(dirname "$f")"
  cat > "$f"
  echo "Wrote $f"
}

grep -qxF ".local-prompts/" .gitignore 2>/dev/null || {
  printf "\n# Private local prompt packs\n.local-prompts/\n" >> .gitignore
  echo "Added .local-prompts/ to .gitignore"
}

write_file ".local-prompts/00-master-context.md" <<'EOF'
# Private Prompt 00 - Master Project Context

Use this prompt when starting a new chat about the Solana Containerised Testbed.

Respond in Russian unless English is explicitly requested. Public repository documentation should normally be written in English.

Repository: https://github.com/okhoshaba/solana-containerised-testbed

Identifiers:
- Software concept DOI: 10.5281/zenodo.20095383
- Software v0.1.x DOI: 10.5281/zenodo.20095384
- Software v0.2.0 DOI: 10.5281/zenodo.20132465
- Technical report DOI: 10.5281/zenodo.20098291

Current baseline:
- Solana Containerised Testbed v0.2.0
- Solana v1.18.25 local validator
- no-AVX2 compatibility build
- Yellowstone/Geyser-enabled validator
- containerised latency monitor
- RPC on 127.0.0.1:8899
- Geyser gRPC on 127.0.0.1:10000
- metrics on 127.0.0.1:9464

Accepted roadmap:
1. Observability Core.
2. Dataset layer 0: observability validation.
3. Kubernetes deployment of the observability core.
4. Dataset layer 1: controlled load response.
5. MPC adaptive control.
6. Single-agent RL.
7. MARL.
8. Agave research branch.

Important decisions:
- Do not move directly to MARL.
- Do not put single-agent RL into Kubernetes observability work.
- Kubernetes hosts the environment; it is not the agent.
- Single-agent RL appears after Dataset layer 1 and after an MPC baseline.
- MARL is a later extension after single-agent RL.
- Agave is a separate research branch.

Methodological chain:
observation -> controlled load -> model -> MPC -> single-agent RL -> MARL
EOF

write_file ".local-prompts/01-dataset-layer0-observability.md" <<'EOF'
# Private Prompt 01 - Dataset Layer 0 Observability

Goal:
Create a reproducible observability validation dataset proving that:

validator + Yellowstone/Geyser + monitor + Prometheus metrics

works correctly and reproducibly.

This is not a throughput benchmark and not a controlled-load dataset.

Do not introduce loadgen, dashboard, Kubernetes, MPC, RL, MARL or Agave.

Runtime:
- compose.yellowstone.release.yaml
- RPC: http://127.0.0.1:8899
- Metrics: http://127.0.0.1:9464/metrics
- Geyser gRPC: validator:10000 inside Compose

Output:
output/datasets/layer0-observability/<run_id>/
  metadata.json
  samples.csv
  samples.jsonl
  raw-metrics.prom

Candidate fields:
timestamp_utc, run_id, host_id, cpu_model, avx2_present, git_commit, testbed_version,
validator_image, monitor_image, validator_health, payer_balance_sol, metrics_scrape_ok,
slot_interval_p50, slot_interval_p90, slot_interval_p99, slot_interval_sum, slot_interval_count,
transaction_latency_p50, transaction_latency_p95, transaction_latency_p99,
transaction_latency_sum, transaction_latency_count, subscription_errors_total.

Default run:
DURATION=60
SAMPLE_INTERVAL=2
EOF

write_file ".local-prompts/02-kubernetes-observability-core.md" <<'EOF'
# Private Prompt 02 - Kubernetes Observability Core

Goal:
Move only the Level 1 observability core to Kubernetes.

This prompt is about the object/environment, not about an RL agent.

Include:
- validator with Yellowstone/Geyser enabled
- wallet-init job
- monitor
- PVC for validator ledger
- Service for RPC 8899
- Service for gRPC 10000
- Service for metrics 9464

Do not include loadgen, dashboard, MPC, single-agent RL, MARL or Agave.

Kubernetes should be future-controller-ready, but it must not include a learning policy at this stage.

Future-controller-ready means:
stable service names, explicit RPC/gRPC/metrics endpoints, resettable validator state,
reproducible run IDs, configurable resource limits, and later actuator interfaces.

Suggested structure:
k8s/base and k8s/overlays/local-single-node, kind, minikube.
EOF

write_file ".local-prompts/03-controlled-load-layer1.md" <<'EOF'
# Private Prompt 03 - Dataset Layer 1 Controlled Load Response

Goal:
Containerise and document the existing controlled load business process.

This layer comes after Dataset layer 0 and Kubernetes observability core.

Existing workflow:
- loadgen2_bin
- knee_step_test.sh
- knee_probe_adaptive.sh
- mpc_dashboard_v2.py
- CSV output and analysis scripts

Do not commit payer.json or private keys.
Do not introduce MPC/RL/MARL yet.

Candidate fields:
timestamp_utc, experiment_id, phase, level_index, lambda_target, workers, burst,
inflight, sample, duration_seconds, submitted_tps, accepted_tps, error_rate,
saturation_score, slot_interval_p50/p90/p99, tx_latency_p50/p95/p99,
subscription_errors_total, validator_health, controller_mode.
EOF

write_file ".local-prompts/04-agave-research-branch.md" <<'EOF'
# Private Prompt 04 - Agave Research Branch

Goal:
Plan a separate Agave research branch.

Do not mix Agave into the current Solana v1.18.25 testbed too early.

Agave should be treated as:
- a separate object of research
- a separate branch or later version line
- likely Kubernetes-oriented
- not a simple replacement of solana-test-validator

Define exact Agave version, compatible Geyser/Yellowstone path, topology, resources, observability model, and comparison baseline.
EOF

write_file ".local-prompts/05-mpc-adaptive-control.md" <<'EOF'
# Private Prompt 05 - MPC Adaptive Control

Goal:
Develop adaptive transaction-load control based on Model Predictive Control.

This comes after Dataset layer 1 controlled load response.

Do not introduce RL/MARL before defining an MPC baseline.

MPC requires measurable state, controllable input, dynamic model, constraints, horizon, and objective.

Candidate state:
latency quantiles, slot interval stats, error rate, submitted/accepted throughput,
inflight transactions, subscription errors, previous action, saturation score.

Candidate actions:
lambda adjustment, workers adjustment, inflight adjustment, burst adjustment, backoff policy.

Objective:
Maximize accepted throughput subject to latency, error, slot stability, health and saturation constraints.
EOF

write_file ".local-prompts/06-single-agent-rl.md" <<'EOF'
# Private Prompt 06 - Single-Agent RL

Goal:
Formulate and evaluate a single-agent RL controller for adaptive transaction-load control.

This comes after Dataset layer 1 and after an MPC baseline.

Kubernetes hosts the environment; the RL policy is a controller interacting with the environment.

Define state, action, reward, episode, reset procedure, safety constraints, and baselines.

Required baselines:
- static load profile
- knee probe adaptive script
- MPC controller
EOF

write_file ".local-prompts/07-marl-long-term.md" <<'EOF'
# Private Prompt 07 - MARL Long-Term Extension

Goal:
Plan a multi-agent RL extension after single-agent RL has been evaluated.

MARL is not the immediate next step.

Potential agents:
- load rate controller
- inflight/backpressure controller
- routing/controller agent
- observer/validator-state agent

Research questions:
coordination vs competition, local vs shared observations, global vs local rewards,
safety constraints, communication topology, policy stability near overload.
EOF

rm -f .local-prompts/05-mpc-rl-marl.md

write_file "docs/research-program/README.md" <<'EOF'
# Research Program

This directory documents the research roadmap built around the Solana Containerised Testbed.

## Baseline

- Solana Containerised Testbed v0.2.0
- Solana v1.18.25 local validator
- no-AVX2 compatibility build
- Yellowstone/Geyser-enabled validator image
- containerised Solana latency monitor
- Prometheus metrics endpoint

## Identifiers

- Software concept DOI: https://doi.org/10.5281/zenodo.20095383
- Software v0.2.0 DOI: https://doi.org/10.5281/zenodo.20132465
- Technical report DOI: https://doi.org/10.5281/zenodo.20098291

## Accepted roadmap

1. Observability Core
2. Dataset layer 0: observability validation
3. Kubernetes deployment of the observability core
4. Dataset layer 1: controlled load response
5. MPC adaptive control
6. Single-agent RL
7. MARL
8. Agave research branch

Each layer must be independently reproducible before moving to the next layer.
EOF

write_file "docs/research-program/01-research-roadmap.md" <<'EOF'
# Research Roadmap

## Level 1: Observability Core

The first level establishes:

```text
validator + Yellowstone/Geyser + monitor + Prometheus metrics
```

## Dataset layer 0

Dataset layer 0 validates observability. It is not a throughput benchmark.

## Kubernetes Observability Core

Kubernetes should initially deploy only the same observability core:

- validator
- wallet-init job
- monitor
- services
- PVC

It should not include loadgen, dashboard, MPC, single-agent RL, MARL or Agave.

Kubernetes should be future-controller-ready, but it is not the controller and not the learning policy.

## Dataset layer 1

Dataset layer 1 introduces controlled load and response measurement.

## MPC

MPC comes after Dataset layer 1, when controlled response data exists.

## Single-Agent RL

Single-agent RL comes after Dataset layer 1 and after an MPC baseline.

## MARL

MARL is a later extension after single-agent RL.

## Agave

Agave is a separate research branch.
EOF

write_file "docs/research-program/03-kubernetes-observability-core.md" <<'EOF'
# Kubernetes Observability Core

## Goal

Move the Level 1 observability core to Kubernetes without introducing load generation or adaptive control.

## Boundary

This stage is about the object/environment, not about an RL agent.

Kubernetes hosts the environment. It is not the controller and not the learning policy.

## Included

- validator with Yellowstone/Geyser enabled
- wallet-init job
- monitor
- PVC for validator ledger
- service for RPC
- service for gRPC
- service for metrics

## Excluded

- loadgen
- dashboard
- MPC
- single-agent RL
- MARL
- Agave

## Future-controller-ready requirements

The environment should provide stable service names, explicit RPC/gRPC/metrics endpoints,
resettable validator state, reproducible run IDs, configurable resource limits, and later actuator interfaces.
EOF

write_file "docs/research-program/05-mpc-adaptive-control.md" <<'EOF'
# MPC Adaptive Control

## Goal

Develop adaptive transaction-load control using Model Predictive Control.

## Position

MPC comes after Dataset layer 1 controlled load response.

## Required elements

- measurable state
- controllable action/input
- dynamic model
- constraints
- prediction horizon
- objective function

## Candidate state

```text
recent latency quantiles
slot interval statistics
error rate
submitted throughput
accepted throughput
inflight transactions
subscription errors
previous action
saturation score
```

## Candidate actions

```text
lambda adjustment
workers adjustment
inflight adjustment
burst adjustment
backoff policy
```

## Candidate objective

```text
Maximize accepted throughput
subject to:
  latency <= threshold
  error rate <= threshold
  slot stability >= threshold
  validator health == ok
  no sustained saturation
```
EOF

write_file "docs/research-program/06-single-agent-rl.md" <<'EOF'
# Single-Agent Reinforcement Learning

## Goal

Formulate and evaluate a single-agent RL controller for adaptive transaction-load control.

## Position

Single-agent RL comes after Dataset layer 1 and after an MPC baseline.

It does not belong to the Kubernetes observability core stage.

## Requirements

- defined environment
- defined action space
- defined reward
- reset procedure
- safety constraints
- baseline controllers

## Required baselines

- static load profile
- knee probe adaptive script
- MPC controller
EOF

write_file "docs/research-program/07-marl-extension.md" <<'EOF'
# MARL Extension

## Goal

Plan a multi-agent reinforcement learning extension after single-agent RL has been formulated and evaluated.

MARL should not be the immediate next step.

## Potential agent roles

- load rate controller
- inflight/backpressure controller
- routing/controller agent
- observer/validator-state agent

## Research questions

- coordination vs competition
- shared vs local observations
- global reward vs local rewards
- safety constraints
- communication topology
- policy stability near overload boundary
EOF

rm -f docs/research-program/05-adaptive-control-mpc-rl-marl.md

write_file "docs/research-program/adr/ADR-0005-separate-kubernetes-single-agent-rl-and-marl.md" <<'EOF'
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
EOF

echo
echo "Updated prompts and public docs to the accepted modified first variant."
echo
echo "Private prompts: .local-prompts/ (ignored by Git)"
echo "Public docs: docs/research-program/"
echo
echo "Recommended checks:"
echo "  tree -L 2 .local-prompts docs/research-program"
echo "  git status --ignored --short | grep local-prompts || true"
echo
echo "Recommended commit:"
echo "  git add docs/research-program scripts/update-research-program-prompts-v2.sh .gitignore"
echo "  git commit -m \"Refine research roadmap prompt structure\""
echo "  git push"
