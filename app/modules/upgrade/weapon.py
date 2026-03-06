"""
===============================================================================
Acknowledgments

The workflow logic, ROIs, and pipeline design in this script are heavily
inspired by and adapted from the open-source project MAA_SnowBreak.

Special thanks to the original author, overflow65537, for their outstanding
work, reverse-engineering efforts, and contribution to the community.

Original Repository: https://github.com/overflow65537/MAA_SnowBreak/
License: MIT License

This script respects the original author's copyright and is built upon the
foundation of their MIT-licensed pipeline files.
===============================================================================
"""

import time
import cv2
import numpy as np
from app.common.config import config
from app.modules.automation.timer import Timer

class WeaponUpgradeModule:
    def __init__(self, auto, logger):
        self.auto = auto
        self.logger = logger
        self.is_log = True

        # 基准分辨率
        self.base_w = 1280
        self.base_h = 720

        # 读取用户的勾选状态
        self.config_data = config.toDict()
        self.enable_weapon_upgrade = self.config_data.get("enable_weapon_upgrade", True)

    def _roi(self, x, y, w, h):
        return (x / self.base_w, y / self.base_h, (x + w) / self.base_w, (y + h) / self.base_h)

    def _count_color_pixels(self, crop_ratio, lower_bgr, upper_bgr, min_count=100):
        """
        寻找指定区域内，符合颜色范围的像素点总数是否达到 min_count。
        """
        if self.auto.first_screenshot is None:
            return False

        h, w = self.auto.first_screenshot.shape[:2]
        x1, y1 = int(crop_ratio[0] * w), int(crop_ratio[1] * h)
        x2, y2 = int(crop_ratio[2] * w), int(crop_ratio[3] * h)

        roi_img = self.auto.first_screenshot[y1:y2, x1:x2]
        if roi_img.size == 0:
            return False

        # 使用 OpenCV 的 inRange 过滤颜色
        lower = np.array(lower_bgr, dtype="uint8")
        upper = np.array(upper_bgr, dtype="uint8")
        mask = cv2.inRange(roi_img, lower, upper)

        # 计算白色像素点（即匹配该颜色的像素点）的数量
        count = cv2.countNonZero(mask)
        return count >= min_count

    def run(self):
        if not self.enable_weapon_upgrade:
            self.logger.info("用户未勾选【升级枪械】，跳过该任务。")
            return

        self.logger.info("开始武器强化流程...")
        self.auto.back_to_home()

        if self.open_inventory_and_sort():
            self.upgrade_loop()

        self.auto.back_to_home()

    def _wait_and_click(self, target, type, crop, timeout=5, delay=0.5):
        """局部重试辅助方法，增强 UI 翻页切换时的稳定性"""
        t = Timer(timeout).start()
        while not t.reached():
            if self.auto.click_element(target, type, crop=crop, take_screenshot=True, is_log=self.is_log):
                time.sleep(delay)
                return True
            time.sleep(0.5)
        return False

    def open_inventory_and_sort(self):
        """打开背包 -> 排序 -> 选择枪械 -> 点击枪械培养 的一连串前置操作"""
        self.logger.info("正在打开背包并筛选武器...")

        # 1. 打开背包
        if not self._wait_and_click('背包', 'text', self._roi(1021, 625, 144, 119)):
            self.logger.error("未找到背包按钮，中止。")
            return False

        # 2. 点击左下角排序按钮
        if not self._wait_and_click('app/resource/images/upgrade/排序.png', 'image', self._roi(0, 616, 175, 147)):
            return False

        # 3. 排序规则选“等级”
        self._wait_and_click('等级', 'text', self._roi(275, 153, 230, 130))

        # 4. 点击倒序图标
        self._wait_and_click('app/resource/images/upgrade/排序倒序.png', 'image', self._roi(419, 203, 36, 30))

        # 5. 确定排序
        self._wait_and_click('确定', 'text', self._roi(881, 544, 62, 42), delay=1)

        # 6. 选择枪械 (固定坐标: 340, 143)
        self.auto.take_screenshot()
        h, w = self.auto.first_screenshot.shape[:2]
        self.auto.move_click(int(340 / self.base_w * w), int(143 / self.base_h * h))
        time.sleep(1)

        # 7. 点击枪械培养
        if self._wait_and_click('枪械培养', 'text', self._roi(620, 500, 122, 72)):
            self.logger.info("成功进入枪械培养界面。")
            return True

        return False

    def upgrade_loop(self):
        """升级枪械 -> 选择材料 -> 检查颜色 -> 升级 -> 确认升级"""
        timeout = Timer(60).start()

        # 确保在“升级”页签
        self._wait_and_click('升级', 'text', self._roi(46, 140, 136, 121))

        while True:
            self.auto.take_screenshot()

            # 状态 1: 武器等级已满
            if self.auto.find_element('武器等级已满', 'text', crop=self._roi(986, 203, 128, 36), take_screenshot=False):
                self.logger.info("武器等级已满，停止升级流程。")
                break

            # 状态 2: 弹出了“等级提升”窗口
            if self.auto.find_element('等级提升', 'text', crop=self._roi(548, 175, 180, 124), take_screenshot=False):
                self.logger.info("触发【等级提升】，点击空白处关闭弹窗...")
                h, w = self.auto.first_screenshot.shape[:2]
                self.auto.move_click(int(100 / self.base_w * w), int(100 / self.base_h * h))
                time.sleep(1)
                continue

            # 状态 3: 寻找材料区域
            # 注意：如果画面里有对应的白色/绿色/蓝色材料
            mat_imgs = ["app/resource/images/upgrade/白材料.png", "app/resource/images/upgrade/绿材料.png", "app/resource/images/upgrade/蓝材料.png", "app/resource/images/upgrade/紫材料.png"]
            has_materials_on_screen = any(self.auto.find_element(mat, 'image', crop=self._roi(0, 20, 387, 192), take_screenshot=False) for mat in mat_imgs)

            if has_materials_on_screen:
                # 检查升级按钮是否亮起 (变成橙红色)
                # RGB为 [239, 72, 39] 到 [241, 74, 41]。在 OpenCV 中转换为 BGR！
                is_ready_to_upgrade = self._count_color_pixels(
                    self._roi(21, 61, 496, 561),
                    lower_bgr=[39, 72, 239],
                    upper_bgr=[41, 74, 241],
                    min_count=100
                )

                if is_ready_to_upgrade:
                    self.logger.info("经验值已足够，点击【升级】按钮！")
                    self.auto.click_element('升级', 'text', crop=self._roi(1040, 600, 189, 141), take_screenshot=False, is_log=self.is_log)
                    time.sleep(2)  # 等待升级动画
                else:
                    self.logger.info("经验不足，持续添加强化材料...")
                    for mat in mat_imgs:
                        if self.auto.click_element(mat, 'image', crop=self._roi(0, 20, 387, 192), take_screenshot=False):
                            break  # 点到任何一个材料就跳出，重新判定经验条
                    time.sleep(0.3)
                continue

            # 状态 4: 如果没有看到材料，但是看到了 "+" 号
            if self.auto.click_element('app/resource/images/upgrade/选择材料.png', 'image', crop=self._roi(828, 386, 193, 189), take_screenshot=False, is_log=self.is_log):
                self.logger.info("发现空的强化槽，点击【+】号打开材料选择面板...")
                time.sleep(1)
                continue

            if timeout.reached():
                self.logger.error("武器升级流程达到最长执行时间 (超时)。")
                break