#!/usr/bin/env bash
set -euo pipefail

SAMPLE="${SAMPLE:-2}"
DUR="${DUR:-30}"
START="${START:-200}"
MULT="${MULT:-1.5}"
MAX="${MAX:-8000}"
RATE_KEY="${RATE_KEY:-lambda}"
SAT_STOP="${SAT_STOP:-0.92}"
LAT_MULT="${LAT_MULT:-1.25}"
ERR_STOP="${ERR_STOP:-0.02}"
MIN_SAT_N="${MIN_SAT_N:-3}"
MIN_LAT_N="${MIN_LAT_N:-3}"
MIN_ERR_N="${MIN_ERR_N:-3}"
LOADGEN_URL="${LOADGEN_URL:-http://127.0.0.1:7070}"
PROM_URL="${PROM_URL:-http://127.0.0.1:9464}"
RPC_URL="${RPC_URL:-http://127.0.0.1:8899}"
LAT_METRIC="${LAT_METRIC:-solana_transaction_latency_seconds}"
SLOT_METRIC="${SLOT_METRIC:-solana_slot_interval_seconds}"
SUBSCRIPTION_ERRORS_METRIC="${SUBSCRIPTION_ERRORS_METRIC:-solana_subscription_errors_total}"
WORKERS="${WORKERS:-}"
BURST="${BURST:-}"
CONTROLLER_MODE="${CONTROLLER_MODE:-adaptive_probe}"
EXPERIMENT_ID="${EXPERIMENT_ID:-knee_probe_$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="${OUT:-data/raw/${EXPERIMENT_ID}.csv}"

mkdir -p "$(dirname "$OUT")"
echo "[probe] writing cumulative CSV -> ${OUT}" >&2

median_py='
import csv, sys, statistics, math
path=sys.argv[1]
sat=[]; lat=[]; err=[]
with open(path, "r", newline="") as f:
    for row in csv.DictReader(f):
        try:
            s=row.get("saturation_score", "").strip()
            l=row.get("tx_latency_p99", "").strip()
            e=row.get("error_rate", "").strip()
            if s:
                sat.append(float(s))
            if l and float(l)>0:
                lat.append(float(l))
            if e:
                err.append(float(e))
        except Exception:
            pass

def med(xs):
    return statistics.median(xs) if xs else float("nan")
print(f"{med(sat)} {med(lat)} {med(err)} {len(sat)} {len(lat)} {len(err)}")
'

ceil_py='
import math,sys
x=float(sys.argv[1]); mult=float(sys.argv[2])
print(int(math.ceil(x*mult)))
'

header_written=0
baseline_lat=""
rate="${START}"
prev_rate=""
trigger_rate=""
level_idx=0

while (( rate <= MAX )); do
  level_idx=$((level_idx + 1))
  echo "[probe] rate=${rate} tx/s for ${DUR}s (sample=${SAMPLE}s, rate_key=${RATE_KEY})" >&2
  tmp="$(mktemp)"

  python3 scripts/collect_csv.py \
    --loadgen-url "${LOADGEN_URL}" \
    --prom-url "${PROM_URL}" \
    --rpc-url "${RPC_URL}" \
    --lat-metric "${LAT_METRIC}" \
    --slot-metric "${SLOT_METRIC}" \
    --subscription-errors-metric "${SUBSCRIPTION_ERRORS_METRIC}" \
    --sample "${SAMPLE}" \
    --rate-key "${RATE_KEY}" \
    --experiment-id "${EXPERIMENT_ID}" \
    --workers "${WORKERS}" \
    --burst "${BURST}" \
    --controller-mode "${CONTROLLER_MODE}" \
    steady \
      --rate "${rate}" \
      --duration "${DUR}" \
    > "${tmp}"

  if (( header_written == 0 )); then
    cat "${tmp}" > "${OUT}"
    header_written=1
  else
    tail -n +2 "${tmp}" >> "${OUT}"
  fi

  read -r sat_med lat_med err_med sat_n lat_n err_n < <(python3 -c "$median_py" "${tmp}")

  if [[ -z "${baseline_lat}" && "${lat_n}" -ge "${MIN_LAT_N}" ]]; then
    baseline_lat="${lat_med}"
    echo "[probe] baseline tx_latency_p99 median=${baseline_lat}s" >&2
  fi

  echo "[probe] medians: saturation=${sat_med} n=${sat_n}; tx_latency_p99=${lat_med}s n=${lat_n}; error_rate=${err_med} n=${err_n}" >&2

  if (( level_idx == 1 )) || [[ -z "${baseline_lat}" ]]; then
    prev_rate="${rate}"
    rate="$(python3 -c "$ceil_py" "${rate}" "${MULT}")"
    rm -f "${tmp}"
    continue
  fi

  stop=0
  if (( sat_n >= MIN_SAT_N )); then
    python3 - <<PY >/dev/null || stop=1
import math
sat=float("${sat_med}"); threshold=float("${SAT_STOP}")
if (not math.isnan(sat)) and sat <= threshold:
    raise SystemExit(1)
PY
  fi
  if (( lat_n >= MIN_LAT_N )); then
    python3 - <<PY >/dev/null || stop=1
import math
lat=float("${lat_med}"); base=float("${baseline_lat}"); k=float("${LAT_MULT}")
if (not math.isnan(lat)) and lat >= k*base:
    raise SystemExit(1)
PY
  fi
  if (( err_n >= MIN_ERR_N )); then
    python3 - <<PY >/dev/null || stop=1
import math
err=float("${err_med}"); threshold=float("${ERR_STOP}")
if (not math.isnan(err)) and err >= threshold:
    raise SystemExit(1)
PY
  fi

  if (( stop == 1 )); then
    trigger_rate="${rate}"
    rm -f "${tmp}"
    break
  fi

  prev_rate="${rate}"
  rate="$(python3 -c "$ceil_py" "${rate}" "${MULT}")"
  rm -f "${tmp}"
done

echo "[probe] done. cumulative log: ${OUT}" >&2

if [[ -z "${trigger_rate}" ]]; then
  echo "[probe] no trigger up to MAX=${MAX}" >&2
  exit 0
fi

echo "[probe] trigger detected at rate=${trigger_rate}; previous rate=${prev_rate:-unknown}" >&2

export TRIG_RATE="${trigger_rate}"
python3 - <<'PY'
import os
k = float(os.environ["TRIG_RATE"])
factors = [0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.4]
levels = sorted(set(max(50, int(round(k*x/50)*50)) for x in factors))
pre = [50,150,300,450,600,800,1000]
pre = [x for x in pre if x < levels[0]]
seq = pre + levels + list(reversed(pre + levels[:-1]))
print("Suggested LEVELS_STR:")
print(" ".join(str(x) for x in seq))
print("Suggested command:")
print(f'HOLD=60 SAMPLE=2 LEVELS_STR="{" ".join(str(x) for x in seq)}" bash scripts/knee_step_test.sh')
PY
