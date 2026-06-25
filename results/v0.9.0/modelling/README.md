# v0.9.0 offline throughput modelling results

## Purpose

This directory contains the first offline throughput-modelling results based on the published v0.8.0 dynamic load system-identification dataset.

The analysed channel is:

    u_cmd(t) -> u_ach(t)

where:

- `u_cmd` is the commanded transaction load;
- `u_ach` is the achieved throughput.

## Persistent identifiers

- Software v0.8.0 DOI: `10.5281/zenodo.20828274`
- Dataset v0.8.0 DOI: `10.5281/zenodo.20834551`

## Files

| file | role |
|---|---|
| `unity-baseline-summary.md` | Human-readable report for the unity-gain baseline model `y[k] = u[k]`. |
| `transition-first-sample-summary.md` | Human-readable report for first recorded post-transition samples. |
| `throughput-modelling-summary.json` | Machine-readable summary of the unity-baseline and transition analyses. |

## Main findings

The settled-sample unity-gain model is highly accurate in the confirmed safe range:

    lambda = 32..128

For settled samples:

| metric | value |
|---|---:|
| RMSE | 0.094648 |
| MAE | 0.085025 |
| max absolute error | 0.293260 |
| mean error | 0.000204 |

The transition analysis shows that by the first recorded post-transition sample, approximately 85.6% of the throughput transition has occurred:

    alpha = 0.856154

The corresponding simple transition model is:

    y[k] = y[k-1] + 0.856154 * (u[k] - y[k-1])

or:

    y[k] = 0.143846 * y[k-1] + 0.856154 * u[k]

## Interpretation

The current evidence supports a two-part offline throughput model:

1. Steady-state model:

       u_ach[k] ≈ u_cmd[k]

2. Boundary-transition correction:

       y[k] = y[k-1] + alpha * (u[k] - y[k-1])

At the current dataset resolution, there is no evidence that a more complex steady-state throughput model is required within the safe range `lambda = 32..128`.

## Limitations

- This is throughput-only modelling.
- Latency-constrained modelling remains out of scope because usable `lat_p99` values are missing.
- The transition analysis uses the first recorded post-transition sample.
- The observed boundary interval is approximately 35 seconds, so sub-35-second dynamics are not identified here.
