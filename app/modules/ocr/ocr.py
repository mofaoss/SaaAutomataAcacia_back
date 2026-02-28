import time

import cv2

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
            image, self._last_input_scale = self._prepare_ocr_image(image, is_log=is_log)
            # ImageUtils.show_ndarray(image)
            # 调用 easyocr 进行 OCR
            original_result = self.ocr.ocr(image)[0]
            if original_result:  # 检查是否识别到文字
                return self.format_and_replace(original_result, is_log)
            else:
                if is_log:
                    self.logger.debug(f"OCR未识别出任何文字")
                return None
        except Exception as e:
            error_message = f"执行ocr出错：{e}"
            now = time.time()
            if error_message != self._last_error_message or now - self._last_error_time > 2:
                self.logger.error(error_message)
                self._last_error_message = error_message
                self._last_error_time = now
            return None

    def format_and_replace(self, result, is_log=False):
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

            scale_x, scale_y = self._last_input_scale
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
