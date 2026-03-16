from datetime import datetime
from typing import Callable, Iterable
from app.framework.i18n import _


class PeriodicDispatcher:
    """Application-level periodic dispatch policy for Daily host."""

    def __init__(self, logger):
        self.logger = logger

    def handle_due_tasks(
        self,
        new_tasks_found: Iterable[str],
        *,
        is_launch_pending: bool,
        is_self_running: bool,
        is_external_running: bool,
        cleanup_enabled: bool,
        queue_tasks: Callable[[list[str]], None],
        mark_task_queued: Callable[[str], None],
        mark_waiting_for_external_finish: Callable[[bool], None],
        run_now: Callable[[list[str]], None],
    ) -> None:
        task_ids = list(new_tasks_found or [])
        if not task_ids or is_launch_pending:
            return

        current_time_str = datetime.now().strftime("%H:%M")

        # 核心逻辑：由于注入逻辑已经下沉到 Controller 的 build_run_plan 中，
        # 此处 Dispatcher 仅负责根据当前运行状态分发策略：是直接运行还是入队排队。

        if is_self_running or is_external_running:
            # 记录即将入队的原始触发任务（注入将在最终执行前由 Controller 处理）
            self.logger.info(
                _(f'⏰ Scheduled task triggered at {current_time_str}, system is busy, added to queue: {task_ids}')
            )
            queue_tasks(task_ids)
            for task_id in task_ids:
                mark_task_queued(task_id)

            if is_external_running and not is_self_running:
                mark_waiting_for_external_finish(True)
            return

        self.logger.info(
            _(f'⏰ Scheduled task triggered at {current_time_str}, executing tasks: {task_ids}')
        )
        run_now(task_ids)
