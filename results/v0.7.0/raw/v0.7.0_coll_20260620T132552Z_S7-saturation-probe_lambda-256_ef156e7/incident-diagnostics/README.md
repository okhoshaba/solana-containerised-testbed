# S7 lambda=256 incident diagnostics

## Classification

This run is classified as the first v0.7.0 saturation/instability candidate.

The failure was not a clean load-generator-only saturation signal. The incident involved Kubernetes node storage pressure and validator pod eviction.

## Run

Run directory:

    v0.7.0_coll_20260620T132552Z_S7-saturation-probe_lambda-256_ef156e7

Configured load:

    load_level=S7
    target_lambda=256
    duration_seconds=60

## Observed failed-run summary

    sent_delta=3769
    ok_delta=3682
    err_delta=83
    final_target_lambda=0
    final_inflight=4

Final error:

    GetLatestBlockhash: rpc call getLatestBlockhash() on http://solana-rpc:8899: connect: connection refused

## Kubernetes incident evidence

The Kubernetes event log reported validator pod eviction caused by node storage pressure.

Relevant symptoms:

    Evicted pod/solana-validator-0
    The node was low on resource: ephemeral-storage
    The node had condition: DiskPressure

After this event, the validator pod was recreated and RPC access became unavailable during the attempted follow-up run.

## Interpretation

This run should be treated as a testbed instability boundary rather than a clean steady-state throughput knee.

The likely immediate cause was node ephemeral-storage pressure on the validator node, which led to validator pod eviction and temporary RPC unavailability.

## Methodological consequence

Further high-load runs should be paused until storage pressure is inspected and mitigated.

The failed run should remain in the v0.7.0 dataset as an incident/saturation-boundary candidate, while the aborted follow-up attempt should be stored under results/v0.7.0/logs rather than counted as a completed raw experiment.
