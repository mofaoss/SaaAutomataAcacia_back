# coding:utf-8
from __future__ import annotations

import ctypes
from typing import Callable


class GlobalHotkeyPoller:
    """Edge-triggered global hotkey poller based on Win32 GetAsyncKeyState."""

    def __init__(self, vk_code: int, on_pressed: Callable[[], None]):
        self.vk_code = int(vk_code)
        self.on_pressed = on_pressed
        self._pressed = False

    def poll(self) -> None:
        state = ctypes.windll.user32.GetAsyncKeyState(self.vk_code)
        is_pressed = (state & 0x8000) != 0

        if is_pressed and not self._pressed:
            self._pressed = True
            self.on_pressed()
            return

        if not is_pressed:
            self._pressed = False

