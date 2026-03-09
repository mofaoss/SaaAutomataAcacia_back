import os
import time
import win32gui
import win32con

from app.framework.infra.config.app_config import config
from app.framework.infra.events.signal_bus import signalBus
from app.framework.ui.shared.text import ui_text
from app.features.modules.enter_game.usecase.enter_game_usecase import is_snowbreak_running

class CloseGameModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger

    def run(self):
        # 1. 退出游戏
        if config.CheckBox_close_game.value:
            self.logger.info(ui_text("正在退出游戏...", "Exiting game..."))
            hwnd = is_snowbreak_running()
            if hwnd:
                win32gui.SendMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                time.sleep(2)

        # 2. 关机
        if config.CheckBox_shutdown.value:
            self.logger.info(ui_text("系统将于60秒后关机...", "System will shut down in 60s..."))
            os.system('shutdown -s -t 60')

        # 3. 退出代理 (发送信号给主窗口处理)
        if config.CheckBox_close_proxy.value:
            self.logger.info(ui_text("正在退出程序...", "Exiting Application..."))
            signalBus.requestExitApp.emit()


