from __future__ import annotations

import hashlib
import inspect
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.framework.i18n.template_render import (
    TemplateFieldMismatch,
    TemplateFieldSpecMismatch,
    extract_template_field_details,
    extract_template_fields,
    render_localized_template,
)

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]

DEBUG_LOG_I18N_MODE = "bilingual"
INFO_LOG_I18N_MODE = "current"
WARNING_LOG_I18N_MODE = "current"
ERROR_LOG_I18N_MODE = "current"

_CATALOGS: dict[str, dict[str, str]] = {lang: {} for lang in SUPPORTED_LANGS}
_LOADED = False
_MSGID_SEMANTIC_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_MSGID_HASHLIKE_RE = re.compile(r"^(?:[0-9a-f]{8,}|h[0-9a-f]{6,})$")

_TELEMETRY_LOGGER = logging.getLogger("i18n.runtime")
_TELEMETRY_SEEN: set[str] = set()


@dataclass(frozen=True, slots=True)
class TranslatableMessage:
    source_text: str
    source_lang: str
    msgid: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)
    owner_scope: str = "framework"
    owner_module: str | None = None
    dynamic: bool = False
    template_skeleton: str | None = None
    template_fields: list[str] = field(default_factory=list)
    template_field_details: dict[str, dict[str, str]] = field(default_factory=dict)
    template_id: str | None = None
    callsite_key: str | None = None
    context_hint: str | None = None
    callsite_kind: str | None = None
    dynamic_candidate: bool = False
    literal_callsite: bool = False

    def __str__(self) -> str:
        return render_message(self, context="ui")


def _telemetry_warn(event: str, detail: str) -> None:
    token = f"{event}:{detail}"
    if token in _TELEMETRY_SEEN:
        return
    _TELEMETRY_SEEN.add(token)
    try:
        _TELEMETRY_LOGGER.warning("i18n_event=%s detail=%s", event, detail)
    except Exception:
        pass


def report_i18n_event(event: str, detail: str) -> None:
    _telemetry_warn(event, detail)


def _contains_han(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def _contains_latin_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def _contains_unsupported_non_ascii(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if code < 128:
            continue
        if 0x4E00 <= code <= 0x9FFF:
            continue
        if 0x3000 <= code <= 0x303F or 0xFF00 <= code <= 0xFFEF:
            continue
        # Reject explicit Japanese/Korean scripts, allow symbols/emoji.
        if 0x3040 <= code <= 0x30FF or 0x31F0 <= code <= 0x31FF:
            return True
        if 0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F or 0xAC00 <= code <= 0xD7AF:
            return True
        continue
    return False


def classify_source_language(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Translation source text must be a non-empty string")

    has_han = _contains_han(text)
    has_latin = _contains_latin_letters(text)

    if _contains_unsupported_non_ascii(text):
        raise ValueError(f"Unsupported source language/script in _(): {text!r}")

    # Enforce per-string single-language rule for extracted source text.
    if has_han and has_latin:
        raise ValueError(f"Mixed-language source text is not allowed in _(): {text!r}")

    if has_han:
        return "zh_CN"
    return "en"


def _normalize_msgid(msgid: str | None) -> str | None:
    if msgid is None:
        return None
    normalized = msgid.strip()
    if not normalized:
        return None
    if _MSGID_HASHLIKE_RE.fullmatch(normalized):
        raise ValueError(f"Hash-like msgid is forbidden: {msgid!r}")
    if not _MSGID_SEMANTIC_RE.fullmatch(normalized):
        raise ValueError(
            "Invalid msgid format. msgid must be semantic snake_case, "
            f"for example task_completed: {msgid!r}"
        )
    return normalized


def _slugify(text: str) -> str:
    # Readable fallback slug; never hash-based.
    lowered = text.strip().lower()
    normalized_chars: list[str] = []
    for ch in lowered:
        code = ord(ch)
        if (97 <= code <= 122) or (48 <= code <= 57):
            normalized_chars.append(ch)
            continue
        # Preserve CJK Unified Ideographs to keep fallback readable.
        if 0x4E00 <= code <= 0x9FFF:
            normalized_chars.append(ch)
            continue
        normalized_chars.append("_")
    slug = re.sub(r"_+", "_", "".join(normalized_chars)).strip("_")
    return slug[:80] if slug else "text"


def validate_msgid(msgid: str | None) -> str | None:
    """Public validator for tooling to enforce msgid policy consistently."""
    return _normalize_msgid(msgid)


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


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return repr(value)


def _resolve_owner_metadata(owner_scope: str | None, owner_module: str | None) -> tuple[str, str | None]:
    if owner_scope in {"module", "framework"}:
        return owner_scope, owner_module
    caller = inspect.currentframe().f_back
    return _infer_owner_from_frame(caller)


def _resolve_static_source_lang(text: str) -> str:
    try:
        return classify_source_language(text)
    except Exception as exc:
        _telemetry_warn("static_source_lang_fallback", _coerce_text(exc))
        return DEFAULT_SOURCE_LANG


def _resolve_template_source_lang(template: str) -> str:
    try:
        return classify_source_language(template)
    except Exception as exc:
        _telemetry_warn("dynamic_template_source_lang_fallback", _coerce_text(exc))
        return DEFAULT_SOURCE_LANG


def _looks_like_template_skeleton(text: str, fields: list[str]) -> bool:
    if not text:
        return False
    if not fields:
        return "{" in text and "}" in text
    for field in fields:
        if f"{{{field}}}" in text:
            return True
    return False


def _(
    text: str,
    *,
    msgid: str | None = None,
    **kwargs: Any,
) -> TranslatableMessage:
    # Internal-only kwargs injected by import/build rewrite pipeline.
    dynamic = bool(kwargs.pop("__i18n_dynamic__", False))
    template_skeleton = kwargs.pop("__i18n_template__", None)
    template_id = kwargs.pop("__i18n_template_id__", None)
    injected_fields = kwargs.pop("__i18n_fields__", None)
    owner_scope_hint = kwargs.pop("__i18n_owner_scope__", None)
    owner_module_hint = kwargs.pop("__i18n_owner_module__", None)
    callsite_key = kwargs.pop("__i18n_callsite_key__", None)
    callsite_kind = kwargs.pop("__i18n_callsite_kind__", None)
    context_hint = kwargs.pop("__i18n_context_hint__", None)
    literal_callsite = bool(kwargs.pop("__i18n_literal__", False))
    dynamic_candidate = bool(kwargs.pop("__i18n_dynamic_candidate__", False))

    stable_msgid = _normalize_msgid(msgid)
    owner_scope, owner_module = _resolve_owner_metadata(owner_scope_hint, owner_module_hint)

    if dynamic or callsite_kind == "dynamic_template":
        source_text = _coerce_text(text)
        skeleton = _coerce_text(template_skeleton) if template_skeleton else source_text
        if stable_msgid is None:
            stable_msgid = f"tmpl_{hashlib.sha1(skeleton.encode('utf-8')).hexdigest()[:12]}"
        source_lang = _resolve_template_source_lang(skeleton)

        payload: dict[str, Any] = {}
        if isinstance(injected_fields, dict):
            payload.update(injected_fields)
        # Backward compatibility for explicit kwargs in rewritten/generated calls.
        payload.update(kwargs)
        fields = extract_template_fields(skeleton)
        field_details = extract_template_field_details(skeleton)
        return TranslatableMessage(
            source_text=source_text,
            source_lang=source_lang,
            msgid=stable_msgid,
            kwargs=payload,
            owner_scope=owner_scope,
            owner_module=owner_module,
            dynamic=True,
            template_skeleton=skeleton,
            template_fields=fields,
            template_field_details=field_details,
            template_id=_coerce_text(template_id) if template_id is not None else None,
            callsite_key=_coerce_text(callsite_key) if callsite_key is not None else None,
            context_hint=_coerce_text(context_hint) if context_hint is not None else None,
            callsite_kind="dynamic_template",
            dynamic_candidate=False,
            literal_callsite=False,
        )

    source_text = _coerce_text(text)
    if dynamic_candidate or callsite_kind == "dynamic_candidate":
        _telemetry_warn(
            "dynamic_candidate_without_metadata",
            _coerce_text(callsite_key or stable_msgid or source_text[:80]),
        )
        _telemetry_warn(
            "external_string_bypassed_i18n_static_enforcement",
            _coerce_text(callsite_key or source_text[:80]),
        )
        if stable_msgid is None:
            stable_msgid = f"txt_{hashlib.sha1(source_text.encode('utf-8')).hexdigest()[:12]}"
        return TranslatableMessage(
            source_text=source_text,
            source_lang=DEFAULT_SOURCE_LANG,
            msgid=stable_msgid,
            kwargs=dict(kwargs),
            owner_scope=owner_scope,
            owner_module=owner_module,
            dynamic=False,
            callsite_key=_coerce_text(callsite_key) if callsite_key is not None else None,
            context_hint=_coerce_text(context_hint) if context_hint is not None else None,
            callsite_kind="dynamic_candidate",
            dynamic_candidate=True,
            literal_callsite=False,
        )

    if not literal_callsite and callsite_kind != "static_literal":
        # Heuristic safety: unresolved non-literal mixed/external strings should not be
        # forced through strict static source-language enforcement.
        if _contains_han(source_text) and _contains_latin_letters(source_text):
            _telemetry_warn(
                "dynamic_candidate_without_metadata",
                _coerce_text(callsite_key or stable_msgid or source_text[:80]),
            )
            _telemetry_warn(
                "external_string_bypassed_i18n_static_enforcement",
                _coerce_text(callsite_key or source_text[:80]),
            )
            if stable_msgid is None:
                stable_msgid = f"txt_{hashlib.sha1(source_text.encode('utf-8')).hexdigest()[:12]}"
            return TranslatableMessage(
                source_text=source_text,
                source_lang=DEFAULT_SOURCE_LANG,
                msgid=stable_msgid,
                kwargs=dict(kwargs),
                owner_scope=owner_scope,
                owner_module=owner_module,
                dynamic=False,
                callsite_key=_coerce_text(callsite_key) if callsite_key is not None else None,
                context_hint=_coerce_text(context_hint) if context_hint is not None else None,
                callsite_kind="dynamic_candidate",
                dynamic_candidate=True,
                literal_callsite=False,
            )

    # Strict static path applies only to known static literals.
    # For external/non-rewritten calls we preserve historical static behavior.
    if stable_msgid is None:
        stable_msgid = f"txt_{hashlib.sha1(source_text.encode('utf-8')).hexdigest()[:12]}"
    source_lang = _resolve_static_source_lang(source_text)
    return TranslatableMessage(
        source_text=source_text,
        source_lang=source_lang,
        msgid=stable_msgid,
        kwargs=dict(kwargs),
        owner_scope=owner_scope,
        owner_module=owner_module,
        dynamic=False,
        callsite_key=_coerce_text(callsite_key) if callsite_key is not None else None,
        context_hint=_coerce_text(context_hint) if context_hint is not None else None,
        callsite_kind=_coerce_text(callsite_kind) if callsite_kind is not None else ("static_literal" if literal_callsite else None),
        dynamic_candidate=False,
        literal_callsite=literal_callsite,
    )


def qt(value: Any) -> str | None:
    """Qt boundary adapter: convert translatable/lazy values to concrete strings."""
    if value is None:
        return None
    if isinstance(value, TranslatableMessage):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def _owner_prefix(message: TranslatableMessage) -> str:
    if message.owner_scope == "module" and message.owner_module:
        return f"module.{message.owner_module}"
    return "framework"


def build_key(message: TranslatableMessage, *, context: str) -> str:
    prefix = _owner_prefix(message)
    if message.msgid:
        suffix = _normalize_msgid(message.msgid) or "text"
    else:
        key_source = message.template_skeleton if message.dynamic else message.source_text
        suffix = _slugify(key_source or "")
    return f"{prefix}.{context}.{suffix}"


def _merge_file(lang: str, path: Path) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
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


def _render_dynamic_message(message: TranslatableMessage, *, key: str, target_lang: str) -> str:
    source_template = message.template_skeleton or message.source_text
    payload = message.kwargs or {}
    original_rendered = message.source_text

    translated_template = _CATALOGS.get(target_lang, {}).get(key)
    if translated_template is None:
        translated_template = _CATALOGS.get(message.source_lang, {}).get(key)
    if translated_template is None:
        _telemetry_warn("dynamic_template_missing", key)
        translated_template = source_template

    expected_fields = list(message.template_fields or extract_template_fields(source_template))
    expected_field_details = dict(message.template_field_details or extract_template_field_details(source_template))
    try:
        return render_localized_template(
            translated_template,
            payload,
            expected_fields=expected_fields,
            expected_field_details=expected_field_details,
            strict_fields=True,
        )
    except TemplateFieldMismatch as mismatch:
        _telemetry_warn("dynamic_template_field_mismatch", f"{key}:{mismatch}")
        _telemetry_warn("translated_render_failed", f"{key}:{mismatch}")
    except TemplateFieldSpecMismatch as mismatch:
        _telemetry_warn("dynamic_template_format_spec_mismatch", f"{key}:{mismatch}")
        _telemetry_warn("translated_render_failed", f"{key}:{mismatch}")
    except Exception as exc:
        _telemetry_warn("dynamic_template_render_failed", f"{key}:{_coerce_text(exc)}")
        _telemetry_warn("translated_render_failed", f"{key}:{_coerce_text(exc)}")

    # Fallback 1: source template render
    try:
        rendered_source = render_localized_template(
            source_template,
            payload,
            expected_fields=expected_fields,
            expected_field_details=expected_field_details,
            strict_fields=False,
        )
        if _looks_like_template_skeleton(rendered_source, expected_fields):
            raise ValueError("source_template_unrendered_skeleton")
        return rendered_source
    except Exception as exc:
        _telemetry_warn("source_render_failed", f"{key}:{_coerce_text(exc)}")
        _telemetry_warn("dynamic_template_render_failed", f"{key}:source:{_coerce_text(exc)}")

    # Fallback 2: original rendered text (from author f-string call)
    _telemetry_warn("dynamic_template_fallback_to_original", key)
    _telemetry_warn("fallback_to_original_rendered", key)
    if _looks_like_template_skeleton(original_rendered, expected_fields):
        # Last-resort best effort: avoid exposing template placeholders.
        try:
            best_effort = render_localized_template(
                source_template,
                payload,
                expected_fields=expected_fields,
                expected_field_details=expected_field_details,
                strict_fields=False,
            )
            if not _looks_like_template_skeleton(best_effort, expected_fields):
                return best_effort
        except Exception:
            pass
    return original_rendered


def translate_message(message: TranslatableMessage, *, context: str, target_lang: str) -> str:
    if not _LOADED:
        load_i18n_catalogs()

    key = build_key(message, context=context)
    if message.dynamic:
        return _render_dynamic_message(message, key=key, target_lang=target_lang)
    if message.dynamic_candidate:
        return message.source_text

    translated = _CATALOGS.get(target_lang, {}).get(key)
    if translated is None:
        translated = _CATALOGS.get(message.source_lang, {}).get(key)
    if translated is None:
        translated = message.source_text

    # Safety guard: prevent placeholder skeleton leak when a dynamic call missed rewrite metadata.
    if isinstance(translated, str) and not message.kwargs and "{" in translated and "}" in translated:
        translated_fields = extract_template_fields(translated)
        if translated_fields and not _looks_like_template_skeleton(message.source_text, translated_fields):
            _telemetry_warn("dynamic_candidate_without_metadata", key)
            _telemetry_warn("fallback_to_original_rendered", key)
            return message.source_text

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
    try:
        if not isinstance(value, TranslatableMessage):
            return str(value)

        current_lang = _resolve_lang()
        if context == "log":
            mode = _log_mode(levelno or logging.INFO)
            source_text = value.source_text
            current_text = translate_message(value, context="log", target_lang=current_lang)
            if mode == "source":
                return source_text
            if mode == "bilingual":
                return source_text if source_text == current_text else f"{source_text} | {current_text}"
            return current_text

        return translate_message(value, context="ui", target_lang=current_lang)
    except Exception as exc:
        _telemetry_warn("render_message_failed", _coerce_text(exc))
        if isinstance(value, TranslatableMessage):
            return value.source_text
        return _coerce_text(value)


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
