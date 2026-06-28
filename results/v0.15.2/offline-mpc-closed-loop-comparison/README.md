# v0.15.2 offline MPC closed-loop simulation comparison

## Purpose

This stage evaluates deterministic MPC skeleton candidates from v0.15.1 in offline closed-loop simulation.

It compares them against the fixed v0.14.3 P-only baseline.

This is not a live controller stage and it does not claim production readiness.

## Reference baseline

- Source stage: v0.14.3
- Candidate: p_kp0.350_ki0.000_kd0.000
- Effective controller: p_only
- Baseline average settled RMSE: 0.047925125701007314

## MPC candidates

- Candidate source: v0.15.1 deterministic MPC skeleton
- Candidate count: 12
- Profile count: 6
- Case count: 72

## Selected offline MPC candidate

- Candidate: mpc_skeleton_ph05_ch01_q1.000_r0.010_du0.100_sc100.0
- Prediction horizon: 5
- Control horizon: 1
- Average settled RMSE: 2.8602488632030694
- Settled RMSE ratio vs baseline: 59.681614213125606
- Average saturation fraction: 0.0
- Average rate-limit fraction: 0.0
- Unexplained failure count: 1
- Settled warning count: 3

## Decision

- Status: fail
- Usable offline trade-off vs baseline: False

Reason: MPC candidates are not yet suitable as baseline competitors under the offline comparison policy.

## Interpretation

This stage provides an offline comparison only. It should be interpreted as evidence for or against continuing MPC development, not as proof of live-controller safety or production superiority.
