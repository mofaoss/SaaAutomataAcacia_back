#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]


def _load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pick_source_value(
    key: str,
    all_maps: dict[str, dict[str, str]],
) -> tuple[str | None, str | None]:
    """Pick source text for key with zh_CN->others support.

    Priority:
    1) en (default source)
    2) zh_CN
    3) zh_HK
    """
    for lang in ("en", "zh_CN", "zh_HK"):
        value = all_maps.get(lang, {}).get(key)
        if value is not None:
            return lang, value
    return None, None


def _sync_owner(base_dir: Path) -> tuple[int, int]:
    maps: dict[str, dict[str, str]] = {
        lang: _load(base_dir / f"{lang}.json")
        for lang in SUPPORTED_LANGS
    }
    has_any_file = any((base_dir / f"{lang}.json").exists() for lang in SUPPORTED_LANGS)
    all_keys: set[str] = set()
    for m in maps.values():
        all_keys.update(m.keys())

    if not all_keys and not has_any_file:
        return 0, 0

    changed_files = 0
    filled = 0
    for lang in SUPPORTED_LANGS:
        path = base_dir / f"{lang}.json"
        cur = dict(maps.get(lang, {}))
        before = len(cur)
        for k in sorted(all_keys):
            if k not in cur:
                _, source_value = _pick_source_value(k, maps)
                if source_value is None:
                    continue
                cur[k] = source_value
                filled += 1
        if len(cur) != before or not path.exists():
            _save(path, cur)
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
        f, c = _sync_owner(i18n_dir)
        files += f
        filled += c

    print(f"changed_files={files}")
    print(f"filled_entries={filled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
