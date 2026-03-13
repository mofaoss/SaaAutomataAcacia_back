import ctypes
import logging
import threading
import time

import cv2
import numpy as np
import win32con
import win32gui
import win32ui

from app.framework.i18n.runtime import _
from app.framework.infra.automation.timer import Timer
from app.framework.infra.vision.image import ImageUtils

logger = logging.getLogger(__name__)

# Prevent concurrent GDI/DC captures from corrupting each other.
SCREENSHOT_LOCK = threading.Lock()


def auto_crop_image(img):
    """Crop black borders around an image."""
    if np.mean(img) < 50:
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    col_sum = np.sum(gray, axis=0) / 255
    col_threshold = np.max(col_sum) * 0.03

    left = 0
    for i in range(w):
        if col_sum[i] > col_threshold:
            left = i + 1
            break

    right = w - 1
    for i in range(w - 1, -1, -1):
        if col_sum[i] > col_threshold:
            right = i - 1
            break

    row_sum = np.sum(gray, axis=1) / 255
    row_threshold = np.max(row_sum) * 0.03

    top = 0
    for i in range(h):
        if row_sum[i] > row_threshold:
            top = i
            break

    bottom = h - 1
    for i in range(h - 1, -1, -1):
        if row_sum[i] > row_threshold:
            bottom = i
            break

    return img[top : bottom + 1, left : right + 1]


class Screenshot:
    _screenshot_interval = Timer(0.01)

    def __init__(self, logger=None):
        self.base_width = 1920
        self.base_height = 1080
        self.logger = logger
        self._last_error_log = {}
        ctypes.windll.user32.SetProcessDPIAware()

    def _log_error_throttled(self, key, message=None, interval=2.0):
        now = time.time()
        last = self._last_error_log.get(key, 0)
        if now - last < interval:
            return

        text = message or key
        active_logger = self.logger or logger
        try:
            active_logger.error(text)
        except Exception:
            logger.error(text)
        self._last_error_log[key] = now

    @staticmethod
    def _is_reasonable_size(width: int, height: int) -> bool:
        return 0 < int(width) < 30000 and 0 < int(height) < 30000

    def get_window(self, title):
        hwnd = win32gui.FindWindow(None, title)
        if hwnd:
            return hwnd
        self._log_error_throttled("window_not_found", f"Window not found: {title}")
        return None

    def _query_window_metrics(self, hwnd):
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w = int(right - left)
        h = int(bottom - top)

        client_rect = win32gui.GetClientRect(hwnd)
        client_width = int(client_rect[2] - client_rect[0])
        client_height = int(client_rect[3] - client_rect[1])

        return {
            "left": int(left),
            "top": int(top),
            "right": int(right),
            "bottom": int(bottom),
            "w": w,
            "h": h,
            "client_width": client_width,
            "client_height": client_height,
        }

    def _resolve_metrics(self, hwnd, metrics):
        left = metrics["left"]
        top = metrics["top"]
        w = metrics["w"]
        h = metrics["h"]
        client_width = metrics["client_width"]
        client_height = metrics["client_height"]

        if not self._is_reasonable_size(w, h):
            if self._is_reasonable_size(client_width, client_height):
                w, h = client_width, client_height
                try:
                    c_left, c_top = win32gui.ClientToScreen(hwnd, (0, 0))
                    left, top = int(c_left), int(c_top)
                except Exception:
                    pass
            else:
                return None

        if not self._is_reasonable_size(client_width, client_height):
            return None

        try:
            client_screen_x, client_screen_y = win32gui.ClientToScreen(hwnd, (0, 0))
        except Exception:
            client_screen_x, client_screen_y = left, top

        client_offset_x = int(client_screen_x - left)
        client_offset_y = int(client_screen_y - top)

        return {
            "left": left,
            "top": top,
            "w": int(w),
            "h": int(h),
            "client_width": int(client_width),
            "client_height": int(client_height),
            "client_offset_x": client_offset_x,
            "client_offset_y": client_offset_y,
        }

    def _capture_bgra(self, hwnd, width: int, height: int):
        if not self._is_reasonable_size(width, height):
            return None

        with SCREENSHOT_LOCK:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            if not hwnd_dc:
                return None

            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = None
            bitmap = None
            try:
                save_dc = mfc_dc.CreateCompatibleDC()
                bitmap = win32ui.CreateBitmap()
                bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(bitmap)

                user32 = ctypes.windll.user32
                print_ok = False
                try:
                    print_ok = bool(user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2))
                except Exception:
                    print_ok = False

                if not print_ok:
                    save_dc.BitBlt((0, 0), (width, height), mfc_dc, (0, 0), win32con.SRCCOPY)

                bmpinfo = bitmap.GetInfo()
                bmpstr = bitmap.GetBitmapBits(True)
                if not bmpstr:
                    return None

                return (
                    np.frombuffer(bmpstr, dtype=np.uint8)
                    .reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
                    .copy()
                )
            finally:
                if bitmap is not None:
                    win32gui.DeleteObject(bitmap.GetHandle())
                if save_dc is not None:
                    save_dc.DeleteDC()
                if mfc_dc is not None:
                    mfc_dc.DeleteDC()
                if hwnd_dc:
                    win32gui.ReleaseDC(hwnd, hwnd_dc)

    def screenshot(self, hwnd, crop=(0, 0, 1, 1), is_starter=True, is_interval=True):
        try:
            if is_interval:
                self._screenshot_interval.wait()
            self._screenshot_interval.reset()

            if not hwnd or not win32gui.IsWindow(hwnd):
                self._log_error_throttled("invalid_hwnd", "Screenshot failed: invalid window handle")
                return None

            if win32gui.IsIconic(hwnd):
                self._log_error_throttled("window_minimized", "Screenshot failed: window is minimized")
                return None

            resolved = None
            last_metrics = None
            for retry in range(3):
                try:
                    metrics = self._query_window_metrics(hwnd)
                    last_metrics = metrics
                    resolved = self._resolve_metrics(hwnd, metrics)
                    if resolved is not None:
                        break
                except Exception as e:
                    self._log_error_throttled("rect_error", f"Screenshot failed: unable to read window rect ({repr(e)})")

                if retry < 2:
                    time.sleep(0.01 * (retry + 1))

            if resolved is None:
                if last_metrics:
                    self._log_error_throttled(
                        "invalid_window_size",
                        (
                            f"Screenshot failed: invalid window size ({last_metrics['w']}x{last_metrics['h']}), "
                            f"client size ({last_metrics['client_width']}x{last_metrics['client_height']})"
                        ),
                    )
                else:
                    self._log_error_throttled("invalid_window_size", "Screenshot failed: invalid window/client size")
                return None

            w = resolved["w"]
            h = resolved["h"]
            client_width = resolved["client_width"]
            client_height = resolved["client_height"]

            img = self._capture_bgra(hwnd, w, h)
            if img is None:
                self._log_error_throttled("capture_failed", "Screenshot failed: both PrintWindow and BitBlt failed")
                return None

            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            x1 = max(0, min(w, resolved["client_offset_x"]))
            y1 = max(0, min(h, resolved["client_offset_y"]))
            x2 = max(x1, min(w, x1 + client_width))
            y2 = max(y1, min(h, y1 + client_height))
            img = img[y1:y2, x1:x2, :]

            if img is None or img.size == 0:
                self._log_error_throttled(
                    "empty_client_capture",
                    (
                        f"Screenshot failed: empty client crop, source size {w}x{h}, "
                        f"client size {client_width}x{client_height}"
                    ),
                )
                return None

            img_crop, relative_pos = ImageUtils.crop_image(img, crop, hwnd)

            if is_starter:
                scale_x = 1
                scale_y = 1
            else:
                scale_x = self.base_width / max(1, client_width)
                scale_y = self.base_height / max(1, client_height)

            return img_crop, scale_x, scale_y, relative_pos

        except Exception as e:
            self._log_error_throttled(
                "screenshot_failed",
                f"Screenshot failed: {repr(e)}; window can be backgrounded but not minimized",
            )
            return None
