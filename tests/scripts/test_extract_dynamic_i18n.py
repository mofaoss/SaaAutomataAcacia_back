from __future__ import annotations

import ast

import scripts.extract_module_i18n as extractor


def test_extract_dynamic_fstring_template_and_fields():
    source = """
from app.framework.i18n.runtime import _

def run(task_name, e, logger):
    logger.error(_(f"Task {task_name} failed: {e}", msgid="task_failed"))
"""
    tree = ast.parse(source)
    fake_path = extractor.ROOT / "app" / "framework" / "tmp_extract_dynamic.py"

    entries, dynamic_meta, callsite_meta = extractor._extract_marked_strings_from_file(fake_path, tree)
    assert entries
    key = "framework.log.task_failed"
    found = [item for item in entries if item[2] == key]
    assert found, entries
    assert found[0][3] == "Task {task_name} failed: {e}"
    owner = ("framework", None)
    assert owner in dynamic_meta
    assert key in dynamic_meta[owner]
    assert dynamic_meta[owner][key]["fields"] == ["task_name", "e"]
    assert dynamic_meta[owner][key]["context"] == "log"

    assert owner in callsite_meta
    callsites = list(callsite_meta[owner].values())
    assert any(cs.get("kind") == "dynamic_template" for cs in callsites)


def test_extract_dynamic_non_fstring_patterns():
    source = """
from app.framework.i18n.runtime import _

def run(a, b):
    x = f"{a}: {b}"
    y = _("{a}: {b}".format(a=a, b=b), msgid="fmt")
    z = _("%s: %s" % (a, b), msgid="pct")
    w = _(a + ": " + b, msgid="add")
    q = _(x, msgid="var")
    return y, z, w, q
"""
    tree = ast.parse(source)
    fake_path = extractor.ROOT / "app" / "framework" / "tmp_extract_non_f.py"

    entries, dynamic_meta, _callsite_meta = extractor._extract_marked_strings_from_file(fake_path, tree)
    keys = {item[2] for item in entries}
    assert "framework.ui.fmt" in keys
    assert "framework.ui.pct" in keys
    assert "framework.ui.add" in keys
    assert "framework.ui.var" in keys
    owner = ("framework", None)
    assert "framework.ui.var" in dynamic_meta[owner]


def test_extract_dynamic_fstring_preserves_format_spec_and_conversion():
    source = """
from app.framework.i18n.runtime import _

def run(client_width, client_height, actual_ratio, status):
    return _(f"Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status!r}", msgid="client_area")
"""
    tree = ast.parse(source)
    fake_path = extractor.ROOT / "app" / "framework" / "tmp_extract_spec.py"

    entries, dynamic_meta, _callsite_meta = extractor._extract_marked_strings_from_file(fake_path, tree)
    key = "framework.ui.client_area"
    found = [item for item in entries if item[2] == key]
    assert found
    assert found[0][3] == "Client area size: {client_width}x{client_height} ({actual_ratio:.3f}:1), {status!r}"
    owner = ("framework", None)
    details = dynamic_meta[owner][key]["field_details"]
    assert details["actual_ratio"]["format_spec"] == ".3f"
    assert details["status"]["conversion"] == "r"
