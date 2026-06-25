# v0.10.0 throughput controller preparation results

## Purpose

This directory contains the machine-readable controller-preparation artefact for the `v0.10.0 throughput controller preparation` stage.

This stage does not implement or deploy a live closed-loop controller. It formalises the throughput-control problem before future PID/MPC prototype work.

## Source stage

The controller preparation is based on the merged `v0.9.0 offline throughput modelling` results.

Relevant source artefacts:

- `docs/experiments/v0.9.0-offline-throughput-modelling.md`
- `docs/experiments/v0.9.0-offline-throughput-modelling-methodological-note.md`
- `results/v0.9.0/modelling/README.md`
- `results/v0.9.0/modelling/throughput-modelling-summary.json`

Persistent identifiers:

- Software v0.8.0 DOI: `10.5281/zenodo.20828274`
- Dataset v0.8.0 DOI: `10.5281/zenodo.20834551`

## Files

| file | role |
|---|---|
| `controller-preparation-summary.json` | Machine-readable definition of the throughput-control problem, plant model, safety policy, PID baseline and MPC formulation. |

## Control problem

The initial control objective is throughput tracking:

    r[k] -> y[k]

where:

- `r[k]` is the desired throughput reference;
- `y[k] = u_ach[k]` is the achieved throughput;
- `u[k] = u_cmd[k]` is the manipulated command sent to the load generator.

## Initial plant model

The settled throughput model is:

    u_ach[k] ~= u_cmd[k]

The transition correction is:

    y[k] = y[k-1] + 0.856154 * (u[k] - y[k-1])

or:

    y[k] = 0.143846 * y[k-1] + 0.856154 * u[k]

The transition model describes the first recorded post-transition sample, not sub-5-second dynamics.

## Safety policy

The initial safe command interval is:

    32 <= u_cmd[k] <= 128

The controller must apply saturation before any command is sent:

    u_cmd[k] = min(max(u_raw[k], 32), 128)

Excluded from this stage:

- `lambda = 256`, except as a future cautious boundary/reference point;
- `lambda = 512`, due to previously identified storage-pressure risk.

## PID preparation

The PID baseline should start conservatively:

- P-only or PI-only;
- saturation enabled from the beginning;
- anti-windup required before live integral control;
- aggressive derivative action avoided.

## MPC preparation

The initial MPC model is:

    y[k+1] = a*y[k] + b*u[k]

with:

    a = 0.143846
    b = 0.856154

Initial constraints:

    32 <= u[k+i] <= 128

Latency constraints remain disabled until usable latency telemetry is available.

## Next expected stage

The expected next stage is:

    v0.11.0 throughput controller prototype

That stage should implement an offline simulator or dry-run controller before any live Kubernetes closed-loop experiment is attempted.
