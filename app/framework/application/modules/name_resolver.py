from __future__ import annotations

from typing import Any, Mapping

from app.framework.core.module_system.naming import humanize_name
from app.framework.i18n import tr
from app.framework.i18n.runtime import _resolve_lang, classify_source_language


def _fallback_title(entity_id: str) -> str:
    normalized = str(entity_id or "").strip()
    if normalized.startswith("task_"):
        normalized = normalized[len("task_") :]
    readable = humanize_name(normalized)
    return readable or str(entity_id or "")


def _safe_source_lang(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    try:
        return classify_source_language(raw)
    except Exception:
        return ""


def _same_language_bucket(current_lang: str, source_lang: str) -> bool:
    current = str(current_lang or "").strip()
    source = str(source_lang or "").strip()
    if not current or not source:
        return False
    if source == "zh_CN":
        return current in {"zh_CN", "zh_HK"}
    return current == source


def resolve_display_name(*, name: str, name_msgid: str, fallback_id: str) -> str:
    declared_name = str(name or "").strip()
    base_name = declared_name or _fallback_title(fallback_id)
    key = str(name_msgid or "").strip()
    if key:
        current_lang = _resolve_lang()
        source_lang = _safe_source_lang(declared_name)
        same_lang = _same_language_bucket(current_lang, source_lang)

        # Source-language UI should immediately reflect declaration changes,
        # even before i18n extraction/sync updates stale JSON entries.
        if declared_name and same_lang:
            return declared_name

        fallback = base_name if same_lang else _fallback_title(fallback_id)
        return tr(key, fallback=fallback)
    return base_name


def resolve_task_display_name(meta: Mapping[str, Any] | None, task_id: str) -> str:
    payload = meta or {}
    return resolve_display_name(
        name=str(payload.get("name", "") or ""),
        name_msgid=str(payload.get("name_msgid", "") or ""),
        fallback_id=task_id,
    )


def resolve_state_display_name(task_name: str, task_name_msgid: str, source: str = "") -> str:
    fallback = str(task_name or "").strip() or str(source or "").strip() or "task"
    return resolve_display_name(
        name=str(task_name or ""),
        name_msgid=str(task_name_msgid or ""),
        fallback_id=fallback,
    )
