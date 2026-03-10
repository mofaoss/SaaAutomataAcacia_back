from __future__ import annotations

import ast
from pathlib import Path

from app.framework.i18n.import_rewrite import _I18nTransformer


def _find_translated_call(tree: ast.AST) -> ast.Call:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_":
            return node
    raise AssertionError("_() call not found")


def _keywords(call: ast.Call) -> dict[str, ast.AST]:
    return {k.arg: k.value for k in call.keywords if k.arg}


def test_import_rewrite_injects_dynamic_template_metadata_for_fstring():
    source = """
from app.framework.i18n.runtime import _

def run(task_name, e, logger):
    logger.error(_(f"Task {task_name} failed: {e}", msgid="task_failed"))
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_module.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert "__i18n_template__" in kw
    assert "__i18n_fields__" in kw
    assert "__i18n_callsite_kind__" in kw
    assert isinstance(kw["__i18n_template__"], ast.Constant)
    assert kw["__i18n_template__"].value == "Task {task_name} failed: {e}"


def test_import_rewrite_marks_concat_as_dynamic_template():
    source = """
from app.framework.i18n.runtime import _

def run(a, b):
    return _(a + ': ' + b)
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_concat.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert "__i18n_template__" in kw


def test_import_rewrite_marks_format_as_dynamic_template():
    source = """
from app.framework.i18n.runtime import _

def run(title, remaining):
    return _("{title}: {remaining}".format(title=title, remaining=remaining))
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_format.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert "__i18n_template__" in kw


def test_import_rewrite_marks_percent_as_dynamic_template():
    source = """
from app.framework.i18n.runtime import _

def run(title, remaining):
    return _("%s: %s" % (title, remaining))
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_percent.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert "__i18n_template__" in kw


def test_import_rewrite_resolves_simple_same_scope_variable():
    source = """
from app.framework.i18n.runtime import _

def run(title, remaining):
    text = f"{title}: {remaining}"
    return _(text)
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_var.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert "__i18n_template__" in kw


def test_import_rewrite_marks_unknown_nonliteral_as_dynamic_candidate():
    source = """
from app.framework.i18n.runtime import _

def run(text):
    return _(text.strip())
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_candidate.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic_candidate__" in kw
    assert "__i18n_literal__" not in kw


def test_import_rewrite_preserves_fstring_spec_and_conversion():
    source = """
from app.framework.i18n.runtime import _

def run(client_width, client_height, actual_ratio, status):
    return _(f"Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status!r}")
"""
    tree = ast.parse(source)
    rewritten = _I18nTransformer(Path("app/framework/tmp_spec.py")).visit(tree)
    ast.fix_missing_locations(rewritten)

    call = _find_translated_call(rewritten)
    kw = _keywords(call)
    assert "__i18n_dynamic__" in kw
    assert isinstance(kw["__i18n_template__"], ast.Constant)
    assert kw["__i18n_template__"].value == "Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status!r}"
