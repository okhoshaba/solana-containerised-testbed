# v0.14.0 offline controller simulator with selected recursive model

## Purpose

This stage creates an offline controller simulator using the v0.13.6 selected recursive model, accepted by v0.13.7 as the candidate surrogate plant model.

This is not a live Kubernetes or validator controller. No actuator is applied to a live system.

## Plant model

- source: `results/v0.13.6/recursive-plant-model-refit/selected-recursive-model.json`
- equation: `y[k+1] = c + a_y*y[k] + b_u*u[k-delay]`
- a_y: `0.10889615191767432`
- b_u: `0.8845312889194352`
- c: `0.0`
- delay_steps: `0`

## Controller cases

- `feedforward`: feedforward_inverse
- `p`: p_with_equilibrium_feedforward
- `pi`: pi_with_equilibrium_feedforward

## Profiles

- `hold-y-eq`: constant
- `step64-96`: step
- `step96-64`: step
- `multistep`: multistep
- `lower-range`: multistep
- `sine-approx`: sine

## Controller ranking

| rank | controller | cases | pass | warn | fail | avg RMSE | avg MAE | avg saturation | worst max error |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | feedforward | 6 | 5 | 0 | 1 | 2.211057 | 0.421360 | 0.000000 | 51.847499 |
| 2 | p | 6 | 5 | 0 | 1 | 2.299471 | 0.544765 | 0.000000 | 51.785095 |
| 3 | pi | 6 | 5 | 0 | 1 | 2.642426 | 1.176554 | 0.000000 | 52.469276 |

## Decision

- status: `fail`
- accepted as initial offline controller simulator: `False`
- reason: At least one simulated controller/profile case failed configured safety thresholds.
- recommended next step: Review controller-ranking.json and simulation-timeseries.csv, then create a follow-up calibration or PID/MPC comparison stage.

## Important limitation

This simulator uses a selected recursive surrogate plant model. It is suitable for offline controller preparation, not for direct live deployment.

## Failure analysis

Detailed failure analysis is recorded in:

results/v0.14.0/offline-controller-simulator-selected-recursive-model/failure-analysis.md

The v0.14.0 fail result is caused by the multistep profile's abrupt 104.0 -> 38.0 target drop under max_step_change = 16.0, producing a transient max absolute error above the configured fail threshold.
