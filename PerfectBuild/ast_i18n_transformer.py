from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class _TemplateState:
    expr_to_key: dict[str, str] = field(default_factory=dict)
    key_to_expr: dict[str, ast.AST] = field(default_factory=dict)
    used_keys: set[str] = field(default_factory=set)


LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}


class I18nFStringTransformer(ast.NodeTransformer):
    """Transform dynamic _(...) payloads into _("...").format(...)."""

    def __init__(self) -> None:
        super().__init__()
        self.changed = False

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if not isinstance(node, ast.Call):
            return node

        # 1. Handle original _(...) calls
        if isinstance(node.func, ast.Name) and node.func.id == "_":
            if not node.args:
                return node
            first_arg = node.args[0]
            if not self._is_rewrite_candidate(first_arg):
                return node
            transformed = self._rewrite_i18n_dynamic_call(node, first_arg)
            if transformed is not node:
                self.changed = True
                return ast.copy_location(transformed, node)
            return node

        # 2. Handle automatic logger.xxx(...) wrapping
        if self._is_log_call(node):
            return self._wrap_log_call_with_i18n(node)

        return node

    def _is_log_call(self, node: ast.Call) -> bool:
        if not isinstance(node.func, ast.Attribute) or node.func.attr not in LOG_METHODS:
            return False
        
        # Check for logger.info, self.logger.info, etc.
        val = node.func.value
        if isinstance(val, ast.Name) and "logger" in val.id.lower():
            return True
        if isinstance(val, ast.Attribute) and "logger" in val.attr.lower():
            return True
        return False

    def _wrap_log_call_with_i18n(self, node: ast.Call) -> ast.Call:
        if not node.args:
            return node
        
        first_arg = node.args[0]
        # Already wrapped? Skip.
        if isinstance(first_arg, ast.Call) and isinstance(first_arg.func, ast.Name) and first_arg.func.id == "_":
            return node

        # Wrap plain string payloads and rewrite only safe dynamic template shapes.
        if isinstance(first_arg, ast.Constant):
            if not isinstance(first_arg.value, str):
                return node
            self.changed = True
            node.args[0] = self._wrap_with_i18n(first_arg)
            return node

        if self._is_rewrite_candidate(first_arg):
            self.changed = True
            virtual_i18n_call = self._wrap_with_i18n(first_arg)
            node.args[0] = self._rewrite_i18n_dynamic_call(virtual_i18n_call, first_arg)
            return node

        # Keep `%` and `"{}".format(...)` payloads as-is, only add i18n wrapper.
        if self._is_percent_format_expr(first_arg) or self._is_str_format_call(first_arg):
            self.changed = True
            node.args[0] = self._wrap_with_i18n(first_arg)

        return node

    @staticmethod
    def _wrap_with_i18n(expr: ast.AST) -> ast.Call:
        return ast.Call(
            func=ast.Name(id="_", ctx=ast.Load()),
            args=[expr],
            keywords=[],
        )

    @staticmethod
    def _is_rewrite_candidate(expr: ast.AST) -> bool:
        if isinstance(expr, ast.JoinedStr):
            return True
        return isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add)

    @staticmethod
    def _is_percent_format_expr(expr: ast.AST) -> bool:
        return isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod)

    @staticmethod
    def _is_str_format_call(expr: ast.AST) -> bool:
        if not isinstance(expr, ast.Call):
            return False
        if not isinstance(expr.func, ast.Attribute) or expr.func.attr != "format":
            return False
        return isinstance(expr.func.value, ast.Constant) and isinstance(expr.func.value.value, str)

    def _rewrite_i18n_dynamic_call(self, call_node: ast.Call, expr: ast.AST) -> ast.AST:
        state = _TemplateState()
        idx_container = [1]  # Shared index counter for current call

        # Handle existing .format() call if expr is a Call node to "format"
        if self._is_str_format_call(expr):
            # Extract the template and existing kwargs
            template_node = expr.func.value
            if not isinstance(template_node, ast.Constant) or not isinstance(template_node.value, str):
                return call_node
            
            # Use original template, but we might need to handle msgid if present in call_node
            template = template_node.value
            
            # Combine original keywords from the format() call
            kwargs = list(expr.keywords)
            # Combine original args from the format() call (convert them to value_N if they are positional)
            for i, arg in enumerate(expr.args):
                kwargs.append(ast.keyword(arg=f"value_{i+1}", value=arg))
            
            return ast.Call(
                func=call_node.func,
                args=[ast.Constant(value=template), *call_node.args[1:]],
                keywords=call_node.keywords + kwargs,
            )

        parsed = self._expr_to_template(expr, state, idx_container)
        if parsed is None:
            return call_node
        template, has_dynamic = parsed
        if not has_dynamic:
            return call_node

        kwargs = [
            ast.keyword(arg=key, value=expr)
            for key, expr in state.key_to_expr.items()
        ]

        return ast.Call(
            func=call_node.func,
            args=[ast.Constant(value=template), *call_node.args[1:]],
            keywords=call_node.keywords + kwargs,
        )

    def _expr_to_template(self, expr: ast.AST, state: _TemplateState, idx: list[int]) -> tuple[str, bool] | None:
        if isinstance(expr, ast.JoinedStr):
            template = self._joined_str_to_template(expr, state, idx)
            has_dynamic = any(isinstance(item, ast.FormattedValue) for item in expr.values)
            return template, has_dynamic

        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
            left_res = self._expr_to_template(expr.left, state, idx)
            right_res = self._expr_to_template(expr.right, state, idx)
            if left_res is None or right_res is None:
                return None
            return left_res[0] + right_res[0], left_res[1] or right_res[1]

        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return self._escape_braces(expr.value), False

        # Treat other non-literal nodes as dynamic placeholders.
        key = self._bind_expression(expr, state, idx)
        return "{" + key + "}", True

    def _joined_str_to_template(self, joined: ast.JoinedStr, state: _TemplateState, idx: list[int]) -> str:
        result: list[str] = []
        for item in joined.values:
            if isinstance(item, ast.Constant):
                text = "" if item.value is None else str(item.value)
                result.append(self._escape_braces(text))
            elif isinstance(item, ast.FormattedValue):
                result.append(self._formatted_value_to_placeholder(item, state, idx))
            else:
                # Unexpected node type inside JoinedStr, keep source equivalent.
                result.append(self._escape_braces(ast.unparse(item)))
        return "".join(result)

    def _formatted_value_to_placeholder(self, part: ast.FormattedValue, state: _TemplateState, idx: list[int]) -> str:
        key = self._bind_expression(part.value, state, idx)

        conversion = ""
        if part.conversion != -1:
            conversion = f"!{chr(part.conversion)}"

        format_spec = ""
        if part.format_spec is not None:
            format_spec_text = self._format_spec_to_text(part.format_spec, state, idx)
            format_spec = f":{format_spec_text}"

        return "{" + key + conversion + format_spec + "}"

    def _format_spec_to_text(self, spec_node: ast.AST, state: _TemplateState, idx: list[int]) -> str:
        if isinstance(spec_node, ast.JoinedStr):
            return self._joined_str_to_template(spec_node, state, idx)
        return self._escape_braces(ast.unparse(spec_node))

    def _bind_expression(self, value: ast.AST, state: _TemplateState, idx: list[int]) -> str:
        # 1. Determine base name
        if isinstance(value, ast.Name):
            base_key = value.id
        elif isinstance(value, ast.Attribute):
            parts = []
            cur = value
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            base_key = "_".join(reversed(parts)) if parts else f"value_{idx[0]}"
        else:
            base_key = f"value_{idx[0]}"

        # 2. Handle unique key requirement
        key = base_key
        if key in state.used_keys:
            # Fallback to indexed naming if base key is taken
            while True:
                idx[0] += 1
                key = f"{base_key}_{idx[0]}"
                if key not in state.used_keys:
                    break
        
        state.used_keys.add(key)
        state.key_to_expr[key] = copy.deepcopy(value)
        # We DO NOT increment idx[0] globally here to match extractor's behavior 
        # where idx is only incremented when a placeholder is consumed.
        idx[0] += 1
        return key

    @staticmethod
    def _escape_braces(text: str) -> str:
        return text.replace("{", "{{").replace("}", "}}")


def process_file(filepath: str | Path) -> bool:
    """Transform one Python file in place. Returns True if file changed."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        print(f"[ast_i18n] skip unparsable file: {path} ({exc.__class__.__name__})")
        return False

    transformer = I18nFStringTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    if not transformer.changed:
        return False

    new_source = ast.unparse(new_tree)
    if source.endswith("\n"):
        new_source += "\n"
    path.write_text(new_source, encoding="utf-8")
    return True
