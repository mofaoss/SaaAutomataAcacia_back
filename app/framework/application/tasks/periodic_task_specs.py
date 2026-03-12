# coding:utf-8
"""Periodic task specs generated from module-system metadata."""

from __future__ import annotations

from app.framework.core.module_system import build_periodic_profiles


def _build_periodic_specs():
    profiles = build_periodic_profiles()
    specs = []
    for profile in profiles:
        specs.append(
            {
                "id": profile.get("task_id"),
                "ui_page_index": profile.get("ui_page_index"),
                "option_key": profile.get("option_key"),
                "requires_home_sync": profile.get("requires_home_sync", True),
                "notify_on_completion": profile.get("notify_on_completion", True),
                "is_mandatory": profile.get("mandatory", False),
                "force_first": profile.get("force_first", False),
                "default_activation_config": list(profile.get("default_activation_config", [])),
            }
        )
    return specs


def _pick_primary_task_id(specs):
    for spec in specs:
        if bool(spec.get("force_first", False)):
            return spec.get("id")
    for spec in specs:
        if bool(spec.get("is_mandatory", False)):
            return spec.get("id")
    return specs[0].get("id") if specs else ""


PERIODIC_TASK_SPECS = _build_periodic_specs()
PRIMARY_TASK_ID = _pick_primary_task_id(PERIODIC_TASK_SPECS)

__all__ = ["PERIODIC_TASK_SPECS", "PRIMARY_TASK_ID"]
