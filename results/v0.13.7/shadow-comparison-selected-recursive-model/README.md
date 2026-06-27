# v0.13.7 repeat shadow-mode comparison with selected recursive model

## Purpose

This stage repeats the shadow-mode model comparison with three candidate plant models:

- placeholder baseline
- v0.13.4 one-step refit model
- v0.13.6 selected recursive model

The purpose is to decide whether the selected recursive model can be promoted as the candidate surrogate plant model for the future v0.14.0 offline controller simulator.

v0.13.7 is still an offline shadow-mode comparison stage. It is not a closed-loop simulator and does not apply actions to a live system.

## Source artefacts

- config_path: `configs/v0.13.7/shadow-comparison-selected-recursive-model.json`
- replay_path: `results/v0.13.2/real-replay-shadow-mode-validation/real-replay-shadow-timeseries.csv`
- placeholder_model_path: `configs/v0.13.0/shadow-controller-replay.json`
- one_step_refit_model_path: `results/v0.13.4/refit-throughput-model/refit-coefficients.json`
- selected_recursive_model_path: `results/v0.13.6/recursive-plant-model-refit/selected-recursive-model.json`
- v0_13_5_comparison_summary_path: `results/v0.13.5/shadow-mode-refit-comparison/comparison-summary.json`
- v0_13_6_summary_path: `results/v0.13.6/recursive-plant-model-refit/recursive-model-summary.json`
- time_column: `source_time_seconds`
- command_column: `u_cmd_replay`
- observed_column: `u_ach_replay`

## Shadow-mode protocol

- Evaluation mode: recursive shadow rollout.
- Evaluation window: v0.13.6 validation segment.
- Recursive state initialization: first observed value of the validation segment.
- Anti-leakage rule: prediction for target row i uses previous recursive state and command history only.
- Actuator applied: false.

## Metrics

| model | count | RMSE | MAE | bias | median AE | max AE | MAPE | SMAPE | R2 | warnings |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| placeholder | 27 | 16.876249 | 12.146221 | -9.896293 | 5.561371 | 35.780292 | 19.992174 | 23.105197 | 0.107904 | 0 |
| one_step_refit | 27 | 49.396593 | 39.592635 | -39.592635 | 29.480841 | 89.783712 | 69.479857 | 120.116003 | -6.642820 | 0 |
| selected_recursive | 27 | 5.301164 | 2.277033 | -1.881456 | 0.486792 | 20.971096 | 4.204217 | 4.566173 | 0.911976 | 0 |

## Ranking

1. `selected_recursive` - RMSE=5.301164, MAE=2.277033
2. `placeholder` - RMSE=16.876249, MAE=12.146221
3. `one_step_refit` - RMSE=49.396593, MAE=39.592635

## Decision

- status: `pass`
- accepted as candidate surrogate plant model: `True`
- reason: Selected recursive model is best or materially tied for best on core metrics with no non-finite predictions or warning count in the evaluated shadow window.
- recommended next step: Use selected_recursive as the candidate surrogate plant model for v0.14.0 offline controller simulator.

## Implication for v0.14.0

The selected recursive model is accepted as the candidate surrogate plant model for v0.14.0 offline controller simulation.
