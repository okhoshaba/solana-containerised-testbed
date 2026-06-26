# v0.13.3 model-fit sanity review results

This directory contains the offline-only model-fit sanity review for the real v0.8.0 replay shadow-mode run.

## Files

- model-fit-summary.json: decision, metrics, thresholds, and interpretation.
- model-fit-timeseries.csv: annotated per-row model-fit errors.

## Interpretation

This stage checks whether the current plant approximation is strong enough to support controller-quality claims.

A weak fit is not a pipeline failure. It means the next research step should be model identification or model refitting before stronger controller claims are made.

## Safety scope

This stage is offline-only. It does not call kubectl, modify Kubernetes, start a live controller, generate transaction load, apply controller recommendations, or execute closed-loop control.
