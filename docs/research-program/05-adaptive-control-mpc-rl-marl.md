# Adaptive Control: MPC, RL, and MARL

## Long-term objective

The long-term research objective is to adaptively keep the Solana/Agave network near the boundary of maximum sustainable throughput without pushing it into overload.

## Recommended progression

1. rule-based controller
2. knee detection
3. MPC controller
4. single-agent RL
5. MARL

MARL should not be the immediate next step.

## Control objective

```text
Maximize accepted throughput
subject to:
  latency <= threshold
  error rate <= threshold
  slot stability >= threshold
  validator health == ok
  no sustained saturation
```

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
routing decision
```
