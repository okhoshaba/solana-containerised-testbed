# v0.11.0 offline controller comparison

## Purpose

This file summarises the automated offline comparison of the implemented controller modes.

The comparison is offline only. It does not access Kubernetes and does not send live testbed commands.

## Fixed comparison setup

- profile: `multistep`
- plant: `transition`
- hold: `12`
- safe command range: `32..128`

## Results

| Case | Controller | RMSE | MAE | Max abs error | Saturation count | Anti-windup freeze count |
|---|---|---:|---:|---:|---:|---:|
| `feedforward` | `feedforward` | 1.200998 | 0.358430 | 4.603072 | 0 | 0 |
| `p_kp_0_10` | `p` | 0.731300 | 0.188537 | 4.603072 | 12 | 0 |
| `pi_kp_0_10_ki_0_002` | `pi` | 0.726439 | 0.204742 | 4.594359 | 12 | 12 |

## Ranking

- Best by MAE: `p_kp_0_10`
- Best by RMSE: `pi_kp_0_10_ki_0_002`

## Interpretation

The P-only controller remains the best simple controller by MAE.

The conservative PI controller slightly improves RMSE, but increases MAE relative to P-only.

The PI anti-windup freeze mechanism is active during saturated upper-bound operation, which confirms that integral accumulation is controlled when the raw command would exceed the safe range.

The result does not yet justify live closed-loop Kubernetes control. Further offline profile coverage is required before a closed-loop readiness decision.
