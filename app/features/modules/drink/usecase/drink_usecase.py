import time
from app.framework.i18n.runtime import _

from app.features.utils.randoms import random_rectangle_point
from app.framework.infra.automation.timer import Timer

from app.framework.core.module_system import Field, on_demand_module


_DRINK_FIELDS = {
    "SpinBox_drink_times": Field("对局次数(-1无限)"),
    "ComboBox_card_mode": Field("对局模式", options=((0, "模式一"), (1, "模式二"))),
    "CheckBox_is_speed_up": Field("开启二倍速"),
}


@on_demand_module(
    "猜心对局",
    fields=_DRINK_FIELDS,
    description="### 提示\n* 站在猜心对局入口位置后再点开始。\n* 自动执行猜心对局领取猜心对局奖励。\n* 两种模式均无策略。",
)
class DrinkModule:
    def __init__(
        self,
        auto,
        logger,
        isLog: bool = False,
        SpinBox_drink_times: int = 1,
        ComboBox_card_mode: int = 0,
        CheckBox_is_speed_up: bool = False,
    ):
        super().__init__()
        self.mode = int(ComboBox_card_mode)
        self.drink_times = int(SpinBox_drink_times)
        self.auto = auto
        self.logger = logger
        self.enter_success = False
        self.select_list = ['分析员', '析员', '天降鸿运', '多喝热水']
        self.is_speed_up = bool(CheckBox_is_speed_up)
        self.is_log = bool(isLog)

    def run(self):
        self.enter_drink()
        if self.enter_success:
            if self.drink_times == -1:
                while True:
                    if self.mode == 0:
                        self.play_mode1()
                    else:
                        self.play_mode2()
                    self.again()
            else:
                count = 1
                while self.drink_times > 0:
                    self.logger.info(_(f"开始第{count}次猜心对局"))
                    if self.mode == 0:
                        self.play_mode1()
                    else:
                        self.play_mode2()
                    self.drink_times -= 1
                    count += 1
                    if self.drink_times > 0:
                        self.again()
                self.logger.info(_(f"已完成{count - 1}次猜心对局"))
        # self.again()

    def enter_drink(self):
        """
        进入并开始猜心对局
        :return:
        """
        timeout = Timer(30).start()
        enter_select = False
        while True:
            self.auto.take_screenshot()

            if self.auto.find_element('玩法', 'text', crop=(1000 / 2560, 682 / 1440, 1555 / 2560, 750 / 1440),
                                      is_log=self.is_log):
                self.enter_success = False
                self.logger.warning(_("玩法未解锁"))
                break

            if self.auto.click_element(self.select_list, 'text',
                                       crop=(737 / 2560, 692 / 1440, 1117 / 2560, 986 / 1440), is_log=self.is_log):
                self.enter_success = True
                break

            if self.auto.find_element(['指定', '牌'], 'text',
                                      crop=(265 / 2560, 1184 / 1440, 375 / 2560, 1224 / 1440),
                                      is_log=self.is_log):
                self.enter_success = True
                break
            if self.auto.click_element('再来', 'text', crop=(1590 / 1920, 950 / 1080, 1872 / 1920, 1032 / 1080),
                                       is_log=self.is_log):
                self.enter_success = True
                break
            # if self.auto.find_element('教学', 'text', crop=(2410 / 2560, 282 / 1440, 2477 / 2560, 319 / 1440),
            #                           is_log=self.is_log, extract=[(196, 172, 128), 128]):
            #     enter_select = True

            if not enter_select:
                if self.auto.find_element("奖励", 'text', crop=(2014 / 2560, 1327 / 1440, 2099 / 2560, 1379 / 1440),
                                          is_log=self.is_log):
                    mode = self.mode
                    if mode == 1:
                        pos = random_rectangle_point(((int(882 / self.auto.scale_x), int(380 / self.auto.scale_y)),
                                                      (int(1000 / self.auto.scale_x), int(415 / self.auto.scale_y))),
                                                     n=3)
                    elif mode == 0:
                        pos = random_rectangle_point(((int(1033 / self.auto.scale_x), int(566 / self.auto.scale_y)),
                                                      (int(1175 / self.auto.scale_x), int(612 / self.auto.scale_y))),
                                                     n=3)
                    self.auto.click_element_with_pos(pos)
                    continue

                if self.auto.find_element(['猜心对局', 'F'], 'text',
                                          crop=(1025 / 1920, 663 / 1080, 1267 / 1920, 717 / 1080), is_log=self.is_log):
                    self.auto.press_key('f')
                    continue
                if self.auto.find_element(['少女', '同', '玩'], 'text',
                                          crop=(0 / 1920, 0 / 1080, 371 / 1920, 111 / 1080),
                                          is_log=self.is_log):
                    enter_select = True
                    continue
            else:
                if self.auto.find_element(['指定', '牌'], 'text',
                                          crop=(265 / 2560, 1184 / 1440, 375 / 2560, 1224 / 1440),
                                          is_log=self.is_log):
                    if not self.is_speed_up:
                        self.auto.click_element_with_pos((int(1754 / self.auto.scale_x), int(61 / self.auto.scale_y)))
                        self.auto.click_element_with_pos((int(1754 / self.auto.scale_x), int(61 / self.auto.scale_y)))
                        self.is_speed_up = True
                    self.enter_success = True
                    break
                # 选人并开始对局
                first_pos = (int(135 / self.auto.scale_x), int(220 / self.auto.scale_y))
                self.auto.click_element_with_pos(first_pos)
                self.auto.click_element_with_pos((first_pos[0], first_pos[1] + 150 / self.auto.scale_y))
                self.auto.click_element_with_pos((first_pos[0], first_pos[1] + 300 / self.auto.scale_y))
                self.auto.click_element_with_pos((int(1664 / self.auto.scale_x), int(979 / self.auto.scale_y)))
                continue

            if timeout.reached():
                self.logger.error(_("进入猜心对局超时"))
                break

    def play_mode1(self):
        timeout = Timer(600).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.find_element('再来', 'text', crop=(1590 / 1920, 950 / 1080, 1872 / 1920, 1032 / 1080),
                                      is_log=self.is_log):
                self.is_speed_up = False
                break

            if self.auto.find_element(['指定', '牌'], 'text',
                                      crop=(265 / 2560, 1184 / 1440, 375 / 2560, 1224 / 1440),
                                      is_log=self.is_log):
                self.auto.press_key('q')
                self.auto.press_key('w')
                self.auto.press_key('e')
                if self.auto.click_element('质疑', 'text', crop=(2438 / 2560, 1143 / 1440, 2511 / 2560, 1186 / 1440),
                                           is_log=self.is_log):
                    continue
                else:
                    if self.auto.find_element('出牌', 'text', crop=(1712 / 1920, 974 / 1080, 1807 / 1920, 1021 / 1080),
                                              is_log=self.is_log):
                        self.auto.click_element_with_pos((int(958 / self.auto.scale_x), int(747 / self.auto.scale_y)))
                        self.auto.click_element('出牌', 'text',
                                                crop=(1712 / 1920, 974 / 1080, 1807 / 1920, 1021 / 1080),
                                                is_log=self.is_log)
                    continue

            if timeout.reached():
                self.logger.error(_("猜心对局对局超时"))
                break

    def play_mode2(self):
        timeout = Timer(600).start()
        select_first = False

        while True:
            self.auto.take_screenshot()

            if self.auto.find_element('再来', 'text', crop=(1590 / 1920, 950 / 1080, 1872 / 1920, 1032 / 1080),
                                      is_log=self.is_log):
                break

            if self.auto.click_element(self.select_list, 'text',
                                       crop=(737 / 2560, 692 / 1440, 1117 / 2560, 986 / 1440), is_log=self.is_log):
                continue
            if self.auto.click_element('开启', 'text',
                                       crop=(1465 / 2560, 1021 / 1440, 1637 / 2560, 1076 / 1440), is_log=self.is_log):
                continue
            if self.auto.click_element('取消', 'text',
                                       crop=(1375 / 1920, 978 / 1080, 1458 / 1920, 1032 / 1080), is_log=self.is_log):
                continue
            if self.auto.find_element('触发', 'text',
                                      crop=(1124 / 2560, 544 / 1440, 1437 / 2560, 608 / 1440), is_log=self.is_log):
                self.auto.press_key('esc')
                time.sleep(0.3)
                continue

            # if self.auto.find_element(['Q', 'W', 'E'], 'text',
            #                           crop=(1203 / 2560, 1304 / 1440, 1729 / 2560, 1400 / 1440), is_log=self.is_log):
            #     self.auto.press_key('q')
            #     self.auto.press_key('w')
            #     self.auto.press_key('e')
            #     continue
            if self.auto.find_element(['指定', '牌'], 'text',
                                      crop=(265 / 2560, 1184 / 1440, 375 / 2560, 1224 / 1440),
                                      is_log=self.is_log):
                if not self.is_speed_up:
                    self.auto.click_element_with_pos((int(1754 / self.auto.scale_x), int(61 / self.auto.scale_y)))
                    self.auto.click_element_with_pos((int(1754 / self.auto.scale_x), int(61 / self.auto.scale_y)))
                    self.is_speed_up = True

                self.auto.press_key('q')
                time.sleep(0.2)
                self.auto.press_key('w')
                time.sleep(0.2)
                self.auto.press_key('e')
                if self.auto.click_element('质疑', 'text', crop=(2438 / 2560, 1143 / 1440, 2511 / 2560, 1186 / 1440),
                                           is_log=self.is_log):
                    select_first = False
                    continue
                else:
                    if self.auto.find_element('出牌', 'text', crop=(1712 / 1920, 974 / 1080, 1807 / 1920, 1021 / 1080),
                                              is_log=self.is_log):
                        if self.auto.find_element('至少', 'text',
                                                  crop=(1074 / 2560, 688 / 1440, 1200 / 2560, 748 / 1440),
                                                  is_log=self.is_log):
                            self.auto.click_element_with_pos(
                                (int(958 / self.auto.scale_x), int(747 / self.auto.scale_y)))
                            select_first = True
                        if self.auto.find_element('2张牌', 'text',
                                                  crop=(1540 / 2560, 674 / 1440, 1654 / 2560, 748 / 1440),
                                                  is_log=self.is_log):
                            self.auto.click_element_with_pos(
                                (int(1103 / self.auto.scale_x), int(762 / self.auto.scale_y)))
                        if not select_first:
                            print(self.auto.scale_x)
                            print(self.auto.scale_y)
                            self.auto.click_element_with_pos(
                                (int(958 / self.auto.scale_x), int(747 / self.auto.scale_y)))
                            select_first = True
                        self.auto.click_element('出牌', 'text',
                                                crop=(1712 / 1920, 974 / 1080, 1807 / 1920, 1021 / 1080),
                                                is_log=self.is_log)
                    continue

            if timeout.reached():
                self.logger.error(_("猜心对局对局超时"))
                break

    def again(self):
        timeout = Timer(10).start()
        while True:
            self.auto.take_screenshot()

            if self.auto.click_element(self.select_list, 'text',
                                       crop=(737 / 2560, 692 / 1440, 1117 / 2560, 986 / 1440), is_log=self.is_log):
                break

            if self.auto.find_element(['指定', '牌'], 'text',
                                      crop=(265 / 2560, 1184 / 1440, 375 / 2560, 1224 / 1440),
                                      is_log=self.is_log):
                break

            if self.auto.click_element('再来', 'text', crop=(1590 / 1920, 950 / 1080, 1872 / 1920, 1032 / 1080),
                                       is_log=self.is_log):
                continue

            if timeout.reached():
                self.logger.error(_("重进对局超时"))
                break
