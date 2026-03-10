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
