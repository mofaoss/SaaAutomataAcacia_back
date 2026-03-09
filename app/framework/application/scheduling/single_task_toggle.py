from __future__ import annotations

from typing import Callable


class SingleTaskToggle:
    """Reusable intent router for single-task start/stop behavior."""

    def toggle(
        self,
        task_id: str,
        *,
        is_global_running: bool,
        request_global_stop: Callable[[], None],
        is_local_running: bool,
        stop_local: Callable[[], None],
        start_local: Callable[[str], None],
    ) -> str:
        if is_global_running:
            request_global_stop()
            return "global_stop_requested"

        if is_local_running:
            stop_local()
            return "local_stop_requested"

        start_local(task_id)
        return "started"
