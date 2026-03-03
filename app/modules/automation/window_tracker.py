import ctypes
import time
from contextlib import contextmanager

import win32api
import win32con
import win32gui

from app.common.config import config


class WindowTracker:
    def __init__(self, hwnd, logger):
        self.hwnd = hwnd
        self.logger = logger
        self._origin_rect = None
        self._session_started = False
        self._root_hwnd = None
        self._min_visible_size = 120
        self._last_good_rect = None
        self._locked_width = None
        self._locked_height = None
        self._offscreen_margin = 80
        self._is_offscreen_hidden = False
        self._tracking_alpha = 1
        self._tracking_visual_applied = False
        self._saved_exstyle = None
        self._align_deadzone_px = 1

    @contextmanager
    def _per_monitor_dpi_context(self):
        user32 = ctypes.windll.user32
        old_ctx = None
        try:
            old_ctx = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            old_ctx = None
        try:
            yield
        finally:
            if old_ctx:
                try:
                    user32.SetThreadDpiAwarenessContext(old_ctx)
                except Exception:
                    pass

    def update_hwnd(self, hwnd):
        self.hwnd = hwnd
        self._root_hwnd = None

    def _resolve_root_hwnd(self):
        if not self._is_hwnd_valid():
            return None
        if self._root_hwnd and win32gui.IsWindow(self._root_hwnd):
            return self._root_hwnd
        self._root_hwnd = win32gui.GetAncestor(self.hwnd, win32con.GA_ROOT)
        if not self._root_hwnd:
            self._root_hwnd = self.hwnd
        return self._root_hwnd

    @staticmethod
    def _get_virtual_screen_rect():
        left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return left, top, left + width, top + height

    def _clamp_root_position(self, left: int, top: int, width: int, height: int):
        vs_left, vs_top, vs_right, vs_bottom = self._get_virtual_screen_rect()
        min_visible = self._min_visible_size
        min_left = vs_left - max(0, width - min_visible)
        max_left = vs_right - min_visible
        min_top = vs_top - max(0, height - min_visible)
        max_top = vs_bottom - min_visible
        return max(min_left, min(max_left, left)), max(min_top, min(max_top, top))

    def _get_offscreen_position(self):
        _, _, vs_right, vs_bottom = self._get_virtual_screen_rect()
        return vs_right + self._offscreen_margin, vs_bottom + self._offscreen_margin

    def _is_hwnd_valid(self):
        return bool(self.hwnd) and win32gui.IsWindow(self.hwnd)

    def _ensure_origin_rect(self):
        with self._per_monitor_dpi_context():
            root_hwnd = self._resolve_root_hwnd()
            if self._origin_rect is None and root_hwnd and win32gui.IsWindow(root_hwnd):
                self._origin_rect = win32gui.GetWindowRect(root_hwnd)
                self._last_good_rect = self._origin_rect
                self._locked_width = max(1, self._origin_rect[2] - self._origin_rect[0])
                self._locked_height = max(1, self._origin_rect[3] - self._origin_rect[1])
                self._session_started = True

    def _recover_window(self, root_hwnd, fallback_rect=None):
        try:
            if win32gui.IsIconic(root_hwnd):
                win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)
            rect = fallback_rect or self._last_good_rect or self._origin_rect
            if rect is None:
                return False
            width = self._locked_width if self._locked_width else max(1, rect[2] - rect[0])
            height = self._locked_height if self._locked_height else max(1, rect[3] - rect[1])
            win32gui.SetWindowPos(
                root_hwnd,
                None,
                rect[0],
                rect[1],
                width,
                height,
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
            )
            repaired_rect = win32gui.GetWindowRect(root_hwnd)
            repaired_w = repaired_rect[2] - repaired_rect[0]
            repaired_h = repaired_rect[3] - repaired_rect[1]
            if repaired_w > 0 and repaired_h > 0:
                self._last_good_rect = repaired_rect
                return True
        except Exception:
            return False
        return False

    def apply_tracking_visual_mode(self) -> bool:
        if not self._is_hwnd_valid():
            return False
        try:
            with self._per_monitor_dpi_context():
                alpha = int(getattr(config, 'windowTrackingAlpha').value)
                self._tracking_alpha = max(1, min(255, alpha))

                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                exstyle = win32gui.GetWindowLong(root_hwnd, win32con.GWL_EXSTYLE)
                if self._saved_exstyle is None:
                    self._saved_exstyle = exstyle

                target_exstyle = exstyle | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                if target_exstyle != exstyle:
                    win32gui.SetWindowLong(root_hwnd, win32con.GWL_EXSTYLE, target_exstyle)

                win32gui.SetLayeredWindowAttributes(root_hwnd, 0, self._tracking_alpha, win32con.LWA_ALPHA)
                self._tracking_visual_applied = True
                return True
        except Exception:
            return False

    def restore_tracking_visual_mode(self):
        if not self._tracking_visual_applied:
            return
        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return

                if self._saved_exstyle is not None:
                    win32gui.SetWindowLong(root_hwnd, win32con.GWL_EXSTYLE, self._saved_exstyle)
                else:
                    exstyle = win32gui.GetWindowLong(root_hwnd, win32con.GWL_EXSTYLE)
                    if exstyle & win32con.WS_EX_LAYERED:
                        win32gui.SetWindowLong(root_hwnd, win32con.GWL_EXSTYLE, exstyle & ~win32con.WS_EX_LAYERED)
        except Exception:
            pass
        finally:
            self._tracking_visual_applied = False
            self._saved_exstyle = None

    def align_target_to_cursor(self, x: int, y: int) -> bool:
        if not self._is_hwnd_valid():
            self.logger.error("窗口追踪失败：无效窗口句柄")
            return False

        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    self.logger.error("窗口追踪失败：无法获取顶层窗口句柄")
                    return False

                self._ensure_origin_rect()
                cursor_pos = win32api.GetCursorPos()
                target_screen_pos = win32gui.ClientToScreen(self.hwnd, (x, y))
                current_rect = win32gui.GetWindowRect(root_hwnd)
                width = current_rect[2] - current_rect[0]
                height = current_rect[3] - current_rect[1]
                if width <= 0 or height <= 0:
                    if not self._recover_window(root_hwnd):
                        self.logger.warning("窗口追踪失败：窗口尺寸异常，恢复失败，已跳过本次移动")
                    return False
                self._last_good_rect = current_rect

                # 会话期间锁定窗口外框尺寸，避免跨屏 DPI 变更导致窗口被异常缩放
                if self._locked_width and self._locked_height:
                    if abs(width - self._locked_width) > 2 or abs(height - self._locked_height) > 2:
                        win32gui.SetWindowPos(
                            root_hwnd,
                            None,
                            current_rect[0],
                            current_rect[1],
                            self._locked_width,
                            self._locked_height,
                            win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                        )
                        current_rect = win32gui.GetWindowRect(root_hwnd)
                        width = current_rect[2] - current_rect[0]
                        height = current_rect[3] - current_rect[1]
                        if width <= 0 or height <= 0:
                            if not self._recover_window(root_hwnd):
                                self.logger.warning("窗口追踪失败：尺寸纠正后仍异常，恢复失败")
                            return False
                        self._last_good_rect = current_rect

                delta_x = cursor_pos[0] - target_screen_pos[0]
                delta_y = cursor_pos[1] - target_screen_pos[1]

                if abs(delta_x) <= self._align_deadzone_px and abs(delta_y) <= self._align_deadzone_px:
                    win32gui.SetWindowPos(
                        root_hwnd,
                        win32con.HWND_BOTTOM,
                        current_rect[0],
                        current_rect[1],
                        0,
                        0,
                        win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                    )
                    self._is_offscreen_hidden = False
                    return True

                new_left = current_rect[0] + delta_x
                new_top = current_rect[1] + delta_y
                new_left, new_top = self._clamp_root_position(new_left, new_top, width, height)

                win32gui.SetWindowPos(
                    root_hwnd,
                    win32con.HWND_BOTTOM,
                    new_left,
                    new_top,
                    0,
                    0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                )

                moved_rect = win32gui.GetWindowRect(root_hwnd)
                moved_width = moved_rect[2] - moved_rect[0]
                moved_height = moved_rect[3] - moved_rect[1]
                if moved_width <= 0 or moved_height <= 0:
                    if not self._recover_window(root_hwnd):
                        self.logger.warning("窗口追踪检测到窗口尺寸异常，回滚失败")
                    return False

                if self._locked_width and self._locked_height and (
                        abs(moved_width - self._locked_width) > 2 or abs(moved_height - self._locked_height) > 2):
                    win32gui.SetWindowPos(
                        root_hwnd,
                        None,
                        moved_rect[0],
                        moved_rect[1],
                        self._locked_width,
                        self._locked_height,
                        win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                    )
                    moved_rect = win32gui.GetWindowRect(root_hwnd)
                    moved_width = moved_rect[2] - moved_rect[0]
                    moved_height = moved_rect[3] - moved_rect[1]
                    if moved_width <= 0 or moved_height <= 0:
                        if not self._recover_window(root_hwnd):
                            self.logger.warning("窗口追踪检测到跨屏缩放异常，修复失败")
                        return False

                self._last_good_rect = moved_rect
                self._is_offscreen_hidden = False
            return True
        except Exception as e:
            self.logger.error(f"窗口追踪失败：{repr(e)}")
            return False

    def hide_window_offscreen(self) -> bool:
        if not self._is_hwnd_valid():
            return False

        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                self._ensure_origin_rect()
                if win32gui.IsIconic(root_hwnd):
                    win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)

                current_rect = win32gui.GetWindowRect(root_hwnd)
                width = current_rect[2] - current_rect[0]
                height = current_rect[3] - current_rect[1]
                if width <= 0 or height <= 0:
                    if not self._recover_window(root_hwnd):
                        return False
                    current_rect = win32gui.GetWindowRect(root_hwnd)
                    width = current_rect[2] - current_rect[0]
                    height = current_rect[3] - current_rect[1]
                    if width <= 0 or height <= 0:
                        return False

                if self._locked_width and self._locked_height:
                    width = self._locked_width
                    height = self._locked_height

                hidden_left, hidden_top = self._get_offscreen_position()
                win32gui.SetWindowPos(
                    root_hwnd,
                    win32con.HWND_BOTTOM,
                    hidden_left,
                    hidden_top,
                    width,
                    height,
                    win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                )
                self._is_offscreen_hidden = True
            return True
        except Exception as e:
            self.logger.warning(f"窗口移出可视区失败：{repr(e)}")
            return False

    def restore_window_position(self):
        if not self._session_started:
            self.restore_tracking_visual_mode()
            return
        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if root_hwnd and win32gui.IsWindow(root_hwnd) and self._origin_rect is not None:
                    if win32gui.IsIconic(root_hwnd):
                        win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)
                    origin_width = self._locked_width if self._locked_width else max(1, self._origin_rect[2] - self._origin_rect[0])
                    origin_height = self._locked_height if self._locked_height else max(1, self._origin_rect[3] - self._origin_rect[1])
                    win32gui.SetWindowPos(
                        root_hwnd,
                        None,
                        self._origin_rect[0],
                        self._origin_rect[1],
                        origin_width,
                        origin_height,
                        win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOOWNERZORDER,
                    )
                self.restore_tracking_visual_mode()
        except Exception as e:
            self.logger.warning(f"窗口归位失败：{repr(e)}")
        finally:
            self._origin_rect = None
            self._session_started = False
            self._root_hwnd = None
            self._last_good_rect = None
            self._locked_width = None
            self._locked_height = None
            self._is_offscreen_hidden = False
