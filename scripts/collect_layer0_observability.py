#!/usr/bin/env python3

"""
Dataset Layer 0 Observability Collector

Purpose:
  Collect a reproducible Layer 0 observability dataset for:

    validator + Yellowstone/Geyser + monitor + Prometheus metrics

This script does not perform controlled load testing.
It does not benchmark throughput.
It only records basic observability-derived runtime estimates.

Default output:

  output/datasets/layer0-observability/<host_id_safe>/<run_id>/
    metadata.json
    samples.csv
    samples.jsonl
    raw-metrics.prom
    metric-candidates.txt

Example:

  python3 scripts/collect_layer0_observability.py \
    --duration 60 \
    --sample-interval 2 \
    --host-id hp-z240-noavx2
"""

import argparse
import csv
import json
import os
import platform
import re
import subprocess
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


LAMPORTS_PER_SOL = 1_000_000_000


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_for_run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(value):
    value = str(value).strip() or "unknown-host"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def run_cmd(cmd, default=""):
    try:
        return subprocess.check_output(
            cmd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return default


def git_commit(short=False):
    if short:
        return run_cmd(["git", "rev-parse", "--short", "HEAD"], default="unknown")
    return run_cmd(["git", "rev-parse", "HEAD"], default="unknown")


def docker_compose_image(service_name, compose_file="compose.yellowstone.release.yaml"):
    try:
        output = subprocess.check_output(
            [
                "docker",
                "compose",
                "-f",
                compose_file,
                "images",
                service_name,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

        lines = [line for line in output.splitlines() if line.strip()]
        if len(lines) < 2:
            return "unknown"

        return lines[-1]
    except Exception:
        return "unknown"


def read_cpu_model():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass

    return platform.processor() or "unknown"


def avx2_present():
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            return "avx2" in f.read().lower()
    except Exception:
        return False


def loadavg_1m():
    try:
        return float(os.getloadavg()[0])
    except Exception:
        return None


def mem_available_kb():
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1])
    except Exception:
        pass

    return None


def http_get_text(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def rpc_call(rpc_url, method, params=None, timeout=3):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
    }

    if params is not None:
        payload["params"] = params

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        rpc_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def validator_health(rpc_url):
    try:
        result = rpc_call(rpc_url, "getHealth")
        return result.get("result", "unknown")
    except Exception:
        return "unreachable"


def payer_balance_sol(rpc_url, payer_pubkey):
    if not payer_pubkey:
        return None

    try:
        result = rpc_call(rpc_url, "getBalance", [payer_pubkey])
        lamports = result.get("result", {}).get("value")
        if lamports is None:
            return None
        return lamports / LAMPORTS_PER_SOL
    except Exception:
        return None


def parse_labels(label_text):
    labels = {}

    if not label_text:
        return labels

    for key, value in re.findall(
        r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"\\])*)"',
        label_text,
    ):
        labels[key] = value.replace('\\"', '"')

    return labels


def parse_prometheus(text):
    metrics = defaultdict(list)

    line_re = re.compile(
        r'^([a-zA-Z_:][a-zA-Z0-9_:]*)'
        r'(\{([^}]*)\})?'
        r'\s+'
        r'([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|NaN|\+Inf|-Inf)'
    )

    for line in text.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        match = line_re.match(line)
        if not match:
            continue

        name = match.group(1)
        label_text = match.group(3)
        value_text = match.group(4)

        try:
            value = float(value_text)
        except Exception:
            continue

        labels = parse_labels(label_text)
        metrics[name].append((labels, value))

    return metrics


def base_metric_name(name):
    for suffix in ("_bucket", "_sum", "_count"):
        if name.endswith(suffix):
            return name[: -len(suffix)]

    return name


def detect_metric_family(metrics, patterns):
    candidates = set()

    for name in metrics.keys():
        candidates.add(base_metric_name(name))

    ranked = []

    for candidate in candidates:
        lower = candidate.lower()
        score = 0

        for pattern in patterns:
            if re.search(pattern, lower):
                score += 1

        if score > 0:
            ranked.append((score, candidate))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][1]


def detect_error_metric(metrics):
    patterns = [
        r"subscription.*error",
        r"geyser.*error",
        r"grpc.*error",
        r"stream.*error",
        r"error.*total",
    ]

    ranked = []

    for name in metrics.keys():
        lower = name.lower()
        score = 0

        for pattern in patterns:
            if re.search(pattern, lower):
                score += 1

        if lower.endswith("_total"):
            score += 1

        if score > 0:
            ranked.append((score, name))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    return ranked[0][1]


def metric_sum(metrics, name):
    if not name or name not in metrics:
        return None

    values = [value for _, value in metrics[name]]

    if not values:
        return None

    return sum(values)


def family_sum(metrics, family):
    if not family:
        return None

    return metric_sum(metrics, f"{family}_sum")


def family_count(metrics, family):
    if not family:
        return None

    return metric_sum(metrics, f"{family}_count")


def summary_quantile(metrics, family, q):
    if not family or family not in metrics:
        return None

    acceptable = {
        str(q),
        f"{q:.1f}",
        f"{q:.2f}",
        f"{q:.3f}",
    }

    for labels, value in metrics[family]:
        if labels.get("quantile") in acceptable:
            return value

    return None


def histogram_quantile(metrics, family, q):
    if not family:
        return None

    bucket_name = f"{family}_bucket"

    if bucket_name not in metrics:
        return None

    buckets_by_le = defaultdict(float)

    for labels, value in metrics[bucket_name]:
        le = labels.get("le")

        if le is None:
            continue

        if le == "+Inf":
            le_value = float("inf")
        else:
            try:
                le_value = float(le)
            except Exception:
                continue

        buckets_by_le[le_value] += value

    if not buckets_by_le:
        return None

    buckets = sorted(buckets_by_le.items(), key=lambda item: item[0])
    total = buckets[-1][1]

    if total <= 0:
        return None

    target = q * total
    previous_le = 0.0
    previous_count = 0.0

    for le, count in buckets:
        if count >= target:
            if le == float("inf"):
                return previous_le

            bucket_count = count - previous_count

            if bucket_count <= 0:
                return le

            fraction = (target - previous_count) / bucket_count
            return previous_le + fraction * (le - previous_le)

        previous_le = le
        previous_count = count

    return None


def family_quantile(metrics, family, q):
    if not family:
        return None

    direct = summary_quantile(metrics, family, q)

    if direct is not None:
        return direct

    return histogram_quantile(metrics, family, q)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def write_metric_candidates(path, metrics):
    interesting = []

    for name in sorted(metrics.keys()):
        lower = name.lower()

        if (
            "slot" in lower
            or "latency" in lower
            or "transaction" in lower
            or "tx" in lower
            or "subscription" in lower
            or "geyser" in lower
            or "grpc" in lower
            or "error" in lower
        ):
            interesting.append(name)

    with open(path, "w", encoding="utf-8") as f:
        for name in interesting:
            f.write(name + "\n")


def validate_runtime(rpc_url, metrics_url):
    health = validator_health(rpc_url)

    metrics_ok = False
    try:
        text = http_get_text(metrics_url)
        metrics_ok = bool(text.strip())
    except Exception:
        metrics_ok = False

    return health, metrics_ok


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Collect Dataset Layer 0 observability samples."
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Collection duration in seconds. Default: 60.",
    )

    parser.add_argument(
        "--sample-interval",
        type=int,
        default=2,
        help="Sampling interval in seconds. Default: 2.",
    )

    parser.add_argument(
        "--rpc-url",
        default="http://127.0.0.1:8899",
        help="Solana JSON-RPC URL.",
    )

    parser.add_argument(
        "--metrics-url",
        default="http://127.0.0.1:9464/metrics",
        help="Prometheus metrics endpoint URL.",
    )

    parser.add_argument(
        "--out-root",
        default="output/datasets/layer0-observability",
        help="Dataset output root directory.",
    )

    parser.add_argument(
        "--testbed-version",
        default="v0.2.0",
        help="Testbed version label.",
    )

    parser.add_argument(
        "--host-id",
        default="",
        help=(
            "Public host identifier for dataset naming. "
            "If omitted, system hostname is used."
        ),
    )

    parser.add_argument(
        "--payer-pubkey",
        default="",
        help="Optional Solana payer public key for getBalance sampling.",
    )

    parser.add_argument(
        "--slot-metric",
        default="",
        help=(
            "Optional explicit Prometheus metric family for slot interval. "
            "Example: slot_interval_seconds"
        ),
    )

    parser.add_argument(
        "--tx-metric",
        default="",
        help=(
            "Optional explicit Prometheus metric family for transaction latency. "
            "Example: transaction_latency_seconds"
        ),
    )

    parser.add_argument(
        "--errors-metric",
        default="",
        help=(
            "Optional explicit Prometheus metric for subscription errors. "
            "Example: subscription_errors_total"
        ),
    )

    parser.add_argument(
        "--compose-file",
        default="compose.yellowstone.release.yaml",
        help="Compose file used for metadata image discovery.",
    )

    parser.add_argument(
        "--validator-service",
        default="validator",
        help="Compose service name for validator.",
    )

    parser.add_argument(
        "--monitor-service",
        default="monitor",
        help="Compose service name for monitor.",
    )

    parser.add_argument(
        "--skip-runtime-check",
        action="store_true",
        help="Skip initial RPC and metrics availability check.",
    )

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    system_hostname = platform.node() or "unknown-host"
    host_id = args.host_id.strip() or system_hostname
    host_id_safe = safe_name(host_id)

    short_commit = git_commit(short=True)
    full_commit = git_commit(short=False)

    run_id = f"layer0_{host_id_safe}_{utc_now_for_run_id()}_{short_commit}"

    out_dir = Path(args.out_root) / host_id_safe / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cpu_model = read_cpu_model()
    avx2 = avx2_present()

    validator_image = docker_compose_image(args.validator_service, args.compose_file)
    monitor_image = docker_compose_image(args.monitor_service, args.compose_file)

    if not args.skip_runtime_check:
        initial_health, initial_metrics_ok = validate_runtime(
            args.rpc_url,
            args.metrics_url,
        )

        if initial_health != "ok" or not initial_metrics_ok:
            print("WARNING: Initial runtime check did not fully pass.")
            print(f"  validator_health: {initial_health}")
            print(f"  metrics_scrape_ok: {initial_metrics_ok}")
            print("  The collector will continue and record observed failures.")

    metadata = {
        "run_id": run_id,
        "host_id": host_id,
        "host_id_safe": host_id_safe,
        "hostname": system_hostname,
        "testbed_version": args.testbed_version,
        "git_commit": full_commit,
        "git_commit_short": short_commit,
        "duration_seconds": args.duration,
        "sample_interval_seconds": args.sample_interval,
        "rpc_url": args.rpc_url,
        "metrics_url": args.metrics_url,
        "geyser_grpc_endpoint": "validator:10000",
        "cpu_model": cpu_model,
        "avx2_present": avx2,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "validator_image": validator_image,
        "monitor_image": monitor_image,
        "compose_file": args.compose_file,
        "validator_service": args.validator_service,
        "monitor_service": args.monitor_service,
        "notes": (
            "Dataset Layer 0 observability validation. "
            "This run records runtime observability signals and does not "
            "perform controlled load testing or throughput benchmarking."
        ),
    }

    metadata_path = out_dir / "metadata.json"
    samples_csv_path = out_dir / "samples.csv"
    samples_jsonl_path = out_dir / "samples.jsonl"
    raw_metrics_path = out_dir / "raw-metrics.prom"
    metric_candidates_path = out_dir / "metric-candidates.txt"

    write_json(metadata_path, metadata)

    fieldnames = [
        "timestamp_utc",
        "run_id",
        "host_id",
        "host_id_safe",
        "hostname",
        "cpu_model",
        "avx2_present",
        "git_commit",
        "git_commit_short",
        "testbed_version",
        "validator_image",
        "monitor_image",
        "validator_health",
        "payer_balance_sol",
        "metrics_scrape_ok",
        "slot_metric_family",
        "slot_interval_p50",
        "slot_interval_p90",
        "slot_interval_p99",
        "slot_interval_sum",
        "slot_interval_count",
        "transaction_latency_metric_family",
        "transaction_latency_p50",
        "transaction_latency_p95",
        "transaction_latency_p99",
        "transaction_latency_sum",
        "transaction_latency_count",
        "subscription_errors_metric",
        "subscription_errors_total",
        "system_load1",
        "system_mem_available_kb",
    ]

    samples = max(1, args.duration // args.sample_interval)
    last_metrics_text = ""

    with open(samples_csv_path, "w", encoding="utf-8", newline="") as csv_file, open(
        samples_jsonl_path,
        "w",
        encoding="utf-8",
    ) as jsonl_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for sample_index in range(samples):
            timestamp = utc_now_iso()

            health = validator_health(args.rpc_url)
            balance = payer_balance_sol(args.rpc_url, args.payer_pubkey)

            metrics_scrape_ok = False
            metrics = defaultdict(list)

            try:
                last_metrics_text = http_get_text(args.metrics_url)
                metrics = parse_prometheus(last_metrics_text)
                metrics_scrape_ok = True
            except Exception:
                metrics_scrape_ok = False

            slot_family = args.slot_metric or detect_metric_family(
                metrics,
                patterns=[
                    r"slot.*interval",
                    r"interval.*slot",
                    r"slot.*duration",
                    r"slot.*time",
                ],
            )

            tx_family = args.tx_metric or detect_metric_family(
                metrics,
                patterns=[
                    r"transaction.*latency",
                    r"latency.*transaction",
                    r"tx.*latency",
                    r"latency.*tx",
                    r"transaction.*duration",
                    r"tx.*duration",
                ],
            )

            errors_metric = args.errors_metric or detect_error_metric(metrics)

            row = {
                "timestamp_utc": timestamp,
                "run_id": run_id,
                "host_id": host_id,
                "host_id_safe": host_id_safe,
                "hostname": system_hostname,
                "cpu_model": cpu_model,
                "avx2_present": avx2,
                "git_commit": full_commit,
                "git_commit_short": short_commit,
                "testbed_version": args.testbed_version,
                "validator_image": validator_image,
                "monitor_image": monitor_image,
                "validator_health": health,
                "payer_balance_sol": balance,
                "metrics_scrape_ok": metrics_scrape_ok,
                "slot_metric_family": slot_family,
                "slot_interval_p50": family_quantile(metrics, slot_family, 0.50),
                "slot_interval_p90": family_quantile(metrics, slot_family, 0.90),
                "slot_interval_p99": family_quantile(metrics, slot_family, 0.99),
                "slot_interval_sum": family_sum(metrics, slot_family),
                "slot_interval_count": family_count(metrics, slot_family),
                "transaction_latency_metric_family": tx_family,
                "transaction_latency_p50": family_quantile(metrics, tx_family, 0.50),
                "transaction_latency_p95": family_quantile(metrics, tx_family, 0.95),
                "transaction_latency_p99": family_quantile(metrics, tx_family, 0.99),
                "transaction_latency_sum": family_sum(metrics, tx_family),
                "transaction_latency_count": family_count(metrics, tx_family),
                "subscription_errors_metric": errors_metric,
                "subscription_errors_total": metric_sum(metrics, errors_metric),
                "system_load1": loadavg_1m(),
                "system_mem_available_kb": mem_available_kb(),
            }

            writer.writerow(row)
            csv_file.flush()

            jsonl_file.write(json.dumps(row, sort_keys=True) + "\n")
            jsonl_file.flush()

            if metrics_scrape_ok:
                write_metric_candidates(metric_candidates_path, metrics)

            if sample_index < samples - 1:
                time.sleep(args.sample_interval)

    if last_metrics_text:
        with open(raw_metrics_path, "w", encoding="utf-8") as f:
            f.write(last_metrics_text)

    print("")
    print("Layer 0 observability dataset collected.")
    print(f"Output directory: {out_dir}")
    print("")
    print("Files:")
    print(f"  {metadata_path}")
    print(f"  {samples_csv_path}")
    print(f"  {samples_jsonl_path}")
    print(f"  {raw_metrics_path}")
    print(f"  {metric_candidates_path}")
    print("")


if __name__ == "__main__":
    main()
