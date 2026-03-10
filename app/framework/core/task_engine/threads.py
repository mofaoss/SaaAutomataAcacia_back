# coding:utf-8
import inspect
import sys
import types
from typing import Callable

from PySide6.QtCore import QThread, Signal

from app.framework.infra.config.app_config import config, is_non_chinese_ui_language
from app.framework.core.task_engine.runtime_session import RuntimeAutomationSession
from app.framework.i18n import _


class TaskQueueThread(QThread):
    """Run a queue of task modules with a shared automation session."""

    is_running_signal = Signal(str)
    stop_signal = Signal()
    task_completed_signal = Signal(str)
    task_started_signal = Signal(str)
    task_failed_signal = Signal(str)
    show_tray_message_signal = Signal(str, str)

    def __init__(
        self,
        tasks_to_run: list,
        logger_instance,
        task_registry: dict,
        *,
        home_sync: Callable[[object, object], bool] | None = None,
        runtime_config=None,
        parent=None,
    ):
        super().__init__(parent)
        self.tasks_to_run = tasks_to_run
        self.logger = logger_instance
        self.task_registry = task_registry
        self.home_sync = home_sync or (lambda _auto, _logger: True)
        self.runtime_config = runtime_config or config
        self.session = RuntimeAutomationSession(self.logger)
        self._is_running = True
        self._interrupted_reason = None

    def stop(self, reason=None):
        self._is_running = False
        if reason:
            self._interrupted_reason = reason
            self.logger.warning(
                _(f'Interrupt detected, stopping automatic task: {reason}', msgid='054ac2160959')
            )
        if self.session.auto is not None:
            try:
                self.session.stop()
            except Exception as e:
                self.logger.warning(
                    _(f'Exception occurred while stopping automatic task, ignored: {e}', msgid='23dc6ab8ded3')
                )

    @staticmethod
    def _bind_runtime_config_to_module(module_class: type, runtime_config):
        module_name = getattr(module_class, "__module__", "")
        module_obj = sys.modules.get(module_name)
        if isinstance(module_obj, types.ModuleType):
            setattr(module_obj, "config", runtime_config)

    @staticmethod
    def _instantiate_module(module_class: type, auto, logger, runtime_config):
        TaskQueueThread._bind_runtime_config_to_module(module_class, runtime_config)
        try:
            return module_class(**TaskQueueThread._build_ctor_kwargs(module_class, auto, logger, runtime_config))
        except Exception:
            pass
        return module_class(auto, logger)

    @staticmethod
    def _read_config_value(runtime_config, key: str):
        if runtime_config is None or not hasattr(runtime_config, key):
            return None
        raw = getattr(runtime_config, key)
        return getattr(raw, "value", raw)

    @staticmethod
    def _build_ctor_kwargs(module_class: type, auto, logger, runtime_config) -> dict:
        sig = inspect.signature(module_class)
        kwargs = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if name in {"auto", "automation"}:
                kwargs[name] = auto
                continue
            if name == "logger":
                kwargs[name] = logger
                continue
            if name in {"config_provider", "app_config"}:
                kwargs[name] = runtime_config
                continue

            cfg_value = TaskQueueThread._read_config_value(runtime_config, name)
            if cfg_value is not None:
                kwargs[name] = cfg_value
                continue
            if param.default is not inspect._empty:
                kwargs[name] = param.default
                continue
            kwargs[name] = None
        return kwargs

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
                self.logger.info(_(f'Current task: {task_name}', msgid='550b7c49b8ff'))
                self.task_started_signal.emit(task_id)

                task_success = True
                requires_home_sync = bool(meta.get("requires_home_sync", True))
                if requires_home_sync:
                    self.logger.info(
                        _(f'Preparing {task_name}, returning to home...', msgid='8cee80e84fc8')
                    )
                    if not self.home_sync(auto, self.logger):
                        self.logger.error(
                            _(f'[{task_name}] Failed to return to home before start, skipping.', msgid='40df1ad8f76d')
                        )
                        task_success = False

                if task_success:
                    module_class = meta["module_class"]
                    module = self._instantiate_module(module_class, auto, self.logger, self.runtime_config)
                    module.run()

                    if requires_home_sync and self._is_running:
                        msg = _(f'{task_name} finished, returning to home...', msgid='c87b23e00aba')
                        self.logger.info(msg)
                        self.home_sync(auto, self.logger)

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
            elif self._interrupted_reason:
                self.is_running_signal.emit("interrupted")
            else:
                self.is_running_signal.emit("no_auto")


class ModuleTaskThread(QThread):
    """Run one module class in its own thread with a dedicated session."""

    is_running = Signal(bool)

    def __init__(self, module, logger_instance, runtime_config=None):
        super().__init__()
        self.logger = logger_instance
        self.runtime_config = runtime_config or config
        self.session = RuntimeAutomationSession(self.logger)
        self.module = None
        self._prepare_module(module)

    def _prepare_module(self, module):
        if not self.session.prepare():
            return
        TaskQueueThread._bind_runtime_config_to_module(module, self.runtime_config)
        try:
            kwargs = TaskQueueThread._build_ctor_kwargs(module, self.session.auto, self.logger, self.runtime_config)
            self.module = module(**kwargs)
            return
        except Exception:
            pass
        self.module = module(self.session.auto, self.logger)

    def stop(self):
        try:
            self.session.stop()
        except Exception as e:
            self.logger.warning(_(f'Exception occurred while stopping sub task, ignored: {e}', msgid='4261c14a6166'))

    def run(self):
        if self.module is None or self.session.auto is None:
            self.is_running.emit(False)
            return

        self.is_running.emit(True)
        try:
            self.module.run()
        except Exception as e:
            self.session.stop_ocr()
            self.logger.warning(f"SubTask：{e}")
        finally:
            try:
                self.session.stop()
            except Exception as stop_error:
                self.logger.warning(f"SubTask结束时恢复窗口位置失败：{stop_error}")
            self.is_running.emit(False)
