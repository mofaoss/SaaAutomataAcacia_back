import ctypes
import time

import win32api
import win32con
import win32gui

from app.common.config import config
from app.common.logger import logger
from app.common.signal_bus import signalBus
from app.common.utils import get_hwnd, launch_game_with_guard
from app.modules.automation.automation import Automation


class BaseTask:
    def __init__(self):
        self.logger = logger
        self.auto = None

    def run(self):
        pass

    def stop(self):
        self.auto.stop()

    @staticmethod
    def _cfg_value(name, default=None):
        item = getattr(config, name, None)
        if item is not None:
            try:
                value = config.get(item)
            except Exception:
                value = getattr(item, 'value', None)
            if value is not None:
                return value
        try:
            value = config.get(name)
            if value is not None:
                return value
        except Exception:
            pass
        return default

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
        # 如果用户设置了自动缩放才执行以下命令
        if config.autoScaling.value:
            # 排除缩放干扰
            ctypes.windll.user32.SetProcessDPIAware()
            # 保存原始窗口矩形位置
            original_rect = win32gui.GetWindowRect(hwnd)
            config.set(config.is_resize, original_rect)
            current_x = original_rect[0]
            current_y = original_rect[1]
            # 若不符合比例则进行窗口调整
            if not is_16_9:
                window_rect = win32gui.GetWindowRect(hwnd)
                non_client_w = (window_rect[2] - window_rect[0]) - client_width
                non_client_h = (window_rect[3] - window_rect[1]) - client_height

                target_client_width = 1920
                target_client_height = 1080
                target_window_width = target_client_width + non_client_w
                target_window_height = target_client_height + non_client_h

                # 设置窗口位置和大小
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    current_x,
                    current_y,
                    target_window_width,
                    target_window_height,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
                )

                self.logger.warn(f"已调整窗口到16:9客户区（目标{target_client_width}x{target_client_height}）")
                is_16_9 = True
            else:
                self.auto.scale_x = 1920 / client_width
                self.auto.scale_y = 1080 / client_height
            return is_16_9
        else:
            if not is_16_9:
                self.logger.warn(f"设置中未开启自动缩放，请手动调整窗口为16:9或在设置中开启自动缩放")
            return is_16_9

    def init_auto(self, name):
        server_interface = int(self._cfg_value('server_interface', 0) or 0)
        configured_title = self._cfg_value('game_title_name', None)
        game_class = 'UnrealWindow'

        title_candidates = []
        if configured_title and str(configured_title).strip():
            title_candidates.append(str(configured_title).strip())

        if server_interface == 2:
            title_candidates.append('Snowbreak: Containment Zone')
        else:
            title_candidates.append('尘白禁区')

        title_candidates.extend(['尘白禁区', 'Snowbreak: Containment Zone'])
        dedup_titles = []
        for title in title_candidates:
            if title and title not in dedup_titles:
                dedup_titles.append(title)

        game_name = dedup_titles[0]
        auto_dict = {
            'game': [game_name, game_class],
            # 'starter': [config.LineEdit_starter_name.value, config.LineEdit_starter_class.value]
        }
        if self.auto is None:
            last_error = None

            for title in dedup_titles:
                try:
                    self.auto = Automation(title, game_class, self.logger)
                    if self.determine_screen_ratio(self.auto.hwnd):
                        signalBus.sendHwnd.emit(self.auto.hwnd)
                        return True
                    self.logger.error('游戏窗口比例不是16:9')
                    return False
                except Exception as e:
                    last_error = e

            if name != 'game':
                self.logger.error(f'初始化auto失败：{last_error}')
                return False

            self.logger.warning(f'未检测到游戏窗口，尝试自动启动游戏：{last_error}')
            launch_result = launch_game_with_guard(logger=self.logger)
            if not launch_result.get('ok', False):
                self.logger.error(f"初始化auto失败：{launch_result.get('error', last_error)}")
                return False

            wait_seconds = 45
            start_ts = time.time()
            while time.time() - start_ts < wait_seconds:
                for title in dedup_titles:
                    hwnd = get_hwnd(title, game_class)
                    if not hwnd:
                        continue
                    try:
                        self.auto = Automation(title, game_class, self.logger)
                        if self.determine_screen_ratio(self.auto.hwnd):
                            signalBus.sendHwnd.emit(self.auto.hwnd)
                            return True
                        self.logger.error('游戏窗口比例不是16:9')
                        return False
                    except Exception as e:
                        last_error = e
                time.sleep(1)

            self.logger.error(f'初始化auto失败：启动游戏后仍未获取到窗口句柄，最后错误：{last_error}')
            return False
        else:
            self.logger.debug(f'延用auto：{self.auto.hwnd}')
            return True
        # else:
        #     if switch:
        #         timeout = Timer(10).start()
        #         while True:
        #             try:
        #                 self.auto = Automation(auto_dict[name][0], auto_dict[name][1], self.logger)
        #                 self.logger.info(f'切换auto成功')
        #                 return True
        #             except Exception as e:
        #                 self.logger.warn(f'未找到{auto_dict[name][0]}，等待1秒')
        #                 time.sleep(1)
        #             if timeout.reached():
        #                 self.logger.error(f'切换auto超时')
        #                 break

    # def chose_auto(self, only_game=False):
    #     """
    #     自动选择auto，有游戏窗口时选游戏，没有游戏窗口时选启动器，都没有的时候循环，寻找频率1次/s
    #     :return:
    #     """
    #     timeout = Timer(20).start()
    #     while True:
    #         # 每次循环重新导入
    #         from app.modules.automation.automation import auto_starter, auto_game
    #         if win32gui.FindWindow(None, config.LineEdit_game_name.value) or only_game:
    #             if not auto_game:
    #                 instantiate_automation(auto_type='game')  # 尝试实例化 auto_game
    #             self.auto = auto_game
    #             flag = 'game'
    #         else:
    #             if not auto_starter:
    #                 instantiate_automation(auto_type='starter')  # 尝试实例化 auto_starter
    #             self.auto = auto_starter
    #             flag = 'starter'
    #         if self.auto:
    #             return flag
    #         if timeout.reached():
    #             logger.error("获取auto超时")
    #             break
