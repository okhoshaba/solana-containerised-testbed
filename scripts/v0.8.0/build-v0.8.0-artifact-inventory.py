#!/usr/bin/env python3
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


OUTPUT_JSON = Path("results/v0.8.0/summary/v0.8.0-artifact-inventory.json")
OUTPUT_MD = Path("results/v0.8.0/summary/v0.8.0-artifact-inventory.md")
OUTPUT_SHA256 = Path("results/v0.8.0/summary/v0.8.0-checksums.sha256")

OUTPUT_PATHS = {
    str(OUTPUT_JSON),
    str(OUTPUT_MD),
    str(OUTPUT_SHA256),
}

ROOT = Path(".")

TARGETS = [
    {
        "group": "raw_dataset",
        "description": "Raw experimental CSVs and commanded/applied load profiles.",
        "paths": [Path("data/raw/v0.8.0")],
    },
    {
        "group": "run_results",
        "description": "Per-run summaries, metadata, Kubernetes Job/Pod captures and derived run-level outputs.",
        "paths": [Path("results/v0.8.0/runs")],
    },
    {
        "group": "preflight_results",
        "description": "Per-run preflight reports and summaries.",
        "paths": [Path("results/v0.8.0/preflight")],
    },
    {
        "group": "aggregate_summaries",
        "description": "Aggregate summaries for M0-M4 and v0.8.0 dynamic identification.",
        "paths": [Path("results/v0.8.0/summary")],
    },
    {
        "group": "experiment_scripts",
        "description": "v0.8.0 runners, summarizers and aggregation scripts.",
        "paths": [Path("scripts/v0.8.0")],
    },
    {
        "group": "schemas",
        "description": "v0.8.0 metadata schemas.",
        "paths": [Path("schemas/v0.8.0")],
    },
    {
        "group": "examples",
        "description": "v0.8.0 metadata examples.",
        "paths": [Path("examples/v0.8.0")],
    },
    {
        "group": "experiment_docs",
        "description": "v0.8.0 experiment and run-matrix documentation.",
        "paths": [
            Path("docs/experiments/v0.8.0-dynamic-load-system-identification.md"),
            Path("docs/experiments/v0.8.0-run-matrix.md"),
        ],
    },
    {
        "group": "release_docs",
        "description": "v0.8.0 release documentation if present.",
        "paths": [Path("docs/releases")],
        "glob_filter": "*v0.8.0*",
    },
]


EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".swp",
    ".tmp",
}


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def is_excluded(path):
    rel = str(path)
    if rel in OUTPUT_PATHS:
        return True
    if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def iter_target_files(target):
    glob_filter = target.get("glob_filter")
    for base in target["paths"]:
        if not base.exists():
            continue

        if base.is_file():
            if not is_excluded(base):
                yield base
            continue

        if glob_filter:
            candidates = sorted(base.rglob(glob_filter))
        else:
            candidates = sorted(base.rglob("*"))

        for p in candidates:
            if p.is_file() and not is_excluded(p):
                yield p


def classify_file(path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".txt"}:
        return "text"
    if suffix in {".py", ".sh"}:
        return "script"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix == ".sha256":
        return "checksum"
    return suffix.lstrip(".") or "unknown"


def line_count_if_text(path):
    if path.suffix.lower() not in {".csv", ".json", ".md", ".txt", ".py", ".sh", ".yaml", ".yml"}:
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def main():
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    files = []
    seen = set()
    groups = {}

    for target in TARGETS:
        group = target["group"]
        groups[group] = {
            "description": target["description"],
            "file_count": 0,
            "size_bytes": 0,
        }

        for path in iter_target_files(target):
            rel = path.as_posix()
            if rel in seen:
                continue
            seen.add(rel)

            size = path.stat().st_size
            digest = sha256_file(path)
            kind = classify_file(path)
            lines = line_count_if_text(path)

            record = {
                "path": rel,
                "group": group,
                "kind": kind,
                "size_bytes": size,
                "sha256": digest,
                "line_count": lines,
            }
            files.append(record)

            groups[group]["file_count"] += 1
            groups[group]["size_bytes"] += size

    files.sort(key=lambda x: x["path"])

    totals = {
        "file_count": len(files),
        "size_bytes": sum(f["size_bytes"] for f in files),
        "csv_file_count": sum(1 for f in files if f["kind"] == "csv"),
        "json_file_count": sum(1 for f in files if f["kind"] == "json"),
        "script_file_count": sum(1 for f in files if f["kind"] == "script"),
        "markdown_file_count": sum(1 for f in files if f["kind"] == "text" and f["path"].endswith(".md")),
    }

    inventory = {
        "stage": "v0.8.0 dynamic load system identification",
        "purpose": "Artifact inventory and checksums for software and dataset publication.",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": {
            "includes": [
                "data/raw/v0.8.0",
                "results/v0.8.0/runs",
                "results/v0.8.0/preflight",
                "results/v0.8.0/summary",
                "scripts/v0.8.0",
                "schemas/v0.8.0",
                "examples/v0.8.0",
                "docs/experiments/v0.8.0-*",
                "docs/releases/*v0.8.0* if present",
            ],
            "excludes": [
                "self-referential inventory outputs",
                ".git",
                "__pycache__",
                "temporary/editor files",
            ],
        },
        "groups": groups,
        "totals": totals,
        "files": files,
    }

    OUTPUT_JSON.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")

    with OUTPUT_SHA256.open("w", encoding="utf-8") as f:
        for rec in files:
            f.write(f"{rec['sha256']}  {rec['path']}\n")

    md = []
    md.append("# v0.8.0 artifact inventory")
    md.append("")
    md.append(f"- generated_at_utc: {inventory['generated_at_utc']}")
    md.append(f"- stage: {inventory['stage']}")
    md.append(f"- total files: {totals['file_count']}")
    md.append(f"- total size bytes: {totals['size_bytes']}")
    md.append(f"- CSV files: {totals['csv_file_count']}")
    md.append(f"- JSON files: {totals['json_file_count']}")
    md.append(f"- script files: {totals['script_file_count']}")
    md.append("")
    md.append("## Groups")
    md.append("")
    md.append("| group | files | size bytes | description |")
    md.append("|---|---:|---:|---|")
    for group, g in groups.items():
        md.append(f"| {group} | {g['file_count']} | {g['size_bytes']} | {g['description']} |")
    md.append("")
    md.append("## Files")
    md.append("")
    md.append("| path | group | kind | size bytes | sha256 |")
    md.append("|---|---|---:|---:|---|")
    for rec in files:
        md.append(
            f"| `{rec['path']}` | {rec['group']} | {rec['kind']} | "
            f"{rec['size_bytes']} | `{rec['sha256']}` |"
        )
    md.append("")
    md.append("## Checksum file")
    md.append("")
    md.append(f"- `{OUTPUT_SHA256}`")
    md.append("")

    OUTPUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"inventory_json: {OUTPUT_JSON}")
    print(f"inventory_md: {OUTPUT_MD}")
    print(f"checksums_sha256: {OUTPUT_SHA256}")
    print(json.dumps(totals, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
