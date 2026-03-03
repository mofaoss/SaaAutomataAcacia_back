import win32api
import win32con
import win32gui

from app.common.config import config
from app.common.logger import logger
from app.common.signal_bus import signalBus
from app.modules.automation.automation import Automation


class BaseTask:
    def __init__(self):
        self.logger = logger
        self.auto = None

    def run(self):
        pass

    def stop(self):
        self.auto.stop()

    def determine_screen_ratio(self, hwnd):
        """判断句柄对应窗口是否为16:9"""
        # 获取窗口客户区尺寸（不含边框和标题栏）
        client_rect = win32gui.GetClientRect(hwnd)
        client_width = client_rect[2] - client_rect[0]
        client_height = client_rect[3] - client_rect[1]

        # 避免除零错误
        if client_height == 0:
            self.logger.warning("窗口高度为0，无法计算比例")
            return False

        # 计算实际宽高比
        actual_ratio = client_width / client_height
        # 16:9的标准比例值
        target_ratio = 16 / 9

        # 允许1%的容差范围
        tolerance = 0.05
        is_16_9 = abs(actual_ratio - target_ratio) <= (target_ratio * tolerance)

        # 记录结果
        status = "符合" if is_16_9 else "不符合"
        self.logger.warn(
            f"窗口客户区尺寸: {client_width}x{client_height} "
            f"({actual_ratio:.3f}:1), {status}16:9标准比例"
        )
        if is_16_9:
            self.auto.scale_x = 1920 / client_width
            self.auto.scale_y = 1080 / client_height
        else:
            self.logger.warn("游戏窗口不符合16:9比例，请手动调整。")

        return is_16_9

    def init_auto(self, name):
        if config.server_interface.value != 2:
            game_name = '尘白禁区'
            game_class = 'UnrealWindow'
        else:
            game_name = 'Snowbreak: Containment Zone'  # 国际服
            game_class = 'UnrealWindow'
        auto_dict = {
            'game': [game_name, game_class],
            # 'starter': [config.LineEdit_starter_name.value, config.LineEdit_starter_class.value]
        }
        if self.auto is None:
            try:
                self.auto = Automation(auto_dict[name][0], auto_dict[name][1], self.logger)
                if self.determine_screen_ratio(self.auto.hwnd):
                    signalBus.sendHwnd.emit(self.auto.hwnd)
                    return True
                else:
                    self.logger.error(f'游戏窗口比例不是16:9')
                    return False
            except Exception as e:
                self.logger.error(f'初始化auto失败：{e}')
                return False
        else:
            self.logger.debug(f'延用auto：{self.auto.hwnd}')
            return True
