from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.framework.i18n.runtime import report_i18n_event
from app.framework.infra.ui_manifest.models import UIDefinition


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return data if isinstance(data, dict) else {}


@dataclass(slots=True)
class ManifestSnapshot:
    path: Path | None
    revision: int
    definitions: dict[str, UIDefinition]
    warnings: list[str]
    discovered_definitions: dict[str, UIDefinition] = field(default_factory=dict)


class ManifestEngine:
    """Runtime read-only manifest loader and query service."""

    def __init__(self):
        self._cache: dict[str, ManifestSnapshot] = {}
        self._rev = 0

    def _cache_key(self, module_id: str, base: Path | None) -> str:
        return f"{module_id}:{str(base) if base else '<none>'}"

    def load(self, module_id: str, generated_path: Path | None, source_path: Path | None) -> ManifestSnapshot:
        key = self._cache_key(module_id, generated_path or source_path)
        if key in self._cache:
            return self._cache[key]

        path = generated_path if (generated_path and generated_path.exists()) else source_path
        raw = _load_json(path) if path else {}
        defs, warnings = self._parse_manifest(module_id, raw, path)
        self._rev += 1
        snapshot = ManifestSnapshot(path=path, revision=self._rev, definitions=defs, warnings=warnings)
        self._cache[key] = snapshot
        return snapshot

    def get_definition(self, module_id: str, ui_id: str, generated_path: Path | None, source_path: Path | None) -> UIDefinition | None:
        snapshot = self.load(module_id, generated_path, source_path)
        return snapshot.definitions.get(ui_id)

    def register_discovered_definition(
        self,
        module_id: str,
        generated_path: Path | None,
        source_path: Path | None,
        definition: UIDefinition,
    ) -> None:
        key = self._cache_key(module_id, generated_path or source_path)
        snapshot = self._cache.get(key)
        if snapshot is None:
            return
        snapshot.discovered_definitions[definition.id] = definition

    def _parse_manifest(self, module_id: str, raw: dict[str, Any], path: Path | None) -> tuple[dict[str, UIDefinition], list[str]]:
        warnings: list[str] = []
        out: dict[str, UIDefinition] = {}

        defs_group = raw.get("definitions", {}) if isinstance(raw.get("definitions"), dict) else {}
        if defs_group:
            for ui_id, node in defs_group.items():
                if not isinstance(node, dict):
                    warnings.append(f"{module_id}:{ui_id}: invalid definition node")
                    continue
                text_map = node.get("text", {}) if isinstance(node.get("text"), dict) else {}
                aliases_raw = node.get("aliases", [])
                aliases = [str(v) for v in aliases_raw if isinstance(v, str)] if isinstance(aliases_raw, list) else []
                image_path = node.get("image") if isinstance(node.get("image"), str) and node.get("image").strip() else None
                pos_node = node.get("position", {}) if isinstance(node.get("position"), dict) else {}
                roi = None
                roi_node = pos_node.get("roi")
                if (not isinstance(roi_node, list)) and all(k in pos_node for k in ("x", "y", "w", "h")):
                    roi_node = [pos_node.get("x"), pos_node.get("y"), pos_node.get("w"), pos_node.get("h")]
                if isinstance(roi_node, list) and len(roi_node) == 4:
                    try:
                        roi = tuple(float(v) for v in roi_node)  # type: ignore[assignment]
                    except Exception:
                        warnings.append(f"{module_id}:{ui_id}: invalid roi")
                match_node = node.get("match", {}) if isinstance(node.get("match"), dict) else {}
                out[str(ui_id)] = UIDefinition(
                    id=str(ui_id),
                    content=image_path or text_map.get("zh_CN") or text_map.get("en"),
                    kind="image" if image_path else "text",
                    text={k: v for k, v in text_map.items() if isinstance(k, str) and isinstance(v, str)},
                    aliases=aliases,
                    image=image_path,
                    position=pos_node if isinstance(pos_node, dict) else None,
                    roi=roi,
                    threshold=float(match_node.get("threshold", 0.5)),
                    include=bool(match_node.get("include", True)),
                    need_ocr=bool(match_node.get("need_ocr", True)),
                    find_type=str(match_node.get("find_type", "image" if image_path else "text")),
                    module_name=module_id,
                    group="generated",
                    extra={
                        "raw_match": match_node,
                        "manifest_path": str(path) if path else "",
                    },
                )
            return out, warnings

        text_group = raw.get("text", {}) if isinstance(raw.get("text"), dict) else {}
        image_group = raw.get("image", {}) if isinstance(raw.get("image"), dict) else {}
        position_group = raw.get("position", {}) if isinstance(raw.get("position"), dict) else {}
        match_group = raw.get("match", {}) if isinstance(raw.get("match"), dict) else {}
        match_default = match_group.get("_default", {}) if isinstance(match_group.get("_default"), dict) else {}
        all_ids = set(text_group.keys()) | set(image_group.keys()) | set(position_group.keys())

        for ui_id in sorted(all_ids):
            text_node = text_group.get(ui_id, {})
            image_node = image_group.get(ui_id, {})
            pos_node = position_group.get(ui_id, {}) if isinstance(position_group.get(ui_id), dict) else {}
            match_node = match_group.get(ui_id, {}) if isinstance(match_group.get(ui_id), dict) else {}
            text_map: dict[str, str] = {}
            aliases: list[str] = []
            if isinstance(text_node, dict):
                value = text_node.get("value")
                if isinstance(value, str):
                    text_map["zh_CN"] = value
                elif isinstance(value, dict):
                    for lang in ("zh_CN", "zh_HK", "en"):
                        v = value.get(lang)
                        if isinstance(v, str) and v.strip():
                            text_map[lang] = v.strip()
                aliases_raw = text_node.get("aliases")
                if isinstance(aliases_raw, list):
                    aliases = [str(v) for v in aliases_raw if isinstance(v, str)]
            image_path = None
            if isinstance(image_node, dict):
                raw_path = image_node.get("path")
                if isinstance(raw_path, str) and raw_path.strip():
                    image_path = raw_path.strip()
            roi = None
            roi_node = pos_node.get("roi")
            if (not isinstance(roi_node, list)) and all(k in pos_node for k in ("x", "y", "w", "h")):
                roi_node = [pos_node.get("x"), pos_node.get("y"), pos_node.get("w"), pos_node.get("h")]
            if isinstance(roi_node, list) and len(roi_node) == 4:
                try:
                    roi = tuple(float(v) for v in roi_node)  # type: ignore[assignment]
                except Exception:
                    warnings.append(f"{module_id}:{ui_id}: invalid roi")
            merged_match: dict[str, Any] = {}
            merged_match.update(match_default)
            merged_match.update(match_node)
            out[str(ui_id)] = UIDefinition(
                id=str(ui_id),
                content=image_path or text_map.get("zh_CN") or text_map.get("en"),
                kind="image" if image_path else "text",
                text=text_map,
                aliases=aliases,
                image=image_path,
                position=pos_node if isinstance(pos_node, dict) else None,
                roi=roi,
                threshold=float(merged_match.get("threshold", 0.5)),
                include=bool(merged_match.get("include", True)),
                need_ocr=bool(merged_match.get("need_ocr", True)),
                find_type=str(merged_match.get("find_type", "image" if image_path else "text")),
                module_name=module_id,
                group="mixed",
                extra={
                    "raw_match": merged_match,
                    "manifest_path": str(path) if path else "",
                },
            )
        if not out:
            report_i18n_event("ui_manifest_empty", module_id)
        return out, warnings
