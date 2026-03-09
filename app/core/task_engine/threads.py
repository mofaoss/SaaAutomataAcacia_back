# coding:utf-8
import sys

from PySide6.QtCore import QThread, Signal

from app.infrastructure.config.app_config import config, is_non_chinese_ui_language
from app.core.task_engine.runtime_session import RuntimeAutomationSession
from app.utils.ui import ui_text


class TaskQueueThread(QThread):
    """Run a queue of task modules with a shared automation session."""

    is_running_signal = Signal(str)
    stop_signal = Signal()
    task_completed_signal = Signal(str)
    task_started_signal = Signal(str)
    task_failed_signal = Signal(str)
    show_tray_message_signal = Signal(str, str)

    def __init__(self, tasks_to_run: list, logger_instance, task_registry: dict, parent=None):
        super().__init__(parent)
        self.tasks_to_run = tasks_to_run
        self.logger = logger_instance
        self.task_registry = task_registry
        self.session = RuntimeAutomationSession(self.logger)
        self._is_running = True
        self._interrupted_reason = None

    def stop(self, reason=None):
        self._is_running = False
        if reason:
            self._interrupted_reason = reason
            self.logger.warning(ui_text(f"检测到中断，停止自动任务：{reason}", f"Interrupt detected, stopping automatic task: {reason}"))
        if self.session.auto is not None:
            try:
                self.session.stop()
            except Exception as e:
                self.logger.warning(ui_text(f"停止自动任务时发生异常，已忽略：{e}", f"Exception occurred while stopping automatic task, ignored: {e}"))

    def run(self):
        self.is_running_signal.emit("start")
        normal_stop_flag = True
        try:
            if self.tasks_to_run and not self.session.prepare():
                normal_stop_flag = False
                return

            auto = self.session.auto
            for task_id in self.tasks_to_run:
                if not self._is_running:
                    normal_stop_flag = False
                    break

                meta = self.task_registry.get(task_id)
                if not meta:
                    continue

                task_name = meta["en_name"] if is_non_chinese_ui_language() else meta["zh_name"]
                self.logger.info(ui_text(f"当前任务：{task_name}", f"Current task: {task_name}"))
                self.task_started_signal.emit(task_id)

                task_success = True
                requires_home_sync = bool(meta.get("requires_home_sync", True))
                if requires_home_sync:
                    self.logger.info(ui_text(f"正在准备 {task_name}，尝试返回主界面...", f"Preparing {task_name}, returning to home..."))
                    if not auto.back_to_home():
                        self.logger.error(ui_text(f"[{task_name}] 开始前返回主界面失败，跳过该任务", f"[{task_name}] Failed to return to home before start, skipping."))
                        task_success = False

                if task_success:
                    module_class = meta["module_class"]
                    module = module_class(auto, self.logger)
                    module.run()

                    if requires_home_sync and self._is_running:
                        msg = ui_text(f"{task_name} 执行完毕，正在返回主界面...", f"{task_name} finished, returning to home...")
                        self.logger.info(msg)
                        auto.back_to_home()

                if self._is_running:
                    if task_success:
                        self.task_completed_signal.emit(task_id)
                    else:
                        self.task_failed_signal.emit(task_id)

                if not self._is_running:
                    normal_stop_flag = False
                    break

                if config.inform_message.value or "--toast-only" in sys.argv:
                    full_time = auto.calculate_power_time() if auto is not None else None
                    content = f"体力将在 {full_time} 完全恢复" if full_time else "体力计算出错"
                    self.show_tray_message_signal.emit("已完成勾选任务", content)

        except Exception as e:
            if str(e) != "已停止":
                self.logger.warning(e)
        finally:
            if self.session.auto is not None:
                self.session.stop()
            if normal_stop_flag and self._is_running:
                self.is_running_signal.emit("end")
            else:
                if self._interrupted_reason:
                    self.is_running_signal.emit("interrupted")
                else:
                    self.is_running_signal.emit("no_auto")


class ModuleTaskThread(QThread):
    """Run one module class in its own thread with a dedicated session."""

    is_running = Signal(bool)

    def __init__(self, module, logger_instance):
        super().__init__()
        self.logger = logger_instance
        self.session = RuntimeAutomationSession(self.logger)
        self.module = None
        self._prepare_module(module)

    def _prepare_module(self, module):
        if not self.session.prepare():
            return
        self.module = module(self.session.auto, self.logger)

    def stop(self):
        try:
            self.session.stop()
        except Exception as e:
            self.logger.warning(ui_text(f"停止子任务时发生异常，已忽略：{e}", f"Exception occurred while stopping sub task, ignored: {e}"))

    def run(self):
        if self.module is None or self.session.auto is None:
            self.is_running.emit(False)
            return

        self.is_running.emit(True)
        try:
            self.module.run()
        except Exception as e:
            from app.modules.ocr import ocr
            ocr.stop_ocr()
            self.logger.warning(f"SubTask：{e}")
        finally:
            try:
                self.session.stop()
            except Exception as stop_error:
                self.logger.warning(f"SubTask结束时恢复窗口位置失败：{stop_error}")
            self.is_running.emit(False)



