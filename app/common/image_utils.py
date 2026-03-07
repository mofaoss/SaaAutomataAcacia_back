import ctypes

import cv2
import numpy as np
import win32api
import win32con
import win32gui


def is_fullscreen(hwnd):
    """
    判断窗口是否全屏运行
    :param hwnd: 窗口句柄
    :return: True if the window is fullscreen, False otherwise
    """
    # 获取窗口的矩形区域（left, top, right, bottom）
    window_rect = win32gui.GetWindowRect(hwnd)
    window_width = window_rect[2] - window_rect[0]  # 窗口宽度
    window_height = window_rect[3] - window_rect[1]  # 窗口高度

    # 获取屏幕的宽度和高度
    screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

    # 判断窗口大小是否与屏幕大小一致
    if window_width == screen_width and window_height == screen_height:
        return True
    else:
        return False


class ImageUtils:
    @staticmethod
    def get_image_info(image_path):
        """
        获取图片的信息，如尺寸。
        :param image_path: 图片路径。
        :return: 图片的宽度和高度。
        """
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        return template.shape[::-1]

    @staticmethod
    def get_template_mask(target):
        template = cv2.imread(target, cv2.IMREAD_UNCHANGED)
        if template is None:
            return None

        if template.shape[-1] == 4:
            alpha_channel = template[:, :, 3]
            # 只有当 alpha 通道不是全白（255）时，mask 才有意义
            if not np.all(alpha_channel == 255):
                return alpha_channel.astype(np.uint8)
        return None

    @staticmethod
    def calculate_ssim(image1, image2) -> float:
        """
        计算两张图像的相似度。

        参数:
        - image1: 第一张图像路径或 numpy 数组, 一般为模板
        - image2: 第二张图像路径或 numpy 数组, 一般为 target

        返回:
        - 相似度值：一般在 0 到 1 之间（极端不匹配可能为负），值越接近 1 表示图像越相似。
        """
        if isinstance(image1, str):
            image1 = cv2.imread(image1)
        if isinstance(image2, str):
            image2 = cv2.imread(image2)

        if image1 is None or image2 is None:
            return 0.0

        # 确保图像是灰度图像，转换为灰度图
        if len(image1.shape) == 3:
            image1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
        if len(image2.shape) == 3:
            image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)

        # 强制类型转换防止 arithm_op 报错
        image1 = image1.astype(np.uint8)
        image2 = image2.astype(np.uint8)

        if image1.shape != image2.shape:
            image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))

        result = cv2.matchTemplate(image1, image2, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val


    @staticmethod
    def match_template(screenshot, template, mask=None, scale=(1, 1), match_method=cv2.TM_CCOEFF_NORMED, extract=None):
        """
        对模版与截图进行匹配，找出匹配位置
        """
        from app.common.config import config # 局部导入避免循环引用
        import logging
        logger = logging.getLogger(__name__)

        try:
            # 1. 缩放处理
            if scale != (1, 1):
                screenshot = ImageUtils.resize_image(screenshot, scale)

            # 2. 特殊特征提取（如文字提取）
            if extract:
                letter = extract[0]
                threshold = extract[1]
                screenshot = ImageUtils.extract_letters(screenshot, letter, threshold)

            # 3. 数据类型强制检查 (OpenCV arithm.cpp 报错的根源)
            # 确保三者都是 uint8 类型，且通道数匹配
            if screenshot.dtype != np.uint8:
                screenshot = screenshot.astype(np.uint8)
            if template.dtype != np.uint8:
                template = template.astype(np.uint8)

            # 灰度转换检查：如果使用了 CCOEFF_NORMED，建议统一为单通道
            if screenshot.ndim == 3 and template.ndim == 2:
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            elif screenshot.ndim == 2 and template.ndim == 3:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

            # 4. 执行匹配
            if mask is not None:
                if mask.dtype != np.uint8:
                    mask = mask.astype(np.uint8)
                # 兼容性处理：如果 CCOEFF_NORMED 带 mask 依然崩溃（某些OpenCV版本Bug）
                try:
                    result = cv2.matchTemplate(screenshot, template, match_method, mask=mask)
                except cv2.error:
                    #  fallback: 丢弃 mask 裸跑，保证不崩溃
                    result = cv2.matchTemplate(screenshot, template, match_method)
            else:
                result = cv2.matchTemplate(screenshot, template, match_method)

            # 5. 解析结果
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if match_method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                val = 1 - min_val
                loc = min_loc
            else:
                val = max_val
                loc = max_loc

            # 转换回相对用户的坐标
            relative_loc = (loc[0] / scale[0], loc[1] / scale[1])
            return val, relative_loc

        except Exception as e:
            # 根据设置决定是否显示图像识别日志
            if config.isLog.value:
                logger.error(f"图像匹配过程出现异常: {e}")
            # 出错时返回最低相似度和零原点，确保业务逻辑能继续走下去而不闪退
            return 0.0, (0, 0)

    @staticmethod
    def crop_image(screenshot, crop, hwnd):
        """
        按crop裁剪screenshot
        """
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        # print(left, top, right, bottom)
        h, w, c = screenshot.shape
        # 计算裁剪区域裁剪图像
        crop_left = int(crop[0] * w)
        crop_top = int(crop[1] * h)
        crop_right = int(crop[2] * w)
        crop_bottom = int(crop[3] * h)

        img_cropped = screenshot[crop_top:crop_bottom, crop_left:crop_right]
        # print(f"left:{crop_left}")
        # print(f"top:{crop_top}")
        # print(f"right:{crop_right}")
        # print(f"bottom:{crop_bottom}")

        if not is_fullscreen(hwnd):
            relative_pos = (
                crop_left + left,
                crop_top + top,
                crop_right + left,
                crop_bottom + top
            )
        else:
            relative_pos = (
                crop_left,
                crop_top,
                crop_right,
                crop_bottom
            )
        # print(f"relative_pos:{relative_pos}")
        return img_cropped, relative_pos

    @staticmethod
    def resize_image(image, scale):
        """
        根据缩放比例缩放图片
        :param image: 输入的图片（numpy数组）
        :param scale: (scale_x,scale_y)
        :return: 缩放后的图片
        """
        # 获取原始图片的宽度和高度
        height, width = image.shape[:2]

        # 计算缩放后的宽度和高度
        new_width = int(width * scale[0])
        new_height = int(height * scale[1])

        # 使用cv2.resize()函数缩放图片
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        return resized_image

    @staticmethod
    def show_ndarray(image, title="show_ndarray"):
        ctypes.windll.user32.SetProcessDPIAware()
        cv2.imshow(title, image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    @staticmethod
    def show_extract(path: str, extract: list):
        image = cv2.imread(path)
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        letter = extract[0]
        threshold = extract[1]
        image = ImageUtils.extract_letters(image, letter, threshold)
        ImageUtils.show_ndarray(image)

    @staticmethod
    def intersected(top_left1, botton_right1, top_left2, botton_right2):
        """判断两个矩形是否相交。

        参数:
        - top_left1: 第一个矩形的左上角坐标 (x, y)。
        - botton_right1: 第一个矩形的右下角坐标 (x, y)。
        - top_left2: 第二个矩形的左上角坐标 (x, y)。
        - botton_right2: 第二个矩形的右下角坐标 (x, y)。

        返回:
        - bool: 如果矩形相交返回True，否则返回False。

        逻辑说明:
        - 如果一个矩形在另一个矩形的右侧或左侧，它们不相交。
        - 如果一个矩形在另一个矩形的上方或下方，它们也不相交。
        - 否则，矩形相交。
        """
        # 检查矩形1是否在矩形2的右侧或矩形2是否在矩形1的右侧
        if top_left1[0] > botton_right2[0] or top_left2[0] > botton_right1[0]:
            return False
        # 检查矩形1是否在矩形2的下方或矩形2是否在矩形1的下方
        if top_left1[1] > botton_right2[1] or top_left2[1] > botton_right1[1]:
            return False
        # 上述条件都不成立，则矩形相交
        return True

    @staticmethod
    def is_match_non_overlapping(top_left, matches, width, height):
        """检查给定的匹配位置是否与已有的匹配重叠。

        参数:
        - top_left: 当前匹配的左上角坐标。
        - matches: 已有的匹配位置列表。
        - width: 模板宽度。
        - height: 模板高度。

        返回:
        - bool: 是否不重叠。
        """
        botton_right = (top_left[0] + width, top_left[1] + height)
        for match_top_left in matches:
            match_botton_right = (match_top_left[0] + width, match_top_left[1] + height)
            if ImageUtils.intersected(top_left, botton_right, match_top_left, match_botton_right):
                return False
        return True

    @staticmethod
    def filter_overlapping_matches(locations, template_size):
        """过滤掉重叠的匹配。

        参数:
        - locations: 匹配的位置数组。
        - template_size: 模板图片的大小 (宽度, 高度)。

        返回:
        - matches: 不重叠的匹配位置列表。
        """
        matches = []
        height, width = template_size
        for top_left in zip(*locations[::-1]):
            if ImageUtils.is_match_non_overlapping(top_left, matches, width, height):
                matches.append(top_left)
        return matches

    @staticmethod
    def count_template_matches(target, template, threshold):
        """使用模板匹配计算目标图片中的匹配数。

        参数:
        - target: 目标图片数组。
        - template: 模板图片数组。
        - threshold: 匹配阈值，用于决定哪些结果被认为是匹配。

        返回:
        - match_count: 匹配的数量。
        """
        # 执行模板匹配
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        matches = ImageUtils.filter_overlapping_matches(locations, template.shape[:2])
        return len(matches)

    @staticmethod
    def extract_letters(image, letter=(255, 255, 255), threshold=128):
        """
        将目标颜色的文字转成黑色，将背景转成白色
        :param image: np.array类型(height, width, channels)
        :param letter: 文字颜色
        :param threshold:
        :return: np.ndarray: Shape (height, width, 3)
        """
        # (*letter, 0) 将 letter 转换为 (255, 255, 255, 0),表示四个通道（RGB + Alpha），diff 是图像和字母颜色之间的差异
        # 逐像素地将图像中的每个像素减去给定的字母颜色,字母部分归0
        diff = cv2.subtract(image, (*letter, 0))
        # 分离通道
        r, g, b = cv2.split(diff)
        # 从 r、g 和 b 三个通道中选择最大值，最终，r 存储的是每个像素通道中最大的差异值
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        # 正向差异最大值
        positive = r
        # 反向再减一次，得到的是图像与字母的反向差异
        cv2.subtract((*letter, 0), image, dst=diff)
        r, g, b = cv2.split(diff)
        cv2.max(r, g, dst=r)
        cv2.max(r, b, dst=r)
        # 反向差异最大值
        negative = r
        # 通过 cv2.add，将它们加起来，得到整个图像中包含字母和背景的综合差异值
        cv2.add(positive, negative, dst=positive)
        # alpha 参数控制图像的亮度比例，255.0 / threshold 用于调整图像的对比度，这个操作会将综合差异值放大，白的更白，黑的更黑
        cv2.convertScaleAbs(positive, alpha=255.0 / threshold, dst=positive)
        # 将单通道图像转换为3通道图像
        three_channel_image = cv2.merge([positive, positive, positive])
        # cv2.imshow("bw", three_channel_image)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
        return three_channel_image
