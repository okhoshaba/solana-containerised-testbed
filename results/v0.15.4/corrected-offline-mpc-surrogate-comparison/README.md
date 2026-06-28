# v0.15.4 corrected offline MPC surrogate comparison

## Purpose

This stage reruns MPC-vs-baseline comparison after correcting surrogate/comparability defects from v0.15.3.

It is offline-only and does not claim live-controller readiness.

## Baseline

- Candidate: p_kp0.350_ki0.000_kd0.000
- Effective controller: p_only
- Corrected baseline comparison RMSE: 0.11336075773667269

## Correction validation

- Correction checks passed: 7
- Correction checks failed: 0
- Explicit delay steps: 1

## Selected corrected MPC candidate

- Candidate: mpc_skeleton_ph05_ch03_q1.000_r0.010_du0.100_sc100.0
- Average comparison RMSE: 2.9098498380832325
- Comparison RMSE ratio vs baseline: 25.66893426067744
- Unexplained failures: 0
- Warnings: 1

## Decision

- Status: fail
- Corrected surrogate comparable: True
- Usable offline trade-off vs baseline: False

Reason: Corrected surrogate is comparable, but MPC candidates remain unsuitable against the fixed baseline.
