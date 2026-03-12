from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from pathlib import Path

from app.framework.core.module_system.config_schema import build_config_schema
from app.framework.core.module_system.models import Field, ModuleHost, ModuleMeta
from app.framework.core.module_system.naming import infer_module_id
from app.framework.core.module_system.registry import register_module

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]

_PENDING_PAGES: dict[str, type] = {}
_DEFAULT_ORDER = 100

_MODULE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_declaration_text(text: object, *, field: str) -> None:
    if not str(text or "").strip():
        raise ValueError(f"{field} must be a non-empty string")


def _validate_module_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("module name must be a non-empty string")


def _validate_module_id(module_id: str) -> None:
    normalized = str(module_id or "").strip()
    if not normalized:
        raise ValueError("module_id must be a non-empty string when provided")
    if not _MODULE_ID_RE.fullmatch(normalized):
        raise ValueError(
            f"module_id must be an English identifier [A-Za-z_][A-Za-z0-9_]*, got: {module_id!r}"
        )


def _normalize_binding_token(raw: str) -> str:
    token = re.sub(r"\s+", "_", str(raw or "").strip())
    token = re.sub(r"[^\w]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    return token.lower()


def _infer_binding_id(target, resolved_id: str, declared_name: str) -> str:
    id_based = _normalize_binding_token(resolved_id)
    if id_based:
        return id_based

    try:
        class_based = infer_module_id(target)
    except Exception:
        class_based = ""
    if class_based:
        return class_based

    name_based = _normalize_binding_token(declared_name)
    if name_based:
        return name_based
    return "module"


def _default_name_msgid(target, declared_module_id: str | None, resolved_id: str) -> str:
    candidate = _normalize_binding_token(declared_module_id or "")
    if not candidate:
        try:
            candidate = infer_module_id(target)
        except Exception:
            candidate = ""
    if not candidate:
        candidate = _normalize_binding_token(resolved_id)
    candidate = candidate or "module"
    return f"module.{candidate}.title"


def _validate_declaration_fields(fields: dict[str, Field] | None) -> None:
    if not fields:
        return
    for param, meta in fields.items():
        if not isinstance(meta, Field):
            raise ValueError(f"fields[{param}] must be a Field declaration")
        if meta.name:
            _validate_declaration_text(meta.name, field=f"fields[{param}] name")
        if meta.help:
            _validate_declaration_text(meta.help, field=f"fields[{param}] help")
        if meta.options:
            for idx, option in enumerate(meta.options):
                label: str | None = None
                if isinstance(option, dict):
                    raw_label = option.get("label")
                    if isinstance(raw_label, str):
                        label = raw_label
                elif isinstance(option, (tuple, list)) and len(option) == 2:
                    left, right = option
                    if isinstance(right, str) and not isinstance(left, str):
                        label = right
                    elif isinstance(left, str) and not isinstance(right, str):
                        label = left
                    elif isinstance(right, str):
                        label = right
                if label:
                    _validate_declaration_text(label, field=f"fields[{param}] options[{idx}] label")


def _validate_declaration_actions(actions: dict[str, str] | None) -> None:
    if not actions:
        return
    for label, method_name in actions.items():
        _validate_declaration_text(label, field=f"actions[{label}] label")
        if not isinstance(method_name, str) or not method_name.strip():
            raise ValueError(f"actions[{label}] method must be a non-empty string")
        normalized = method_name.strip()
        if not re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", normalized):
            raise ValueError(
                f"actions[{label}] method must be a valid class method name, got: {method_name!r}"
            )


def _normalize_background_keys(
    background_keys: tuple[str, ...] | list[str] | str | None,
) -> tuple[str, ...]:
    if background_keys is None:
        return ()
    if isinstance(background_keys, str):
        candidates = (background_keys,)
    else:
        candidates = tuple(background_keys)

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in candidates:
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return tuple(normalized)


def _resolve_symbol(symbol_path: str):
    module_path, symbol_name = symbol_path.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    return getattr(mod, symbol_name)


def _module_package_from_target(target) -> str | None:
    module_name = getattr(target, "__module__", "")
    parts = module_name.split(".")
    if "modules" not in parts:
        return None
    idx = parts.index("modules")
    if idx + 1 >= len(parts):
        return None
    return ".".join(parts[: idx + 2])


def _module_name_from_target(target) -> str | None:
    pkg = _module_package_from_target(target)
    if not pkg:
        return None
    return pkg.split(".")[-1]


def _candidate_ui_modules(module_name: str, host: ModuleHost) -> list[str]:
    ui_package_path = f"app.features.modules.{module_name}.ui"
    try:
        ui_pkg = importlib.import_module(ui_package_path)
    except ImportError:
        return []

    found_modules = []
    if hasattr(ui_pkg, "__path__"):
        for _, name, ispkg in pkgutil.iter_modules(ui_pkg.__path__):
            if not ispkg and name != "__init__":
                found_modules.append(f"{ui_package_path}.{name}")

    priority: list[str] = []
    if host == ModuleHost.PERIODIC:
        priority.extend(sorted([m for m in found_modules if m.endswith("_periodic_page")]))
        priority.extend(sorted([m for m in found_modules if m.endswith("_interface")]))
    else:
        priority.extend(sorted([m for m in found_modules if m.endswith("_interface")]))

    seen = set(priority)
    priority.extend(sorted([m for m in found_modules if m not in seen]))
    return priority


def _extract_preferred_class_name_from_module(module_path: str, host: ModuleHost) -> str | None:
    try:
        mod = importlib.import_module(module_path)
    except Exception:
        return None

    classes = [name for name, obj in inspect.getmembers(mod, inspect.isclass)
               if obj.__module__ == module_path]
    if not classes:
        return None

    # Priority 1: Match preferred suffixes
    preferred = []
    if host == ModuleHost.PERIODIC:
        preferred = [n for n in classes if n.endswith("Page") or n.endswith("Interface")]
    else:
        preferred = [n for n in classes if n.endswith("Interface") or n.endswith("Page")]
    
    if preferred:
        return preferred[0]

    # If no preferred suffix is found, we do NOT return any random class.
    # This prevents misidentifying internal logic classes (like AdjustColor) as UI pages.
    return None


def _infer_page_class_path(target, host: ModuleHost) -> str | None:
    module_name = _module_name_from_target(target)
    if not module_name:
        return None

    for module_path in _candidate_ui_modules(module_name, host):
        class_name = _extract_preferred_class_name_from_module(module_path, host)
        if class_name:
            return f"{module_path}:{class_name}"

    return None


def _infer_periodic_index(resolved_order: int) -> int:
    # Most periodic tasks use step-10 ordering. Keep deterministic mapping.
    return max(0, (resolved_order // 10) - 1)


def _infer_ui_bindings(
    resolved_id: str,
    module_name: str | None,
    host: ModuleHost,
    *,
    binding_id: str,
    page_alias: str | None = None,
):
    from app.framework.application.modules.contracts import ModuleUiBindings

    normalized_page_alias = _normalize_binding_token(page_alias or "")
    module_token = _normalize_binding_token(module_name or "")
    resolved_token = _normalize_binding_token(resolved_id)

    if host == ModuleHost.PERIODIC:
        alias = normalized_page_alias or module_token
        if not alias:
            if resolved_id.startswith("task_"):
                alias = _normalize_binding_token(resolved_id[len("task_"):])
            else:
                alias = resolved_token
        alias = alias or "module"
        return ModuleUiBindings(page_attr=f"page_{alias}")

    # on-demand defaults
    binding_token = _normalize_binding_token(binding_id or resolved_id) or "module"
    suffix = normalized_page_alias or binding_token
    page_attr = f"page_{suffix}"

    return ModuleUiBindings(
        page_attr=page_attr,
        start_button_attr=f"PushButton_start_{binding_token}",
        card_widget_attr=f"SimpleCardWidget_{suffix}",
        log_widget_attr=f"textBrowser_log_{binding_token}",
    )


def _periodic_activation_defaults(
    periodic_default_activation_config: list[dict] | tuple[dict, ...] | None,
) -> list[dict]:
    if periodic_default_activation_config:
        normalized: list[dict] = []
        for item in periodic_default_activation_config:
            if isinstance(item, dict):
                normalized.append(dict(item))
        if normalized:
            return normalized
    return [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]


def _build_meta(
    *,
    target,
    host: ModuleHost,
    name: str,
    fields: dict[str, Field] | None,
    actions: dict[str, str] | None,
    module_id: str | None,
    binding_id: str | None = None,
    page_alias: str | None = None,
    order: int | None = None,
    enabled: bool = True,
    notify_on_completion: bool | None = None,
    passive: bool | None = None,
    on_demand_execution: str | None = None,
    on_demand_background_keys: tuple[str, ...] | list[str] | str | None = None,
    auto_page_collapsible_groups: bool | None = None,
    auto_page_groups_collapsed_by_default: bool | None = None,
    periodic_enabled_by_default: bool | None = None,
    periodic_role: str | None = None,
    periodic_mandatory: bool | None = None,
    periodic_force_first: bool | None = None,
    periodic_requires_home_sync: bool | None = None,
    periodic_option_key: str | None = None,
    periodic_default_activation_config: list[dict] | tuple[dict, ...] | None = None,
    description: str = "",
) -> ModuleMeta:
    _validate_module_name(name)
    _validate_declaration_fields(fields)
    _validate_declaration_actions(actions)

    module_name = _module_name_from_target(target)
    inferred_id = infer_module_id(target)
    if host == ModuleHost.PERIODIC and not inferred_id.startswith("task_"):
        inferred_id = f"task_{inferred_id}"
    if module_id is not None:
        _validate_module_id(module_id)
    resolved_id = str(module_id or inferred_id).strip()
    declared_binding_id = str(binding_id or "").strip()
    if declared_binding_id:
        resolved_binding_id = _normalize_binding_token(declared_binding_id)
        if not resolved_binding_id:
            raise ValueError(f"binding_id must be a non-empty identifier, got: {binding_id!r}")
    else:
        resolved_binding_id = _infer_binding_id(target, resolved_id, name)

    name_msgid = _default_name_msgid(target, module_id, resolved_id)
    resolved_order = int(_DEFAULT_ORDER if order is None else order)
    resolved_page_class_path = _infer_page_class_path(target, host)
    resolved_ui_bindings = _infer_ui_bindings(
        resolved_id,
        module_name,
        host,
        binding_id=resolved_binding_id,
        page_alias=page_alias,
    )
    resolved_passive = bool(False if passive is None else passive)
    resolved_notify_on_completion = True if notify_on_completion is None else bool(notify_on_completion)
    resolved_on_demand_execution = "exclusive"
    resolved_background_keys: tuple[str, ...] = ()
    resolved_auto_page_collapsible_groups = bool(auto_page_collapsible_groups) if auto_page_collapsible_groups is not None else False
    if auto_page_groups_collapsed_by_default is None:
        resolved_auto_page_groups_collapsed_by_default = False
    else:
        resolved_auto_page_groups_collapsed_by_default = bool(auto_page_groups_collapsed_by_default)
    if host == ModuleHost.ON_DEMAND:
        requested_execution = "exclusive" if on_demand_execution is None else on_demand_execution
        resolved_on_demand_execution = str(requested_execution).strip().lower()
        if resolved_on_demand_execution not in {"exclusive", "background"}:
            raise ValueError(
                "on_demand execution must be either 'exclusive' or 'background', "
                f"got: {on_demand_execution!r}"
            )
        resolved_background_keys = _normalize_background_keys(on_demand_background_keys)

    normalized_periodic_role = str(periodic_role or "").strip().lower()
    if normalized_periodic_role and normalized_periodic_role not in {"bootstrap"}:
        raise ValueError(
            "periodic_role must be one of: 'bootstrap'. "
            f"got: {periodic_role!r}"
        )
    is_bootstrap_role = normalized_periodic_role == "bootstrap"

    resolved_periodic_enabled_by_default = bool(periodic_enabled_by_default) if periodic_enabled_by_default is not None else False
    resolved_periodic_mandatory = bool(periodic_mandatory) if periodic_mandatory is not None else is_bootstrap_role
    resolved_periodic_force_first = bool(periodic_force_first) if periodic_force_first is not None else is_bootstrap_role
    if periodic_requires_home_sync is None:
        resolved_periodic_requires_home_sync = not is_bootstrap_role
    else:
        resolved_periodic_requires_home_sync = bool(periodic_requires_home_sync)
    resolved_periodic_ui_page_index = _infer_periodic_index(resolved_order) if host == ModuleHost.PERIODIC else None
    if host == ModuleHost.PERIODIC:
        default_option_key = f"CheckBox_{_normalize_binding_token(resolved_id)}"
        resolved_periodic_option_key = str(periodic_option_key or "").strip() or default_option_key
    else:
        resolved_periodic_option_key = None
    resolved_activation_config = _periodic_activation_defaults(periodic_default_activation_config) if host == ModuleHost.PERIODIC else []

    module_class = target if isinstance(target, type) else None
    schema_target = target
    runner = target
    if isinstance(target, type):
        run_method = getattr(target, "run", None)
        if callable(run_method):
            runner = run_method
        else:
            runner = lambda *args, **kwargs: None

    i18n_owner_dir = str(Path(target.__module__.replace(".", "/")))
    meta = ModuleMeta(
        id=resolved_id,
        name=name,
        name_msgid=name_msgid,
        binding_id=resolved_binding_id,
        host=host,
        runner=runner,
        order=resolved_order,
        description=description,
        enabled=enabled,
        notify_on_completion=resolved_notify_on_completion,
        passive=resolved_passive,
        on_demand_execution=resolved_on_demand_execution,
        on_demand_background_keys=resolved_background_keys,
        auto_page_collapsible_groups=resolved_auto_page_collapsible_groups,
        auto_page_groups_collapsed_by_default=resolved_auto_page_groups_collapsed_by_default,
        module_class=module_class,
        periodic_enabled_by_default=resolved_periodic_enabled_by_default,
        periodic_mandatory=resolved_periodic_mandatory,
        periodic_force_first=resolved_periodic_force_first,
        periodic_default_hour=0,
        periodic_default_minute=0,
        periodic_max_runs=1,
        periodic_requires_home_sync=resolved_periodic_requires_home_sync,
        periodic_ui_page_index=resolved_periodic_ui_page_index,
        periodic_option_key=resolved_periodic_option_key,
        periodic_default_activation_config=resolved_activation_config,
        source_lang=DEFAULT_SOURCE_LANG,
        i18n_owner_dir=i18n_owner_dir,
        config_schema=build_config_schema(
            schema_target,
            module_id=resolved_id,
            fields=fields,
        ),
        actions=dict(actions or {}),
    )
    meta.ui_bindings = resolved_ui_bindings
    if resolved_page_class_path:
        meta.ui_factory = (
            lambda parent, _host, **_kwargs: _resolve_symbol(_kwargs.get('_path', resolved_page_class_path))(parent)
        )

    if resolved_id in _PENDING_PAGES:
        meta.page_cls = _PENDING_PAGES.pop(resolved_id)
    return meta


def _register_with_host(
    *,
    host: ModuleHost,
    name: str,
    fields: dict[str, Field] | None = None,
    actions: dict[str, str] | None = None,
    module_id: str | None = None,
    binding_id: str | None = None,
    page_alias: str | None = None,
    order: int | None = None,
    enabled: bool = True,
    notify_on_completion: bool | None = None,
    passive: bool | None = None,
    on_demand_execution: str | None = None,
    on_demand_background_keys: tuple[str, ...] | list[str] | str | None = None,
    auto_page_collapsible_groups: bool | None = None,
    auto_page_groups_collapsed_by_default: bool | None = None,
    periodic_enabled_by_default: bool | None = None,
    periodic_role: str | None = None,
    periodic_mandatory: bool | None = None,
    periodic_force_first: bool | None = None,
    periodic_requires_home_sync: bool | None = None,
    periodic_option_key: str | None = None,
    periodic_default_activation_config: list[dict] | tuple[dict, ...] | None = None,
    description: str = "",
):
    def decorator(target):
        meta = _build_meta(
            target=target,
            host=host,
            name=name,
            fields=fields,
            actions=actions,
            module_id=module_id,
            binding_id=binding_id,
            page_alias=page_alias,
            order=order,
            enabled=enabled,
            notify_on_completion=notify_on_completion,
            passive=passive,
            on_demand_execution=on_demand_execution,
            on_demand_background_keys=on_demand_background_keys,
            auto_page_collapsible_groups=auto_page_collapsible_groups,
            auto_page_groups_collapsed_by_default=auto_page_groups_collapsed_by_default,
            periodic_enabled_by_default=periodic_enabled_by_default,
            periodic_role=periodic_role,
            periodic_mandatory=periodic_mandatory,
            periodic_force_first=periodic_force_first,
            periodic_requires_home_sync=periodic_requires_home_sync,
            periodic_option_key=periodic_option_key,
            periodic_default_activation_config=periodic_default_activation_config,
            description=description,
        )
        register_module(meta)
        return target

    return decorator


def on_demand_module(
    name: str,
    *,
    fields: dict[str, Field] | None = None,
    actions: dict[str, str] | None = None,
    module_id: str | None = None,
    binding_id: str | None = None,
    page_alias: str | None = None,
    order: int | None = None,
    notify_on_completion: bool | None = None,
    passive: bool | None = None,
    execution: str | None = None,
    background_keys: tuple[str, ...] | list[str] | str | None = None,
    auto_page_collapsible_groups: bool | None = None,
    auto_page_groups_collapsed_by_default: bool | None = None,
    description: str = "",
):
    return _register_with_host(
        host=ModuleHost.ON_DEMAND,
        name=name,
        fields=fields,
        actions=actions,
        module_id=module_id,
        binding_id=binding_id,
        page_alias=page_alias,
        order=order,
        notify_on_completion=notify_on_completion,
        passive=passive,
        on_demand_execution=execution,
        on_demand_background_keys=background_keys,
        auto_page_collapsible_groups=auto_page_collapsible_groups,
        auto_page_groups_collapsed_by_default=auto_page_groups_collapsed_by_default,
        description=description,
    )


def periodic_module(
    name: str,
    *,
    fields: dict[str, Field] | None = None,
    actions: dict[str, str] | None = None,
    module_id: str | None = None,
    binding_id: str | None = None,
    page_alias: str | None = None,
    order: int | None = None,
    notify_on_completion: bool | None = None,
    periodic_enabled_by_default: bool | None = None,
    periodic_role: str | None = None,
    periodic_mandatory: bool | None = None,
    periodic_force_first: bool | None = None,
    periodic_requires_home_sync: bool | None = None,
    periodic_option_key: str | None = None,
    periodic_default_activation_config: list[dict] | tuple[dict, ...] | None = None,
    auto_page_collapsible_groups: bool | None = None,
    auto_page_groups_collapsed_by_default: bool | None = None,
    description: str = "",
):
    return _register_with_host(
        host=ModuleHost.PERIODIC,
        name=name,
        fields=fields,
        actions=actions,
        module_id=module_id,
        binding_id=binding_id,
        page_alias=page_alias,
        order=order,
        notify_on_completion=notify_on_completion,
        periodic_enabled_by_default=periodic_enabled_by_default,
        periodic_role=periodic_role,
        periodic_mandatory=periodic_mandatory,
        periodic_force_first=periodic_force_first,
        periodic_requires_home_sync=periodic_requires_home_sync,
        periodic_option_key=periodic_option_key,
        periodic_default_activation_config=periodic_default_activation_config,
        auto_page_collapsible_groups=auto_page_collapsible_groups,
        auto_page_groups_collapsed_by_default=auto_page_groups_collapsed_by_default,
        description=description,
    )


def module_page(module_id: str):
    def decorator(cls: type):
        from app.framework.core.module_system.registry import get_module

        meta = get_module(module_id)
        if meta is not None:
            meta.page_cls = cls
            if meta.ui_factory is None:
                meta.ui_factory = lambda parent, _host, **_: cls(parent)
        else:
            _PENDING_PAGES[module_id] = cls
        return cls

    return decorator


