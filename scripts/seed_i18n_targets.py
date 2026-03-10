#!/usr/bin/env python
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SUPPORTED_LANGS = ["en", "zh_CN", "zh_HK"]
_MSGID_RE = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_\-\.]*$")


def _contains_han(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _contains_unsupported_non_ascii(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if code < 128:
            continue
        if "\u4e00" <= ch <= "\u9fff":
            continue
        return True
    return False


def classify_source_language(text: str) -> str:
    if not text.strip():
        raise ValueError("empty source text")
    if _contains_unsupported_non_ascii(text):
        raise ValueError(f"unsupported language/script: {text!r}")
    return "zh_CN" if _contains_han(text) else "en"


def slugify(text: str) -> str:
    if _contains_han(text):
        return f"h{abs(hash(text)) & 0xFFFFFFFF:x}"
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:64] if slug else "text"


def infer_owner(path: Path) -> tuple[str, str | None]:
    parts = list(path.parts)
    try:
        idx = parts.index("modules")
        return "module", parts[idx + 1]
    except Exception:
        pass
    return "framework", None


def owner_prefix(owner_scope: str, owner_module: str | None) -> str:
    if owner_scope == "module" and owner_module:
        return f"module.{owner_module}"
    return "framework"


def context_from_parent(parent: ast.AST) -> str:
    if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
        if parent.func.attr in {"debug", "info", "warning", "error", "critical", "exception", "log"}:
            return "log"
    return "ui"


def extract_source_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                placeholder = "value"
                if isinstance(v.value, ast.Name):
                    placeholder = v.value.id
                parts.append("{" + placeholder + "}")
        return "".join(parts)
    return None


def catalog_file(owner_scope: str, owner_module: str | None, lang: str) -> Path:
    if owner_scope == "module" and owner_module:
        return ROOT / "app" / "features" / "modules" / owner_module / "i18n" / f"{lang}.json"
    return ROOT / "app" / "framework" / "i18n" / f"{lang}.json"


def load_catalog(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def save_catalog(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect_expected():
    expected = defaultdict(list)
    for path in ROOT.joinpath("app").rglob("*.py"):
        if path.parts[-3:-1] == ("framework", "i18n"):
            continue

        src = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(src)
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        owner_scope, owner_module = infer_owner(path)
        prefix = owner_prefix(owner_scope, owner_module)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "_":
                continue
            if not node.args:
                raise ValueError(f"{path}:_() requires a source text argument")

            source_text = extract_source_text(node.args[0])
            if source_text is None:
                raise ValueError(f"{path}:_() first argument must be string literal or f-string")
            source_lang = classify_source_language(source_text)

            msgid = None
            for kw in node.keywords:
                if kw.arg == "msgid":
                    if not isinstance(kw.value, ast.Constant) or not isinstance(kw.value.value, str):
                        raise ValueError(f"{path}:msgid must be a string literal")
                    msgid = kw.value.value.strip()
                    if msgid and not _MSGID_RE.match(msgid):
                        raise ValueError(f"{path}:invalid msgid format: {msgid!r}")

            suffix = msgid or slugify(source_text)
            context = context_from_parent(parents.get(node))
            key = f"{prefix}.{context}.{suffix}"
            expected[(owner_scope, owner_module)].append((key, source_lang, source_text))
    return expected


def main() -> int:
    expected = collect_expected()
    filled = 0
    files_changed = set()

    for owner, items in expected.items():
        owner_scope, owner_module = owner
        catalogs = {
            lang: load_catalog(catalog_file(owner_scope, owner_module, lang))
            for lang in SUPPORTED_LANGS
        }

        for key, source_lang, source_text in items:
            source_catalog = catalogs[source_lang]
            if key not in source_catalog:
                source_catalog[key] = source_text
                filled += 1
                files_changed.add(catalog_file(owner_scope, owner_module, source_lang))

            for target_lang in SUPPORTED_LANGS:
                if target_lang == source_lang:
                    continue
                target_catalog = catalogs[target_lang]
                if key not in target_catalog:
                    target_catalog[key] = source_catalog.get(key, source_text)
                    filled += 1
                    files_changed.add(catalog_file(owner_scope, owner_module, target_lang))

        for lang, catalog in catalogs.items():
            path = catalog_file(owner_scope, owner_module, lang)
            save_catalog(path, catalog)

    print(f"filled_entries={filled}")
    print(f"changed_files={len(files_changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
