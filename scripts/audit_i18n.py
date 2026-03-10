#!/usr/bin/env python
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SOURCE_LANG = "en"
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]


def _load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _source_lang_for_key(en_map: dict[str, str], zh_cn_map: dict[str, str], zh_hk_map: dict[str, str], key: str) -> str | None:
    if key in en_map:
        return "en"
    if key in zh_cn_map:
        return "zh_CN"
    if key in zh_hk_map:
        return "zh_HK"
    return None


def _audit_owner(base: Path, owner_name: str) -> list[str]:
    lines = [f"{owner_name}:"]
    paths = {lang: base / f"{lang}.json" for lang in SUPPORTED_LANGS}
    maps = {lang: _load_json(path) for lang, path in paths.items()}

    missing_files = [lang for lang, path in paths.items() if not path.exists()]

    all_keys: set[str] = set()
    for m in maps.values():
        all_keys.update(m.keys())

    source_count = {"en": 0, "zh_CN": 0, "zh_HK": 0}
    missing_from_en = {"zh_CN": 0, "zh_HK": 0}
    missing_from_zh_cn = {"en": 0, "zh_HK": 0}

    for key in all_keys:
        source_lang = _source_lang_for_key(maps["en"], maps["zh_CN"], maps["zh_HK"], key)
        if source_lang is None:
            continue
        source_count[source_lang] += 1

        if source_lang == "en":
            if key not in maps["zh_CN"]:
                missing_from_en["zh_CN"] += 1
            if key not in maps["zh_HK"]:
                missing_from_en["zh_HK"] += 1
        elif source_lang == "zh_CN":
            if key not in maps["en"]:
                missing_from_zh_cn["en"] += 1
            if key not in maps["zh_HK"]:
                missing_from_zh_cn["zh_HK"] += 1

    source_lang_report = []
    if source_count["en"]:
        source_lang_report.append(f"en={source_count['en']}")
    if source_count["zh_CN"]:
        source_lang_report.append(f"zh_CN={source_count['zh_CN']}")
    if source_count["zh_HK"]:
        source_lang_report.append(f"zh_HK={source_count['zh_HK']}")

    if not source_lang_report:
        source_lang_report.append(DEFAULT_SOURCE_LANG)

    lines.append(f"  source_lang: {', '.join(source_lang_report)}")
    lines.append(f"  missing_files: {', '.join(missing_files) if missing_files else 'none'}")
    lines.append(
        "  missing_keys: "
        f"from_en->zh_CN={missing_from_en['zh_CN']}, "
        f"from_en->zh_HK={missing_from_en['zh_HK']}, "
        f"from_zh_CN->en={missing_from_zh_cn['en']}, "
        f"from_zh_CN->zh_HK={missing_from_zh_cn['zh_HK']}"
    )

    return lines


def _discover_registered_module_dirs(modules_root: Path) -> set[str]:
    registered: set[str] = set()
    for py in modules_root.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                continue
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Name) and deco.func.id in {"on_demand_module", "periodic_module"}:
                    rel = py.relative_to(modules_root)
                    if rel.parts:
                        registered.add(rel.parts[0])
    return registered


def _audit_framework() -> list[str]:
    base = ROOT / "app" / "framework" / "i18n"
    lines = ["[framework]"]
    lines.extend(f"  {line}" if idx else line for idx, line in enumerate(_audit_owner(base, "framework")))
    return lines


def _audit_modules() -> list[str]:
    modules_root = ROOT / "app" / "features" / "modules"
    lines = ["[modules]"]

    registered_dirs = _discover_registered_module_dirs(modules_root)
    for module_dir in sorted([p for p in modules_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        if module_dir.name.startswith("__"):
            continue
        if module_dir.name not in registered_dirs:
            continue

        owner_lines = _audit_owner(module_dir / "i18n", module_dir.name)
        lines.extend(owner_lines)

    return lines


def main() -> int:
    output = []
    output.extend(_audit_framework())
    output.append("")
    output.extend(_audit_modules())
    print("\n".join(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
