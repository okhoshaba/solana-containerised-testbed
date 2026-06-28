# v0.15.3 MPC failure diagnostics

## Purpose

This stage diagnoses why v0.15.2 produced a fail result.

It does not run a new MPC experiment and does not claim that MPC is generally unsuitable.

## v0.15.2 result under diagnosis

- Decision: fail
- Selected candidate: mpc_skeleton_ph05_ch01_q1.000_r0.010_du0.100_sc100.0
- Settled RMSE ratio vs baseline: 59.681614213125606
- Unexplained failures: 1
- Settled warnings: 3
- Baseline: p_kp0.350_ki0.000_kd0.000

## Diagnostic findings

- F001: v0.15.2 failure is a scientific negative result, not an execution failure (high)
- F002: Best MPC surrogate candidate is far worse than the fixed baseline (critical)
- F003: Multiple MPC candidates have identical metric signatures (high)
- F004: control_horizon is not active inside the MPC scoring loop (high)
- F005: v0.15.2 used delay_steps=0 while the simulator policy is delay-aware (medium)
- F006: sine-approx has very high target-change density (medium)
- F007: Case status distribution shows systemic surrogate weakness (medium)

## Severity count

- Critical findings: 1
- High findings: 3
- Total findings: 7

## Correction plan

- Step 1: Correct surrogate comparability before another MPC comparison.
- Step 2: Make control horizon operational.
- Step 3: Make objective weights identifiable.
- Step 4: Audit delay extraction.
- Step 5: Repair high-frequency target settled-metric interpretation.
- Step 6: Only after surrogate correction, rerun offline comparison.

## Decision

- Status: diagnostic_pass
- Ready for corrected surrogate stage: True

Reason: The v0.15.2 failure is diagnosed as a surrogate/comparability problem requiring correction before another MPC comparison.
