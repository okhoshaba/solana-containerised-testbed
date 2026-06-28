#!/usr/bin/env python3
"""
v0.15.0 MPC controller preparation.

This stage prepares a formal offline MPC problem specification.
It does not implement MPC and does not claim MPC superiority over the
v0.14.3 fixed P-only baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def load_json(path: str | Path) -> Any:
    p = repo_path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, obj: Any) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def write_text(path: str | Path, text: str) -> None:
    p = repo_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def require_file(path: str | Path) -> Path:
    p = repo_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {p}")
    return p


def top_level_summary(path: str | Path) -> Dict[str, Any]:
    p = require_file(path)
    data = load_json(p)
    if isinstance(data, dict):
        return {
            "path": str(Path(path)),
            "exists": True,
            "top_level_keys": sorted(str(k) for k in data.keys())[:40],
            "stage": data.get("stage"),
            "experiment": data.get("experiment"),
            "title": data.get("title")
        }
    return {
        "path": str(Path(path)),
        "exists": True,
        "type": type(data).__name__
    }


def validate_baseline(config: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    expected = config["reference_baseline"]["candidate_id"]
    selected = baseline.get("selected_candidate", {})
    decision = baseline.get("decision", {})

    checks = {
        "stage_is_v0_14_3": baseline.get("stage") == "v0.14.3",
        "candidate_count_is_one": baseline.get("candidate_count") == 1,
        "candidate_id_matches_config": selected.get("candidate_id") == expected,
        "effective_controller_is_p_only": selected.get("effective_controller") == "p_only",
        "accepted_as_reference_baseline_for_mpc": decision.get("accepted_as_reference_baseline_for_mpc") is True,
        "decision_status_pass": decision.get("status") == "pass"
    }

    return {
        "expected_candidate_id": expected,
        "observed_candidate_id": selected.get("candidate_id"),
        "effective_controller": selected.get("effective_controller"),
        "decision_status": decision.get("status"),
        "accepted_as_reference_baseline_for_mpc": decision.get("accepted_as_reference_baseline_for_mpc"),
        "checks": checks,
        "valid": all(checks.values())
    }


def requirement_status(config: Dict[str, Any], baseline_validation: Dict[str, Any]) -> List[Dict[str, Any]]:
    formulation = config.get("mpc_problem_formulation", {})
    protocol = config.get("offline_validation_protocol", {})

    return [
        {
            "requirement": "source artefacts exist",
            "status": "pass"
        },
        {
            "requirement": "v0.14.3 baseline is accepted as MPC reference",
            "status": "pass" if baseline_validation["valid"] else "fail"
        },
        {
            "requirement": "MPC variables are specified",
            "status": "pass" if formulation.get("controlled_output") and formulation.get("manipulated_input") else "fail"
        },
        {
            "requirement": "MPC objective terms are specified",
            "status": "pass" if formulation.get("objective_terms") else "fail"
        },
        {
            "requirement": "MPC constraints are specified",
            "status": "pass" if formulation.get("constraint_classes") else "fail"
        },
        {
            "requirement": "offline validation protocol is specified",
            "status": "pass" if protocol.get("required_future_metrics") and protocol.get("comparison_principle") else "fail"
        }
    ]


def decide(requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [r for r in requirements if r["status"] != "pass"]
    if failed:
        return {
            "status": "blocked",
            "ready_for_offline_mpc_prototype": False,
            "reason": "One or more MPC preparation requirements are not satisfied.",
            "failed_requirements": failed
        }

    return {
        "status": "ready_for_offline_mpc_prototype",
        "ready_for_offline_mpc_prototype": True,
        "reason": "All preparation requirements are satisfied. The next stage may implement an offline MPC prototype without making live-system claims."
    }


def write_readme(path: str | Path, summary: Dict[str, Any]) -> None:
    cfg = summary["config"]
    ref = cfg["reference_baseline"]
    formulation = cfg["mpc_problem_formulation"]
    protocol = cfg["offline_validation_protocol"]
    decision = summary["decision"]

    text = f"""# v0.15.0 MPC controller preparation

## Purpose

This stage prepares a formal offline MPC problem specification before implementing MPC or claiming MPC performance.

It is a preparation stage only.

## Non-goals

- It does not implement a production Kubernetes controller.
- It does not claim MPC superiority over the v0.14.3 baseline.
- It does not run live closed-loop experiments.
- It does not retune the v0.14.3 PID/P-only baseline.

## Reference baseline

- Source stage: {ref["source_stage"]}
- Candidate: {ref["candidate_id"]}
- Effective controller: {ref["effective_controller"]}
- kp: {ref["kp"]}
- ki: {ref["ki"]}
- kd: {ref["kd"]}
- Role: {ref["role"]}

Future MPC work must compare against this fixed baseline rather than a moving PID target.

## MPC problem formulation

- Controlled output: {formulation["controlled_output"]}
- Manipulated input: {formulation["manipulated_input"]}
- State representation: {formulation["state_representation"]}

Prediction horizon candidates:

- {formulation["prediction_horizon_candidates"]}

Control horizon candidates:

- {formulation["control_horizon_candidates"]}

Objective terms:

{chr(10).join("- " + item for item in formulation["objective_terms"])}

Constraint classes:

{chr(10).join("- " + item for item in formulation["constraint_classes"])}

## Offline validation protocol

Mode: {protocol["mode"]}

Comparison principle:

{protocol["comparison_principle"]}

Required future metrics:

{chr(10).join("- " + item for item in protocol["required_future_metrics"])}

## Decision

- Status: {decision["status"]}
- Ready for offline MPC prototype: {decision["ready_for_offline_mpc_prototype"]}

Reason: {decision["reason"]}

## Next step

Implement an offline MPC prototype stage that uses this specification and compares against the fixed v0.14.3 P-only baseline.
"""
    write_text(path, text)


def write_experiment_doc(path: str | Path, summary: Dict[str, Any]) -> None:
    cfg = summary["config"]
    formulation = cfg["mpc_problem_formulation"]
    protocol = cfg["offline_validation_protocol"]
    decision = summary["decision"]

    text = f"""# v0.15.0 MPC controller preparation

## Purpose

v0.15.0 defines the preparation layer for Model Predictive Control in the Solana Containerised Testbed throughput-control research line.

The stage intentionally stops before implementing MPC. Its purpose is to define the MPC problem, required constraints, objective terms, and comparison protocol.

## Scientific rationale

The project now has a fixed reference baseline from v0.14.3:

    p_kp0.350_ki0.000_kd0.000

This baseline is effectively P-only and has been accepted as a reference controller before MPC. Therefore, MPC should not be evaluated against an abstract PID family. It should be evaluated against this concrete fixed controller.

## MPC variables

Controlled output:

    {formulation["controlled_output"]}

Manipulated input:

    {formulation["manipulated_input"]}

State representation:

    {formulation["state_representation"]}

## Horizons

Prediction horizon candidates:

    {formulation["prediction_horizon_candidates"]}

Control horizon candidates:

    {formulation["control_horizon_candidates"]}

Preliminary initial horizon policy:

    prediction horizon = {formulation["preliminary_horizon_policy"]["initial_prediction_horizon"]}
    control horizon = {formulation["preliminary_horizon_policy"]["initial_control_horizon"]}

## Objective function terms

The future MPC prototype should include:

{chr(10).join("- " + item for item in formulation["objective_terms"])}

The precise weights are not claimed in this stage. They must be selected or swept in a later offline prototype stage.

## Constraint classes

The future MPC prototype should represent:

{chr(10).join("- " + item for item in formulation["constraint_classes"])}

These constraints should be derived from the offline simulator, calibrated transient-aware interpretation, and safety policy already used in v0.14.x.

## Offline validation protocol

This stage specifies that future MPC candidates must be compared against the v0.14.3 fixed P-only baseline.

Required metrics include:

{chr(10).join("- " + item for item in protocol["required_future_metrics"])}

The future MPC result should report trade-offs, not only improvements. For example, a lower settled RMSE may not be sufficient if rate-limit behaviour or safety classification worsens.

## Decision

Status:

    {decision["status"]}

Reason:

    {decision["reason"]}

## Interpretation

v0.15.0 does not prove MPC performance. It only establishes that the project is ready to build an offline MPC prototype using a specified problem formulation and a fixed reference baseline.

## Recommended next stage

The recommended next stage is v0.15.1 offline MPC prototype skeleton.
"""
    write_text(path, text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    config = load_json(args.config)
    sources = config["source_artifacts"]
    outputs = config["preparation_outputs"]

    source_summaries = {
        name: top_level_summary(path)
        for name, path in sources.items()
    }

    baseline = load_json(sources["v0_14_3_baseline_summary_path"])
    baseline_validation = validate_baseline(config, baseline)

    requirements = requirement_status(config, baseline_validation)
    decision = decide(requirements)

    summary = {
        "stage": config["stage"],
        "experiment": config["experiment"],
        "title": config["title"],
        "offline_only": True,
        "purpose": config["purpose"],
        "config_path": args.config,
        "config": config,
        "source_summaries": source_summaries,
        "baseline_validation": baseline_validation,
        "requirements": requirements,
        "decision": decision,
        "outputs": outputs
    }

    write_json(outputs["summary_json"], summary)
    write_readme(outputs["readme_md"], summary)
    write_experiment_doc(outputs["experiment_doc"], summary)

    print(json.dumps({
        "stage": summary["stage"],
        "decision": decision["status"],
        "ready_for_offline_mpc_prototype": decision["ready_for_offline_mpc_prototype"],
        "reference_baseline": config["reference_baseline"]["candidate_id"],
        "effective_controller": config["reference_baseline"]["effective_controller"]
    }, indent=2))


if __name__ == "__main__":
    main()
