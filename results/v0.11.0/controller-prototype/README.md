# v0.11.0 controller prototype results

## Purpose

This directory contains offline throughput-controller prototype results for the Solana Containerised Testbed research line.

The prototype is a dry-run simulator. It does not access Kubernetes and does not send commands to the live testbed.

## Source stage

This result directory belongs to:

    v0.11.0 throughput controller prototype

The stage starts from the merged v0.10.0 controller-preparation artefacts.

Relevant documents:

- `docs/experiments/v0.11.0-throughput-controller-prototype.md`
- `docs/experiments/v0.10.0-throughput-controller-preparation.md`
- `docs/experiments/v0.10.0-offline-controller-simulator-spec.md`

## Simulator

Implementation file:

- `scripts/v0.11.0/offline-throughput-controller-sim.py`

Current simulator capabilities:

- safe reference profiles;
- unity plant;
- first-order transition plant;
- command saturation;
- feed-forward baseline;
- P-only controller;
- PI controller;
- freeze anti-windup for PI mode;
- CSV trace output;
- JSON summary output.

## Plant model used for comparison

The main comparison uses the first-order transition plant:

    y[k+1] = a*y[k] + b*u_cmd[k]

with:

    a = 0.143846
    b = 0.856154

This model represents the first recorded post-transition behaviour from the v0.9.0 offline throughput modelling stage. It should not be interpreted as finely resolved sub-5-second dynamics.

## Safety bounds

All controller outputs are saturated before plant application:

    32 <= u_cmd[k] <= 128

The simulator records both:

- `u_raw[k]`
- `u_cmd[k]`

This makes saturation behaviour explicit.

## Reference profile

The main comparison uses:

    profile = multistep
    hold = 12

Reference sequence:

    64 -> 96 -> 128 -> 96 -> 64

## Controller comparison

### Feed-forward baseline

Command law:

    u_raw[k] = r[k]

Observed metrics:

    RMSE = 1.200998
    MAE = 0.358430
    saturation_count = 0

Interpretation:

The feed-forward baseline is safe and simple. It works because the settled plant is close to unity gain, but it does not compensate transition lag.

### P-only controller

Command law:

    e_feedback[k] = r[k] - y[k-1]
    u_raw[k] = r[k] + Kp * e_feedback[k]

Parameters:

    Kp = 0.10

Observed metrics:

    RMSE = 0.731300
    MAE = 0.188537
    saturation_count = 12

Interpretation:

The P-only controller improves tracking substantially compared with feed-forward control.

The saturation count is expected on the `r = 128` segment. Since the feed-forward term already reaches the upper safe bound, the proportional correction can temporarily request `u_raw > 128`, which is then correctly saturated to `u_cmd = 128`.

### PI controller with freeze anti-windup

Command law:

    e_feedback[k] = r[k] - y[k-1]
    I_candidate[k] = I[k-1] + Ts * e_feedback[k]

If the candidate command is outside the safe interval, the integral state is frozen.

Parameters:

    Kp = 0.10
    Ki = 0.002
    Ts = 1.0

Observed metrics:

    RMSE = 0.726439
    MAE = 0.204742
    saturation_count = 12
    anti_windup_freeze_count = 12
    final_error = 0.061743

Interpretation:

The conservative PI controller slightly improves RMSE compared with P-only, but worsens MAE.

The anti-windup freeze mechanism works as intended: it activates during the saturated `r = 128` segment and prevents further integral accumulation while the candidate command would exceed the safe range.

## Main conclusion

For the current offline transition model, the ranking is:

1. P-only is the best simple controller by MAE.
2. Conservative PI is acceptable as an anti-windup prototype, but not yet clearly superior.
3. Feed-forward remains the simplest safe baseline.

The current result does not justify live closed-loop Kubernetes control yet.

The next stage should continue offline testing, including broader reference profiles and automated controller comparison, before any live control experiment is considered.

## Files

Current files:

- `offline-controller-summary.json`
- `offline-controller-traces.csv`
- `README.md`

Important note:

The JSON and CSV files represent the most recent simulator run. At the time of this README, that run is the config-driven PI run:

    simulation_name = multistep-pi-transition-ts1
    controller = pi
    profile = config_piecewise_constant
    plant = transition
    sample_count = 60
    Kp = 0.10
    Ki = 0.002
    Ts = 1.0

This config-driven run is intentionally equivalent to the earlier CLI run:

    --profile multistep
    --plant transition
    --controller pi
    --kp 0.10
    --ki 0.002
    --ts 1.0
    --hold 12
