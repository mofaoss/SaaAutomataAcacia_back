import time

import cv2
import numpy as np

from app.common.config import config
from app.common.image_utils import ImageUtils
from app.common.text_normalizer import normalize_chinese_text
from app.common.utils import cpu_support_avx2
from app.modules.onnxocr.onnx_paddleocr import ONNXPaddleOcr


class OCR:
    def __init__(self, logger, replacements=None):
        # 使用 easyocr 创建 OCR 阅读器
        self.ocr = None
        self.logger = logger
        self.replacements = replacements
        self._last_error_message = None
        self._last_error_time = 0.0
        self._last_input_scale = (1.0, 1.0)
        self._fallback_conf_threshold = 0.75
        self._low_res_width = 1600
        self._low_res_height = 900
        self._early_stop_conf_threshold = 0.90
        self._frame_cache_ttl = 0.25
        self._no_text_cooldown = 0.5
        self._last_signature = None
        self._last_signature_time = 0.0
        self._last_result = None
        self._small_crop_min_side = 140
        self._small_crop_max_area = 140 * 140

    @staticmethod
    def _compute_signature(image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        tiny = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)
        return tiny

    @staticmethod
    def _signature_distance(sig1, sig2):
        if sig1 is None or sig2 is None:
            return 999.0
        return float(np.mean(cv2.absdiff(sig1, sig2)))

    @staticmethod
    def _low_text_likelihood(image):
        """极低成本文本概率判定：纹理/边缘都很低时，通常是过场或纯背景。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        std = float(np.std(gray))
        edges = cv2.Canny(gray, 80, 160)
        edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)
        return std < 12.0 and edge_ratio < 0.006

    def _is_small_crop(self, image):
        h, w = image.shape[:2]
        return min(h, w) <= self._small_crop_min_side or (h * w) <= self._small_crop_max_area

    @staticmethod
    def _has_text_candidate(image):
        """快速文本候选检测：结合边缘密度和连通域数量，避免误判小字无文本。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        if h < 2 or w < 2:
            return False

        edges = cv2.Canny(gray, 60, 140)
        edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)

        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            6,
        )
        binary = cv2.medianBlur(binary, 3)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(255 - binary, connectivity=8)
        valid_components = 0
        img_area = h * w
        min_area = max(3, int(img_area * 0.00008))
        max_area = int(img_area * 0.08)
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            comp_w = int(stats[i, cv2.CC_STAT_WIDTH])
            comp_h = int(stats[i, cv2.CC_STAT_HEIGHT])
            if min_area <= area <= max_area and comp_w >= 2 and comp_h >= 2:
                valid_components += 1

        return edge_ratio >= 0.004 or valid_components >= 2

    def _try_cache_or_skip(self, image, is_log=False):
        now = time.time()
        signature = self._compute_signature(image)
        distance = self._signature_distance(signature, self._last_signature)
        is_small = self._is_small_crop(image)
        has_text_candidate = self._has_text_candidate(image)

        # 同帧或近似帧在短时间内直接复用，避免重复OCR
        if distance <= 1.8 and now - self._last_signature_time <= self._frame_cache_ttl:
            if is_log:
                self.logger.debug("OCR命中帧缓存，跳过重复识别")
            return True, self._last_result, signature

        # 无文本结果冷却期内，近似帧直接跳过（小图不跳，且文本候选存在时不跳）
        if (
            not is_small
            and not has_text_candidate
            and self._last_result is None
            and distance <= 2.5
            and now - self._last_signature_time <= self._no_text_cooldown
        ):
            if is_log:
                self.logger.debug("OCR命中无文本冷却，跳过识别")
            return True, None, signature

        # 低文本概率硬跳过仅对非小图生效，且需文本候选也为否
        if (not is_small) and (not has_text_candidate) and self._low_text_likelihood(image):
            if is_log:
                self.logger.debug("OCR快速判定为低文本概率帧，跳过识别")
            return True, None, signature

        return False, None, signature

    def _update_cache(self, signature, result):
        self._last_signature = signature
        self._last_signature_time = time.time()
        self._last_result = result

    @staticmethod
    def _enhance_low_res_text(image):
        """低分辨率文本增强：轻度锐化，尽量不破坏颜色特征。"""
        blur = cv2.GaussianBlur(image, (0, 0), 1.0)
        return cv2.addWeighted(image, 1.35, blur, -0.35, 0)

    def _prepare_ocr_image(self, image, is_log=False):
        """对低分辨率图像做自适应放大和增强，并返回缩放信息用于坐标回映射。"""
        h, w = image.shape[:2]
        target_w, target_h = 1600, 900
        scale = max(target_w / max(w, 1), target_h / max(h, 1), 1.0)

        # 限制放大倍率，避免极小图像过度插值导致伪影与性能抖动
        scale = min(scale, 2.2)

        if scale > 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            image = self._enhance_low_res_text(image)
            if is_log:
                self.logger.debug(f"OCR低分辨率增强：{w}x{h} -> {new_w}x{new_h} (x{scale:.2f})")
            return image, (scale, scale)

        return image, (1.0, 1.0)

    @staticmethod
    def _prepare_binary_variant(image):
        """更强文本增强：灰度 + CLAHE + 自适应阈值，适合低分辨率小字。"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            8,
        )
        binary = cv2.medianBlur(binary, 3)
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def _is_low_resolution(self, image):
        h, w = image.shape[:2]
        return w < self._low_res_width or h < self._low_res_height

    def _ocr_raw(self, image):
        result = self.ocr.ocr(image)
        if not result:
            return None
        return result[0]

    def _try_strategy(self, image, strategy, is_log=False):
        if strategy == "fast":
            raw = self._ocr_raw(image)
            return self.format_and_replace(raw, is_log=False, scale=(1.0, 1.0)) if raw else None

        if strategy == "base":
            prepared, scale = self._prepare_ocr_image(image, is_log=is_log)
            raw = self._ocr_raw(prepared)
            return self.format_and_replace(raw, is_log=False, scale=scale) if raw else None

        if strategy == "binary":
            binary = self._prepare_binary_variant(image)
            prepared, scale = self._prepare_ocr_image(binary, is_log=False)
            raw = self._ocr_raw(prepared)
            return self.format_and_replace(raw, is_log=False, scale=scale) if raw else None

        return None

    def _is_good_enough(self, formatted_result):
        if not formatted_result:
            return False
        confs = [item[1] for item in formatted_result if isinstance(item, list) and len(item) >= 2]
        if not confs:
            return False
        high_conf_count = sum(1 for c in confs if c >= self._fallback_conf_threshold)
        return max(confs) >= self._early_stop_conf_threshold and high_conf_count >= 1

    def _score_formatted_result(self, formatted_result):
        if not formatted_result:
            return -1
        confs = [item[1] for item in formatted_result if isinstance(item, list) and len(item) >= 2]
        if not confs:
            return -1
        high_conf = sum(1 for c in confs if c >= self._fallback_conf_threshold)
        avg_conf = sum(confs) / len(confs)
        return high_conf * 100 + len(confs) * 10 + avg_conf

    @staticmethod
    def _needs_fallback(formatted_result, conf_threshold):
        if not formatted_result:
            return True
        confs = [item[1] for item in formatted_result if isinstance(item, list) and len(item) >= 2]
        if not confs:
            return True
        return max(confs) < conf_threshold

    def run(self, image, extract: list = None, is_log=False):
        self.instance_ocr()
        try:
            if image is None:
                if is_log:
                    self.logger.debug("OCR输入图像为空，跳过本次识别")
                return None

            if isinstance(image, str):
                image_path = image
                image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)  # 读取图像，保持原始通道
                if image is None:
                    if is_log:
                        self.logger.debug(f"OCR读取图像失败，路径无效或文件不可读：{image_path}")
                    return None
                if len(image.shape) == 3 and image.shape[2] == 4:  # 如果是RGBA图像
                    image = image[:, :, :3]  # 只保留RGB通道
            if extract:
                letter = extract[0]
                threshold = extract[1]
                image = ImageUtils.extract_letters(image, letter, threshold)

            skipped, cached_result, signature = self._try_cache_or_skip(image, is_log=is_log)
            if skipped:
                self._update_cache(signature, cached_result)
                return cached_result

            low_res_mode = self._is_low_resolution(image)
            strategy_order = ["base", "binary", "fast"] if low_res_mode else ["fast", "base", "binary"]

            candidates = []
            for strategy in strategy_order:
                formatted = self._try_strategy(image, strategy, is_log=is_log and strategy == strategy_order[0])
                if formatted:
                    candidates.append((strategy, formatted))
                    if self._is_good_enough(formatted):
                        break

            if not candidates:
                if is_log:
                    self.logger.debug("OCR未识别出任何文字")
                self._update_cache(signature, None)
                return None

            best_name, best_result = max(candidates, key=lambda x: self._score_formatted_result(x[1]))
            if is_log:
                self.logger.debug(f"OCR采用策略: {best_name}")
                self.log_result(best_result)
            self._update_cache(signature, best_result)
            return best_result
        except Exception as e:
            error_message = f"执行ocr出错：{e}"
            now = time.time()
            if error_message != self._last_error_message or now - self._last_error_time > 2:
                self.logger.error(error_message)
                self._last_error_message = error_message
                self._last_error_time = now
            return None

    def format_and_replace(self, result, is_log=False, scale=(1.0, 1.0)):
        """
        转换OCR结果格式，返回统一的数据格式并替换OCR结果中的错误字符串
        :param result: 原始OCR识别结果
        :param is_log: 是否打印日志
        :return: 格式化后的输出，形如 [['16 +', 0.93, [[10.0, 23.0], [75.0, 58.0]]], ...]
        """
        formatted_result = []

        # 遍历每个识别框
        for item in result:
            text = item[1][0]  # OCR 提取的文本
            conf = item[1][1]  # 识别置信度
            box = item[0]  # 识别框的坐标

            scale_x, scale_y = scale
            if scale_x <= 0:
                scale_x = 1.0
            if scale_y <= 0:
                scale_y = 1.0

            # 获取坐标
            left = box[0][0] / scale_x
            top = box[0][1] / scale_y
            right = box[2][0] / scale_x
            bottom = box[2][1] / scale_y

            # 进行错误文本替换
            if self.replacements:
                for old_text, new_text in self.replacements['direct'].items():
                    text = text.replace(old_text, new_text)

            # 条件替换：只有当 new_str 不出现在 item["text"] 中时，才进行替换
                for old_text, new_text in self.replacements['conditional'].items():
                    if new_text not in text:
                        text = text.replace(old_text, new_text)

            # 游戏语言为繁体时，统一转简体以复用现有简体关键词逻辑
            if config.game_language.value == 1:
                text = normalize_chinese_text(text)

            # 格式化输出: [文本, 置信度, 左上和右下坐标]
            formatted_result.append([text, round(conf, 2), [[left, top], [right, bottom]]])

        if is_log:
            self.log_result(formatted_result)
        return formatted_result

    def log_result(self, results):
        log_content = []
        for result in results:
            log_content.append(f'{result[0]}:{result[1]}')
        self.logger.debug(f"OCR识别结果: {log_content}")

    def instance_ocr(self):
        """实例化OCR，若ocr实例未创建，则创建之"""
        if self.ocr is None:
            if config.cpu_support_avx2.value is None:
                cpu_support_avx2()
            try:
                self.logger.debug("开始初始化OCR...")
                #
                if config.cpu_support_avx2.value or config.ocr_use_gpu.value:
                    self.ocr = ONNXPaddleOcr(use_angle_cls=True, use_gpu=config.ocr_use_gpu.value)
                    self.logger.info(f"初始化OCR完成")
                else:
                    self.logger.error(f"初始化OCR失败：此cpu不支持AVX2指令集")
            except Exception as e:
                self.logger.error(f"初始化OCR失败：{e}")
                raise Exception("初始化OCR失败")

    def stop_ocr(self):
        pass
