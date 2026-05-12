# MPC Adaptive Control

## Goal

Develop adaptive transaction-load control using Model Predictive Control.

## Position

MPC comes after Dataset layer 1 controlled load response.

## Required elements

- measurable state
- controllable action/input
- dynamic model
- constraints
- prediction horizon
- objective function

## Candidate state

```text
recent latency quantiles
slot interval statistics
error rate
submitted throughput
accepted throughput
inflight transactions
subscription errors
previous action
saturation score
```

## Candidate actions

```text
lambda adjustment
workers adjustment
inflight adjustment
burst adjustment
backoff policy
```

## Candidate objective

```text
Maximize accepted throughput
subject to:
  latency <= threshold
  error rate <= threshold
  slot stability >= threshold
  validator health == ok
  no sustained saturation
```
