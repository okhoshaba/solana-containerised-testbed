#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "results" / "v0.7.0" / "raw"
OUT_CSV = ROOT / "results" / "v0.7.0" / "processed" / "v0.7.0-run-summary.csv"


FIELDNAMES = [
    "run_dir",
    "run_id",
    "stage",
    "load_level",
    "run_kind",
    "target_lambda",
    "duration_seconds",
    "sample_interval_seconds",
    "sample_count",
    "sent_initial",
    "sent_final",
    "sent_delta",
    "ok_initial",
    "ok_final",
    "ok_delta",
    "err_initial",
    "err_final",
    "err_delta",
    "final_target_lambda",
    "final_inflight",
    "final_last_err",
    "sample_inflight_max",
    "sample_err_per_sec_max",
    "sample_sent_per_sec_max",
    "completed_utc",
]


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}

    if not path.exists():
        return data

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()

    return data


def to_float(value: str) -> float:
    value = (value or "").strip()
    if value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def sample_maxima(path: Path) -> dict[str, str]:
    if not path.exists():
        return {
            "sample_inflight_max": "",
            "sample_err_per_sec_max": "",
            "sample_sent_per_sec_max": "",
        }

    inflight_values: list[float] = []
    err_per_sec_values: list[float] = []
    sent_per_sec_values: list[float] = []

    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)

        for row in reader:
            inflight_values.append(to_float(row.get("inflight", "")))
            err_per_sec_values.append(to_float(row.get("err_per_sec", "")))
            sent_per_sec_values.append(to_float(row.get("sent_per_sec", "")))

    def fmt(values: list[float]) -> str:
        if not values:
            return ""
        value = max(values)
        if value.is_integer():
            return str(int(value))
        return f"{value:.6f}"

    return {
        "sample_inflight_max": fmt(inflight_values),
        "sample_err_per_sec_max": fmt(err_per_sec_values),
        "sample_sent_per_sec_max": fmt(sent_per_sec_values),
    }


def main() -> int:
    rows: list[dict[str, str]] = []

    for run_dir in sorted(RAW_DIR.glob("v0.7.0_*")):
        if not run_dir.is_dir():
            continue

        combined = read_env(run_dir / "summary" / "combined-summary.env")
        run_env = read_env(run_dir / "summary" / "run.env")
        metadata = read_env(run_dir / "metadata.env")
        maxima = sample_maxima(run_dir / "loadgen" / "stats_samples.csv")

        merged: dict[str, str] = {}
        merged.update(metadata)
        merged.update(run_env)
        merged.update(combined)
        merged.update(maxima)

        row = {field: merged.get(field, "") for field in FIELDNAMES}
        row["run_dir"] = run_dir.name

        rows.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {OUT_CSV}")
    print(f"rows={len(rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
