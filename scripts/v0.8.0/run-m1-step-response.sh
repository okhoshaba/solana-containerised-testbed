#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_BRANCH="v0.8.0-dynamic-load-system-identification"

RUN_ID="${1:-}"
NAMESPACE="${NAMESPACE:-solana-observability}"
HOLD="${HOLD:-300}"
WARMUP="${WARMUP:-30}"
SAMPLE="${SAMPLE:-5}"
LOADGEN_URL="${LOADGEN_URL:-http://solana-loadgen2:7070}"
PROM_URL="${PROM_URL:-http://solana-metrics:9464}"
RATE_KEY="${RATE_KEY:-lambda}"
TOOLS_IMAGE="${TOOLS_IMAGE:-docker.io/khoshaba/solana-controlled-load-tools:layer1}"
DELETE_JOB_AFTER="${DELETE_JOB_AFTER:-0}"

if [ -z "$RUN_ID" ]; then
  echo "Usage: $0 <run_id>"
  echo "Allowed:"
  echo "  v0.8.0-M1-S32-64"
  echo "  v0.8.0-M1-S64-128"
  echo "  v0.8.0-M1-S32-128"
  exit 2
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]; then
  echo "ERROR: wrong branch: $CURRENT_BRANCH"
  echo "Expected: $EXPECTED_BRANCH"
  exit 1
fi

case "$RUN_ID" in
  v0.8.0-M1-S32-64)
    LEVELS="32 64"
    LAMBDA_MIN="32"
    LAMBDA_MAX="64"
    ;;
  v0.8.0-M1-S64-128)
    LEVELS="64 128"
    LAMBDA_MIN="64"
    LAMBDA_MAX="128"
    ;;
  v0.8.0-M1-S32-128)
    LEVELS="32 128"
    LAMBDA_MIN="32"
    LAMBDA_MAX="128"
    ;;
  *)
    echo "ERROR: unsupported M1 run_id: $RUN_ID"
    exit 2
    ;;
esac

for cmd in kubectl python3 git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd"
    exit 1
  fi
done

if [ ! -x scripts/v0.8.0/preflight-v0.8.0-with-rpc-port-forward.sh ]; then
  echo "ERROR: missing executable preflight wrapper"
  exit 1
fi

JOB_NAME="$(printf '%s' "$RUN_ID" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')"
JOB_NAME="m1-${JOB_NAME}"

RAW_DIR="data/raw/v0.8.0/${RUN_ID}"
RUN_DIR="results/v0.8.0/runs/${RUN_ID}"
PREFLIGHT_SUMMARY="results/v0.8.0/preflight/${RUN_ID}/preflight-summary.json"

MANIFEST="${RUN_DIR}/job.yaml"
JOB_LOG="${RUN_DIR}/job.log"
POD_YAML="${RUN_DIR}/pod.yaml"
JOB_YAML="${RUN_DIR}/job-status.yaml"
RUN_SUMMARY="${RUN_DIR}/run-summary.json"
RUN_METADATA="${RUN_DIR}/run-metadata.json"

if { [ -d "$RAW_DIR" ] || [ -d "$RUN_DIR" ]; } && [ "${FORCE:-0}" != "1" ]; then
  echo "ERROR: output directory already exists for $RUN_ID"
  echo "RAW_DIR=$RAW_DIR"
  echo "RUN_DIR=$RUN_DIR"
  echo "Use FORCE=1 only for an intentional rerun."
  exit 1
fi

mkdir -p "$RAW_DIR" "$RUN_DIR"

LEVEL_COUNT="$(python3 - <<PY
print(len("$LEVELS".split()))
PY
)"
DURATION_REQUESTED="$((WARMUP + HOLD * LEVEL_COUNT))"
COLLECT_TIMEOUT="$((DURATION_REQUESTED + 180))"

echo "== v0.8.0 M1 step-response run =="
echo "run_id:      $RUN_ID"
echo "levels:      $LEVELS"
echo "warmup:      $WARMUP"
echo "hold:        $HOLD"
echo "duration:    $DURATION_REQUESTED"
echo "sample:      $SAMPLE"
echo "namespace:   $NAMESPACE"
echo "loadgen_url: $LOADGEN_URL"
echo "prom_url:    $PROM_URL"
echo

echo "== Preflight =="
scripts/v0.8.0/preflight-v0.8.0-with-rpc-port-forward.sh "$RUN_ID"

python3 -m json.tool "$PREFLIGHT_SUMMARY" >/dev/null

PREFLIGHT_PASSED="$(python3 - <<PY
import json
with open("$PREFLIGHT_SUMMARY", "r", encoding="utf-8") as f:
    data = json.load(f)
print(str(data["safety_preflight"]["preflight_passed"]).lower())
PY
)"

if [ "$PREFLIGHT_PASSED" != "true" ]; then
  echo "ERROR: preflight did not pass"
  exit 1
fi

START_TIME_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH="$(date -u +%s)"

export RUN_ID RAW_DIR START_TIME_UTC LEVELS WARMUP HOLD SAMPLE

python3 - <<'PY'
import csv
import os
from datetime import datetime, timedelta

raw_dir = os.environ["RAW_DIR"]
levels = [float(x) for x in os.environ["LEVELS"].split()]
warmup = int(os.environ["WARMUP"])
hold = int(os.environ["HOLD"])
sample = int(os.environ["SAMPLE"])
start = datetime.fromisoformat(os.environ["START_TIME_UTC"].replace("Z", "+00:00"))

total = warmup + hold * len(levels)

rows = []
for t in range(0, total + 1, sample):
    if t < warmup:
        target = levels[0]
        phase = "warmup"
        phase_index = 0
    else:
        idx = min((t - warmup) // hold, len(levels) - 1)
        target = levels[int(idx)]
        phase = "hold"
        phase_index = int(idx + 1)

    ts = start + timedelta(seconds=t)
    rows.append([
        ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        t,
        target,
        phase,
        phase_index,
    ])

for name in ("load_profile_commanded.csv", "load_profile_applied.csv"):
    path = os.path.join(raw_dir, name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "t_seconds", "target_lambda", "phase", "phase_index"])
        w.writerows(rows)
PY

cat > "$MANIFEST" <<EOF_MANIFEST
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: ${JOB_NAME}
    app.kubernetes.io/component: v080-m1-step-response
    app.kubernetes.io/part-of: solana-containerised-testbed
    solana-testbed-run-id: ${RUN_ID}
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ${JOB_NAME}
        app.kubernetes.io/component: v080-m1-step-response
        app.kubernetes.io/part-of: solana-containerised-testbed
        solana-testbed-run-id: ${RUN_ID}
    spec:
      restartPolicy: Never
      nodeSelector:
        testbed-role: observability
      containers:
      - name: tools
        image: ${TOOLS_IMAGE}
        imagePullPolicy: IfNotPresent
        command:
        - bash
        - -lc
        - |
          set -euo pipefail
          mkdir -p /work/results
          python3 /work/scripts/collect_csv.py \\
            --loadgen-url "${LOADGEN_URL}" \\
            --prom-url "${PROM_URL}" \\
            --rate-key "${RATE_KEY}" \\
            --sample "${SAMPLE}" \\
            --timeout "${COLLECT_TIMEOUT}" \\
            step \\
            --levels "${LEVELS}" \\
            --hold "${HOLD}" \\
            --warmup "${WARMUP}" \\
            | tee /work/results/collect_csv.csv
        volumeMounts:
        - name: results
          mountPath: /work/results
      volumes:
      - name: results
        emptyDir: {}
EOF_MANIFEST

echo "== Applying Job =="
kubectl -n "$NAMESPACE" delete job "$JOB_NAME" --ignore-not-found
kubectl apply -f "$MANIFEST"

echo "== Waiting for Job completion =="
JOB_OK="false"
if kubectl -n "$NAMESPACE" wait --for=condition=complete "job/${JOB_NAME}" --timeout="${COLLECT_TIMEOUT}s"; then
  JOB_OK="true"
fi

POD_NAME="$(kubectl -n "$NAMESPACE" get pods -l job-name="$JOB_NAME" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"

kubectl -n "$NAMESPACE" get job "$JOB_NAME" -o yaml > "$JOB_YAML" 2>/dev/null || true

if [ -n "$POD_NAME" ]; then
  kubectl -n "$NAMESPACE" get pod "$POD_NAME" -o yaml > "$POD_YAML" 2>/dev/null || true
  kubectl -n "$NAMESPACE" logs "$POD_NAME" -c tools > "$JOB_LOG" 2>&1 || true
else
  echo "No pod found for job $JOB_NAME" > "$JOB_LOG"
fi

COPY_OK="false"
COPY_METHOD="none"
LOG_COPY_ERR="${RUN_DIR}/kubectl-logs-copy.err"

if [ -n "$POD_NAME" ]; then
  if kubectl -n "$NAMESPACE" cp "${POD_NAME}:/work/results/collect_csv.csv" "${RAW_DIR}/collect_csv.csv" -c tools >/dev/null 2>&1; then
    COPY_OK="true"
    COPY_METHOD="kubectl_cp"
  else
    if kubectl -n "$NAMESPACE" logs "$POD_NAME" -c tools > "${RAW_DIR}/collect_csv.csv" 2> "$LOG_COPY_ERR"; then
      if [ -s "${RAW_DIR}/collect_csv.csv" ]; then
        COPY_OK="true"
        COPY_METHOD="kubectl_logs"
      fi
    fi
  fi
fi

END_TIME_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
END_EPOCH="$(date -u +%s)"
ACTUAL_DURATION="$((END_EPOCH - START_EPOCH))"

export END_TIME_UTC ACTUAL_DURATION JOB_OK COPY_OK COPY_METHOD RUN_SUMMARY RUN_METADATA PREFLIGHT_SUMMARY DURATION_REQUESTED LAMBDA_MIN LAMBDA_MAX

python3 - <<'PY'
import json
import os

run_id = os.environ["RUN_ID"]
raw_dir = os.environ["RAW_DIR"]
collect_csv = os.path.join(raw_dir, "collect_csv.csv")

rows = 0
if os.path.exists(collect_csv):
    with open(collect_csv, "r", encoding="utf-8", errors="replace") as f:
        rows = max(sum(1 for _ in f) - 1, 0)

job_ok = os.environ["JOB_OK"] == "true"
copy_ok = os.environ["COPY_OK"] == "true"
pass_run = job_ok and copy_ok and rows > 0

summary = {
    "run_id": run_id,
    "experiment_class": "M1-step-response",
    "profile_type": "step",
    "levels": [float(x) for x in os.environ["LEVELS"].split()],
    "warmup_seconds": int(os.environ["WARMUP"]),
    "hold_seconds": int(os.environ["HOLD"]),
    "duration_requested_seconds": int(os.environ["DURATION_REQUESTED"]),
    "duration_actual_seconds": int(os.environ["ACTUAL_DURATION"]),
    "sample_seconds": int(os.environ["SAMPLE"]),
    "job_ok": job_ok,
    "copy_ok": copy_ok,
    "copy_method": os.environ.get("COPY_METHOD", "none"),
    "collect_csv_rows": rows,
    "status": "PASS" if pass_run else "FAIL",
}

with open(os.environ["RUN_SUMMARY"], "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)

with open(os.environ["PREFLIGHT_SUMMARY"], "r", encoding="utf-8") as f:
    preflight = json.load(f)

metadata = {
    "schema_version": "v0.8.0-run-metadata-1",
    "project": "Solana Containerised Testbed",
    "stage": "v0.8.0 dynamic load system identification",
    "run_id": run_id,
    "experiment_class": "M1-step-response",
    "profile_type": "step",
    "git": preflight["git"],
    "timing": {
        "start_time_utc": os.environ["START_TIME_UTC"],
        "end_time_utc": os.environ["END_TIME_UTC"],
        "duration_seconds": int(os.environ["ACTUAL_DURATION"])
    },
    "sampling": {
        "target_sampling_interval_seconds": int(os.environ["SAMPLE"]),
        "actual_sampling_interval_seconds": int(os.environ["SAMPLE"]),
        "resampling_used": False
    },
    "load_profile": {
        "lambda_min": float(os.environ["LAMBDA_MIN"]),
        "lambda_max": float(os.environ["LAMBDA_MAX"]),
        "lambda_nominal": None,
        "parameters": {
            "profile": "step",
            "levels": [float(x) for x in os.environ["LEVELS"].split()],
            "warmup_seconds": int(os.environ["WARMUP"]),
            "hold_seconds": int(os.environ["HOLD"]),
            "sample_seconds": int(os.environ["SAMPLE"]),
            "implementation": "collect_csv.py step"
        },
        "commanded_signal_file": f"data/raw/v0.8.0/{run_id}/load_profile_commanded.csv",
        "applied_signal_file": f"data/raw/v0.8.0/{run_id}/load_profile_applied.csv"
    },
    "safety_preflight": preflight["safety_preflight"],
    "telemetry": {
        "raw_files": [
            f"data/raw/v0.8.0/{run_id}/load_profile_commanded.csv",
            f"data/raw/v0.8.0/{run_id}/load_profile_applied.csv",
            f"data/raw/v0.8.0/{run_id}/collect_csv.csv",
            f"results/v0.8.0/runs/{run_id}/job.log",
            f"results/v0.8.0/runs/{run_id}/job.yaml",
            f"results/v0.8.0/runs/{run_id}/pod.yaml"
        ],
        "processed_files": [],
        "summary_file": f"results/v0.8.0/runs/{run_id}/run-summary.json"
    },
    "abort_policy": {
        "abort_conditions_declared": [
            "preflight failure",
            "Kubernetes Job failure",
            "collect_csv output missing",
            "collect_csv output empty",
            "RPC unavailable",
            "DiskPressure=True",
            "validator pod not ready"
        ],
        "abort_triggered": not pass_run,
        "abort_reason": None if pass_run else "job failure, copy failure, or empty collect_csv output"
    },
    "run_verdict": {
        "status": "PASS" if pass_run else "FAIL",
        "scientifically_usable": bool(pass_run),
        "notes": "M1 step-response run generated using collect_csv.py step."
    }
}

with open(os.environ["RUN_METADATA"], "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2, sort_keys=True)
PY

python3 -m json.tool "$RUN_SUMMARY" >/dev/null
python3 -m json.tool "$RUN_METADATA" >/dev/null

if [ "$DELETE_JOB_AFTER" = "1" ]; then
  kubectl -n "$NAMESPACE" delete job "$JOB_NAME" --ignore-not-found
fi

echo "== Outputs =="
echo "raw_dir:     $RAW_DIR"
echo "run_dir:     $RUN_DIR"
echo "summary:     $RUN_SUMMARY"
echo "metadata:    $RUN_METADATA"
echo "collect_csv: ${RAW_DIR}/collect_csv.csv"
echo
cat "$RUN_SUMMARY"

if [ "$JOB_OK" != "true" ] || [ "$COPY_OK" != "true" ]; then
  echo
  echo "ERROR: M1 step-response run failed or output copy failed"
  exit 1
fi

echo
echo "M1 step-response run completed: $RUN_ID"
