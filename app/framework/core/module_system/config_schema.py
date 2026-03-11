from __future__ import annotations

import inspect
from typing import Any

from app.framework.core.module_system.models import Field, SchemaField
from app.framework.core.module_system.naming import humanize_name


RUNTIME_PARAMS = {
    "self",
    "cls",
    "auto",
    "automation",
    "logger",
    "app_config",
    "config_provider",
    "cancel_token",
    "task_context",
}


def _resolve_field_meta(
    *,
    module_id: str,
    param_name: str,
    field_decl: str | Field | None,
) -> tuple[str, str, str | None, str, str, str | None, str, str | None, str | None]:
    if isinstance(field_decl, Field):
        field_id = field_decl.id or param_name
        label_default = field_decl.label or humanize_name(param_name)
        help_default = field_decl.help
        group = field_decl.group
        layout = field_decl.layout
        icon = field_decl.icon
        description_md = field_decl.description_md
    elif isinstance(field_decl, str):
        field_id = param_name
        label_default = field_decl
        help_default = None
        group = None
        layout = "full"
        icon = None
        description_md = None
    else:
        field_id = param_name
        label_default = humanize_name(param_name)
        help_default = None
        group = None
        layout = "full"
        icon = None
        description_md = None

    label_key = f"module.{module_id}.field.{field_id}.label"
    help_key = f"module.{module_id}.field.{field_id}.help"
    return field_id, label_default, help_default, label_key, help_key, group, layout, icon, description_md


def build_config_schema(
    func,
    *,
    module_id: str,
    fields: dict[str, str | Field] | None = None,
) -> list[SchemaField]:
    sig = inspect.signature(func)
    schema: list[SchemaField] = []
    field_defs: dict[str, str | Field] = fields or {}

    for name, param in sig.parameters.items():
        if name in RUNTIME_PARAMS:
            continue
        field_id, label_default, help_default, label_key, help_key, group, layout, icon, description_md = _resolve_field_meta(
            module_id=module_id,
            param_name=name,
            field_decl=field_defs.get(name),
        )
        schema.append(
            SchemaField(
                param_name=name,
                field_id=field_id,
                type_hint=param.annotation,
                default=None if param.default is inspect._empty else param.default,
                required=param.default is inspect._empty,
                label_key=label_key,
                help_key=help_key,
                label_default=label_default,
                help_default=help_default,
                group=group,
                layout=layout,
                icon=icon,
                description_md=description_md,
            )
        )
    return schema
