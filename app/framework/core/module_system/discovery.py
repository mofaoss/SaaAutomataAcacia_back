from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path


def _is_usecase_module_name(name: str) -> bool:
    leaf = name.rsplit(".", 1)[-1]
    return ".usecase." in name and leaf.endswith("_usecase")


def _discover_by_pkgutil(pkg) -> list[str]:
    imported: list[str] = []
    for _, name, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        if not _is_usecase_module_name(name):
            continue
        importlib.import_module(name)
        imported.append(name)
    return imported


def _discover_by_filesystem(pkg) -> list[str]:
    imported: list[str] = []
    seen: set[str] = set()
    for base in getattr(pkg, "__path__", []):
        base_path = Path(base)
        if not base_path.exists():
            continue
        for py in base_path.rglob("*_usecase.py"):
            if "__pycache__" in py.parts:
                continue
            if "usecase" not in py.parts:
                continue
            rel = py.relative_to(base_path).with_suffix("")
            module_name = pkg.__name__ + "." + ".".join(rel.parts)
            if module_name in seen or not _is_usecase_module_name(module_name):
                continue
            importlib.import_module(module_name)
            seen.add(module_name)
            imported.append(module_name)
    return imported


# Fallback for packaged builds where pkgutil/filesystem enumeration can be incomplete.
_FALLBACK_USECASE_MODULES: tuple[str, ...] = (
    "app.features.modules.alien_guardian.usecase.alien_guardian_usecase",
    "app.features.modules.capture_pals.usecase.capture_pals_usecase",
    "app.features.modules.chasm.usecase.chasm_usecase",
    "app.features.modules.close_game.usecase.close_game_usecase",
    "app.features.modules.collect_supplies.usecase.collect_supplies_usecase",
    "app.features.modules.drink.usecase.drink_usecase",
    "app.features.modules.enter_game.usecase.enter_game_usecase",
    "app.features.modules.event_tips.usecase.event_tips_usecase",
    "app.features.modules.fishing.usecase.fishing_usecase",
    "app.features.modules.get_reward.usecase.get_reward_usecase",
    "app.features.modules.jigsaw.usecase.jigsaw_usecase",
    "app.features.modules.jigsaw.usecase.shard_exchange_usecase",
    "app.features.modules.massaging.usecase.massaging_usecase",
    "app.features.modules.maze.usecase.maze_usecase",
    "app.features.modules.operation_action.usecase.operation_usecase",
    "app.features.modules.person.usecase.person_usecase",
    "app.features.modules.redeem_codes.usecase.redeem_codes_usecase",
    "app.features.modules.shopping.usecase.shopping_usecase",
    "app.features.modules.trigger.usecase.auto_f_usecase",
    "app.features.modules.trigger.usecase.nita_auto_e_usecase",
    "app.features.modules.upgrade.usecase.weapon_upgrade_usecase",
    "app.features.modules.use_power.usecase.use_power_usecase",
    "app.features.modules.water_bomb.usecase.water_bomb_usecase",
)


def _discover_by_fallback_list() -> list[str]:
    imported: list[str] = []
    for module_name in _FALLBACK_USECASE_MODULES:
        try:
            importlib.import_module(module_name)
            imported.append(module_name)
        except Exception:
            continue
    return imported


def discover_modules(package: str):
    pkg = importlib.import_module(package)
    if not hasattr(pkg, "__path__"):
        return

    # In packaged environments pkgutil/filesystem enumeration can be partial.
    # Execute all strategies; duplicate imports are naturally deduplicated by Python.
    _discover_by_pkgutil(pkg)
    _discover_by_filesystem(pkg)
    _discover_by_fallback_list()
