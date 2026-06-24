#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${1:-}"

if [[ -z "$RUN_ID" ]]; then
  echo "Usage: $0 <run_id>"
  echo "Allowed:"
  echo "  v0.8.0-M3-MS32-64-128-64-32"
  echo "  v0.8.0-M3-MS32-128-64-128-32"
  exit 2
fi

NAMESPACE="${NAMESPACE:-solana-observability}"
LOADGEN_URL="${LOADGEN_URL:-http://solana-loadgen2:7070}"
PROM_URL="${PROM_URL:-http://solana-metrics:9464}"
TOOLS_IMAGE="${TOOLS_IMAGE:-docker.io/khoshaba/solana-controlled-load-tools:layer1}"

WARMUP="${WARMUP:-30}"
HOLD="${HOLD:-180}"
SAMPLE="${SAMPLE:-5}"
TIMEOUT="${TIMEOUT:-5}"

case "$RUN_ID" in
  v0.8.0-M4-SINE-L80-A48-T720)
    LEVELS="80 104 122 128 122 104 80 56 38 32 38 56 80"
    LAMBDA_MIN="32"
    LAMBDA_MAX="128"
    ;;
  *)
    echo "ERROR: unsupported M4 run_id: $RUN_ID"
    echo "Allowed:"
    echo "  v0.8.0-M4-SINE-L80-A48-T720"
    exit 2
    ;;
esac

read -r -a LEVEL_ARRAY <<< "$LEVELS"
LEVEL_COUNT="${#LEVEL_ARRAY[@]}"
DURATION=$(( WARMUP + HOLD * LEVEL_COUNT ))
WAIT_TIMEOUT=$(( DURATION + 300 ))

RAW_DIR="data/raw/v0.8.0/${RUN_ID}"
RUN_DIR="results/v0.8.0/runs/${RUN_ID}"
PREFLIGHT_DIR="results/v0.8.0/preflight/${RUN_ID}"

mkdir -p "$RAW_DIR" "$RUN_DIR" "$PREFLIGHT_DIR"

echo "== v0.8.0 M4 sine-approximation run =="
echo "run_id:      $RUN_ID"
echo "levels:      $LEVELS"
echo "level_count: $LEVEL_COUNT"
echo "warmup:      $WARMUP"
echo "hold:        $HOLD"
echo "duration:    $DURATION"
echo "sample:      $SAMPLE"
echo "namespace:   $NAMESPACE"
echo "loadgen_url: $LOADGEN_URL"
echo "prom_url:    $PROM_URL"
echo

echo "== Preflight =="
if [[ -x scripts/v0.8.0/preflight-v0.8.0-with-rpc-port-forward.sh ]]; then
  set +e
  RUN_ID="$RUN_ID" PREFLIGHT_DIR="$PREFLIGHT_DIR" \
    scripts/v0.8.0/preflight-v0.8.0-with-rpc-port-forward.sh "$RUN_ID"
  PREFLIGHT_STATUS=$?
  set -e
else
  echo "ERROR: missing scripts/v0.8.0/preflight-v0.8.0-with-rpc-port-forward.sh"
  exit 1
fi

echo "preflight status: $PREFLIGHT_STATUS"
if [[ "$PREFLIGHT_STATUS" -ne 0 ]]; then
  echo "ERROR: preflight failed"
  exit "$PREFLIGHT_STATUS"
fi

JOB_NAME="$(echo "m4-${RUN_ID}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9-]+/-/g' | cut -c1-63 | sed -E 's/-+$//')"

cat > "$RUN_DIR/job.yaml" <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: solana-controlled-load-m4
    testbed.stage: v0.8.0
    testbed.run_id: ${RUN_ID}
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: solana-controlled-load-m4
        testbed.stage: v0.8.0
        testbed.run_id: ${RUN_ID}
    spec:
      restartPolicy: Never
      containers:
        - name: collect
          image: ${TOOLS_IMAGE}
          imagePullPolicy: IfNotPresent
          command:
            - /bin/sh
            - -lc
          args:
            - |
              set -eu
              mkdir -p /work/results
              python3 /work/scripts/collect_csv.py \
                --loadgen-url ${LOADGEN_URL} \
                --prom-url ${PROM_URL} \
                --rate-key lambda \
                --sample ${SAMPLE} \
                --timeout ${TIMEOUT} \
                step \
                --levels '${LEVELS}' \
                --hold ${HOLD} \
                --warmup ${WARMUP} \
                | tee /work/results/collect_csv.csv
EOF

echo "== Applying Job =="
kubectl delete job -n "$NAMESPACE" "$JOB_NAME" --ignore-not-found=true >/dev/null 2>&1 || true
kubectl apply -f "$RUN_DIR/job.yaml"

echo "== Waiting for Job completion =="
JOB_OK=false
if kubectl wait -n "$NAMESPACE" --for=condition=complete "job/${JOB_NAME}" --timeout="${WAIT_TIMEOUT}s"; then
  JOB_OK=true
else
  JOB_OK=false
fi

kubectl get job -n "$NAMESPACE" "$JOB_NAME" -o yaml > "$RUN_DIR/job-status.yaml" || true

POD_NAME="$(kubectl get pods -n "$NAMESPACE" -l job-name="$JOB_NAME" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [[ -n "$POD_NAME" ]]; then
  kubectl get pod -n "$NAMESPACE" "$POD_NAME" -o yaml > "$RUN_DIR/pod.yaml" || true
fi

kubectl logs -n "$NAMESPACE" "job/${JOB_NAME}" > "$RUN_DIR/job.log" 2> "$RUN_DIR/kubectl-logs-copy.err" || true

awk '
  BEGIN { seen = 0 }
  /^t_iso,t_sec,u_cmd,sent_total,u_ach,lat_p99,inflight,err_per_sec/ { seen = 1 }
  seen == 1 { print }
' "$RUN_DIR/job.log" > "$RAW_DIR/collect_csv.csv"

COPY_OK=false
if [[ -s "$RAW_DIR/collect_csv.csv" ]]; then
  COPY_OK=true
fi

COLLECT_ROWS=0
if [[ -s "$RAW_DIR/collect_csv.csv" ]]; then
  COLLECT_ROWS="$(tail -n +2 "$RAW_DIR/collect_csv.csv" | grep -c . || true)"
fi

RUN_ID="$RUN_ID" \
LEVELS="$LEVELS" \
LAMBDA_MIN="$LAMBDA_MIN" \
LAMBDA_MAX="$LAMBDA_MAX" \
WARMUP="$WARMUP" \
HOLD="$HOLD" \
SAMPLE="$SAMPLE" \
DURATION="$DURATION" \
LEVEL_COUNT="$LEVEL_COUNT" \
JOB_OK="$JOB_OK" \
COPY_OK="$COPY_OK" \
COLLECT_ROWS="$COLLECT_ROWS" \
RAW_DIR="$RAW_DIR" \
RUN_DIR="$RUN_DIR" \
PREFLIGHT_DIR="$PREFLIGHT_DIR" \
python3 - <<'PY'
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

run_id = os.environ["RUN_ID"]
levels = [float(x) for x in os.environ["LEVELS"].split()]
warmup = float(os.environ["WARMUP"])
hold = float(os.environ["HOLD"])
sample = float(os.environ["SAMPLE"])
duration = float(os.environ["DURATION"])
level_count = int(os.environ["LEVEL_COUNT"])
lambda_min = float(os.environ["LAMBDA_MIN"])
lambda_max = float(os.environ["LAMBDA_MAX"])
job_ok = os.environ["JOB_OK"] == "true"
copy_ok = os.environ["COPY_OK"] == "true"
collect_rows = int(os.environ["COLLECT_ROWS"])
raw_dir = Path(os.environ["RAW_DIR"])
run_dir = Path(os.environ["RUN_DIR"])
preflight_dir = Path(os.environ["PREFLIGHT_DIR"])

commanded_path = raw_dir / "load_profile_commanded.csv"
applied_path = raw_dir / "load_profile_applied.csv"

rows = []
start = warmup
for idx, level in enumerate(levels):
    end = start + hold
    rows.append({
        "phase_index": idx,
        "start_seconds": start,
        "end_seconds": end,
        "target_lambda": level,
    })
    start = end

for path in [commanded_path, applied_path]:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["phase_index", "start_seconds", "end_seconds", "target_lambda"],
        )
        writer.writeheader()
        writer.writerows(rows)

status = "PASS" if job_ok and copy_ok and collect_rows > 0 else "FAIL"

summary = {
    "run_id": run_id,
    "experiment_class": "M4-sine-approximation",
    "profile_type": "sine_approx_stepwise",
    "levels": levels,
    "level_count": level_count,
    "lambda_min": lambda_min,
    "lambda_max": lambda_max,
    "warmup_seconds": warmup,
    "hold_seconds": hold,
    "sample_seconds": sample,
    "duration_requested_seconds": duration,
    "job_ok": job_ok,
    "copy_ok": copy_ok,
    "copy_method": "kubectl_logs",
    "collect_csv_rows": collect_rows,
    "status": status,
}

metadata = {
    "run_id": run_id,
    "stage": "v0.8.0 dynamic load system identification",
    "experiment_class": "M4 sine-approximation load profile",
    "profile_type": "sine_approx_stepwise",
    "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "levels": levels,
    "level_count": level_count,
    "lambda_min": lambda_min,
    "lambda_max": lambda_max,
    "warmup_seconds": warmup,
    "hold_seconds": hold,
    "sample_seconds": sample,
    "duration_requested_seconds": duration,
    "raw_dir": str(raw_dir),
    "run_dir": str(run_dir),
    "preflight_dir": str(preflight_dir),
    "notes": "M4 sine-approximation profile generated using collect_csv.py step with more than two levels.",
}

(run_dir / "run-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
(run_dir / "run-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "== Outputs =="
echo "raw_dir:     $RAW_DIR"
echo "run_dir:     $RUN_DIR"
echo "summary:     $RUN_DIR/run-summary.json"
echo "metadata:    $RUN_DIR/run-metadata.json"
echo "collect_csv: $RAW_DIR/collect_csv.csv"
echo

python3 -m json.tool "$RUN_DIR/run-summary.json"

if [[ "$JOB_OK" != "true" || "$COPY_OK" != "true" || "$COLLECT_ROWS" -le 0 ]]; then
  echo "ERROR: M4 sine-approximation run failed: $RUN_ID"
  exit 1
fi

echo "M4 sine-approximation run completed: $RUN_ID"
