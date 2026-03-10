import math
import re
import time
from app.framework.i18n.runtime import _

from app.framework.infra.automation.timer import Timer
from app.features.utils.home_navigation import back_to_home

from app.framework.core.module_system import on_demand_module, periodic_module


@periodic_module("Character Shards")
class PersonModule:
    def __init__(
        self,
        auto,
        logger,
        isLog=False,
        all_characters=0,
        CheckBox_is_use_chip=False,
        home_interface_person=None,
    ):
        self.auto = auto
        self.logger = logger
        self.power_times = None
        self.select_person_dic = home_interface_person or {}
        self.character_list = [
            self.select_person_dic.get("LineEdit_c1", ""),
            self.select_person_dic.get("LineEdit_c2", ""),
            self.select_person_dic.get("LineEdit_c3", ""),
            self.select_person_dic.get("LineEdit_c4", ""),
        ]
        self.pages = math.ceil(int(all_characters) / 4) + 1
        self.use_chip_enabled = bool(CheckBox_is_use_chip)
        self.no_chip = False
        self.is_log = bool(isLog)

    def run(self):
        back_to_home(self.auto, self.logger)
        self.enter_person()
        for character in self.character_list:
            self.scroll_page(-1, self.pages)
            if character == '':
                continue
            self.find_person_and_quick_fight(character)
            if self.no_chip:
                break
        back_to_home(self.auto, self.logger)

    def enter_person(self):
        timeout = Timer(30).start()
        while True:
            self.auto.take_screenshot()
            # 已进入
            if self.auto.find_element("故事", "text", crop=(786 / 1920, 985 / 1080, 1022 / 1920, 1069 / 1080),
                                      is_log=self.is_log):
                break
            if self.auto.click_element("个人故事", "text", crop=(673 / 1920, 806 / 1080, 953 / 1920, 889 / 1080),
                                       is_log=self.is_log):
                time.sleep(0.3)
                continue
            if self.auto.click_element("战斗", "text", crop=(1510 / 1920, 450 / 1080, 1650 / 1920, 530 / 1080),
                                       is_log=self.is_log, extract=[(39, 39, 56), 128]):
                time.sleep(0.3)
                continue

            # if timeout.reached():
            #     self.logger.error("进入任务碎片界面超时")
            #     break

    def find_person_and_quick_fight(self, person_name):
        timeout = Timer(50).start()
        finish_flag = False
        fight_flag = False
        pos = None
        while True:
            self.auto.take_screenshot()

            if timeout.reached():
                self.logger.error(_("刷取角色碎片超时"))
                break

            if fight_flag and self.auto.find_element('完成', 'text',
                                                     crop=(880 / 1920, 968 / 1080, 1033 / 1920, 1024 / 1080),
                                                     is_log=self.is_log):
                finish_flag = True
            if finish_flag:
                if self.auto.click_element('完成', 'text', crop=(880 / 1920, 968 / 1080, 1033 / 1920, 1024 / 1080),
                                           is_log=self.is_log):
                    time.sleep(0.5)
                    if not self.auto.find_element('完成', 'text',
                                                  crop=(880 / 1920, 968 / 1080, 1033 / 1920, 1024 / 1080),
                                                  is_log=self.is_log,
                                                  take_screenshot=True):
                        break
                else:
                    self.update_power_times()
                    if self.auto.find_element("故事", "text", crop=(786 / 1920, 985 / 1080, 1022 / 1920, 1069 / 1080),
                                              is_log=self.is_log) and (
                            self.power_times == 0 or self.power_times == 6):
                        break
                continue
            if self.auto.find_element("快速作战", "text", crop=(856 / 1920, 229 / 1080, 1056 / 1920, 295 / 1080),
                                      is_log=self.is_log):
                self.auto.click_element('最大', 'text', crop=(1225 / 1920, 683 / 1080, 1341 / 1920, 750 / 1080),
                                        is_log=self.is_log)
                self.auto.click_element('开始作战', 'text', crop=(873 / 1920, 807 / 1080, 1047 / 1920, 864 / 1080),
                                        is_log=self.is_log)
                fight_flag = True
                time.sleep(1.5)
                continue
            # 先尝试使用记忆嵌片
            self.update_power_times()
            # 如果没有嵌片，则尝试使用
            if self.power_times == 0 and self.use_chip_enabled:
                if not self.use_chip():
                    # 没有记忆嵌片
                    if self.no_chip:
                        break
                    continue
                else:
                    self.auto.take_screenshot()
            pos = self.auto.find_element(person_name, "text", crop=(0, 738 / 1080, 1, 838 / 1080), is_log=self.is_log)
            # 找到对应角色
            if pos:
                top_left, bottom_right = pos
                # 传入bottom_right更准确一点
                quick_fight_pos = self.find_quick_fight(bottom_right, person_name)
                if quick_fight_pos:
                    self.auto.click_element_with_pos(quick_fight_pos)
                    time.sleep(0.5)
                    continue
                else:
                    self.logger.warning(_(f"未找到对应速战，检查是否已刷取或是否解锁{person_name}的速战"))
                    break
            else:
                self.scroll_page()
                time.sleep(0.7)

    def find_quick_fight(self, name_pos, person_name):
        """
        根据角色名位置寻找最佳的速战
        :param person_name: 角色名
        :param name_pos: (x,y)
        :return: (x,y)|none
        """
        pos, min_distance = self.auto.find_target_near_source('速战', name_pos, crop=(0, 868 / 1080, 1, 940 / 1080),
                                                              is_log=False)
        if pos:
            # 适配屏幕缩放
            if min_distance < 250 / self.auto.scale_x:
                self.logger.info(_(f"找到对应的“速战”：({pos},{min_distance})"))
                return pos
            else:
                self.logger.warning(_(
                    f"“速战”距离大于{250 / self.auto.scale_x}：({pos},{min_distance})，不是{person_name}的速战"))
                return None
        return pos

    def use_chip(self):
        """
        使用记忆嵌片：固定使用 2 片
        :return: bool 是否成功使用
        """
        timeout = Timer(20).start()

        while True:
            self.auto.take_screenshot()

            # 1. 检查是否提示“没有该类道具”（即碎片/嵌片已经彻底用光）
            if self.auto.find_element('没有该类道具', 'text', crop=(821 / 1920, 511 / 1080, 1092 / 1920, 568 / 1080), is_log=self.is_log):
                self.logger.warning(_("记忆嵌片已用尽"))
                self.no_chip = True
                return False

            # 2. 检查是否在补充对话框内（通过识别“是否”关键字）
            if self.auto.find_element("是否", "text", crop=(588 / 1920, 309 / 1080, 1324 / 1920, 384 / 1080), is_log=self.is_log):
                self.logger.info(_("已打开补充对话框，准备使用 2 片记忆嵌片"))

                # 核心修改：固定点击加号 2 次（1235, 624 为对话框内加号的坐标）
                for click_idx in range(2):
                    self.auto.click_element_with_pos(pos=(int(1235 / self.auto.scale_x), int(624 / self.auto.scale_y)))
                    time.sleep(0.2)

                # 点击确定
                self.auto.click_element('确定', 'text', crop=(1353 / 1920, 729 / 1080, 1528 / 1920, 800 / 1080), is_log=self.is_log)
                time.sleep(1)

                # 确认后按 ESC 关闭可能弹出的“获得物品”提示框
                self.auto.press_key('esc')
                time.sleep(1)
                return True

            # 3. 容错处理：如果不小心点到了物品详情（而不是右上角的加号）
            if self.auto.find_element("记忆嵌片", "text", crop=(803 / 1920, 275 / 1080, 991 / 1920, 346 / 1080), is_log=self.is_log):
                self.logger.debug("未点到加号（点成了物品详情），按 ESC 退出重试")
                self.auto.press_key('esc')
                time.sleep(0.5)
                continue

            # 4. 如果在列表界面，点击右上角的“+”号打开补充对话框
            if self.auto.find_element("故事", "text", crop=(786 / 1920, 985 / 1080, 1022 / 1920, 1069 / 1080), is_log=self.is_log):
                self.logger.info(_("点击右上角加号补充体力"))
                # 1574, 50 为右上角加号的坐标
                self.auto.click_element_with_pos(pos=(int(1574 / self.auto.scale_x), int(50 / self.auto.scale_y)))
                time.sleep(1)
                continue

            # 5. 超时判断
            if timeout.reached():
                self.logger.error(_("使用记忆嵌片超时"))
                self.auto.press_key('esc')
                return False

    def scroll_page(self, direction: int = 1, page=1):
        """
        前后翻页
        :param page: 默认翻一页
        :param direction: 输入 -1（上一页） 或 1（下一页）
        :return:
        """
        direction = -1 if direction >= 0 else 1
        self.auto.mouse_scroll(int(904 / self.auto.scale_x), int(538 / self.auto.scale_y), 7000 * direction * page)

    # def update_power_times(self):
    #     """更新嵌片数量"""
    #     # 格式化后的，并非ocr原生结果：result=[['12/12', 1.0, [[58.0, 16.0], [112.0, 40.0]]]]
    #     result = self.auto.read_text_from_crop(crop=(1430 / 1920, 15 / 1080, 1554 / 1920, 104 / 1080))
    #     # 取出文字送去正则匹配
    #     times = self.detect_times(result[0][0])
    #     if times is not None:
    #         self.logger.info(f"记忆嵌片更新成功：{times}")
    #     else:
    #         self.logger.info(f"记忆嵌片更新失败：{result}")
    #     self.power_times = times
    def update_power_times(self):
        """更新嵌片数量（健壮版）"""
        try:
            result = self.auto.read_text_from_crop(
                crop=(1430 / 1920, 15 / 1080, 1554 / 1920, 104 / 1080)
            )

            # 结构/空值防御
            text = ""
            if isinstance(result, list) and result:
                first = result[0]
                if isinstance(first, (list, tuple)) and first:
                    text = first[0] if isinstance(first[0], str) else ""

            if not text:
                self.logger.warning(_(f"OCR结果为空或结构异常: {result}"))
                self.power_times = None
                return

            # 归一化再匹配
            norm = (
                str(text)
                .replace("／", "/")  # 全角斜杠
                .replace(" ", "")  # 去空格
            )
            times = self.detect_times(norm)
            if times is not None:
                self.logger.info(_(f"记忆嵌片更新成功：{times}"))
            else:
                self.logger.info(_(f"记忆嵌片更新失败：{norm}"))
            self.power_times = times

        except Exception as e:
            self.logger.exception(f"更新嵌片次数失败: {e}")
            self.power_times = None

    @staticmethod
    def detect_times(text: str):
        """
        通过文本检查还有多少次刷取次数
        :param text:格式为“**/**”,str
        :return: '/'前面的嵌片数量
        """
        # 正则表达式模式，匹配任意以数字开头并有"/"的部分
        pattern = r"(\d+)/"
        match = re.search(pattern, text)
        if match:
            # 获取匹配到的第一个组，也就是“/”前的数字
            times = match.group(1)
            return int(times)
        else:
            return None


