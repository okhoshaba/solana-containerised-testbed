# v0.11.0 offline controller safety checks

## Purpose

This file reports conservative offline pass/warn/fail safety checks for the v0.11.0 controller profile-coverage simulations.

These checks are offline-only.

They are not a live Kubernetes safety supervisor and do not justify live closed-loop control by themselves.

## Overall result

- overall_status: WARN
- PASS: 14
- WARN: 1
- FAIL: 0

## WARN case

The only WARN case is:

- profile: lower-range
- controller_case: p
- reason: saturation_fraction > 0.20
- observed saturation_fraction: 0.25

## Interpretation

The result does not reject the offline controller simulator.

No controller-profile case triggered a FAIL condition.

The WARN case is methodologically useful: it shows that the P-only controller can achieve strong tracking metrics while still spending a non-trivial fraction of time at the configured safety bounds on the lower-range profile.

Therefore, the P-only controller remains a strong offline candidate by tracking performance, but it should not be treated as live-control ready without additional saturation-aware validation.

The safety checker should be interpreted as an offline screening tool, not as a runtime protection mechanism.
