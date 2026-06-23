#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "results" / "v0.6.0" / "raw"
OUT_DIR = ROOT / "results" / "v0.6.0" / "processed"
OUT_CSV = OUT_DIR / "v0.6.0-run-summary.csv"


FIELDS = [
    "run_dir",
    "run_id",
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
    "completed_utc",
]


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()

    return data


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []

    for run_dir in sorted(RAW_DIR.iterdir()):
        if not run_dir.is_dir():
            continue

        combined = parse_env_file(run_dir / "summary" / "combined-summary.env")
        run_env = parse_env_file(run_dir / "summary" / "run.env")
        metadata = parse_env_file(run_dir / "metadata.env")

        merged: dict[str, str] = {}
        merged.update(metadata)
        merged.update(run_env)
        merged.update(combined)

        if not merged:
            continue

        row = {field: merged.get(field, "") for field in FIELDS}
        row["run_dir"] = str(run_dir.relative_to(ROOT))
        row["run_id"] = row["run_id"] or run_dir.name
        rows.append(row)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {OUT_CSV}")
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
