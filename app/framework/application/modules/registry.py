from __future__ import annotations

from app.framework.application.modules.contracts import (
    HostContext,
    ModuleSpec,
    ModuleUiBindings,
)

from app.features.modules.alien_guardian.ui.alien_guardian_interface import (
    AlienGuardianInterface,
)
from app.features.modules.alien_guardian.usecase.alien_guardian_usecase import (
    AlienGuardianModule,
)
from app.features.modules.capture_pals.ui.capture_pals_interface import (
    CapturePalsInterface,
)
from app.features.modules.capture_pals.usecase.capture_pals_usecase import (
    CapturePalsModule,
)
from app.features.modules.drink.ui.drink_interface import DrinkInterface
from app.features.modules.drink.usecase.drink_usecase import DrinkModule
from app.features.modules.fishing.ui.fishing_interface import FishingInterface
from app.features.modules.fishing.usecase.fishing_usecase import FishingModule
from app.features.modules.maze.ui.maze_interface import MazeInterface
from app.features.modules.maze.usecase.maze_usecase import MazeModule
from app.features.modules.operation_action.ui.operation_interface import (
    OperationInterface,
)
from app.features.modules.operation_action.usecase.operation_usecase import (
    OperationModule,
)
from app.features.modules.trigger.ui.trigger_interface import TriggerInterface
from app.features.modules.water_bomb.ui.water_bomb_interface import WaterBombInterface
from app.features.modules.water_bomb.usecase.water_bomb_usecase import (
    WaterBombModule,
)


ON_DEMAND_MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        id="trigger",
        zh_name="自动辅助",
        en_name="Trigger",
        order=10,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: TriggerInterface(parent),
        ui_bindings=ModuleUiBindings(
            page_attr="page_trigger",
            log_widget_attr="textBrowser_log_trigger",
        ),
        passive=True,
    ),
    ModuleSpec(
        id="fishing",
        zh_name="钓鱼",
        en_name="Fishing",
        order=20,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: FishingInterface(parent),
        module_class=FishingModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_fishing",
            start_button_attr="PushButton_start_fishing",
            card_widget_attr="SimpleCardWidget_fish",
            log_widget_attr="textBrowser_log_fishing",
        ),
    ),
    ModuleSpec(
        id="action",
        zh_name="常规训练",
        en_name="Operation",
        order=30,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: OperationInterface(parent),
        module_class=OperationModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_action",
            start_button_attr="PushButton_start_action",
            card_widget_attr="SimpleCardWidget_action",
            log_widget_attr="textBrowser_log_action",
        ),
    ),
    ModuleSpec(
        id="water_bomb",
        zh_name="心动水弹",
        en_name="Water Bomb",
        order=40,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: WaterBombInterface(parent),
        module_class=WaterBombModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_water_bomb",
            start_button_attr="PushButton_start_water_bomb",
            card_widget_attr="SimpleCardWidget_water_bomb",
            log_widget_attr="textBrowser_log_water_bomb",
        ),
    ),
    ModuleSpec(
        id="alien_guardian",
        zh_name="异星守护",
        en_name="Alien Guardian",
        order=50,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: AlienGuardianInterface(parent),
        module_class=AlienGuardianModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_alien_guardian",
            start_button_attr="PushButton_start_alien_guardian",
            card_widget_attr="SimpleCardWidget_alien_guardian",
            log_widget_attr="textBrowser_log_alien_guardian",
        ),
    ),
    ModuleSpec(
        id="maze",
        zh_name="验证战场",
        en_name="Maze",
        order=60,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: MazeInterface(parent),
        module_class=MazeModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_maze",
            start_button_attr="PushButton_start_maze",
            card_widget_attr="SimpleCardWidget_maze",
            log_widget_attr="textBrowser_log_maze",
        ),
    ),
    ModuleSpec(
        id="drink",
        zh_name="猜心对局",
        en_name="Card Match",
        order=70,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: DrinkInterface(parent),
        module_class=DrinkModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_card",
            start_button_attr="PushButton_start_drink",
            card_widget_attr="SimpleCardWidget_card",
            log_widget_attr="textBrowser_log_drink",
        ),
    ),
    ModuleSpec(
        id="capture_pals",
        zh_name="抓帕鲁",
        en_name="Capture Pals",
        order=80,
        hosts=(HostContext.ON_DEMAND,),
        ui_factory=lambda parent, _host: CapturePalsInterface(parent),
        module_class=CapturePalsModule,
        ui_bindings=ModuleUiBindings(
            page_attr="page_capture_pals",
            start_button_attr="PushButton_start_capture_pals",
            card_widget_attr="SimpleCardWidget_capture_pals",
            log_widget_attr="textBrowser_log_capture_pals",
        ),
    ),
)


def get_on_demand_module_specs(*, include_passive: bool = True) -> list[ModuleSpec]:
    specs = sorted(ON_DEMAND_MODULE_SPECS, key=lambda item: item.order)
    if include_passive:
        return specs
    return [spec for spec in specs if not spec.passive]

