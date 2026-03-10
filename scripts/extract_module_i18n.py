#!/usr/bin/env python
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.framework.core.module_system.models import Field
from app.framework.core.module_system.naming import infer_module_id, humanize_name

MODULES_ROOT = ROOT / "app" / "features" / "modules"


_EN_DECL_RE = re.compile(r"^[\x20-\x7E]+$")


def _validate_english_declaration(text: str, *, field: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{field} must be a non-empty English string")
    if not _EN_DECL_RE.fullmatch(text):
        raise ValueError(
            f"{field} must use English ASCII declaration text only (found unsupported chars): {text!r}"
        )


def _literal(node: ast.AST):
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


def _extract_from_file(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    out = []

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

            entries = {f"module.{module_id}.title": title}
            for param_name, meta in fields.items():
                field_id = meta["field_id"] or param_name
                entries[f"module.{module_id}.field.{field_id}.label"] = meta["label"] or humanize_name(param_name)
                if meta.get("help"):
                    entries[f"module.{module_id}.field.{field_id}.help"] = meta["help"]

            out.append((module_id, entries))

    return out


def _module_root(py_file: Path) -> Path:
    current = py_file.parent
    while current.parent != MODULES_ROOT and current.parent != ROOT:
        current = current.parent
    return current


def main() -> int:
    updates = 0
    for py in MODULES_ROOT.rglob("*.py"):
        found = _extract_from_file(py)
        if not found:
            continue

        module_dir = _module_root(py)
        i18n_dir = module_dir / "i18n"
        i18n_dir.mkdir(parents=True, exist_ok=True)
        en_path = i18n_dir / "en.json"

        current = {}
        if en_path.exists():
            try:
                current = json.loads(en_path.read_text(encoding="utf-8"))
            except Exception:
                current = {}

        for _, entries in found:
            current.update(entries)

        en_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        updates += 1

    print(f"updated_modules={updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
