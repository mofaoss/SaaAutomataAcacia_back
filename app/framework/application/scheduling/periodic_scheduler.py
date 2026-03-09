from datetime import datetime
from typing import Callable, Iterable


class PeriodicScheduler:
    """Application-level periodic dispatch policy for Daily host."""

    def __init__(self, logger, ui_text_fn: Callable[[str, str], str]):
        self.logger = logger
        self._ui_text = ui_text_fn

    def handle_due_tasks(
        self,
        new_tasks_found: Iterable[str],
        *,
        is_launch_pending: bool,
        is_self_running: bool,
        is_external_running: bool,
        queue_tasks: Callable[[list[str]], None],
        mark_task_queued: Callable[[str], None],
        mark_waiting_for_external_finish: Callable[[bool], None],
        run_now: Callable[[list[str]], None],
    ) -> None:
        task_ids = list(new_tasks_found or [])
        if not task_ids or is_launch_pending:
            return

        current_time_str = datetime.now().strftime("%H:%M")
        if is_self_running or is_external_running:
            self.logger.info(
                self._ui_text(
                    f"⏰ 到点触发计划: {current_time_str}，系统正忙，已加入队列排队: {task_ids}",
                    f"⏰ Scheduled task triggered at {current_time_str}, system is busy, added to queue: {task_ids}",
                )
            )
            queue_tasks(task_ids)
            for task_id in task_ids:
                mark_task_queued(task_id)

            if is_external_running and not is_self_running:
                mark_waiting_for_external_finish(True)
            return

        self.logger.info(
            self._ui_text(
                f"⏰ 到点触发计划: {current_time_str}，执行列表: {task_ids}",
                f"⏰ Scheduled task triggered at {current_time_str}, executing tasks: {task_ids}",
            )
        )
        run_now(task_ids)
