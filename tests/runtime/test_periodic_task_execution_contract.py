from __future__ import annotations

from app.framework.core.task_engine.threads import TaskExecutionResult, TaskQueueThread


class _DummyLogger:
    def __init__(self):
        self.debug_logs: list[str] = []

    def debug(self, msg, *args):
        self.debug_logs.append(msg % args if args else str(msg))

    def info(self, msg, *args):
        pass

    def warning(self, msg, *args):
        pass

    def error(self, msg, *args):
        pass


def _build_thread(logger: _DummyLogger) -> TaskQueueThread:
    return TaskQueueThread(
        tasks_to_run=[],
        logger_instance=logger,
        task_registry={},
    )


def test_normalize_none_result_without_unpack_failure():
    logger = _DummyLogger()
    thread = _build_thread(logger)
    result = thread._normalize_task_result("task_login", "Auto Login", None)
    assert isinstance(result, TaskExecutionResult)
    assert result.ok is True
    assert any("periodic_event=task_execution_return_none" in item for item in logger.debug_logs)
    assert any("periodic_event=task_execution_unpacked_guarded" in item for item in logger.debug_logs)


def test_normalize_bool_result():
    logger = _DummyLogger()
    thread = _build_thread(logger)
    result = thread._normalize_task_result("task_logout", "Logout", False)
    assert result.ok is False


def test_normalize_tuple_result():
    logger = _DummyLogger()
    thread = _build_thread(logger)
    result = thread._normalize_task_result("task_normal", "Collect Supplies", (True, "ok"))
    assert result.ok is True
    assert result.message == "ok"


def test_execute_module_task_exception_returns_structured_failure():
    logger = _DummyLogger()
    thread = _build_thread(logger)

    class BrokenModule:
        def run(self):
            raise RuntimeError("boom")

    result = thread._execute_module_task("task_normal", "Collect Supplies", BrokenModule())
    assert result.ok is False
    assert isinstance(result.error, RuntimeError)
    assert any("periodic_event=task_execution_result_invalid" in item for item in logger.debug_logs)

