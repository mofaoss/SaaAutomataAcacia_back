# coding:utf-8
import copy
from typing import Any, Dict, List


def normalize_daily_task_sequence(
    sequence: List[Dict[str, Any]],
    defaults: List[Dict[str, Any]],
    mandatory_task_ids: set[str],
    primary_task_id: str,
) -> List[Dict[str, Any]]:
    """Normalize persisted daily sequence against defaults and policy constraints."""
    default_by_id = {item["id"]: item for item in defaults}
    normalized = []
    seen = set()

    for item in sequence or []:
        task_id = item.get("id")
        if task_id not in default_by_id:
            continue
        merged = copy.deepcopy(default_by_id[task_id])
        merged.update(item)

        activation_rules = merged.get("activation_config")
        if activation_rules is None:
            activation_rules = merged.get("refresh_config", {}) or {}
        if isinstance(activation_rules, dict):
            activation_rules = [activation_rules]
        if not activation_rules:
            activation_rules = [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
        merged["activation_config"] = activation_rules
        merged.pop("refresh_config", None)

        execution_rules = merged.get("execution_config")
        if execution_rules is None:
            execution_rules = []
        elif isinstance(execution_rules, dict):
            execution_rules = [execution_rules]
        merged["execution_config"] = execution_rules

        normalized.append(merged)
        seen.add(task_id)

    for item in defaults:
        if item["id"] in seen:
            continue
        missing = copy.deepcopy(item)
        missing["execution_config"] = []
        if not missing.get("activation_config"):
            missing["activation_config"] = [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]
        normalized.append(missing)

    for task in normalized:
        if task["id"] in mandatory_task_ids:
            task["enabled"] = True

    first_task = next((t for t in normalized if t["id"] == primary_task_id), None)
    if first_task:
        normalized.remove(first_task)
        normalized.insert(0, first_task)

    return normalized

