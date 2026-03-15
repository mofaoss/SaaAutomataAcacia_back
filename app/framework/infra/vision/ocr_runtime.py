import gc
import json
import logging
from pathlib import Path
import time

import cv2
import numpy as np

from app.framework.infra.config.app_config import config
from app.framework.infra.config.app_config import is_non_chinese_ui_language
from app.features.utils.text_normalizer import normalize_chinese_text
from app.framework.infra.system.cpu import cpu_support_avx2
from app.framework.infra.vision.onnxocr.onnx_paddleocr import ONNXPaddleOcr
from app.framework.infra.vision.image import ImageUtils
from app.framework.infra.runtime.paths import APPDATA_DIR, APPDATA_OLD_DIR, PROJECT_ROOT, copy_user_data, ensure_runtime_dirs
from app.framework.i18n import _


class OCR:
    def __init__(self, logger, replacements=None):
        self.ocr = None
        self._is_initialized = False
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

        self._is_non_chinese = is_non_chinese_ui_language()

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese else zh_text

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
        """低计算复杂度文本概率判定。"""
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
        """文本候选区域特征检测。"""
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

        if distance <= 1.8 and now - self._last_signature_time <= self._frame_cache_ttl:
            if is_log:
                self.logger.debug(
                    _('OCR hit frame cache, skipping repeated recognition', msgid='ocr_hit_frame_cache_skipping_repeated_recognitio')
                )
            return True, self._last_result, signature

        if (
            not is_small
            and not has_text_candidate
            and self._last_result is None
            and distance <= 2.5
            and now - self._last_signature_time <= self._no_text_cooldown
        ):
            if is_log:
                self.logger.debug(
                    _('OCR hit no-text cooldown, skipping recognition', msgid='ocr_hit_no_text_cooldown_skipping_recognition')
                )
            return True, None, signature

        if (not is_small) and (not has_text_candidate) and self._low_text_likelihood(image):
            if is_log:
                self.logger.debug(
                    _('OCR quick check: low text probability frame, skipping recognition', msgid='ocr_quick_check_low_text_probability_frame_skipp')
                )
            return True, None, signature

        return False, None, signature

    def _update_cache(self, signature, result):
        self._last_signature = signature
        self._last_signature_time = time.time()
        self._last_result = result

    @staticmethod
    def _enhance_low_res_text(image):
        """图像锐化处理。"""
        blur = cv2.GaussianBlur(image, (0, 0), 1.0)
        return cv2.addWeighted(image, 1.35, blur, -0.35, 0)

    def _prepare_ocr_image(self, image, is_log=False):
        """低分辨率图像自适应缩放预处理。"""
        h, w = image.shape[:2]
        target_w, target_h = 1600, 900
        scale = max(target_w / max(w, 1), target_h / max(h, 1), 1.0)
        scale = min(scale, 2.2)

        if scale > 1.0:
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            image = self._enhance_low_res_text(image)
            if is_log:
                self.logger.debug(_(f'OCR low-res enhance: {w}x{h} -> {new_w}x{new_h} (x{scale:.2f})', msgid='ocr_low_res_enhance_w_x_h_new_w_x_new_h_x_scale'))
            return image, (scale, scale)

        return image, (1.0, 1.0)

    @staticmethod
    def _prepare_binary_variant(image):
        """灰度阈值过滤，适用于低对比度图像。"""
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
        result = self.ocr.ocr(image, det=True, rec=True, cls=False)
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
                    self.logger.debug(
                        _('OCR input image is empty, skipping this recognition', msgid='ocr_input_image_is_empty_skipping_this_recogniti')
                    )
                return None

            if isinstance(image, str):
                image_path = image
                image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
                if image is None:
                    if is_log:
                        self.logger.debug(_(f'OCR failed to read image, invalid path or unreadable file: {image_path}', msgid='ocr_failed_to_read_image_invalid_path_or_unreada'))
                    return None
                if len(image.shape) == 3 and image.shape[2] == 4:
                    image = image[:, :, :3]
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
                    self.logger.debug(_('OCR recognized no text', msgid='ocr_recognized_no_text'))
                self._update_cache(signature, None)
                return None

            best_name, best_result = max(candidates, key=lambda x: self._score_formatted_result(x[1]))
            if is_log:
                self.logger.debug(_(f'OCR adopted strategy: {best_name}', msgid='ocr_adopted_strategy_best_name'))
                self.log_result(best_result)
            self._update_cache(signature, best_result)
            return best_result
        except Exception as e:
            error_message = _(f'Error executing ocr: {e}', msgid='error_executing_ocr_e')
            now = time.time()
            if error_message != self._last_error_message or now - self._last_error_time > 2:
                self.logger.error(error_message)
                self._last_error_message = error_message
                self._last_error_time = now
            return None

    def format_and_replace(self, result, is_log=False, scale=(1.0, 1.0)):
        formatted_result = []
        for item in result:
            text = item[1][0]
            conf = item[1][1]
            box = item[0]

            scale_x, scale_y = scale
            if scale_x <= 0:
                scale_x = 1.0
            if scale_y <= 0:
                scale_y = 1.0

            left = box[0][0] / scale_x
            top = box[0][1] / scale_y
            right = box[2][0] / scale_x
            bottom = box[2][1] / scale_y

            if self.replacements:
                for old_text, new_text in self.replacements['direct'].items():
                    text = text.replace(old_text, new_text)

                for old_text, new_text in self.replacements['conditional'].items():
                    if new_text not in text:
                        text = text.replace(old_text, new_text)

            if config.game_language.value == 1:
                text = normalize_chinese_text(text)

            formatted_result.append([text, round(conf, 2), [[left, top], [right, bottom]]])

        if is_log:
            self.log_result(formatted_result)
        return formatted_result

    def log_result(self, results):
        log_content = []
        for result in results:
            log_content.append(f'{result[0]}:{result[1]}')
        self.logger.debug(_(f'OCR recognition result: {log_content}', msgid='ocr_recognition_result_log_content'))

    def instance_ocr(self):
        """实例化OCR引擎。采用单例机制，防止重复初始化导致显存泄漏。"""
        if self._is_initialized and self.ocr is not None:
            return

        if self.ocr is None:
            if config.cpu_support_avx2.value is None:
                cpu_support_avx2(config)
            try:
                self.logger.debug(_('Starting to initialize OCR...', msgid='starting_to_initialize_ocr'))
                if config.cpu_support_avx2.value:
                    # if config.isLog.value:
                    #     self.ocr = ONNXPaddleOcr(use_angle_cls=False, use_gpu=False, logger=self.logger)
                    # else:
                    self.ocr = ONNXPaddleOcr(use_angle_cls=False, use_gpu=False)
                    self.logger.info(_('OCR initialization completed', msgid='ocr_initialization_completed'))
                    self._is_initialized = True
                else:
                    self.logger.error(
                        _('OCR initialization failed: This CPU does not support AVX2 instruction set', msgid='ocr_initialization_failed_this_cpu_does_not_supp')
                    )
            except Exception as e:
                self.logger.error(_(f'OCR initialization failed: {e}', msgid='ocr_initialization_failed_e'))
                raise Exception("初始化OCR失败")

    def stop_ocr(self):
        """清理识别缓存与内部状态，强制执行垃圾回收。不销毁模型实例以支持高频复用。"""
        self._last_signature = None
        self._last_result = None
        self._last_error_message = None
        self._last_signature_time = 0.0
        self._last_error_time = 0.0

        # 强制释放图像残余占用空间
        gc.collect()

def load_ocr_replacements():
    """
    加载 OCR 替换表。
    返回替换数据字典。
    """
    ensure_runtime_dirs()
    user_json_path = APPDATA_DIR / "ocr_replacements.json"
    user_json_old_path = APPDATA_OLD_DIR / "ocr_replacements.json"

    # 1. 确保文件存在（优先级：原文件 > 旧版迁移 > 默认模板 > 空初始化）
    if not user_json_path.exists():
        template_path = PROJECT_ROOT / "resources" / "ocr_table" / "ocr_replacements.json"

        if user_json_old_path.exists():
            copy_user_data(source_path=user_json_old_path, target_path=user_json_path)
        elif template_path.exists():
            copy_user_data(source_path=template_path, target_path=user_json_path)
        else:
            user_json_path.write_text(json.dumps({'direct': {}, 'conditional': {}}, indent=4), encoding='utf-8')

    # 2. 读取并验证数据结构
    try:
        data = json.loads(user_json_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    return {
        "direct": data.get("direct") if isinstance(data.get("direct"), dict) else {},
        "conditional": data.get("conditional") if isinstance(data.get("conditional"), dict) else {}
    }

logger = logging.getLogger(__name__)


ocr = OCR(logger, load_ocr_replacements())
