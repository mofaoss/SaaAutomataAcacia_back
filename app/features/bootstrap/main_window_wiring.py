# coding:utf-8
from __future__ import annotations

from app.framework.core.module_system import discover_modules
from app.framework.core.interfaces.main_window_bridge import MainWindowFeatureBridge
from app.framework.core.task_engine.threads import ModuleTaskThread
from app.framework.i18n import load_i18n_catalogs
from app.framework.infra.config.app_config import config
from app.framework.ui.views.on_demand_tasks_page import OnDemandTasksPage
from app.framework.ui.views.periodic_tasks_page import PeriodicTasksPage

from app.features.modules.collect_supplies.usecase.collect_supplies_usecase import (
    CollectSuppliesModule,
)
from app.features.modules.enter_game.usecase.enter_game_usecase import (
    EnterGameService,
)
from app.features.modules.event_tips.usecase.event_tips_usecase import (
    EventTipsActions,
    EventTipsUseCase,
)
from app.features.utils.home_navigation import back_to_home
from app.features.utils.network import start_cloudflare_update
from app.framework.application.tasks.periodic_task_profile import get_periodic_task_profile


class SnowbreakMainWindowBridge(MainWindowFeatureBridge):
    """Feature-side composition root that wires Snowbreak business modules into framework shell."""

    def configure_module_registry(self) -> None:
        discover_modules("app.features.modules")
        load_i18n_catalogs()

    def create_home_interface(self, window):
        enter_game_service = EnterGameService(window._is_non_chinese_ui, app_config=config)

        return PeriodicTasksPage(
            "Periodic Tasks",
            window,
            game_environment=enter_game_service,
            home_sync=back_to_home,
            task_profile_provider=get_periodic_task_profile,
            create_enter_game_actions=lambda _game_environment: enter_game_service,
            create_collect_supplies_actions=lambda settings_usecase: CollectSuppliesModule(
                app_config=config,
                settings_usecase=settings_usecase,
            ),
            create_event_tips_actions=lambda settings_usecase, _is_non_chinese_ui, _ui_text_fn: EventTipsActions(
                EventTipsUseCase(settings_usecase)

            ),
            startup_update_hook=start_cloudflare_update,
        )

    def create_additional_interface(self, window):
        shared_log_browser = None
        if window.homeInterface is not None and hasattr(window.homeInterface, "textBrowser_log"):
            shared_log_browser = window.homeInterface.textBrowser_log

        return OnDemandTasksPage(
            "On Demand Tasks",
            window,
            shared_log_browser=shared_log_browser,
            module_thread_cls=ModuleTaskThread,
        )

    def initialize_ocr_module(self):
        from app.framework.infra.vision.ocr_runtime import ocr

        ocr.instance_ocr()
        return ocr


def build_main_window_bridge() -> MainWindowFeatureBridge:
    return SnowbreakMainWindowBridge()
