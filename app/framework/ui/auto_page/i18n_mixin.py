from __future__ import annotations

import re
from functools import lru_cache

from app.framework.application.modules.name_resolver import resolve_display_name
from app.framework.core.module_system.models import SchemaField
from app.framework.i18n import tr
from app.framework.i18n.runtime import _resolve_lang, get_catalog


class AutoPageI18nMixin:
    @staticmethod
    def _snake_key(text: str, *, max_len: int | None = None) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(text or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if max_len is not None and max_len > 0:
            normalized = normalized[:max_len].rstrip("_")
        return normalized or "action"

    @staticmethod
    def _strip_widget_prefix(param_name: str) -> str:
        return re.sub(r"^(SpinBox|ComboBox|CheckBox|LineEdit|DoubleSpinBox|Slider|TextEdit)_", "", str(param_name or ""))

    @staticmethod
    def _looks_like_mojibake(text: str) -> bool:
        if not text:
            return False
        cjk = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
        if cjk > 0:
            return False
        latin_ext = sum(1 for ch in text if 0x00C0 <= ord(ch) <= 0x024F)
        return latin_ext >= 4 and (latin_ext * 2) >= len(text)

    @staticmethod
    def _is_unusable_translated_text(text: str) -> bool:
        stripped = str(text or "").strip()
        if not stripped:
            return True
        if "\ufffd" in stripped:
            return True
        if "?" in stripped or any(ord(ch) == 0xFF1F for ch in stripped):
            has_meaningful = any(ch.isalnum() or (0x4E00 <= ord(ch) <= 0x9FFF) for ch in stripped)
            if not has_meaningful:
                return True
        if AutoPageI18nMixin._looks_like_mojibake(stripped):
            return True
        return False

    @staticmethod
    def _first_translated(candidates: list[str]) -> str:
        for key in candidates:
            if not key:
                continue
            rendered = tr(key)
            if rendered != key and not AutoPageI18nMixin._is_unusable_translated_text(rendered):
                return rendered
        return ""

    @staticmethod
    def _first_translated_in_current_lang(candidates: list[str]) -> str:
        lang = _resolve_lang()
        catalog = get_catalog(lang)
        zh_cn_catalog = get_catalog("zh_CN") if lang == "zh_HK" else {}
        for key in candidates:
            if not key:
                continue
            rendered = catalog.get(key)
            if rendered is None and lang == "zh_HK":
                rendered = zh_cn_catalog.get(key)
            if rendered and not AutoPageI18nMixin._is_unusable_translated_text(rendered):
                return rendered
        return ""

    @staticmethod
    def _owner_slug_from_dir(owner_dir: str) -> str:
        owner_match = re.search(r"(?:^|[./\\])modules[./\\]([a-z0-9_]+)(?:[./\\]|$)", str(owner_dir or "").lower())
        return owner_match.group(1) if owner_match else ""

    def _related_module_ids(self, owner_slug: str) -> list[str]:
        related: list[str] = []
        try:
            from app.framework.core.module_system.registry import get_all_modules
        except Exception:
            return related

        current_class = getattr(self.module_meta, "module_class", None)
        current_name = self._snake_key(getattr(self.module_meta, "name", ""), max_len=80)

        for meta in get_all_modules():
            candidate_id = str(getattr(meta, "id", "") or "").strip()
            if not candidate_id:
                continue

            same_module = False
            if current_class is not None and getattr(meta, "module_class", None) is current_class:
                same_module = True
            else:
                other_owner_slug = self._owner_slug_from_dir(str(getattr(meta, "i18n_owner_dir", "") or ""))
                if owner_slug and other_owner_slug == owner_slug:
                    same_module = True
                elif current_name and self._snake_key(getattr(meta, "name", ""), max_len=80) == current_name:
                    same_module = True

            if same_module and candidate_id not in related:
                related.append(candidate_id)

        return related

    def _module_i18n_ids(self) -> list[str]:
        ids: list[str] = []

        def add(candidate: str | None) -> None:
            normalized = str(candidate or "").strip()
            if normalized and normalized not in ids:
                ids.append(normalized)

        module_id = str(getattr(self.module_meta, "id", "") or "")
        add(module_id)
        if module_id.startswith("task_"):
            add(module_id[5:])

        owner_dir = str(getattr(self.module_meta, "i18n_owner_dir", "") or "")
        owner_slug = self._owner_slug_from_dir(owner_dir)
        add(owner_slug)

        module_name = getattr(self.module_meta, "name", "")
        add(self._snake_key(module_name, max_len=80))

        for related_id in self._related_module_ids(owner_slug):
            add(related_id)
            if related_id.startswith("task_"):
                add(related_id[5:])

        if not ids:
            add("module")
        return ids
    @staticmethod
    def _expand_match_tokens(tokens: set[str]) -> set[str]:
        expanded = set(tokens)
        aliases = {
            "times": {"count", "times", "streak", "runs", "attempts"},
            "count": {"count", "times", "streak", "runs", "attempts"},
            "mail": {"mail", "claim"},
            "bait": {"bait", "fish", "claim"},
            "fish": {"fish", "bait"},
            "dormitory": {"dormitory", "dorm", "shards"},
            "dorm": {"dorm", "dormitory", "shards"},
            "win": {"win", "wins", "streak", "count"},
            "wins": {"win", "wins", "streak", "count"},
            "threshold": {"threshold", "confidence"},
            "mode": {"mode", "run", "stage", "sprint"},
            "run": {"run", "mode", "sprint", "operation"},
            "action": {"action", "operation", "run"},
            "power": {"power", "stamina"},
            "stamina": {"stamina", "power"},
            "redeem": {"redeem", "code", "codes"},
            "close": {"close", "exit", "shutdown"},
            "wife": {"wife", "character", "partner"},
        }
        for token in list(expanded):
            expanded.update(aliases.get(token, set()))
        return expanded

    @staticmethod
    @lru_cache(maxsize=2048)
    def _best_ui_label_key(module_ids_key: tuple[str, ...], token_key: tuple[str, ...]) -> str:
        if not module_ids_key or not token_key:
            return ""

        source_catalog = get_catalog("en")
        base_tokens = set(token_key)
        search_tokens = AutoPageI18nMixin._expand_match_tokens(base_tokens)

        best_score = 0
        best_key = ""

        for module_id in module_ids_key:
            prefix = f"module.{module_id}.ui."
            for key, value in source_catalog.items():
                if not isinstance(key, str) or not key.startswith(prefix):
                    continue
                if ".option." in key:
                    continue

                suffix = key[len(prefix):]
                if not suffix:
                    continue

                lower_suffix = suffix.lower()
                # Exclude non-label UI keys.
                if any(x in lower_suffix for x in ("tips", "start_", "stop_", "log", "description", "group_")):
                    continue

                suffix_tokens = AutoPageI18nMixin._tokenize_for_match(suffix)
                value_tokens = AutoPageI18nMixin._tokenize_for_match(str(value))
                overlap = len(search_tokens & suffix_tokens)
                overlap = max(overlap, len(search_tokens & value_tokens))
                if overlap == 0:
                    continue

                score = overlap * 10
                if any(tok in lower_suffix for tok in base_tokens):
                    score += 4
                if lower_suffix.endswith(tuple(base_tokens)):
                    score += 2

                if score > best_score:
                    best_score = score
                    best_key = key

        return best_key if best_score >= 10 else ""

    def _field_label_heuristic_key(self, field: SchemaField) -> str:
        stripped = self._strip_widget_prefix(field.param_name)
        token_text = f"{field.param_name} {field.field_id} {stripped} {field.label_default}"
        tokens = self._tokenize_for_match(token_text)
        if not tokens:
            return ""
        module_ids = tuple(self._module_i18n_ids())
        token_key = tuple(sorted(tokens))
        return self._best_ui_label_key(module_ids, token_key)


    @staticmethod
    @lru_cache(maxsize=256)
    def _tips_key_candidates(module_ids_key: tuple[str, ...]) -> tuple[str, ...]:
        source_catalog = get_catalog("en")
        collected: list[str] = []
        seen: set[str] = set()

        for module_id in module_ids_key:
            direct_candidates = (
                f"module.{module_id}.description",
                f"module.{module_id}.ui.description",
                f"module.{module_id}.ui.tips",
            )
            for key in direct_candidates:
                if key in source_catalog and key not in seen:
                    collected.append(key)
                    seen.add(key)

            tips_prefix = f"module.{module_id}.ui.tips"
            for key in source_catalog.keys():
                if not isinstance(key, str) or not key.startswith(tips_prefix):
                    continue
                if key not in seen:
                    collected.append(key)
                    seen.add(key)

        return tuple(collected)
    def _field_label_candidates(self, field: SchemaField, *, include_heuristic: bool = True) -> list[str]:
        stripped = self._strip_widget_prefix(field.param_name)
        ui_name = self._snake_key(stripped)
        full_ui_name = self._snake_key(field.param_name)
        candidates = [field.label_key]

        # Bridge field protocol keys to legacy/existing UI msgid keys:
        # module.<id>.field.<msgid>.label -> module.<id>.ui.<msgid>
        label_key_match = re.match(
            r"^module\.([a-zA-Z0-9_]+)\.field\.([a-zA-Z0-9_]+)\.label$",
            str(field.label_key or ""),
        )
        if label_key_match:
            module_token = label_key_match.group(1)
            msgid_token = label_key_match.group(2)
            candidates.append(f"module.{module_token}.ui.{msgid_token}")
            for module_id in self._module_i18n_ids():
                candidates.append(f"module.{module_id}.ui.{msgid_token}")

        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.field.{field.param_name}.label",
                f"module.{module_id}.field.{field.field_id}.label",
                f"module.{module_id}.ui.{ui_name}",
                f"module.{module_id}.ui.{full_ui_name}",
                f"module.{module_id}.ui.{self._snake_key(field.label_default)}",
            ])
            if ui_name.endswith("_times"):
                stem = ui_name[:-6]
                candidates.append(f"module.{module_id}.ui.{stem}_attempts")
                candidates.append(f"module.{module_id}.ui.run_count_1_means_infinite")
            if ui_name.startswith("is_"):
                candidates.append(f"module.{module_id}.ui.{ui_name[3:]}")

        candidates.extend([
            f"module.dummy.field.{field.param_name}.label",
            f"module.dummy.field.{field.field_id}.label",
        ])

        if include_heuristic:
            heuristic_key = self._field_label_heuristic_key(field)
            if heuristic_key:
                candidates.append(heuristic_key)

        # De-duplicate while preserving order.
        seen: set[str] = set()
        ordered: list[str] = []
        for item in candidates:
            if item and item not in seen:
                ordered.append(item)
                seen.add(item)
        return ordered

    def _group_label(self, group_name: str | None) -> str:
        if not group_name:
            module_id = str(getattr(self.module_meta, "id", "") or "")
            module_name = str(getattr(self.module_meta, "name", "") or "")
            name_msgid = str(getattr(self.module_meta, "name_msgid", "") or "").strip()
            if not name_msgid and module_id:
                name_msgid = f"module.{module_id}.title"
            return resolve_display_name(
                name=module_name,
                name_msgid=name_msgid,
                fallback_id=module_id or "module",
            )

        group_key = self._snake_key(group_name, max_len=80)
        candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.group.{group_key}",
                f"module.{module_id}.group.{group_name}",
                f"module.{module_id}.ui.group_{group_key}",
                f"module.{module_id}.ui.{group_key}",
            ])
        candidates.extend([
            f"framework.ui.group_{group_key}",
            f"framework.group.{group_key}",
            str(group_name),
        ])
        translated = self._first_translated(candidates)
        if translated:
            return translated
        return tr(str(group_name), fallback=str(group_name))

    @staticmethod
    def _normalize_tips_markdown(text: str) -> str:
        normalized = str(text or "")
        normalized = normalized.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")

        lines = [line.rstrip() for line in normalized.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return ""

        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                stripped = f"* {stripped[2:].strip()}"
            cleaned.append(stripped)

        if cleaned[0].startswith("###") and len(cleaned) > 1 and cleaned[1].startswith("*"):
            cleaned.insert(1, "")

        return "\n".join(cleaned)

    def _tips_text(self, description: str) -> str:
        description_key = self._snake_key(description, max_len=80)
        module_ids = self._module_i18n_ids()
        candidates: list[str] = []
        for module_id in module_ids:
            candidates.extend([
                f"module.{module_id}.description",
                f"module.{module_id}.ui.description",
                f"module.{module_id}.ui.tips",
                f"module.{module_id}.ui.{description_key}",
                f"module.{module_id}.ui.tips_{description_key}",
            ])

        # Legacy tips keys often use long slugged names (module.xxx.ui.tips_*).
        candidates.extend(self._tips_key_candidates(tuple(module_ids)))
        candidates.append(description)

        translated = self._first_translated(candidates)
        if translated:
            return self._normalize_tips_markdown(translated)
        return self._normalize_tips_markdown(tr(description, fallback=description))

    def _action_label(self, label: str, method_name: str) -> str:
        action_id = self._snake_key(method_name)
        candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.action.{action_id}.label",
                f"module.{module_id}.ui.{action_id}",
                f"module.{module_id}.ui.{self._snake_key(label)}",
            ])
        candidates.append(label)
        translated = self._first_translated(candidates)
        return translated or str(label)

    @staticmethod
    def _normalize_group_key(group_name: str | None) -> str:
        return AutoPageI18nMixin._snake_key(str(group_name or ""), max_len=80)

    @staticmethod
    def _tokenize_for_match(text: str) -> set[str]:
        tokens: set[str] = set()
        normalized = AutoPageI18nMixin._snake_key(text, max_len=120)
        for token in normalized.split("_"):
            token = token.strip()
            if len(token) < 2:
                continue
            tokens.add(token)
            if len(token) >= 5:
                tokens.add(token[:5])
        return tokens

