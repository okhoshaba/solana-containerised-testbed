#!/usr/bin/env python3

import argparse
import csv
import json
import math
from pathlib import Path


def load_json(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required JSON file is missing: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
        f.write("\n")


def require_file(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Required file is missing: {path}")
    return p


def finite_or_none(x):
    if x is None:
        return None
    try:
        y = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(y):
        return None
    return y


def target_at_step(profile, k):
    ptype = profile["type"]

    if ptype == "constant":
        return float(profile["target"])

    if ptype == "step":
        if k < int(profile["change_step"]):
            return float(profile["initial_target"])
        return float(profile["target"])

    if ptype == "multistep":
        current = float(profile["segments"][0]["target"])
        for segment in profile["segments"]:
            if k >= int(segment["start"]):
                current = float(segment["target"])
            else:
                break
        return current

    if ptype == "sine":
        base = float(profile["base"])
        amplitude = float(profile["amplitude"])
        period_steps = float(profile["period_steps"])
        return base + amplitude * math.sin(2.0 * math.pi * float(k) / period_steps)

    raise ValueError(f"Unsupported profile type: {ptype}")


def equilibrium_command(model, target):
    a_y = float(model["a_y"])
    b_u = float(model["b_u"])
    c = float(model.get("c", 0.0))
    denom = a_y + b_u

    if abs(denom) > 1e-12:
        return (target - c) / denom

    if abs(b_u) > 1e-12:
        return (target - c) / b_u

    return float(model.get("u_eq", target))


def inverse_command(model, current_y, target_next_y):
    a_y = float(model["a_y"])
    b_u = float(model["b_u"])
    c = float(model.get("c", 0.0))

    if abs(b_u) <= 1e-12:
        return equilibrium_command(model, target_next_y)

    return (target_next_y - c - a_y * current_y) / b_u


def apply_limits(raw_u, previous_u, safety):
    action_min = float(safety["action_min"])
    action_max = float(safety["action_max"])
    max_step_change = safety.get("max_step_change")

    limited_by_rate = False
    limited_by_bounds = False

    u = float(raw_u)

    if max_step_change is not None and previous_u is not None:
        max_delta = abs(float(max_step_change))
        delta = u - previous_u
        if delta > max_delta:
            u = previous_u + max_delta
            limited_by_rate = True
        elif delta < -max_delta:
            u = previous_u - max_delta
            limited_by_rate = True

    if u < action_min:
        u = action_min
        limited_by_bounds = True
    elif u > action_max:
        u = action_max
        limited_by_bounds = True

    return u, limited_by_rate, limited_by_bounds


def simulate_case(model, controller, profile, config):
    steps = int(config["simulation_policy"]["steps_per_profile"])
    dt = float(config["simulation_policy"]["dt_seconds"])
    safety = config["safety_policy"]

    a_y = float(model["a_y"])
    b_u = float(model["b_u"])
    c = float(model.get("c", 0.0))
    delay_steps = int(model.get("delay_steps", 0))

    initial_y = finite_or_none(profile.get("initial_y"))
    if initial_y is None:
        initial_y = finite_or_none(model.get("y_eq"))
    if initial_y is None:
        initial_y = 0.0

    y = initial_y
    previous_u = equilibrium_command(model, target_at_step(profile, 0))
    integral = 0.0
    command_history = []

    rows = []
    errors = []
    abs_errors = []
    command_changes = []

    saturation_count = 0
    rate_limit_count = 0
    anti_windup_freeze_count = 0
    non_finite_count = 0

    for k in range(steps):
        target = target_at_step(profile, k)
        error_before = target - y

        candidate_integral = integral + error_before * dt

        ctype = controller["type"]
        kp = float(controller.get("kp", 0.0))
        ki = float(controller.get("ki", 0.0))

        if ctype == "feedforward_inverse":
            raw_u = inverse_command(model, y, target)
        elif ctype == "p_with_equilibrium_feedforward":
            raw_u = equilibrium_command(model, target) + kp * error_before
        elif ctype == "pi_with_equilibrium_feedforward":
            raw_u = equilibrium_command(model, target) + kp * error_before + ki * candidate_integral
        else:
            raise ValueError(f"Unsupported controller type: {ctype}")

        u_cmd, limited_by_rate, limited_by_bounds = apply_limits(raw_u, previous_u, safety)

        if limited_by_bounds:
            saturation_count += 1

        if limited_by_rate:
            rate_limit_count += 1

        if controller.get("anti_windup", False) and limited_by_bounds:
            anti_windup_freeze_count += 1
        else:
            integral = candidate_integral

        command_history.append(u_cmd)

        if delay_steps <= 0:
            delayed_u = u_cmd
        else:
            delayed_index = len(command_history) - 1 - delay_steps
            if delayed_index < 0:
                delayed_u = command_history[0]
            else:
                delayed_u = command_history[delayed_index]

        y_next = c + a_y * y + b_u * delayed_u

        if not math.isfinite(y_next):
            non_finite_count += 1
            y_next = y

        error_after = target - y_next

        errors.append(error_after)
        abs_errors.append(abs(error_after))
        command_changes.append(abs(u_cmd - previous_u))

        rows.append({
            "profile": profile["name"],
            "controller_case": controller["name"],
            "step": k,
            "time_seconds": k * dt,
            "target": target,
            "y_before": y,
            "error_before": error_before,
            "raw_u": raw_u,
            "u_cmd": u_cmd,
            "delayed_u": delayed_u,
            "y_after": y_next,
            "error_after": error_after,
            "limited_by_rate": limited_by_rate,
            "limited_by_bounds": limited_by_bounds,
            "anti_windup_frozen": bool(controller.get("anti_windup", False) and limited_by_bounds),
            "actuator_applied": False
        })

        previous_u = u_cmd
        y = y_next

    n = len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / n) if n else None
    mae = sum(abs_errors) / n if n else None
    mean_error = sum(errors) / n if n else None
    final_error = errors[-1] if errors else None
    max_abs_error = max(abs_errors) if abs_errors else None
    mean_abs_command_change = sum(command_changes) / len(command_changes) if command_changes else None
    max_abs_command_change = max(command_changes) if command_changes else None
    saturation_fraction = saturation_count / n if n else None
    rate_limit_fraction = rate_limit_count / n if n else None
    anti_windup_fraction = anti_windup_freeze_count / n if n else None

    metrics = {
        "count": n,
        "rmse": rmse,
        "mae": mae,
        "mean_error": mean_error,
        "final_error": final_error,
        "max_abs_error": max_abs_error,
        "mean_abs_command_change": mean_abs_command_change,
        "max_abs_command_change": max_abs_command_change,
        "saturation_count": saturation_count,
        "saturation_fraction": saturation_fraction,
        "rate_limit_count": rate_limit_count,
        "rate_limit_fraction": rate_limit_fraction,
        "anti_windup_freeze_count": anti_windup_freeze_count,
        "anti_windup_freeze_fraction": anti_windup_fraction,
        "non_finite_count": non_finite_count
    }

    status, reasons = classify_case(metrics, config["safety_policy"])

    return {
        "profile": profile["name"],
        "controller_case": controller["name"],
        "status": status,
        "reasons": reasons,
        "metrics": metrics,
        "rows": rows
    }


def classify_case(metrics, safety):
    reasons = []

    if metrics["non_finite_count"] > 0:
        reasons.append("non_finite_count > 0")

    if metrics["rmse"] is not None and metrics["rmse"] > float(safety["fail_rmse"]):
        reasons.append("rmse > fail_rmse")

    if metrics["max_abs_error"] is not None and metrics["max_abs_error"] > float(safety["fail_max_abs_error"]):
        reasons.append("max_abs_error > fail_max_abs_error")

    if metrics["saturation_fraction"] is not None and metrics["saturation_fraction"] > float(safety["fail_saturation_fraction"]):
        reasons.append("saturation_fraction > fail_saturation_fraction")

    if reasons:
        return "FAIL", reasons

    warn_reasons = []

    if metrics["rmse"] is not None and metrics["rmse"] > float(safety["warn_rmse"]):
        warn_reasons.append("rmse > warn_rmse")

    if metrics["max_abs_error"] is not None and metrics["max_abs_error"] > float(safety["warn_max_abs_error"]):
        warn_reasons.append("max_abs_error > warn_max_abs_error")

    if metrics["saturation_fraction"] is not None and metrics["saturation_fraction"] > float(safety["warn_saturation_fraction"]):
        warn_reasons.append("saturation_fraction > warn_saturation_fraction")

    if warn_reasons:
        return "WARN", warn_reasons

    return "PASS", ["no safety warnings or failures"]


def aggregate_controller_ranking(case_results):
    by_controller = {}

    for result in case_results:
        name = result["controller_case"]
        by_controller.setdefault(name, {
            "controller_case": name,
            "case_count": 0,
            "pass_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "rmse_values": [],
            "mae_values": [],
            "saturation_values": [],
            "max_abs_error_values": []
        })

        item = by_controller[name]
        item["case_count"] += 1

        if result["status"] == "PASS":
            item["pass_count"] += 1
        elif result["status"] == "WARN":
            item["warn_count"] += 1
        elif result["status"] == "FAIL":
            item["fail_count"] += 1

        m = result["metrics"]

        if m["rmse"] is not None:
            item["rmse_values"].append(m["rmse"])
        if m["mae"] is not None:
            item["mae_values"].append(m["mae"])
        if m["saturation_fraction"] is not None:
            item["saturation_values"].append(m["saturation_fraction"])
        if m["max_abs_error"] is not None:
            item["max_abs_error_values"].append(m["max_abs_error"])

    ranking = []

    for item in by_controller.values():
        avg_rmse = sum(item["rmse_values"]) / len(item["rmse_values"]) if item["rmse_values"] else None
        avg_mae = sum(item["mae_values"]) / len(item["mae_values"]) if item["mae_values"] else None
        avg_saturation = sum(item["saturation_values"]) / len(item["saturation_values"]) if item["saturation_values"] else None
        worst_max_abs_error = max(item["max_abs_error_values"]) if item["max_abs_error_values"] else None

        ranking.append({
            "controller_case": item["controller_case"],
            "case_count": item["case_count"],
            "pass_count": item["pass_count"],
            "warn_count": item["warn_count"],
            "fail_count": item["fail_count"],
            "average_rmse": avg_rmse,
            "average_mae": avg_mae,
            "average_saturation_fraction": avg_saturation,
            "worst_max_abs_error": worst_max_abs_error
        })

    ranking.sort(key=lambda x: (
        x["fail_count"],
        x["warn_count"],
        x["average_rmse"] if x["average_rmse"] is not None else float("inf"),
        x["average_saturation_fraction"] if x["average_saturation_fraction"] is not None else float("inf"),
        x["controller_case"]
    ))

    for idx, item in enumerate(ranking, start=1):
        item["rank"] = idx

    return ranking


def decide_overall(case_results, thresholds):
    fail_count = sum(1 for r in case_results if r["status"] == "FAIL")
    warn_count = sum(1 for r in case_results if r["status"] == "WARN")
    pass_count = sum(1 for r in case_results if r["status"] == "PASS")

    if fail_count > int(thresholds["maximum_fail_cases_for_pass"]):
        status = "fail"
        reason = "At least one simulated controller/profile case failed configured safety thresholds."
        accepted = False
    elif warn_count <= int(thresholds["maximum_warn_cases_for_pass"]):
        status = "pass"
        reason = "All simulated controller/profile cases passed configured safety thresholds."
        accepted = True
    elif warn_count <= int(thresholds["maximum_warn_cases_for_caution"]):
        status = "caution"
        reason = "Simulator ran successfully, but some controller/profile cases produced warnings."
        accepted = True
    else:
        status = "fail"
        reason = "Too many controller/profile cases produced warnings."
        accepted = False

    return {
        "status": status,
        "reason": reason,
        "case_counts": {
            "PASS": pass_count,
            "WARN": warn_count,
            "FAIL": fail_count
        },
        "accepted_as_initial_offline_controller_simulator": accepted,
        "recommended_next_step": (
            "Review controller-ranking.json and simulation-timeseries.csv, then create a follow-up calibration or PID/MPC comparison stage."
        )
    }


def write_timeseries(path, rows):
    fieldnames = [
        "profile",
        "controller_case",
        "step",
        "time_seconds",
        "target",
        "y_before",
        "error_before",
        "raw_u",
        "u_cmd",
        "delayed_u",
        "y_after",
        "error_after",
        "limited_by_rate",
        "limited_by_bounds",
        "anti_windup_frozen",
        "actuator_applied"
    ]

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_readme(path, summary, ranking):
    lines = []
    lines.append("# v0.14.0 offline controller simulator with selected recursive model")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This stage creates an offline controller simulator using the v0.13.6 selected recursive model, accepted by v0.13.7 as the candidate surrogate plant model.")
    lines.append("")
    lines.append("This is not a live Kubernetes or validator controller. No actuator is applied to a live system.")
    lines.append("")
    lines.append("## Plant model")
    lines.append("")
    model = summary["plant_model"]
    lines.append(f"- source: `{model['source_path']}`")
    lines.append(f"- equation: `{summary['simulation_policy']['plant_equation']}`")
    lines.append(f"- a_y: `{model['a_y']}`")
    lines.append(f"- b_u: `{model['b_u']}`")
    lines.append(f"- c: `{model['c']}`")
    lines.append(f"- delay_steps: `{model['delay_steps']}`")
    lines.append("")
    lines.append("## Controller cases")
    lines.append("")
    for controller in summary["controller_cases"]:
        lines.append(f"- `{controller['name']}`: {controller['type']}")
    lines.append("")
    lines.append("## Profiles")
    lines.append("")
    for profile in summary["profiles"]:
        lines.append(f"- `{profile['name']}`: {profile['type']}")
    lines.append("")
    lines.append("## Controller ranking")
    lines.append("")
    lines.append("| rank | controller | cases | pass | warn | fail | avg RMSE | avg MAE | avg saturation | worst max error |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in ranking["ranking"]:
        lines.append(
            f"| {item['rank']} | {item['controller_case']} | {item['case_count']} | "
            f"{item['pass_count']} | {item['warn_count']} | {item['fail_count']} | "
            f"{item['average_rmse']:.6f} | {item['average_mae']:.6f} | "
            f"{item['average_saturation_fraction']:.6f} | {item['worst_max_abs_error']:.6f} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- accepted as initial offline controller simulator: `{decision['accepted_as_initial_offline_controller_simulator']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append(f"- recommended next step: {decision['recommended_next_step']}")
    lines.append("")
    lines.append("## Important limitation")
    lines.append("")
    lines.append("This simulator uses a selected recursive surrogate plant model. It is suitable for offline controller preparation, not for direct live deployment.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_experiment_doc(path, summary, ranking):
    lines = []
    lines.append("# v0.14.0 offline controller simulator with selected recursive model")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("v0.14.0 introduces an offline controller simulator based on the v0.13.6 selected recursive model.")
    lines.append("")
    lines.append("The simulator is a preparation tool for controller logic. It is not a live controller and does not apply actions to Kubernetes, a validator, or a transaction-load process.")
    lines.append("")
    lines.append("## Methodological context")
    lines.append("")
    lines.append("- v0.13.4 produced a one-step throughput model refit.")
    lines.append("- v0.13.5 showed caution for placeholder vs one-step refit shadow comparison.")
    lines.append("- v0.13.6 selected a recursive plant model with pass status.")
    lines.append("- v0.13.7 confirmed the selected recursive model as candidate surrogate plant model.")
    lines.append("- v0.14.0 uses that model inside an offline closed-loop simulation harness.")
    lines.append("")
    lines.append("## Source artefacts")
    lines.append("")
    for key, value in summary["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Plant model")
    lines.append("")
    model = summary["plant_model"]
    lines.append(f"- equation: `{summary['simulation_policy']['plant_equation']}`")
    lines.append(f"- a_y: `{model['a_y']}`")
    lines.append(f"- b_u: `{model['b_u']}`")
    lines.append(f"- c: `{model['c']}`")
    lines.append(f"- delay_steps: `{model['delay_steps']}`")
    lines.append("")
    lines.append("## Simulation protocol")
    lines.append("")
    lines.append(f"- mode: `{summary['simulation_policy']['mode']}`")
    lines.append(f"- dt_seconds: `{summary['simulation_policy']['dt_seconds']}`")
    lines.append(f"- steps_per_profile: `{summary['simulation_policy']['steps_per_profile']}`")
    lines.append(f"- actuator_applied: `{summary['simulation_policy']['actuator_applied']}`")
    lines.append("")
    lines.append("## Safety policy")
    lines.append("")
    for key, value in summary["safety_policy"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| rank | controller | pass | warn | fail | avg RMSE | avg MAE | avg saturation |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for item in ranking["ranking"]:
        lines.append(
            f"| {item['rank']} | {item['controller_case']} | {item['pass_count']} | "
            f"{item['warn_count']} | {item['fail_count']} | {item['average_rmse']:.6f} | "
            f"{item['average_mae']:.6f} | {item['average_saturation_fraction']:.6f} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    decision = summary["decision"]
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- accepted as initial offline controller simulator: `{decision['accepted_as_initial_offline_controller_simulator']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Next step")
    lines.append("")
    lines.append("The next stage should review controller behaviour and either tune PID-style baselines or introduce an MPC-ready interface.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_json(args.config)

    for path in config["source_artifacts"].values():
        require_file(path)

    model_path = config["source_artifacts"]["selected_recursive_model_path"]
    model = load_json(model_path)
    model["source_path"] = model_path

    v0137_summary = load_json(config["source_artifacts"]["v0_13_7_shadow_comparison_summary_path"])
    if v0137_summary.get("decision", {}).get("accepted_as_candidate_surrogate_plant_model") is not True:
        raise RuntimeError("v0.13.7 did not accept selected_recursive as candidate surrogate plant model.")

    all_rows = []
    case_results = []

    for profile in config["profiles"]:
        for controller in config["controller_cases"]:
            result = simulate_case(model, controller, profile, config)
            all_rows.extend(result.pop("rows"))
            case_results.append(result)

    ranking_list = aggregate_controller_ranking(case_results)
    decision = decide_overall(case_results, config["decision_thresholds"])

    summary = {
        "stage": config["stage"],
        "title": config["title"],
        "offline_only": config["offline_only"],
        "inputs": {
            "config_path": args.config,
            "selected_recursive_model_path": model_path,
            "v0_13_7_shadow_comparison_summary_path": config["source_artifacts"]["v0_13_7_shadow_comparison_summary_path"],
            "v0_13_7_model_ranking_path": config["source_artifacts"]["v0_13_7_model_ranking_path"],
            "v0_11_0_safety_checks_path": config["source_artifacts"]["v0_11_0_safety_checks_path"]
        },
        "simulation_policy": config["simulation_policy"],
        "safety_policy": config["safety_policy"],
        "plant_model": {
            "source_path": model_path,
            "a_y": model["a_y"],
            "b_u": model["b_u"],
            "c": model.get("c", 0.0),
            "delay_steps": model.get("delay_steps", 0),
            "model_type": model.get("model_type"),
            "y_eq": model.get("y_eq"),
            "u_eq": model.get("u_eq")
        },
        "controller_cases": config["controller_cases"],
        "profiles": config["profiles"],
        "case_results": case_results,
        "decision": decision,
        "outputs": config["outputs"]
    }

    ranking = {
        "stage": config["stage"],
        "title": "controller ranking for v0.14.0 offline controller simulator",
        "ranking_basis": [
            "fail_count",
            "warn_count",
            "average_rmse",
            "average_saturation_fraction"
        ],
        "ranking": ranking_list,
        "decision": decision
    }

    write_timeseries(config["outputs"]["timeseries_csv"], all_rows)
    write_json(config["outputs"]["summary_json"], summary)
    write_json(config["outputs"]["ranking_json"], ranking)
    write_readme(config["outputs"]["readme_md"], summary, ranking)
    write_experiment_doc(config["outputs"]["experiment_doc"], summary, ranking)

    print(f"Wrote {config['outputs']['summary_json']}")
    print(f"Wrote {config['outputs']['ranking_json']}")
    print(f"Wrote {config['outputs']['timeseries_csv']}")
    print(f"Wrote {config['outputs']['readme_md']}")
    print(f"Wrote {config['outputs']['experiment_doc']}")
    print(f"Decision: {decision['status']}")
    print(f"Accepted as initial offline controller simulator: {decision['accepted_as_initial_offline_controller_simulator']}")


if __name__ == "__main__":
    main()
