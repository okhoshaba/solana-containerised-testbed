#!/usr/bin/env python3
"""
v0.12.0 closed-loop readiness review.

This script is intentionally offline-only.

It does not:
- start a live controller;
- call kubectl;
- modify Kubernetes;
- generate transaction load;
- perform a closed-loop experiment.

It checks whether the repository contains enough prior artefacts to justify
moving from offline controller work toward a bounded, supervised, limited
live closed-loop experiment.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSION = "v0.12.0"
STAGE = "closed-loop readiness review"

OUT_DIR = Path("results/v0.12.0/closed-loop-readiness-review")
OUT_JSON = OUT_DIR / "readiness-review.json"


@dataclass(frozen=True)
class ArtefactCheck:
    name: str
    path_or_glob: str
    category: str
    required: bool = True


ARTEFACTS = [
    ArtefactCheck("v0.8.0 experiment documentation", "docs/experiments/v0.8.0*", "artefact_readiness"),
    ArtefactCheck("v0.9.0 experiment documentation", "docs/experiments/v0.9.0*", "modelling_readiness"),
    ArtefactCheck("v0.10.0 controller-preparation documentation", "docs/experiments/v0.10.0*", "safety_readiness"),
    ArtefactCheck("v0.11.0 controller-prototype documentation", "docs/experiments/v0.11.0*", "controller_simulation_readiness"),

    ArtefactCheck("v0.8.0 result directory", "results/v0.8.0", "artefact_readiness"),
    ArtefactCheck("v0.9.0 result directory", "results/v0.9.0", "modelling_readiness"),
    ArtefactCheck("v0.10.0 result directory", "results/v0.10.0", "safety_readiness"),
    ArtefactCheck("v0.11.0 result directory", "results/v0.11.0", "controller_simulation_readiness"),

    ArtefactCheck("v0.11.0 scripts directory", "scripts/v0.11.0", "controller_simulation_readiness"),
    ArtefactCheck(
        "offline controller safety checks JSON",
        "results/v0.11.0/controller-prototype/offline-controller-safety-checks.json",
        "safety_readiness",
    ),
    ArtefactCheck(
        "offline controller safety checks report",
        "results/v0.11.0/controller-prototype/offline-controller-safety-checks.md",
        "safety_readiness",
    ),

    ArtefactCheck("observability documentation", "docs/experiments/v0.4.0*", "observability_readiness", required=False),
    ArtefactCheck("controlled-load documentation", "docs/experiments/v0.6.0*", "observability_readiness", required=False),
    ArtefactCheck("saturation analysis documentation", "docs/experiments/v0.7.0*", "observability_readiness", required=False),

    ArtefactCheck("live closed-loop runbook", "docs/runbooks/*closed-loop*live*", "operational_readiness", required=False),
    ArtefactCheck("manual abort procedure", "docs/runbooks/*abort*", "operational_readiness", required=False),
    ArtefactCheck("rollback procedure", "docs/runbooks/*rollback*", "operational_readiness", required=False),
]


def repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(result.stdout.strip())
    except Exception:
        return Path.cwd()


def matches(root: Path, pattern: str) -> list[str]:
    candidate = root / pattern
    if any(ch in pattern for ch in "*?[]"):
        return sorted(str(p.relative_to(root)) for p in root.glob(pattern))
    if candidate.exists():
        return [pattern]
    return []


def status_from_score(score: float, required_missing: int) -> str:
    if required_missing > 0:
        return "FAIL"
    if score >= 0.85:
        return "PASS"
    if score >= 0.5:
        return "WARN"
    return "FAIL"


def category_summary(checked: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, list[dict[str, Any]]] = {}
    for item in checked:
        categories.setdefault(item["category"], []).append(item)

    summary: dict[str, Any] = {}
    for category, items in categories.items():
        required_items = [i for i in items if i["required"]]
        required_present = [i for i in required_items if i["exists"]]
        required_missing = [i for i in required_items if not i["exists"]]

        optional_items = [i for i in items if not i["required"]]
        optional_present = [i for i in optional_items if i["exists"]]

        required_score = (
            len(required_present) / len(required_items)
            if required_items
            else 1.0
        )
        optional_score = (
            len(optional_present) / len(optional_items)
            if optional_items
            else 1.0
        )

        if required_items:
            score = required_score
        else:
            score = optional_score

        summary[category] = {
            "status": status_from_score(score, len(required_missing)),
            "required_present": len(required_present),
            "required_total": len(required_items),
            "optional_present": len(optional_present),
            "optional_total": len(optional_items),
            "score": round(score, 3),
            "missing_required": [i["path_or_glob"] for i in required_missing],
            "missing_optional": [i["path_or_glob"] for i in optional_items if not i["exists"]],
        }

    for expected in [
        "artefact_readiness",
        "modelling_readiness",
        "controller_simulation_readiness",
        "safety_readiness",
        "observability_readiness",
        "operational_readiness",
        "reproducibility_readiness",
    ]:
        summary.setdefault(
            expected,
            {
                "status": "WARN" if expected in {"observability_readiness", "operational_readiness", "reproducibility_readiness"} else "FAIL",
                "required_present": 0,
                "required_total": 0,
                "optional_present": 0,
                "optional_total": 0,
                "score": 0.0,
                "missing_required": [],
                "missing_optional": [],
            },
        )

    return summary


def determine_decision(summary: dict[str, Any]) -> tuple[str, list[str]]:
    artefact_ok = summary["artefact_readiness"]["status"] in {"PASS", "WARN"}
    model_ok = summary["modelling_readiness"]["status"] == "PASS"
    simulation_ok = summary["controller_simulation_readiness"]["status"] == "PASS"
    safety_ok = summary["safety_readiness"]["status"] == "PASS"

    operational_score = summary["operational_readiness"]["score"]
    observability_status = summary["observability_readiness"]["status"]

    rationale: list[str] = []

    if artefact_ok:
        rationale.append("Prior research artefacts are present sufficiently for a review gate.")
    else:
        rationale.append("Prior research artefacts are incomplete.")

    if model_ok:
        rationale.append("Offline modelling artefacts are present.")
    else:
        rationale.append("Offline modelling artefacts are incomplete or missing.")

    if simulation_ok:
        rationale.append("Controller simulation/prototype artefacts are present.")
    else:
        rationale.append("Controller simulation/prototype artefacts are incomplete or missing.")

    if safety_ok:
        rationale.append("Offline controller safety-check artefacts are present.")
    else:
        rationale.append("Offline controller safety-check artefacts are incomplete or missing.")

    if observability_status in {"PASS", "WARN"}:
        rationale.append("Observability-related prior documentation is at least partially represented.")
    else:
        rationale.append("Observability readiness is weak and must be reviewed before live control.")

    if operational_score < 1.0:
        rationale.append("Live runbook, manual abort, or rollback documentation is not fully represented.")

    if not (artefact_ok and model_ok and simulation_ok and safety_ok):
        return "NO_GO", rationale

    if operational_score < 1.0:
        return "CONDITIONAL_GO_FOR_LIMITED_LIVE", rationale

    return "GO_FOR_LIMITED_LIVE", rationale


def main() -> int:
    root = repo_root()
    checked: list[dict[str, Any]] = []

    for artefact in ARTEFACTS:
        found = matches(root, artefact.path_or_glob)
        checked.append(
            {
                "name": artefact.name,
                "path_or_glob": artefact.path_or_glob,
                "category": artefact.category,
                "required": artefact.required,
                "exists": bool(found),
                "matches": found,
            }
        )

    summary = category_summary(checked)

    # Reproducibility is not tied to one specific file here. It is inferred from
    # the presence of versioned docs, versioned results, and this offline checker.
    reproducibility_score = 1.0 if (
        summary["artefact_readiness"]["status"] in {"PASS", "WARN"}
        and summary["modelling_readiness"]["status"] == "PASS"
        and summary["controller_simulation_readiness"]["status"] == "PASS"
        and summary["safety_readiness"]["status"] == "PASS"
    ) else 0.5

    summary["reproducibility_readiness"] = {
        "status": "PASS" if reproducibility_score == 1.0 else "WARN",
        "score": reproducibility_score,
        "basis": "Versioned documentation, versioned results, and an offline checker are present.",
    }

    decision, decision_rationale = determine_decision(summary)

    required_preconditions = [
        "Define a maximum transaction-generation rate for the live experiment.",
        "Define minimum and maximum controller output bounds.",
        "Define a controller output rate limit.",
        "Define a controller cooldown interval.",
        "Define a manual abort command and test it before the experiment.",
        "Define automatic abort thresholds.",
        "Define a maximum experiment duration.",
        "Confirm metric capture before enabling live control.",
        "Document rollback procedure.",
        "Document post-run audit procedure.",
    ]

    safety_constraints = [
        "The controller output must be clamped.",
        "The controller must fail closed, not fail open.",
        "The controller must not increase load after telemetry loss.",
        "The first live experiment must be short-duration and supervised.",
        "The first live experiment must use conservative actuator limits.",
        "The first live experiment must not be treated as production-like autonomous control.",
    ]

    abort_conditions = [
        "Validator health becomes degraded or unavailable.",
        "RPC error rate exceeds the configured threshold.",
        "p95 or p99 transaction latency exceeds the configured threshold.",
        "Pod restart count increases unexpectedly.",
        "CPU or memory saturation exceeds the configured threshold.",
        "Ledger growth rate exceeds the configured threshold.",
        "Telemetry is missing, stale, or internally inconsistent.",
        "Controller output attempts to exceed configured bounds.",
    ]

    observability_requirements = [
        "Validator health metrics must be visible before controller activation.",
        "RPC latency and error metrics must be captured.",
        "Transaction-generation rate must be captured.",
        "Controller input, output, setpoint, error, and saturation state must be logged.",
        "Pod restart and resource saturation metrics must be captured.",
        "Experiment start, abort, rollback, and end timestamps must be recorded.",
    ]

    missing_or_weak_items = []
    for category, data in summary.items():
        status = data.get("status")
        if status in {"WARN", "FAIL"}:
            missing_or_weak_items.append(
                {
                    "category": category,
                    "status": status,
                    "missing_required": data.get("missing_required", []),
                    "missing_optional": data.get("missing_optional", []),
                }
            )

    review = {
        "version": VERSION,
        "stage": STAGE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "live_controller_started": False,
        "kubernetes_modified": False,
        "review_only": True,
        "decision": decision,
        "decision_rationale": decision_rationale,
        "readiness_dimensions": summary,
        "checked_artefacts": checked,
        "missing_or_weak_items": missing_or_weak_items,
        "required_preconditions_for_live_experiment": required_preconditions,
        "recommended_next_stage": (
            "v0.13.0 closed-loop shadow-mode controller validation"
            if decision in {"CONDITIONAL_GO_FOR_LIMITED_LIVE", "GO_FOR_LIMITED_LIVE"}
            else "address missing offline readiness artefacts before live telemetry or live control"
        ),
        "safety_constraints": safety_constraints,
        "abort_conditions": abort_conditions,
        "observability_requirements": observability_requirements,
        "reproducibility_notes": [
            "This review is generated by an offline script.",
            "The script does not call kubectl or modify the cluster.",
            "The JSON output should be committed together with the review documentation.",
            "The review result should be treated as a gate, not as a live experiment result.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Decision: {decision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
