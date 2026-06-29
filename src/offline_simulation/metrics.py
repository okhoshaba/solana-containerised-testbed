from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


def compute_case_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        raise ValueError("Cannot compute metrics for an empty case.")

    abs_errors = [abs(float(row["error"])) for row in rows]
    replicas = [int(row["current_replicas"]) for row in rows]
    replica_deltas = [int(row["applied_replica_delta"]) for row in rows]
    violations = [int(row["constraint_violation"]) for row in rows]

    first = rows[0]
    return {
        "controller": first["controller"],
        "profile_id": first["profile_id"],
        "case_id": first["case_id"],
        "steps": len(rows),
        "mean_abs_error": sum(abs_errors) / len(abs_errors),
        "max_abs_error": max(abs_errors),
        "replica_changes": sum(1 for delta in replica_deltas if delta != 0),
        "total_abs_replica_change": sum(abs(delta) for delta in replica_deltas),
        "min_replicas": min(replicas),
        "max_replicas": max(replicas),
        "mean_replicas": sum(replicas) / len(replicas),
        "constraint_violations": sum(violations)
    }


def aggregate_metrics(case_metrics: Iterable[Dict[str, Any]], group_key: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for metric in case_metrics:
        grouped[str(metric[group_key])].append(metric)

    result = []
    for key, items in sorted(grouped.items()):
        result.append(
            {
                group_key: key,
                "case_count": len(items),
                "mean_abs_error": _mean(items, "mean_abs_error"),
                "max_abs_error": max(float(item["max_abs_error"]) for item in items),
                "total_abs_replica_change": sum(int(item["total_abs_replica_change"]) for item in items),
                "replica_changes": sum(int(item["replica_changes"]) for item in items),
                "constraint_violations": sum(int(item["constraint_violations"]) for item in items),
                "mean_replicas": _mean(items, "mean_replicas")
            }
        )
    return result


def _mean(items: List[Dict[str, Any]], key: str) -> float:
    return sum(float(item[key]) for item in items) / len(items)
