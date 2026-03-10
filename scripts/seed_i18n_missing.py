#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.framework.i18n.runtime import classify_source_language
from app.framework.i18n.template_render import extract_template_field_details
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]
SOURCE_LANGS = {"en", "zh_CN"}


def _load(path: Path) -> dict[str, str]:
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


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_dynamic_source_lang(template_meta: dict) -> str:
    source_template = template_meta.get("source_template")
    if isinstance(source_template, str) and source_template.strip():
        try:
            return classify_source_language(source_template)
        except Exception:
            return "en"
    return "en"


def _sync_owner(base_dir: Path) -> tuple[int, int]:
    maps = {lang: _load(base_dir / f"{lang}.json") for lang in SUPPORTED_LANGS}
    source_map = _load(base_dir / "source_map.json")
    template_meta = _load_template_meta(base_dir / "template_meta.json")

    all_keys: set[str] = set(source_map.keys())
    for m in maps.values():
        all_keys.update(m.keys())
    all_keys.update(template_meta.keys())

    changed_files = 0
    filled = 0

    for key in sorted(all_keys):
        src = source_map.get(key)
        if src not in SOURCE_LANGS:
            if key in template_meta:
                src = _resolve_dynamic_source_lang(template_meta[key])
            else:
                src = "en" if key in maps["en"] else "zh_CN" if key in maps["zh_CN"] else "en"
            source_map[key] = src

        source_value = maps[src].get(key)
        if source_value is None and key in template_meta:
            source_template = template_meta[key].get("source_template")
            if isinstance(source_template, str) and source_template:
                source_value = source_template
        if source_value is None:
            for lang in SUPPORTED_LANGS:
                if key in maps[lang]:
                    source_value = maps[lang][key]
                    break
        if source_value is None:
            continue

        if maps[src].get(key) != source_value:
            maps[src][key] = source_value
            filled += 1

        meta = template_meta.get(key)
        if isinstance(meta, dict):
            source_template = meta.get("source_template")
            if isinstance(source_template, str) and source_template:
                details = meta.get("field_details")
                expected_details = extract_template_field_details(source_template)
                if details != expected_details:
                    meta["field_details"] = expected_details

    for lang in SUPPORTED_LANGS:
        path = base_dir / f"{lang}.json"
        before = _load(path)
        after = maps[lang]
        if before != after:
            _save(path, after)
            changed_files += 1

    sm_path = base_dir / "source_map.json"
    before_sm = _load(sm_path)
    after_sm = dict(sorted(source_map.items()))
    if before_sm != after_sm:
        _save(sm_path, after_sm)
        changed_files += 1

    tm_path = base_dir / "template_meta.json"
    before_tm = _load_template_meta(tm_path)
    after_tm = dict(sorted(template_meta.items()))
    if before_tm != after_tm:
        _save(tm_path, after_tm)
        changed_files += 1

    return changed_files, filled


def main() -> int:
    files = 0
    filled = 0

    framework_dir = ROOT / "app" / "framework" / "i18n"
    f, c = _sync_owner(framework_dir)
    files += f
    filled += c

    modules_root = ROOT / "app" / "features" / "modules"
    for module_dir in modules_root.iterdir():
        if not module_dir.is_dir() or module_dir.name.startswith("__"):
            continue
        i18n_dir = module_dir / "i18n"
        if not i18n_dir.exists():
            continue
        f, c = _sync_owner(i18n_dir)
        files += f
        filled += c

    print(f"changed_files={files}")
    print(f"filled_entries={filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
