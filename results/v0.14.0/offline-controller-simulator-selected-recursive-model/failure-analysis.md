# v0.14.0 failure analysis

## Summary

v0.14.0 successfully created and executed the first offline controller simulator using the v0.13.6 selected recursive plant model accepted by v0.13.7.

The stage result is fail.

This failure is not a script/runtime failure. It is a simulator-gate failure caused by configured safety thresholds.

## Failing profile

All failing cases occur in the multistep profile:

- multistep / feedforward
- multistep / p
- multistep / pi

The common failure reason is:

max_abs_error > fail_max_abs_error

## Root cause

The failure occurs around simulation step 35, where the target changes sharply:

104.0 -> 38.0

The configured actuator rate limit is:

max_step_change = 16.0

Because of this rate limit, the controller command cannot immediately move to the command required for the new lower target.

The resulting transient error reaches approximately 51-52 units, exceeding the configured threshold:

fail_max_abs_error = 48.0

## Interpretation

This is a useful negative result.

The selected recursive plant model can be used inside an offline simulation harness, but the first simulator gate shows that the current profile, safety, and controller configuration is too strict or insufficiently calibrated for large abrupt multistep drops.

The result should not be hidden by relaxing thresholds inside v0.14.0.

## Decision

v0.14.0 should be preserved as:

offline controller simulator created, result fail

## Recommended next stage

Create a follow-up calibration stage:

v0.14.1 offline simulator calibration and profile safety review

Candidate goals for v0.14.1:

- separate tracking error from rate-limit-induced transient error;
- introduce settling-window metrics;
- distinguish hard safety violations from expected transient response;
- review multistep profile severity;
- calibrate thresholds before PID/MPC comparison;
- keep actuator_applied = false.
