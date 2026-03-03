import re
import time
from pathlib import Path

import win32gui

from app.common.config import config
from app.common.data_models import parse_config_update_data
from app.common.utils import random_rectangle_point
from app.modules.automation.timer import Timer


class UsePowerModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger
        self.day_num = 0
        self.is_log = False

    def run(self):
        self.is_log = config.isLog.value

        self.auto.back_to_home()
        if config.CheckBox_is_use_power.value:
            self.day_num = config.ComboBox_power_day.value + 1
            self.check_power()
        if config.ComboBox_power_usage.value == 0:
            self.by_maneuver()
        elif config.ComboBox_power_usage.value == 1:
            self.by_routine_logistics()
            self.by_maneuver(only_collect=True)

    def get_click_pos(self, name: str, n=3):
        """
        获取固定点击位置
        :param n: 密集度
        :param name: "stuff" or "chasm"
        :return: (x,y)
        """
        config_data = parse_config_update_data(config.update_data.value)
        if not config_data:
            self.logger.error("配置数据为空或格式不正确")
            return None, None

        update_data = config_data.data.updateData
        # print(update_data.dict())

        online_width = float(update_data.onlineWidth)  # 2560
        online_height = online_width * 9 / 16  # 1440
        client_rect = win32gui.GetClientRect(self.auto.hwnd)
        client_width = client_rect[2] - client_rect[0]  # 1920
        client_height = client_rect[3] - client_rect[1]  # 1080
        scale_x = client_width / online_width
        scale_y = client_height / online_height
        if name == "stuff":
            coords = update_data.stuff
        else:
            coords = update_data.chasm

        x1 = int(float(coords.x1) * scale_x)
        y1 = int(float(coords.y1) * scale_y)
        x2 = int(float(coords.x2) * scale_x)
        y2 = int(float(coords.y2) * scale_y)
        return random_rectangle_point(((x1, y1), (x2, y2)), n=n)

    def is_in_home(self):
        """是否位于主页面"""
        return self.auto.find_element('基地', 'text', crop=(
                1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080), is_log=self.is_log) and self.auto.find_element(
                '任务', 'text', crop=(1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log)

    @staticmethod
    def _extract_day_value(text: str):
        """从 OCR 文本中提取“X天”里的天数，未提取到则返回 None。"""
        if not text:
            return None
        match = re.search(r"(\d+)\s*天", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _collect_day_option_positions(self):
        """收集当前 OCR 结果中各“X天”选项对应的可点击区域。"""
        day_options = {}
        if not self.auto.ocr_result:
            return day_options
        for result in self.auto.ocr_result:
            text = result[0] if result else ""
            day_value = self._extract_day_value(text)
            if day_value is None:
                continue
            pos = self.auto.calculate_text_position(result)
            if day_value not in day_options:
                day_options[day_value] = []
            day_options[day_value].append(pos)
        return day_options

    def check_power(self):
        relative_path = Path("app/resource/images/use_power/time.png")
        project_root = Path(__file__).resolve().parents[3]
        power_icon_template = next(
            (str(path) for path in (relative_path, project_root / relative_path) if path.exists()),
            None
        )

        timeout = Timer(50).start()
        current_check = 1  # 当前检查的体力剩余天数
        confirm_flag = False  # 是否选择好了体力
        enter_power_select = False  # 是否进入选择体力界面，用户禁止对体力图标的判断
        has_colon = False  # 是否存在冒号
        while True:
            self.auto.take_screenshot()

            if current_check > self.day_num:
                break

            if self.auto.find_element("恢复感知", "text", crop=(1044 / 1920, 295 / 1080, 1487 / 1920, 402 / 1080),
                                      is_log=self.is_log):
                enter_power_select = True
            else:
                enter_power_select = False

            if confirm_flag:
                if self.auto.find_element('获得道具', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                          is_log=self.is_log):
                    self.auto.press_key('esc')
                    confirm_flag = False
                    enter_power_select = False

            if enter_power_select:
                # 选择好了体力
                if confirm_flag:
                    if self.auto.click_element("确定", "text", crop=(1259 / 1920, 808 / 1080, 1422 / 1920, 864 / 1080)):
                        time.sleep(0.2)
                        continue
                # 执行ocr更新self.auto.ocr_result
                crop_image = self.auto.get_crop_form_first_screenshot(
                    crop=(387 / 2560, 409 / 1440, 1023 / 2560, 495 / 1440))
                self.auto.perform_ocr(image=crop_image, is_log=self.is_log)
                # 更新colon
                has_colon = any(':' in item[0] for item in self.auto.ocr_result)
                # print(f"{has_colon=}")
                day_option_positions = self._collect_day_option_positions()
                has_day = bool(day_option_positions)
                # 没有能使用的体力
                if not has_day and not has_colon:
                    break
                # 存在低于一天的体力药,并且进入了选择体力界面
                if has_colon:
                    if self.auto.click_element([':', '：'], 'text',
                                               crop=(387 / 2560, 409 / 1440, 1023 / 2560, 495 / 1440)):
                        confirm_flag = True
                        continue
                    confirm_flag = False
                # 存在大于一天但是小于day_num的体力药,并且进入了选择体力界面
                if current_check <= self.day_num:
                    target_positions = day_option_positions.get(current_check, [])
                    if target_positions and self.auto.click_element_with_pos(target_positions[0]):
                        confirm_flag = True
                        continue
                    # 低于day_num，没colon，没点击选择x_day.png->加一进行下一天的判断
                    else:
                        current_check += 1
                        # print("current_check", current_check)
                        confirm_flag = False
                        continue
            if not confirm_flag and not enter_power_select:
                if power_icon_template and self.auto.click_element(power_icon_template, 'image',
                                           crop=(833 / 1920, 0, 917 / 1920, 68 / 1080),
                                           threshold=0.7,
                                           is_log=self.is_log):
                    time.sleep(0.5)
                    continue
                # 兜底固定坐标仅在主页面可见时使用，避免误触顶部其它按钮
                if self.auto.find_element('基地', 'text', crop=(
                        1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080), is_log=self.is_log) and self.auto.find_element(
                        '任务', 'text', crop=(1452 / 1920, 327 / 1080, 1529 / 1920, 376 / 1080), is_log=self.is_log):
                    self.auto.click_element_with_pos(pos=(int(910 / self.auto.scale_x), int(35 / self.auto.scale_y)))
                    time.sleep(0.5)
                    continue
            if timeout.reached():
                self.logger.error("检查体力超时")
                break
        self.auto.back_to_home()

    def wait_activity_task_tab(self, timeout_seconds=10):
        """等待活动页面任务入口稳定显示"""
        timeout_animation = Timer(timeout_seconds).start()
        task_name = config.task_name.value
        while True:
            self.auto.take_screenshot()
            if task_name and self.auto.find_element(task_name, 'text', crop=(0, 1280 / 1440, 1, 1),
                                                    is_log=self.is_log):
                return True
            if self.auto.find_element('任务', 'text', crop=(0, 1280 / 1440, 1, 1), is_log=self.is_log):
                return True
            if timeout_animation.reached():
                return False
            time.sleep(0.5)

    def wait_activity_reward_page(self, timeout_seconds=8):
        """等待活动任务奖励页面加载完成"""
        timeout_reward = Timer(timeout_seconds).start()
        while True:
            self.auto.take_screenshot()
            if self.auto.find_element(['剩余', '刷新', '天'], 'text',
                                      crop=(826 / 2560, 239 / 1440, 1393 / 2560, 1188 / 1440),
                                      is_log=self.is_log) or self.auto.find_element('领取', 'text', crop=(
                    0, 937 / 1080, 266 / 1920, 1), is_log=self.is_log):
                return True
            if timeout_reward.reached():
                return False
            time.sleep(0.3)

    def open_activity_reward_page(self, max_attempts=3):
        """打开活动任务奖励页面并确认进入，失败时自动重试"""
        task_name = config.task_name.value
        for attempt in range(1, max_attempts + 1):
            self.auto.take_screenshot()
            in_home = self.is_in_home()
            if not in_home and self.wait_activity_reward_page(timeout_seconds=1):
                has_reward = self.auto.find_element('领取', 'text', crop=(0, 937 / 1080, 266 / 1920, 1),
                                                    is_log=self.is_log)
                if has_reward:
                    self.logger.info("已进入活动奖励页面，检测到可领取奖励")
                else:
                    self.logger.info("已进入活动奖励页面，当前无可领取奖励")
                return True

            # 在活动页内，优先点任务标签/活动名
            clicked_task = self.auto.click_element('任务', 'text', crop=(0, 1280 / 1440, 1, 1),
                                                   is_log=self.is_log)
            if not clicked_task and task_name:
                clicked_task = self.auto.click_element(task_name, 'text', crop=(0, 1280 / 1440, 1, 1),
                                                       is_log=self.is_log)

            # 若仍在主页面，再执行从主页跳活动页
            if not clicked_task and in_home:
                if self.auto.click_element("任务", "text", crop=(1445 / 1920, 321 / 1080, 1552 / 1920, 398 / 1080),
                                           offset=(-34 / self.auto.scale_x, 140 / self.auto.scale_y),
                                           is_log=self.is_log):
                    if not self.wait_activity_task_tab(timeout_seconds=8):
                        self.logger.warn(f"第{attempt}次进入活动页面失败，准备重试")
                        continue
                    clicked_task = self.auto.click_element('任务', 'text', crop=(0, 1280 / 1440, 1, 1),
                                                           is_log=self.is_log)
                    if not clicked_task and task_name:
                        clicked_task = self.auto.click_element(task_name, 'text', crop=(0, 1280 / 1440, 1, 1),
                                                               is_log=self.is_log)

            if not clicked_task:
                self.logger.warn(f"第{attempt}次未找到活动任务入口，准备重试")
                continue

            if self.wait_activity_reward_page(timeout_seconds=8):
                has_reward = self.auto.find_element('领取', 'text', crop=(0, 937 / 1080, 266 / 1920, 1),
                                                    is_log=self.is_log)
                if has_reward:
                    self.logger.info("已打开活动奖励页面，检测到可领取奖励")
                else:
                    self.logger.info("已打开活动奖励页面，当前无可领取奖励")
                return True

            self.logger.warn(f"第{attempt}次活动奖励页面未打开，准备重试")

        return False

    def by_maneuver(self, only_collect=False):
        """通过活动使用体力；only_collect=True 时仅进入活动页领取物资"""
        timeout = Timer(50).start()
        finish_flag = only_collect  # 是否完成体力刷取
        enter_task = False  # 是否进入任务界面
        enter_maneuver_flag = False  # 是否进入活动页面
        reward_status_logged = False

        config_data = parse_config_update_data(config.update_data.value)
        if not config_data:
            self.logger.error("配置数据为空或格式不正确")
            return

        update_data = config_data.data.updateData
        online_width = float(update_data.onlineWidth)
        online_height = online_width * 9 / 16

        stuff_pos = (float(update_data.stuff.x1) / online_width, float(update_data.stuff.y1) / online_height,
                     float(update_data.stuff.x2) / online_width,
                     float(update_data.stuff.y2) / online_height)
        chasm_pos = (float(update_data.chasm.x1) / online_width, float(update_data.chasm.y1) / online_height,
                     float(update_data.chasm.x2) / online_width,
                     float(update_data.chasm.y2) / online_height)
        while True:
            self.auto.take_screenshot()

            if not enter_maneuver_flag:
                if only_collect:
                    # 仅领取活动物资时，直接进入活动任务页，不再点击材料本/深渊
                    if self.wait_activity_reward_page(timeout_seconds=2):
                        enter_maneuver_flag = True
                        continue

                    if self.open_activity_reward_page(max_attempts=3):
                        enter_maneuver_flag = True
                        continue
                    else:
                        self.logger.warn("活动奖励页面未成功打开，继续重试")
                        time.sleep(0.5)
                        continue

                # 关卡未解锁
                if self.auto.find_element('解锁', 'text', crop=(717 / 1920, 441 / 1080, 1211 / 1920, 621 / 1080),
                                          is_log=self.is_log):
                    finish_flag = True
                    enter_maneuver_flag = True
                    self.auto.press_key('esc')
                    self.logger.warn("材料本未解锁“深渊”难度")
                    time.sleep(0.5)
                    continue
                if self.auto.click_element('速战', 'text', crop=(1368 / 1920, 963 / 1080, 1592 / 1920, 1),
                                           is_log=self.is_log):
                    time.sleep(1)
                    enter_maneuver_flag = True
                    continue
                # 在区域内找材料，没找到就固定点击
                if self.auto.click_element(['材料', '材', '料'], 'text', crop=stuff_pos, n=50, is_log=self.is_log):
                    time.sleep(0.3)
                    continue
                else:
                    if not (self.auto.find_element('基地', 'text', crop=(
                            1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080)) and self.auto.find_element('任务',
                                                                                                          'text',
                                                                                                          crop=(
                                                                                                                  1452 / 1920,
                                                                                                                  327 / 1080,
                                                                                                                  1529 / 1920,
                                                                                                                  376 / 1080))):
                        pos = self.get_click_pos("stuff")  # 获取点击位置
                        self.auto.click_element_with_pos(pos)
                        time.sleep(0.3)
                if self.auto.click_element(['深渊', '深', '渊'], 'text', crop=chasm_pos,
                                           is_log=self.is_log):

                    time.sleep(1)
                    continue
                else:
                    if not (self.auto.find_element('基地', 'text', crop=(
                            1598 / 1920, 678 / 1080, 1661 / 1920, 736 / 1080)) and self.auto.find_element('任务',
                                                                                                          'text',
                                                                                                          crop=(
                                                                                                                  1452 / 1920,
                                                                                                                  327 / 1080,
                                                                                                                  1529 / 1920,
                                                                                                                  376 / 1080))):
                        pos = self.get_click_pos("chasm")
                        self.auto.click_element_with_pos(pos)
                        time.sleep(1)
                # 需要用偏移的方式实现，这样有一个对“任务”的判断，说明还在主页面
                if self.auto.click_element("任务", "text", crop=(1445 / 1920, 321 / 1080, 1552 / 1920, 398 / 1080),
                                           offset=(-34 / self.auto.scale_x, 140 / self.auto.scale_y),
                                           is_log=self.is_log):
                    if not self.wait_activity_task_tab(timeout_seconds=10):
                        self.logger.error("进入活动页面超时")
                    continue
            else:
                if finish_flag:
                    if self.auto.find_element(['剩余', '刷新', '天'], 'text',
                                              crop=(826 / 2560, 239 / 1440, 1393 / 2560, 1188 / 1440),
                                              is_log=self.is_log) or self.auto.find_element('领取', 'text', crop=(
                            0, 937 / 1080, 266 / 1920, 1), is_log=self.is_log):
                        enter_task = True
                        if not reward_status_logged:
                            has_reward = self.auto.find_element('领取', 'text', crop=(0, 937 / 1080, 266 / 1920, 1),
                                                                is_log=self.is_log)
                            if has_reward:
                                self.logger.info("活动奖励页面已就绪，检测到可领取奖励")
                            else:
                                self.logger.info("活动奖励页面已就绪，当前无可领取奖励")
                            reward_status_logged = True
                    if enter_task:
                        if self.auto.click_element('领取', 'text', crop=(0, 937 / 1080, 266 / 1920, 1),
                                                   is_log=self.is_log):
                            break
                        if not self.auto.find_element('领取', 'text', crop=(0, 937 / 1080, 266 / 1920, 1),
                                                      is_log=self.is_log):
                            break
                    task_name = config.task_name.value
                    clicked_task = self.auto.click_element('任务', 'text', crop=(0, 1280 / 1440, 1, 1),
                                                          is_log=self.is_log)
                    if not clicked_task and task_name:
                        clicked_task = self.auto.click_element(task_name, 'text', crop=(0, 1280 / 1440, 1, 1),
                                                              is_log=self.is_log)
                    if clicked_task:
                        if self.wait_activity_reward_page(timeout_seconds=8):
                            enter_task = True
                        else:
                            self.logger.warn("等待活动任务奖励页面超时，重试打开任务")
                        continue
                else:
                    if self.auto.find_element("恢复感知", "text",
                                              crop=(1044 / 1920, 295 / 1080, 1487 / 1920, 402 / 1080),
                                              is_log=self.is_log):
                        self.auto.press_key('esc')
                        finish_flag = True
                        time.sleep(0.3)
                        self.auto.press_key('esc')
                        time.sleep(0.5)
                        continue

                    if self.auto.find_element(["快速", "作战"], 'text',
                                              crop=(854 / 1920, 214 / 1080, 1054 / 1920, 286 / 1080)):
                        time.sleep(0.3)
                        self.auto.click_element_with_pos((int(1289 / self.auto.scale_x), int(732 / self.auto.scale_y)))
                        time.sleep(0.2)
                        self.auto.click_element_with_pos((int(980 / self.auto.scale_x), int(851 / self.auto.scale_y)))
                        time.sleep(0.5)
                        continue

                    if self.auto.click_element('速战', 'text', crop=(1368 / 1920, 963 / 1080, 1592 / 1920, 1),
                                               is_log=self.is_log):
                        time.sleep(1)
                        continue
                    if self.auto.click_element('完成', 'text', crop=(880 / 1920, 968 / 1080, 1033 / 1920, 1024 / 1080),
                                               is_log=self.is_log):
                        finish_flag = True
                        continue
                    if self.auto.click_element('等级提升', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                               is_log=self.is_log):
                        continue

            if timeout.reached():
                if only_collect:
                    self.logger.error("领取活动物资超时")
                else:
                    self.logger.error("刷活动体力超时")
                break
        self.auto.back_to_home()

    def by_routine_logistics(self):
        """通过常规后勤使用体力"""
        timeout = Timer(90).start()
        stage_enter_action = 0
        stage_find_battle = 1
        stage_find_chasm = 2
        stage_fight = 3
        stage_done = 4

        stage = stage_enter_action
        no_progress_count = 0
        scroll_no_progress_count = 0

        while True:
            self.auto.take_screenshot()

            progressed = False
            finished = False
            # 战斗内动作只在进入浴火链路后处理，避免在其它页面误判
            if stage == stage_fight:
                progressed, finished = self._handle_routine_common_actions()
                if finished:
                    stage = stage_done
                if progressed:
                    no_progress_count = 0
                    scroll_no_progress_count = 0
                    if not finished:
                        continue

            if stage == stage_enter_action:
                if self.auto.find_element('行动', 'text', crop=(480 / 2560, 1340 / 1440, 625 / 2560, 1400 / 1440),
                                          is_log=self.is_log):
                    stage = stage_find_battle
                    no_progress_count = 0
                    continue

                if self.auto.click_element("战斗", "text", crop=(1510 / 1920, 450 / 1080, 1650 / 1920, 530 / 1080),
                                           is_log=self.is_log, extract=[(39, 39, 56), 128]):
                    no_progress_count = 0
                    time.sleep(0.6)
                    continue

                if self.auto.click_element('行动', 'text', crop=(2085 / 2560, 716 / 1440, 2542 / 2560, 853 / 1440),
                                           is_log=self.is_log):
                    no_progress_count = 0
                    time.sleep(0.5)
                    continue

            elif stage == stage_find_battle:
                if self.auto.click_element('浴火之战', 'text',
                                           crop=(0, 792 / 1080, 1, 862 / 1080),
                                           take_screenshot=True,
                                           is_log=self.is_log):
                    stage = stage_find_chasm
                    no_progress_count = 0
                    scroll_no_progress_count = 0
                    time.sleep(0.8)
                    continue

                if self._routine_scroll_to_find():
                    scroll_no_progress_count += 1
                    no_progress_count = 0
                    if scroll_no_progress_count >= 10:
                        self.logger.warn("查找“浴火之战”连续滚动无进展，尝试重置页面")
                        stage = stage_enter_action
                        scroll_no_progress_count = 0
                    continue

            elif stage == stage_find_chasm:
                if self.auto.click_element(['深渊', '深', '渊'], 'text', is_log=self.is_log):
                    stage = stage_fight
                    no_progress_count = 0
                    scroll_no_progress_count = 0
                    time.sleep(0.8)
                    continue

                # 仅在已进入浴火链路（当前阶段）时，才允许通过战斗特征切到战斗阶段
                if self.auto.find_element('速战', 'text', crop=(1368 / 1920, 963 / 1080, 1592 / 1920, 1),
                                          is_log=self.is_log) or self.auto.find_element(
                        ["快速", "作战"], 'text', crop=(854 / 1920, 214 / 1080, 1054 / 1920, 286 / 1080),
                        is_log=self.is_log) or self.auto.find_element(
                        "恢复感知", "text", crop=(1044 / 1920, 295 / 1080, 1487 / 1920, 402 / 1080), is_log=self.is_log):
                    stage = stage_fight
                    no_progress_count = 0
                    continue

                if self._routine_scroll_to_find():
                    scroll_no_progress_count += 1
                    no_progress_count = 0
                    if scroll_no_progress_count >= 10:
                        self.logger.warn("查找“深渊”连续滚动无进展，尝试重置页面")
                        stage = stage_enter_action
                        scroll_no_progress_count = 0
                    continue

            elif stage == stage_fight:
                if finished:
                    stage = stage_done
                    continue

            elif stage == stage_done:
                break

            no_progress_count += 1
            if no_progress_count >= 8:
                self.logger.warn("常规后勤当前页面无进展，重试")
                self.auto.back_to_home()
                time.sleep(0.4)
                no_progress_count = 0

                # 回退后若回到主页，则重走流程，可从任意位置恢复
                self.auto.take_screenshot()
                if self.is_in_home():
                    stage = stage_enter_action

            if timeout.reached():
                self.logger.error("刷常规后勤超时")
                break

        self.auto.take_screenshot()
        if not self.is_in_home():
            self.auto.back_to_home()

    def _routine_scroll_to_find(self):
        """用于查找浴火之战/深渊时的统一滚动。"""
        return self.auto.mouse_scroll(int(1280 / self.auto.scale_x), int(720 / self.auto.scale_y), -8500,
                                      time_out=1.2)

    def _routine_collect_receive_rewards(self):
        """在完成后领取接收奖励。"""
        for _ in range(3):
            self.auto.take_screenshot()
            if self.auto.click_element('接收', 'text', crop=(982 / 1920, 964 / 1080, 1038 / 1920, 998 / 1080),
                                       is_log=self.is_log):
                time.sleep(0.4)
                self.auto.press_key('esc')
                time.sleep(0.4)

    def _handle_routine_common_actions(self):
        """处理常规后勤全局动作。返回 (是否有进展, 是否完成)。"""
        # 体力不足，结束刷取
        if self.auto.find_element("恢复感知", "text", crop=(1044 / 1920, 295 / 1080, 1487 / 1920, 402 / 1080),
                                  is_log=self.is_log):
            self.auto.press_key('esc')
            time.sleep(0.5)
            self._routine_collect_receive_rewards()
            self.auto.press_key('esc')
            time.sleep(0.5)
            return True, True

        # 快速作战确认面板
        if self.auto.find_element(["快速", "作战"], 'text', crop=(854 / 1920, 214 / 1080, 1054 / 1920, 286 / 1080),
                                  is_log=self.is_log):
            time.sleep(0.2)
            self.auto.click_element_with_pos((int(1289 / self.auto.scale_x), int(732 / self.auto.scale_y)))
            time.sleep(0.2)
            self.auto.click_element_with_pos((int(980 / self.auto.scale_x), int(851 / self.auto.scale_y)))
            time.sleep(0.5)
            return True, False

        # 发起速战
        if self.auto.click_element('速战', 'text', crop=(1368 / 1920, 963 / 1080, 1592 / 1920, 1),
                                   is_log=self.is_log):
            time.sleep(0.8)
            return True, False

        # 战斗完成，收奖励后结束
        if self.auto.click_element('完成', 'text', crop=(880 / 1920, 968 / 1080, 1033 / 1920, 1024 / 1080),
                                   is_log=self.is_log):
            time.sleep(0.4)
            self._routine_collect_receive_rewards()
            return True, True

        # 干扰弹窗
        if self.auto.click_element('等级提升', 'text', crop=(824 / 1920, 0, 1089 / 1920, 129 / 1080),
                                   is_log=self.is_log):
            return True, False

        return False, False
