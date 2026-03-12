#!/usr/bin/env python
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.framework.i18n.template_render import extract_template_fields
from app.framework.i18n.template_render import extract_template_field_details

SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]
REQUIRED_LANGS = ["en", "zh_CN"]
HAN_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
FORMAT_TOKEN_RE = re.compile(r"{([^{}]+)}")


def _canonicalize_template_ignoring_spec(template: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        token = match.group(1)
        field_part = token.split(":", 1)[0]
        field_part = field_part.split("!", 1)[0]
        base = field_part.split("[", 1)[0].split(".", 1)[0]
        return "{" + base + "}" if base else "{}"

    return FORMAT_TOKEN_RE.sub(_replace, template)


def _load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _load_template_meta(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, dict)}


def _classify_value_lang(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    has_han = bool(HAN_RE.search(value))
    has_latin = bool(LATIN_RE.search(value))
    if has_han and not has_latin:
        return "zh_CN"
    if has_latin and not has_han:
        return "en"
    return None


def _resolve_source_lang(key: str, source_map: dict[str, str], maps: dict[str, dict[str, str]], template_meta: dict[str, dict]) -> str | None:
    source_lang = source_map.get(key)
    if source_lang in {"en", "zh_CN", "zh_HK"}:
        return source_lang
    if key in template_meta:
        lang = template_meta[key].get("source_language")
        if isinstance(lang, str) and lang in {"en", "zh_CN", "zh_HK"}:
            return lang
    if key in maps.get("en", {}):
        return "en"
    if key in maps.get("zh_CN", {}):
        return "zh_CN"
    if key in maps.get("zh_HK", {}):
        return "zh_HK"
    return None


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


def _module_id_to_owner() -> dict[str, str]:
    mapping: dict[str, str] = {}
    try:
        from app.framework.core.module_system import discover_modules
        from app.framework.core.module_system.registry import get_all_modules

        discover_modules("app.features.modules")
        for meta in get_all_modules():
            module_cls = getattr(meta, "module_class", None)
            module_path = str(getattr(module_cls, "__module__", "") or "")
            match = re.search(r"app\.features\.modules\.([a-z0-9_]+)(?:\.|$)", module_path)
            if not match:
                continue
            mapping[str(meta.id)] = match.group(1)
    except Exception:
        pass
    return mapping


def _audit_owner(base: Path, owner_name: str, *, module_id_map: dict[str, str] | None = None) -> dict:
    paths = {lang: base / f"{lang}.json" for lang in SUPPORTED_LANGS}
    maps = {lang: _load_json(path) for lang, path in paths.items()}
    source_map = _load_json(base / "source_map.json")
    template_meta = _load_template_meta(base / "template_meta.json")

    missing_files = [lang for lang in REQUIRED_LANGS if not paths[lang].exists()]

    all_keys: set[str] = set(source_map.keys())
    for m in maps.values():
        all_keys.update(m.keys())
    all_keys.update(template_meta.keys())

    source_count = {"en": 0, "zh_CN": 0, "zh_HK": 0}
    source_key_missing = {"en": 0, "zh_CN": 0, "zh_HK": 0}
    missing_from_en = {"zh_CN": 0, "zh_HK": 0}
    missing_from_zh_cn = {"en": 0, "zh_HK": 0}

    english_values_in_zh_cn = 0
    chinese_values_in_en = 0
    chinese_key_suffixes = 0
    owner_drift_keys = 0

    dynamic_template_count = len(template_meta)
    dynamic_template_missing_translation_count = 0
    dynamic_template_field_mismatch_count = 0
    dynamic_template_format_spec_mismatch_count = 0
    dynamic_template_unresolved_runtime_key_count = 0
    dynamic_template_spec_loss_duplicate_count = 0
    event_status_resource_missing_count = 0

    source_template_to_keys: dict[str, list[str]] = defaultdict(list)
    canonical_template_to_keys: dict[str, list[str]] = defaultdict(list)
    key_to_source_template: dict[str, str] = {}

    for key in sorted(all_keys):
        source_lang = _resolve_source_lang(key, source_map, maps, template_meta)
        if source_lang is None:
            continue

        source_count[source_lang] += 1
        if key not in maps.get(source_lang, {}):
            source_key_missing[source_lang] += 1

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

        if HAN_RE.search(key.rsplit(".", 1)[-1]):
            chinese_key_suffixes += 1

        zh_val = maps["zh_CN"].get(key)
        if zh_val is not None and _classify_value_lang(zh_val) == "en":
            english_values_in_zh_cn += 1

        en_val = maps["en"].get(key)
        if en_val is not None and _classify_value_lang(en_val) == "zh_CN":
            chinese_values_in_en += 1

        if owner_name != "framework" and key.startswith("module.") and module_id_map:
            parts = key.split(".")
            if len(parts) >= 2:
                module_id = parts[1]
                expected = module_id_map.get(module_id)
                if expected and expected != owner_name:
                    owner_drift_keys += 1

        meta = template_meta.get(key)
        if not meta:
            continue

        source_template = str(meta.get("source_template", ""))
        expected_fields = [str(f) for f in meta.get("fields", []) if isinstance(f, str)]
        expected_field_details = {
            str(k): {"format_spec": str(v.get("format_spec", "")), "conversion": str(v.get("conversion", ""))}
            for k, v in (meta.get("field_details", {}) or {}).items()
            if isinstance(k, str) and isinstance(v, dict)
        }
        if not expected_field_details and source_template:
            expected_field_details = extract_template_field_details(source_template)
        if source_template:
            source_template_to_keys[source_template].append(key)
            canonical_template_to_keys[_canonicalize_template_ignoring_spec(source_template)].append(key)
            key_to_source_template[key] = source_template

        source_value = maps.get(source_lang, {}).get(key)
        if source_value is None:
            dynamic_template_unresolved_runtime_key_count += 1
            continue

        for lang in SUPPORTED_LANGS:
            val = maps[lang].get(key)
            if val is None:
                dynamic_template_missing_translation_count += 1
                continue
            actual_fields = extract_template_fields(val)
            if sorted(actual_fields) != sorted(expected_fields):
                dynamic_template_field_mismatch_count += 1
            actual_field_details = extract_template_field_details(val)
            if expected_field_details and actual_field_details != expected_field_details:
                dynamic_template_format_spec_mismatch_count += 1

    dynamic_template_duplicate_template_count = sum(max(0, len(keys) - 1) for keys in source_template_to_keys.values())
    for canonical_key, keys in canonical_template_to_keys.items():
        if len(keys) < 2:
            continue
        has_spec = False
        has_no_spec = False
        for key in keys:
            tmpl = key_to_source_template.get(key, "")
            details = extract_template_field_details(tmpl) if tmpl else {}
            any_spec = any(
                (meta.get("format_spec") or meta.get("conversion"))
                for meta in details.values()
                if isinstance(meta, dict)
            )
            if any_spec:
                has_spec = True
            else:
                has_no_spec = True
        if has_spec and has_no_spec:
            dynamic_template_spec_loss_duplicate_count += max(0, len(keys) - 1)

    mixed_source = source_count["en"] > 0 and source_count["zh_CN"] > 0

    if owner_name == "event_tips":
        required_suffixes = {
            "event_status_remaining_days",
            "event_status_remaining_hours",
            "event_status_remaining_minutes",
            "event_status_finished",
            "event_status_display_with_title",
        }
        for suffix in required_suffixes:
            for lang in REQUIRED_LANGS:
                expected_key = f"module.event_tips.ui.{suffix}"
                if expected_key not in maps.get(lang, {}):
                    event_status_resource_missing_count += 1

    translation_gap_count = (
        missing_from_en["zh_CN"]
        + missing_from_en["zh_HK"]
        + missing_from_zh_cn["en"]
        + missing_from_zh_cn["zh_HK"]
    )

    # Chinese key suffixes are now allowed (tracked as warning-only metrics),
    # so they must not block CI.
    structural_issues = english_values_in_zh_cn + chinese_values_in_en + owner_drift_keys
    dynamic_issues = (
        dynamic_template_field_mismatch_count
        + dynamic_template_format_spec_mismatch_count
        + dynamic_template_unresolved_runtime_key_count
        + dynamic_template_spec_loss_duplicate_count
    )
    blocking_issues = (
        len(missing_files)
        + sum(source_key_missing.values())
        + structural_issues
        + dynamic_issues
        + event_status_resource_missing_count
    )

    return {
        "owner": owner_name,
        "source_lang": source_count,
        "mixed_source": mixed_source,
        "missing_files": missing_files,
        "source_key_missing": source_key_missing,
        "missing_keys": {
            "from_en->zh_CN": missing_from_en["zh_CN"],
            "from_en->zh_HK": missing_from_en["zh_HK"],
            "from_zh_CN->en": missing_from_zh_cn["en"],
            "from_zh_CN->zh_HK": missing_from_zh_cn["zh_HK"],
        },
        "structural": {
            "english_values_in_zh_CN": english_values_in_zh_cn,
            "chinese_values_in_en": chinese_values_in_en,
            "chinese_key_suffixes": chinese_key_suffixes,
            "owner_drift_keys": owner_drift_keys,
        },
        "dynamic": {
            "dynamic_template_count": dynamic_template_count,
            "dynamic_template_missing_translation_count": dynamic_template_missing_translation_count,
            "dynamic_template_field_mismatch_count": dynamic_template_field_mismatch_count,
            "dynamic_template_format_spec_mismatch_count": dynamic_template_format_spec_mismatch_count,
            "dynamic_template_unresolved_runtime_key_count": dynamic_template_unresolved_runtime_key_count,
            "dynamic_template_duplicate_template_count": dynamic_template_duplicate_template_count,
            "dynamic_template_spec_loss_duplicate_count": dynamic_template_spec_loss_duplicate_count,
        },
        "event_status_resource_missing_count": event_status_resource_missing_count,
        "translation_gap_count": translation_gap_count,
        "issue_count": blocking_issues,
    }


def collect_report() -> dict:
    framework_base = ROOT / "app" / "framework" / "i18n"
    module_id_map = _module_id_to_owner()
    framework_report = _audit_owner(framework_base, "framework", module_id_map=module_id_map)

    modules_root = ROOT / "app" / "features" / "modules"
    registered_dirs = _discover_registered_module_dirs(modules_root)

    module_reports = []
    for module_dir in sorted([p for p in modules_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        if module_dir.name.startswith("__"):
            continue
        if module_dir.name not in registered_dirs:
            continue
        module_reports.append(_audit_owner(module_dir / "i18n", module_dir.name, module_id_map=module_id_map))

    issue_count = framework_report["issue_count"] + sum(item["issue_count"] for item in module_reports)
    translation_gap_count = framework_report["translation_gap_count"] + sum(item["translation_gap_count"] for item in module_reports)
    mixed_source_modules = [item["owner"] for item in module_reports if item["mixed_source"]]

    dynamic_summary = {
        "dynamic_template_count": framework_report["dynamic"]["dynamic_template_count"] + sum(item["dynamic"]["dynamic_template_count"] for item in module_reports),
        "dynamic_template_missing_translation_count": framework_report["dynamic"]["dynamic_template_missing_translation_count"] + sum(item["dynamic"]["dynamic_template_missing_translation_count"] for item in module_reports),
        "dynamic_template_field_mismatch_count": framework_report["dynamic"]["dynamic_template_field_mismatch_count"] + sum(item["dynamic"]["dynamic_template_field_mismatch_count"] for item in module_reports),
        "dynamic_template_format_spec_mismatch_count": framework_report["dynamic"]["dynamic_template_format_spec_mismatch_count"] + sum(item["dynamic"]["dynamic_template_format_spec_mismatch_count"] for item in module_reports),
        "dynamic_template_unresolved_runtime_key_count": framework_report["dynamic"]["dynamic_template_unresolved_runtime_key_count"] + sum(item["dynamic"]["dynamic_template_unresolved_runtime_key_count"] for item in module_reports),
        "dynamic_template_duplicate_template_count": framework_report["dynamic"]["dynamic_template_duplicate_template_count"] + sum(item["dynamic"]["dynamic_template_duplicate_template_count"] for item in module_reports),
        "dynamic_template_spec_loss_duplicate_count": framework_report["dynamic"]["dynamic_template_spec_loss_duplicate_count"] + sum(item["dynamic"]["dynamic_template_spec_loss_duplicate_count"] for item in module_reports),
    }
    event_status_resource_missing_count = framework_report.get("event_status_resource_missing_count", 0) + sum(
        item.get("event_status_resource_missing_count", 0) for item in module_reports
    )

    return {
        "summary": {
            "issue_count": issue_count,
            "translation_gap_count": translation_gap_count,
            "mixed_source_module_count": len(mixed_source_modules),
            "mixed_source_modules": mixed_source_modules,
            "event_status_resource_missing_count": event_status_resource_missing_count,
            **dynamic_summary,
        },
        "framework": framework_report,
        "modules": module_reports,
    }


def _format_text(report: dict) -> str:
    lines: list[str] = []
    lines.append("[framework]")
    fw = report["framework"]
    lines.append(f"{fw['owner']}:")
    lines.append(f"  source_lang: en={fw['source_lang']['en']}, zh_CN={fw['source_lang']['zh_CN']}, zh_HK={fw['source_lang']['zh_HK']}")
    lines.append(f"  mixed_source: {'yes' if fw['mixed_source'] else 'no'}")
    lines.append(f"  missing_files: {', '.join(fw['missing_files']) if fw['missing_files'] else 'none'}")
    lines.append(
        "  source_key_missing: "
        f"en={fw['source_key_missing']['en']}, "
        f"zh_CN={fw['source_key_missing']['zh_CN']}, "
        f"zh_HK={fw['source_key_missing']['zh_HK']}"
    )
    lines.append(
        "  structural: "
        f"en_in_zh_CN={fw['structural']['english_values_in_zh_CN']}, "
        f"zh_in_en={fw['structural']['chinese_values_in_en']}, "
        f"zh_key_suffix={fw['structural']['chinese_key_suffixes']}, "
        f"owner_drift={fw['structural']['owner_drift_keys']}"
    )
    lines.append(
        "  dynamic: "
        f"count={fw['dynamic']['dynamic_template_count']}, "
        f"missing={fw['dynamic']['dynamic_template_missing_translation_count']}, "
        f"field_mismatch={fw['dynamic']['dynamic_template_field_mismatch_count']}, "
        f"format_spec_mismatch={fw['dynamic']['dynamic_template_format_spec_mismatch_count']}, "
        f"unresolved={fw['dynamic']['dynamic_template_unresolved_runtime_key_count']}, "
        f"duplicates={fw['dynamic']['dynamic_template_duplicate_template_count']}, "
        f"spec_loss_duplicates={fw['dynamic']['dynamic_template_spec_loss_duplicate_count']}"
    )
    lines.append(f"  event_status_resource_missing_count={fw.get('event_status_resource_missing_count', 0)}")

    lines.append("")
    lines.append("[modules]")
    for item in report["modules"]:
        lines.append(f"{item['owner']}:")
        lines.append(f"  source_lang: en={item['source_lang']['en']}, zh_CN={item['source_lang']['zh_CN']}, zh_HK={item['source_lang']['zh_HK']}")
        lines.append(f"  mixed_source: {'yes' if item['mixed_source'] else 'no'}")
        lines.append(f"  missing_files: {', '.join(item['missing_files']) if item['missing_files'] else 'none'}")
        lines.append(
            "  source_key_missing: "
            f"en={item['source_key_missing']['en']}, "
            f"zh_CN={item['source_key_missing']['zh_CN']}, "
            f"zh_HK={item['source_key_missing']['zh_HK']}"
        )
        lines.append(
            "  structural: "
            f"en_in_zh_CN={item['structural']['english_values_in_zh_CN']}, "
            f"zh_in_en={item['structural']['chinese_values_in_en']}, "
            f"zh_key_suffix={item['structural']['chinese_key_suffixes']}, "
            f"owner_drift={item['structural']['owner_drift_keys']}"
        )
        lines.append(
            "  dynamic: "
            f"count={item['dynamic']['dynamic_template_count']}, "
            f"missing={item['dynamic']['dynamic_template_missing_translation_count']}, "
            f"field_mismatch={item['dynamic']['dynamic_template_field_mismatch_count']}, "
            f"format_spec_mismatch={item['dynamic']['dynamic_template_format_spec_mismatch_count']}, "
            f"unresolved={item['dynamic']['dynamic_template_unresolved_runtime_key_count']}, "
            f"duplicates={item['dynamic']['dynamic_template_duplicate_template_count']}, "
            f"spec_loss_duplicates={item['dynamic']['dynamic_template_spec_loss_duplicate_count']}"
        )
        lines.append(f"  event_status_resource_missing_count={item.get('event_status_resource_missing_count', 0)}")

    if report["summary"]["mixed_source_module_count"]:
        lines.append("")
        lines.append("[warnings]")
        lines.append("  mixed_source_modules: " + ", ".join(report["summary"]["mixed_source_modules"]))

    lines.append("")
    lines.append(f"summary.issue_count={report['summary']['issue_count']}")
    lines.append(f"summary.translation_gap_count={report['summary']['translation_gap_count']}")
    lines.append(f"summary.dynamic_template_count={report['summary']['dynamic_template_count']}")
    lines.append(f"summary.dynamic_template_missing_translation_count={report['summary']['dynamic_template_missing_translation_count']}")
    lines.append(f"summary.dynamic_template_field_mismatch_count={report['summary']['dynamic_template_field_mismatch_count']}")
    lines.append(f"summary.dynamic_template_format_spec_mismatch_count={report['summary']['dynamic_template_format_spec_mismatch_count']}")
    lines.append(f"summary.dynamic_template_unresolved_runtime_key_count={report['summary']['dynamic_template_unresolved_runtime_key_count']}")
    lines.append(f"summary.dynamic_template_duplicate_template_count={report['summary']['dynamic_template_duplicate_template_count']}")
    lines.append(f"summary.dynamic_template_spec_loss_duplicate_count={report['summary']['dynamic_template_spec_loss_duplicate_count']}")
    lines.append(f"summary.event_status_resource_missing_count={report['summary']['event_status_resource_missing_count']}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit i18n completeness and structural correctness")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    parser.add_argument("--fail-on-issues", action="store_true", help="Return non-zero when blocking issues are found")
    args = parser.parse_args()

    report = collect_report()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))

    if args.fail_on_issues and report["summary"]["issue_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
