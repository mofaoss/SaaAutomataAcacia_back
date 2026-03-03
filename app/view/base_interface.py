from app.common.logger import logger
from app.common.gui_logger import bind_log_widget


class BaseInterface:
    def __init__(self):
        self.logger = logger
        self.auto = None

    def redirectOutput(self, log_widget):
        bind_log_widget(log_widget)

    def toggle_button(self, running):
        pass

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
