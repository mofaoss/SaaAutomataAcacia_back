# coding:utf-8
import inspect
import sys
import types
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QThread, Signal

from app.framework.infra.config.app_config import config, is_non_chinese_ui_language
from app.framework.core.task_engine.runtime_session import RuntimeAutomationSession
from app.framework.i18n import _


@dataclass(slots=True)
class TaskExecutionResult:
    ok: bool
    skipped: bool = False
    message: str = ""
    detail: str = ""
    error: Exception | None = None


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
                _(f'Interrupt detected, stopping automatic task: {reason}', msgid='interrupt_detected_stopping_automatic_task_reaso')
            )
        if self.session.auto is not None:
            try:
                self.session.stop()
            except Exception as e:
                self.logger.warning(
                    _(f'Exception occurred while stopping automatic task, ignored: {e}', msgid='exception_occurred_while_stopping_automatic_task')
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

    def _telemetry_periodic(self, event: str, task_id: str, task_name: str, detail: str = "") -> None:
        try:
            self.logger.debug(
                "periodic_event=%s task_id=%s task_name=%s detail=%s",
                event,
                task_id,
                task_name,
                detail,
            )
        except Exception:
            pass

    def _normalize_task_result(
        self,
        task_id: str,
        task_name: str,
        raw_result,
    ) -> TaskExecutionResult:
        return_type = type(raw_result).__name__
        preview = repr(raw_result)
        if len(preview) > 180:
            preview = preview[:177] + "..."

        self._telemetry_periodic(
            "task_execution_return_observed",
            task_id,
            task_name,
            f"type={return_type} value={preview}",
        )

        if raw_result is None:
            self._telemetry_periodic("task_execution_return_none", task_id, task_name, "legacy_none_return")
            self._telemetry_periodic("task_execution_unpacked_guarded", task_id, task_name, "legacy_none_return")
            self._telemetry_periodic("task_execution_result_normalized", task_id, task_name, "none=>ok")
            return TaskExecutionResult(ok=True, message="legacy_none_return")

        if isinstance(raw_result, TaskExecutionResult):
            return raw_result

        if isinstance(raw_result, bool):
            self._telemetry_periodic("task_execution_result_normalized", task_id, task_name, f"bool=>ok:{raw_result}")
            return TaskExecutionResult(ok=bool(raw_result))

        if isinstance(raw_result, dict):
            ok = bool(raw_result.get("ok", True))
            skipped = bool(raw_result.get("skipped", False))
            message = str(raw_result.get("message", "") or "")
            detail = str(raw_result.get("detail", "") or "")
            error_obj = raw_result.get("error")
            error = error_obj if isinstance(error_obj, Exception) else None
            self._telemetry_periodic("task_execution_result_normalized", task_id, task_name, "dict=>TaskExecutionResult")
            return TaskExecutionResult(ok=ok, skipped=skipped, message=message, detail=detail, error=error)

        if isinstance(raw_result, (tuple, list)):
            if len(raw_result) == 0:
                self._telemetry_periodic("task_execution_result_invalid", task_id, task_name, "empty_tuple_or_list")
                self._telemetry_periodic("task_execution_unpacked_guarded", task_id, task_name, "empty_tuple_or_list")
                return TaskExecutionResult(ok=False, detail="empty_tuple_or_list")
            first = raw_result[0]
            if isinstance(first, bool):
                message = str(raw_result[1]) if len(raw_result) > 1 else ""
                self._telemetry_periodic("task_execution_result_normalized", task_id, task_name, "tuple/list=>TaskExecutionResult")
                return TaskExecutionResult(ok=first, message=message, detail=preview)
            self._telemetry_periodic("task_execution_result_invalid", task_id, task_name, "tuple/list first item is not bool")
            self._telemetry_periodic("task_execution_unpacked_guarded", task_id, task_name, "tuple/list first item is not bool")
            return TaskExecutionResult(ok=False, detail=preview)

        self._telemetry_periodic("task_execution_result_normalized", task_id, task_name, f"default=>ok ({return_type})")
        return TaskExecutionResult(ok=True, detail=preview)

    def _execute_module_task(self, task_id: str, task_name: str, module) -> TaskExecutionResult:
        try:
            raw_result = module.run()
            return self._normalize_task_result(task_id, task_name, raw_result)
        except Exception as exc:
            self._telemetry_periodic("task_execution_result_invalid", task_id, task_name, f"exception={exc!r}")
            return TaskExecutionResult(ok=False, message="exception", detail=str(exc), error=exc)

    def run(self):
        self.is_running_signal.emit("start")
        normal_stop_flag = True
        try:
            if not self.tasks_to_run:
                self.logger.warning(_('No tasks queued; skipping execution', msgid='no_tasks_queued_skipping_execution'))
                normal_stop_flag = False
                return

            if not self.session.prepare():
                self.logger.error(_('Runtime automation session initialization failed; tasks skipped', msgid='runtime_automation_session_initialization_failed'))
                normal_stop_flag = False
                return

            auto = self.session.auto
            queue_names = []
            for queued_task_id in self.tasks_to_run:
                queued_meta = self.task_registry.get(queued_task_id, {})
                queued_name = queued_meta.get('en_name', queued_task_id) if is_non_chinese_ui_language() else queued_meta.get('zh_name', queued_task_id)
                queue_names.append(queued_name)
            self.logger.info(
                _("Task queue resolved: {tasks}", msgid='task_queue_resolved', tasks=', '.join(queue_names))
            )

            for task_id in self.tasks_to_run:
                if not self._is_running:
                    normal_stop_flag = False
                    self.logger.warning(_('Execution interrupted before task start', msgid='execution_interrupted_before_task_start'))
                    break

                meta = self.task_registry.get(task_id)
                if not meta:
                    self.logger.warning(
                        _("Skipping task '{task_id}': metadata not found", msgid='skipping_task_metadata_not_found', task_id=task_id)
                    )
                    continue

                task_name = meta['en_name'] if is_non_chinese_ui_language() else meta['zh_name']
                self.logger.info(_("Current task: {task_name}", msgid='current_task_task_name', task_name=task_name))
                self.task_started_signal.emit(task_id)

                task_success = True
                requires_home_sync = bool(meta.get('requires_home_sync', True))
                if requires_home_sync:
                    self.logger.info(
                        _('Preparing {task_name}, returning to home...', msgid='preparing_task_name_returning_to_home', task_name=task_name)
                    )
                    if not self.home_sync(auto, self.logger):
                        self.logger.error(
                            _('[{task_name}] Failed to return to home before start, skipping.', msgid='task_name_failed_to_return_to_home_before_start', task_name=task_name)
                        )
                        self.logger.warning(
                            _('Task skipped: {task_name}, reason=home_sync_failed', msgid='task_skipped_home_sync_failed', task_name=task_name)
                        )
                        task_success = False

                if task_success:
                    module_class = meta['module_class']
                    module = self._instantiate_module(module_class, auto, self.logger, self.runtime_config)
                    execution_result = self._execute_module_task(task_id, task_name, module)
                    if execution_result.skipped:
                        task_success = False
                        self.logger.warning(
                            _(
                                "Task skipped: {task_name}, reason={reason}",
                                msgid="task_skipped_reason",
                                task_name=task_name,
                                reason=execution_result.message or execution_result.detail or "unknown",
                            )
                        )
                    elif not execution_result.ok:
                        task_success = False
                        err_text = execution_result.detail or execution_result.message or (
                            str(execution_result.error) if execution_result.error else ""
                        )
                        self.logger.error(
                            _(
                                "Task failed: {task_name}, reason={reason}",
                                msgid="task_failed_reason",
                                task_name=task_name,
                                reason=err_text or "unknown",
                            )
                        )

                    if requires_home_sync and self._is_running:
                        msg = _('{task_name} finished, returning to home...', msgid='task_name_finished_returning_to_home', task_name=task_name)
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

                if config.inform_message.value or '--toast-only' in sys.argv:
                    try:
                        full_time = auto.calculate_power_time() if auto is not None else None
                        content = f'体力将在 {full_time} 完全恢复' if full_time else '体力计算出错'
                        self.show_tray_message_signal.emit('已完成勾选任务', content)
                    except Exception as tray_error:
                        self._telemetry_periodic("task_execution_result_invalid", task_id, task_name, f"tray_notify_error={tray_error!r}")
                        self.logger.warning(
                            _(
                                "Non-critical tray message update failed: {error}",
                                msgid="non_critical_tray_message_update_failed",
                                error=str(tray_error),
                            )
                        )

        except Exception as e:
            if str(e) != '已停止':
                self.logger.exception(
                    _("Unhandled queue runtime exception: {error}", msgid="unhandled_queue_runtime_exception", error=str(e))
                )
        finally:
            if self.session.auto is not None:
                self.session.stop()
            if normal_stop_flag and self._is_running:
                self.is_running_signal.emit('end')
            elif self._interrupted_reason:
                self.is_running_signal.emit('interrupted')
            else:
                self.is_running_signal.emit('no_auto')


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
            self.logger.warning(_(f'Exception occurred while stopping sub task, ignored: {e}', msgid='exception_occurred_while_stopping_sub_task_ignor'))

    def run(self):
        if self.module is None or self.session.auto is None:
            self.is_running.emit(False)
            return

        self.is_running.emit(True)
        try:
            self.module.run()
        except Exception as e:
            self.session.stop_ocr()
            self.logger.warning(_(f"SubTask：{e}"))
        finally:
            try:
                self.session.stop()
            except Exception as stop_error:
                self.logger.warning(_(f"SubTask结束时恢复窗口位置失败：{stop_error}"))
            self.is_running.emit(False)
