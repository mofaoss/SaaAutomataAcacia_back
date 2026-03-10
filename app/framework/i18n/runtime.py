from __future__ import annotations

import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]

DEBUG_LOG_I18N_MODE = "bilingual"
INFO_LOG_I18N_MODE = "current"
WARNING_LOG_I18N_MODE = "current"
ERROR_LOG_I18N_MODE = "current"

_CATALOGS: dict[str, dict[str, str]] = {lang: {} for lang in SUPPORTED_LANGS}
_LOADED = False
_MSGID_RE = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_\-\.]*$")


@dataclass(frozen=True, slots=True)
class TranslatableMessage:
    source_text: str
    source_lang: str
    msgid: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)
    owner_scope: str = "framework"
    owner_module: str | None = None

    def __str__(self) -> str:
        return render_message(self, context="ui")


def _contains_han(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _contains_unsupported_non_ascii(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if code < 128:
            continue
        if "一" <= ch <= "鿿":
            continue
        return True
    return False


def classify_source_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Translation source text must be a non-empty string")
    if _contains_unsupported_non_ascii(text):
        raise ValueError(f"Unsupported source language/script in _(): {text!r}")
    if _contains_han(text):
        return "zh_CN"
    return "en"


def _normalize_msgid(msgid: str | None) -> str | None:
    if msgid is None:
        return None
    normalized = msgid.strip()
    if not normalized:
        return None
    if not _MSGID_RE.match(normalized):
        raise ValueError(f"Invalid msgid format: {msgid!r}")
    return normalized


def _slugify(text: str) -> str:
    if _contains_han(text):
        return f"h{abs(hash(text)) & 0xFFFFFFFF:x}"
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:64] if slug else "text"


def _infer_owner_from_frame(frame) -> tuple[str, str | None]:
    file_name = Path(getattr(frame, "f_code", None).co_filename if frame else "")
    parts = [p.lower() for p in file_name.parts]
    try:
        mod_idx = parts.index("modules")
        module_id = file_name.parts[mod_idx + 1]
        return "module", module_id
    except Exception:
        pass
    if "framework" in parts:
        return "framework", None
    return "framework", None


def _(
    text: str,
    *,
    msgid: str | None = None,
    **kwargs: Any,
) -> TranslatableMessage:
    source_lang = classify_source_language(text)
    stable_msgid = _normalize_msgid(msgid)
    caller = inspect.currentframe().f_back
    owner_scope, owner_module = _infer_owner_from_frame(caller)
    return TranslatableMessage(
        source_text=text,
        source_lang=source_lang,
        msgid=stable_msgid,
        kwargs=dict(kwargs),
        owner_scope=owner_scope,
        owner_module=owner_module,
    )


def _owner_prefix(message: TranslatableMessage) -> str:
    if message.owner_scope == "module" and message.owner_module:
        return f"module.{message.owner_module}"
    return "framework"


def build_key(message: TranslatableMessage, *, context: str) -> str:
    prefix = _owner_prefix(message)
    suffix = message.msgid or _slugify(message.source_text)
    return f"{prefix}.{context}.{suffix}"


def _merge_file(lang: str, path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    _CATALOGS.setdefault(lang, {}).update({str(k): str(v) for k, v in data.items()})


def load_i18n_catalogs() -> None:
    global _LOADED
    root = Path(__file__).resolve().parents[3]

    framework_i18n = root / "app" / "framework" / "i18n"
    for lang in SUPPORTED_LANGS:
        _merge_file(lang, framework_i18n / f"{lang}.json")

    modules_root = root / "app" / "features" / "modules"
    if modules_root.exists():
        for module_dir in modules_root.iterdir():
            if not module_dir.is_dir():
                continue
            i18n_dir = module_dir / "i18n"
            if not i18n_dir.exists():
                continue
            for lang in SUPPORTED_LANGS:
                _merge_file(lang, i18n_dir / f"{lang}.json")
    _LOADED = True


def _resolve_lang() -> str:
    try:
        from app.framework.infra.config.app_config import (
            is_non_chinese_ui_language,
            is_traditional_ui_language,
        )

        if is_non_chinese_ui_language():
            return "en"
        if is_traditional_ui_language():
            return "zh_HK"
        return "zh_CN"
    except Exception:
        return DEFAULT_SOURCE_LANG


def _safe_format(value: str, kwargs: dict[str, Any]) -> str:
    try:
        return value.format(**kwargs) if kwargs else value
    except Exception:
        return value


def translate_message(message: TranslatableMessage, *, context: str, target_lang: str) -> str:
    if not _LOADED:
        load_i18n_catalogs()

    key = build_key(message, context=context)
    translated = _CATALOGS.get(target_lang, {}).get(key)
    if translated is None:
        translated = _CATALOGS.get(message.source_lang, {}).get(key)
    if translated is None:
        translated = message.source_text
    return _safe_format(translated, message.kwargs)


def _log_mode(levelno: int) -> str:
    if levelno <= logging.DEBUG:
        return DEBUG_LOG_I18N_MODE
    if levelno <= logging.INFO:
        return INFO_LOG_I18N_MODE
    if levelno <= logging.WARNING:
        return WARNING_LOG_I18N_MODE
    return ERROR_LOG_I18N_MODE


def render_message(value: Any, *, context: str = "ui", levelno: int | None = None) -> str:
    if not isinstance(value, TranslatableMessage):
        return str(value)

    current_lang = _resolve_lang()
    if context == "log":
        mode = _log_mode(levelno or logging.INFO)
        source_text = _safe_format(value.source_text, value.kwargs)
        current_text = translate_message(value, context="log", target_lang=current_lang)
        if mode == "source":
            return source_text
        if mode == "bilingual":
            return source_text if source_text == current_text else f"{source_text} | {current_text}"
        return current_text

    return translate_message(value, context="ui", target_lang=current_lang)


def get_catalog(lang: str) -> dict[str, str]:
    if not _LOADED:
        load_i18n_catalogs()
    return dict(_CATALOGS.get(lang, {}))


def tr(key: str, fallback: str | None = None, **kwargs: Any) -> str:
    """Key-based lookup for framework/module i18n resources.

    Fallback order:
    1. current language
    2. English source catalog
    3. explicit fallback
    4. key
    """
    if not _LOADED:
        load_i18n_catalogs()

    lang = _resolve_lang()
    value = (
        _CATALOGS.get(lang, {}).get(key)
        or _CATALOGS.get(DEFAULT_SOURCE_LANG, {}).get(key)
        or fallback
        or key
    )
    return _safe_format(value, kwargs)
