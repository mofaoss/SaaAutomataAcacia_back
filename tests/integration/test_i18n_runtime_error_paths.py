from __future__ import annotations

import logging

from app.features.modules.event_tips.usecase.event_tips_usecase import format_event_status_display
from app.features.utils import network
from app.framework.core.observability.error_codes import AppErrorCode
from app.framework.core.observability.reporting import capture_exception
from app.framework.i18n import runtime


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _setup_logger() -> tuple[logging.Logger, _ListHandler]:
    logger = logging.getLogger("test.i18n.runtime.paths")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()
    handler = _ListHandler()
    logger.addHandler(handler)
    return logger, handler


def test_capture_exception_with_mixed_payload_never_raises(monkeypatch):
    monkeypatch.setattr(runtime, "_CATALOGS", {"en": {}, "zh_CN": {}, "zh_HK": {}})
    monkeypatch.setattr(runtime, "_LOADED", True)

    logger, handler = _setup_logger()
    error = RuntimeError("Cloudflare 错误: 1020")
    capture_exception(logger, error, AppErrorCode.TASK_EXECUTION_FAILED, context="global_exception_hook")

    assert handler.records
    rendered = runtime.render_message(handler.records[-1].msg, context="log", levelno=logging.ERROR)
    assert "Cloudflare" in rendered or "1020" in rendered


def test_network_cloudflare_error_path_never_raises(monkeypatch):
    monkeypatch.setattr(runtime, "_CATALOGS", {"en": {}, "zh_CN": {}, "zh_HK": {}})
    monkeypatch.setattr(runtime, "_LOADED", True)

    class Host:
        def __init__(self, logger):
            self.logger = logger

        def refresh_tips(self, url=None):
            return None

    logger, handler = _setup_logger()
    host = Host(logger)
    network.handle_cloudflare_error("Cloudflare blocked: 错误 1020", host)

    assert handler.records
    rendered = runtime.render_message(handler.records[-1].msg, context="log", levelno=logging.ERROR)
    assert "Cloudflare" in rendered


def test_external_status_normalization_outputs_localized_chinese(monkeypatch):
    monkeypatch.setattr(runtime, "_CATALOGS", {
        "en": {
            "module.event_tips.ui.event_status_remaining_days": "{days} days remaining",
            "module.event_tips.ui.event_status_display_with_title": "{title}: {status}",
            "module.event_tips.ui.event_status_finished": "Finished",
        },
        "zh_CN": {
            "module.event_tips.ui.event_status_remaining_days": "剩余 {days} 天",
            "module.event_tips.ui.event_status_display_with_title": "{title}：{status}",
            "module.event_tips.ui.event_status_finished": "已结束",
        },
        "zh_HK": {},
    })
    monkeypatch.setattr(runtime, "_LOADED", True)
    monkeypatch.setattr(runtime, "_resolve_lang", lambda: "zh_CN")

    value = format_event_status_display("多诺-巅峰对决", "3d(s) left")
    value2 = format_event_status_display("多诺-巅峰对决", "remaining 3 ds")
    finished = format_event_status_display("异星守护", "finished")
    assert value == "多诺-巅峰对决：剩余 3 天"
    assert value2 == "多诺-巅峰对决：剩余 3 天"
    assert finished == "异星守护：已结束"


def test_external_unparsed_status_bypasses_static_enforcement(monkeypatch):
    monkeypatch.setattr(runtime, "_TELEMETRY_SEEN", set())
    value = format_event_status_display("多诺-巅峰对决", "T-3")
    assert value == "多诺-巅峰对决：T-3"
