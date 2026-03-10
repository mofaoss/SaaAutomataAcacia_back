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
                _('Window height is 0, cannot calculate ratio', msgid='543f0c4715ee')
            )
            return False

        actual_ratio = client_width / client_height
        target_ratio = 16 / 9
        tolerance = 0.05
        is_16_9 = abs(actual_ratio - target_ratio) <= (target_ratio * tolerance)

        status = (
            _('Meets', msgid='95af714f631f')
            if is_16_9
            else _('Does not meet', msgid='25bb2217a017')
        )
        self.logger.warning(
            _(f'Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status} 16:9 standard ratio', msgid='fcaa237cbac3')
        )
        if is_16_9:
            self.auto.scale_x = 1920 / client_width
            self.auto.scale_y = 1080 / client_height
        else:
            self.logger.warning(
                _('Game window does not meet 16:9 ratio, please adjust manually.', msgid='27eb3232a97e')
            )
        return is_16_9

    def init_auto(
        self,
        name: Optional[str] = None,
        *,
        automation=None,
        automation_factory: Optional[Callable[[], object]] = None,
    ):
        _ = name
        if self.auto is not None:
            self.logger.debug(_(f'Using existing auto: {self.auto.hwnd}', msgid='d079a661e93d'))
            return True

        try:
            if automation is not None:
                self.auto = automation
            elif callable(automation_factory):
                self.auto = automation_factory()
            else:
                raise ValueError("automation_factory is required when automation is not provided")

            if self.determine_screen_ratio(self.auto.hwnd):
                signalBus.sendHwnd.emit(self.auto.hwnd)
                return True

            self.logger.error(_('Game window ratio is not 16:9', msgid='89eefa0e1faa'))
            return False
        except Exception as e:
            self.logger.error(_(f'Failed to initialize auto: {e}', msgid='20cc4907bd27'))
            return False
