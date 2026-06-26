#!/usr/bin/env python3
import argparse
import csv
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


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required CSV file not found: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def metrics(predicted: List[float], observed: List[float]) -> Dict[str, Any]:
    pairs = [(p, y) for p, y in zip(predicted, observed) if math.isfinite(p) and math.isfinite(y)]
    if not pairs:
        return {
            "valid_rows": 0,
            "mae": None,
            "rmse": None,
            "bias": None,
            "mape": None,
            "r2": None
        }

    errors = [p - y for p, y in pairs]
    abs_errors = [abs(e) for e in errors]
    sq_errors = [e * e for e in errors]

    mae = statistics.mean(abs_errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    bias = statistics.mean(errors)

    pct_errors = [abs((p - y) / y) for p, y in pairs if y != 0]
    mape = statistics.mean(pct_errors) * 100.0 if pct_errors else None

    ys = [y for _p, y in pairs]
    y_mean = statistics.mean(ys)
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((p - y) ** 2 for p, y in pairs)
    r2 = None if ss_tot == 0 else 1.0 - ss_res / ss_tot

    return {
        "valid_rows": len(pairs),
        "mae": mae,
        "rmse": rmse,
        "bias": bias,
        "mape": mape,
        "r2": r2
    }


def solve_linear_least_squares(xs: List[List[float]], ys: List[float]) -> List[float]:
    # Small normal-equation solver with Gaussian elimination.
    if not xs:
        raise RuntimeError("No samples for least squares.")
    n = len(xs[0])
    ata = [[0.0 for _ in range(n)] for _ in range(n)]
    aty = [0.0 for _ in range(n)]

    for row, y in zip(xs, ys):
        for i in range(n):
            aty[i] += row[i] * y
            for j in range(n):
                ata[i][j] += row[i] * row[j]

    # Augmented matrix.
    aug = [ata[i] + [aty[i]] for i in range(n)]

    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise RuntimeError("Singular least-squares normal matrix.")
        aug[col], aug[pivot] = aug[pivot], aug[col]

        pivot_val = aug[col][col]
        for j in range(col, n + 1):
            aug[col][j] /= pivot_val

        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            for j in range(col, n + 1):
                aug[r][j] -= factor * aug[col][j]

    return [aug[i][n] for i in range(n)]


def build_samples(
    commands: List[float],
    observed: List[float],
    start: int,
    end_exclusive: int,
    delay: int
) -> List[Tuple[int, float, float, float]]:
    samples = []
    for k in range(start, end_exclusive - 1):
        delayed_index = k - delay
        if delayed_index < start or delayed_index < 0:
            continue
        samples.append((k, observed[k], commands[delayed_index], observed[k + 1]))
    return samples


def fit_candidate(
    family: str,
    delay: int,
    commands: List[float],
    observed: List[float],
    train_start: int,
    train_end: int
) -> Dict[str, Any]:
    samples = build_samples(commands, observed, train_start, train_end, delay)
    if len(samples) < 5:
        raise RuntimeError(f"Not enough training samples for family={family}, delay={delay}: {len(samples)}")

    train_y_values = [observed[i] for i in range(train_start, train_end)]
    train_u_values = [commands[i] for i in range(train_start, train_end)]

    y_eq = statistics.mean(train_y_values)
    u_eq = statistics.mean(train_u_values)

    xs = []
    ys = []

    if family == "no_intercept":
        for _k, y_cur, u_delayed, y_next in samples:
            xs.append([y_cur, u_delayed])
            ys.append(y_next)
        a_y, b_u = solve_linear_least_squares(xs, ys)
        c = 0.0

    elif family == "intercept":
        for _k, y_cur, u_delayed, y_next in samples:
            xs.append([1.0, y_cur, u_delayed])
            ys.append(y_next)
        c, a_y, b_u = solve_linear_least_squares(xs, ys)

    elif family == "equilibrium_deviation":
        for _k, y_cur, u_delayed, y_next in samples:
            xs.append([y_cur - y_eq, u_delayed - u_eq])
            ys.append(y_next - y_eq)
        a_y, b_u = solve_linear_least_squares(xs, ys)
        c = y_eq - a_y * y_eq - b_u * u_eq

    else:
        raise ValueError(f"Unknown model family: {family}")

    return {
        "family": family,
        "delay_steps": delay,
        "c": c,
        "a_y": a_y,
        "b_u": b_u,
        "y_eq": y_eq,
        "u_eq": u_eq,
        "train_sample_count": len(samples)
    }


def predict_next(model: Dict[str, Any], y_current: float, u_delayed: float) -> float:
    return model["c"] + model["a_y"] * y_current + model["b_u"] * u_delayed


def one_step_predictions(
    model: Dict[str, Any],
    commands: List[float],
    observed: List[float],
    start: int,
    end_exclusive: int
) -> Tuple[List[float], List[float]]:
    delay = int(model["delay_steps"])
    preds = []
    actuals = []

    for k in range(start, end_exclusive - 1):
        delayed_index = k - delay
        if delayed_index < start or delayed_index < 0:
            continue
        pred = predict_next(model, observed[k], commands[delayed_index])
        preds.append(pred)
        actuals.append(observed[k + 1])

    return preds, actuals


def recursive_predictions(
    model: Dict[str, Any],
    commands: List[float],
    observed: List[float],
    start: int,
    end_exclusive: int
) -> Tuple[List[float], List[float], List[int]]:
    delay = int(model["delay_steps"])
    if end_exclusive - start < 2:
        return [], [], []

    y_hat = observed[start]
    preds = []
    actuals = []
    indices = []

    for k in range(start, end_exclusive - 1):
        delayed_index = k - delay
        if delayed_index < 0:
            u_delayed = commands[start]
        else:
            u_delayed = commands[delayed_index]

        y_hat = predict_next(model, y_hat, u_delayed)
        preds.append(y_hat)
        actuals.append(observed[k + 1])
        indices.append(k + 1)

    return preds, actuals, indices


def extract_model_from_json(path: str, label: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    obj = load_json(path)

    def find_key(o: Any, names: List[str]) -> Optional[float]:
        names_lower = {n.lower() for n in names}

        def walk(x: Any):
            if isinstance(x, dict):
                for k, v in x.items():
                    if str(k).lower() in names_lower:
                        val = to_float(v)
                        if val is not None:
                            yield val
                    yield from walk(v)
            elif isinstance(x, list):
                for v in x:
                    yield from walk(v)

        for value in walk(o):
            return value
        return None

    a_y = find_key(obj, ["a_y", "ay", "a"])
    b_u = find_key(obj, ["b_u", "bu", "b"])
    delay = find_key(obj, ["delay_steps", "delay", "input_delay"])
    c = find_key(obj, ["c", "intercept"])
    y0 = find_key(obj, ["y0", "initial_y", "initial_output"])

    if a_y is None or b_u is None:
        return None

    return {
        "family": label,
        "delay_steps": int(round(delay or 0)),
        "c": float(c or 0.0),
        "a_y": float(a_y),
        "b_u": float(b_u),
        "y_eq": None,
        "u_eq": None,
        "train_sample_count": None,
        "source_path": path,
        "y0": y0
    }


def improvement_pct(old: Optional[float], new: Optional[float]) -> Optional[float]:
    if old is None or new is None or old == 0:
        return None
    return 100.0 * (old - new) / old


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    config = load_json(args.config)
    if not config.get("offline_only", False):
        raise RuntimeError("Config must explicitly set offline_only=true")

    os.makedirs(args.output_dir, exist_ok=True)

    replay_path = config["source_artifacts"]["real_replay_timeseries_path"]
    rows = read_csv_rows(replay_path)
    if not rows:
        raise RuntimeError(f"Replay CSV is empty: {replay_path}")

    columns = config["replay_columns"]
    headers = rows[0].keys()
    time_col = first_present_column(headers, columns["time_candidates"], "time")
    command_col = first_present_column(headers, columns["command_candidates"], "command")
    observed_col = first_present_column(headers, columns["observed_candidates"], "observed")

    clean = []
    for idx, row in enumerate(rows):
        t = to_float(row.get(time_col))
        u = to_float(row.get(command_col))
        y = to_float(row.get(observed_col))
        if u is None or y is None:
            continue
        clean.append({
            "row_index": idx,
            "time": float(idx) if t is None else t,
            "u": u,
            "y": y
        })

    if len(clean) < 20:
        raise RuntimeError(f"Not enough valid rows for recursive refit: {len(clean)}")

    commands = [r["u"] for r in clean]
    observed = [r["y"] for r in clean]

    train_fraction = float(config["fit_policy"]["train_fraction"])
    train_end = int(len(clean) * train_fraction)
    train_end = max(10, min(train_end, len(clean) - 5))

    train_start = 0
    validation_start = train_end
    validation_end = len(clean)

    candidates = []
    failures = []

    for family in config["fit_policy"]["model_families"]:
        for delay in config["fit_policy"]["delay_candidates"]:
            try:
                model = fit_candidate(
                    family=family,
                    delay=int(delay),
                    commands=commands,
                    observed=observed,
                    train_start=train_start,
                    train_end=train_end
                )

                train_one_pred, train_one_actual = one_step_predictions(
                    model, commands, observed, train_start, train_end
                )
                val_one_pred, val_one_actual = one_step_predictions(
                    model, commands, observed, validation_start, validation_end
                )
                train_rec_pred, train_rec_actual, _train_idx = recursive_predictions(
                    model, commands, observed, train_start, train_end
                )
                val_rec_pred, val_rec_actual, _val_idx = recursive_predictions(
                    model, commands, observed, validation_start, validation_end
                )

                candidate = dict(model)
                candidate["train_one_step_metrics"] = metrics(train_one_pred, train_one_actual)
                candidate["validation_one_step_metrics"] = metrics(val_one_pred, val_one_actual)
                candidate["train_recursive_metrics"] = metrics(train_rec_pred, train_rec_actual)
                candidate["validation_recursive_metrics"] = metrics(val_rec_pred, val_rec_actual)

                candidates.append(candidate)

            except Exception as exc:
                failures.append({
                    "family": family,
                    "delay_steps": int(delay),
                    "error": str(exc)
                })

    if not candidates:
        raise RuntimeError(f"No candidate model could be fitted. Failures={failures}")

    def selection_key(c: Dict[str, Any]) -> float:
        rmse = c["validation_recursive_metrics"]["rmse"]
        if rmse is None:
            return float("inf")
        return rmse

    candidates.sort(key=selection_key)
    selected = candidates[0]

    placeholder = extract_model_from_json(
        config["source_artifacts"]["placeholder_model_path"],
        "v0.13.0_placeholder"
    )
    previous_refit = extract_model_from_json(
        config["source_artifacts"]["v0_13_4_refit_coefficients_path"],
        "v0.13.4_no_intercept_refit"
    )

    baselines = []
    for baseline in [placeholder, previous_refit]:
        if baseline is None:
            continue
        val_rec_pred, val_rec_actual, _idx = recursive_predictions(
            baseline, commands, observed, validation_start, validation_end
        )
        val_one_pred, val_one_actual = one_step_predictions(
            baseline, commands, observed, validation_start, validation_end
        )
        baseline["validation_recursive_metrics"] = metrics(val_rec_pred, val_rec_actual)
        baseline["validation_one_step_metrics"] = metrics(val_one_pred, val_one_actual)
        baselines.append(baseline)

    placeholder_rmse = None
    previous_refit_rmse = None
    for b in baselines:
        if b["family"] == "v0.13.0_placeholder":
            placeholder_rmse = b["validation_recursive_metrics"]["rmse"]
        if b["family"] == "v0.13.4_no_intercept_refit":
            previous_refit_rmse = b["validation_recursive_metrics"]["rmse"]

    selected_rmse = selected["validation_recursive_metrics"]["rmse"]
    selected_mape = selected["validation_recursive_metrics"]["mape"]

    imp_vs_placeholder = improvement_pct(placeholder_rmse, selected_rmse)
    imp_vs_previous_refit = improvement_pct(previous_refit_rmse, selected_rmse)

    thresholds = config["decision_thresholds"]
    status = "pass"
    reasons = []

    if imp_vs_placeholder is None:
        status = "caution"
        reasons.append("Could not compute recursive RMSE improvement versus placeholder.")
    elif imp_vs_placeholder < float(thresholds["minimum_recursive_rmse_improvement_pct_vs_placeholder_for_pass"]):
        status = "caution"
        reasons.append(
            f"Recursive RMSE improvement versus placeholder is below threshold: {imp_vs_placeholder:.6g}%."
        )

    if imp_vs_previous_refit is None:
        if status == "pass":
            status = "caution"
        reasons.append("Could not compute recursive RMSE improvement versus v0.13.4 refit.")
    elif imp_vs_previous_refit < float(thresholds["minimum_recursive_rmse_improvement_pct_vs_v0_13_4_for_pass"]):
        if status == "pass":
            status = "caution"
        reasons.append(
            f"Recursive RMSE improvement versus v0.13.4 refit is below threshold: {imp_vs_previous_refit:.6g}%."
        )

    if selected_mape is not None and selected_mape > float(thresholds["maximum_validation_recursive_mape_for_pass"]):
        if status == "pass":
            status = "caution"
        reasons.append(
            f"Validation recursive MAPE is above threshold: {selected_mape:.6g}%."
        )

    if not reasons:
        reasons.append("Selected model improves recursive validation metrics versus both placeholder and v0.13.4 refit under configured thresholds.")

    if status == "pass":
        recommended_next_step = "Use the selected recursive model as the new candidate plant model in a repeat shadow-mode controller comparison stage."
    else:
        recommended_next_step = "Do not promote a model yet. Review candidate metrics and consider richer model structures or additional replay data."

    candidates_csv = os.path.join(args.output_dir, "recursive-model-candidates.csv")
    with open(candidates_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "family",
            "delay_steps",
            "c",
            "a_y",
            "b_u",
            "y_eq",
            "u_eq",
            "train_sample_count",
            "train_one_step_rmse",
            "validation_one_step_rmse",
            "train_recursive_rmse",
            "validation_recursive_rmse",
            "validation_recursive_mae",
            "validation_recursive_bias",
            "validation_recursive_mape",
            "validation_recursive_r2"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            vr = c["validation_recursive_metrics"]
            writer.writerow({
                "family": c["family"],
                "delay_steps": c["delay_steps"],
                "c": c["c"],
                "a_y": c["a_y"],
                "b_u": c["b_u"],
                "y_eq": c["y_eq"],
                "u_eq": c["u_eq"],
                "train_sample_count": c["train_sample_count"],
                "train_one_step_rmse": c["train_one_step_metrics"]["rmse"],
                "validation_one_step_rmse": c["validation_one_step_metrics"]["rmse"],
                "train_recursive_rmse": c["train_recursive_metrics"]["rmse"],
                "validation_recursive_rmse": vr["rmse"],
                "validation_recursive_mae": vr["mae"],
                "validation_recursive_bias": vr["bias"],
                "validation_recursive_mape": vr["mape"],
                "validation_recursive_r2": vr["r2"]
            })

    val_pred, val_actual, val_indices = recursive_predictions(
        selected, commands, observed, validation_start, validation_end
    )
    validation_csv = os.path.join(args.output_dir, "recursive-model-validation-timeseries.csv")
    with open(validation_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "row_index",
            "time_seconds",
            "u_cmd",
            "observed",
            "selected_recursive_prediction",
            "recursive_error",
            "model_family",
            "delay_steps",
            "actuator_applied"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for pred, actual, idx in zip(val_pred, val_actual, val_indices):
            writer.writerow({
                "row_index": clean[idx]["row_index"],
                "time_seconds": clean[idx]["time"],
                "u_cmd": commands[idx],
                "observed": actual,
                "selected_recursive_prediction": pred,
                "recursive_error": pred - actual,
                "model_family": selected["family"],
                "delay_steps": selected["delay_steps"],
                "actuator_applied": False
            })

    selected_model_path = os.path.join(args.output_dir, "selected-recursive-model.json")
    selected_model_payload = {
        "stage": config["stage"],
        "offline_only": True,
        "model_type": selected["family"],
        "equation": "y[k+1] = c + a_y*y[k] + b_u*u[k-delay]",
        "c": selected["c"],
        "a_y": selected["a_y"],
        "b_u": selected["b_u"],
        "delay_steps": selected["delay_steps"],
        "y_eq": selected["y_eq"],
        "u_eq": selected["u_eq"],
        "y0_policy": "initialize recursive validation from first observed value of validation segment",
        "selection_metric": config["fit_policy"]["selection_metric"],
        "validation_recursive_metrics": selected["validation_recursive_metrics"],
        "validation_one_step_metrics": selected["validation_one_step_metrics"]
    }
    write_json(selected_model_path, selected_model_payload)

    summary = {
        "stage": config["stage"],
        "decision": {
            "status": status,
            "reason": " ".join(reasons),
            "recommended_next_step": recommended_next_step
        },
        "offline_only": True,
        "actuator_applied": False,
        "input": {
            "replay_path": replay_path,
            "time_column": time_col,
            "command_column": command_col,
            "observed_column": observed_col,
            "valid_rows": len(clean),
            "train_rows": train_end - train_start,
            "validation_rows": validation_end - validation_start,
            "train_fraction": train_fraction
        },
        "selected_model": {
            "family": selected["family"],
            "c": selected["c"],
            "a_y": selected["a_y"],
            "b_u": selected["b_u"],
            "delay_steps": selected["delay_steps"],
            "y_eq": selected["y_eq"],
            "u_eq": selected["u_eq"],
            "train_sample_count": selected["train_sample_count"],
            "validation_recursive_metrics": selected["validation_recursive_metrics"],
            "validation_one_step_metrics": selected["validation_one_step_metrics"],
            "train_recursive_metrics": selected["train_recursive_metrics"],
            "train_one_step_metrics": selected["train_one_step_metrics"]
        },
        "baseline_comparison": {
            "placeholder_validation_recursive_rmse": placeholder_rmse,
            "v0_13_4_refit_validation_recursive_rmse": previous_refit_rmse,
            "selected_validation_recursive_rmse": selected_rmse,
            "selected_recursive_rmse_improvement_pct_vs_placeholder": imp_vs_placeholder,
            "selected_recursive_rmse_improvement_pct_vs_v0_13_4": imp_vs_previous_refit,
            "baselines": baselines
        },
        "candidate_count": len(candidates),
        "fit_failures": failures,
        "outputs": {
            "summary_json": os.path.join(args.output_dir, "recursive-model-summary.json"),
            "selected_model_json": selected_model_path,
            "candidates_csv": candidates_csv,
            "validation_timeseries_csv": validation_csv
        }
    }

    write_json(os.path.join(args.output_dir, "recursive-model-summary.json"), summary)

    print(json.dumps({
        "stage": config["stage"],
        "status": status,
        "selected_family": selected["family"],
        "selected_delay_steps": selected["delay_steps"],
        "selected_validation_recursive_rmse": selected_rmse,
        "improvement_pct_vs_placeholder": imp_vs_placeholder,
        "improvement_pct_vs_v0_13_4": imp_vs_previous_refit,
        "summary_path": os.path.join(args.output_dir, "recursive-model-summary.json")
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
