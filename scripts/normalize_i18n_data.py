#!/usr/bin/env python
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
import string

ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = ROOT / "app" / "features" / "modules"
FRAMEWORK_I18N = ROOT / "app" / "framework" / "i18n"
LANGS = ("en", "zh_CN", "zh_HK")
REQUIRED_LANGS = ("en", "zh_CN")
OPTIONAL_LANGS = ("zh_HK",)

HAN_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
HASHLIKE_SUFFIX_RE = re.compile(r"^(?:[0-9a-f]{8,}|h[0-9a-f]{6,}|txt_[0-9a-f]{8,}|tmpl_[0-9a-f]{8,})$")
SYNTHETIC_CN_SUFFIX_RE = re.compile(r"^cn_text_\d+(?:_\d+)?$")
LEGACY_TIPS_KEY_RE = re.compile(r"^module\.([a-z0-9_]+)\.ui\.tips_[a-z0-9_]+$")


def _load_json(path: Path) -> dict:
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
    return data


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _remove_legacy_zh_tw_file(i18n_dir: Path) -> bool:
    zh_tw = i18n_dir / "zh_TW.json"
    if zh_tw.exists():
        zh_tw.unlink(missing_ok=True)
        return True
    return False


def _classify_value_lang(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    has_han = bool(HAN_RE.search(value))
    has_latin = bool(LATIN_RE.search(value))
    if has_han:
        return "zh_CN"
    if has_latin and not has_han:
        return "en"
    return None


def _snake_from_text(value: str) -> str:
    raw = value.strip().lower()
    chars: list[str] = []
    for ch in raw:
        code = ord(ch)
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            chars.append(ch)
            continue
        if 0x4E00 <= code <= 0x9FFF:
            chars.append(ch)
            continue
        chars.append("_")
    lowered = re.sub(r"_+", "_", "".join(chars)).strip("_")
    if not lowered:
        return ""
    if not re.match(r"^[a-z\u4e00-\u9fff]", lowered):
        lowered = f"text_{lowered}"
    return lowered[:80]


def _key_has_chinese_suffix(key: str) -> bool:
    suffix = key.rsplit(".", 1)[-1]
    return bool(HAN_RE.search(suffix))


def _owner_dirs() -> dict[str, Path]:
    owners = {"framework": FRAMEWORK_I18N}
    for module_dir in MODULES_ROOT.iterdir():
        if not module_dir.is_dir() or module_dir.name.startswith("__"):
            continue
        i18n_dir = module_dir / "i18n"
        if i18n_dir.exists():
            owners[module_dir.name] = i18n_dir
    return owners


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


def _semantic_suffix(key: str, all_lang_maps: dict[str, dict[str, str]], used: set[str], seq: int) -> tuple[str, int]:
    en_val = all_lang_maps["en"].get(key, "")
    zh_val = all_lang_maps["zh_CN"].get(key, "")
    suffix = ""
    if _classify_value_lang(en_val) == "en":
        suffix = _snake_from_text(en_val)
    elif _classify_value_lang(zh_val) == "zh_CN":
        suffix = _snake_from_text(zh_val)

    if not suffix:
        suffix = f"cn_text_{seq:04d}"
        seq += 1

    candidate = suffix
    idx = 2
    while candidate in used:
        candidate = f"{suffix}_{idx}"
        idx += 1
    used.add(candidate)
    return candidate, seq


def _normalize_template_meta(template_meta: dict[str, dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, raw in template_meta.items():
        if not isinstance(raw, dict):
            continue
        rec = dict(raw)
        fields = rec.get("fields")
        if isinstance(fields, list):
            normalized_fields: list[str] = []
            seen: set[str] = set()
            for f in fields:
                if not isinstance(f, str):
                    continue
                if f in seen:
                    continue
                seen.add(f)
                normalized_fields.append(f)
            rec["fields"] = normalized_fields
        else:
            rec["fields"] = []
        if "kind" not in rec:
            rec["kind"] = "dynamic_template"
        out[str(key)] = rec
    return out


def _canonicalize_template_ignoring_spec(template: str) -> str:
    formatter = string.Formatter()
    chunks: list[str] = []
    for literal, field_name, _format_spec, _conversion in formatter.parse(template or ""):
        chunks.append(literal or "")
        if field_name:
            base = field_name.split("[", 1)[0].split(".", 1)[0]
            chunks.append("{" + (base or "value") + "}")
    return "".join(chunks)


def _canonicalize_template_structure(template: str) -> str:
    formatter = string.Formatter()
    chunks: list[str] = []
    for literal, field_name, _format_spec, _conversion in formatter.parse(template or ""):
        chunks.append(literal or "")
        if field_name:
            chunks.append("{}")
    return "".join(chunks)


def _template_spec_score(template: str) -> tuple[int, int]:
    formatter = string.Formatter()
    spec_count = 0
    field_count = 0
    for _literal, field_name, format_spec, conversion in formatter.parse(template or ""):
        if not field_name:
            continue
        field_count += 1
        if (format_spec or "") or (conversion or ""):
            spec_count += 1
    return spec_count, field_count


def _key_semantic_score(key: str, template: str) -> tuple[int, int, int, int]:
    suffix = key.rsplit(".", 1)[-1]
    is_semantic = 0 if HASHLIKE_SUFFIX_RE.fullmatch(suffix) else 1
    spec_count, field_count = _template_spec_score(template)
    generic_field_penalty = template.count("{value_") + template.count("{value}")
    return (is_semantic, spec_count, field_count, -generic_field_penalty)


def _static_key_priority(key: str) -> tuple[int, int, int, int]:
    """Pick a stable winner among duplicate static keys."""
    suffix = key.rsplit(".", 1)[-1]
    is_synthetic_cn = bool(SYNTHETIC_CN_SUFFIX_RE.fullmatch(suffix))
    is_hashlike = bool(HASHLIKE_SUFFIX_RE.fullmatch(suffix))
    # semantic key > hashlike key > synthetic cn_text key
    if not is_synthetic_cn and not is_hashlike:
        kind_score = 2
    elif is_hashlike:
        kind_score = 1
    else:
        kind_score = 0
    # avoid numbered tail variants like *_2 when a base key exists
    numbered_tail = 0 if re.search(r"_\d+$", suffix) else 1
    return (kind_score, numbered_tail, -len(suffix), 1 if ".log." in key else 0)


def _is_nonsemantic_static_key(key: str) -> bool:
    suffix = key.rsplit(".", 1)[-1]
    return bool(SYNTHETIC_CN_SUFFIX_RE.fullmatch(suffix) or HASHLIKE_SUFFIX_RE.fullmatch(suffix))

def _normalize_markdown_text(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("### tips") or line.startswith("### ??"):
            continue
        if line.startswith("- "):
            line = f"* {line[2:].strip()}"
        lines.append(line)
    return "\n".join(lines).strip()


def _prune_legacy_tips_aliases(
    maps: dict[str, dict[str, str]],
    source_map: dict[str, str],
    template_meta: dict[str, dict],
    stats: dict[str, int],
) -> None:
    candidate_keys = set(source_map.keys())
    for lang in LANGS:
        candidate_keys.update(maps.get(lang, {}).keys())

    for key in sorted(candidate_keys):
        matched = LEGACY_TIPS_KEY_RE.match(key)
        if not matched:
            continue

        module_id = matched.group(1)
        desc_key = f"module.{module_id}.description"
        desc_present = desc_key in source_map or any(desc_key in maps.get(lang, {}) for lang in LANGS)
        if not desc_present:
            continue

        for lang in LANGS:
            tip_val = maps.get(lang, {}).get(key)
            if tip_val is None:
                continue
            if desc_key not in maps.get(lang, {}):
                maps[lang][desc_key] = tip_val
                stats["legacy_tips_alias_migrated"] += 1

        if desc_key not in source_map and key in source_map:
            source_map[desc_key] = source_map[key]
        if desc_key not in template_meta and key in template_meta:
            template_meta[desc_key] = template_meta[key]

        tip_norm = {
            _normalize_markdown_text(maps.get(lang, {}).get(key, ""))
            for lang in LANGS
            if maps.get(lang, {}).get(key)
        }
        desc_norm = {
            _normalize_markdown_text(maps.get(lang, {}).get(desc_key, ""))
            for lang in LANGS
            if maps.get(lang, {}).get(desc_key)
        }

        if not tip_norm:
            continue

        removable = bool(tip_norm & desc_norm)
        if not removable:
            removable = all(
                (not maps.get(lang, {}).get(key)) or (maps.get(lang, {}).get(desc_key) is not None)
                for lang in LANGS
            )
        if not removable:
            continue

        for lang in LANGS:
            maps.get(lang, {}).pop(key, None)
        source_map.pop(key, None)
        template_meta.pop(key, None)
        stats["legacy_tips_alias_pruned"] += 1


def _normalize_owner_keys(owner: str, maps: dict[str, dict[str, str]], source_map: dict[str, str], template_meta: dict[str, dict], stats: dict[str, int]) -> tuple[dict[str, dict[str, str]], dict[str, str], dict[str, dict]]:
    template_meta = _normalize_template_meta(template_meta)

    all_keys = set(source_map.keys())
    for lang in LANGS:
        all_keys.update(maps[lang].keys())
    all_keys.update(template_meta.keys())

    # 0) deduplicate spec-loss dynamic templates by canonical skeleton.
    dynamic_by_canonical: dict[str, list[str]] = defaultdict(list)
    for key, meta in template_meta.items():
        source_template = str(meta.get("source_template", "") or "")
        if not source_template:
            continue
        canonical_key = (
            _canonicalize_template_structure(source_template)
            + "||"
            + _canonicalize_template_ignoring_spec(source_template)
        )
        dynamic_by_canonical[canonical_key].append(key)

    for canonical_skeleton, dup_keys in dynamic_by_canonical.items():
        if len(dup_keys) < 2:
            continue
        ordered = sorted(
            dup_keys,
            key=lambda key: (
                _key_semantic_score(
                    key,
                    str(template_meta.get(key, {}).get("source_template", "") or ""),
                ),
                len(str(template_meta.get(key, {}).get("source_template", "") or "")),
            ),
            reverse=True,
        )
        keep_key = ordered[0]
        for drop_key in ordered[1:]:
            for lang in LANGS:
                keep_val = maps[lang].get(keep_key)
                drop_val = maps[lang].get(drop_key)
                if keep_val is None and drop_val is not None:
                    maps[lang][keep_key] = drop_val
                maps[lang].pop(drop_key, None)
            if keep_key not in source_map and drop_key in source_map:
                source_map[keep_key] = source_map[drop_key]
            source_map.pop(drop_key, None)
            template_meta.pop(drop_key, None)
            stats["dynamic_template_spec_loss_duplicate_count"] += 1

    # 1) normalize Chinese natural-language key suffixes.
    rename_pairs: dict[str, str] = {}
    used_suffixes = {k.rsplit(".", 1)[-1] for k in all_keys}
    seq = 1
    for key in sorted(all_keys):
        if not _key_has_chinese_suffix(key):
            continue
        prefix = key.rsplit(".", 1)[0]
        new_suffix, seq = _semantic_suffix(key, maps, used_suffixes, seq)
        new_key = f"{prefix}.{new_suffix}"
        while new_key in all_keys or new_key in rename_pairs.values():
            new_suffix, seq = _semantic_suffix(key, maps, used_suffixes, seq)
            new_key = f"{prefix}.{new_suffix}"
        rename_pairs[key] = new_key

    for old_key, new_key in rename_pairs.items():
        for lang in LANGS:
            if old_key in maps[lang]:
                maps[lang][new_key] = maps[lang].pop(old_key)
        if old_key in source_map:
            source_map[new_key] = source_map.pop(old_key)
        if old_key in template_meta:
            template_meta[new_key] = template_meta.pop(old_key)
        stats["normalized_keys"] += 1

    all_keys = set(source_map.keys())
    for lang in LANGS:
        all_keys.update(maps[lang].keys())
    all_keys.update(template_meta.keys())

    # 2) source-of-truth placement and cleanup of mirrored misplaced source values.
    for key in sorted(all_keys):
        src = source_map.get(key)
        if src not in {"en", "zh_CN"}:
            vals = [maps[lang].get(key, "") for lang in LANGS]
            langs = [_classify_value_lang(v) for v in vals if v]
            src = "zh_CN" if "zh_CN" in langs else "en"
            source_map[key] = src

        source_val = maps[src].get(key)
        if source_val is None:
            for lang in ("en", "zh_CN", "zh_HK"):
                if key in maps[lang]:
                    source_val = maps[lang][key]
                    break
        if source_val is None:
            continue
        maps[src][key] = source_val

        for lang in LANGS:
            if lang == src:
                continue
            val = maps[lang].get(key)
            if val is None:
                continue
            val_lang = _classify_value_lang(val)
            if src == "en" and val_lang == "en":
                maps[lang].pop(key, None)
                stats["moved_misplaced_values"] += 1
            elif src == "zh_CN" and val_lang == "zh_CN":
                maps[lang].pop(key, None)
                stats["moved_misplaced_values"] += 1

    # 3) prune stale template metadata.
    for key in list(template_meta.keys()):
        if key not in source_map and all(key not in maps[lang] for lang in LANGS):
            template_meta.pop(key, None)

    # 4) eliminate hashlike duplicate keys when semantic key exists with same template structure.
    groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for key, src in source_map.items():
        if src not in {"en", "zh_CN"}:
            continue
        source_val = maps.get(src, {}).get(key)
        if not isinstance(source_val, str) or "{" not in source_val or "}" not in source_val:
            continue
        canonical = _canonicalize_template_structure(source_val)
        context_prefix = key.rsplit(".", 1)[0]
        groups[(src, context_prefix, canonical)].append(key)

    for (_src, _prefix, _canonical), keys in groups.items():
        if len(keys) < 2:
            continue
        semantic_keys = [k for k in keys if not HASHLIKE_SUFFIX_RE.fullmatch(k.rsplit(".", 1)[-1])]
        if not semantic_keys:
            continue
        keep_key = sorted(semantic_keys)[0]
        for drop_key in keys:
            if drop_key == keep_key:
                continue
            if not HASHLIKE_SUFFIX_RE.fullmatch(drop_key.rsplit(".", 1)[-1]):
                continue
            for lang in LANGS:
                keep_val = maps[lang].get(keep_key)
                drop_val = maps[lang].get(drop_key)
                if keep_val is None and drop_val is not None:
                    maps[lang][keep_key] = drop_val
                maps[lang].pop(drop_key, None)
            source_map.pop(drop_key, None)
            template_meta.pop(drop_key, None)
            stats["hashlike_merged"] += 1

    # 5) merge duplicated static keys with same source value under same context prefix.
    static_groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for key, src in source_map.items():
        if src not in {"en", "zh_CN"}:
            continue
        if key in template_meta:
            continue
        source_val = maps.get(src, {}).get(key)
        if not isinstance(source_val, str) or not source_val:
            continue
        context_prefix = key.rsplit(".", 1)[0]
        static_groups[(src, context_prefix, source_val)].append(key)

    for (_src, _prefix, _source_val), keys in static_groups.items():
        if len(keys) < 2:
            continue
        nonsemantic_keys = {k for k in keys if _is_nonsemantic_static_key(k)}
        # Keep semantic aliases; only collapse synthetic/hash-like duplicates.
        if not nonsemantic_keys:
            continue
        ordered = sorted(keys, key=_static_key_priority, reverse=True)
        keep_key = ordered[0]
        for drop_key in ordered[1:]:
            if drop_key not in nonsemantic_keys:
                continue
            for lang in LANGS:
                keep_val = maps[lang].get(keep_key)
                drop_val = maps[lang].get(drop_key)
                if keep_val is None and drop_val is not None:
                    maps[lang][keep_key] = drop_val
                maps[lang].pop(drop_key, None)
            source_map.pop(drop_key, None)
            template_meta.pop(drop_key, None)
            stats["static_duplicate_merged"] += 1

    # 6) prune legacy long-form tips aliases when canonical module.<id>.description exists.
    _prune_legacy_tips_aliases(maps, source_map, template_meta, stats)

    return maps, source_map, template_meta


def main() -> int:
    owners = _owner_dirs()
    id_to_owner = _module_id_to_owner()

    owner_data: dict[str, dict] = {}
    for owner, i18n_dir in owners.items():
        maps = {lang: _load_json(i18n_dir / f"{lang}.json") for lang in LANGS}
        maps = {lang: {str(k): str(v) for k, v in maps[lang].items()} for lang in LANGS}
        source_map = {str(k): str(v) for k, v in _load_json(i18n_dir / "source_map.json").items()}
        template_meta_raw = _load_json(i18n_dir / "template_meta.json")
        template_meta = {str(k): v for k, v in template_meta_raw.items() if isinstance(v, dict)}
        owner_data[owner] = {"dir": i18n_dir, "maps": maps, "source_map": source_map, "template_meta": template_meta}

    stats = defaultdict(int)

    # Per-owner normalization.
    for owner, payload in owner_data.items():
        maps, source_map, template_meta = _normalize_owner_keys(owner, payload["maps"], payload["source_map"], payload["template_meta"], stats)
        payload["maps"] = maps
        payload["source_map"] = source_map
        payload["template_meta"] = template_meta

    # 4) owner drift correction by module id prefix.
    for owner, payload in list(owner_data.items()):
        if owner == "framework":
            continue
        maps = payload["maps"]
        source_map = payload["source_map"]
        template_meta = payload["template_meta"]

        keys = set(source_map.keys())
        for lang in LANGS:
            keys.update(maps[lang].keys())
        keys.update(template_meta.keys())

        for key in sorted(keys):
            if not key.startswith("module."):
                continue
            parts = key.split(".")
            if len(parts) < 2:
                continue
            module_id = parts[1]
            expected_owner = id_to_owner.get(module_id)
            if not expected_owner or expected_owner == owner or expected_owner not in owner_data:
                continue

            target = owner_data[expected_owner]
            for lang in LANGS:
                if key in maps[lang]:
                    target["maps"][lang][key] = maps[lang].pop(key)
            if key in source_map:
                target["source_map"][key] = source_map.pop(key)
            if key in template_meta:
                target["template_meta"][key] = template_meta.pop(key)
            stats["owner_drift_moved"] += 1

    # Save files.
    changed_files = 0
    for owner, payload in owner_data.items():
        i18n_dir = payload["dir"]
        if _remove_legacy_zh_tw_file(i18n_dir):
            changed_files += 1
        for lang in LANGS:
            path = i18n_dir / f"{lang}.json"
            before = _load_json(path)
            after = payload["maps"][lang]
            if lang in OPTIONAL_LANGS and not path.exists() and not after:
                continue
            if lang in OPTIONAL_LANGS and path.exists() and not after:
                path.unlink(missing_ok=True)
                changed_files += 1
                continue
            if before != after or (lang in REQUIRED_LANGS and not path.exists()):
                _save_json(path, after)
                changed_files += 1
        sm_path = i18n_dir / "source_map.json"
        before_sm = _load_json(sm_path)
        after_sm = dict(sorted(payload["source_map"].items()))
        if before_sm != after_sm:
            _save_json(sm_path, after_sm)
            changed_files += 1

        tm_path = i18n_dir / "template_meta.json"
        before_tm = _load_json(tm_path)
        after_tm = dict(sorted(payload["template_meta"].items()))
        if before_tm != after_tm:
            _save_json(tm_path, after_tm)
            changed_files += 1

    print(f"changed_files={changed_files}")
    print(f"normalized_keys={stats['normalized_keys']}")
    print(f"moved_misplaced_values={stats['moved_misplaced_values']}")
    print(f"owner_drift_moved={stats['owner_drift_moved']}")
    print(f"dynamic_template_spec_loss_duplicate_count={stats['dynamic_template_spec_loss_duplicate_count']}")
    print(f"hashlike_merged={stats['hashlike_merged']}")
    print(f"static_duplicate_merged={stats['static_duplicate_merged']}")
    print(f"legacy_tips_alias_migrated={stats['legacy_tips_alias_migrated']}")
    print(f"legacy_tips_alias_pruned={stats['legacy_tips_alias_pruned']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
