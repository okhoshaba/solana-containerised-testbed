# v0.11.0 offline controller profile coverage

## Purpose

This file summarises offline controller behaviour across multiple safe reference profiles.

The comparison is offline only. It does not access Kubernetes and does not send live testbed commands.

## Results

| Profile | Controller case | RMSE | MAE | Max abs error | Saturation count | Anti-windup freeze count |
|---|---|---:|---:|---:|---:|---:|
| `constant64` | `feedforward` | 0.000000 | 0.000000 | 0.000000 | 0 | 0 |
| `constant64` | `p` | 0.000000 | 0.000000 | 0.000000 | 0 | 0 |
| `constant64` | `pi` | 0.000000 | 0.000000 | 0.000000 | 0 | 0 |
| `step64-96` | `feedforward` | 0.600499 | 0.089608 | 4.603072 | 0 | 0 |
| `step64-96` | `p` | 0.240970 | 0.032977 | 1.863379 | 0 | 0 |
| `step64-96` | `pi` | 0.237834 | 0.064687 | 1.808585 | 0 | 0 |
| `multistep` | `feedforward` | 1.200998 | 0.358430 | 4.603072 | 0 | 0 |
| `multistep` | `p` | 0.731300 | 0.188537 | 4.603072 | 12 | 0 |
| `multistep` | `pi` | 0.726439 | 0.204742 | 4.594359 | 12 | 12 |
| `lower-range` | `feedforward` | 0.849234 | 0.179215 | 4.603072 | 0 | 0 |
| `lower-range` | `p` | 0.647044 | 0.122584 | 4.603072 | 15 | 0 |
| `lower-range` | `pi` | 0.646967 | 0.155177 | 4.611660 | 3 | 3 |
| `sine-approx` | `feedforward` | 0.712104 | 0.206787 | 3.452304 | 0 | 0 |
| `sine-approx` | `p` | 0.299729 | 0.084268 | 1.397534 | 24 | 0 |
| `sine-approx` | `pi` | 0.299509 | 0.117110 | 1.401133 | 24 | 24 |

## Per-profile ranking

- `constant64`: best by MAE = `feedforward`, best by RMSE = `feedforward`
- `step64-96`: best by MAE = `p`, best by RMSE = `pi`
- `multistep`: best by MAE = `p`, best by RMSE = `pi`
- `lower-range`: best by MAE = `p`, best by RMSE = `pi`
- `sine-approx`: best by MAE = `p`, best by RMSE = `pi`

## Interpretation

This profile-coverage run broadens offline testing beyond the original multistep profile.

It is still not a live-control readiness decision. The results should be used to identify controller candidates that remain safe and stable across several reference profiles before any closed-loop Kubernetes experiment is considered.
