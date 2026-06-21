# S7 post-incident validation run

## Classification

This run is a post-incident validation run after the S7 storage-pressure incident.

It should not be interpreted as an ordinary repeated S7 saturation-probe run. Its purpose is to check whether the testbed recovered after the validator-node DiskPressure event.

## Run

Run directory:

    v0.7.0_coll_20260621T032454Z_S7-post-incident-validation_lambda-256_9c2f081

Configured load:

    load_level=S7
    run_kind=post-incident-validation
    target_lambda=256
    duration_seconds=60

## Result

The validation run completed without new errors.

Observed counters:

    sent_delta=17465
    ok_delta=17465
    err_initial=87
    err_final=87
    err_delta=0
    final_target_lambda=0
    final_inflight=0

Sample-level maxima:

    sample_inflight_max=1
    sample_err_per_sec_max=0
    sample_sent_per_sec_max=256

## Note on final_last_err

The final_last_err field still contains the previous connection-refused error from the earlier S7 storage-pressure incident.

This is interpreted as a sticky diagnostic field in loadgen2, not as a new validation-run error, because err_delta=0 and err_per_sec remained 0 during this run.

## Storage state

Storage preflight passed before and after the validation run.

The validator node reported:

    DiskPressure=False
    validator pod Ready 1/1
    root_use_percent=38
    root_available_gb=28

## Interpretation

The post-incident validation run shows that the testbed recovered after the storage-pressure incident.

However, the earlier S7 failed run remains a valid infrastructure-boundary observation, because it exposed a validator-node storage-pressure failure mode under the S7 lambda=256 experiment sequence.
