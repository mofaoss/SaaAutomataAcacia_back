import time
from app.framework.i18n.runtime import _

from app.framework.infra.automation.timer import Timer
from app.features.utils.home_navigation import back_to_home

from app.framework.core.module_system import Field, on_demand_module, periodic_module


_OPERATION_FIELDS = {
    "SpinBox_action_times": Field(name="行动次数", layout="full"),
    "ComboBox_run": Field(name="疾跑模式", layout="full", options=((0, _("切换疾跑")), (1, _("按住疾跑")))),
}

@on_demand_module(
    "常规训练",
    fields=_OPERATION_FIELDS,
    description="### 提示\n* 重复刷指定次数无需体力的实战训练第一关\n* 用于完成凭证20次常规行动周常任务\n* 请从主页或常规作战选择界面开始",
)
@periodic_module(
    "常规训练",
    fields=_OPERATION_FIELDS,
    description="### 提示\n* 重复刷指定次数无需体力的实战训练第一关\n* 用于完成凭证20次常规行动周常任务\n* 请从主页或常规作战选择界面开始",)
class OperationModule:
    def __init__(self, auto, logger, isLog: bool = False, SpinBox_action_times: int = 1, ComboBox_run: int = 0):
        self.auto = auto
        self.logger = logger
        self.is_log = bool(isLog)
        self.times = int(SpinBox_action_times)
        self.run_mode = int(ComboBox_run)

    def run(self):
        back_to_home(self.auto, self.logger)

        self.enter_train()
        for fight_idx in range(self.times):
            self.fight()
        back_to_home(self.auto, self.logger)

    def fight(self):
        timeout = Timer(40).start()
        is_enter = False
        is_move = False
        is_finish = False

        while True:
            self.auto.take_screenshot()

            if not is_finish:
                if not is_enter:
                    if self.auto.find_element(['技', '援技', '支援技', '黄色', '区域'], 'text',
                                              crop=(40 / 1920, 63 / 1080, 380 / 1920, 400 / 1080),
                                              is_log=self.is_log):
                        is_enter = True
                        continue
                    if self.auto.click_element("退出", 'text', crop=(903 / 1920, 938 / 1080, 1017 / 1920, 1004 / 1080),
                                               is_log=self.is_log):
                        continue
                    if self.auto.click_element('开始', 'text',
                                               crop=(2303 / 2560, 1300 / 1440, 2492 / 2560, 1383 / 1440),
                                               is_log=self.is_log):
                        is_enter = True
                        time.sleep(3)
                        continue
                    if self.auto.click_element('准备', 'text',
                                               crop=(2303 / 2560, 1309 / 1440, 2492 / 2560, 1383 / 1440),
                                               is_log=self.is_log):
                        continue
                    if self.auto.click_element('支援技', 'text', crop=(106 / 1920, 455 / 1080, 305 / 1920, 536 / 1080),
                                               is_log=self.is_log):
                        time.sleep(0.5)
                        continue
                else:
                    if not is_move:
                        if self.auto.find_element(['技', '援技', '支援技', '黄色', '区域'], 'text',
                                                  crop=(40 / 1920, 63 / 1080, 380 / 1920, 400 / 1080),
                                                  is_log=self.is_log):
                            self.auto.key_down("w")
                            is_move = True
                            continue
                    else:
                        if self.run_mode == 0:
                            self.auto.press_key("shift")
                            time.sleep(6)
                        else:
                            for sprint_idx in range(10):
                                self.auto.press_key("shift", press_time=1)
                                time.sleep(0.3)
                        self.auto.key_up("w")
                        is_finish = True
                        continue
            else:
                if self.auto.click_element("退出", 'text', crop=(903 / 1920, 938 / 1080, 1017 / 1920, 1004 / 1080),
                                           is_log=self.is_log):
                    time.sleep(3)
                    break
                if self.auto.find_element('设置', 'text', crop=(1211 / 2560, 778 / 1440, 1340 / 2560, 842 / 1440),
                                          is_log=self.is_log):
                    self.auto.press_key("esc")
                    continue
                time.sleep(2)

            if timeout.reached():
                self.logger.error(_("执行常规训练超时"))
                break

    def enter_train(self):
        timeout = Timer(20).start()
        scroll_no_progress_count = 0

        while True:
            self.auto.take_screenshot()

            if self.auto.click_element('支援技', 'text', crop=(106 / 1920, 455 / 1080, 305 / 1920, 536 / 1080),
                                       is_log=self.is_log):
                break
            if self.auto.find_element('行动', 'text', crop=(480 / 2560, 1340 / 1440, 625 / 2560, 1400 / 1440),
                                      is_log=self.is_log):
                if not self.auto.click_element('实战训练', 'text',
                                               crop=(2168 / 2560, 1060 / 1440, 2400 / 2560, 1132 / 1440),
                                               is_log=self.is_log):
                    self.auto.mouse_scroll(int(619 / self.auto.scale_x), int(866 / self.auto.scale_y), -8500,
                                           time_out=1.2)
                    scroll_no_progress_count += 1
                    if scroll_no_progress_count >= 6:
                        self.logger.error(_("进入常规行动时连续滚轮无进展，已停止以避免后台卡死"))
                        break
                else:
                    scroll_no_progress_count = 0
                    break
            else:
                if self.auto.click_element("战斗", "text", crop=(1510 / 1920, 450 / 1080, 1650 / 1920, 530 / 1080),
                                           is_log=self.is_log, extract=[(39, 39, 56), 128]):
                    time.sleep(1)
                    continue
                if self.auto.click_element('行动', 'text', crop=(2085 / 2560, 716 / 1440, 2542 / 2560, 853 / 1440),
                                           is_log=self.is_log):
                    time.sleep(0.5)
                    continue

            if timeout.reached():
                self.logger.error(_("进入常规行动超时"))
                break
