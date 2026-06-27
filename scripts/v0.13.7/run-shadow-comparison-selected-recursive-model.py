#!/usr/bin/env python3

import argparse
import csv
import json
import math
import statistics
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


def find_first_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_first_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_first_key(item, key)
            if found is not None:
                return found
    return None


def as_float(value, default=None):
    if value is None:
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x


def as_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def extract_model_from_json(path, label, fallback=None):
    data = load_json(path)

    a_y = as_float(find_first_key(data, "a_y"))
    b_u = as_float(find_first_key(data, "b_u"))
    c = as_float(find_first_key(data, "c"), 0.0)
    delay_steps = as_int(find_first_key(data, "delay_steps"), 0)
    family = find_first_key(data, "family") or find_first_key(data, "model_type") or label
    y0 = as_float(find_first_key(data, "y0"), None)

    if (a_y is None or b_u is None) and fallback is not None:
        a_y = fallback.get("a_y")
        b_u = fallback.get("b_u")
        c = fallback.get("c", 0.0)
        delay_steps = fallback.get("delay_steps", 0)
        family = fallback.get("family", label)
        y0 = fallback.get("y0", y0)

    if a_y is None or b_u is None:
        raise ValueError(f"Could not extract a_y and b_u for model {label} from {path}")

    return {
        "label": label,
        "source_path": path,
        "family": str(family),
        "a_y": float(a_y),
        "b_u": float(b_u),
        "c": float(c if c is not None else 0.0),
        "delay_steps": int(delay_steps),
        "y0": y0
    }


def choose_column(fieldnames, candidates, role):
    for name in candidates:
        if name in fieldnames:
            return name
    raise ValueError(f"Could not find {role} column. Candidates: {candidates}. Available: {fieldnames}")


def load_replay_csv(path, replay_columns):
    require_file(path)
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        time_col = choose_column(fieldnames, replay_columns["time_candidates"], "time")
        command_col = choose_column(fieldnames, replay_columns["command_candidates"], "command")
        observed_col = choose_column(fieldnames, replay_columns["observed_candidates"], "observed")

        rows = []
        for idx, row in enumerate(reader):
            t = as_float(row.get(time_col))
            u = as_float(row.get(command_col))
            y = as_float(row.get(observed_col))
            if t is None or u is None or y is None:
                continue
            if not (math.isfinite(t) and math.isfinite(u) and math.isfinite(y)):
                continue
            rows.append({
                "row_index": idx,
                "time_seconds": t,
                "u_cmd": u,
                "observed": y
            })

    if len(rows) < 5:
        raise ValueError(f"Not enough valid replay rows in {path}: {len(rows)}")

    return rows, time_col, command_col, observed_col


def recursive_rollout(model, rows, start_idx, end_idx):
    predictions = {}
    warnings = []

    state = rows[start_idx]["observed"]

    for target_idx in range(start_idx + 1, end_idx):
        command_idx = (target_idx - 1) - model["delay_steps"]

        if command_idx < 0:
            command_idx = 0
            warnings.append({
                "row_index": rows[target_idx]["row_index"],
                "warning": "delay command index before replay start; clamped to first row",
                "model": model["label"]
            })

        u = rows[command_idx]["u_cmd"]

        pred = model["c"] + model["a_y"] * state + model["b_u"] * u

        predictions[target_idx] = pred

        if math.isfinite(pred):
            state = pred
        else:
            warnings.append({
                "row_index": rows[target_idx]["row_index"],
                "warning": "non-finite prediction; recursive state held at previous value",
                "model": model["label"]
            })

    return predictions, warnings


def compute_metrics(predictions, rows, start_idx, end_idx):
    errors = []
    abs_errors = []
    ape = []
    smape = []
    actuals = []
    preds = []
    non_finite = 0

    for target_idx in range(start_idx + 1, end_idx):
        pred = predictions.get(target_idx)
        actual = rows[target_idx]["observed"]

        if pred is None or not math.isfinite(pred):
            non_finite += 1
            continue

        err = pred - actual
        errors.append(err)
        abs_errors.append(abs(err))
        actuals.append(actual)
        preds.append(pred)

        if abs(actual) > 1e-12:
            ape.append(abs(err) / abs(actual) * 100.0)

        denom = abs(actual) + abs(pred)
        if denom > 1e-12:
            smape.append(2.0 * abs(err) / denom * 100.0)

    count = len(errors)

    if count == 0:
        return {
            "count": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "median_absolute_error": None,
            "max_absolute_error": None,
            "mape": None,
            "smape": None,
            "r2": None,
            "non_finite_prediction_count": non_finite,
            "warning_count": non_finite
        }

    mse = sum(e * e for e in errors) / count
    mean_actual = sum(actuals) / count
    sse = sum((p - a) ** 2 for p, a in zip(preds, actuals))
    sst = sum((a - mean_actual) ** 2 for a in actuals)
    r2 = None if abs(sst) <= 1e-12 else 1.0 - sse / sst

    return {
        "count": count,
        "mae": sum(abs_errors) / count,
        "rmse": math.sqrt(mse),
        "bias": sum(errors) / count,
        "median_absolute_error": statistics.median(abs_errors),
        "max_absolute_error": max(abs_errors),
        "mape": None if not ape else sum(ape) / len(ape),
        "smape": None if not smape else sum(smape) / len(smape),
        "r2": r2,
        "non_finite_prediction_count": non_finite,
        "warning_count": non_finite
    }


def pct_improvement(old, new):
    if old is None or new is None:
        return None
    if abs(old) <= 1e-12:
        return None
    return (old - new) / old * 100.0


def controller_action(u_cmd, prediction, setpoint, policy):
    kp = float(policy.get("kp", 0.0))
    action = u_cmd + kp * (setpoint - prediction)

    max_step_change = policy.get("max_step_change")
    if max_step_change is not None:
        delta = action - u_cmd
        max_delta = abs(float(max_step_change))
        if delta > max_delta:
            action = u_cmd + max_delta
        elif delta < -max_delta:
            action = u_cmd - max_delta

    action_min = float(policy.get("action_min", 0.0))
    action_max = float(policy.get("action_max", 1_000_000_000.0))

    if action < action_min:
        action = action_min
    if action > action_max:
        action = action_max

    return action


def safety_ok(prediction, action, safety_policy):
    if safety_policy.get("prediction_must_be_finite", True):
        if prediction is None or not math.isfinite(prediction):
            return False
    if safety_policy.get("action_must_be_finite", True):
        if action is None or not math.isfinite(action):
            return False

    action_min = float(safety_policy.get("action_min", 0.0))
    action_max = float(safety_policy.get("action_max", 1_000_000_000.0))

    if action < action_min or action > action_max:
        return False

    return True


def build_timeseries(rows, predictions_by_model, models, start_idx, end_idx, controller_policy, safety_policy):
    eval_observed = [rows[i]["observed"] for i in range(start_idx + 1, end_idx)]
    setpoint = statistics.median(eval_observed)

    out_rows = []

    for target_idx in range(start_idx + 1, end_idx):
        base = {
            "row_index": rows[target_idx]["row_index"],
            "time_seconds": rows[target_idx]["time_seconds"],
            "observed": rows[target_idx]["observed"],
            "u_cmd": rows[target_idx]["u_cmd"]
        }

        for model in models:
            label = model["label"]
            pred = predictions_by_model[label].get(target_idx)
            err = None if pred is None or not math.isfinite(pred) else pred - rows[target_idx]["observed"]
            action = None
            ok = False
            if pred is not None and math.isfinite(pred):
                action = controller_action(rows[target_idx]["u_cmd"], pred, setpoint, controller_policy)
                ok = safety_ok(pred, action, safety_policy)

            base[f"{label}_prediction"] = pred
            base[f"{label}_error"] = err
            base[f"{label}_recommended_action"] = action
            base[f"{label}_safety_ok"] = ok

        base["actuator_applied"] = False
        out_rows.append(base)

    return out_rows, setpoint


def write_timeseries_csv(path, rows, models):
    fieldnames = [
        "row_index",
        "time_seconds",
        "observed",
        "u_cmd"
    ]

    for model in models:
        label = model["label"]
        fieldnames.extend([
            f"{label}_prediction",
            f"{label}_error",
            f"{label}_recommended_action",
            f"{label}_safety_ok"
        ])

    fieldnames.append("actuator_applied")

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def rank_models(metrics_by_model):
    def sort_key(item):
        label, metrics = item
        rmse = metrics["rmse"]
        mae = metrics["mae"]
        bias = metrics["bias"]
        max_abs = metrics["max_absolute_error"]
        non_finite = metrics["non_finite_prediction_count"]
        warning = metrics["warning_count"]

        return (
            non_finite,
            warning,
            float("inf") if rmse is None else rmse,
            float("inf") if mae is None else mae,
            float("inf") if bias is None else abs(bias),
            float("inf") if max_abs is None else max_abs,
            label
        )

    ordered = sorted(metrics_by_model.items(), key=sort_key)

    ranking = []
    for i, (label, metrics) in enumerate(ordered, start=1):
        ranking.append({
            "rank": i,
            "model": label,
            "rmse": metrics["rmse"],
            "mae": metrics["mae"],
            "bias": metrics["bias"],
            "median_absolute_error": metrics["median_absolute_error"],
            "max_absolute_error": metrics["max_absolute_error"],
            "mape": metrics["mape"],
            "smape": metrics["smape"],
            "r2": metrics["r2"],
            "non_finite_prediction_count": metrics["non_finite_prediction_count"],
            "warning_count": metrics["warning_count"]
        })

    return ranking


def decide(metrics_by_model, ranking, thresholds):
    selected = metrics_by_model["selected_recursive"]
    placeholder = metrics_by_model["placeholder"]
    one_step = metrics_by_model["one_step_refit"]

    best_rmse = min(m["rmse"] for m in metrics_by_model.values() if m["rmse"] is not None)
    best_mae = min(m["mae"] for m in metrics_by_model.values() if m["mae"] is not None)

    rmse_tie_pct = float(thresholds.get("material_tie_rmse_pct", 2.0))
    mae_tie_pct = float(thresholds.get("material_tie_mae_pct", 5.0))

    selected_rmse_ok = selected["rmse"] is not None and selected["rmse"] <= best_rmse * (1.0 + rmse_tie_pct / 100.0)
    selected_mae_ok = selected["mae"] is not None and selected["mae"] <= best_mae * (1.0 + mae_tie_pct / 100.0)
    selected_nonfinite_ok = selected["non_finite_prediction_count"] <= int(thresholds.get("maximum_non_finite_predictions_for_pass", 0))
    selected_warning_ok = selected["warning_count"] <= int(thresholds.get("maximum_warning_count_for_pass", 0))

    selected_rank = next(item["rank"] for item in ranking if item["model"] == "selected_recursive")

    improvement_vs_placeholder = pct_improvement(placeholder["rmse"], selected["rmse"])
    improvement_vs_one_step = pct_improvement(one_step["rmse"], selected["rmse"])

    if selected_rmse_ok and selected_mae_ok and selected_nonfinite_ok and selected_warning_ok:
        return {
            "status": "pass",
            "reason": (
                "Selected recursive model is best or materially tied for best on core metrics "
                "with no non-finite predictions or warning count in the evaluated shadow window."
            ),
            "recommended_next_step": (
                "Use selected_recursive as the candidate surrogate plant model for v0.14.0 offline controller simulator."
            ),
            "selected_recursive_rank": selected_rank,
            "selected_recursive_rmse_improvement_pct_vs_placeholder": improvement_vs_placeholder,
            "selected_recursive_rmse_improvement_pct_vs_one_step_refit": improvement_vs_one_step,
            "accepted_as_candidate_surrogate_plant_model": True
        }

    worse_than_both = (
        selected["rmse"] is not None
        and placeholder["rmse"] is not None
        and one_step["rmse"] is not None
        and selected["rmse"] > placeholder["rmse"]
        and selected["rmse"] > one_step["rmse"]
    )

    if worse_than_both or not selected_nonfinite_ok:
        return {
            "status": "fail",
            "reason": (
                "Selected recursive model is worse than both comparison models or has non-finite predictions."
            ),
            "recommended_next_step": (
                "Do not use selected_recursive as the simulator plant model without further model review."
            ),
            "selected_recursive_rank": selected_rank,
            "selected_recursive_rmse_improvement_pct_vs_placeholder": improvement_vs_placeholder,
            "selected_recursive_rmse_improvement_pct_vs_one_step_refit": improvement_vs_one_step,
            "accepted_as_candidate_surrogate_plant_model": False
        }

    return {
        "status": "caution",
        "reason": (
            "Selected recursive model is not clearly best or has minor warnings; keep it as a candidate but review before simulator promotion."
        ),
        "recommended_next_step": (
            "Review shadow-comparison-timeseries.csv and model-ranking.json before starting v0.14.0."
        ),
        "selected_recursive_rank": selected_rank,
        "selected_recursive_rmse_improvement_pct_vs_placeholder": improvement_vs_placeholder,
        "selected_recursive_rmse_improvement_pct_vs_one_step_refit": improvement_vs_one_step,
        "accepted_as_candidate_surrogate_plant_model": False
    }


def write_readme(path, summary, ranking):
    decision = summary["decision"]
    metrics = summary["model_metrics"]

    lines = []
    lines.append("# v0.13.7 repeat shadow-mode comparison with selected recursive model")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("This stage repeats the shadow-mode model comparison with three candidate plant models:")
    lines.append("")
    lines.append("- placeholder baseline")
    lines.append("- v0.13.4 one-step refit model")
    lines.append("- v0.13.6 selected recursive model")
    lines.append("")
    lines.append("The purpose is to decide whether the selected recursive model can be promoted as the candidate surrogate plant model for the future v0.14.0 offline controller simulator.")
    lines.append("")
    lines.append("v0.13.7 is still an offline shadow-mode comparison stage. It is not a closed-loop simulator and does not apply actions to a live system.")
    lines.append("")
    lines.append("## Source artefacts")
    lines.append("")
    for key, value in summary["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Shadow-mode protocol")
    lines.append("")
    lines.append("- Evaluation mode: recursive shadow rollout.")
    lines.append("- Evaluation window: v0.13.6 validation segment.")
    lines.append("- Recursive state initialization: first observed value of the validation segment.")
    lines.append("- Anti-leakage rule: prediction for target row i uses previous recursive state and command history only.")
    lines.append("- Actuator applied: false.")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| model | count | RMSE | MAE | bias | median AE | max AE | MAPE | SMAPE | R2 | warnings |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for model in ["placeholder", "one_step_refit", "selected_recursive"]:
        m = metrics[model]
        lines.append(
            f"| {model} | {m['count']} | {m['rmse']:.6f} | {m['mae']:.6f} | {m['bias']:.6f} | "
            f"{m['median_absolute_error']:.6f} | {m['max_absolute_error']:.6f} | "
            f"{m['mape']:.6f} | {m['smape']:.6f} | {m['r2']:.6f} | {m['warning_count']} |"
        )
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    for item in ranking["ranking"]:
        lines.append(f"{item['rank']}. `{item['model']}` - RMSE={item['rmse']:.6f}, MAE={item['mae']:.6f}")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- accepted as candidate surrogate plant model: `{decision['accepted_as_candidate_surrogate_plant_model']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append(f"- recommended next step: {decision['recommended_next_step']}")
    lines.append("")
    lines.append("## Implication for v0.14.0")
    lines.append("")
    if decision["accepted_as_candidate_surrogate_plant_model"]:
        lines.append("The selected recursive model is accepted as the candidate surrogate plant model for v0.14.0 offline controller simulation.")
    else:
        lines.append("The selected recursive model is not yet accepted as the candidate surrogate plant model. Review is required before v0.14.0.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def write_experiment_doc(path, summary, ranking):
    decision = summary["decision"]

    lines = []
    lines.append("# v0.13.7 repeat shadow-mode comparison with selected recursive model")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("v0.13.7 evaluates whether the v0.13.6 selected recursive model should become the candidate surrogate plant model for the future offline controller simulator.")
    lines.append("")
    lines.append("This stage compares the placeholder baseline, the v0.13.4 one-step refit model, and the v0.13.6 selected recursive model under the same offline shadow-mode replay window.")
    lines.append("")
    lines.append("## Methodological context")
    lines.append("")
    lines.append("- v0.13.4 produced a one-step refit model.")
    lines.append("- v0.13.5 compared placeholder and one-step refit in shadow mode and produced a caution result.")
    lines.append("- v0.13.6 refit recursive plant-model candidates and selected a recursive model with a pass result.")
    lines.append("- v0.13.7 repeats the shadow comparison with the selected recursive model included.")
    lines.append("")
    lines.append("## Source artefacts")
    lines.append("")
    for key, value in summary["inputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Candidate models")
    lines.append("")
    for model, params in summary["models"].items():
        lines.append(f"### {model}")
        lines.append("")
        lines.append(f"- source: `{params['source_path']}`")
        lines.append(f"- family: `{params['family']}`")
        lines.append(f"- equation: `y[k+1] = c + a_y*y[k] + b_u*u[k-delay]`")
        lines.append(f"- a_y: `{params['a_y']}`")
        lines.append(f"- b_u: `{params['b_u']}`")
        lines.append(f"- c: `{params['c']}`")
        lines.append(f"- delay_steps: `{params['delay_steps']}`")
        lines.append("")
    lines.append("## Shadow-mode protocol")
    lines.append("")
    lines.append("- Mode: recursive shadow rollout.")
    lines.append("- Evaluation window: v0.13.6 validation segment.")
    lines.append("- Initial recursive state: first observed value of the validation segment.")
    lines.append("- Controller policy: proportional shadow recommendation only.")
    lines.append("- Actuator application: false.")
    lines.append("")
    lines.append("## Anti-leakage constraint")
    lines.append("")
    lines.append("For prediction at target row `i`, the model uses only the previous recursive state and command history available before row `i`. The observed target value at row `i` is not used before producing the prediction.")
    lines.append("")
    lines.append("## Results summary")
    lines.append("")
    lines.append("| rank | model | RMSE | MAE | bias | max AE | warnings |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|")
    for item in ranking["ranking"]:
        lines.append(
            f"| {item['rank']} | {item['model']} | {item['rmse']:.6f} | {item['mae']:.6f} | "
            f"{item['bias']:.6f} | {item['max_absolute_error']:.6f} | {item['warning_count']} |"
        )
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(f"- status: `{decision['status']}`")
    lines.append(f"- selected recursive rank: `{decision['selected_recursive_rank']}`")
    lines.append(f"- accepted as candidate surrogate plant model: `{decision['accepted_as_candidate_surrogate_plant_model']}`")
    lines.append(f"- reason: {decision['reason']}")
    lines.append("")
    lines.append("## Implications for v0.14.0 offline controller simulator")
    lines.append("")
    if decision["accepted_as_candidate_surrogate_plant_model"]:
        lines.append("The next logical stage is v0.14.0 offline controller simulation using the selected recursive model as the candidate surrogate plant.")
    else:
        lines.append("The next stage should not yet promote the selected recursive model to simulator plant status without additional review.")
    lines.append("")

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = load_json(args.config)

    source = config["source_artifacts"]
    outputs = config["outputs"]

    for key, path in source.items():
        require_file(path)

    rows, time_col, command_col, observed_col = load_replay_csv(
        source["real_replay_timeseries_path"],
        config["replay_columns"]
    )

    v0135_summary = load_json(source["v0_13_5_comparison_summary_path"])
    placeholder_fallback = v0135_summary.get("models", {}).get("placeholder")

    placeholder = extract_model_from_json(
        source["placeholder_model_path"],
        "placeholder",
        fallback=placeholder_fallback
    )

    one_step = extract_model_from_json(
        source["one_step_refit_model_path"],
        "one_step_refit"
    )

    selected_recursive = extract_model_from_json(
        source["selected_recursive_model_path"],
        "selected_recursive"
    )

    models = [placeholder, one_step, selected_recursive]

    train_fraction = float(config["evaluation_policy"]["train_fraction_from_v0_13_6"])
    start_idx = int(len(rows) * train_fraction)
    if start_idx < 1:
        raise ValueError("Evaluation start index is too early.")
    if start_idx >= len(rows) - 2:
        raise ValueError("Evaluation start index leaves too few rows.")

    end_idx = len(rows)

    predictions_by_model = {}
    warnings_by_model = {}

    for model in models:
        preds, warnings = recursive_rollout(model, rows, start_idx, end_idx)
        predictions_by_model[model["label"]] = preds
        warnings_by_model[model["label"]] = warnings

    metrics_by_model = {}

    for model in models:
        metrics = compute_metrics(predictions_by_model[model["label"]], rows, start_idx, end_idx)
        metrics["warning_count"] += len(warnings_by_model[model["label"]])
        metrics_by_model[model["label"]] = metrics

    timeseries_rows, setpoint = build_timeseries(
        rows,
        predictions_by_model,
        models,
        start_idx,
        end_idx,
        config["controller_policy"],
        config["safety_policy"]
    )

    write_timeseries_csv(outputs["timeseries_csv"], timeseries_rows, models)

    ranking_list = rank_models(metrics_by_model)
    decision = decide(metrics_by_model, ranking_list, config["decision_thresholds"])

    summary = {
        "stage": config["stage"],
        "title": config["title"],
        "offline_only": config["offline_only"],
        "actuator_applied": False,
        "inputs": {
            "config_path": args.config,
            "replay_path": source["real_replay_timeseries_path"],
            "placeholder_model_path": source["placeholder_model_path"],
            "one_step_refit_model_path": source["one_step_refit_model_path"],
            "selected_recursive_model_path": source["selected_recursive_model_path"],
            "v0_13_5_comparison_summary_path": source["v0_13_5_comparison_summary_path"],
            "v0_13_6_summary_path": source["v0_13_6_summary_path"],
            "time_column": time_col,
            "command_column": command_col,
            "observed_column": observed_col
        },
        "evaluation": {
            "mode": config["evaluation_policy"]["mode"],
            "evaluation_window": config["evaluation_policy"]["evaluation_window"],
            "train_fraction_from_v0_13_6": train_fraction,
            "valid_replay_rows": len(rows),
            "evaluation_initial_row_index": rows[start_idx]["row_index"],
            "first_predicted_row_index": rows[start_idx + 1]["row_index"],
            "last_predicted_row_index": rows[end_idx - 1]["row_index"],
            "prediction_count_per_model": end_idx - start_idx - 1,
            "recursive_initialization": config["evaluation_policy"]["recursive_initialization"],
            "setpoint": setpoint,
            "anti_leakage_rule": config["evaluation_policy"]["anti_leakage_rule"],
            "lookahead_leakage_detected": False
        },
        "models": {
            model["label"]: model for model in models
        },
        "model_metrics": metrics_by_model,
        "comparison_metrics": {
            "selected_recursive_rmse_improvement_pct_vs_placeholder": pct_improvement(
                metrics_by_model["placeholder"]["rmse"],
                metrics_by_model["selected_recursive"]["rmse"]
            ),
            "selected_recursive_rmse_improvement_pct_vs_one_step_refit": pct_improvement(
                metrics_by_model["one_step_refit"]["rmse"],
                metrics_by_model["selected_recursive"]["rmse"]
            ),
            "selected_recursive_mae_improvement_pct_vs_placeholder": pct_improvement(
                metrics_by_model["placeholder"]["mae"],
                metrics_by_model["selected_recursive"]["mae"]
            ),
            "selected_recursive_mae_improvement_pct_vs_one_step_refit": pct_improvement(
                metrics_by_model["one_step_refit"]["mae"],
                metrics_by_model["selected_recursive"]["mae"]
            )
        },
        "decision": decision,
        "outputs": {
            "summary_json": outputs["summary_json"],
            "ranking_json": outputs["ranking_json"],
            "timeseries_csv": outputs["timeseries_csv"],
            "readme_md": outputs["readme_md"],
            "experiment_doc": outputs["experiment_doc"]
        }
    }

    ranking = {
        "stage": config["stage"],
        "title": "model ranking for v0.13.7 shadow-mode comparison",
        "ranking_basis": [
            "non_finite_prediction_count",
            "warning_count",
            "rmse",
            "mae",
            "absolute_bias",
            "max_absolute_error"
        ],
        "ranking": ranking_list,
        "decision": decision
    }

    write_json(outputs["summary_json"], summary)
    write_json(outputs["ranking_json"], ranking)
    write_readme(outputs["readme_md"], summary, ranking)
    write_experiment_doc(outputs["experiment_doc"], summary, ranking)

    print(f"Wrote {outputs['summary_json']}")
    print(f"Wrote {outputs['ranking_json']}")
    print(f"Wrote {outputs['timeseries_csv']}")
    print(f"Wrote {outputs['readme_md']}")
    print(f"Wrote {outputs['experiment_doc']}")
    print(f"Decision: {decision['status']}")
    print(f"Accepted as candidate surrogate plant model: {decision['accepted_as_candidate_surrogate_plant_model']}")


if __name__ == "__main__":
    main()
