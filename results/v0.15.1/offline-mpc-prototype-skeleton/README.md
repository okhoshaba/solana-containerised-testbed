# v0.15.1 offline MPC prototype skeleton

## Purpose

This stage creates a minimal offline MPC prototype skeleton.

It does not run closed-loop MPC optimisation and does not claim that MPC is better than the v0.14.3 baseline.

## Reference baseline

- Source stage: v0.14.3
- Candidate: p_kp0.350_ki0.000_kd0.000
- Effective controller: p_only
- Role: fixed_reference_baseline_for_future_mpc_comparison

Future MPC simulation must compare against this fixed P-only baseline.

## Skeleton components

- Problem loader: True
- Baseline loader: True
- Candidate spec generator: True
- Objective placeholder: True
- Constraint placeholder: True
- Optimizer placeholder: True
- Closed-loop simulation: False
- Performance claim: False

## Candidate grid

- Candidate generation mode: deterministic_grid
- Candidate count: 12
- Prediction horizons: [5, 10, 15]
- Control horizons: [1, 3]
- Tracking error weights: [1.0]
- Control effort weights: [0.01, 0.05]
- Control delta weights: [0.1]
- Soft constraint weights: [100.0]

## Decision

- Status: ready_for_offline_mpc_simulation
- Ready for offline MPC simulation: True

Reason: The MPC prototype skeleton defines deterministic candidates, placeholders, constraints, and a fixed reference baseline for the next offline simulation stage.

## Next step

Proceed to v0.15.2 offline MPC closed-loop simulation comparison.
