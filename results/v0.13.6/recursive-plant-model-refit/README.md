# v0.13.6 recursive plant model refit results

This directory contains the offline-only recursive plant model refit and validation outputs for v0.13.6.

## Purpose

v0.13.6 addresses the gap discovered in v0.13.5: the v0.13.4 one-step fitted model had good one-step metrics but poor recursive/free-run shadow-mode behaviour.

The purpose of this stage is to select a plant model using recursive validation performance, not only one-step-ahead fit quality.

## Input

The replay input is:

    results/v0.13.2/real-replay-shadow-mode-validation/real-replay-shadow-timeseries.csv

The comparison baselines are:

    configs/v0.13.0/shadow-controller-replay.json
    results/v0.13.4/refit-throughput-model/refit-coefficients.json
    results/v0.13.5/shadow-mode-refit-comparison/comparison-summary.json

The selected replay columns are:

- time: `source_time_seconds`
- command input: `u_cmd_replay`
- observed output: `u_ach_replay`

## Model families

The script evaluates:

1. no-intercept model:

       y[k+1] = a_y*y[k] + b_u*u[k-delay]

2. intercept model:

       y[k+1] = c + a_y*y[k] + b_u*u[k-delay]

3. equilibrium-deviation model:

       y[k+1] - y_eq = a_y*(y[k] - y_eq) + b_u*(u[k-delay] - u_eq)

Candidate delays:

    0, 1, 2, 3, 4, 5, 10, 15, 20

## Train/validation split

The replay contains 78 valid rows.

The configured train fraction is 0.65:

- train rows: 50
- validation rows: 28

Model selection is based on validation recursive RMSE.

## Selected model

The selected model is:

- family: `no_intercept`
- `c = 0.0`
- `a_y = 0.10889615191767432`
- `b_u = 0.8845312889194352`
- `delay_steps = 0`
- `y_eq = 97.16156286`
- `u_eq = 97.04`

## Validation metrics

Selected model validation one-step metrics:

- RMSE: `5.234810941749596`
- MAE: `2.0416659028441795`
- bias: `-1.6789754250972049`
- MAPE: `3.792300780256609`
- R2: `0.9141655433795702`

Selected model validation recursive metrics:

- RMSE: `5.3011639284964245`
- MAE: `2.277032799758361`
- bias: `-1.8814556821807338`
- MAPE: `4.204217268662627`
- R2: `0.9119757917318732`

## Baseline comparison

Validation recursive RMSE:

- v0.13.0 placeholder model: `16.876249223579954`
- v0.13.4 no-intercept refit model: `49.39659303862327`
- v0.13.6 selected recursive model: `5.3011639284964245`

Improvements:

- improvement versus placeholder: `68.58802060656052%`
- improvement versus v0.13.4 refit: `89.2681587891063%`

## Decision

The stage decision is:

    pass

Reason:

The selected model improves recursive validation metrics versus both the v0.13.0 placeholder model and the v0.13.4 refit model under the configured thresholds.

## Interpretation

v0.13.6 confirms that model selection should be based on recursive/free-run validation, not only one-step fit.

The selected model is simple and has delay zero. This is useful for replay prediction quality, but it should still be treated conservatively. It may be capturing an apparent command-following relationship in the replay data rather than deeper plant dynamics.

Therefore, this result does not approve live control. It only provides a stronger candidate plant model for the next offline shadow-mode comparison stage.

## Files

- `recursive-model-summary.json`: decision, baseline comparison, selected model, and metrics.
- `selected-recursive-model.json`: selected model coefficients and validation metrics.
- `recursive-model-candidates.csv`: all candidate models and validation metrics.
- `recursive-model-validation-timeseries.csv`: validation-segment recursive predictions.

## Recommended next step

The recommended next stage is:

    v0.13.7 repeat shadow-mode comparison with selected recursive model

That stage should compare:

1. v0.13.0 placeholder model;
2. v0.13.4 one-step fitted model;
3. v0.13.6 selected recursive model.

The comparison should remain offline-only and should not apply controller recommendations.

## Safety scope

This stage is offline-only.

It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.
