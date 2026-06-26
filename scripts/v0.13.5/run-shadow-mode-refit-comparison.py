#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import math
import os
import statistics
from typing import Any, Dict, Iterable, List, Optional, Tuple


def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required JSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required replay CSV not found: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def first_present_column(headers: Iterable[str], candidates: List[str], purpose: str) -> str:
    header_set = set(headers)
    for c in candidates:
        if c in header_set:
            return c
    raise ValueError(f"No {purpose} column found. Candidates={candidates}, headers={sorted(header_set)}")


def walk_json(obj: Any, path: Tuple[str, ...] = ()) -> Iterable[Tuple[Tuple[str, ...], Any]]:
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_json(v, path + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_json(v, path + (str(i),))


def find_numeric_key_anywhere(obj: Any, names: List[str]) -> Optional[float]:
    names_lower = {n.lower() for n in names}
    for path, value in walk_json(obj):
        if not path:
            continue
        if path[-1].lower() in names_lower:
            x = to_float(value)
            if x is not None:
                return x
    return None


def extract_model_coefficients(obj: Dict[str, Any], source_path: str) -> Dict[str, Any]:
    a_y = find_numeric_key_anywhere(obj, ["a_y", "ay", "a", "autoregressive_coefficient"])
    b_u = find_numeric_key_anywhere(obj, ["b_u", "bu", "b", "input_coefficient"])
    delay = find_numeric_key_anywhere(obj, ["delay", "input_delay", "delay_steps", "dead_time_steps"])
    y0 = find_numeric_key_anywhere(obj, ["y0", "initial_y", "initial_output", "initial_prediction"])

    if a_y is None or b_u is None:
        raise ValueError(f"Could not extract a_y and b_u from {source_path}")

    if delay is None:
        delay = 0.0

    delay_int = int(round(delay))
    if delay_int < 0:
        raise ValueError(f"Invalid negative delay extracted from {source_path}: {delay}")

    return {
        "source_path": source_path,
        "a_y": float(a_y),
        "b_u": float(b_u),
        "delay_steps": delay_int,
        "y0": None if y0 is None else float(y0)
    }


def discover_fitted_model(config: Dict[str, Any]) -> Dict[str, Any]:
    globs = config["fitted_model_discovery"]["candidate_globs"]
    candidates: List[str] = []
    for pattern in globs:
        candidates.extend(glob.glob(pattern, recursive=True))
    candidates = sorted(set(candidates))

    errors = []
    valid = []

    for path in candidates:
        try:
            obj = load_json(path)
            model = extract_model_coefficients(obj, path)
            valid.append(model)
        except Exception as exc:
            errors.append({"path": path, "error": str(exc)})

    if not valid:
        raise RuntimeError(
            "No v0.13.4 fitted/refit model coefficients found. "
            "Expected a JSON file under configs/v0.13.4 or results/v0.13.4 containing numeric a_y and b_u fields. "
            f"Scanned candidates: {candidates}. Extraction errors: {errors[:10]}"
        )

    preferred = []
    for model in valid:
        p = model["source_path"].lower()
        score = 0
        if "v0.13.4" in p:
            score += 100
        if "fit" in p or "refit" in p:
            score += 20
        if "coeff" in p:
            score += 10
        if "summary" in p:
            score += 5
        preferred.append((score, model["source_path"], model))

    preferred.sort(reverse=True)
    selected = preferred[0][2]
    selected["all_valid_candidates"] = valid
    selected["invalid_candidate_errors"] = errors
    return selected


def extract_placeholder_model(config: Dict[str, Any]) -> Dict[str, Any]:
    path = config["source_artifacts"]["placeholder_config_path"]
    obj = load_json(path)
    model = extract_model_coefficients(obj, path)
    model["all_valid_candidates"] = [model]
    model["invalid_candidate_errors"] = []
    return model


def simulate_predictions(commands: List[float], observed: List[Optional[float]], model: Dict[str, Any]) -> List[float]:
    a_y = model["a_y"]
    b_u = model["b_u"]
    delay = model["delay_steps"]

    valid_observed = [x for x in observed if x is not None]
    if model.get("y0") is not None:
        y_prev = float(model["y0"])
    elif valid_observed:
        y_prev = valid_observed[0]
    elif commands:
        y_prev = commands[0]
    else:
        y_prev = 0.0

    y_hat = []
    for k, _u in enumerate(commands):
        delayed_index = k - delay
        if delayed_index >= 0:
            u_delayed = commands[delayed_index]
        else:
            u_delayed = commands[0]
        y_next = a_y * y_prev + b_u * u_delayed
        if not math.isfinite(y_next):
            y_next = float("nan")
        y_hat.append(y_next)
        y_prev = y_next
    return y_hat


def compute_actions(
    predictions: List[float],
    commands: List[float],
    observed: List[Optional[float]],
    policy: Dict[str, Any]
) -> List[float]:
    valid_observed = [x for x in observed if x is not None]
    if policy.get("setpoint_source") == "median_observed" and valid_observed:
        setpoint = statistics.median(valid_observed)
    else:
        setpoint = to_float(policy.get("setpoint"))
        if setpoint is None:
            setpoint = statistics.median(commands) if commands else 0.0

    kp = float(policy.get("kp", 0.0))
    ki = float(policy.get("ki", 0.0))
    kd = float(policy.get("kd", 0.0))
    action_min = float(policy.get("action_min", 0.0))
    action_max = float(policy.get("action_max", 1_000_000_000.0))
    max_step_change = policy.get("max_step_change")
    max_step_change = None if max_step_change is None else float(max_step_change)

    actions = []
    integral = 0.0
    prev_error = 0.0

    for k, y_hat in enumerate(predictions):
        baseline = commands[k]
        error = setpoint - y_hat
        integral += error
        derivative = error - prev_error
        raw = baseline + kp * error + ki * integral + kd * derivative

        if max_step_change is not None and actions:
            prev_action = actions[-1]
            raw = max(prev_action - max_step_change, min(prev_action + max_step_change, raw))

        action = max(action_min, min(action_max, raw))
        actions.append(action)
        prev_error = error

    return actions


def finite_error_pairs(predictions: List[float], observed: List[Optional[float]]) -> List[Tuple[float, float]]:
    pairs = []
    for y_hat, y in zip(predictions, observed):
        if y is not None and math.isfinite(y_hat):
            pairs.append((y_hat, y))
    return pairs


def model_metrics(predictions: List[float], observed: List[Optional[float]]) -> Dict[str, Any]:
    pairs = finite_error_pairs(predictions, observed)
    if not pairs:
        return {
            "valid_error_rows": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "mape": None,
            "r2": None
        }

    errors = [yh - y for yh, y in pairs]
    abs_errors = [abs(e) for e in errors]
    sq_errors = [e * e for e in errors]

    mae = statistics.mean(abs_errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    bias = statistics.mean(errors)

    pct_errors = [abs((yh - y) / y) for yh, y in pairs if y != 0]
    mape = statistics.mean(pct_errors) * 100.0 if pct_errors else None

    ys = [y for _yh, y in pairs]
    y_mean = statistics.mean(ys)
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((yh - y) ** 2 for yh, y in pairs)
    r2 = None if ss_tot == 0 else 1.0 - ss_res / ss_tot

    return {
        "valid_error_rows": len(pairs),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "mape": mape,
        "r2": r2
    }


def safe_improvement(old: Optional[float], new: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if old is None or new is None:
        return None, None
    improvement_abs = old - new
    improvement_pct = None if old == 0 else 100.0 * improvement_abs / old
    return improvement_abs, improvement_pct


def safety_flags(predictions: List[float], actions: List[float], safety: Dict[str, Any]) -> List[bool]:
    action_min = float(safety.get("action_min", 0.0))
    action_max = float(safety.get("action_max", 1_000_000_000.0))
    flags = []
    for y_hat, action in zip(predictions, actions):
        ok = True
        if safety.get("prediction_must_be_finite", True) and not math.isfinite(y_hat):
            ok = False
        if safety.get("action_must_be_finite", True) and not math.isfinite(action):
            ok = False
        if action < action_min or action > action_max:
            ok = False
        flags.append(ok)
    return flags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    config = load_json(args.config)
    os.makedirs(args.output_dir, exist_ok=True)

    if not config.get("offline_only", False):
        raise RuntimeError("Config must explicitly set offline_only=true")

    replay_path = config["source_artifacts"]["real_replay_timeseries_path"]
    rows = read_csv_rows(replay_path)
    if not rows:
        raise RuntimeError(f"Replay CSV is empty: {replay_path}")

    headers = rows[0].keys()
    replay_columns = config["replay_columns"]

    time_col = first_present_column(headers, replay_columns["time_candidates"], "time")
    command_col = first_present_column(headers, replay_columns["command_candidates"], "command")
    observed_col = first_present_column(headers, replay_columns["observed_candidates"], "observed")

    clean_rows = []
    for idx, row in enumerate(rows):
        u = to_float(row.get(command_col))
        if u is None:
            continue
        t = to_float(row.get(time_col))
        y = to_float(row.get(observed_col))
        clean_rows.append({
            "row_index": idx,
            "time": float(idx) if t is None else t,
            "command": u,
            "observed": y
        })

    if len(clean_rows) < 3:
        raise RuntimeError(f"Not enough valid replay rows after parsing {replay_path}: {len(clean_rows)}")

    commands = [r["command"] for r in clean_rows]
    observed = [r["observed"] for r in clean_rows]

    placeholder_model = extract_placeholder_model(config)
    fitted_model = discover_fitted_model(config)

    placeholder_pred = simulate_predictions(commands, observed, placeholder_model)
    fitted_pred = simulate_predictions(commands, observed, fitted_model)

    policy = config["controller_policy"]
    placeholder_actions = compute_actions(placeholder_pred, commands, observed, policy)
    fitted_actions = compute_actions(fitted_pred, commands, observed, policy)

    safety = config["safety_policy"]
    placeholder_safe = safety_flags(placeholder_pred, placeholder_actions, safety)
    fitted_safe = safety_flags(fitted_pred, fitted_actions, safety)

    csv_path = os.path.join(args.output_dir, "shadow-mode-comparison.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "row_index",
            "time_seconds",
            "observed",
            "u_cmd",
            "placeholder_prediction",
            "fitted_prediction",
            "prediction_delta",
            "placeholder_recommended_action",
            "fitted_recommended_action",
            "action_delta",
            "action_disagreement",
            "placeholder_safety_ok",
            "fitted_safety_ok",
            "fitted_new_safety_regression_vs_placeholder",
            "actuator_applied"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, r in enumerate(clean_rows):
            prediction_delta = fitted_pred[i] - placeholder_pred[i]
            action_delta = fitted_actions[i] - placeholder_actions[i]
            action_disagreement = abs(action_delta) > 1e-9
            regression = bool(placeholder_safe[i] and not fitted_safe[i])
            writer.writerow({
                "row_index": r["row_index"],
                "time_seconds": r["time"],
                "observed": "" if r["observed"] is None else r["observed"],
                "u_cmd": r["command"],
                "placeholder_prediction": placeholder_pred[i],
                "fitted_prediction": fitted_pred[i],
                "prediction_delta": prediction_delta,
                "placeholder_recommended_action": placeholder_actions[i],
                "fitted_recommended_action": fitted_actions[i],
                "action_delta": action_delta,
                "action_disagreement": action_disagreement,
                "placeholder_safety_ok": placeholder_safe[i],
                "fitted_safety_ok": fitted_safe[i],
                "fitted_new_safety_regression_vs_placeholder": regression,
                "actuator_applied": False
            })

    placeholder_metrics = model_metrics(placeholder_pred, observed)
    fitted_metrics = model_metrics(fitted_pred, observed)

    rmse_abs, rmse_pct = safe_improvement(placeholder_metrics["rmse"], fitted_metrics["rmse"])
    mae_abs, mae_pct = safe_improvement(placeholder_metrics["mae"], fitted_metrics["mae"])
    bias_reduction_abs = None
    if placeholder_metrics["bias"] is not None and fitted_metrics["bias"] is not None:
        bias_reduction_abs = abs(placeholder_metrics["bias"]) - abs(fitted_metrics["bias"])

    action_deltas = [fa - pa for pa, fa in zip(placeholder_actions, fitted_actions)]
    abs_action_deltas = [abs(x) for x in action_deltas]
    disagreement_count = sum(1 for x in abs_action_deltas if x > 1e-9)
    disagreement_rate = disagreement_count / len(abs_action_deltas) if abs_action_deltas else None

    placeholder_violations = sum(1 for x in placeholder_safe if not x)
    fitted_violations = sum(1 for x in fitted_safe if not x)
    new_regressions = sum(1 for ps, fs in zip(placeholder_safe, fitted_safe) if ps and not fs)

    thresholds = config["decision_thresholds"]

    status = "pass"
    reasons = []

    if rmse_pct is None:
        status = "caution"
        reasons.append("RMSE improvement could not be computed.")
    elif rmse_pct < float(thresholds["minimum_rmse_improvement_pct_for_pass"]):
        status = "caution"
        reasons.append(
            f"Fitted model RMSE improvement is below pass threshold: {rmse_pct:.6g}%."
        )

    if new_regressions > int(thresholds["maximum_new_safety_regressions_for_pass"]):
        status = "fail"
        reasons.append(f"Fitted model introduced new safety regressions: {new_regressions}.")

    if disagreement_rate is not None and disagreement_rate > float(thresholds["maximum_action_disagreement_rate_for_pass"]):
        if status == "pass":
            status = "caution"
        reasons.append(f"Action disagreement rate is high: {disagreement_rate:.6g}.")

    if not reasons:
        reasons.append("Fitted model improved predictive metrics without new safety regressions under the configured offline comparison policy.")

    if status == "pass":
        recommended_next_step = "Promote fitted coefficients as the default model candidate for the next closed-loop preparation gate, still offline-only."
    elif status == "caution":
        recommended_next_step = "Keep fitted coefficients as a candidate, but review action deltas and model-fit evidence before closed-loop preparation."
    else:
        recommended_next_step = "Do not promote fitted coefficients. Refit or revise model-identification assumptions before further controller preparation."

    summary = {
        "stage": config["stage"],
        "decision": {
            "status": status,
            "reason": " ".join(reasons),
            "recommended_next_step": recommended_next_step
        },
        "offline_only": True,
        "actuator_applied": False,
        "inputs": {
            "config_path": args.config,
            "replay_path": replay_path,
            "time_column": time_col,
            "command_column": command_col,
            "observed_column": observed_col,
            "placeholder_model_source": placeholder_model["source_path"],
            "fitted_model_source": fitted_model["source_path"]
        },
        "models": {
            "placeholder": {
                "a_y": placeholder_model["a_y"],
                "b_u": placeholder_model["b_u"],
                "delay_steps": placeholder_model["delay_steps"],
                "y0": placeholder_model["y0"]
            },
            "fitted": {
                "a_y": fitted_model["a_y"],
                "b_u": fitted_model["b_u"],
                "delay_steps": fitted_model["delay_steps"],
                "y0": fitted_model["y0"]
            }
        },
        "model_metrics": {
            "placeholder_mae": placeholder_metrics["mae"],
            "fitted_mae": fitted_metrics["mae"],
            "placeholder_rmse": placeholder_metrics["rmse"],
            "fitted_rmse": fitted_metrics["rmse"],
            "placeholder_bias": placeholder_metrics["bias"],
            "fitted_bias": fitted_metrics["bias"],
            "placeholder_mape": placeholder_metrics["mape"],
            "fitted_mape": fitted_metrics["mape"],
            "placeholder_r2": placeholder_metrics["r2"],
            "fitted_r2": fitted_metrics["r2"],
            "valid_error_rows": fitted_metrics["valid_error_rows"]
        },
        "comparison_metrics": {
            "rmse_improvement_abs": rmse_abs,
            "rmse_improvement_pct": rmse_pct,
            "mae_improvement_abs": mae_abs,
            "mae_improvement_pct": mae_pct,
            "bias_reduction_abs": bias_reduction_abs,
            "action_disagreement_count": disagreement_count,
            "action_disagreement_rate": disagreement_rate,
            "mean_abs_action_delta": statistics.mean(abs_action_deltas) if abs_action_deltas else None,
            "max_abs_action_delta": max(abs_action_deltas) if abs_action_deltas else None,
            "fitted_more_conservative_count": sum(1 for x in action_deltas if x < -1e-9),
            "fitted_more_aggressive_count": sum(1 for x in action_deltas if x > 1e-9)
        },
        "safety_metrics": {
            "placeholder_safety_violation_count": placeholder_violations,
            "fitted_safety_violation_count": fitted_violations,
            "placeholder_constraint_warning_count": placeholder_violations,
            "fitted_constraint_warning_count": fitted_violations,
            "fitted_new_safety_regressions_vs_placeholder": new_regressions
        },
        "fitted_model_discovery": {
            "selected": fitted_model["source_path"],
            "valid_candidate_count": len(fitted_model.get("all_valid_candidates", [])),
            "invalid_candidate_error_count": len(fitted_model.get("invalid_candidate_errors", []))
        },
        "outputs": {
            "comparison_csv": csv_path,
            "summary_json": os.path.join(args.output_dir, "comparison-summary.json")
        }
    }

    write_json(os.path.join(args.output_dir, "comparison-summary.json"), summary)

    print(json.dumps({
        "stage": config["stage"],
        "status": status,
        "replay_rows": len(clean_rows),
        "placeholder_model_source": placeholder_model["source_path"],
        "fitted_model_source": fitted_model["source_path"],
        "summary_path": os.path.join(args.output_dir, "comparison-summary.json"),
        "csv_path": csv_path
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
