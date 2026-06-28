# v0.15.0 MPC controller preparation

## Purpose

This stage prepares a formal offline MPC problem specification before implementing MPC or claiming MPC performance.

It is a preparation stage only.

## Non-goals

- It does not implement a production Kubernetes controller.
- It does not claim MPC superiority over the v0.14.3 baseline.
- It does not run live closed-loop experiments.
- It does not retune the v0.14.3 PID/P-only baseline.

## Reference baseline

- Source stage: v0.14.3
- Candidate: p_kp0.350_ki0.000_kd0.000
- Effective controller: p_only
- kp: 0.35
- ki: 0.0
- kd: 0.0
- Role: fixed_reference_baseline_before_mpc

Future MPC work must compare against this fixed baseline rather than a moving PID target.

## MPC problem formulation

- Controlled output: predicted_throughput_or_normalized_throughput
- Manipulated input: controller_command_or_load_control_signal
- State representation: derived_from_selected_recursive_plant_model

Prediction horizon candidates:

- [5, 10, 15, 20]

Control horizon candidates:

- [1, 2, 3, 5]

Objective terms:

- tracking_error_penalty
- control_effort_penalty
- control_delta_penalty
- soft_constraint_violation_penalty

Constraint classes:

- input_bounds
- input_rate_limits
- output_safety_bounds
- saturation_avoidance
- calibrated_transient_handling

## Offline validation protocol

Mode: preparation_only_no_mpc_performance_claim

Comparison principle:

Future MPC candidates must be compared against the fixed v0.14.3 P-only baseline using the same offline profiles where possible.

Required future metrics:

- full_rmse
- full_mae
- full_max_abs_error
- settled_rmse
- settled_mae
- settled_max_abs_error
- overshoot
- undershoot
- rate_limit_fraction
- saturation_fraction
- safety_classification
- recovery_behaviour_after_target_changes

## Decision

- Status: ready_for_offline_mpc_prototype
- Ready for offline MPC prototype: True

Reason: All preparation requirements are satisfied. The next stage may implement an offline MPC prototype without making live-system claims.

## Next step

Implement an offline MPC prototype stage that uses this specification and compares against the fixed v0.14.3 P-only baseline.
