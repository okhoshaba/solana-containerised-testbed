# v0.13.2 real replay shadow-mode validation results

This directory contains the offline-only v0.13.2 real replay shadow-mode validation outputs.

## Purpose

v0.13.2 runs the existing v0.13.0 shadow-mode controller runner against the real v0.8.0 replay dataset selected by v0.13.1.

## Files

- runtime-shadow-controller-replay.json: resolved v0.13.0 runner config for the real replay source.
- shadow-controller-timeseries.csv: raw timeseries emitted by the v0.13.0 runner.
- shadow-controller-summary.json: raw summary emitted by the v0.13.0 runner.
- real-replay-shadow-timeseries.csv: annotated v0.13.2 timeseries with source replay time columns.
- real-replay-shadow-summary.json: v0.13.2 validation summary.

## Safety scope

This stage is offline-only.

It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.

## Interpretation

A successful result means the offline shadow-mode runner can consume the real v0.8.0 replay source.

It does not validate live telemetry or closed-loop control.
