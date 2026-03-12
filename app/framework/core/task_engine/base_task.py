import logging
from typing import Callable, Optional

import win32gui

from app.framework.infra.events.signal_bus import signalBus
from app.framework.i18n import _


logger = logging.getLogger(__name__)


class BaseTask:
    def __init__(self):
        self.logger = logger
        self.auto = None

    def run(self):
        pass

    def stop(self):
        if self.auto is not None:
            self.auto.stop()

    def determine_screen_ratio(self, hwnd):
        client_rect = win32gui.GetClientRect(hwnd)
        client_width = client_rect[2] - client_rect[0]
        client_height = client_rect[3] - client_rect[1]

        if client_height == 0:
            self.logger.warning(
                _('Window height is 0, cannot calculate ratio', msgid='window_height_is_0_cannot_calculate_ratio')
            )
            return False

        actual_ratio = client_width / client_height
        target_ratio = 16 / 9
        tolerance = 0.05
        is_16_9 = abs(actual_ratio - target_ratio) <= (target_ratio * tolerance)

        status = (
            _('Meets', msgid='meets')
            if is_16_9
            else _('Does not meet', msgid='does_not_meet')
        )
        self.logger.warning(
            _(f'Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status} 16:9 standard ratio', msgid='client_area_size_client_width_x_client_height_ac')
        )
        if is_16_9:
            self.auto.scale_x = 1920 / client_width
            self.auto.scale_y = 1080 / client_height
        else:
            self.logger.warning(
                _('Game window does not meet 16:9 ratio, please adjust manually.', msgid='game_window_does_not_meet_16_9_ratio_please_adju')
            )
        return is_16_9

    def init_auto(
        self,
        name: Optional[str] = None,
        *,
        automation=None,
        automation_factory: Optional[Callable[[], object]] = None,
    ):
        if self.auto is not None:
            self.logger.debug(_(f'Using existing auto: {self.auto.hwnd}', msgid='using_existing_auto_value'))
            return True

        try:
            if automation is not None:
                self.auto = automation
            elif callable(automation_factory):
                self.auto = automation_factory()
            elif name is not None:
                self.auto = self._build_default_automation()
            else:
                raise ValueError("automation_factory is required when automation is not provided")

            if self.determine_screen_ratio(self.auto.hwnd):
                signalBus.sendHwnd.emit(self.auto.hwnd)
                return True

            self.logger.error(_('Game window ratio is not 16:9', msgid='game_window_ratio_is_not_16_9'))
            return False
        except Exception as e:
            self.logger.error(_(f'Failed to initialize auto: {e}', msgid='failed_to_initialize_auto_e'))
            return False

    def _build_default_automation(self):
        from app.framework.infra.automation.automation import Automation
        from app.framework.infra.config.app_config import config

        game_name = "尘白禁区" if config.server_interface.value != 2 else "Snowbreak: Containment Zone"
        return Automation(game_name, "UnrealWindow", self.logger)
