from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class OnDemandState:
    current_task_id: Optional[str] = None
    current_thread: Optional[object] = None


class OnDemandRunner:
    """Single-task execution strategy for non-periodic module host."""

    def __init__(self):
        self.state = OnDemandState()

    def toggle(
        self,
        task_id: str,
        *,
        is_global_running: bool,
        request_global_stop: Callable[[], None],
        get_module_class: Callable[[str], Optional[type]],
        get_logger: Callable[[str], object],
        build_thread: Callable[[type, object], object],
        on_thread_state_changed: Callable[[bool], None],
    ):
        if is_global_running:
            request_global_stop()
            return

        if self.state.current_task_id is not None:
            self.stop_current()
            return

        module_class = get_module_class(task_id)
        if module_class is None:
            return

        specific_logger = get_logger(task_id)
        thread = build_thread(module_class, specific_logger)
        thread.is_running.connect(on_thread_state_changed)
        thread.start()

        self.state.current_task_id = task_id
        self.state.current_thread = thread

    def stop_current(self):
        thread = self.state.current_thread
        if thread is not None and thread.isRunning():
            thread.stop()

    def clear(self):
        self.state.current_task_id = None
        self.state.current_thread = None
