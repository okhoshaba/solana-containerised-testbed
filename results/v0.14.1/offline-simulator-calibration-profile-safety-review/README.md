# v0.14.1 offline simulator calibration and profile safety review

## Purpose

This stage reviews the v0.14.0 simulator-gate failure without modifying v0.14.0.

The purpose is to separate true unsafe behaviour from expected rate-limit-induced transient error after abrupt target changes.

## Important rule

v0.14.1 does not reclassify v0.14.0. The v0.14.0 result remains fail.

## Calibration policy

- transient_window_steps_after_target_change: `5`
- treat_rate_limited_target_change_as_explained_transient: `True`
- do_not_reclassify_v0_14_0: `True`
- actuator_applied: `False`

## Decision

- status: `caution`
- accepted calibrated metrics for follow-up: `True`
- reason: All v0.14.0 failures are explained as rate-limit-induced transients, but calibrated transient-aware metrics should be used in follow-up stages.

## Profile safety review

| profile | original fail | explained transient | unexplained fail | max target delta | max original error | max settled error | recommendation |
|---|---:|---:|---:|---:|---:|---:|---|
| multistep | 3 | 3 | 0 | 66.000000 | 52.469276 | 8.867557 | keep profile but evaluate with transient-aware and settling-window metrics |
| step64-96 | 0 | 0 | 0 | 32.000000 | 17.885902 | 2.416973 | profile passes calibrated review |
| step96-64 | 0 | 0 | 0 | 32.000000 | 17.847499 | 2.439426 | profile passes calibrated review |
| lower-range | 0 | 0 | 0 | 26.000000 | 11.847499 | 1.631927 | profile passes calibrated review |
| sine-approx | 0 | 0 | 0 | 3.754427 | 1.525656 | 0.051873 | profile passes calibrated review |
| hold-y-eq | 0 | 0 | 0 | 0.000000 | 0.070001 | 0.070001 | profile passes calibrated review |

## Interpretation

The v0.14.0 failing cases are concentrated in the multistep profile and are explained by a large target drop under actuator rate limiting.

Follow-up controller comparisons should report both full-window metrics and settling-window metrics.
