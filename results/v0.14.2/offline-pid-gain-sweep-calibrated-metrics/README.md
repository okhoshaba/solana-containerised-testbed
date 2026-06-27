# v0.14.2 offline PID gain sweep with calibrated metrics

## Purpose

This stage performs an offline gain sweep for P, PI, and PID candidates using the selected recursive plant model and v0.14.1 calibrated metrics.

No actuator is applied to a live system.

## Decision

- status: `pass`
- selected candidate: `p_kp0.350_ki0.000_kd0.000`
- reason: Best-ranked candidate has no unexplained failures, no settled warnings, and acceptable settled RMSE.

## Top candidates

| rank | candidate | family | kp | ki | kd | unexplained fail | settled warn | explained transient | avg settled RMSE | avg full RMSE |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | p_kp0.350_ki0.000_kd0.000 | p | 0.350 | 0.000 | 0.000 | 0 | 0 | 1 | 0.047925 | 2.299471 |
| 2 | p_kp0.300_ki0.000_kd0.000 | p | 0.300 | 0.000 | 0.000 | 0 | 0 | 1 | 0.048882 | 2.283013 |
| 3 | p_kp0.500_ki0.000_kd0.000 | p | 0.500 | 0.000 | 0.000 | 0 | 0 | 1 | 0.049278 | 2.348174 |
| 4 | p_kp0.200_ki0.000_kd0.000 | p | 0.200 | 0.000 | 0.000 | 0 | 0 | 1 | 0.051930 | 2.249397 |
| 5 | p_kp0.100_ki0.000_kd0.000 | p | 0.100 | 0.000 | 0.000 | 0 | 0 | 1 | 0.055787 | 2.233161 |
| 6 | p_kp0.750_ki0.000_kd0.000 | p | 0.750 | 0.000 | 0.000 | 0 | 0 | 1 | 0.081185 | 2.416816 |
| 7 | pi_kp0.500_ki0.005_kd0.000 | pi | 0.500 | 0.005 | 0.000 | 0 | 0 | 1 | 0.418366 | 2.426248 |
| 8 | pi_kp0.350_ki0.005_kd0.000 | pi | 0.350 | 0.005 | 0.000 | 0 | 0 | 1 | 0.453894 | 2.394778 |
| 9 | pid_kp0.350_ki0.005_kd0.050 | pid | 0.350 | 0.005 | 0.050 | 0 | 0 | 1 | 0.457671 | 2.390803 |
| 10 | pid_kp0.350_ki0.005_kd0.100 | pid | 0.350 | 0.005 | 0.100 | 0 | 0 | 1 | 0.461774 | 2.390317 |

## Interpretation

Candidates are ranked by calibrated safety first, then by settled-window performance.
The v0.14.0 fail result remains unchanged; v0.14.2 uses the v0.14.1 transient-aware interpretation for controller comparison.
