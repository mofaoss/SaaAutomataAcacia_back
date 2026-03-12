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


class I18nFStringTransformer(ast.NodeTransformer):
    """Transform _(f"...") into _("...").format(...)."""

    def __init__(self) -> None:
        super().__init__()
        self.changed = False
        self._counter = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if not isinstance(node, ast.Call):
            return node

        if not isinstance(node.func, ast.Name) or node.func.id != "_":
            return node
        if not node.args:
            return node

        first_arg = node.args[0]
        if not isinstance(first_arg, ast.JoinedStr):
            return node

        transformed = self._rewrite_i18n_fstring_call(node, first_arg)
        self.changed = True
        return ast.copy_location(transformed, node)

    def _rewrite_i18n_fstring_call(self, call_node: ast.Call, joined: ast.JoinedStr) -> ast.Call:
        state = _TemplateState()
        template = self._joined_str_to_template(joined, state)

        new_i18n_call = ast.Call(
            func=call_node.func,
            args=[ast.Constant(value=template), *call_node.args[1:]],
            keywords=call_node.keywords,
        )

        if not state.key_to_expr:
            return new_i18n_call

        kwargs = [
            ast.keyword(arg=key, value=expr)
            for key, expr in state.key_to_expr.items()
        ]
        return ast.Call(
            func=ast.Attribute(value=new_i18n_call, attr="format", ctx=ast.Load()),
            args=[],
            keywords=kwargs,
        )

    def _joined_str_to_template(self, joined: ast.JoinedStr, state: _TemplateState) -> str:
        result: list[str] = []
        for item in joined.values:
            if isinstance(item, ast.Constant):
                text = "" if item.value is None else str(item.value)
                result.append(self._escape_braces(text))
            elif isinstance(item, ast.FormattedValue):
                result.append(self._formatted_value_to_placeholder(item, state))
            else:
                # Unexpected node type inside JoinedStr, keep source equivalent.
                result.append(self._escape_braces(ast.unparse(item)))
        return "".join(result)

    def _formatted_value_to_placeholder(self, part: ast.FormattedValue, state: _TemplateState) -> str:
        key = self._bind_expression(part.value, state)

        conversion = ""
        if part.conversion != -1:
            conversion = f"!{chr(part.conversion)}"

        format_spec = ""
        if part.format_spec is not None:
            format_spec_text = self._format_spec_to_text(part.format_spec, state)
            format_spec = f":{format_spec_text}"

        return "{" + key + conversion + format_spec + "}"

    def _format_spec_to_text(self, spec_node: ast.AST, state: _TemplateState) -> str:
        if isinstance(spec_node, ast.JoinedStr):
            return self._joined_str_to_template(spec_node, state)
        return self._escape_braces(ast.unparse(spec_node))

    def _bind_expression(self, value: ast.AST, state: _TemplateState) -> str:
        if isinstance(value, ast.Name) and value.id.isidentifier():
            key = value.id
            if key not in state.key_to_expr:
                state.key_to_expr[key] = copy.deepcopy(value)
            state.used_keys.add(key)
            return key

        expr_source = ast.unparse(value)
        existing_key = state.expr_to_key.get(expr_source)
        if existing_key is not None:
            return existing_key

        key = self._next_var_name(state)
        state.expr_to_key[expr_source] = key
        state.key_to_expr[key] = copy.deepcopy(value)
        return key

    def _next_var_name(self, state: _TemplateState) -> str:
        while True:
            key = f"var_{self._counter}"
            self._counter += 1
            if key not in state.used_keys:
                state.used_keys.add(key)
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
