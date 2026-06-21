#!/usr/bin/env python3
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev


ROOT = Path(__file__).resolve().parents[2]
IN_CSV = ROOT / "results" / "v0.7.0" / "processed" / "v0.7.0-run-summary.csv"
OUT_CSV = ROOT / "results" / "v0.7.0" / "processed" / "v0.7.0-level-summary.csv"


def to_float(value: str) -> float | None:
    value = (value or "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def safe_mean(values: list[float]) -> str:
    if not values:
        return ""
    return f"{mean(values):.6f}"


def safe_std(values: list[float]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return "0.000000"
    return f"{pstdev(values):.6f}"


def safe_max(values: list[float]) -> str:
    if not values:
        return ""
    value = max(values)
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}"


def sort_key(item: tuple[tuple[str, str], list[dict[str, str]]]) -> tuple[int, float]:
    level, target = item[0]

    level_rank = {
        "S0": 0,
        "S1": 1,
        "S2": 2,
        "S3": 3,
        "S4": 4,
        "S5": 5,
        "S6": 6,
        "S7": 7,
    }.get(level, 99)

    target_value = to_float(target)
    if target_value is None:
        target_value = -1.0

    return level_rank, target_value


def main() -> int:
    if not IN_CSV.exists():
        raise FileNotFoundError(f"missing input CSV: {IN_CSV}")

    with IN_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        level = row.get("load_level", "")
        target = row.get("target_lambda", "")

        if not level.startswith("S"):
            continue

        groups[(level, target)].append(row)

    out_rows: list[dict[str, str]] = []

    for (level, target), items in sorted(groups.items(), key=sort_key):
        sent_delta: list[float] = []
        ok_delta: list[float] = []
        err_delta: list[float] = []
        achieved_tps: list[float] = []
        final_inflight: list[float] = []
        sample_inflight_max: list[float] = []
        sample_err_per_sec_max: list[float] = []
        sample_sent_per_sec_max: list[float] = []

        valid_runs = 0
        clean_runs = 0

        for row in items:
            sent = to_float(row.get("sent_delta", ""))
            ok = to_float(row.get("ok_delta", ""))
            err = to_float(row.get("err_delta", ""))
            duration = to_float(row.get("duration_seconds", ""))
            fin = to_float(row.get("final_inflight", ""))
            sim = to_float(row.get("sample_inflight_max", ""))
            sem = to_float(row.get("sample_err_per_sec_max", ""))
            ssm = to_float(row.get("sample_sent_per_sec_max", ""))

            if sent is not None:
                sent_delta.append(sent)
            if ok is not None:
                ok_delta.append(ok)
            if err is not None:
                err_delta.append(err)
            if fin is not None:
                final_inflight.append(fin)
            if sim is not None:
                sample_inflight_max.append(sim)
            if sem is not None:
                sample_err_per_sec_max.append(sem)
            if ssm is not None:
                sample_sent_per_sec_max.append(ssm)

            if ok is not None and duration and duration > 0:
                achieved_tps.append(ok / duration)

            if row.get("run_id", ""):
                valid_runs += 1

            if (
                row.get("err_delta", "") in {"", "0", "0.0"}
                and row.get("final_target_lambda", "") in {"", "0", "0.0"}
                and row.get("final_inflight", "") in {"", "0", "0.0"}
            ):
                clean_runs += 1

        out_rows.append({
            "load_level": level,
            "target_lambda": target,
            "run_count": str(len(items)),
            "valid_runs": str(valid_runs),
            "clean_runs": str(clean_runs),
            "sent_delta_mean": safe_mean(sent_delta),
            "sent_delta_std": safe_std(sent_delta),
            "ok_delta_mean": safe_mean(ok_delta),
            "ok_delta_std": safe_std(ok_delta),
            "err_delta_total": f"{sum(err_delta):.0f}" if err_delta else "",
            "final_inflight_mean": safe_mean(final_inflight),
            "sample_inflight_max": safe_max(sample_inflight_max),
            "sample_inflight_max_mean": safe_mean(sample_inflight_max),
            "sample_err_per_sec_max": safe_max(sample_err_per_sec_max),
            "sample_sent_per_sec_max": safe_max(sample_sent_per_sec_max),
            "achieved_tps_mean": safe_mean(achieved_tps),
            "achieved_tps_std": safe_std(achieved_tps),
        })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "load_level",
        "target_lambda",
        "run_count",
        "valid_runs",
        "clean_runs",
        "sent_delta_mean",
        "sent_delta_std",
        "ok_delta_mean",
        "ok_delta_std",
        "err_delta_total",
        "final_inflight_mean",
        "sample_inflight_max",
        "sample_inflight_max_mean",
        "sample_err_per_sec_max",
        "sample_sent_per_sec_max",
        "achieved_tps_mean",
        "achieved_tps_std",
    ]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"wrote {OUT_CSV}")
    print(f"groups={len(out_rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
