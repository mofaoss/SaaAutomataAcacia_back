import json
import os

import cv2
import numpy as np

from app.common.config import config
from app.common.image_utils import ImageUtils


class Matcher:
    def __init__(self,
                 scale_steps=100,
                 scale_factor=0.01,
                 match_threshold=0.5,
                 early_stop_threshold=0.7,
                 nms_threshold=0.4):
        self.scale_steps = scale_steps
        self.scale_factor = scale_factor
        self.match_threshold = match_threshold
        self.early_stop_threshold = early_stop_threshold
        self.nms_threshold = nms_threshold
        self.max_scale = 1
        self.scales = {}
        self._init_scales()
        self._get_max_scale()

    def _init_scales(self):
        # 定义文件路径
        file_path = "AppData/scale_cache.json"
        if config.saveScaleCache.value:
            # 检查文件是否存在
            if os.path.exists(file_path):
                try:
                    # 打开并读取 JSON 文件
                    with open(file_path, 'r', encoding='utf-8') as file:
                        self.scales = json.load(file)  # 将 JSON 数据加载到 self.scales
                    # print("scale_cache.json 文件已加载，数据已赋值给 self.scales。")
                except Exception as e:
                    print(f"读取 scale_cache.json 文件时出错: {e}")
        else:
            if os.path.exists(file_path):
                try:
                    # 删除文件
                    os.remove(file_path)
                    # print("scale_cache.json 文件已成功删除。")
                except Exception as e:
                    print(f"删除 scale_cache.json 文件时出错: {e}")

    def save_scale_cache(self):
        # 定义文件路径
        file_path = "AppData/scale_cache.json"

        # 检查 AppData 目录是否存在，如果不存在则创建
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            # 将 self.scales 写入 JSON 文件
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(self.scales, file, indent=4)  # 使用 indent 参数格式化 JSON
            # print("self.scales 已成功保存到 scale_cache.json 文件。")
        except Exception as e:
            print(f"保存 scale_cache.json 文件时出错: {e}")

    def _get_max_scale(self):
        import ctypes
        # 使用 Windows 原生 API 获取屏幕主显示器的宽高，纯原生、0 依赖、极速
        user32 = ctypes.windll.user32
        # 0 代表 SM_CXSCREEN (宽度)，1 代表 SM_CYSCREEN (高度)
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        max_scale = max(1920 / screen_width, 1080 / screen_height) + 0.5
        self.max_scale = round(max_scale, 2)
        self.scale_steps = int(self.max_scale / 0.01)

    def step(self, scale, orig_w, orig_h, tpl_w, tpl_h, template, target, mask):
        step_boxes = []
        step_confidences = []

        resized_w = int(orig_w * scale)
        resized_h = int(orig_h * scale)

        # 跳过无效尺寸
        if resized_w < tpl_w or resized_h < tpl_h or scale <= 0:
            return [], []

        # 执行图像缩放
        resized = cv2.resize(target, (resized_w, resized_h))

        # 模板匹配（使用归一化相关系数法）
        result = cv2.matchTemplate(
            resized,
            template,
            cv2.TM_CCOEFF_NORMED,
            mask=mask)

        # 获取所有超过阈值的匹配位置
        loc = np.where(result >= self.match_threshold)
        for pt in zip(*loc[::-1]):  # pt为(x, y)坐标
            confidence = result[pt[1], pt[0]]
            if not np.isfinite(confidence):  # 跳过非有限值
                continue
            # 将坐标转换回原始图像坐标系
            orig_x = int(pt[0] / scale)
            orig_y = int(pt[1] / scale)
            # 计算原始图像中的目标尺寸
            orig_tpl_w = int(tpl_w / scale)
            orig_tpl_h = int(tpl_h / scale)
            # 收集候选框（原始图像坐标系）
            step_boxes.append([
                orig_x,
                orig_y,
                orig_tpl_w,
                orig_tpl_h
            ])
            step_confidences.append(float(confidence))
        return step_confidences, step_boxes

    def match(self, template_path: str, target: cv2.typing.MatLike):
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            raise FileNotFoundError(f"模板图片读取失败: {template_path}")

        if template.ndim == 3 and template.shape[-1] == 4:
            mask = template[:, :, 3].copy()  # 提取alpha通道
            template = template[:, :, :3]
        else:
            mask = None

        # 统一数据类型，避免 matchTemplate 内部算术操作类型不一致
        if template.dtype != np.uint8:
            template = cv2.normalize(template, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        if target.dtype != np.uint8:
            target = cv2.normalize(target, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        if mask is not None and mask.dtype != np.uint8:
            mask = cv2.normalize(mask, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # 预处理：锐化 + 边缘增强
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        template = cv2.filter2D(template, -1, kernel)
        target = cv2.filter2D(target, -1, kernel)
        # 转换为灰度图
        if template.ndim == 3:
            template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        if target.ndim == 3:
            target = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
        # 获取模板尺寸
        tpl_h, tpl_w = template.shape[:2]
        orig_h, orig_w = target.shape[:2]
        # print(f"{template_path=},{template.shape=},{target.shape=}")

        if config.saveScaleCache.value:
            scale = self.scales.get(template_path, None)
        else:
            scale = None
        if scale is None:
            boxes = []
            confidences = [0]
            for i in range(self.scale_steps):
                scale = self.max_scale - i * self.scale_factor
                step_confidences, step_boxes = self.step(
                    scale,
                    orig_w,
                    orig_h,
                    tpl_w,
                    tpl_h,
                    template,
                    target,
                    mask
                )
                if len(step_confidences) == 0:
                    continue
                if max(step_confidences) > max(confidences):
                    confidences = step_confidences
                    boxes = step_boxes
                    self.scales[template_path] = scale
                    # print(f"if的scale：{self.scales[template_path]}")
                    if min(confidences) > self.early_stop_threshold:
                        break
        else:
            # print(f'else的scale:{self.scales[template_path]}')
            confidences, boxes = self.step(
                scale,
                orig_w,
                orig_h,
                tpl_w,
                tpl_h,
                template,
                target,
                mask
            )

        if len(boxes) == 0:
            return []

        # 非极大值抑制（在原始图像坐标系进行）
        indices = cv2.dnn.NMSBoxes(
            boxes, confidences,
            score_threshold=self.match_threshold,
            nms_threshold=self.nms_threshold
        )

        # 收集检测框
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                x, y, w, h = boxes[i]
                confidence = confidences[i]
                results.append((x, y, w, h, confidence))
        return results


matcher = Matcher()
