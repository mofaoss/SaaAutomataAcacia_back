# coding:utf-8
from app.modules.base_task.base_task import BaseTask


class RuntimeAutomationSession:
    """Shared runtime session for task execution threads."""

    def __init__(self, logger_instance):
        self.logger = logger_instance
        self._task_context = BaseTask()
        self._task_context.logger = self.logger

        from app.modules.ocr import ocr
        ocr.logger = self.logger

    @property
    def auto(self):
        return self._task_context.auto

    def prepare(self):
        ok = self._task_context.init_auto("game")
        if not ok:
            return False
        if self.auto is not None:
            self.auto.reset()
        return True

    def stop(self):
        if self.auto is None:
            return
        self.auto.stop()

