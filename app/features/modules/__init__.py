"""Feature modules package bootstrap.

This package eagerly imports all module usecase entry modules so decorator
registration does not depend on runtime filesystem/package enumeration.
"""

from __future__ import annotations

import importlib

_EAGER_USECASE_IMPORTS: tuple[str, ...] = (
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

for _module_name in _EAGER_USECASE_IMPORTS:
    try:
        importlib.import_module(_module_name)
    except Exception:
        # Keep bootstrap tolerant: discovery layer can still try fallback strategies.
        pass
