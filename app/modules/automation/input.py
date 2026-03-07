import ctypes
import logging
import string
import threading
import time
from ctypes import windll

import win32api
import win32con
import win32gui  # 不能删

from app.common.config import config
from app.modules.automation.window_tracker import WindowTracker

logger = logging.getLogger(__name__)

class Input:
    def __init__(self, hwnd, logger):
        self.logger = logger
        self.hwnd = hwnd
        self.VkCode = {
            "back": 0x08, "tab": 0x09, "return": 0x0D, "shift": 0x10,
            "ctrl": 0x11, "alt": 0x12, "pause": 0x13, "capital": 0x14,
            "esc": 0x1B, "space": 0x20, "end": 0x23, "home": 0x24,
            "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
            "print": 0x2A, "snapshot": 0x2C, "insert": 0x2D, "delete": 0x2E,
            "lwin": 0x5B, "rwin": 0x5C, "numpad0": 0x60, "numpad1": 0x61,
            "numpad2": 0x62, "numpad3": 0x63, "numpad4": 0x64, "numpad5": 0x65,
            "numpad6": 0x66, "numpad7": 0x67, "numpad8": 0x68, "numpad9": 0x69,
            "multiply": 0x6A, "add": 0x6B, "separator": 0x6C, "subtract": 0x6D,
            "decimal": 0x6E, "divide": 0x6F, "f1": 0x70, "f2": 0x71,
            "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75, "f7": 0x76,
            "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
            "numlock": 0x90, "scroll": 0x91, "lshift": 0xA0, "rshift": 0xA1,
            "lcontrol": 0xA2, "rcontrol": 0xA3, "lmenu": 0xA4, "rmenu": 0XA5
        }
        self.WmCode = {
            "left_down": 0x0201, "left_up": 0x0202,
            "middle_down": 0x0207, "middle_up": 0x0208,
            "right_down": 0x0204, "right_up": 0x0205,
            "x1_down": 0x020B, "x1_up": 0x020C,
            "x2_down": 0x020B, "x2_up": 0x020C,
            "key_down": 0x0100, "key_up": 0x0101,
            "mouse_move": 0x0200, "mouse_wheel": 0x020A,
        }
        self.MwParam = {
            "x1": 0x0001<<16,
            "x2": 0x0002<<16,
        }
        self._tracking_align_tolerance = 2
        self._tracking_stable_samples = 2
        self._tracking_sample_interval = 0.004
        self._tracking_post_align_settle = 0.006
        self._mouse_action_lock = threading.Lock()
        self._last_shell_guard_log_time = 0.0
        self._shell_guard_log_interval = 2.0
        self._shell_guard_check_interval = 0.08
        self._shell_guard_next_check_time = 0.0
        self._shell_guard_cached_result = False
        self._shell_guard_wait_step = 0.06
        self._shell_guard_max_wait_step = 0.2
        self._shell_window_classes = {
            "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
            "notifyiconoverflowwindow", "dv2controlhost", "multitaskingviewframe",
            "tasklistthumbnailwnd", "xamlexplorerhostislandwindow",
        }
        self.window_tracker = WindowTracker(self.hwnd, self.logger)
        ctypes.windll.user32.SetProcessDPIAware()

    @property
    def _window_tracking_enabled(self):
        return bool(config.windowTrackingInput.value)

    def _sync_tracker_hwnd(self):
        if self.window_tracker.hwnd != self.hwnd:
            self.window_tracker.update_hwnd(self.hwnd)

    @staticmethod
    def _safe_get_root_hwnd(hwnd):
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None
        try:
            root = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            return root or hwnd
        except Exception:
            return hwnd

    def _is_shell_related_hwnd(self, hwnd):
        root_hwnd = self._safe_get_root_hwnd(hwnd)
        if not root_hwnd:
            return False
        try:
            class_name = (win32gui.GetClassName(root_hwnd) or "").lower()
            if class_name in self._shell_window_classes:
                return True

            title = (win32gui.GetWindowText(root_hwnd) or "").lower()
            if "start" in title or "开始" in title or "search" in title or "搜索" in title:
                return True
            if "xaml" in class_name and ("start" in title or "search" in title or "开始" in title or "搜索" in title):
                return True
        except Exception:
            return False
        return False

    def _should_defer_tracking_interaction(self):
        if not self._window_tracking_enabled:
            return False

        now = time.time()
        if now < self._shell_guard_next_check_time:
            return self._shell_guard_cached_result

        try:
            cursor_pos = win32api.GetCursorPos()
            cursor_hwnd = win32gui.WindowFromPoint(cursor_pos)
            foreground_hwnd = win32gui.GetForegroundWindow()

            if self._is_shell_related_hwnd(cursor_hwnd) or self._is_shell_related_hwnd(foreground_hwnd):
                self._shell_guard_cached_result = True
                self._shell_guard_next_check_time = now + self._shell_guard_check_interval
                return True
        except Exception:
            self._shell_guard_cached_result = False
            self._shell_guard_next_check_time = now + self._shell_guard_check_interval
            return False

        self._shell_guard_cached_result = False
        self._shell_guard_next_check_time = now + self._shell_guard_check_interval
        return False

    def _log_shell_guard_wait(self):
        now = time.time()
        if now - self._last_shell_guard_log_time >= self._shell_guard_log_interval:
            if config.isInputLog.value:
                self.logger.info("检测到用户正在与桌面/任务栏等交互，窗口追踪保持隐藏并等待")
            self._last_shell_guard_log_time = now

    def _sleep_for_shell_guard(self):
        wait_step = self._shell_guard_wait_step
        time.sleep(wait_step)
        self._shell_guard_wait_step = min(self._shell_guard_max_wait_step, wait_step + 0.02)

    def _reset_shell_guard_wait(self):
        self._shell_guard_wait_step = 0.06

    def restore_window_position(self):
        self._sync_tracker_hwnd()
        self.window_tracker.restore_window_position()

    def get_virtual_keycode(self, key: str):
        if len(key) == 1 and key in string.printable:
            return windll.user32.VkKeyScanA(ord(key)) & 0xff
        else:
            return self.VkCode[key]

    def activate(self):
        win32gui.PostMessage(self.hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)

    def _client_to_screen(self, x: int, y: int):
        return win32gui.ClientToScreen(self.hwnd, (x, y))

    def _send_mouse_button(self, x: int, y: int, mouse_key: str, is_down: bool, sync: bool = False):
        wparam = 0
        if mouse_key == "left" and is_down:
            wparam |= win32con.MK_LBUTTON
        elif mouse_key == "right" and is_down:
            wparam |= win32con.MK_RBUTTON
        elif mouse_key == "middle" and is_down:
            wparam |= win32con.MK_MBUTTON
        if mouse_key in ["x1", "x2"]:
            wparam = self.MwParam[mouse_key]
        lparam = y << 16 | x
        suffix = "down" if is_down else "up"
        message = self.WmCode[f"{mouse_key}_{suffix}"]
        if sync:
            win32gui.SendMessage(self.hwnd, message, wparam, lparam)
        else:
            win32gui.PostMessage(self.hwnd, message, wparam, lparam)

    def _tracking_alignment_error(self, x: int, y: int):
        target = self._client_to_screen(x, y)
        cursor = win32api.GetCursorPos()
        return abs(cursor[0] - target[0]), abs(cursor[1] - target[1])

    def _is_tracking_alignment_stable(self, x: int, y: int):
        stable_count = 0
        for _ in range(self._tracking_stable_samples):
            dx, dy = self._tracking_alignment_error(x, y)
            if dx <= self._tracking_align_tolerance and dy <= self._tracking_align_tolerance:
                stable_count += 1
            else:
                stable_count = 0
            time.sleep(self._tracking_sample_interval)
        return stable_count >= self._tracking_stable_samples

    def _align_tracking_target(self, x: int, y: int, max_align_attempts=6):
        for _ in range(max_align_attempts):
            if not self.window_tracker.align_target_to_cursor(x, y):
                time.sleep(0.001)
                continue

            time.sleep(self._tracking_post_align_settle)
            if self._is_tracking_alignment_stable(x, y):
                return True
        return False

    def mouse_down(self, x: int, y: int, mouse_key: str = 'left'):
        self._send_mouse_button(x, y, mouse_key, is_down=True, sync=False)

    def mouse_up(self, x: int, y: int, mouse_key: str = 'left'):
        self._send_mouse_button(x, y, mouse_key, is_down=False, sync=False)

    @staticmethod
    def is_mouse_in_use(last_position, threshold=1):
        time.sleep(0.1)
        current_position = win32api.GetCursorPos()
        if abs(current_position[0] - last_position[0]) > threshold or abs(
                current_position[1] - last_position[1]) > threshold:
            return True
        return False

    def move_click(self, x: int, y: int, mouse_key='left', press_time: float = 0.04, time_out: float = 10):
        if isinstance(x, float):
            x = int(x)
        if isinstance(y, float):
            y = int(y)

        start_time = time.time()
        deferred_time = 0.0
        lock_timeout = max(0.1, min(time_out, 1.0))
        if not self._mouse_action_lock.acquire(timeout=lock_timeout):
            self.logger.error(f"鼠标移动点击({x}, {y})出错：获取鼠标操作锁超时")
            return

        try:
            self._sync_tracker_hwnd()
            if not self._window_tracking_enabled:
                self.window_tracker.restore_window_position()
            else:
                self.window_tracker.apply_tracking_visual_mode()

            while True:
                active_elapsed = time.time() - start_time - (deferred_time if self._window_tracking_enabled else 0.0)
                if active_elapsed >= time_out:
                    break

                if not self._window_tracking_enabled:
                    idle_start = None
                    sample_last = win32api.GetCursorPos()
                    while True:
                        active_elapsed = time.time() - start_time
                        if active_elapsed >= time_out:
                            break

                        time.sleep(0.02)
                        sample_now = win32api.GetCursorPos()
                        moved = abs(sample_now[0] - sample_last[0]) > 1 or abs(sample_now[1] - sample_last[1]) > 1
                        if moved:
                            idle_start = None
                        else:
                            if idle_start is None:
                                idle_start = time.time()
                            elif time.time() - idle_start >= 0.08:
                                break
                        sample_last = sample_now

                active_elapsed = time.time() - start_time - (deferred_time if self._window_tracking_enabled else 0.0)
                if active_elapsed >= time_out:
                    break

                current_pos = None
                target_screen_pos = None
                try:
                    self.activate()
                    if self._window_tracking_enabled:
                        click_done = False
                        max_attempts = 3
                        for _ in range(max_attempts):
                            active_elapsed = time.time() - start_time - deferred_time
                            if active_elapsed >= time_out:
                                break

                            if self._should_defer_tracking_interaction():
                                self.window_tracker.hide_window_offscreen()
                                self._log_shell_guard_wait()
                                defer_started = time.time()
                                self._sleep_for_shell_guard()
                                deferred_time += max(0.0, time.time() - defer_started)
                                continue

                            self._reset_shell_guard_wait()

                            if not self._align_tracking_target(x, y):
                                continue

                            dx, dy = self._tracking_alignment_error(x, y)
                            if dx > self._tracking_align_tolerance or dy > self._tracking_align_tolerance:
                                continue

                            lparam = y << 16 | x
                            win32gui.SendMessage(self.hwnd, self.WmCode['mouse_move'], 0, lparam)
                            self._send_mouse_button(x, y, mouse_key, is_down=True, sync=True)
                            time.sleep(max(0.01, press_time))
                            self._send_mouse_button(x, y, mouse_key, is_down=False, sync=True)

                            dx_after, dy_after = self._tracking_alignment_error(x, y)
                            if (
                                dx_after <= self._tracking_align_tolerance + 1
                                and dy_after <= self._tracking_align_tolerance + 1
                                and self._is_tracking_alignment_stable(x, y)
                            ):
                                click_done = True
                                break

                        if click_done:
                            self.window_tracker.hide_window_offscreen()
                            if config.isInputLog.value:
                                self.logger.info(f"窗口追踪点击完成({x}, {y})")
                            return
                        time.sleep(0.003)
                        continue
                    else:
                        target_screen_pos = self._client_to_screen(x, y)
                        current_pos = win32api.GetCursorPos()
                        win32api.SetCursorPos(target_screen_pos)
                        if win32api.GetCursorPos() != target_screen_pos:
                            time.sleep(0.01)
                            win32api.SetCursorPos(target_screen_pos)

                        lparam = y << 16 | x
                        win32gui.PostMessage(self.hwnd, self.WmCode['mouse_move'], 0, lparam)

                        self.mouse_down(x, y, mouse_key)
                        time.sleep(press_time)
                        cur = win32api.GetCursorPos()
                        if abs(cur[0] - target_screen_pos[0]) > 3 or abs(cur[1] - target_screen_pos[1]) > 3:
                            win32api.SetCursorPos(target_screen_pos)
                        self.mouse_up(x, y, mouse_key)

                    time.sleep(0.02)
                    if config.isInputLog.value:
                        self.logger.info(f"鼠标移动后点击({x}, {y})")
                    return
                finally:
                    if current_pos is not None:
                        try:
                            win32api.SetCursorPos(current_pos)
                        except Exception:
                            pass

            active_elapsed = time.time() - start_time - (deferred_time if self._window_tracking_enabled else 0.0)
            if active_elapsed > time_out:
                raise RuntimeError("等待点击超时")
        except Exception as e:
            self.logger.error(f"鼠标移动点击({x}, {y})出错：{repr(e)}")
        finally:
            if self._window_tracking_enabled:
                self.window_tracker.hide_window_offscreen()
            self._mouse_action_lock.release()

    def mouse_click(self, x: int, y: int, mouse_key='left', press_time: float = 0.002):
        try:
            self.activate()
            self.mouse_down(x, y, mouse_key)
            time.sleep(press_time)
            self.mouse_up(x, y, mouse_key)
            if config.isInputLog.value:
                self.logger.info(f"鼠标移动后点击({x}, {y})")
        except Exception as e:
            self.logger.error(f"鼠标移动点击({x}, {y})出错：{repr(e)}")

    def move_to(self, x: int, y: int):
        wparam = 0
        lparam = y << 16 | x
        win32gui.PostMessage(self.hwnd, self.WmCode['mouse_move'], wparam, lparam)

    def _send_scroll_tracking(self, x: int, y: int, delta: int, time_out: float, start_time: float) -> bool:
        if delta == 0:
            return True

        lparam = y << 16 | x
        direction = 1 if delta > 0 else -1
        abs_delta = abs(int(delta))
        notch_count = abs_delta // 120
        remainder = abs_delta % 120

        batch_notches = 16
        total_batches = (notch_count + batch_notches - 1) // batch_notches if notch_count > 0 else 0
        if remainder > 0:
            total_batches += 1

        min_timeout = min(60.0, 1.2 + total_batches * 0.12)
        effective_timeout = max(time_out, min_timeout)
        deferred_time = 0.0

        finished_batches = 0
        sent_notches = 0

        while sent_notches < notch_count:
            active_elapsed = time.time() - start_time - deferred_time
            if active_elapsed >= effective_timeout:
                self.logger.warning(
                    f"窗口追踪滚轮超时，放弃本次滚轮输入: ({x}, {y}, {delta}), "
                    f"batches={total_batches}, finished={finished_batches}, timeout={effective_timeout:.2f}s"
                )
                return False

            if self._should_defer_tracking_interaction():
                self.window_tracker.hide_window_offscreen()
                self._log_shell_guard_wait()
                defer_started = time.time()
                self._sleep_for_shell_guard()
                deferred_time += max(0.0, time.time() - defer_started)
                continue

            self._reset_shell_guard_wait()

            aligned = False
            for _ in range(5):
                if self.window_tracker.align_target_to_cursor(x, y):
                    aligned = True
                    break
                time.sleep(0.001)

            if not aligned:
                self.logger.warning(f"窗口追踪滚轮对齐失败，放弃本次滚轮输入: ({x}, {y}, {delta})")
                return False

            self.activate()
            win32gui.SendMessage(self.hwnd, self.WmCode['mouse_move'], 0, lparam)
            current_batch = min(batch_notches, notch_count - sent_notches)
            for _ in range(current_batch):
                wparam_step = (direction * 120) << 16
                win32gui.SendMessage(self.hwnd, self.WmCode['mouse_wheel'], wparam_step, lparam)

            sent_notches += current_batch
            finished_batches += 1
            time.sleep(0.0015)

        if remainder > 0:
            while True:
                active_elapsed = time.time() - start_time - deferred_time
                if active_elapsed >= effective_timeout:
                    self.logger.warning(
                        f"窗口追踪滚轮超时(尾量)，放弃本次滚轮输入: ({x}, {y}, {delta}), "
                        f"batches={total_batches}, finished={finished_batches}, timeout={effective_timeout:.2f}s"
                    )
                    return False

                if self._should_defer_tracking_interaction():
                    self.window_tracker.hide_window_offscreen()
                    self._log_shell_guard_wait()
                    defer_started = time.time()
                    self._sleep_for_shell_guard()
                    deferred_time += max(0.0, time.time() - defer_started)
                    continue

                self._reset_shell_guard_wait()

                aligned = False
                for _ in range(5):
                    if self.window_tracker.align_target_to_cursor(x, y):
                        aligned = True
                        break
                    time.sleep(0.001)

                if not aligned:
                    self.logger.warning(f"窗口追踪滚轮尾量对齐失败，放弃本次滚轮输入: ({x}, {y}, {delta})")
                    return False

                self.activate()
                win32gui.SendMessage(self.hwnd, self.WmCode['mouse_move'], 0, lparam)
                win32gui.SendMessage(self.hwnd, self.WmCode['mouse_wheel'], (direction * remainder) << 16, lparam)
                break

        if config.isInputLog.value:
            self.logger.info(f"窗口追踪模式滚动完成 ({x},{y}) delta={delta}")
        return True

    def mouse_scroll(self, x: int, y: int, delta: int = 120, time_out: float = 10.):
        if isinstance(x, float):
            x = int(x)
        if isinstance(y, float):
            y = int(y)

        wparam = delta << 16
        message = self.WmCode['mouse_wheel']
        lparam = y << 16 | x

        last_position = win32api.GetCursorPos()
        start_time = time.time()
        try:
            self._sync_tracker_hwnd()
            if not self._window_tracking_enabled:
                self.window_tracker.restore_window_position()
            else:
                self.window_tracker.apply_tracking_visual_mode()
                result = self._send_scroll_tracking(x, y, delta, time_out, start_time)
                self.window_tracker.hide_window_offscreen()
                return result

            while time.time() - start_time < time_out:
                if not self.is_mouse_in_use(last_position):
                    current_pos = None
                    try:
                        if self._window_tracking_enabled and not self.window_tracker.align_target_to_cursor(x, y):
                            time.sleep(0.02)
                            continue

                        self.activate()
                        if not self._window_tracking_enabled:
                            current_pos = win32api.GetCursorPos()
                            target_screen_pos = self._client_to_screen(x, y)
                            win32api.SetCursorPos(target_screen_pos)
                            if win32api.GetCursorPos() != target_screen_pos:
                                time.sleep(0.01)
                                win32api.SetCursorPos(target_screen_pos)
                        else:
                            current_pos = None

                        win32gui.PostMessage(self.hwnd, self.WmCode['mouse_move'], 0, lparam)

                        win32gui.PostMessage(self.hwnd, message, wparam, lparam)
                        time.sleep(0.005)
                        win32gui.PostMessage(self.hwnd, message, wparam, lparam)

                        if config.isInputLog.value:
                            self.logger.info(f"鼠标移动至({x},{y})滚动滚轮 {delta}")
                        return True
                    finally:
                        if current_pos is not None:
                            try:
                                win32api.SetCursorPos(current_pos)
                            except Exception:
                                pass
                last_position = win32api.GetCursorPos()
                time.sleep(0.02)

            self.logger.warning(f"等待滚动滚轮超时，放弃本次滚轮输入: ({x}, {y}, {delta})")
            return False
        except Exception as e:
            self.logger.error(f"鼠标移动({x}, {y})后滚动出错：{repr(e)}")
            return False

    def press_key(self, key, press_time=0.2):
        try:
            self.key_down(key)
            time.sleep(press_time)
            self.key_up(key)
        except Exception as e:
            self.logger.error(f"键盘模拟{key}出错：{repr(e)}")

    def key_down(self, key):
        vk_code = self.get_virtual_keycode(key)
        scan_code = windll.user32.MapVirtualKeyW(vk_code, 0)
        wparam = vk_code
        lparam = (scan_code << 16) | 1
        win32gui.PostMessage(self.hwnd, self.WmCode["key_down"], wparam, lparam)
        if config.isInputLog.value:
            self.logger.info(f"键盘按下{key}")

    def key_up(self, key):
        vk_code = self.get_virtual_keycode(key)
        scan_code = windll.user32.MapVirtualKeyW(vk_code, 0)
        wparam = vk_code
        lparam = (scan_code << 16) | 1
        win32gui.PostMessage(self.hwnd, self.WmCode["key_up"], wparam, lparam)
        if config.isInputLog.value:
            self.logger.info(f"键盘松开{key}")

if __name__ == '__main__':
    import win32gui

    def get_hwnd_by_title(window_title):

        def callback(hwnd, hwnd_list):
            if window_title.lower() in win32gui.GetWindowText(hwnd).lower():
                hwnd_list.append(hwnd)
            return True

        hwnd_list = []
        win32gui.EnumWindows(callback, hwnd_list)
        return hwnd_list[0] if hwnd_list else None

    def enumerate_child_windows(parent_hwnd):
        def callback(handle, windows):
            windows.append(handle)
            return True

        child_windows = []
        win32gui.EnumChildWindows(parent_hwnd, callback, child_windows)
        return child_windows

    def get_hwnd(window_title):
        hwnd = win32gui.FindWindow(None, window_title)
        handle_list = []
        if hwnd:
            handle_list.append(hwnd)
            handle_list.extend(enumerate_child_windows(hwnd))
            print(handle_list)
        return None

    hwnd = get_hwnd_by_title("BrownDust II")
    print(f"窗口句柄：{hwnd}")
    title = "BrownDust II"
    get_hwnd(title)
    i = Input(hwnd, logger)
    click_dict = {
        "安卡希雅·自律姬": [230, 895],
        "无标题 - 画图": [933, 594],
        "画图": [933, 594],
        "鸣潮": [1178, 477],
        "鸣潮  ": [1406, 40],
        "Wuthering Waves": [1178, 477],
        "西山居启动器-尘白禁区": [337, 559],
        "尘白禁区": [110, 463],
        "BrownDust II": [1441, 1336],
    }
    x_1 = click_dict[title][0]
    y_1 = click_dict[title][1]
    time.sleep(2)
