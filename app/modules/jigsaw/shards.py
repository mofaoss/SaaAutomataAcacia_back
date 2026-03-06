"""
The workflow logic, ROIs, and pipeline design in this script are heavily
inspired by and adapted from the open-source project MAA_SnowBreak.

Special thanks to the original author, overflow65537, for their outstanding
work, reverse-engineering efforts, and contribution to the community.

Original Repository: https://github.com/overflow65537/MAA_SnowBreak/
License: MIT License

# This script respects the original author's copyright and is built upon the foundation of their MIT-licensed pipeline files.
"""

import time
import cv2
from app.modules.automation.timer import Timer
from app.common.config import config


class ShardExchangeModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger
        self.is_log = True
        self.base_w = 1280
        self.base_h = 720

        # 将配置转为字典
        self.config_data = config.toDict()

        # 读取用户的勾选状态。
        # 注意：这里的 key ("enable_receive_shards" 等) 需要和你的 UI 界面以及 config.py 里的定义保持一致！
        self.enable_receive = self.config_data.get("enable_receive_shards", True)
        self.enable_gift = self.config_data.get("enable_gift_shards", True)
        self.enable_recycle = self.config_data.get("enable_recycle_shards", True)

    def _roi(self, x, y, w, h):
        return (x / self.base_w, y / self.base_h, (x + w) / self.base_w, (y + h) / self.base_h)

    def _is_color_match(self, crop_ratio, lower_bgr, upper_bgr):
        if self.auto.first_screenshot is None:
            return False

        h, w = self.auto.first_screenshot.shape[:2]
        x1, y1 = int(crop_ratio[0] * w), int(crop_ratio[1] * h)
        x2, y2 = int(crop_ratio[2] * w), int(crop_ratio[3] * h)

        roi_img = self.auto.first_screenshot[y1:y2, x1:x2]
        if roi_img.size == 0:
            return False

        mean_color = cv2.mean(roi_img)[:3]  # 返回 (B, G, R)
        return all(l <= c <= u for c, l, u in zip(mean_color, lower_bgr, upper_bgr))

    def run(self):
        if not (self.enable_receive or self.enable_gift or self.enable_recycle):
            self.logger.info("信源碎片相关操作均未勾选，跳过该任务。")
            return

        self.logger.info("开始信源碎片相关流程...")
        self.auto.back_to_home()
        self.swipe_to_base_puzzle()

        # 根据用户勾选状态执行对应流程
        if self.enable_receive:
            self.receive_shards()
        else:
            self.logger.info("未勾选【接收碎片】，跳过。")

        if self.enable_gift:
            self.gift_shards()
        else:
            self.logger.info("未勾选【赠送碎片】，跳过。")

        if self.enable_recycle:
            self.exchange_and_recycle()
        else:
            self.logger.info("未勾选【信源回收】，跳过。")

    def swipe_to_base_puzzle(self):
        # 注意这里加入 take_screenshot=True 确保刷新了首张截图
        if self.auto.find_element('app/resource/images/jigsaw/base.png', 'image', crop=self._roi(0, 0, 95, 102), take_screenshot=True, is_log=self.is_log):
            self.logger.info("识别到在基地内部，调整拼图视角...")

            # 使用 first_screenshot 的宽高计算实际点击像素坐标
            h, w = self.auto.first_screenshot.shape[:2]
            sx = int(127 / self.base_w * w)
            sy = int(508 / self.base_h * h)

            # 向左移动
            self.auto.key_down('a')
            time.sleep(0.2)
            self.auto.key_up('a')

    def receive_shards(self):
        self.logger.info("检查是否有待接收的碎片...")
        if self.auto.click_element('接收', 'text', crop=self._roi(247, 0, 504, 129), take_screenshot=True, is_log=self.is_log):
            if self.auto.click_element('键接收', 'text', crop=self._roi(1039, 615, 196, 93), take_screenshot=True, is_log=self.is_log):
                self.logger.info("成功一键接收碎片。")
                time.sleep(1)

    def gift_shards(self):
        self.logger.info("开始赠送流程...")
        if not self.auto.click_element('赠送', 'text', crop=self._roi(247, 0, 504, 129), take_screenshot=True, is_log=self.is_log):
            return

        timeout = Timer(30).start()
        while True:
            self.auto.take_screenshot()

            # 赠送已满颜色阈值 (BGR): lower=[180, 220, 240], upper=[190, 240, 255]
            if self.auto.find_element('信源断片已达上限', 'text', crop=self._roi(454, 333, 383, 48), take_screenshot=False) or \
            self._is_color_match(self._roi(1014, 671, 22, 23), [180, 220, 240], [190, 240, 255]):

                self.logger.warning("达到赠送/接收上限。")
                self.auto.click_element('获得道具', 'text', crop=self._roi(488, 0, 298, 169), take_screenshot=False, is_log=self.is_log)
                break

            if self.auto.click_element('可赠送', 'text', crop=self._roi(53, 16, 189, 82), take_screenshot=False, is_log=self.is_log):
                time.sleep(1)

                self.execute_custom_getting_max()

                if self.auto.click_element('赠送', 'text', crop=self._roi(1145, 100, 135, 322), take_screenshot=True, is_log=self.is_log):
                    self.logger.info("已成功赠送给好友。")
                    time.sleep(1)
                continue

            if self.auto.find_element('app/resource/images/jigsaw/9_piece_present.png', 'image', crop=self._roi(495, 618, 567, 74), take_screenshot=False):
                self.logger.info("没有更多碎片可以赠送了。")
                break

            if timeout.reached():
                self.logger.error("赠送流程超时。")
                break

    def exchange_and_recycle(self):
        self.logger.info("进入信源交换与回收...")
        if self.auto.click_element('交换', 'text', crop=self._roi(821, 240, 257, 307), take_screenshot=True, is_log=self.is_log):
            if self.auto.click_element('回收', 'text', crop=self._roi(853, 254, 220, 300), take_screenshot=True, is_log=self.is_log):
                time.sleep(1)

                self.execute_custom_puzzle_recycle(min_retain=15)

                if self.auto.find_element('不足5段', 'text', crop=self._roi(450, 333, 391, 51), take_screenshot=True):
                    self.logger.warning("碎片不足，无法进行回收。")
                    self.auto.take_screenshot()

    def execute_custom_getting_max(self):
        """寻找数量最大的碎片并选中 """
        self.logger.info("执行自定义动作：寻找并选择数量最多的碎片...")

        pc_roi_list = [
            [28, 147, 25, 21],  [164, 148, 25, 20], [30, 245, 25, 20],  [166, 245, 22, 22],
            [28, 339, 33, 25],  [164, 342, 24, 19], [34, 439, 21, 22],  [161, 440, 28, 20]
        ]

        max_val = -1
        max_roi_ratio = None
        self.auto.take_screenshot()

        for roi in pc_roi_list:
            crop_ratio = self._roi(*roi)
            ocr_results = self.auto.read_text_from_crop(crop=crop_ratio, is_screenshot=False, is_log=False)

            if ocr_results and len(ocr_results) > 0:
                text = ocr_results[0][0]  # ocr_result 格式：[['文本', conf, [[x,y]...]]]
                try:
                    cleaned_text = ''.join(filter(str.isdigit, text))
                    if cleaned_text:
                        digit_val = int(cleaned_text)
                        if digit_val > max_val:
                            max_val = digit_val
                            max_roi_ratio = crop_ratio
                except ValueError:
                    continue

        if max_roi_ratio is not None and max_val > 0:
            self.logger.info(f"寻找到最大碎片数量为: {max_val}，准备点击选中该碎片。")

            h, w = self.auto.first_screenshot.shape[:2]

            top_left = (int(max_roi_ratio[0] * w), int(max_roi_ratio[1] * h))
            bottom_right = (int(max_roi_ratio[2] * w), int(max_roi_ratio[3] * h))

            self.auto.click_element_with_pos((top_left, bottom_right), action="move_click", n=3)
            time.sleep(0.5)
        else:
            self.logger.warning("未能通过 OCR 识别到有效的碎片数量，跳过该操作。")

    def execute_custom_puzzle_recycle(self, min_retain=15):
        self.logger.info(f"开始扫描碎片数量，每种至少保留 {min_retain} 个...")
        self.auto.take_screenshot()

        roi_list = [
            [302, 290, 31, 22], [446, 290, 26, 22], [587, 290, 24, 21], [728, 289, 27, 25],
            [869, 289, 23, 25], [305, 411, 23, 21], [445, 411, 26, 23], [586, 410, 26, 24]
        ]

        puzzle_counts = [0] * 8
        for i, roi in enumerate(roi_list):
            crop_ratio = self._roi(*roi)
            ocr_results = self.auto.read_text_from_crop(crop=crop_ratio, is_screenshot=False, is_log=False)

            if ocr_results and len(ocr_results) > 0:
                text = ocr_results[0][0]
                try:
                    cleaned_text = ''.join(filter(str.isdigit, text))
                    puzzle_counts[i] = int(cleaned_text) if cleaned_text else 0
                except ValueError:
                    puzzle_counts[i] = 0

        self.logger.info(f"当前信源碎片数量总计: {puzzle_counts}")

        recycle_amounts = self._calculate_recycle_amounts(puzzle_counts, min_retain)
        self.logger.info(f"计算完毕，待回收碎片数量分布: {recycle_amounts}")

        h, w = self.auto.first_screenshot.shape[:2]

        for i, count in enumerate(recycle_amounts):
            if count == 0:
                continue

            self.logger.info(f"选中碎片类型 [{i+1}]，准备回收 {count} 个。")

            # 点击对应的碎片
            target_ratio = self._roi(*roi_list[i])
            top_left = (int(target_ratio[0] * w), int(target_ratio[1] * h))
            bottom_right = (int(target_ratio[2] * w), int(target_ratio[3] * h))
            self.auto.click_element_with_pos((top_left, bottom_right), action="move_click")
            time.sleep(0.5)

            # 点击右侧的“添加”按钮 count - 1 次
            add_x = int(835 / self.base_w * w)
            add_y = int(486 / self.base_h * h)

            for _ in range(count - 1):
                self.auto.move_click(add_x, add_y)
                time.sleep(0.5)

        self.logger.info("信源选择完毕，等待后续点击确认回收...")

    def _calculate_recycle_amounts(self, fragment_counts: list, min_retain: int) -> list:
        recyclable = []
        for count in fragment_counts:
            if count >= min_retain:
                recyclable.append(count - min_retain)
            else:
                recyclable.append(0)

        total_recyclable = sum(recyclable)
        actual_recycle = (total_recyclable // 5) * 5
        new_recyclable = [0] * 8

        if actual_recycle == 0:
            return new_recyclable

        remaining = actual_recycle
        for i in range(8):
            if remaining <= 0:
                break
            take = min(recyclable[i], remaining)
            new_recyclable[i] = take
            remaining -= take

        return new_recyclable
