# coding:utf-8
from __future__ import annotations

from typing import Callable, Iterable


def collect_checked_tasks(
    task_order: list[str],
    is_checked: Callable[[str], bool],
) -> list[str]:
    return [task_id for task_id in task_order if is_checked(task_id)]


def collect_checked_tasks_from(
    task_order: list[str],
    start_task_id: str,
    is_checked: Callable[[str], bool],
) -> list[str]:
    tasks: list[str] = []
    started = False
    for task_id in task_order:
        if task_id == start_task_id:
            started = True
        if started and is_checked(task_id):
            tasks.append(task_id)
    return tasks


def collect_checked_task_ids_for_rule(
    task_order: list[str],
    is_checked: Callable[[str], bool],
    primary_task_id: str,
    current_panel_task_id: str | None,
    allow_primary_when_current: bool,
) -> list[str]:
    selected: list[str] = []
    for task_id in task_order:
        if task_id == primary_task_id and not (
            allow_primary_when_current and current_panel_task_id == primary_task_id
        ):
            continue
        if is_checked(task_id):
            selected.append(task_id)
    return selected


def normalize_tasks_for_launch(
    task_ids: Iterable[str],
    primary_task_id: str,
    should_force_primary: bool,
) -> list[str]:
    normalized = [task_id for task_id in task_ids if task_id != primary_task_id]
    if should_force_primary:
        normalized.insert(0, primary_task_id)
    return normalized


def upsert_rule_to_tasks(
    sequence: list[dict],
    target_task_ids: set[str],
    primary_task_id: str,
    rule_data: dict,
) -> int:
    modified_count = 0
    for task_cfg in sequence:
        task_id = task_cfg.get("id")
        if task_id not in target_task_ids or task_id == primary_task_id:
            continue

        task_cfg["use_periodic"] = True
        existing_rules = task_cfg.get("execution_config", [])
        if not isinstance(existing_rules, list):
            existing_rules = []

        is_duplicate = False
        for existing_rule in existing_rules:
            if (
                existing_rule.get("type") == rule_data.get("type")
                and existing_rule.get("day") == rule_data.get("day")
                and existing_rule.get("time") == rule_data.get("time")
            ):
                existing_rule["max_runs"] = rule_data.get("max_runs")
                is_duplicate = True
                break

        if not is_duplicate:
            existing_rules.append(
                {
                    "type": rule_data.get("type"),
                    "day": rule_data.get("day"),
                    "time": rule_data.get("time"),
                    "max_runs": rule_data.get("max_runs"),
                }
            )

        task_cfg["execution_config"] = existing_rules
        modified_count += 1

    return modified_count


def withdraw_rule_from_tasks(
    sequence: list[dict],
    target_task_ids: set[str],
    rule_data: dict,
) -> int:
    modified_count = 0
    for task_cfg in sequence:
        if task_cfg.get("id") not in target_task_ids:
            continue

        existing_rules = task_cfg.get("execution_config", [])
        if not isinstance(existing_rules, list):
            continue

        original_len = len(existing_rules)
        new_rules = [
            rule
            for rule in existing_rules
            if not (
                rule.get("type") == rule_data.get("type")
                and rule.get("day") == rule_data.get("day")
                and rule.get("time") == rule_data.get("time")
            )
        ]

        if len(new_rules) < original_len:
            task_cfg["execution_config"] = new_rules
            modified_count += 1

    return modified_count


def build_active_schedule_lines(
    sequence: list[dict],
    task_registry: dict[str, dict],
    is_non_chinese_ui: bool,
) -> list[str]:
    color_task = "#00BFFF"
    color_type = "#32CD32"
    color_time = "#FFA500"
    lines: list[str] = []

    for task_cfg in sequence:
        task_id = task_cfg.get("id")
        if not task_cfg.get("use_periodic", False):
            continue

        rules = task_cfg.get("execution_config", [])
        if not rules:
            continue

        meta = task_registry.get(task_id, {})
        task_name = (
            meta.get("en_name", task_id)
            if is_non_chinese_ui
            else meta.get("zh_name", task_id)
        )

        rule_strs: list[str] = []
        for rule in rules:
            rule_type = str(rule.get("type", "daily")).lower()
            rule_time = rule.get("time", "00:00")
            rule_day = int(rule.get("day", 0))
            colored_time = f'<span style="color: {color_time};"><b>{rule_time}</b></span>'

            if rule_type in {"daily", "每天"}:
                type_label = "Daily" if is_non_chinese_ui else "每天"
                rule_strs.append(
                    f'<span style="color: {color_type};">{type_label}</span> {colored_time}'
                )
                continue

            if rule_type in {"weekly", "每周"}:
                weekday_names = (
                    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    if is_non_chinese_ui
                    else ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                )
                safe_idx = min(max(rule_day, 0), len(weekday_names) - 1)
                rule_strs.append(
                    f'<span style="color: {color_type};">{weekday_names[safe_idx]}</span> {colored_time}'
                )
                continue

            if rule_type in {"monthly", "每月"}:
                type_label = f"Day {rule_day}" if is_non_chinese_ui else f"每月{rule_day}日"
                rule_strs.append(
                    f'<span style="color: {color_type};">{type_label}</span> {colored_time}'
                )

        if rule_strs:
            lines.append(
                f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='color: {color_task};'><b>[{task_name}]</b></span> ➔ {', '.join(rule_strs)}"
            )

    return lines

