#!/usr/bin/env python
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import string
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.framework.core.module_system.naming import humanize_name, infer_module_id
from app.framework.i18n.runtime import (
    TranslatableMessage,
    build_key,
    classify_source_language,
    validate_msgid,
)
from app.framework.i18n.template_render import extract_template_field_details

APP_ROOT = ROOT / "app"
MODULES_ROOT = APP_ROOT / "features" / "modules"
FEATURES_UTILS_ROOT = APP_ROOT / "features" / "utils"
FRAMEWORK_ROOT = APP_ROOT / "framework"
SUPPORTED_SOURCE_LANGS = ["en", "zh_CN"]

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
PERCENT_TOKEN_RE = re.compile(
    r"%(?:\((?P<named>[A-Za-z_][A-Za-z0-9_]*)\))?"
    r"(?P<spec>[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%])"
)
HASHLIKE_SUFFIX_RE = re.compile(r"^(?:[0-9a-f]{8,}|h[0-9a-f]{6,}|txt_[0-9a-f]{8,}|tmpl_[0-9a-f]{8,})$")
LABEL_KEY_RE = re.compile(r"^module\.([A-Za-z0-9_]+)\.field\.([A-Za-z0-9_]+)\.label$")


def _canonicalize_template_ignoring_spec(template: str) -> str:
    formatter = string.Formatter()
    chunks: list[str] = []
    for literal, field_name, _format_spec, _conversion in formatter.parse(template or ""):
        chunks.append(literal or "")
        if field_name:
            base = field_name.split("[", 1)[0].split(".", 1)[0]
            chunks.append("{" + (base or "value") + "}")
    return "".join(chunks)


def _canonicalize_template_structure(template: str) -> str:
    formatter = string.Formatter()
    chunks: list[str] = []
    for literal, field_name, _format_spec, _conversion in formatter.parse(template or ""):
        chunks.append(literal or "")
        if field_name:
            chunks.append("{}")
    return "".join(chunks)


def _safe_source_lang(text: str, *, default: str = "en") -> str:
    raw = str(text or "")
    try:
        lang = classify_source_language(raw)
    except Exception:
        has_han = any("\u4e00" <= ch <= "\u9fff" for ch in raw)
        return "zh_CN" if has_han else default
    return lang if lang in SUPPORTED_SOURCE_LANGS else default


def _safe_source_lang_with_mixed(text: str, *, default: str = "en") -> tuple[str, bool]:
    raw = str(text or "")
    try:
        lang = classify_source_language(raw)
        if lang not in SUPPORTED_SOURCE_LANGS:
            lang = default
        return lang, False
    except Exception:
        has_han = any("\u4e00" <= ch <= "\u9fff" for ch in raw)
        has_latin = bool(re.search(r"[A-Za-z]", raw))
        lang = "zh_CN" if has_han else default
        return lang, bool(has_han and has_latin)


def _template_spec_score(template: str) -> tuple[int, int]:
    formatter = string.Formatter()
    spec_count = 0
    field_count = 0
    for _literal, field_name, format_spec, conversion in formatter.parse(template or ""):
        if not field_name:
            continue
        field_count += 1
        if (format_spec or "") or (conversion or ""):
            spec_count += 1
    return spec_count, field_count


def _key_semantic_score(key: str, template: str) -> tuple[int, int, int, int]:
    suffix = key.rsplit(".", 1)[-1]
    is_semantic = 0 if HASHLIKE_SUFFIX_RE.fullmatch(suffix) else 1
    spec_count, field_count = _template_spec_score(template)
    generic_field_penalty = template.count("{value_") + template.count("{value}")
    return (is_semantic, spec_count, field_count, -generic_field_penalty)


def _clean_widget_label(param_name: str) -> str:
    cleaned = re.sub(r"^(SpinBox|ComboBox|CheckBox|LineEdit|DoubleSpinBox|Slider|TextEdit)_", "", str(param_name or ""))
    return humanize_name(cleaned)


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _translatable_literal(node: ast.AST) -> str | None:
    value = _literal(node)
    if isinstance(value, str):
        text = value.strip()
        return text or None

    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    helper = node.func.id

    if helper == "_" and node.args:
        inner = _literal(node.args[0])
        if isinstance(inner, str):
            text = inner.strip()
            return text or None
        return None

    if helper in {"ui_text", "_ui_text"}:
        if node.args:
            zh_raw = _literal(node.args[0])
            if isinstance(zh_raw, str) and zh_raw.strip():
                return zh_raw.strip()
        if len(node.args) >= 2:
            en_raw = _literal(node.args[1])
            if isinstance(en_raw, str) and en_raw.strip():
                return en_raw.strip()
    return None


def _extract_fields(fields_node: ast.AST) -> dict[str, dict[str, str | None]]:
    result: dict[str, dict[str, str | None]] = {}
    if not isinstance(fields_node, ast.Dict):
        return result

    for key_node, value_node in zip(fields_node.keys, fields_node.values):
        param_name = _literal(key_node)
        if not isinstance(param_name, str):
            continue

        field_id = param_name
        label = _clean_widget_label(param_name)
        help_text = None

        value = _translatable_literal(value_node)
        if isinstance(value, str):
            label = value
        elif isinstance(value_node, ast.Call) and isinstance(value_node.func, ast.Name) and value_node.func.id == "Field":
            label_explicit = False
            for kw in value_node.keywords:
                if kw.arg == "id":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        field_id = v.strip()
                elif kw.arg == "label":
                    v = _translatable_literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        label = v.strip()
                        label_explicit = True
                elif kw.arg == "help":
                    v = _translatable_literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        help_text = v.strip()
            if not label_explicit:
                label = _clean_widget_label(field_id)

        result[param_name] = {
            "field_id": field_id,
            "label": label,
            "help": help_text,
        }
    return result


def _target_name(node: ast.AST) -> str:
    if isinstance(node, ast.FunctionDef):
        return node.name
    if isinstance(node, ast.ClassDef):
        return node.name
    return "module"


def _extract_actions(actions_node: ast.AST) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if not isinstance(actions_node, ast.Dict):
        return result

    for key_node, value_node in zip(actions_node.keys, actions_node.values):
        label = _translatable_literal(key_node)
        if not isinstance(label, str) or not label.strip():
            continue

        method_name = ""
        raw_value = _literal(value_node)
        if isinstance(raw_value, str):
            method_name = raw_value.strip()
        elif isinstance(value_node, ast.Dict):
            for inner_key_node, inner_value_node in zip(value_node.keys, value_node.values):
                inner_key = _literal(inner_key_node)
                if inner_key in {"method", "name"}:
                    inner_val = _literal(inner_value_node)
                    if isinstance(inner_val, str):
                        method_name = inner_val.strip()
                        break

        if not method_name or re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", method_name) is None:
            continue
        result.append((label.strip(), method_name))
    return result


def _module_owner_from_i18n_dir(owner_dir: str) -> tuple[str, str | None]:
    normalized = str(owner_dir or "").replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    if len(parts) >= 4 and parts[0] == "app" and parts[1] == "features" and parts[2] == "modules":
        return "module", parts[3]
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "features" and parts[2] == "utils":
        return "module", "utils"
    return "framework", None


def _module_i18n_tokens(meta: Any) -> list[str]:
    out: list[str] = []

    def _add(value: str | None) -> None:
        token = str(value or "").strip()
        if token and token not in out:
            out.append(token)

    raw_id = str(getattr(meta, "id", "") or "").strip()
    _add(raw_id)
    if raw_id.startswith("task_"):
        _add(raw_id[5:])

    name_msgid = str(getattr(meta, "name_msgid", "") or "").strip()
    m = re.fullmatch(r"module\.([A-Za-z0-9_]+)\.title", name_msgid)
    if m:
        _add(m.group(1))

    if not out:
        _add("module")
    return out


def _ascii_key(text: str, *, default: str = "group", max_len: int = 80) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if max_len > 0:
        normalized = normalized[:max_len].rstrip("_")
    return normalized or default


def _field_tokens(field: Any) -> list[str]:
    out: list[str] = []

    def _add(value: str | None) -> None:
        token = str(value or "").strip()
        if token and token not in out:
            out.append(token)

    _add(str(getattr(field, "field_id", "") or ""))
    _add(str(getattr(field, "param_name", "") or ""))

    label_key = str(getattr(field, "label_key", "") or "")
    m = LABEL_KEY_RE.fullmatch(label_key)
    if m:
        _add(m.group(2))

    return out


def _normalize_option(option: Any) -> tuple[Any, str | None]:
    if isinstance(option, dict):
        if "value" in option:
            value = option.get("value")
            label = option.get("label")
            return value, str(label) if label is not None else None
        if len(option) == 1:
            value, label = next(iter(option.items()))
            return value, str(label)

    if isinstance(option, (tuple, list)) and len(option) == 2:
        first, second = option
        if isinstance(first, str) and not isinstance(second, str):
            return second, first
        if isinstance(second, str):
            return first, second
        return first, None

    return option, None


def _extract_option_labels(options: Any) -> list[tuple[str, str]]:
    if options is None:
        return []

    if isinstance(options, (list, tuple, set)):
        raw_items = list(options)
    else:
        raw_items = [options]

    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        value, label = _normalize_option(item)
        if not isinstance(label, str) or not label.strip():
            continue
        value_token = str(value)
        rec = (value_token, label.strip())
        if rec in seen:
            continue
        seen.add(rec)
        out.append(rec)
    return out


def _extract_action_specs(actions: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if not isinstance(actions, dict):
        return out

    for raw_label, raw_spec in actions.items():
        label = str(raw_label or "").strip()
        if not label:
            continue

        method = ""
        if isinstance(raw_spec, str):
            method = raw_spec.strip()
        elif isinstance(raw_spec, dict):
            method = str(raw_spec.get("method") or raw_spec.get("name") or "").strip()

        if not method or re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", method) is None:
            continue
        out.append((label, method))
    return out


def _extract_declarations_from_registry() -> list[tuple[str, str | None, str, str, str]]:
    try:
        from app.framework.core.module_system.registry import get_all_modules
    except Exception:
        return []

    try:
        metas = list(get_all_modules())
    except Exception:
        return []

    out: list[tuple[str, str | None, str, str, str]] = []
    seen: set[tuple[str, str | None, str, str, str]] = set()

    def _add(owner_scope: str, owner_module: str | None, key: str, text: str) -> None:
        value = str(text or "").strip()
        if not key or not value:
            return
        source_lang = _safe_source_lang(value, default="en")
        rec = (owner_scope, owner_module, key, value, source_lang)
        if rec in seen:
            return
        seen.add(rec)
        out.append(rec)

    for meta in metas:
        owner_scope, owner_module = _module_owner_from_i18n_dir(str(getattr(meta, "i18n_owner_dir", "") or ""))
        module_tokens = _module_i18n_tokens(meta)

        title_key = str(getattr(meta, "name_msgid", "") or "").strip()
        if not title_key:
            title_key = f"module.{module_tokens[0]}.title"
        _add(owner_scope, owner_module, title_key, str(getattr(meta, "name", "") or ""))

        description = str(getattr(meta, "description", "") or "").strip()
        if description:
            for token in module_tokens:
                _add(owner_scope, owner_module, f"module.{token}.description", description)

        schema = list(getattr(meta, "config_schema", []) or [])
        for field in schema:
            field_keys = _field_tokens(field)
            label_key = str(getattr(field, "label_key", "") or "").strip()
            if not label_key:
                label_key = f"module.{module_tokens[0]}.field.{str(getattr(field, 'field_id', '') or '')}.label"
            label_default = str(getattr(field, "label_default", "") or "").strip()
            if label_default:
                _add(owner_scope, owner_module, label_key, label_default)

            help_key = str(getattr(field, "help_key", "") or "").strip()
            help_default = str(getattr(field, "help_default", "") or "").strip()
            if help_key and help_default:
                _add(owner_scope, owner_module, help_key, help_default)

            description_md = str(getattr(field, "description_md", "") or "").strip()
            if description_md:
                for token in module_tokens:
                    for field_token in field_keys:
                        _add(
                            owner_scope,
                            owner_module,
                            f"module.{token}.field.{field_token}.description",
                            description_md,
                        )

            group_name = str(getattr(field, "group", "") or "").strip()
            if group_name:
                group_key = _ascii_key(group_name, default="group", max_len=80)
                for token in module_tokens:
                    _add(owner_scope, owner_module, f"module.{token}.group.{group_key}", group_name)
                    # raw-text alias keeps non-Latin group labels stable for i18n lookup.
                    _add(owner_scope, owner_module, f"module.{token}.group.{group_name}", group_name)

            option_entries = _extract_option_labels(getattr(field, "options", None))
            for option_value, option_label in option_entries:
                for token in module_tokens:
                    for field_token in field_keys:
                        _add(
                            owner_scope,
                            owner_module,
                            f"module.{token}.field.{field_token}.option.{option_value}",
                            option_label,
                        )

        for action_label, method_name in _extract_action_specs(getattr(meta, "actions", None)):
            for token in module_tokens:
                _add(
                    owner_scope,
                    owner_module,
                    f"module.{token}.action.{method_name}.label",
                    action_label,
                )

    return out


def _declaration_title_key(node: ast.AST, module_id: str) -> str:
    return f"module.{module_id}.title"


def _owner_from_file(path: Path) -> tuple[str, str | None]:
    rel = path.relative_to(ROOT)
    parts = list(rel.parts)
    if len(parts) >= 5 and parts[0] == "app" and parts[1] == "features" and parts[2] == "modules":
        return "module", parts[3]
    if len(parts) >= 4 and parts[0] == "app" and parts[1] == "features" and parts[2] == "utils":
        return "module", "utils"
    return "framework", None


def _owner_i18n_dir(owner_scope: str, owner_module: str | None) -> Path:
    if owner_scope == "module" and owner_module:
        if owner_module == "utils":
            return FEATURES_UTILS_ROOT / "i18n"
        return MODULES_ROOT / owner_module / "i18n"
    return FRAMEWORK_ROOT / "i18n"


def _existing_owner_i18n_dirs() -> dict[tuple[str, str | None], Path]:
    owners: dict[tuple[str, str | None], Path] = {("framework", None): FRAMEWORK_ROOT / "i18n"}
    if FEATURES_UTILS_ROOT.exists():
        owners[("module", "utils")] = FEATURES_UTILS_ROOT / "i18n"
    if MODULES_ROOT.exists():
        for module_dir in MODULES_ROOT.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("__"):
                continue
            owners[("module", module_dir.name)] = module_dir / "i18n"
    return owners


def _extract_declarations_from_file(path: Path, tree: ast.AST) -> list[tuple[str, str | None, str, str, str]]:
    out: list[tuple[str, str | None, str, str, str]] = []
    owner_scope, owner_module = _owner_from_file(path)
    if owner_scope != "module" or owner_module is None:
        return out

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Name):
                continue
            if deco.func.id not in {"on_demand_module", "periodic_module"}:
                continue

            title = _literal(deco.args[0]) if deco.args else None
            if not isinstance(title, str):
                continue
            module_id = None
            fields: dict[str, dict[str, str | None]] = {}
            actions: list[tuple[str, str]] = []
            for kw in deco.keywords:
                if kw.arg == "module_id":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        module_id = v.strip()
                elif kw.arg == "fields":
                    fields = _extract_fields(kw.value)
                elif kw.arg == "actions":
                    actions = _extract_actions(kw.value)

            if not module_id:
                name = _target_name(node)
                dummy = type(name, (), {})
                module_id = infer_module_id(dummy)

            source_lang = _safe_source_lang(title, default="en")

            out.append((owner_scope, owner_module, _declaration_title_key(node, module_id), title, source_lang))
            for param_name, meta in fields.items():
                field_id = meta["field_id"] or param_name
                field_label = str(meta["label"] or _clean_widget_label(field_id))
                field_label_lang = _safe_source_lang(field_label, default="en")
                out.append(
                    (
                        owner_scope,
                        owner_module,
                        f"module.{module_id}.field.{field_id}.label",
                        field_label,
                        field_label_lang,
                    )
                )
                if meta.get("help"):
                    help_text = str(meta["help"])
                    help_lang = _safe_source_lang(help_text, default="en")
                    out.append(
                        (
                            owner_scope,
                            owner_module,
                            f"module.{module_id}.field.{field_id}.help",
                            help_text,
                            help_lang,
                        )
                    )
            for action_label, method_name in actions:
                action_lang = _safe_source_lang(action_label, default="en")
                out.append(
                    (
                        owner_scope,
                        owner_module,
                        f"module.{module_id}.action.{method_name}.label",
                        action_label,
                        action_lang,
                    )
                )
    return out


def _build_parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _detect_context(node: ast.Call, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    if isinstance(parent, ast.Call):
        func = parent.func
        if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
            if node in parent.args:
                return "log"
            for kw in parent.keywords:
                if kw.value is node:
                    return "log"
    return "ui"


def _nearest_scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[str, str | None]:
    cur = node
    func_name = ""
    class_name = None
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, ast.FunctionDef) and not func_name:
            func_name = cur.name
        if isinstance(cur, ast.ClassDef) and class_name is None:
            class_name = cur.name
    return func_name, class_name


def _expr_to_field_name(expr: ast.AST, idx: int) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        parts: list[str] = []
        cur: ast.AST | None = expr
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        parts = list(reversed(parts))
        candidate = "_".join(parts)
        if candidate:
            return candidate
    return f"value_{idx}"


def _escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _extract_dynamic_template(joined: ast.JoinedStr, state_idx: list[int], used: set[str]) -> tuple[str, list[str]]:
    def _format_spec_to_text(spec: ast.AST | None) -> str | None:
        if spec is None:
            return ""
        if isinstance(spec, ast.Constant) and isinstance(spec.value, str):
            return spec.value
        if isinstance(spec, ast.JoinedStr):
            chunks: list[str] = []
            for value in spec.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    chunks.append(value.value)
                    continue
                return None
            return "".join(chunks)
        return None

    def _placeholder(item: ast.FormattedValue, field: str) -> str | None:
        conversion = ""
        if item.conversion != -1:
            try:
                conversion = f"!{chr(item.conversion)}"
            except Exception:
                return None
        format_spec = _format_spec_to_text(item.format_spec)
        if format_spec is None:
            return None
        spec_suffix = f":{format_spec}" if format_spec else ""
        return "{" + field + conversion + spec_suffix + "}"

    chunks: list[str] = []
    fields: list[str] = []
    
    for value in joined.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            # IMPORTANT: Match transformer by escaping braces in literal parts
            chunks.append(_escape_braces(value.value))
            continue
        if not isinstance(value, ast.FormattedValue):
            continue
        
        base_key = _expr_to_field_name(value.value, state_idx[0])
        field_name = base_key
        if field_name in used:
            while True:
                state_idx[0] += 1
                field_name = f"{base_key}_{state_idx[0]}"
                if field_name not in used:
                    break
        
        used.add(field_name)
        fields.append(field_name)
        placeholder = _placeholder(value, field_name)
        chunks.append(placeholder if placeholder is not None else ("{" + field_name + "}"))
        state_idx[0] += 1
    return "".join(chunks), fields


def _flatten_concat_parts(expr: ast.AST) -> list[ast.AST] | None:
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _flatten_concat_parts(expr.left)
        right = _flatten_concat_parts(expr.right)
        if left is None or right is None:
            return None
        return left + right
    return [expr]


def _extract_dynamic_template_from_expr(expr: ast.AST, parents: dict[ast.AST, ast.AST], depth: int = 0) -> tuple[str, list[str]] | None:
    if depth > 5: # Increased depth for complex logs
        return None
    
    parts = _flatten_concat_parts(expr)
    if not parts:
        return None
    
    # Check if there is actually any dynamic content
    has_dynamic = False
    for p in parts:
        if isinstance(p, (ast.JoinedStr, ast.FormattedValue)):
            has_dynamic = True
            break
        if isinstance(p, ast.BinOp): # Might be complex
            has_dynamic = True
            break
    
    if not has_dynamic and len(parts) == 1:
        # Simple constants are handled by the main loop
        return None

    state_idx = [1]
    used: set[str] = set()
    all_chunks = []
    all_fields = []
    
    for part in parts:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            all_chunks.append(_escape_braces(part.value))
        elif isinstance(part, ast.JoinedStr):
            tmpl, flds = _extract_dynamic_template(part, state_idx, used)
            all_chunks.append(tmpl)
            all_fields.extend(flds)
        else:
            # Treats other expressions as generic placeholders
            base_key = _expr_to_field_name(part, state_idx[0])
            field_name = base_key
            if field_name in used:
                while True:
                    state_idx[0] += 1
                    field_name = f"{base_key}_{state_idx[0]}"
                    if field_name not in used:
                        break
            used.add(field_name)
            all_chunks.append("{" + field_name + "}")
            all_fields.append(field_name)
            state_idx[0] += 1
            
    return "".join(all_chunks), all_fields


def _extract_msgid(node: ast.Call) -> str | None:
    for kw in node.keywords:
        if kw.arg == "msgid":
            v = _literal(kw.value)
            if isinstance(v, str) and v.strip():
                return validate_msgid(v.strip())
    return None


def _extract_marked_strings_from_file(
    path: Path,
    tree: ast.AST,
) -> tuple[
    list[tuple[str, str | None, str, str, str]],
    dict[tuple[str, str | None], dict[str, dict[str, Any]]],
    dict[tuple[str, str | None], dict[str, dict[str, Any]]],
]:
    out: list[tuple[str, str | None, str, str, str]] = []
    dynamic_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}
    callsite_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}
    parents = _build_parents(tree)
    owner_scope, owner_module = _owner_from_file(path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        
        is_i18n_call = isinstance(node.func, ast.Name) and node.func.id == "_"
        is_logger_call = False
        
        # Detect logger.info(...) or self.logger.warning(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS:
            val = node.func.value
            if isinstance(val, ast.Name) and "logger" in val.id.lower():
                is_logger_call = True
            elif isinstance(val, ast.Attribute) and "logger" in val.attr.lower():
                is_logger_call = True

        if not (is_i18n_call or is_logger_call):
            continue
        if not node.args:
            continue

        msgid = _extract_msgid(node) if is_i18n_call else None
        context = _detect_context(node, parents) if is_i18n_call else "log"
        rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
        callsite_key = f"{rel_path}:{node.lineno}:{node.col_offset}"
        owner = (owner_scope, owner_module)

        first_arg = node.args[0]
        literal_dynamic: tuple[str, list[str]] | None = None
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            template_text = first_arg.value
            template_fields = list(extract_template_field_details(template_text).keys())
            runtime_kw_fields = [
                kw.arg
                for kw in node.keywords
                if isinstance(kw.arg, str) and kw.arg != "msgid" and not kw.arg.startswith("__i18n_")
            ]
            # Treat literal templates with explicit kwargs as dynamic templates so
            # template_meta/source_map stay in sync with named placeholders.
            if template_fields and runtime_kw_fields:
                literal_dynamic = (template_text, template_fields)

        if literal_dynamic is not None:
            template, fields = literal_dynamic
            dynamic_msgid = msgid
            source_lang, mixed_source_template = _safe_source_lang_with_mixed(template, default="en")
            message = TranslatableMessage(
                source_text=template,
                source_lang=source_lang,
                msgid=dynamic_msgid,
                kwargs={},
                owner_scope=owner_scope,
                owner_module=owner_module,
                dynamic=True,
                template_skeleton=template,
                template_fields=list(fields),
            )
            key = build_key(message, context=context)
            out.append((owner_scope, owner_module, key, template, source_lang))

            func_name, class_name = _nearest_scope(node, parents)
            rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
            template_hash = hashlib.sha1(template.encode("utf-8")).hexdigest()
            dynamic_meta.setdefault(owner, {})[key] = {
                "kind": "dynamic_template",
                "template_id": dynamic_msgid,
                "msgid": dynamic_msgid,
                "source_template": template,
                "fields": list(fields),
                "field_details": extract_template_field_details(template),
                "owner_scope": owner_scope,
                "owner_module": owner_module,
                "file_path": rel_path,
                "line": int(getattr(node, "lineno", 0)),
                "col": int(getattr(node, "col_offset", 0)),
                "function_name": func_name,
                "class_name": class_name,
                "context": context,
                "source_language": source_lang,
                "template_hash": template_hash,
                "callsite_key": callsite_key,
                "is_runtime_visible": True,
                "mixed_source_template": mixed_source_template,
            }
            callsite_meta.setdefault(owner, {})[callsite_key] = {
                "kind": "dynamic_template",
                "key": key,
                "msgid": dynamic_msgid,
                "source_template": template,
                "fields": list(fields),
                "field_details": extract_template_field_details(template),
                "owner_scope": owner_scope,
                "owner_module": owner_module,
                "file_path": rel_path,
                "line": int(getattr(node, "lineno", 0)),
                "col": int(getattr(node, "col_offset", 0)),
                "context": context,
            }
            continue

        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            text = first_arg.value
            if not text.strip():
                # Ignore intentionally empty placeholders like _("").
                continue
            static_msgid = msgid
            source_lang = _safe_source_lang(text, default="en")
            message = TranslatableMessage(
                source_text=text,
                source_lang=source_lang,
                msgid=static_msgid,
                kwargs={},
                owner_scope=owner_scope,
                owner_module=owner_module,
                dynamic=False,
            )
            key = build_key(message, context=context)
            out.append((owner_scope, owner_module, key, text, source_lang))
            callsite_meta.setdefault(owner, {})[callsite_key] = {
                "kind": "static_literal",
                "key": key,
                "msgid": static_msgid,
                "source_text": text,
                "owner_scope": owner_scope,
                "owner_module": owner_module,
                "file_path": rel_path,
                "line": int(getattr(node, "lineno", 0)),
                "col": int(getattr(node, "col_offset", 0)),
                "context": context,
            }
            continue

        extracted_dynamic = _extract_dynamic_template_from_expr(first_arg, parents)
        if extracted_dynamic is not None:
            template, fields = extracted_dynamic
            dynamic_msgid = msgid
            source_lang, mixed_source_template = _safe_source_lang_with_mixed(template, default="en")
            message = TranslatableMessage(
                source_text=template,
                source_lang=source_lang,
                msgid=dynamic_msgid,
                kwargs={},
                owner_scope=owner_scope,
                owner_module=owner_module,
                dynamic=True,
                template_skeleton=template,
                template_fields=list(fields),
            )
            key = build_key(message, context=context)
            out.append((owner_scope, owner_module, key, template, source_lang))

            func_name, class_name = _nearest_scope(node, parents)
            rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
            template_hash = hashlib.sha1(template.encode("utf-8")).hexdigest()
            dynamic_meta.setdefault(owner, {})[key] = {
                "kind": "dynamic_template",
                "template_id": dynamic_msgid,
                "msgid": dynamic_msgid,
                "source_template": template,
                "fields": list(fields),
                "field_details": extract_template_field_details(template),
                "owner_scope": owner_scope,
                "owner_module": owner_module,
                "file_path": rel_path,
                "line": int(getattr(node, "lineno", 0)),
                "col": int(getattr(node, "col_offset", 0)),
                "function_name": func_name,
                "class_name": class_name,
                "context": context,
                "source_language": source_lang,
                "template_hash": template_hash,
                "callsite_key": callsite_key,
                "is_runtime_visible": True,
                "mixed_source_template": mixed_source_template,
            }
            callsite_meta.setdefault(owner, {})[callsite_key] = {
                "kind": "dynamic_template",
                "key": key,
                "msgid": dynamic_msgid,
                "source_template": template,
                "fields": list(fields),
                "field_details": extract_template_field_details(template),
                "owner_scope": owner_scope,
                "owner_module": owner_module,
                "file_path": rel_path,
                "line": int(getattr(node, "lineno", 0)),
                "col": int(getattr(node, "col_offset", 0)),
                "context": context,
            }
            continue

        expr_repr = ""
        try:
            expr_repr = ast.unparse(first_arg)
        except Exception:
            expr_repr = type(first_arg).__name__
        callsite_meta.setdefault(owner, {})[callsite_key] = {
            "kind": "dynamic_candidate",
            "key": None,
            "msgid": msgid,
            "raw_expression": expr_repr,
            "owner_scope": owner_scope,
            "owner_module": owner_module,
            "file_path": rel_path,
            "line": int(getattr(node, "lineno", 0)),
            "col": int(getattr(node, "col_offset", 0)),
            "context": context,
        }

    return out, dynamic_meta, callsite_meta


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            return data
    except Exception:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _owner_target_keys(
    by_lang: dict[str, dict[str, str]],
    source_map: dict[str, str],
    dynamic_meta: dict[str, dict[str, Any]],
) -> set[str]:
    keys: set[str] = set(source_map.keys())
    keys.update(dynamic_meta.keys())
    for payload in by_lang.values():
        keys.update(payload.keys())
    return keys


def _replace_lang_payload(
    *,
    current: dict[str, Any],
    extracted_for_lang: dict[str, str],
    target_keys: set[str],
) -> dict[str, str]:
    def _canonical_drop_numeric_tail(key: str) -> str:
        if "." not in key:
            return key
        prefix, suffix = key.rsplit(".", 1)
        normalized = re.sub(r"_\d+$", "", suffix)
        if normalized == suffix:
            return key
        return f"{prefix}.{normalized}"

    alias_candidates: dict[str, list[str]] = {}
    for cur_key in current.keys():
        if not isinstance(cur_key, str):
            continue
        alias_key = _canonical_drop_numeric_tail(cur_key)
        if alias_key == cur_key:
            continue
        alias_candidates.setdefault(alias_key, []).append(cur_key)

    replacement: dict[str, str] = {}
    for key, value in extracted_for_lang.items():
        replacement[str(key)] = str(value)
    for key in sorted(target_keys):
        if key in replacement:
            continue
        cur_val = current.get(key)
        if isinstance(cur_val, str):
            replacement[key] = cur_val
            continue
        # Backward-compat migration: preserve old numbered-tail keys such as
        # "...timeout_2" when extractor now emits "...timeout".
        aliases = alias_candidates.get(key, [])
        if len(aliases) == 1:
            alias_val = current.get(aliases[0])
            if isinstance(alias_val, str):
                replacement[key] = alias_val
    return replacement


def _replace_source_map_payload(
    *,
    current: dict[str, Any],
    extracted_source_map: dict[str, str],
    by_lang: dict[str, dict[str, str]],
    target_keys: set[str],
) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in sorted(target_keys):
        src = extracted_source_map.get(key)
        if src not in SUPPORTED_SOURCE_LANGS:
            if key in by_lang.get("en", {}):
                src = "en"
            elif key in by_lang.get("zh_CN", {}):
                src = "zh_CN"
            else:
                existing = current.get(key)
                if isinstance(existing, str) and existing in SUPPORTED_SOURCE_LANGS:
                    src = existing
        if src in SUPPORTED_SOURCE_LANGS:
            out[key] = src
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract i18n entries from code. Default is replace/prune; use --incremental for merge-only mode."
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Incremental merge mode (legacy behavior): append/update keys without pruning stale entries.",
    )
    args = parser.parse_args()
    replace_mode = not args.incremental

    owner_lang_entries: dict[tuple[str, str | None], dict[str, dict[str, str]]] = {}
    owner_source_map: dict[tuple[str, str | None], dict[str, str]] = {}
    owner_dynamic_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}
    owner_callsite_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}
    declaration_entries = _extract_declarations_from_registry()
    use_registry_declarations = bool(declaration_entries)

    py_files = sorted(APP_ROOT.rglob("*.py"))
    for py in py_files:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        except Exception:
            continue

        entries = []
        if not use_registry_declarations:
            entries.extend(_extract_declarations_from_file(py, tree))
        extracted_entries, dynamic_meta, callsite_meta = _extract_marked_strings_from_file(py, tree)
        entries.extend(extracted_entries)

        for owner, records in dynamic_meta.items():
            owner_dynamic_meta.setdefault(owner, {}).update(records)
        for owner, records in callsite_meta.items():
            owner_callsite_meta.setdefault(owner, {}).update(records)

        for owner_scope, owner_module, key, value, source_lang in entries:
            if source_lang not in SUPPORTED_SOURCE_LANGS:
                continue
            owner = (owner_scope, owner_module)
            owner_lang_entries.setdefault(owner, {})
            owner_lang_entries[owner].setdefault(source_lang, {})
            owner_lang_entries[owner][source_lang][key] = value

            owner_source_map.setdefault(owner, {})
            prev = owner_source_map[owner].get(key)
            if prev and prev != source_lang:
                raise ValueError(
                    f"Conflicting source language for key {key}: {prev} vs {source_lang}"
                )
            owner_source_map[owner][key] = source_lang

    for owner_scope, owner_module, key, value, source_lang in declaration_entries:
        if source_lang not in SUPPORTED_SOURCE_LANGS:
            continue
        owner = (owner_scope, owner_module)
        owner_lang_entries.setdefault(owner, {})
        owner_lang_entries[owner].setdefault(source_lang, {})
        owner_lang_entries[owner][source_lang][key] = value

        owner_source_map.setdefault(owner, {})
        prev = owner_source_map[owner].get(key)
        if prev and prev != source_lang:
            raise ValueError(
                f"Conflicting source language for key {key}: {prev} vs {source_lang}"
            )
        owner_source_map[owner][key] = source_lang

    # Deduplicate dynamic templates that only differ by dropped format spec/conversion.
    for owner, records in list(owner_dynamic_meta.items()):
        by_canonical: dict[str, list[str]] = {}
        for key, meta in records.items():
            source_template = str(meta.get("source_template", "") or "")
            if not source_template:
                continue
            canonical = (
                _canonicalize_template_structure(source_template)
                + "||"
                + _canonicalize_template_ignoring_spec(source_template)
            )
            by_canonical.setdefault(canonical, []).append(key)

        for _canonical, keys in by_canonical.items():
            if len(keys) < 2:
                continue
            ordered = sorted(
                keys,
                key=lambda key: (
                    _key_semantic_score(
                        key,
                        str(records.get(key, {}).get("source_template", "") or ""),
                    ),
                    len(str(records.get(key, {}).get("source_template", "") or "")),
                ),
                reverse=True,
            )
            keep_key = ordered[0]
            for drop_key in ordered[1:]:
                source_lang = owner_source_map.get(owner, {}).get(drop_key)
                if source_lang:
                    owner_lang_entries.setdefault(owner, {}).setdefault(source_lang, {})
                    keep_val = owner_lang_entries[owner][source_lang].get(keep_key)
                    drop_val = owner_lang_entries[owner][source_lang].get(drop_key)
                    if keep_val is None and drop_val is not None:
                        owner_lang_entries[owner][source_lang][keep_key] = drop_val
                    owner_lang_entries[owner][source_lang].pop(drop_key, None)
                owner_source_map.get(owner, {}).pop(drop_key, None)
                records.pop(drop_key, None)

                for callsite in owner_callsite_meta.get(owner, {}).values():
                    if callsite.get("kind") != "dynamic_template":
                        continue
                    if callsite.get("key") == drop_key:
                        callsite["key"] = keep_key
                        keep_meta = records.get(keep_key, {})
                        callsite["msgid"] = keep_meta.get("msgid")
                        callsite["source_template"] = keep_meta.get("source_template")
                        callsite["fields"] = keep_meta.get("fields", [])
                        callsite["field_details"] = keep_meta.get("field_details", {})

    owners_to_update: set[tuple[str, str | None]] = set(owner_lang_entries.keys())
    owners_to_update.update(owner_source_map.keys())
    owners_to_update.update(owner_dynamic_meta.keys())
    existing_owner_dirs = _existing_owner_i18n_dirs()
    if replace_mode:
        owners_to_update.update(existing_owner_dirs.keys())

    updated_owners = 0
    for owner in sorted(owners_to_update, key=lambda item: (item[0], item[1] or "")):
        owner_scope, owner_module = owner
        by_lang = owner_lang_entries.get(owner, {})
        extracted_source_map = owner_source_map.get(owner, {})
        extracted_template_meta = owner_dynamic_meta.get(owner, {})
        target_keys = _owner_target_keys(by_lang, extracted_source_map, extracted_template_meta)

        i18n_dir = existing_owner_dirs.get(owner) or _owner_i18n_dir(owner_scope, owner_module)
        i18n_dir.mkdir(parents=True, exist_ok=True)

        existing_langs = {
            path.stem
            for path in i18n_dir.glob("*.json")
            if path.stem not in {"source_map", "template_meta"}
        }
        langs_to_process = set(SUPPORTED_SOURCE_LANGS)
        if replace_mode:
            langs_to_process.update(existing_langs)

        for lang in sorted(langs_to_process):
            path = i18n_dir / f"{lang}.json"
            current = _load_json(path)
            if not isinstance(current, dict):
                current = {}
            if replace_mode:
                replacement = _replace_lang_payload(
                    current=current,
                    extracted_for_lang=by_lang.get(lang, {}),
                    target_keys=target_keys,
                )
                if lang not in SUPPORTED_SOURCE_LANGS and not replacement:
                    path.unlink(missing_ok=True)
                    continue
                _save_json(path, replacement)
            else:
                if lang not in by_lang:
                    continue
                current.update(by_lang[lang])
                _save_json(path, current)

        source_map_path = i18n_dir / "source_map.json"
        source_map = _load_json(source_map_path)
        if not isinstance(source_map, dict):
            source_map = {}
        if replace_mode:
            source_map = _replace_source_map_payload(
                current=source_map,
                extracted_source_map=extracted_source_map,
                by_lang=by_lang,
                target_keys=target_keys,
            )
        else:
            source_map.update(extracted_source_map)
        _save_json(source_map_path, dict(sorted(source_map.items(), key=lambda x: x[0])))

        template_meta_path = i18n_dir / "template_meta.json"
        template_meta = _load_json(template_meta_path)
        if not isinstance(template_meta, dict):
            template_meta = {}
        if replace_mode:
            template_meta = dict(sorted(extracted_template_meta.items(), key=lambda x: x[0]))
        else:
            template_meta.update(extracted_template_meta)
        _save_json(template_meta_path, dict(sorted(template_meta.items(), key=lambda x: x[0])))

        # callsite metadata is intentionally not persisted as a standalone i18n
        # artifact anymore; source_map + template_meta already cover extraction
        # governance needs while reducing per-owner JSON clutter.

        updated_owners += 1

    print(f"mode={'replace' if replace_mode else 'incremental'}")
    print(f"updated_owners={updated_owners}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
