# v0.15.5 MPC line decision review

## Purpose

This stage records the decision to stop immediate MPC surrogate/weight tuning and proceed to a modular offline simulation platform.

## Decision

Proceed to v0.16.0 modular offline controller simulation platform.

## Reference controller

The v0.14.3 P-only controller is fixed as the current best offline reference controller on the current calibrated offline model.

## MPC line status

The current MPC surrogate/weighted policy line is not rejected, but deferred.

It became comparable to the v0.14.3 P-only reference controller, but did not demonstrate stable superiority sufficient to justify further immediate tuning.

## Rationale

A modular simulation platform is now more valuable than another controller-specific tuning iteration because it will allow strict MPC, PID variants, adaptive controllers, and heuristic policies to be evaluated under the same simulation engine, metrics, scenarios, and safety constraints.

## Next stage

v0.16.0 modular offline controller simulation platform.

