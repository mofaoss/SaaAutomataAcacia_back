#!/usr/bin/env python
from __future__ import annotations

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
FRAMEWORK_ROOT = APP_ROOT / "framework"
SUPPORTED_SOURCE_LANGS = ["en", "zh_CN"]

_EN_DECL_RE = re.compile(r"^[\x20-\x7E]+$")
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
PERCENT_TOKEN_RE = re.compile(
    r"%(?:\((?P<named>[A-Za-z_][A-Za-z0-9_]*)\))?"
    r"(?P<spec>[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%])"
)
HASHLIKE_SUFFIX_RE = re.compile(r"^(?:[0-9a-f]{8,}|h[0-9a-f]{6,}|txt_[0-9a-f]{8,}|tmpl_[0-9a-f]{8,})$")


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


def _validate_english_declaration(text: str, *, field: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{field} must be a non-empty English string")
    if not _EN_DECL_RE.fullmatch(text):
        raise ValueError(
            f"{field} must use English ASCII declaration text only (found unsupported chars): {text!r}"
        )


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
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
        label = humanize_name(param_name)
        help_text = None

        value = _literal(value_node)
        if isinstance(value, str):
            _validate_english_declaration(value, field=f"fields[{param_name}] label")
            label = value
        elif isinstance(value_node, ast.Call) and isinstance(value_node.func, ast.Name) and value_node.func.id == "Field":
            for kw in value_node.keywords:
                if kw.arg == "id":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        field_id = v.strip()
                elif kw.arg == "label":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        _validate_english_declaration(v.strip(), field=f"fields[{param_name}] label")
                        label = v.strip()
                elif kw.arg == "help":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        _validate_english_declaration(v.strip(), field=f"fields[{param_name}] help")
                        help_text = v.strip()

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


def _owner_from_file(path: Path) -> tuple[str, str | None]:
    rel = path.relative_to(ROOT)
    parts = list(rel.parts)
    if len(parts) >= 5 and parts[0] == "app" and parts[1] == "features" and parts[2] == "modules":
        return "module", parts[3]
    return "framework", None


def _owner_i18n_dir(owner_scope: str, owner_module: str | None) -> Path:
    if owner_scope == "module" and owner_module:
        return MODULES_ROOT / owner_module / "i18n"
    return FRAMEWORK_ROOT / "i18n"


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
            _validate_english_declaration(title, field=f"{path}: decorator title")

            module_id = None
            fields: dict[str, dict[str, str | None]] = {}
            for kw in deco.keywords:
                if kw.arg == "module_id":
                    v = _literal(kw.value)
                    if isinstance(v, str) and v.strip():
                        module_id = v.strip()
                elif kw.arg == "fields":
                    fields = _extract_fields(kw.value)

            if not module_id:
                dummy = type("Dummy", (), {"__name__": _target_name(node)})
                module_id = infer_module_id(dummy)

            out.append((owner_scope, owner_module, f"module.{module_id}.title", title, "en"))
            for param_name, meta in fields.items():
                field_id = meta["field_id"] or param_name
                out.append(
                    (
                        owner_scope,
                        owner_module,
                        f"module.{module_id}.field.{field_id}.label",
                        meta["label"] or humanize_name(param_name),
                        "en",
                    )
                )
                if meta.get("help"):
                    out.append(
                        (
                            owner_scope,
                            owner_module,
                            f"module.{module_id}.field.{field_id}.help",
                            str(meta["help"]),
                            "en",
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


def _extract_dynamic_template(joined: ast.JoinedStr) -> tuple[str, list[str]]:
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
    used: set[str] = set()
    idx = 1
    for value in joined.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            chunks.append(value.value)
            continue
        if not isinstance(value, ast.FormattedValue):
            continue
        field_name = _expr_to_field_name(value.value, idx)
        while field_name in used:
            idx += 1
            field_name = f"{field_name}_{idx}"
        used.add(field_name)
        fields.append(field_name)
        placeholder = _placeholder(value, field_name)
        chunks.append(placeholder if placeholder is not None else ("{" + field_name + "}"))
        idx += 1
    return "".join(chunks), fields


def _flatten_concat_parts(expr: ast.AST) -> list[ast.AST] | None:
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _flatten_concat_parts(expr.left)
        right = _flatten_concat_parts(expr.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(expr, (ast.Constant, ast.Name, ast.Attribute, ast.Subscript, ast.Call, ast.JoinedStr, ast.BinOp)):
        return [expr]
    return None


def _extract_dynamic_concat(expr: ast.AST) -> tuple[str, list[str]] | None:
    parts = _flatten_concat_parts(expr)
    if not parts or len(parts) < 2:
        return None
    chunks: list[str] = []
    fields: list[str] = []
    used: set[str] = set()
    idx = 1
    has_dynamic = False
    for part in parts:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            chunks.append(part.value)
            continue
        has_dynamic = True
        field = _expr_to_field_name(part, idx)
        while field in used:
            idx += 1
            field = f"{field}_{idx}"
        used.add(field)
        fields.append(field)
        chunks.append("{" + field + "}")
        idx += 1
    if not has_dynamic:
        return None
    return "".join(chunks), fields


def _extract_dynamic_format(expr: ast.AST) -> tuple[str, list[str]] | None:
    if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format"):
        return None
    base = expr.func.value
    if not (isinstance(base, ast.Constant) and isinstance(base.value, str)):
        return None
    fields: list[str] = []
    used: set[str] = set()
    idx = 1
    for _arg in expr.args:
        field = f"value_{idx}"
        while field in used:
            idx += 1
            field = f"value_{idx}"
        used.add(field)
        fields.append(field)
        idx += 1
    for kw in expr.keywords:
        if kw.arg and kw.arg not in used:
            used.add(kw.arg)
            fields.append(kw.arg)
    return base.value, fields


def _extract_dynamic_percent(expr: ast.AST) -> tuple[str, list[str]] | None:
    if not (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod)):
        return None
    if not (isinstance(expr.left, ast.Constant) and isinstance(expr.left.value, str)):
        return None
    fmt = expr.left.value
    fields: list[str] = []
    idx = 1
    chunks: list[str] = []
    cursor = 0
    for match in PERCENT_TOKEN_RE.finditer(fmt):
        chunks.append(fmt[cursor:match.start()])
        cursor = match.end()
        spec = match.group("spec")
        named = match.group("named")
        if spec == "%":
            chunks.append("%")
            continue
        if named:
            field = named
        else:
            field = f"value_{idx}"
            idx += 1
        fields.append(field)
        type_char = spec[-1]
        body = spec[:-1]
        conversion_suffix = ""
        format_suffix = ""
        if type_char in {"r", "a"}:
            conversion_suffix = f"!{type_char}"
            if body:
                format_suffix = f":{body}"
        else:
            format_type = type_char
            if type_char in {"i", "u"}:
                format_type = "d"
            if type_char == "s":
                format_suffix = f":{body}" if body else ""
            else:
                format_suffix = f":{body}{format_type}" if body else f":{format_type}"
        chunks.append("{" + field + conversion_suffix + format_suffix + "}")
    if not fields:
        return None
    chunks.append(fmt[cursor:])
    return "".join(chunks), fields


def _find_enclosing_stmt(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.stmt | None:
    cur: ast.AST | None = node
    while cur is not None:
        if isinstance(cur, ast.stmt):
            return cur
        cur = parents.get(cur)
    return None


def _find_enclosing_body(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> tuple[list[ast.stmt], int] | None:
    stmt = _find_enclosing_stmt(node, parents)
    if stmt is None:
        return None
    cur: ast.AST | None = stmt
    while cur is not None:
        parent = parents.get(cur)
        if parent is None:
            break
        for attr in ("body", "orelse", "finalbody"):
            seq = getattr(parent, attr, None)
            if isinstance(seq, list) and cur in seq:
                return seq, seq.index(cur)
        cur = parent
    return None


def _resolve_name_assignment_expr(name_node: ast.Name, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    body_info = _find_enclosing_body(name_node, parents)
    if body_info is None:
        return None
    body, idx = body_info
    for cursor in range(idx - 1, -1, -1):
        stmt = body[cursor]
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == name_node.id:
                    return stmt.value
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == name_node.id:
            return stmt.value
    return None


def _extract_dynamic_template_from_expr(expr: ast.AST, parents: dict[ast.AST, ast.AST], depth: int = 0) -> tuple[str, list[str]] | None:
    if depth > 2:
        return None
    if isinstance(expr, ast.JoinedStr):
        return _extract_dynamic_template(expr)
    from_concat = _extract_dynamic_concat(expr)
    if from_concat is not None:
        return from_concat
    from_format = _extract_dynamic_format(expr)
    if from_format is not None:
        return from_format
    from_percent = _extract_dynamic_percent(expr)
    if from_percent is not None:
        return from_percent
    if isinstance(expr, ast.Name):
        bound = _resolve_name_assignment_expr(expr, parents)
        if bound is not None:
            return _extract_dynamic_template_from_expr(bound, parents, depth + 1)
    return None


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
        if not (isinstance(node.func, ast.Name) and node.func.id == "_"):
            continue
        if not node.args:
            continue

        msgid = _extract_msgid(node)
        context = _detect_context(node, parents)
        rel_path = str(path.relative_to(ROOT)).replace("\\", "/")
        callsite_key = f"{rel_path}:{node.lineno}:{node.col_offset}"
        owner = (owner_scope, owner_module)

        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            text = first_arg.value
            static_msgid = msgid or f"txt_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"
            source_lang = classify_source_language(text)
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
            dynamic_msgid = msgid or f"tmpl_{hashlib.sha1(template.encode('utf-8')).hexdigest()[:12]}"
            try:
                source_lang = classify_source_language(template)
                mixed_source_template = False
            except Exception:
                has_han = any("\u4e00" <= ch <= "\u9fff" for ch in template)
                source_lang = "zh_CN" if has_han else "en"
                mixed_source_template = True
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


def main() -> int:
    owner_lang_entries: dict[tuple[str, str | None], dict[str, dict[str, str]]] = {}
    owner_source_map: dict[tuple[str, str | None], dict[str, str]] = {}
    owner_dynamic_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}
    owner_callsite_meta: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = {}

    py_files = sorted(APP_ROOT.rglob("*.py"))
    for py in py_files:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        except Exception:
            continue

        entries = []
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

    updated_owners = 0
    for owner, by_lang in owner_lang_entries.items():
        owner_scope, owner_module = owner
        i18n_dir = _owner_i18n_dir(owner_scope, owner_module)
        i18n_dir.mkdir(parents=True, exist_ok=True)

        for lang in SUPPORTED_SOURCE_LANGS:
            if lang not in by_lang:
                continue
            path = i18n_dir / f"{lang}.json"
            current = _load_json(path)
            if not isinstance(current, dict):
                current = {}
            current.update(by_lang[lang])
            _save_json(path, current)

        source_map_path = i18n_dir / "source_map.json"
        source_map = _load_json(source_map_path)
        if not isinstance(source_map, dict):
            source_map = {}
        source_map.update(owner_source_map.get(owner, {}))
        _save_json(source_map_path, dict(sorted(source_map.items(), key=lambda x: x[0])))

        template_meta_path = i18n_dir / "template_meta.json"
        template_meta = _load_json(template_meta_path)
        if not isinstance(template_meta, dict):
            template_meta = {}
        template_meta.update(owner_dynamic_meta.get(owner, {}))
        _save_json(template_meta_path, dict(sorted(template_meta.items(), key=lambda x: x[0])))

        callsite_meta_path = i18n_dir / "callsite_meta.json"
        callsite_meta = _load_json(callsite_meta_path)
        if not isinstance(callsite_meta, dict):
            callsite_meta = {}
        callsite_meta.update(owner_callsite_meta.get(owner, {}))
        _save_json(callsite_meta_path, dict(sorted(callsite_meta.items(), key=lambda x: x[0])))

        updated_owners += 1

    print(f"updated_owners={updated_owners}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
