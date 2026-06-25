# v0.9.0 unity-baseline throughput model summary

## Purpose

This report evaluates the simplest offline throughput-channel model for the published v0.8.0 dynamic-identification dataset:

    y[k] = u[k]

where:

- `u[k]` is the commanded load, `u_cmd`;
- `y[k]` is the achieved throughput, `u_ach`.

## Persistent identifiers

- Software v0.8.0 DOI: `10.5281/zenodo.20828274`
- Dataset v0.8.0 DOI: `10.5281/zenodo.20834551`

## Input data

- input root: `data/raw/v0.8.0`
- collect_csv files: 12
- total samples: 1569
- columns used:
  - `t_sec`
  - `u_cmd`
  - `u_ach`

## Method

Two metrics were computed.

### Full-sample metrics

All samples are included, including:

- the first sample of each run;
- the first sample immediately after each `u_cmd` change.

### Settled-sample metrics

The following samples are excluded:

- the first row of each run;
- the first row after each change in `u_cmd`.

This separates steady-state tracking accuracy from one-sample transition effects.

## Results

| sample set | n | RMSE | MAE | max abs error | mean error |
|---|---:|---:|---:|---:|---:|
| full | 1569 | 2.044515 | 0.243630 | 64.000000 | -0.061057 |
| settled | 1531 | 0.094648 | 0.085025 | 0.293260 | 0.000204 |

## Interpretation

The full-sample metrics are dominated by transition samples and start-up samples.

The settled-sample metrics show that the unity-gain model is highly accurate in the confirmed safe range:

    lambda = 32..128

For settled samples, the mean error is close to zero and the maximum absolute error is below 0.3 TPS.

This means that, at the current 5-second sampling resolution, the steady-state throughput channel can be modelled as:

    u_ach[k] ≈ u_cmd[k]

The observed dynamic effect is concentrated mainly in the first sample after a command change. Therefore, the next modelling step should focus on transition-sample behaviour rather than replacing the steady-state unity model with a more complex model.

## Limitation

This report covers throughput only. Latency-constrained modelling remains out of scope because usable `lat_p99` values are missing in the v0.8.0 `collect_csv.csv` outputs.
