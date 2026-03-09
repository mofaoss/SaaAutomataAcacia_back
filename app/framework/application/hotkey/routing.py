# coding:utf-8
from __future__ import annotations

from enum import Enum


class HotkeyAction(str, Enum):
    NOOP = "noop"
    REQUEST_STOP = "request_stop"
    START_DAILY = "start_daily"
    START_ADDITIONAL = "start_additional"


def resolve_f8_action(global_is_running: bool, context: str) -> HotkeyAction:
    if global_is_running:
        return HotkeyAction.REQUEST_STOP
    if context == "home":
        return HotkeyAction.START_DAILY
    if context == "additional":
        return HotkeyAction.START_ADDITIONAL
    return HotkeyAction.NOOP

