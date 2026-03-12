from __future__ import annotations

import logging

import pytest

from app.framework.i18n import runtime


@pytest.fixture(autouse=True)
def _isolated_catalogs(monkeypatch):
    catalogs = {"en": {}, "zh_CN": {}, "zh_HK": {}}
    monkeypatch.setattr(runtime, "_CATALOGS", catalogs)
    monkeypatch.setattr(runtime, "_LOADED", True)
    monkeypatch.setattr(runtime, "_TELEMETRY_SEEN", set())
    monkeypatch.setattr(runtime, "_TEMPLATE_META", {})
    monkeypatch.setattr(runtime, "_TEMPLATE_META_LOADED", True)
    monkeypatch.setattr(runtime, "_DYNAMIC_RECOVERY_KEYS", set())
    monkeypatch.setattr(runtime, "_DYNAMIC_KEYS_BY_OWNER_CONTEXT", {})
    monkeypatch.setattr(runtime, "_CATALOG_DYNAMIC_KEYS", set())
    monkeypatch.setattr(runtime, "_CATALOG_DYNAMIC_KEYS_BY_OWNER_CONTEXT", {})
    monkeypatch.setattr(runtime, "_CATALOG_DYNAMIC_INDEX_READY", False)
    monkeypatch.setattr(runtime, "_SOURCE_TEXT_KEY_BY_OWNER_CONTEXT", {})
    monkeypatch.setattr(runtime, "_SOURCE_TEXT_KEY_GLOBAL", {})
    monkeypatch.setattr(runtime, "_SOURCE_TEXT_INDEX_READY", False)
    monkeypatch.setattr(runtime, "_PAYLOAD_TEXT_TRANSLATION_CACHE", {})
    yield


def test_static_mixed_literal_does_not_raise_runtime_exception():
    msg = runtime._("Cloudflare 错误", __i18n_literal__=True)
    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "Cloudflare 错误"


def test_dynamic_template_renders_with_mixed_payload():
    key = "framework.ui.task_failed"
    runtime._CATALOGS["zh_CN"][key] = "任务 {task_name} 失败：{e}"

    msg = runtime._(
        "Task A failed: Cloudflare 错误 1020",
        __i18n_dynamic__=True,
        __i18n_template__="Task {task_name} failed: {e}",
        __i18n_fields__={"task_name": "任务A", "e": "Cloudflare 错误 1020"},
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="task_failed",
    )

    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "任务 任务A 失败：Cloudflare 错误 1020"


def test_dynamic_template_preserves_format_spec_and_conversion():
    key = "framework.ui.client_size"
    runtime._CATALOGS["zh_CN"][key] = "客户端尺寸：{client_width}x{client_height}（{actual_ratio:.3f}:1）状态={status!r}"

    msg = runtime._(
        "Client area size: 1920x1080 (1.778:1), 'ok'",
        __i18n_dynamic__=True,
        __i18n_template__="Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status!r}",
        __i18n_fields__={
            "client_width": 1920,
            "client_height": 1080,
            "actual_ratio": 1.7777777,
            "status": "ok",
        },
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="client_size",
    )

    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "客户端尺寸：1920x1080（1.778:1）状态='ok'"


def test_dynamic_field_mismatch_falls_back_to_original_rendered_text_without_skeleton():
    key = "framework.ui.task_failed"
    runtime._CATALOGS["zh_CN"][key] = "任务失败：{task_name}"

    msg = runtime._(
        "Task A failed: network timeout",
        __i18n_dynamic__=True,
        __i18n_template__="Task {task_name} failed: {e}",
        __i18n_fields__={"task_name": "A", "e": "network timeout"},
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="task_failed",
    )

    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "Task A failed: network timeout"
    assert "{task_name}" not in rendered
    assert "{e}" not in rendered


def test_dynamic_format_spec_mismatch_falls_back_to_original_rendered_text():
    key = "framework.ui.client_size_mismatch"
    runtime._CATALOGS["zh_CN"][key] = "客户端尺寸：{client_width}x{client_height}（{actual_ratio}:1）"

    msg = runtime._(
        "Client area size: 1920x1080 (1.778:1)",
        __i18n_dynamic__=True,
        __i18n_template__="Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1)",
        __i18n_fields__={
            "client_width": 1920,
            "client_height": 1080,
            "actual_ratio": 1.7777777,
        },
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="client_size_mismatch",
    )

    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "Client area size: 1920x1080 (1.778:1)"
    assert "{actual_ratio" not in rendered


def test_dynamic_double_render_failure_falls_back_to_original_rendered_text():
    key = "framework.ui.window_handle"
    runtime._CATALOGS["zh_CN"][key] = "Found handle for window {self_window_title}: {hwnd}"

    msg = runtime._(
        "Found handle for window Main Window: 1234",
        __i18n_dynamic__=True,
        __i18n_template__="Found handle for window {self_window_title}: {hwnd}",
        __i18n_fields__={"self_window_title": "Main Window"},
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="window_handle",
    )

    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "Found handle for window Main Window: 1234"
    assert "{self_window_title}" not in rendered
    assert "{hwnd}" not in rendered


def test_dynamic_candidate_without_metadata_skips_static_enforcement():
    msg = runtime._(
        "多诺-巅峰对决: 3d(s) left",
        __i18n_dynamic_candidate__=True,
        __i18n_callsite_kind__="dynamic_candidate",
    )
    rendered = runtime.render_message(msg, context="ui")
    assert rendered == "多诺-巅峰对决: 3d(s) left"


def test_dynamic_recovery_without_template_meta_uses_catalog_templates():
    runtime._CATALOGS["en"]["framework.log.task_queue_resolved"] = "Task queue resolved: {count} tasks"
    runtime._CATALOGS["zh_CN"]["framework.log.task_queue_resolved"] = "任务队列已解析：{count} 个任务"
    runtime._CATALOGS["en"]["framework.log.client_area_size"] = (
        "Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status}"
    )
    runtime._CATALOGS["zh_CN"]["framework.log.client_area_size"] = (
        "客户区尺寸：{client_width}x{client_height}（{actual_ratio:.3f}:1），{status}"
    )
    runtime._CATALOG_DYNAMIC_INDEX_READY = False
    runtime._resolve_lang = lambda: "zh_CN"  # type: ignore[assignment]

    without_msgid = runtime._(
        "Task queue resolved: 12 tasks",
        __i18n_owner_scope__="framework",
        __i18n_context_hint__="log",
    )
    rendered_without_msgid = runtime.render_message(without_msgid, context="log", levelno=logging.INFO)
    assert rendered_without_msgid == "任务队列已解析：12 个任务"

    explicit_msgid = runtime._(
        "Client area size: 1920x1080 (1.778:1), Meets 16:9 standard ratio",
        msgid="client_area_size",
        __i18n_owner_scope__="framework",
        __i18n_context_hint__="log",
    )
    rendered_explicit_msgid = runtime.render_message(explicit_msgid, context="log", levelno=logging.WARNING)
    assert rendered_explicit_msgid == "客户区尺寸：1920x1080（1.778:1），Meets 16:9 standard ratio"

def test_dynamic_payload_value_is_auto_localized_when_catalog_has_mapping():
    runtime._CATALOGS["en"]["framework.log.client_area_size"] = (
        "Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status}"
    )
    runtime._CATALOGS["zh_CN"]["framework.log.client_area_size"] = (
        "客户区尺寸：{client_width}x{client_height}（{actual_ratio:.3f}:1），{status}"
    )
    runtime._CATALOGS["en"]["framework.log.meets_16_9_standard_ratio"] = "Meets 16:9 standard ratio"
    runtime._CATALOGS["zh_CN"]["framework.log.meets_16_9_standard_ratio"] = "符合 16:9 标准比例"
    runtime._CATALOG_DYNAMIC_INDEX_READY = False
    runtime._SOURCE_TEXT_INDEX_READY = False
    runtime._resolve_lang = lambda: "zh_CN"  # type: ignore[assignment]

    explicit_msgid = runtime._(
        "Client area size: 1920x1080 (1.778:1), Meets 16:9 standard ratio",
        msgid="client_area_size",
        __i18n_owner_scope__="framework",
        __i18n_context_hint__="log",
    )
    rendered = runtime.render_message(explicit_msgid, context="log", levelno=logging.WARNING)
    assert rendered == "客户区尺寸：1920x1080（1.778:1），符合 16:9 标准比例"


def test_log_context_can_render_from_translatable_string_payload():
    runtime._CATALOGS["en"]["framework.log.task_queue_resolved"] = "Task queue resolved: {tasks}"
    runtime._CATALOGS["zh_CN"]["framework.log.task_queue_resolved"] = "任务队列已解析：{tasks}"
    runtime._resolve_lang = lambda: "zh_CN"  # type: ignore[assignment]

    msg = runtime._(
        "Task queue resolved: {tasks}",
        msgid="task_queue_resolved",
        __i18n_owner_scope__="framework",
        __i18n_context_hint__="log",
        tasks="自动登录, 精神拟境",
    )

    # Public API should still behave as str while retaining metadata.
    assert isinstance(msg, str)
    rendered = runtime.render_message(msg, context="log", levelno=logging.INFO)
    assert rendered == "任务队列已解析：自动登录, 精神拟境"


def test_owner_inference_prefers_module_name_when_filename_is_not_path():
    class _Code:
        co_filename = "<frozen app.features.modules.fishing.usecase.fishing_usecase>"

    class _Frame:
        f_code = _Code()
        f_globals = {"__name__": "app.features.modules.fishing.usecase.fishing_usecase"}

    owner_scope, owner_module = runtime._infer_owner_from_frame(_Frame())
    assert owner_scope == "module"
    assert owner_module == "fishing"


def test_render_message_never_raises_on_bad_stringify():
    class BadValue:
        def __str__(self):
            raise RuntimeError("boom")

        def __repr__(self):
            return "<BadValue>"

    msg = runtime._(
        "Task A failed: <BadValue>",
        __i18n_dynamic__=True,
        __i18n_template__="Task {task_name} failed: {e}",
        __i18n_fields__={"task_name": "A", "e": BadValue()},
        __i18n_owner_scope__="framework",
        __i18n_callsite_kind__="dynamic_template",
        msgid="task_failed_2",
    )
    rendered = runtime.render_message(msg, context="ui")
    assert isinstance(rendered, str)
    assert rendered


