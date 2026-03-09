# coding:utf-8
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class GlobalTaskState:
    is_running: bool
    zh_name: str
    en_name: str
    source: str


class GlobalTaskBus(QObject):
    """Cross-page task state and stop-request event bus."""

    state_changed = Signal(bool, str, str, str)
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self._state = GlobalTaskState(False, "", "", "")

    @property
    def state(self) -> GlobalTaskState:
        return self._state

    def publish_state(self, is_running: bool, zh_name: str, en_name: str, source: str):
        self._state = GlobalTaskState(bool(is_running), zh_name, en_name, source)
        self.state_changed.emit(self._state.is_running, self._state.zh_name, self._state.en_name, self._state.source)

    def request_stop(self):
        self.stop_requested.emit()


global_task_bus = GlobalTaskBus()

