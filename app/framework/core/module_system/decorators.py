from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

from app.framework.core.module_system.config_schema import build_config_schema
from app.framework.core.module_system.models import Field, ModuleHost, ModuleMeta
from app.framework.core.module_system.naming import infer_module_id
from app.framework.core.module_system.registry import register_module

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]

_PENDING_PAGES: dict[str, type] = {}
_DEFAULT_ORDER: dict[str, int] = {
    # periodic
    "task_login": 10,
    "task_supplies": 20,
    "task_shop": 30,
    "task_stamina": 40,
    "task_shards": 50,
    "task_chasm": 60,
    "task_reward": 70,
    "task_operation": 80,
    "task_weapon": 90,
    "task_shard_exchange": 100,
    "task_close_game": 110,
    # on-demand
    "trigger": 10,
    "fishing": 20,
    "action": 30,
    "water_bomb": 40,
    "alien_guardian": 50,
    "maze": 60,
    "drink": 70,
    "capture_pals": 80,
    "massaging": 90,
}

# Keep only true policy-level periodic overrides here. UI class discovery and UI bindings
# are inferred from module location and naming conventions.
_PERIODIC_POLICY_OVERRIDES: dict[str, dict] = {
    "task_login": {
        "periodic_mandatory": True,
        "periodic_force_first": True,
        "periodic_requires_home_sync": False,
    },
    "task_chasm": {
        "periodic_default_activation_config": [{"type": "weekly", "day": 1, "time": "10:00", "max_runs": 1}],
    },
    "task_close_game": {
        "periodic_requires_home_sync": False,
    },
}

# Backed by existing config keys for periodic option persistence.
_PERIODIC_OPTION_KEY_OVERRIDES: dict[str, str] = {
    "task_login": "CheckBox_entry_1",
    "task_supplies": "CheckBox_stamina_2",
    "task_shop": "CheckBox_shop_3",
    "task_stamina": "CheckBox_use_power_4",
    "task_shards": "CheckBox_person_5",
    "task_chasm": "CheckBox_chasm_6",
    "task_reward": "CheckBox_reward_7",
    "task_operation": "CheckBox_operation_8",
    "task_weapon": "CheckBox_weapon_8",
    "task_shard_exchange": "CheckBox_shard_exchange_9",
    "task_close_game": "CheckBox_close_game_10",
}

_PERIODIC_PAGE_ATTR_ALIAS: dict[str, str] = {
    "task_login": "enter",
    "task_supplies": "collect",
    "task_shop": "shop",
    "task_stamina": "use_power",
    "task_shards": "person",
    "task_chasm": "chasm",
    "task_reward": "reward",
    "task_operation": "operation",
    "task_weapon": "weapon",
    "task_shard_exchange": "shard_exchange",
    "task_close_game": "close_game",
}

_ON_DEMAND_PAGE_ALIAS: dict[str, str] = {
    "drink": "card",
}

_ON_DEMAND_PASSIVE: dict[str, bool] = {
    "trigger": True,
}

# Keep module ids stable while declarations stay minimal (no explicit module_id).
# Keys are package folder names under app/features/modules.
_PERIODIC_MODULE_ID_BY_PACKAGE: dict[str, str] = {
    "enter_game": "task_login",
    "collect_supplies": "task_supplies",
    "shopping": "task_shop",
    "use_power": "task_stamina",
    "person": "task_shards",
    "chasm": "task_chasm",
    "get_reward": "task_reward",
    "operation_action": "task_operation",
    "upgrade": "task_weapon",
    "jigsaw": "task_shard_exchange",
    "close_game": "task_close_game",
}

_ON_DEMAND_MODULE_ID_BY_PACKAGE: dict[str, str] = {
    "trigger": "trigger",
    "fishing": "fishing",
    "operation_action": "action",
    "water_bomb": "water_bomb",
    "alien_guardian": "alien_guardian",
    "maze": "maze",
    "drink": "drink",
    "capture_pals": "capture_pals",
    "massaging": "massaging",
}

_EN_DECL_RE = re.compile(r"^[\x20-\x7E]+$")


def _validate_english_declaration(text: str, *, field: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{field} must be a non-empty English string")
    if not _EN_DECL_RE.fullmatch(text):
        raise ValueError(
            f"{field} must use English ASCII declaration text only (found unsupported chars): {text!r}"
        )


def _validate_declaration_fields(fields: dict[str, str | Field] | None) -> None:
    if not fields:
        return
    for param, meta in fields.items():
        if isinstance(meta, str):
            _validate_english_declaration(meta, field=f"fields[{param}] label")
        elif isinstance(meta, Field):
            if meta.label:
                _validate_english_declaration(meta.label, field=f"fields[{param}] label")
            if meta.help:
                _validate_english_declaration(meta.help, field=f"fields[{param}] help")


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


def _ui_dir_from_module_name(module_name: str) -> Path:
    root = Path(__file__).resolve().parents[4]
    return root / "app" / "features" / "modules" / module_name / "ui"


def _candidate_ui_files(ui_dir: Path, host: ModuleHost) -> list[Path]:
    if not ui_dir.exists():
        return []

    all_py = [p for p in ui_dir.glob("*.py") if p.name != "__init__.py"]
    priority: list[Path] = []

    if host == ModuleHost.PERIODIC:
        priority.extend(sorted([p for p in all_py if p.name.endswith("_periodic_page.py")]))
        priority.extend(sorted([p for p in all_py if p.name.endswith("_interface.py")]))
    else:
        priority.extend(sorted([p for p in all_py if p.name.endswith("_interface.py")]))

    seen = {p.name for p in priority}
    priority.extend(sorted([p for p in all_py if p.name not in seen]))
    return priority


def _extract_preferred_class_name(py_file: Path, host: ModuleHost) -> str | None:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return None

    class_names = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    if not class_names:
        return None

    if host == ModuleHost.PERIODIC:
        for name in class_names:
            if name.endswith("Page"):
                return name
        for name in class_names:
            if name.endswith("Interface"):
                return name
    else:
        for name in class_names:
            if name.endswith("Interface"):
                return name
        for name in class_names:
            if name.endswith("Page"):
                return name

    return class_names[0]


def _infer_page_class_path(target, host: ModuleHost) -> str | None:
    module_name = _module_name_from_target(target)
    if not module_name:
        return None

    ui_dir = _ui_dir_from_module_name(module_name)
    for py_file in _candidate_ui_files(ui_dir, host):
        class_name = _extract_preferred_class_name(py_file, host)
        if not class_name:
            continue

        rel = py_file.relative_to(Path(__file__).resolve().parents[4]).with_suffix("")
        module_import = ".".join(rel.parts)
        return f"{module_import}:{class_name}"

    return None


def _infer_periodic_index(resolved_order: int) -> int:
    # Most periodic tasks use step-10 ordering. Keep deterministic mapping.
    return max(0, (resolved_order // 10) - 1)


def _infer_ui_bindings(resolved_id: str, module_name: str | None, host: ModuleHost):
    from app.framework.application.modules.contracts import ModuleUiBindings

    if host == ModuleHost.PERIODIC:
        alias = _PERIODIC_PAGE_ATTR_ALIAS.get(resolved_id, module_name or resolved_id)
        return ModuleUiBindings(page_attr=f"page_{alias}")

    # on-demand defaults
    suffix = _ON_DEMAND_PAGE_ALIAS.get(resolved_id, resolved_id)
    page_attr = f"page_{suffix}"
    if resolved_id == "trigger":
        return ModuleUiBindings(page_attr=page_attr, log_widget_attr="textBrowser_log_trigger")

    return ModuleUiBindings(
        page_attr=page_attr,
        start_button_attr=f"PushButton_start_{resolved_id}",
        card_widget_attr=f"SimpleCardWidget_{suffix}",
        log_widget_attr=f"textBrowser_log_{resolved_id}",
    )


def _periodic_activation_defaults(resolved_id: str) -> list[dict]:
    if resolved_id in _PERIODIC_POLICY_OVERRIDES and "periodic_default_activation_config" in _PERIODIC_POLICY_OVERRIDES[resolved_id]:
        return list(_PERIODIC_POLICY_OVERRIDES[resolved_id]["periodic_default_activation_config"])
    return [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}]


def _build_meta(
    *,
    target,
    host: ModuleHost,
    name: str,
    fields: dict[str, str | Field] | None,
    module_id: str | None,
    order: int | None = None,
    enabled: bool = True,
    passive: bool | None = None,
    description: str = "",
) -> ModuleMeta:
    _validate_english_declaration(name, field="module name")
    _validate_declaration_fields(fields)

    module_name = _module_name_from_target(target)
    inferred_id = infer_module_id(target)
    if host == ModuleHost.PERIODIC and module_name in _PERIODIC_MODULE_ID_BY_PACKAGE:
        inferred_id = _PERIODIC_MODULE_ID_BY_PACKAGE[module_name]
    elif host == ModuleHost.ON_DEMAND and module_name in _ON_DEMAND_MODULE_ID_BY_PACKAGE:
        inferred_id = _ON_DEMAND_MODULE_ID_BY_PACKAGE[module_name]
    elif host == ModuleHost.PERIODIC and not inferred_id.startswith("task_"):
        inferred_id = f"task_{inferred_id}"
    resolved_id = module_id or inferred_id
    resolved_order = int(_DEFAULT_ORDER.get(resolved_id, 100) if order is None else order)
    resolved_page_class_path = _infer_page_class_path(target, host)
    resolved_ui_bindings = _infer_ui_bindings(resolved_id, module_name, host)
    resolved_passive = bool(_ON_DEMAND_PASSIVE.get(resolved_id, False) if passive is None else passive)

    periodic_overrides = _PERIODIC_POLICY_OVERRIDES.get(resolved_id, {})
    resolved_periodic_enabled_by_default = bool(periodic_overrides.get("periodic_enabled_by_default", False))
    resolved_periodic_mandatory = bool(periodic_overrides.get("periodic_mandatory", False))
    resolved_periodic_force_first = bool(periodic_overrides.get("periodic_force_first", False))
    resolved_periodic_requires_home_sync = bool(periodic_overrides.get("periodic_requires_home_sync", True))
    resolved_periodic_ui_page_index = _infer_periodic_index(resolved_order) if host == ModuleHost.PERIODIC else None
    resolved_periodic_option_key = _PERIODIC_OPTION_KEY_OVERRIDES.get(resolved_id)
    resolved_activation_config = _periodic_activation_defaults(resolved_id) if host == ModuleHost.PERIODIC else []

    module_class = target if isinstance(target, type) else None
    schema_target = target
    runner = target
    if isinstance(target, type):
        run_method = getattr(target, "run", None)
        if callable(run_method):
            runner = run_method
            schema_target = run_method
        else:
            runner = lambda *args, **kwargs: None

    i18n_owner_dir = str(Path(target.__module__.replace(".", "/")))
    meta = ModuleMeta(
        id=resolved_id,
        name=name,
        en_name=name,
        host=host,
        runner=runner,
        order=resolved_order,
        description=description,
        enabled=enabled,
        passive=resolved_passive,
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
    )
    meta.ui_bindings = resolved_ui_bindings
    if resolved_page_class_path:
        meta.ui_factory = (
            lambda parent, _host, _path=resolved_page_class_path: _resolve_symbol(_path)(parent)
        )

    if resolved_id in _PENDING_PAGES:
        meta.page_cls = _PENDING_PAGES.pop(resolved_id)
    return meta


def _register_with_host(
    *,
    host: ModuleHost,
    name: str,
    fields: dict[str, str | Field] | None = None,
    module_id: str | None = None,
    order: int | None = None,
    enabled: bool = True,
    passive: bool | None = None,
    description: str = "",
):
    def decorator(target):
        meta = _build_meta(
            target=target,
            host=host,
            name=name,
            fields=fields,
            module_id=module_id,
            order=order,
            enabled=enabled,
            passive=passive,
            description=description,
        )
        register_module(meta)
        return target

    return decorator


def on_demand_module(
    name: str,
    *,
    fields: dict[str, str | Field] | None = None,
    module_id: str | None = None,
):
    return _register_with_host(
        host=ModuleHost.ON_DEMAND,
        name=name,
        fields=fields,
        module_id=module_id,
    )


def periodic_module(
    name: str,
    *,
    fields: dict[str, str | Field] | None = None,
    module_id: str | None = None,
):
    return _register_with_host(
        host=ModuleHost.PERIODIC,
        name=name,
        fields=fields,
        module_id=module_id,
    )


def module_page(module_id: str):
    def decorator(cls: type):
        from app.framework.core.module_system.registry import get_module

        meta = get_module(module_id)
        if meta is not None:
            meta.page_cls = cls
            if meta.ui_factory is None:
                meta.ui_factory = lambda parent, _host: cls(parent)
        else:
            _PENDING_PAGES[module_id] = cls
        return cls

    return decorator
