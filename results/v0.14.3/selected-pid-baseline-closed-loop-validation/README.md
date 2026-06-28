# v0.14.3 selected PID baseline closed-loop validation

## Purpose

This stage validates the selected controller from v0.14.2 as a fixed closed-loop reference baseline before MPC experiments.

This is not a new gain sweep. It does not retune the controller.

## Selected controller

- Candidate: p_kp0.350_ki0.000_kd0.000
- Controller type: PID-style baseline
- Effective controller: P-only baseline
- kp: 0.35
- ki: 0.0
- kd: 0.0

The selected PID baseline is effectively a proportional-only controller. Integral and derivative terms are intentionally disabled because the v0.14.2 sweep selected ki=0 and kd=0 under calibrated closed-loop metrics.

## Source artefacts

- configs/v0.14.2/offline-pid-gain-sweep-calibrated-metrics.json
- results/v0.14.2/offline-pid-gain-sweep-calibrated-metrics/pid-sweep-summary.json
- configs/v0.14.0/offline-controller-simulator-selected-recursive-model.json
- results/v0.14.1/offline-simulator-calibration-profile-safety-review/calibration-summary.json

## Validation protocol

The validation freezes the selected controller and executes the offline closed-loop simulation protocol for exactly one candidate.

- Gain sweep allowed: false
- Retuning allowed: false
- Candidate count: 1
- Case count: 6
- Profile count: 6

## Metrics summary

- Pass count: 5
- Settled warning count: 0
- Explained transient count: 1
- Review count: 0
- Unexplained failure count: 0
- Average full RMSE: 2.2994707054434707
- Average full MAE: 0.5447648198740777
- Average full max absolute error: 16.67488303859327
- Average settled RMSE: 0.047925125701007314
- Average settled MAE: 0.04686417826987709
- Average settled max absolute error: 0.07525707608968564
- Worst settled max absolute error: 0.15332754794125947
- Average rate-limit fraction: 0.027083333333333334
- Average saturation fraction: 0.0

## Safety summary

- Unexplained failure count: 0
- Average saturation fraction: 0.0
- Average rate-limit fraction: 0.027083333333333334

The inherited case-metrics schema does not emit separate unsafe-action counters. This stage therefore uses calibrated status, unexplained failure count, saturation fraction, and rate-limit fraction as offline safety indicators.

## Decision

- Status: pass
- Accepted as MPC reference baseline: True

Reason: The fixed selected baseline has no unexplained failures, no settled warnings, and acceptable settled RMSE under calibrated offline closed-loop metrics.

## Limitations

This is an offline validation stage. It does not prove live Kubernetes safety or production stability.

The controller should not be described as a globally optimal PID controller. It should be described as the selected, fixed, reproducible P-only baseline produced by the calibrated offline PID-style sweep.

## Next step

Use this fixed P-only baseline as the reference comparator for MPC-oriented experiments.
