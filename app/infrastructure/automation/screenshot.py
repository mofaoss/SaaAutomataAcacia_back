import ctypes
import logging
import time
import threading

import cv2
import numpy as np
import win32gui
import win32ui
import win32con

from app.infrastructure.vision.image import ImageUtils
from app.infrastructure.automation.timer import Timer

logger = logging.getLogger(__name__)

# ====== 全局截图锁，防止多线程同时抢占窗口 DC 导致崩溃 ======
SCREENSHOT_LOCK = threading.Lock()
# =========================================================


def auto_crop_image(img):
    """裁切四周的黑边"""
    # 如果是全图都是黑的
    if np.mean(img) < 50:
        return img
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # =============== 垂直方向裁剪（左右黑边） ===============
    col_sum = np.sum(gray, axis=0) / 255  # 每列像素强度总和

    # 动态阈值（取最大值的3%作为黑边判断基准）
    col_threshold = np.max(col_sum) * 0.03

    # 左边界检测（第一个非黑列）
    left = 0
    for i in range(w):
        if col_sum[i] > col_threshold:
            left = i + 1  # 直接使用检测到的索引
            break

    # 右边界检测（最后一个非黑列）
    right = w - 1
    for i in range(w - 1, -1, -1):
        if col_sum[i] > col_threshold:
            right = i - 1
            break

    # =============== 水平方向裁剪（顶部标题+底部黑边） ===============
    row_sum = np.sum(gray, axis=1) / 255

    # 动态阈值（取最大值的3%作为内容判断基准）
    row_threshold = np.max(row_sum) * 0.03

    # 顶部边界检测
    top = 0
    for i in range(h):
        if row_sum[i] > row_threshold:
            top = i
            break

    # 底部边界检测
    bottom = h - 1
    for i in range(h - 1, -1, -1):
        if row_sum[i] > row_threshold:
            bottom = i
            break

    # =============== 执行精确裁剪 ===============
    cropped = img[top:bottom + 1, left:right + 1]  # Python切片含头不含尾
    return cropped


class Screenshot:
    _screenshot_interval = Timer(0.01)

    def __init__(self, logger=None):
        self.base_width = 1920
        self.base_height = 1080
        self.logger = logger
        self._last_error_log = {}
        # 排除缩放干扰
        ctypes.windll.user32.SetProcessDPIAware()

    def _log_error_throttled(self, key, message, interval=2.0):
        now = time.time()
        last = self._last_error_log.get(key, 0)
        if now - last >= interval:
            self.logger.error(message)
            self._last_error_log[key] = now

    def get_window(self, title):
        hwnd = win32gui.FindWindow(None, title)  # 获取窗口句柄
        if hwnd:
            # logger.info(f"找到窗口‘{title}’的句柄为：{hwnd}")
            return hwnd
        else:
            self.logger.error(f"未找到窗口: {title}")
            return None

    def screenshot(self, hwnd, crop=(0, 0, 1, 1), is_starter=True, is_interval=True):
        """
        截取特定区域
        :param is_interval: 是否间隔
        :param is_starter: 是否是启动器
        :param hwnd: 需要截图的窗口句柄
        :param crop: 截取区域, 格式为 (crop_left, crop_top, crop_right, crop_bottom)，范围是0到1之间，表示相对于窗口的比例
        :return:
        """

        try:
            if is_interval:
                self._screenshot_interval.wait()
            self._screenshot_interval.reset()

            if not hwnd or not win32gui.IsWindow(hwnd):
                self._log_error_throttled('invalid_hwnd', "截图失败：无效的窗口句柄，窗口可能已关闭")
                return None

            # 获取窗口尺寸与客户区尺寸
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)

            w = right - left
            h = bottom - top
            if w <= 0 or h <= 0:
                self._log_error_throttled('invalid_window_size', "截图失败：窗口尺寸无效")
                return None

            client_rect = win32gui.GetClientRect(hwnd)
            client_width = client_rect[2] - client_rect[0]
            client_height = client_rect[3] - client_rect[1]
            if client_width <= 0 or client_height <= 0:
                self._log_error_throttled('invalid_client_size', "截图失败：客户区尺寸无效，等待下一帧重试")
                return None
            client_screen_x, client_screen_y = win32gui.ClientToScreen(hwnd, (0, 0))
            client_offset_x = client_screen_x - left
            client_offset_y = client_screen_y - top

            # ====== 核心修复区：加锁并确保安全释放资源 ======
            with SCREENSHOT_LOCK:
                hwnd_dc = win32gui.GetWindowDC(hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = None
                bitmap = None

                try:
                    save_dc = mfc_dc.CreateCompatibleDC()
                    bitmap = win32ui.CreateBitmap()
                    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
                    save_dc.SelectObject(bitmap)

                    # 进行截图
                    user32 = ctypes.windll.user32
                    user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)  # PW_RENDERFULLCONTENT=2

                    # 转换为 numpy 数组
                    bmpinfo = bitmap.GetInfo()
                    bmpstr = bitmap.GetBitmapBits(True)

                    # 为了安全起见，加上 .copy() 脱离底层内存绑定
                    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)).copy()
                finally:
                    # 无论截图成功与否，严谨释放 GDI 资源，防止内存溢出和电脑卡顿
                    if bitmap is not None:
                        win32gui.DeleteObject(bitmap.GetHandle())
                    if save_dc is not None:
                        save_dc.DeleteDC()
                    if mfc_dc is not None:
                        mfc_dc.DeleteDC()
                    if hwnd_dc is not None and hwnd_dc != 0:
                        win32gui.ReleaseDC(hwnd, hwnd_dc)
            # ================================================

            # OpenCV 处理
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            # 始终依据真实客户区偏移裁切，避免固定边框裁切在不同分辨率/主题下失准
            x1 = max(0, min(w, client_offset_x))
            y1 = max(0, min(h, client_offset_y))
            x2 = max(x1, min(w, x1 + client_width))
            y2 = max(y1, min(h, y1 + client_height))
            img = img[y1:y2, x1:x2, :]
            img_crop, relative_pos = ImageUtils.crop_image(img, crop, hwnd)

            # 缩放图像以自适应分辨率图像识别
            if is_starter:
                scale_x = 1
                scale_y = 1
            else:
                # 需要除以用户区域（无标题）才是正确的比例
                scale_x = self.base_width / max(1, client_width)
                scale_y = self.base_height / max(1, client_height)

            return img_crop, scale_x, scale_y, relative_pos

        except Exception as e:
            # print(traceback.format_exc())
            self._log_error_throttled('screenshot_failed', f"截图失败：{repr(e)},窗口可以不置顶但不能最小化")
            return None



