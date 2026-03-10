from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Callable

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
_FRAMEWORK_DEFAULTS = {
    "trigger": {
        "page_class_path": "app.features.modules.trigger.ui.trigger_interface:TriggerInterface",
        "ui_bindings": dict(page_attr="page_trigger", log_widget_attr="textBrowser_log_trigger"),
        "passive": True,
    },
    "fishing": {
        "page_class_path": "app.features.modules.fishing.ui.fishing_interface:FishingInterface",
        "ui_bindings": dict(
            page_attr="page_fishing",
            start_button_attr="PushButton_start_fishing",
            card_widget_attr="SimpleCardWidget_fish",
            log_widget_attr="textBrowser_log_fishing",
        ),
    },
    "action": {
        "page_class_path": "app.features.modules.operation_action.ui.operation_interface:OperationInterface",
        "ui_bindings": dict(
            page_attr="page_action",
            start_button_attr="PushButton_start_action",
            card_widget_attr="SimpleCardWidget_action",
            log_widget_attr="textBrowser_log_action",
        ),
    },
    "water_bomb": {
        "page_class_path": "app.features.modules.water_bomb.ui.water_bomb_interface:WaterBombInterface",
        "ui_bindings": dict(
            page_attr="page_water_bomb",
            start_button_attr="PushButton_start_water_bomb",
            card_widget_attr="SimpleCardWidget_water_bomb",
            log_widget_attr="textBrowser_log_water_bomb",
        ),
    },
    "alien_guardian": {
        "page_class_path": "app.features.modules.alien_guardian.ui.alien_guardian_interface:AlienGuardianInterface",
        "ui_bindings": dict(
            page_attr="page_alien_guardian",
            start_button_attr="PushButton_start_alien_guardian",
            card_widget_attr="SimpleCardWidget_alien_guardian",
            log_widget_attr="textBrowser_log_alien_guardian",
        ),
    },
    "maze": {
        "page_class_path": "app.features.modules.maze.ui.maze_interface:MazeInterface",
        "ui_bindings": dict(
            page_attr="page_maze",
            start_button_attr="PushButton_start_maze",
            card_widget_attr="SimpleCardWidget_maze",
            log_widget_attr="textBrowser_log_maze",
        ),
    },
    "drink": {
        "page_class_path": "app.features.modules.drink.ui.drink_interface:DrinkInterface",
        "ui_bindings": dict(
            page_attr="page_card",
            start_button_attr="PushButton_start_drink",
            card_widget_attr="SimpleCardWidget_card",
            log_widget_attr="textBrowser_log_drink",
        ),
    },
    "capture_pals": {
        "page_class_path": "app.features.modules.capture_pals.ui.capture_pals_interface:CapturePalsInterface",
        "ui_bindings": dict(
            page_attr="page_capture_pals",
            start_button_attr="PushButton_start_capture_pals",
            card_widget_attr="SimpleCardWidget_capture_pals",
            log_widget_attr="textBrowser_log_capture_pals",
        ),
    },
    "massaging": {
        "page_class_path": "app.features.modules.massaging.ui.massaging_interface:MassagingInterface",
        "ui_bindings": dict(
            page_attr="page_massaging",
            start_button_attr="PushButton_start_massaging",
            card_widget_attr="SimpleCardWidget_massaging",
        ),
    },
    "task_login": {
        "page_class_path": "app.features.modules.enter_game.ui.enter_game_periodic_page:EnterGamePage",
        "ui_bindings": dict(page_attr="page_enter"),
        "periodic_mandatory": True,
        "periodic_force_first": True,
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 0,
        "periodic_option_key": "CheckBox_entry_1",
        "periodic_requires_home_sync": False,
    },
    "task_supplies": {
        "page_class_path": "app.features.modules.collect_supplies.ui.collect_supplies_periodic_page:CollectSuppliesPage",
        "ui_bindings": dict(page_attr="page_collect"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 1,
        "periodic_option_key": "CheckBox_stamina_2",
    },
    "task_shop": {
        "page_class_path": "app.features.modules.shopping.ui.shop_periodic_page:ShopPage",
        "ui_bindings": dict(page_attr="page_shop"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 2,
        "periodic_option_key": "CheckBox_shop_3",
    },
    "task_stamina": {
        "page_class_path": "app.features.modules.use_power.ui.use_power_periodic_page:UsePowerPage",
        "ui_bindings": dict(page_attr="page_use_power"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 3,
        "periodic_option_key": "CheckBox_use_power_4",
    },
    "task_shards": {
        "page_class_path": "app.features.modules.person.ui.person_periodic_page:PersonPage",
        "ui_bindings": dict(page_attr="page_person"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 4,
        "periodic_option_key": "CheckBox_person_5",
    },
    "task_chasm": {
        "page_class_path": "app.features.modules.chasm.ui.chasm_periodic_page:ChasmPage",
        "ui_bindings": dict(page_attr="page_chasm"),
        "periodic_default_activation_config": [{"type": "weekly", "day": 1, "time": "10:00", "max_runs": 1}],
        "periodic_ui_page_index": 5,
        "periodic_option_key": "CheckBox_chasm_6",
    },
    "task_reward": {
        "page_class_path": "app.features.modules.get_reward.ui.reward_periodic_page:RewardPage",
        "ui_bindings": dict(page_attr="page_reward"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 6,
        "periodic_option_key": "CheckBox_reward_7",
    },
    "task_operation": {
        "page_class_path": "app.features.modules.operation_action.ui.operation_interface:OperationInterface",
        "ui_bindings": dict(page_attr="page_operation"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 7,
        "periodic_option_key": "CheckBox_operation_8",
    },
    "task_weapon": {
        "page_class_path": "app.features.modules.upgrade.ui.weapon_upgrade_periodic_page:WeaponUpgradePage",
        "ui_bindings": dict(page_attr="page_weapon"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 8,
        "periodic_option_key": "CheckBox_weapon_8",
    },
    "task_shard_exchange": {
        "page_class_path": "app.features.modules.jigsaw.ui.shard_exchange_periodic_page:ShardExchangePage",
        "ui_bindings": dict(page_attr="page_shard_exchange"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 9,
        "periodic_option_key": "CheckBox_shard_exchange_9",
    },
    "task_close_game": {
        "page_class_path": "app.features.modules.close_game.ui.close_game_periodic_page:CloseGamePage",
        "ui_bindings": dict(page_attr="page_close_game"),
        "periodic_default_activation_config": [{"type": "daily", "day": 0, "time": "00:00", "max_runs": 1}],
        "periodic_ui_page_index": 10,
        "periodic_option_key": "CheckBox_close_game_10",
        "periodic_requires_home_sync": False,
    },
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


def _resolve_module_defaults(module_id: str) -> dict:
    return dict(_FRAMEWORK_DEFAULTS.get(module_id, {}))


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

    resolved_id = module_id or infer_module_id(target)
    defaults = _resolve_module_defaults(resolved_id)
    resolved_order = int(_DEFAULT_ORDER.get(resolved_id, 100) if order is None else order)
    resolved_page_class_path = defaults.get("page_class_path")
    resolved_ui_bindings = defaults.get("ui_bindings")
    if isinstance(resolved_ui_bindings, dict):
        from app.framework.application.modules.contracts import ModuleUiBindings

        resolved_ui_bindings = ModuleUiBindings(**resolved_ui_bindings)
    resolved_passive = bool(defaults.get("passive", False) if passive is None else passive)
    resolved_periodic_enabled_by_default = bool(defaults.get("periodic_enabled_by_default", False))
    resolved_periodic_mandatory = bool(defaults.get("periodic_mandatory", False))
    resolved_periodic_force_first = bool(defaults.get("periodic_force_first", False))
    resolved_periodic_requires_home_sync = bool(defaults.get("periodic_requires_home_sync", True))
    resolved_periodic_ui_page_index = defaults.get("periodic_ui_page_index")
    resolved_periodic_option_key = defaults.get("periodic_option_key")
    resolved_activation_config = list(defaults.get("periodic_default_activation_config", []))

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
        periodic_default_hour=4,
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
