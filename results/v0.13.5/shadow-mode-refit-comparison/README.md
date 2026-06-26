# v0.13.5 shadow-mode refit comparison results

This directory contains the offline-only placeholder-vs-fitted shadow-mode comparison for v0.13.5.

## Purpose

v0.13.5 repeats shadow-mode validation using the same real replay input and compares:

1. the v0.13.0 placeholder plant model;
2. the v0.13.4 fitted/refit plant model.

The comparison is intended to determine whether the fitted coefficients should be promoted as the default model candidate for the next closed-loop preparation gate.

## Input

The replay input is:

    results/v0.13.2/real-replay-shadow-mode-validation/real-replay-shadow-timeseries.csv

The placeholder model source is:

    configs/v0.13.0/shadow-controller-replay.json

The fitted model source is:

    results/v0.13.4/refit-throughput-model/refit-coefficients.json

## Compared models

Placeholder model:

- `a_y = 0.92`
- `b_u = 0.08`
- `delay_steps = 1`
- `y0 = 0.0`

Fitted model:

- `a_y = 1.02763034203239`
- `b_u = -0.03997702623417542`
- `delay_steps = 15`
- `y0 = 80.0`

## Result summary

The decision status is:

    caution

Predictive metrics:

- placeholder RMSE: `34.006020960563724`
- fitted RMSE: `158.66751537803125`
- RMSE improvement: `-366.58653643140315%`
- placeholder MAE: `29.09838054616022`
- fitted MAE: `130.38018618894728`

Controller recommendation comparison:

- action disagreement count: `78`
- action disagreement rate: `1.0`
- mean absolute action delta: `13.362404581772056`
- max absolute action delta: `33.91340488500906`
- fitted more aggressive count: `65`
- fitted more conservative count: `13`

Safety comparison:

- placeholder safety violations: `0`
- fitted safety violations: `0`
- new fitted safety regressions versus placeholder: `0`

## Interpretation

v0.13.5 shows that the v0.13.4 fitted model should not be promoted as the default shadow-mode plant model.

Although v0.13.4 produced a strong one-step fit, the fitted coefficients perform poorly in recursive/free-run shadow-mode simulation. The fitted model produces substantially worse prediction metrics than the placeholder model and changes every controller recommendation in the comparison.

This is not a pipeline failure. It is a useful validation result: the current no-intercept fitted model is not yet suitable for controller-preparation claims.

## Files

- `comparison-summary.json`: decision, metrics, model sources, and safety comparison.
- `shadow-mode-comparison.csv`: per-row placeholder-vs-fitted prediction and action comparison.

## Recommended next step

The recommended next modelling step is to fit a better recursive plant model, most likely one of:

- an intercept model: `y[k+1] = c + a_y*y[k] + b_u*u[k-delay]`;
- an equilibrium-deviation model: `y[k+1] - y_eq = a_y*(y[k] - y_eq) + b_u*(u[k-delay] - u_eq)`;
- a train/validation split comparing one-step fit and free-run replay behaviour.

Closed-loop preparation should not proceed on the basis of the current v0.13.4 coefficients.

## Safety scope

This stage is offline-only.

It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.
