# coding:utf-8
from __future__ import annotations

from dataclasses import dataclass

from app.framework.application.modules import get_periodic_module_specs
from app.framework.application.tasks.periodic_task_specs import (
    PERIODIC_TASK_SPECS,
    PRIMARY_TASK_ID,
)


@dataclass(frozen=True)
class PeriodicTaskProfile:
    task_registry: dict[str, dict]
    primary_task_id: str
    mandatory_task_ids: frozenset[str]
    force_first_task_ids: frozenset[str]
    primary_option_key: str


_CACHED_PROFILE: PeriodicTaskProfile | None = None


def _build_module_class_by_task_id() -> dict[str, type]:
    mapping: dict[str, type] = {}
    for spec in get_periodic_module_specs():
        if spec.module_class is None:
            continue
        mapping[spec.id] = spec.module_class
    return mapping


def _build_task_registry() -> dict[str, dict]:
    module_class_by_task_id = _build_module_class_by_task_id()
    registry: dict[str, dict] = {}
    for spec in PERIODIC_TASK_SPECS:
        task_id = spec.get("id")
        if not task_id:
            continue
        module_class = module_class_by_task_id.get(task_id)
        if module_class is None:
            continue
        registry[task_id] = {
            "module_class": module_class,
            "ui_page_index": spec.get("ui_page_index"),
            "option_key": spec.get("option_key"),
            "zh_name": spec.get("zh_name", ""),
            "en_name": spec.get("en_name", ""),
            "requires_home_sync": spec.get("requires_home_sync", True),
            "is_mandatory": spec.get("is_mandatory", False),
            "force_first": spec.get("force_first", False),
        }
    return registry


def get_periodic_task_profile() -> PeriodicTaskProfile:
    global _CACHED_PROFILE
    if _CACHED_PROFILE is not None:
        return _CACHED_PROFILE

    registry = _build_task_registry()
    primary_task_id = PRIMARY_TASK_ID or "task_login"
    mandatory_task_ids = frozenset(
        task_id for task_id, meta in registry.items() if bool(meta.get("is_mandatory", False))
    )
    force_first_task_ids = frozenset(
        task_id for task_id, meta in registry.items() if bool(meta.get("force_first", False))
    )
    primary_option_key = registry.get(primary_task_id, {}).get("option_key", "CheckBox_entry_1")

    _CACHED_PROFILE = PeriodicTaskProfile(
        task_registry=registry,
        primary_task_id=primary_task_id,
        mandatory_task_ids=mandatory_task_ids,
        force_first_task_ids=force_first_task_ids,
        primary_option_key=primary_option_key,
    )
    return _CACHED_PROFILE

