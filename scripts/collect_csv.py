#!/usr/bin/env python3
import argparse
import json
import re
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

DEFAULT_RATE_KEY = "lambda"

# Try hard to find these in /stats JSON (including nested)
CAND_SENT_TOTAL = [
    "sent_total", "sentTotal", "total_sent", "totalSent",
    "sent_ok_total", "sent_success_total", "sent_successful_total",
    "sent_count", "sentCount", "tx_sent_total", "transactions_sent_total",
    "sent", "total"
]
CAND_INFLIGHT = ["inflight", "in_flight", "inFlight", "pending", "outstanding"]
CAND_ERR_PSEC = ["err_per_sec", "errors_per_sec", "errPerSec", "error_rate", "errorsPerSec", "errRate"]
CAND_ACH_REPORTED = [
    "sent_per_sec", "sent_per_sec_reported", "sentPerSec", "tps",
    "throughput", "achieved_rate", "achievedRate", "u_ach"
]

def http_get(url: str, timeout: float = 2.5) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def http_post_json(url: str, payload: Dict[str, Any], timeout: float = 2.5) -> str:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def as_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None

def find_key_recursive(obj: Any, candidates: list[str]) -> Optional[float]:
    """
    Return first numeric value found for any candidate key (recursive in dict/list),
    accepts numeric strings too.
    """
    if isinstance(obj, dict):
        # direct match
        for k in candidates:
            if k in obj:
                got = as_float(obj[k])
                if got is not None:
                    return got

        # case-insensitive key match
        lower_map = {str(k).lower(): k for k in obj.keys()}
        for k in candidates:
            lk = k.lower()
            if lk in lower_map:
                got = as_float(obj[lower_map[lk]])
                if got is not None:
                    return got

        # recurse
        for v in obj.values():
            got = find_key_recursive(v, candidates)
            if got is not None:
                return got

    elif isinstance(obj, list):
        for it in obj:
            got = find_key_recursive(it, candidates)
            if got is not None:
                return got

    return None

def parse_stats(stats_text: str) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[float]]:
    """
    Returns: sent_total (int), inflight, err_per_sec, u_ach_reported
    """
    try:
        obj = json.loads(stats_text)
    except Exception:
        return None, None, None, None

    sent = find_key_recursive(obj, CAND_SENT_TOTAL)
    infl = find_key_recursive(obj, CAND_INFLIGHT)
    err  = find_key_recursive(obj, CAND_ERR_PSEC)
    ach  = find_key_recursive(obj, CAND_ACH_REPORTED)

    sent_i = int(sent) if sent is not None else None
    return sent_i, infl, err, ach

def parse_lat_p99(metrics_text: str, metric_name: str, quantile: str) -> Optional[float]:
    pat = re.compile(
        rf'^{re.escape(metric_name)}\{{[^}}]*quantile="{re.escape(quantile)}"[^}}]*\}}\s+([0-9eE\.\+\-]+)\s*$'
    )
    for line in metrics_text.splitlines():
        m = pat.match(line.strip())
        if m:
            try:
                return float(m.group(1))
            except Exception:
                return None
    return None

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

def emit_header():
    print("t_iso,t_sec,u_cmd,sent_total,u_ach,lat_p99,inflight,err_per_sec")

def emit_row(t_iso: str, t_sec: float, u_cmd: float, sent_total: Optional[int], u_ach: Optional[float],
             lat_p99: Optional[float], inflight: Optional[float], err_psec: Optional[float]):
    def f(x: Optional[float], fmt: str) -> str:
        if x is None:
            return ""
        return fmt % x
    def i(x: Optional[int]) -> str:
        return "" if x is None else str(x)

    print(",".join([
        t_iso,
        f(t_sec, "%.3f"),
        f(u_cmd, "%.3f"),
        i(sent_total),
        f(u_ach, "%.6f"),
        f(lat_p99, "%.9f"),
        f(inflight, "%.3f"),
        f(err_psec, "%.6f"),
    ]))

def sample_once(loadgen_url: str, prom_url: str, metric_name: str, quantile: str,
                u_cmd: float, t0: float,
                prev_sent: Optional[int], prev_t: Optional[float],
                timeout: float) -> Tuple[Optional[int], Optional[float], Optional[float], Optional[float], Optional[float]]:
    # returns: sent_total, inflight, err_psec, lat_p99, u_ach
    sent_total = inflight = err_psec = None
    lat_p99 = None
    u_ach_reported = None

    # stats
    try:
        stats_text = http_get(loadgen_url + "/stats", timeout=timeout)
        sent_total, inflight, err_psec, u_ach_reported = parse_stats(stats_text)
    except Exception:
        pass

    # metrics
    try:
        metrics_text = http_get(prom_url + "/metrics", timeout=timeout)
        lat_p99 = parse_lat_p99(metrics_text, metric_name=metric_name, quantile=quantile)
    except Exception:
        pass

    # u_ach: prefer Δsent_total/Δt, else fallback to reported throughput if available
    t_sec = time.time() - t0
    u_ach = None
    if sent_total is not None and prev_sent is not None and prev_t is not None:
        dt = t_sec - prev_t
        ds = sent_total - prev_sent
        if dt > 0 and ds >= 0:
            u_ach = ds / dt

    if u_ach is None and u_ach_reported is not None and u_ach_reported > 0:
        u_ach = float(u_ach_reported)

    return sent_total, inflight, err_psec, lat_p99, u_ach

def set_rate(loadgen_url: str, rate_key: str, rate: float, timeout: float):
    payload = {rate_key: rate}
    http_post_json(loadgen_url + "/rate", payload, timeout=timeout)

def run_steady(args):
    t0 = time.time()
    prev_sent = None
    prev_t = None

    set_rate(args.loadgen_url, args.rate_key, args.rate, args.timeout)
    emit_header()

    start = time.time()
    while True:
        t_iso = now_iso()
        sent_total, inflight, err_psec, lat_p99, u_ach = sample_once(
            args.loadgen_url, args.prom_url, args.lat_metric, args.lat_quantile,
            args.rate, t0, prev_sent, prev_t, args.timeout
        )
        t_sec = time.time() - t0
        emit_row(t_iso, t_sec, args.rate, sent_total, u_ach, lat_p99, inflight, err_psec)

        if sent_total is not None:
            prev_sent = sent_total
            prev_t = t_sec

        if (time.time() - start) >= args.duration:
            break
        time.sleep(args.sample)

def run_step(args):
    t0 = time.time()
    prev_sent = None
    prev_t = None

    emit_header()

    for u in args.levels:
        set_rate(args.loadgen_url, args.rate_key, u, args.timeout)
        level_start = time.time()

        if args.warmup > 0:
            time.sleep(args.warmup)

        while True:
            if (time.time() - level_start) >= args.hold:
                break

            t_iso = now_iso()
            sent_total, inflight, err_psec, lat_p99, u_ach = sample_once(
                args.loadgen_url, args.prom_url, args.lat_metric, args.lat_quantile,
                u, t0, prev_sent, prev_t, args.timeout
            )
            t_sec = time.time() - t0
            emit_row(t_iso, t_sec, u, sent_total, u_ach, lat_p99, inflight, err_psec)

            if sent_total is not None:
                prev_sent = sent_total
                prev_t = t_sec

            time.sleep(args.sample)

def parse_levels(s: str) -> list[float]:
    s = s.replace(",", " ")
    return [float(tok) for tok in s.split() if tok.strip()]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loadgen-url", default="http://127.0.0.1:7070")
    ap.add_argument("--prom-url", default="http://127.0.0.1:9464")
    ap.add_argument("--lat-metric", default="solana_transaction_latency_seconds")
    ap.add_argument("--lat-quantile", default="0.99")
    ap.add_argument("--rate-key", default=DEFAULT_RATE_KEY)
    ap.add_argument("--sample", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=2.5)

    sub = ap.add_subparsers(dest="mode", required=True)

    st = sub.add_parser("steady")
    st.add_argument("--rate", type=float, required=True)
    st.add_argument("--duration", type=float, required=True)

    sp = sub.add_parser("step")
    sp.add_argument("--levels", type=parse_levels, required=True)
    sp.add_argument("--hold", type=float, required=True)
    sp.add_argument("--warmup", type=float, default=0.0)

    args = ap.parse_args()

    if args.mode == "steady":
        run_steady(args)
    else:
        run_step(args)

if __name__ == "__main__":
    main()
