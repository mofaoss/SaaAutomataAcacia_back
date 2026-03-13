import ctypes
import time
from contextlib import contextmanager

import win32api
import win32con
import win32gui

from app.framework.i18n.runtime import _
from app.framework.infra.config.app_config import config


class WindowTracker:
    def __init__(self, hwnd, logger):
        self.hwnd = hwnd
        self.logger = logger
        self._origin_rect = None
        self._session_started = False
        self._root_hwnd = None
        self._min_visible_size = 1
        self._last_good_rect = None
        self._locked_width = None
        self._locked_height = None
        self._locked_client_width = None
        self._locked_client_height = None
        self._non_client_pad_width = None
        self._non_client_pad_height = None
        self._is_offscreen_hidden = False
        self._tracking_alpha = 1
        self._tracking_visual_applied = False
        self._saved_exstyle = None
        self._restore_width = 1920
        self._restore_height = 1080
        self._hidden_visible_pixels = 1
        self._size_tolerance_px = 2
        self._capture_settle_delay = 0.01

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

    @staticmethod
    def _is_reasonable_size(width: int, height: int) -> bool:
        return 0 < int(width) < 30000 and 0 < int(height) < 30000

    def update_hwnd(self, hwnd):
        self.hwnd = hwnd
        self._root_hwnd = None

    def _resolve_root_hwnd(self):
        if not self._is_hwnd_valid():
            return None
        if self._root_hwnd and win32gui.IsWindow(self._root_hwnd):
            return self._root_hwnd
        try:
            self._root_hwnd = win32gui.GetAncestor(self.hwnd, win32con.GA_ROOT)
        except Exception:
            self._root_hwnd = None
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

    @staticmethod
    def _get_primary_monitor_rect():
        try:
            monitor = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
            monitor_info = win32api.GetMonitorInfo(monitor)
            return monitor_info.get(
                "Monitor",
                (
                    0,
                    0,
                    win32api.GetSystemMetrics(win32con.SM_CXSCREEN),
                    win32api.GetSystemMetrics(win32con.SM_CYSCREEN),
                ),
            )
        except Exception:
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            return 0, 0, width, height

    def _is_hwnd_valid(self):
        return bool(self.hwnd) and win32gui.IsWindow(self.hwnd)

    def _read_metrics(self, root_hwnd):
        rect = win32gui.GetWindowRect(root_hwnd)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        client_width = 0
        client_height = 0
        candidates = []
        if root_hwnd and win32gui.IsWindow(root_hwnd):
            candidates.append(root_hwnd)
        if self.hwnd and win32gui.IsWindow(self.hwnd) and self.hwnd not in candidates:
            candidates.append(self.hwnd)

        for candidate in candidates:
            try:
                client_rect = win32gui.GetClientRect(candidate)
                c_w = int(client_rect[2] - client_rect[0])
                c_h = int(client_rect[3] - client_rect[1])
                if c_w > 0 and c_h > 0:
                    client_width = c_w
                    client_height = c_h
                    break
            except Exception:
                continue

        return rect, int(width), int(height), int(client_width), int(client_height)

    def _remember_size_lock(self, window_w: int, window_h: int, client_w: int, client_h: int):
        if self._is_reasonable_size(window_w, window_h):
            if self._locked_width is None:
                self._locked_width = int(window_w)
            if self._locked_height is None:
                self._locked_height = int(window_h)

        if self._is_reasonable_size(client_w, client_h):
            if self._locked_client_width is None:
                self._locked_client_width = int(client_w)
            if self._locked_client_height is None:
                self._locked_client_height = int(client_h)

            if self._is_reasonable_size(window_w, window_h):
                self._non_client_pad_width = max(0, int(window_w) - int(client_w))
                self._non_client_pad_height = max(0, int(window_h) - int(client_h))

    def set_locked_client_size(self, client_width: int, client_height: int):
        if not self._is_reasonable_size(client_width, client_height):
            return

        self._locked_client_width = int(client_width)
        self._locked_client_height = int(client_height)

        root_hwnd = self._resolve_root_hwnd()
        if not root_hwnd or not win32gui.IsWindow(root_hwnd):
            return

        try:
            _, w, h, c_w, c_h = self._read_metrics(root_hwnd)
            self._remember_size_lock(w, h, c_w, c_h)
        except Exception:
            pass

        if (
            self._non_client_pad_width is not None
            and self._non_client_pad_height is not None
            and self._locked_client_width is not None
            and self._locked_client_height is not None
        ):
            self._locked_width = self._locked_client_width + self._non_client_pad_width
            self._locked_height = self._locked_client_height + self._non_client_pad_height

    def _target_window_size(self, root_hwnd):
        width = self._locked_width
        height = self._locked_height

        if (
            self._locked_client_width is not None
            and self._locked_client_height is not None
            and self._non_client_pad_width is not None
            and self._non_client_pad_height is not None
        ):
            width = self._locked_client_width + self._non_client_pad_width
            height = self._locked_client_height + self._non_client_pad_height

        if not self._is_reasonable_size(width or 0, height or 0):
            try:
                _, current_w, current_h, current_c_w, current_c_h = self._read_metrics(root_hwnd)
                if self._is_reasonable_size(current_w, current_h):
                    width, height = current_w, current_h
                self._remember_size_lock(current_w, current_h, current_c_w, current_c_h)
            except Exception:
                pass

        if not self._is_reasonable_size(width or 0, height or 0):
            width = self._restore_width
            height = self._restore_height

        return int(width), int(height)

    def _set_window_position(self, root_hwnd, insert_after, left, top, width, height):
        win32gui.SetWindowPos(
            root_hwnd,
            insert_after,
            int(left),
            int(top),
            int(width),
            int(height),
            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW | win32con.SWP_NOOWNERZORDER,
        )

    def _pin_to_bottom(self, root_hwnd):
        win32gui.SetWindowPos(
            root_hwnd,
            win32con.HWND_BOTTOM,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_SHOWWINDOW
            | win32con.SWP_NOOWNERZORDER,
        )

    def _ensure_window_size(self, root_hwnd, target_width: int, target_height: int):
        try:
            rect, current_w, current_h, c_w, c_h = self._read_metrics(root_hwnd)
            self._remember_size_lock(current_w, current_h, c_w, c_h)
            if (
                self._is_reasonable_size(current_w, current_h)
                and abs(current_w - target_width) <= self._size_tolerance_px
                and abs(current_h - target_height) <= self._size_tolerance_px
            ):
                self._pin_to_bottom(root_hwnd)
                return
            left, top = rect[0], rect[1]
        except Exception:
            if self._last_good_rect:
                left, top = self._last_good_rect[0], self._last_good_rect[1]
            else:
                m_left, m_top, _, _ = self._get_primary_monitor_rect()
                left, top = m_left + 100, m_top + 100

        self._set_window_position(root_hwnd, win32con.HWND_BOTTOM, left, top, target_width, target_height)

    def _clamp_root_position(self, left: int, top: int, width: int, height: int):
        vs_left, vs_top, vs_right, vs_bottom = self._get_virtual_screen_rect()
        min_visible = self._min_visible_size
        min_left = vs_left - max(0, width - min_visible)
        max_left = vs_right - min_visible
        min_top = vs_top - max(0, height - min_visible)
        max_top = vs_bottom - min_visible
        return max(min_left, min(max_left, left)), max(min_top, min(max_top, top))

    def _get_hidden_parking_position(self):
        vs_left, vs_top, vs_right, vs_bottom = self._get_virtual_screen_rect()
        _ = vs_left, vs_top
        return vs_right - self._hidden_visible_pixels, vs_bottom - self._hidden_visible_pixels

    def _ensure_origin_rect(self):
        with self._per_monitor_dpi_context():
            root_hwnd = self._resolve_root_hwnd()
            if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                return
            try:
                rect, w, h, c_w, c_h = self._read_metrics(root_hwnd)
                if self._is_reasonable_size(w, h):
                    if self._origin_rect is None:
                        self._origin_rect = rect
                    self._last_good_rect = rect
                    self._remember_size_lock(w, h, c_w, c_h)
                    self._session_started = True
            except Exception:
                pass

    def _recover_window(self, root_hwnd, fallback_rect=None):
        try:
            if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                return False

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

            target_width, target_height = self._target_window_size(root_hwnd)
            self._set_window_position(
                root_hwnd,
                win32con.HWND_BOTTOM,
                target_left,
                target_top,
                target_width,
                target_height,
            )
            self._is_offscreen_hidden = False
            return True
        except Exception:
            return False

    def apply_tracking_visual_mode(self) -> bool:
        if not self._is_hwnd_valid():
            return False
        try:
            with self._per_monitor_dpi_context():
                alpha = int(getattr(config, "windowTrackingAlpha").value)
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
                self._pin_to_bottom(root_hwnd)
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

    def prepare_for_capture(self) -> bool:
        if not self._is_hwnd_valid():
            return False

        hidden_before = self._is_offscreen_hidden
        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                self._ensure_origin_rect()
                self.apply_tracking_visual_mode()

                try:
                    _, current_w, current_h, current_c_w, current_c_h = self._read_metrics(root_hwnd)
                except Exception:
                    current_w = current_h = current_c_w = current_c_h = 0

                target_w, target_h = self._target_window_size(root_hwnd)
                invalid_metrics = (
                    not self._is_reasonable_size(current_w, current_h)
                    or not self._is_reasonable_size(current_c_w, current_c_h)
                )

                if hidden_before:
                    hidden_left, hidden_top = self._get_hidden_parking_position()
                    self._set_window_position(
                        root_hwnd,
                        win32con.HWND_BOTTOM,
                        hidden_left,
                        hidden_top,
                        target_w,
                        target_h,
                    )
                    time.sleep(self._capture_settle_delay)
                elif invalid_metrics:
                    if not self._recover_window(root_hwnd):
                        self._set_window_position(
                            root_hwnd,
                            win32con.HWND_BOTTOM,
                            100,
                            100,
                            target_w,
                            target_h,
                        )
                else:
                    self._ensure_window_size(root_hwnd, target_w, target_h)
                    self._pin_to_bottom(root_hwnd)
        except Exception:
            return hidden_before

        return hidden_before

    def align_target_to_cursor(self, x: int, y: int) -> bool:
        if not self._is_hwnd_valid():
            return False

        try:
            with self._per_monitor_dpi_context():
                root_hwnd = self._resolve_root_hwnd()
                if not root_hwnd or not win32gui.IsWindow(root_hwnd):
                    return False

                self._ensure_origin_rect()
                self.apply_tracking_visual_mode()

                try:
                    current_rect, width, height, c_w, c_h = self._read_metrics(root_hwnd)
                    self._remember_size_lock(width, height, c_w, c_h)
                except Exception:
                    width = 0
                    height = 0
                    current_rect = None

                if not self._is_reasonable_size(width, height):
                    self._recover_window(root_hwnd)
                    current_rect, width, height, c_w, c_h = self._read_metrics(root_hwnd)
                    self._remember_size_lock(width, height, c_w, c_h)

                cursor_pos = win32api.GetCursorPos()
                try:
                    target_screen_pos = win32gui.ClientToScreen(self.hwnd, (x, y))
                except Exception:
                    return False

                delta_x = cursor_pos[0] - target_screen_pos[0]
                delta_y = cursor_pos[1] - target_screen_pos[1]

                if current_rect:
                    base_left, base_top = current_rect[0], current_rect[1]
                elif self._last_good_rect:
                    base_left, base_top = self._last_good_rect[0], self._last_good_rect[1]
                else:
                    base_left, base_top = 100, 100

                new_left = base_left + delta_x
                new_top = base_top + delta_y

                width_final, height_final = self._target_window_size(root_hwnd)
                new_left, new_top = self._clamp_root_position(new_left, new_top, width_final, height_final)

                self._set_window_position(
                    root_hwnd,
                    win32con.HWND_BOTTOM,
                    new_left,
                    new_top,
                    width_final,
                    height_final,
                )

                self._last_good_rect = (new_left, new_top, new_left + width_final, new_top + height_final)
                self._is_offscreen_hidden = False
            return True
        except Exception as e:
            self.logger.error(_(f"Window tracking failed: {repr(e)}"))
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
                self.apply_tracking_visual_mode()
                width, height = self._target_window_size(root_hwnd)
                hidden_left, hidden_top = self._get_hidden_parking_position()

                self._set_window_position(
                    root_hwnd,
                    win32con.HWND_BOTTOM,
                    hidden_left,
                    hidden_top,
                    width,
                    height,
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
                    if self._origin_rect and self._is_reasonable_size(
                        self._origin_rect[2] - self._origin_rect[0],
                        self._origin_rect[3] - self._origin_rect[1],
                    ):
                        target_left = self._origin_rect[0]
                        target_top = self._origin_rect[1]
                        target_width = self._origin_rect[2] - self._origin_rect[0]
                        target_height = self._origin_rect[3] - self._origin_rect[1]
                    else:
                        monitor_left, monitor_top, monitor_right, monitor_bottom = self._get_primary_monitor_rect()
                        monitor_width = monitor_right - monitor_left
                        monitor_height = monitor_bottom - monitor_top
                        target_width, target_height = self._target_window_size(root_hwnd)
                        target_left = monitor_left + (monitor_width - target_width) // 2
                        target_top = monitor_top + (monitor_height - target_height) // 2

                    self._set_window_position(
                        root_hwnd,
                        win32con.HWND_NOTOPMOST,
                        target_left,
                        target_top,
                        target_width,
                        target_height,
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
            self._locked_client_width = None
            self._locked_client_height = None
            self._non_client_pad_width = None
            self._non_client_pad_height = None
            self._is_offscreen_hidden = False
