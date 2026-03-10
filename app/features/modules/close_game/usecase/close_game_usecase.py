import os
import time
import win32gui
import win32con

from app.framework.infra.events.signal_bus import signalBus
from app.features.modules.enter_game.usecase.enter_game_usecase import is_snowbreak_running

from app.framework.core.module_system import on_demand_module, periodic_module
from app.framework.i18n import _


@periodic_module("Execute Exit", module_id="task_close_game")
class CloseGameModule:
    def __init__(
        self,
        auto,
        logger,
        CheckBox_close_game=False,
        CheckBox_shutdown=False,
        CheckBox_close_proxy=False,
    ):
        self.auto = auto
        self.logger = logger
        self.close_game_enabled = bool(CheckBox_close_game)
        self.shutdown_enabled = bool(CheckBox_shutdown)
        self.close_proxy_enabled = bool(CheckBox_close_proxy)

    def run(self):
        # 1. 退出游戏
        if self.close_game_enabled:
            self.logger.info(_('Exiting game...', msgid='d37a4e4fc0c2'))
            hwnd = is_snowbreak_running()
            if hwnd:
                win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(2)

        # 2. 关机
        if self.shutdown_enabled:
            self.logger.info(_('System will shut down in 60s...', msgid='429e494e4e1c'))
            os.system("shutdown -s -t 60")

        # 3. 退出代理 (发送信号给主窗口处理)
        if self.close_proxy_enabled:
            self.logger.info(_('Exiting Application...', msgid='fb1533f4f2b1'))
            signalBus.requestExitApp.emit()


