from __future__ import annotations

import ast
import copy
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = PROJECT_ROOT / "app"
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


def _owner_from_path(file_path: Path) -> tuple[str, str | None]:
    try:
        rel = file_path.resolve().relative_to(PROJECT_ROOT).parts
    except Exception:
        return "framework", None
    if len(rel) >= 5 and rel[0] == "app" and rel[1] == "features" and rel[2] == "modules":
        return "module", rel[3]
    return "framework", None


class _DynamicTemplate(NamedTuple):
    template: str
    payload: dict[str, ast.AST]


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
            # Dynamic format-spec expression cannot be represented as a stable template token.
            return None
        return "".join(chunks)
    return None


def _formatted_placeholder(item: ast.FormattedValue, field_name: str) -> str | None:
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
    return "{" + field_name + conversion + spec_suffix + "}"


def _expr_to_field_name(expr: ast.AST, index: int) -> str:
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
    return f"value_{index}"


def _extract_template_and_payload_from_joined(
    joined: ast.JoinedStr,
) -> _DynamicTemplate:
    chunks: list[str] = []
    payload: dict[str, ast.AST] = {}
    used: set[str] = set()
    value_idx = 1

    for item in joined.values:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            chunks.append(item.value)
            continue
        if not isinstance(item, ast.FormattedValue):
            continue

        field_name = _expr_to_field_name(item.value, value_idx)
        while field_name in used:
            value_idx += 1
            field_name = f"{field_name}_{value_idx}"
        used.add(field_name)

        placeholder = _formatted_placeholder(item, field_name)
        if placeholder is None:
            # Preserve dynamic format-spec semantics by evaluating the original segment.
            payload[field_name] = ast.JoinedStr(values=[copy.deepcopy(item)])
            chunks.append("{" + field_name + "}")
        else:
            payload[field_name] = copy.deepcopy(item.value)
            chunks.append(placeholder)
        value_idx += 1

    return _DynamicTemplate("".join(chunks), payload)


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


def _extract_template_and_payload_from_concat(expr: ast.AST) -> _DynamicTemplate | None:
    parts = _flatten_concat_parts(expr)
    if not parts:
        return None
    if len(parts) == 1:
        return None

    chunks: list[str] = []
    payload: dict[str, ast.AST] = {}
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
        payload[field] = copy.deepcopy(part)
        chunks.append("{" + field + "}")
        idx += 1
    if not has_dynamic:
        return None
    return _DynamicTemplate("".join(chunks), payload)


def _extract_template_and_payload_from_format_call(expr: ast.AST) -> _DynamicTemplate | None:
    if not (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format"):
        return None
    base = expr.func.value
    if not (isinstance(base, ast.Constant) and isinstance(base.value, str)):
        return None
    template = base.value
    payload: dict[str, ast.AST] = {}
    used: set[str] = set()
    idx = 1
    for arg in expr.args:
        field = f"value_{idx}"
        while field in used:
            idx += 1
            field = f"value_{idx}"
        used.add(field)
        payload[field] = copy.deepcopy(arg)
        idx += 1
    for kw in expr.keywords:
        if not kw.arg:
            continue
        field = kw.arg
        if field in used:
            continue
        used.add(field)
        payload[field] = copy.deepcopy(kw.value)
    return _DynamicTemplate(template, payload)


_PERCENT_TOKEN_RE = re.compile(
    r"%(?:\((?P<named>[A-Za-z_][A-Za-z0-9_]*)\))?"
    r"(?P<spec>[#0\- +]?(?:\d+|\*)?(?:\.\d+)?[hlL]?[diouxXeEfFgGcrs%])"
)


def _extract_template_and_payload_from_percent(expr: ast.AST) -> _DynamicTemplate | None:
    if not (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod)):
        return None
    if not (isinstance(expr.left, ast.Constant) and isinstance(expr.left.value, str)):
        return None

    fmt = expr.left.value
    values_by_name: dict[str, ast.AST] = {}
    values_by_pos: list[ast.AST] = []

    right = expr.right
    if isinstance(right, ast.Dict):
        for key_node, value_node in zip(right.keys, right.values):
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                values_by_name[key_node.value] = copy.deepcopy(value_node)
    elif isinstance(right, ast.Tuple):
        values_by_pos = [copy.deepcopy(v) for v in right.elts]
    else:
        values_by_pos = [copy.deepcopy(right)]

    payload: dict[str, ast.AST] = {}
    chunks: list[str] = []
    pos_idx = 0
    cursor = 0
    generated_idx = 1
    for match in _PERCENT_TOKEN_RE.finditer(fmt):
        chunks.append(fmt[cursor:match.start()])
        cursor = match.end()

        spec = match.group("spec")
        named = match.group("named")
        if spec == "%":
            chunks.append("%")
            continue

        if named:
            field = named
            expr_value = values_by_name.get(named, ast.Constant(""))
        else:
            field = f"value_{generated_idx}"
            generated_idx += 1
            if pos_idx < len(values_by_pos):
                expr_value = values_by_pos[pos_idx]
            else:
                expr_value = ast.Constant("")
            pos_idx += 1

        payload[field] = expr_value
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

    chunks.append(fmt[cursor:])
    if not payload:
        return None
    return _DynamicTemplate("".join(chunks), payload)


def _extract_dynamic_template(expr: ast.AST) -> _DynamicTemplate | None:
    if isinstance(expr, ast.JoinedStr):
        return _extract_template_and_payload_from_joined(expr)
    from_concat = _extract_template_and_payload_from_concat(expr)
    if from_concat is not None:
        return from_concat
    from_format = _extract_template_and_payload_from_format_call(expr)
    if from_format is not None:
        return from_format
    from_percent = _extract_template_and_payload_from_percent(expr)
    if from_percent is not None:
        return from_percent
    return None


class _I18nTransformer(ast.NodeTransformer):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.owner_scope, self.owner_module = _owner_from_path(file_path)
        self._parents: list[ast.AST] = []
        self._local_bindings: list[dict[str, ast.AST]] = []

    def visit(self, node):  # type: ignore[override]
        self._parents.append(node)
        new_node = super().visit(node)
        self._parents.pop()
        return new_node

    def _detect_context_hint(self) -> str:
        if len(self._parents) < 2:
            return "ui"
        parent = self._parents[-2]
        if isinstance(parent, ast.Call):
            fn = parent.func
            if isinstance(fn, ast.Attribute) and fn.attr in LOG_METHODS:
                return "log"
        return "ui"

    def _append_owner_metadata(self, node: ast.Call) -> None:
        kw_names = {kw.arg for kw in node.keywords if kw.arg}
        if "__i18n_owner_scope__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_owner_scope__", value=ast.Constant(self.owner_scope)))
        if "__i18n_owner_module__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_owner_module__", value=ast.Constant(self.owner_module)))

    def _append_callsite_metadata(self, node: ast.Call, kind: str) -> None:
        kw_names = {kw.arg for kw in node.keywords if kw.arg}
        try:
            rel_path = str(self.file_path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
        except Exception:
            rel_path = str(self.file_path).replace("\\", "/")
        callsite_key = f"{rel_path}:{getattr(node, 'lineno', 0)}:{getattr(node, 'col_offset', 0)}"
        if "__i18n_callsite_key__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_callsite_key__", value=ast.Constant(callsite_key)))
        if "__i18n_callsite_kind__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_callsite_kind__", value=ast.Constant(kind)))

    def _resolve_binding(self, name: str) -> ast.AST | None:
        for scope in reversed(self._local_bindings):
            if name in scope:
                return scope[name]
        return None

    def _extract_template_for_arg(self, arg: ast.AST) -> _DynamicTemplate | None:
        if isinstance(arg, ast.Name):
            bound = self._resolve_binding(arg.id)
            if bound is not None:
                return _extract_dynamic_template(bound)
        return _extract_dynamic_template(arg)

    def _track_binding_stmt(self, stmt: ast.stmt) -> None:
        if not self._local_bindings:
            return
        scope = self._local_bindings[-1]

        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    scope[target.id] = copy.deepcopy(stmt.value)
            return
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            scope[stmt.target.id] = copy.deepcopy(stmt.value)
            return
        if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            scope.pop(stmt.target.id, None)
            return
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While, ast.If, ast.Try, ast.With, ast.AsyncWith, ast.Match)):
            scope.clear()

    def _visit_stmt_list(self, statements: list[ast.stmt]) -> list[ast.stmt]:
        result: list[ast.stmt] = []
        for stmt in statements:
            new_stmt = self.visit(stmt)
            if new_stmt is None:
                continue
            if isinstance(new_stmt, list):
                for item in new_stmt:
                    result.append(item)
                    self._track_binding_stmt(item)
            else:
                result.append(new_stmt)
                self._track_binding_stmt(new_stmt)
        return result

    def visit_Module(self, node: ast.Module):  # type: ignore[override]
        self._local_bindings.append({})
        node.body = self._visit_stmt_list(node.body)
        self._local_bindings.pop()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
        self._local_bindings.append({})
        node.body = self._visit_stmt_list(node.body)
        self._local_bindings.pop()
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # type: ignore[override]
        self._local_bindings.append({})
        node.body = self._visit_stmt_list(node.body)
        self._local_bindings.pop()
        return node

    def visit_Call(self, node: ast.Call):  # type: ignore[override]
        node = self.generic_visit(node)
        if not (isinstance(node.func, ast.Name) and node.func.id == "_"):
            return node
        if not node.args:
            return node

        self._append_owner_metadata(node)
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            self._append_callsite_metadata(node, kind="static_literal")
            if "__i18n_literal__" not in kw_names:
                node.keywords.append(ast.keyword(arg="__i18n_literal__", value=ast.Constant(True)))
            return node

        extracted = self._extract_template_for_arg(first_arg)
        if extracted is None:
            kw_names = {kw.arg for kw in node.keywords if kw.arg}
            self._append_callsite_metadata(node, kind="dynamic_candidate")
            if "__i18n_dynamic_candidate__" not in kw_names:
                node.keywords.append(ast.keyword(arg="__i18n_dynamic_candidate__", value=ast.Constant(True)))
            return node

        template, payload = extracted
        payload_dict = ast.Dict(
            keys=[ast.Constant(k) for k in payload.keys()],
            values=[v for v in payload.values()],
        )
        template_id = f"tmpl_{hashlib.sha1(template.encode('utf-8')).hexdigest()[:12]}"
        kw_names = {kw.arg for kw in node.keywords if kw.arg}
        self._append_callsite_metadata(node, kind="dynamic_template")
        if "__i18n_dynamic__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_dynamic__", value=ast.Constant(True)))
        if "__i18n_template__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_template__", value=ast.Constant(template)))
        if "__i18n_template_id__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_template_id__", value=ast.Constant(template_id)))
        if "__i18n_fields__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_fields__", value=payload_dict))
        if "__i18n_context_hint__" not in kw_names:
            node.keywords.append(ast.keyword(arg="__i18n_context_hint__", value=ast.Constant(self._detect_context_hint())))
        return node


class _I18nRewriteLoader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname: str):  # type: ignore[override]
        # Always compile from source so dynamic _() metadata injection is not bypassed by stale .pyc cache.
        try:
            source_bytes = self.get_data(self.path)
            return self.source_to_code(source_bytes, self.path)
        except Exception:
            return super().get_code(fullname)

    def source_to_code(self, data, path, *, _optimize=-1):  # type: ignore[override]
        try:
            source = data.decode("utf-8")
        except Exception:
            return super().source_to_code(data, path, _optimize=_optimize)

        try:
            tree = ast.parse(source, filename=path)
            transformer = _I18nTransformer(Path(path))
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)
            return compile(new_tree, path, "exec", dont_inherit=True, optimize=_optimize)
        except Exception:
            # Safe fallback: never block import on rewrite failure.
            return super().source_to_code(data, path, _optimize=_optimize)


class _I18nRewriteFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):
        if not (fullname == "app" or fullname.startswith("app.")):
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.origin is None:
            return spec
        if not spec.origin.endswith(".py"):
            return spec

        origin = Path(spec.origin)
        try:
            origin.relative_to(APP_ROOT)
        except Exception:
            return spec

        if isinstance(spec.loader, importlib.machinery.SourceFileLoader):
            spec.loader = _I18nRewriteLoader(fullname, spec.origin)
        return spec


_INSTALLED = False


def install_import_rewrite() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    finder = _I18nRewriteFinder()
    sys.meta_path.insert(0, finder)
    _INSTALLED = True
