import ctypes
import time
from contextlib import contextmanager
from app.framework.i18n.runtime import _

import win32api
import win32con
import win32gui

from app.framework.infra.config.app_config import config


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
        self._restore_width = 1920
        self._restore_height = 1080

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
        vs_left, vs_top, vs_right, vs_bottom = self._get_virtual_screen_rect()
        # 移出到虚拟屏幕右下角之外
        return vs_right + self._offscreen_margin, vs_bottom + self._offscreen_margin

    @staticmethod
    def _get_primary_monitor_rect():
        try:
            monitor = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
            monitor_info = win32api.GetMonitorInfo(monitor)
            return monitor_info.get("Monitor", (0, 0, win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                                                  win32api.GetSystemMetrics(win32con.SM_CYSCREEN)))
        except Exception:
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            return 0, 0, width, height

    def _is_hwnd_valid(self):
        return bool(self.hwnd) and win32gui.IsWindow(self.hwnd)

    def _ensure_origin_rect(self):
        with self._per_monitor_dpi_context():
            root_hwnd = self._resolve_root_hwnd()
            if self._origin_rect is None and root_hwnd and win32gui.IsWindow(root_hwnd):
                try:
                    rect = win32gui.GetWindowRect(root_hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if 0 < w < 30000 and 0 < h < 30000:
                        self._origin_rect = rect
                        self._last_good_rect = rect
                        self._locked_width = w
                        self._locked_height = h
                        self._session_started = True
                except Exception:
                    pass

    def _recover_window(self, root_hwnd, fallback_rect=None):
        """强制窗口物理可见并恢复预设尺寸。"""
        try:
            if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                return False
            
            # 强制唤醒
            if win32gui.IsIconic(root_hwnd):
                win32gui.ShowWindow(root_hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(root_hwnd, win32con.SW_SHOWNOACTIVATE)
            
            rect = fallback_rect or self._last_good_rect or self._origin_rect
            if rect:
                target_left, target_top = rect[0], rect[1]
            else:
                m_left, m_top, _, _ = self._get_primary_monitor_rect()
                target_left, target_top = m_left + 100, m_top + 100

            width = self._locked_width or self._restore_width
            height = self._locked_height or self._restore_height

            # 关键：显式设置尺寸，不使用 SWP_NOSIZE
            win32gui.SetWindowPos(
                root_hwnd,
                win32con.HWND_NOTOPMOST,
                target_left,
                target_top,
                width,
                height,
                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            return False

    def align_target_to_cursor(self, x: int, y: int) -> bool:
        if not self._is_hwnd_valid():
            return False

        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                self._ensure_origin_rect()
                
                # 显式获取尺寸，如果发现 0x0 立即原地恢复
                try:
                    current_rect = win32gui.GetWindowRect(root_hwnd)
                    width = current_rect[2] - current_rect[0]
                    height = current_rect[3] - current_rect[1]
                except Exception:
                    width = 0
                    
                if width <= 0 or height <= 0 or width > 30000:
                    self._recover_window(root_hwnd)
                    current_rect = win32gui.GetWindowRect(root_hwnd)
                    width = current_rect[2] - current_rect[0]
                    height = current_rect[3] - current_rect[1]

                # 获取坐标映射
                cursor_pos = win32api.GetCursorPos()
                try:
                    target_screen_pos = win32gui.ClientToScreen(self.hwnd, (x, y))
                except Exception:
                    return False

                delta_x = cursor_pos[0] - target_screen_pos[0]
                delta_y = cursor_pos[1] - target_screen_pos[1]

                new_left = current_rect[0] + delta_x
                new_top = current_rect[1] + delta_y
                
                # 限制位置，确保不会完全飞出虚拟桌面导致被系统强杀
                width_final = self._locked_width or width
                height_final = self._locked_height or height
                new_left, new_top = self._clamp_root_position(new_left, new_top, width_final, height_final)

                # 核心移动：绝对禁止使用 SWP_NOSIZE，每一帧都强制同步尺寸
                # 移除 HWND_BOTTOM 以防止 DWM 遮蔽触发
                win32gui.SetWindowPos(
                    root_hwnd,
                    None,
                    new_left,
                    new_top,
                    width_final,
                    height_final,
                    win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
                )

                self._last_good_rect = (new_left, new_top, new_left + width_final, new_top + height_final)
                self._is_offscreen_hidden = False
            return True
        except Exception as e:
            self.logger.error(_(f"Window tracking failed: {repr(e)}"))
            return False

    def hide_window_offscreen(self) -> bool:
        """安全地将窗口推送到视线之外，同时保持其存活。"""
        if not self._is_hwnd_valid():
            return False

        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                self._ensure_origin_rect()
                
                # 推送前最后一次同步尺寸
                width = self._locked_width or self._restore_width
                height = self._locked_height or self._restore_height

                hidden_left, hidden_top = self._get_offscreen_position()
                
                # 关键修复：绝对不使用 HWND_BOTTOM 和 SWP_NOSIZE
                # 使用普通层级（HWND_NOTOPMOST）移动到极远坐标，系统通常不会置零尺寸
                win32gui.SetWindowPos(
                    root_hwnd,
                    win32con.HWND_NOTOPMOST,
                    hidden_left,
                    hidden_top,
                    width,
                    height,
                    win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
                )
                self._is_offscreen_hidden = True
            return True
        except Exception as e:
            self.logger.warning(_(f"Window out of view area failed: {repr(e)}"))
            return False

    def restore_window_position(self):
        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if root_hwnd and win32gui.IsWindow(root_hwnd):
                    monitor_left, monitor_top, monitor_right, monitor_bottom = self._get_primary_monitor_rect()
                    monitor_width = monitor_right - monitor_left
                    monitor_height = monitor_bottom - monitor_top

                    target_width = self._locked_width or self._restore_width
                    target_height = self._locked_height or self._restore_height
                    target_left = monitor_left + (monitor_width - target_width) // 2
                    target_top = monitor_top + (monitor_height - target_height) // 2

                    win32gui.SetWindowPos(
                        root_hwnd,
                        win32con.HWND_NOTOPMOST,
                        target_left,
                        target_top,
                        target_width,
                        target_height,
                        win32con.SWP_SHOWWINDOW,
                    )
                self.restore_tracking_visual_mode()
        except Exception as e:
            self.logger.warning(_(f"Window restoration failed: {repr(e)}"))
        finally:
            self._origin_rect = None
            self._session_started = False
            self._root_hwnd = None
            self._last_good_rect = None
            self._locked_width = None
            self._locked_height = None
            self._is_offscreen_hidden = False
