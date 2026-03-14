from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import logging
import re
import sys
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.framework.i18n.template_render import (
    TemplateFieldMismatch,
    TemplateFieldSpecMismatch,
    extract_template_field_details,
    extract_template_fields,
    render_localized_template,
)

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]

DEBUG_LOG_I18N_MODE = "source"
INFO_LOG_I18N_MODE = "current"
WARNING_LOG_I18N_MODE = "current"
ERROR_LOG_I18N_MODE = "current"

_CATALOGS: dict[str, dict[str, str]] = {lang: {} for lang in SUPPORTED_LANGS}
_LOADED = False
_TEMPLATE_META: dict[str, dict[str, Any]] = {}
_TEMPLATE_META_LOADED = False
_DYNAMIC_RECOVERY_KEYS: set[str] = set()
_DYNAMIC_KEYS_BY_OWNER_CONTEXT: dict[str, list[str]] = {}
_CATALOG_DYNAMIC_KEYS: set[str] = set()
_CATALOG_DYNAMIC_KEYS_BY_OWNER_CONTEXT: dict[str, list[str]] = {}
_CATALOG_DYNAMIC_INDEX_READY = False
_DYNAMIC_RECOVERY_MATCH_CACHE: dict[tuple[str, str], str | None] = {}
_DYNAMIC_RECOVERY_CACHE_MAX = 2048
_SOURCE_TEXT_KEY_BY_OWNER_CONTEXT: dict[str, dict[str, str | None]] = {}
_SOURCE_TEXT_KEY_GLOBAL: dict[str, str | None] = {}
_SOURCE_TEXT_INDEX_READY = False
_PAYLOAD_TEXT_TRANSLATION_CACHE: dict[tuple[str, str, str], str] = {}
_PAYLOAD_TEXT_TRANSLATION_CACHE_MAX = 2048
_MSGID_SEMANTIC_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_MSGID_HASHLIKE_RE = re.compile(r"^(?:[0-9a-f]{8,}|h[0-9a-f]{6,})$")

_TELEMETRY_LOGGER = logging.getLogger("i18n.runtime")
_TELEMETRY_SEEN: set[str] = set()


class TranslatableString(str):
    """A real string subclass carrying i18n metadata for high-performance UI paths.
    This bypasses all attribute/type issues in packaged environments (Nuitka/PyInstaller).
    """
    __slots__ = ("_i18n_msg",)

    def __new__(cls, content: str, message: TranslatableMessage):
        obj = super().__new__(cls, content)
        # Preserve architectural metadata for auditing/log analysis
        object.__setattr__(obj, "_i18n_msg", message)
        return obj

    @property
    def i18n_msg(self) -> TranslatableMessage:
        return self._i18n_msg

    def format(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        """
        Preserve i18n metadata across `.format(...)` so prepare_build rewritten
        calls like _("...").format(...) can still render under log context.
        """
        if args or not kwargs:
            return super().format(*args, **kwargs)

        message = getattr(self, "_i18n_msg", None)
        if not isinstance(message, TranslatableMessage):
            return super().format(*args, **kwargs)

        merged_kwargs = dict(message.kwargs or {})
        merged_kwargs.update(kwargs)
        # For non-explicit hash-like msgids (e.g. txt_xxx), preserve recoverability:
        # after prepare_build rewrites _("...").format(...), keeping that generated
        # hash msgid can block framework.log.* key lookup for auto-wrapped logs.
        next_msgid = message.msgid
        if (not message.msgid_explicit) and isinstance(next_msgid, str) and next_msgid.startswith("txt_"):
            next_msgid = None

        updated = replace(message, msgid=next_msgid, kwargs=merged_kwargs, _rendered_cache=None)
        return _public_text(updated)


@dataclass(frozen=False)
class TranslatableMessage:
    source_text: str
    source_lang: str
    msgid: str | None = None
    msgid_explicit: bool = False
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

    # Rendering cache should not affect identity/equality semantics.
    _rendered_cache: str | None = field(default=None, compare=False, repr=False)

    def __str__(self) -> str:
        if self._rendered_cache is None:
            self._rendered_cache = render_message(self, context="ui")
        return self._rendered_cache

    def __getattr__(self, name: str) -> Any:
        # Proxy for safety, but TranslatableString handles most cases now.
        return getattr(str(self), name)

    def splitlines(self, keepends: bool = False) -> list[str]:
        return str(self).splitlines(keepends)

    def strip(self, chars: str | None = None) -> str:
        return str(self).strip(chars)

    def split(self, sep: str | None = None, maxsplit: int = -1) -> list[str]:
        return str(self).split(sep, maxsplit)

    def replace(self, old: str, new: str, count: int = -1) -> str:
        return str(self).replace(old, new, count)

    def startswith(self, prefix: str | tuple[str, ...], start: int | None = None, end: int | None = None) -> bool:
        return str(self).startswith(prefix, start, end)

    def endswith(self, suffix: str | tuple[str, ...], start: int | None = None, end: int | None = None) -> bool:
        return str(self).endswith(suffix, start, end)

    def lower(self) -> str:
        return str(self).lower()

    def upper(self) -> str:
        return str(self).upper()

    def find(self, sub: str, start: int | None = None, end: int | None = None) -> int:
        return str(self).find(sub, start, end)

    def __len__(self) -> int:
        return len(str(self))

    def __add__(self, other: Any) -> str:
        return str(self) + str(other)

    def __radd__(self, other: Any) -> str:
        return str(other) + str(self)

    def __bool__(self) -> bool:
        return bool(self.source_text)

    # def _hash_identity(self) -> tuple[str, str]:
    #     """Stable hash key: prefer semantic msgid, fallback to template/source text."""
    #     if self.msgid:
    #         return ("msgid", str(self.msgid))
    #     if self.template_id:
    #         return ("template", str(self.template_id))
    #     return ("source", str(self.source_text))

    # def __hash__(self) -> int:
    #     return hash(self._hash_identity())


def _telemetry_warn(event: str, detail: str) -> None:
    from app.framework.infra.config.app_config import config
    if not config.showI18nWarnings.value:
        return
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
    try:
        module_name = str(getattr(getattr(frame, "f_globals", {}), "get", lambda *_: "")("__name__", "") or "")
    except Exception:
        module_name = ""

    if module_name:
        lower_module = module_name.lower()
        if lower_module.startswith("app.features.utils") or "features.utils." in lower_module:
            return "module", "utils"
        if lower_module.startswith("app.features.modules."):
            tail = module_name[len("app.features.modules."):]
            module_id = re.split(r"[.:/\\]", tail, maxsplit=1)[0]
            if module_id:
                return "module", module_id
        if "features.modules." in lower_module:
            tail = module_name.split("features.modules.", 1)[1]
            module_id = re.split(r"[.:/\\]", tail, maxsplit=1)[0]
            if module_id:
                return "module", module_id
        if lower_module.startswith("app.framework") or ".framework." in lower_module:
            return "framework", None

    file_name = Path(getattr(frame, "f_code", None).co_filename if frame else "")
    normalized = str(file_name).replace("\\", "/").lower()
    if re.search(r"(?:^|[./\\])features[./\\]utils(?:[./\\]|$)", normalized):
        return "module", "utils"
    module_match = re.search(r"(?:^|[./\\])modules[./\\]([a-z0-9_]+)(?:[./\\]|$)", normalized)
    if module_match:
        return "module", module_match.group(1)
    dotted_match = re.search(r"features\.modules\.([a-z0-9_]+)", normalized)
    if dotted_match:
        return "module", dotted_match.group(1)
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


def _public_text(message: TranslatableMessage) -> str:
    """Expose a string value while preserving i18n metadata for log re-rendering."""
    return TranslatableString(str(message), message)


def _(
    text: str,
    *,
    msgid: str | None = None,
    **kwargs: Any,
) -> str:
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

    normalized_msgid = _normalize_msgid(msgid)
    msgid_explicit = normalized_msgid is not None
    stable_msgid = normalized_msgid
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
        message = TranslatableMessage(
            source_text=source_text,
            source_lang=source_lang,
            msgid=stable_msgid,
            msgid_explicit=msgid_explicit,
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
        return _public_text(message)

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
        message = TranslatableMessage(
            source_text=source_text,
            source_lang=DEFAULT_SOURCE_LANG,
            msgid=stable_msgid,
            msgid_explicit=msgid_explicit,
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
        return _public_text(message)

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
            message = TranslatableMessage(
                source_text=source_text,
                source_lang=DEFAULT_SOURCE_LANG,
                msgid=stable_msgid,
                msgid_explicit=msgid_explicit,
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
            return _public_text(message)

    # Strict static path applies only to known static literals.
    # For external/non-rewritten calls we preserve historical static behavior.
    if stable_msgid is None:
        stable_msgid = f"txt_{hashlib.sha1(source_text.encode('utf-8')).hexdigest()[:12]}"
    source_lang = _resolve_static_source_lang(source_text)
    message = TranslatableMessage(
        source_text=source_text,
        source_lang=source_lang,
        msgid=stable_msgid,
        msgid_explicit=msgid_explicit,
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
    return _public_text(message)


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


@lru_cache(maxsize=1)
def _resolve_i18n_project_root() -> Path:
    """Resolve runtime project root robustly across source and Nuitka layouts."""
    marker = ("app", "framework", "i18n", "en.json")

    def has_i18n_root(candidate: Path) -> bool:
        try:
            return (candidate / marker[0] / marker[1] / marker[2] / marker[3]).is_file()
        except Exception:
            return False

    candidates: list[Path] = []
    try:
        # Preferred root resolver used by runtime folders/config.
        from app.framework.infra.runtime.paths import PROJECT_ROOT as runtime_project_root

        candidates.append(Path(runtime_project_root))
    except Exception:
        pass

    try:
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    module_path = Path(__file__).resolve()
    # Source layout fallback: .../app/framework/i18n/runtime.py -> parents[3] is project root.
    candidates.append(module_path.parents[3])
    # Compiled module fallback: .../dist/app.framework.i18n.runtime.pyd -> parent is dist root.
    candidates.append(module_path.parent)

    for candidate in candidates:
        if has_i18n_root(candidate):
            return candidate

    # Last-resort: keep historical behavior.
    return module_path.parents[3]


def load_i18n_catalogs() -> None:
    global _LOADED
    global _SOURCE_TEXT_INDEX_READY
    global _CATALOG_DYNAMIC_INDEX_READY
    global _DYNAMIC_RECOVERY_MATCH_CACHE
    global _PAYLOAD_TEXT_TRANSLATION_CACHE
    root = _resolve_i18n_project_root()

    framework_i18n = root / "app" / "framework" / "i18n"
    for lang in SUPPORTED_LANGS:
        _merge_file(lang, framework_i18n / f"{lang}.json")

    features_utils_i18n = root / "app" / "features" / "utils" / "i18n"
    for lang in SUPPORTED_LANGS:
        _merge_file(lang, features_utils_i18n / f"{lang}.json")

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
    _SOURCE_TEXT_INDEX_READY = False
    _CATALOG_DYNAMIC_INDEX_READY = False
    _DYNAMIC_RECOVERY_MATCH_CACHE.clear()
    _PAYLOAD_TEXT_TRANSLATION_CACHE.clear()

def _owner_context_key_from_i18n_key(key: str) -> str | None:
    parts = key.split(".")
    if len(parts) >= 3 and parts[0] == "framework":
        return f"framework.{parts[1]}"
    if len(parts) >= 4 and parts[0] == "module":
        return f"module.{parts[1]}.{parts[2]}"
    return None


def _owner_context_key_for_message(message: TranslatableMessage, *, context: str) -> str:
    return f"{_owner_prefix(message)}.{context}"


def _build_source_text_index() -> None:
    global _SOURCE_TEXT_INDEX_READY
    if _SOURCE_TEXT_INDEX_READY:
        return
    if not _LOADED:
        load_i18n_catalogs()

    _SOURCE_TEXT_KEY_BY_OWNER_CONTEXT.clear()
    _SOURCE_TEXT_KEY_GLOBAL.clear()

    en_catalog = _CATALOGS.get(DEFAULT_SOURCE_LANG, {})
    for key, source_text in en_catalog.items():
        if not isinstance(key, str) or not isinstance(source_text, str):
            continue
        owner_context_key = _owner_context_key_from_i18n_key(key)
        if not owner_context_key:
            continue
        bucket = _SOURCE_TEXT_KEY_BY_OWNER_CONTEXT.setdefault(owner_context_key, {})
        existing = bucket.get(source_text)
        if existing is None:
            bucket[source_text] = key
        elif existing != key:
            # Mark ambiguous source text to avoid wrong substitutions.
            bucket[source_text] = None

        global_existing = _SOURCE_TEXT_KEY_GLOBAL.get(source_text)
        if global_existing is None:
            _SOURCE_TEXT_KEY_GLOBAL[source_text] = key
        elif global_existing != key:
            _SOURCE_TEXT_KEY_GLOBAL[source_text] = None

    _SOURCE_TEXT_INDEX_READY = True
def _recover_static_message_without_msgid(
    message: TranslatableMessage,
    *,
    context: str,
    target_lang: str,
) -> str | None:
    _build_source_text_index()
    owner_context_key = _owner_context_key_for_message(message, context=context)
    bucket = _SOURCE_TEXT_KEY_BY_OWNER_CONTEXT.get(owner_context_key, {})
    recovered_key = bucket.get(message.source_text)
    # Generic fallback: if current owner-context misses, use the global unique
    # source-text index (already ambiguity-safe: duplicates are stored as None).
    if not recovered_key:
        recovered_key = _SOURCE_TEXT_KEY_GLOBAL.get(message.source_text)
    if not recovered_key:
        return None

    translated = _CATALOGS.get(target_lang, {}).get(recovered_key)
    if translated is None and target_lang == "zh_HK":
        zh_cn_value = _CATALOGS.get("zh_CN", {}).get(recovered_key)
        if zh_cn_value is not None:
            translated = _zh_hk_fallback_text(zh_cn_value)
    if translated is None:
        translated = _CATALOGS.get(DEFAULT_SOURCE_LANG, {}).get(recovered_key)
    if translated is None:
        return None

    _telemetry_warn("static_without_msgid_recovered", recovered_key)
    return translated



def _translate_payload_plain_text(
    source_text: str,
    *,
    owner_context_key: str | None,
    target_lang: str,
) -> str:
    if not source_text:
        return source_text

    cache_key = (owner_context_key or "__global__", target_lang, source_text)
    cached = _PAYLOAD_TEXT_TRANSLATION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    _build_source_text_index()
    recovered_key: str | None = None
    if owner_context_key:
        recovered_key = _SOURCE_TEXT_KEY_BY_OWNER_CONTEXT.get(owner_context_key, {}).get(source_text)
    if not recovered_key:
        recovered_key = _SOURCE_TEXT_KEY_GLOBAL.get(source_text)

    translated = source_text
    if recovered_key:
        translated = _CATALOGS.get(target_lang, {}).get(recovered_key) or translated
        if translated == source_text and target_lang == "zh_HK":
            zh_cn_value = _CATALOGS.get("zh_CN", {}).get(recovered_key)
            if zh_cn_value is not None:
                translated = _zh_hk_fallback_text(zh_cn_value)

    if len(_PAYLOAD_TEXT_TRANSLATION_CACHE) >= _PAYLOAD_TEXT_TRANSLATION_CACHE_MAX:
        _PAYLOAD_TEXT_TRANSLATION_CACHE.clear()
    _PAYLOAD_TEXT_TRANSLATION_CACHE[cache_key] = translated
    return translated


def _localize_dynamic_payload_values(
    payload: dict[str, Any],
    *,
    owner_context_key: str | None,
    target_lang: str,
) -> dict[str, Any]:
    if not payload:
        return payload

    localized_payload: dict[str, Any] = {}
    changed = False
    for key, value in payload.items():
        if isinstance(value, str):
            localized = _translate_payload_plain_text(
                value,
                owner_context_key=owner_context_key,
                target_lang=target_lang,
            )
            localized_payload[key] = localized
            if localized != value:
                changed = True
            continue
        localized_payload[key] = value

    return localized_payload if changed else payload
def _merge_template_meta_file(path: Path) -> None:
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

    for key, meta in data.items():
        if not (isinstance(key, str) and isinstance(meta, dict)):
            continue
        _TEMPLATE_META[key] = meta

        source_template = str(meta.get("source_template") or "")
        if not source_template:
            continue
        if not extract_template_fields(source_template):
            continue

        _DYNAMIC_RECOVERY_KEYS.add(key)
        owner_context_key = _owner_context_key_from_i18n_key(key)
        if not owner_context_key:
            continue
        bucket = _DYNAMIC_KEYS_BY_OWNER_CONTEXT.setdefault(owner_context_key, [])
        if key not in bucket:
            bucket.append(key)


def _cache_dynamic_recovery_match(owner_context_key: str, rendered_text: str, best_key: str | None) -> None:
    if len(_DYNAMIC_RECOVERY_MATCH_CACHE) >= _DYNAMIC_RECOVERY_CACHE_MAX:
        _DYNAMIC_RECOVERY_MATCH_CACHE.clear()
    _DYNAMIC_RECOVERY_MATCH_CACHE[(owner_context_key, rendered_text)] = best_key

def _get_cached_dynamic_recovery_match(owner_context_key: str, rendered_text: str) -> tuple[bool, str | None]:
    cache_key = (owner_context_key, rendered_text)
    if cache_key not in _DYNAMIC_RECOVERY_MATCH_CACHE:
        return False, None
    return True, _DYNAMIC_RECOVERY_MATCH_CACHE.get(cache_key)


def _build_catalog_dynamic_index() -> None:
    global _CATALOG_DYNAMIC_INDEX_READY
    if _CATALOG_DYNAMIC_INDEX_READY:
        return
    if not _LOADED:
        load_i18n_catalogs()

    _CATALOG_DYNAMIC_KEYS.clear()
    _CATALOG_DYNAMIC_KEYS_BY_OWNER_CONTEXT.clear()

    for lang in (DEFAULT_SOURCE_LANG, "zh_CN", "zh_HK"):
        catalog = _CATALOGS.get(lang, {})
        for key, value in catalog.items():
            if not (isinstance(key, str) and isinstance(value, str)):
                continue
            if not extract_template_fields(value):
                continue
            _CATALOG_DYNAMIC_KEYS.add(key)
            owner_context_key = _owner_context_key_from_i18n_key(key)
            if not owner_context_key:
                continue
            bucket = _CATALOG_DYNAMIC_KEYS_BY_OWNER_CONTEXT.setdefault(owner_context_key, [])
            if key not in bucket:
                bucket.append(key)

    _CATALOG_DYNAMIC_INDEX_READY = True


def _is_dynamic_recovery_key(key: str) -> bool:
    _load_template_meta()
    if key in _DYNAMIC_RECOVERY_KEYS:
        return True
    _build_catalog_dynamic_index()
    return key in _CATALOG_DYNAMIC_KEYS


def _load_template_meta() -> None:
    global _TEMPLATE_META_LOADED
    global _DYNAMIC_RECOVERY_MATCH_CACHE
    global _PAYLOAD_TEXT_TRANSLATION_CACHE
    if _TEMPLATE_META_LOADED:
        return
    _DYNAMIC_RECOVERY_MATCH_CACHE.clear()
    _PAYLOAD_TEXT_TRANSLATION_CACHE.clear()
    root = _resolve_i18n_project_root()
    _merge_template_meta_file(root / "app" / "framework" / "i18n" / "template_meta.json")
    _merge_template_meta_file(root / "app" / "features" / "utils" / "i18n" / "template_meta.json")

    modules_root = root / "app" / "features" / "modules"
    if modules_root.exists():
        for module_dir in modules_root.iterdir():
            if not module_dir.is_dir():
                continue
            _merge_template_meta_file(module_dir / "i18n" / "template_meta.json")

    _TEMPLATE_META_LOADED = True


@lru_cache(maxsize=512)
def _dynamic_payload_pattern(source_template: str) -> tuple[re.Pattern[str], tuple[tuple[str, str], ...]] | None:
    import string

    pattern_parts: list[str] = []
    field_order: list[tuple[str, str]] = []
    for literal_text, field_name, format_spec, _conversion in string.Formatter().parse(source_template):
        pattern_parts.append(re.escape(literal_text or ""))
        if not field_name:
            continue
        base = field_name.split("[", 1)[0].split(".", 1)[0]
        if not base:
            continue
        pattern_parts.append(f"(?P<{base}>.*?)")
        field_order.append((base, format_spec or ""))

    if not field_order:
        return None

    try:
        pattern = re.compile("".join(pattern_parts), flags=re.DOTALL)
    except Exception:
        return None

    return pattern, tuple(field_order)


def _extract_dynamic_payload(
    source_template: str,
    rendered_text: str,
    field_details: dict[str, dict[str, str]] | None,
) -> dict[str, Any] | None:
    compiled = _dynamic_payload_pattern(source_template)
    if compiled is None:
        return None

    pattern, field_order = compiled
    match = pattern.fullmatch(rendered_text)
    if not match:
        return None

    payload: dict[str, Any] = {}
    for name, fallback_spec in field_order:
        raw = match.group(name)
        spec = fallback_spec
        if field_details and name in field_details:
            spec = str(field_details[name].get("format_spec") or fallback_spec or "")
        raw_text = str(raw)
        if spec:
            end_ch = spec[-1]
            if end_ch in {"f", "F", "e", "E", "g", "G", "%"}:
                try:
                    payload[name] = float(raw_text)
                    continue
                except Exception:
                    pass
            if end_ch in {"d", "i", "u"}:
                try:
                    payload[name] = int(raw_text)
                    continue
                except Exception:
                    pass
        payload[name] = raw_text
    return payload


def _render_dynamic_candidate_message(message: TranslatableMessage, *, key: str, target_lang: str) -> str | None:
    _load_template_meta()
    meta = _TEMPLATE_META.get(key)
    source_template = ""
    if isinstance(meta, dict):
        source_template = str(meta.get("source_template") or "")
    if not source_template:
        source_template = str(_CATALOGS.get(DEFAULT_SOURCE_LANG, {}).get(key) or "")
    if not source_template:
        source_template = str(_CATALOGS.get(target_lang, {}).get(key) or "")
    if not source_template:
        return None

    field_details = meta.get("field_details") if isinstance(meta, dict) else None
    parsed_payload = _extract_dynamic_payload(
        source_template=source_template,
        rendered_text=message.source_text,
        field_details=field_details if isinstance(field_details, dict) else None,
    )
    if not parsed_payload:
        return None

    owner_context_key = _owner_context_key_from_i18n_key(key)
    parsed_payload = _localize_dynamic_payload_values(
        parsed_payload,
        owner_context_key=owner_context_key,
        target_lang=target_lang,
    )

    translated_template = _CATALOGS.get(target_lang, {}).get(key)
    if translated_template is None and target_lang == "zh_HK":
        zh_cn_template = _CATALOGS.get("zh_CN", {}).get(key)
        if zh_cn_template is not None:
            translated_template = _zh_hk_fallback_text(zh_cn_template)
    if translated_template is None:
        translated_template = _CATALOGS.get(DEFAULT_SOURCE_LANG, {}).get(key)
    if translated_template is None:
        translated_template = source_template

    try:
        expected_fields = extract_template_fields(source_template)
        expected_field_details = extract_template_field_details(source_template)
        return render_localized_template(
            translated_template,
            parsed_payload,
            expected_fields=expected_fields,
            expected_field_details=expected_field_details,
            strict_fields=False,
        )
    except Exception as exc:
        _telemetry_warn("dynamic_candidate_render_failed", f"{key}:{_coerce_text(exc)}")
        return None

def _find_best_matching_template(
    message: TranslatableMessage,
    candidate_keys: Iterable[str],
) -> str | None:
    best_key: str | None = None
    best_template_len = -1
    for candidate_key in candidate_keys:
        meta = _TEMPLATE_META.get(candidate_key)
        source_template = ""
        field_details = None
        if isinstance(meta, dict):
            source_template = str(meta.get("source_template") or "")
            field_details = meta.get("field_details")
        if not source_template:
            source_template = str(
                _CATALOGS.get(DEFAULT_SOURCE_LANG, {}).get(candidate_key)
                or _CATALOGS.get("zh_CN", {}).get(candidate_key)
                or _CATALOGS.get("zh_HK", {}).get(candidate_key)
                or ""
            )
        if not source_template:
            continue

        parsed_payload = _extract_dynamic_payload(
            source_template=source_template,
            rendered_text=message.source_text,
            field_details=field_details if isinstance(field_details, dict) else None,
        )
        if not parsed_payload:
            continue

        template_len = len(source_template)
        if template_len > best_template_len:
            best_template_len = template_len
            best_key = candidate_key
    return best_key


def _recover_dynamic_message_without_msgid(
    message: TranslatableMessage,
    *,
    context: str,
    target_lang: str,
) -> str | None:
    _load_template_meta()
    _build_catalog_dynamic_index()

    # 1. Try scoped search first (Fast path)
    owner_context_key = _owner_context_key_for_message(message, context=context)
    cached_hit, best_key = _get_cached_dynamic_recovery_match(owner_context_key, message.source_text)
    if not cached_hit:
        candidate_keys = list(dict.fromkeys(
            _DYNAMIC_KEYS_BY_OWNER_CONTEXT.get(owner_context_key, [])
            + _CATALOG_DYNAMIC_KEYS_BY_OWNER_CONTEXT.get(owner_context_key, [])
        ))
        best_key = _find_best_matching_template(message, candidate_keys)
        _cache_dynamic_recovery_match(owner_context_key, message.source_text, best_key)

    # 2. If scoped search fails, try global search (Slow path fallback)
    # This handles cases where Nuitka obfuscates frame info, causing owner inference failure.
    if not best_key:
        global_owner_key = "__global__"
        global_hit, global_best_key = _get_cached_dynamic_recovery_match(global_owner_key, message.source_text)
        if not global_hit:
            global_keys = list(dict.fromkeys(list(_DYNAMIC_RECOVERY_KEYS) + list(_CATALOG_DYNAMIC_KEYS)))
            global_best_key = _find_best_matching_template(message, global_keys)
            _cache_dynamic_recovery_match(global_owner_key, message.source_text, global_best_key)
        best_key = global_best_key

    if not best_key:
        return None

    rendered = _render_dynamic_candidate_message(message, key=best_key, target_lang=target_lang)
    if rendered is not None:
        _telemetry_warn("dynamic_without_msgid_recovered", best_key)
    return rendered


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


@lru_cache(maxsize=1)
def _build_opencc_s2t_converter():
    try:
        OpenCC = importlib.import_module("opencc").OpenCC
        return OpenCC("s2t")
    except Exception:
        return None


def _zh_hk_fallback_text(text: str) -> str:
    converter = _build_opencc_s2t_converter()
    if converter is None:
        return text
    try:
        return converter.convert(text)
    except Exception:
        return text


def _render_dynamic_message(message: TranslatableMessage, *, key: str, target_lang: str) -> str:
    source_template = message.template_skeleton or message.source_text
    payload = message.kwargs or {}
    owner_context_key = _owner_context_key_from_i18n_key(key)
    payload = _localize_dynamic_payload_values(
        payload,
        owner_context_key=owner_context_key,
        target_lang=target_lang,
    )
    original_rendered = message.source_text

    translated_template = _CATALOGS.get(target_lang, {}).get(key)
    if translated_template is None and target_lang == "zh_HK":
        translated_template = _CATALOGS.get("zh_CN", {}).get(key)
        if translated_template is not None:
            translated_template = _zh_hk_fallback_text(translated_template)
    if translated_template is None:
        translated_template = _CATALOGS.get(message.source_lang, {}).get(key)
    # Context-aware fallback: allow ui/log catalogs to share the same dynamic msgid
    # when one side has no explicit seeded entry yet.
    if translated_template is None and ".ui." in key:
        log_key = key.replace(".ui.", ".log.", 1)
        translated_template = (
            _CATALOGS.get(target_lang, {}).get(log_key)
            or _CATALOGS.get(message.source_lang, {}).get(log_key)
        )
        if translated_template is None and target_lang == "zh_HK":
            translated_template = _CATALOGS.get("zh_CN", {}).get(log_key)
            if translated_template is not None:
                translated_template = _zh_hk_fallback_text(translated_template)
    if translated_template is None and ".log." in key:
        ui_key = key.replace(".log.", ".ui.", 1)
        translated_template = (
            _CATALOGS.get(target_lang, {}).get(ui_key)
            or _CATALOGS.get(message.source_lang, {}).get(ui_key)
        )
        if translated_template is None and target_lang == "zh_HK":
            translated_template = _CATALOGS.get("zh_CN", {}).get(ui_key)
            if translated_template is not None:
                translated_template = _zh_hk_fallback_text(translated_template)
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
        rendered = _render_dynamic_candidate_message(message, key=key, target_lang=target_lang)
        if rendered is not None:
            return rendered
        return message.source_text

    # Nuitka/compiled fallback: if AST import rewrite metadata is unavailable,
    # an author-side f-string with explicit msgid may reach here as a pre-rendered
    # static string without kwargs. Recover by reverse-parsing through template_meta.
    if message.msgid_explicit and message.msgid and not message.kwargs:
        if _is_dynamic_recovery_key(key):
            rendered = _render_dynamic_candidate_message(message, key=key, target_lang=target_lang)
            if rendered is not None:
                _telemetry_warn("dynamic_msgid_recovered_without_rewrite", key)
                return rendered

    translated = _CATALOGS.get(target_lang, {}).get(key)
    if translated is None and not message.msgid_explicit:
        recovered_static = _recover_static_message_without_msgid(message, context=context, target_lang=target_lang)
        if recovered_static is not None:
            return _safe_format(recovered_static, message.kwargs)
        if not message.kwargs:
            recovered_dynamic = _recover_dynamic_message_without_msgid(message, context=context, target_lang=target_lang)
            if recovered_dynamic is not None:
                return recovered_dynamic
    if translated is None and target_lang == "zh_HK":
        zh_cn_value = _CATALOGS.get("zh_CN", {}).get(key)
        if zh_cn_value is not None:
            translated = _zh_hk_fallback_text(zh_cn_value)
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
        if isinstance(value, TranslatableString):
            value = value.i18n_msg
        if not isinstance(value, TranslatableMessage):
            return str(value)

        current_lang = _resolve_lang()
        if context == "log":
            mode = _log_mode(levelno or logging.INFO)
            source_text = translate_message(value, context="log", target_lang=DEFAULT_SOURCE_LANG)
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
