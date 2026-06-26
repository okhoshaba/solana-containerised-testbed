# v0.13.4 real replay throughput model refit results

This directory contains the offline-only throughput model refit outputs for v0.13.4.

## Purpose

v0.13.4 refits a discrete first-order throughput model using the real replay shadow-mode timeseries produced by v0.13.2.

The fitted model is intended as a candidate replacement for the placeholder plant model used by the v0.13.0 shadow-mode runner.

## Input

The source replay file is:

    results/v0.13.2/real-replay-shadow-mode-validation/real-replay-shadow-timeseries.csv

The selected columns are:

- time: `source_time_seconds`
- command input: `u_cmd_replay`
- observed output: `u_ach_replay`

## Model structure

The fitted model uses the structure:

    y[k+1] = a_y * y[k] + b_u * u[k-delay]

The fit does not include an intercept term.

## Selected coefficients

The selected model is:

- `a_y = 1.02763034203239`
- `b_u = -0.03997702623417542`
- `delay_steps = 15`
- `y0 = 80.0`

## One-step fit metrics

The selected one-step fit produced:

- RMSE: `5.586271591418611`
- MAE: `3.110984215151178`
- bias: `-0.627255234576628`
- MAPE: `5.195506583982073`
- R2: `0.9730152858434464`

## Files

- `refit-coefficients.json`: selected coefficients and all evaluated delay candidates.
- `refit-summary.json`: concise decision and selected model summary.
- `refit-timeseries.csv`: one-step fitted prediction series.

## Interpretation

v0.13.4 successfully produced a fitted one-step model from real replay data.

However, this result alone does not prove that the fitted model is suitable for recursive shadow-mode simulation or controller preparation. That question is evaluated in v0.13.5 by comparing the placeholder model and the fitted model under the same shadow-mode replay protocol.

## Safety scope

This stage is offline-only.

It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.
