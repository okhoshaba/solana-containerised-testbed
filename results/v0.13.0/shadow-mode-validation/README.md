# v0.13.0 shadow-mode validation results

## Purpose

This directory contains outputs from the v0.13.0 config-driven shadow-mode controller runner.

The runner is offline-only.

It computes controller recommendations but does not apply them.

## Inputs

The default config is:

    configs/v0.13.0/shadow-controller-replay.json

The runner searches for replay CSV files in earlier result directories.

If no suitable replay file is found, the runner uses a deterministic synthetic replay profile.

## Outputs

The expected outputs are:

    shadow-controller-timeseries.csv
    shadow-controller-summary.json

The CSV contains per-step replay input, predicted output, controller error, and shadow recommendation.

The JSON contains summary metrics, safety notes, and limitations.

## Safety statement

This result is not a live closed-loop experiment.

The controller output is not applied.

Kubernetes is not modified.

Transaction load is not changed.

## Interpretation

If the input mode is replay_csv and an achieved output column is available, the prediction error metrics can be used for model-validation discussion.

If the input mode is synthetic_replay, the result should be interpreted only as a software, reproducibility, and pipeline validation check.
