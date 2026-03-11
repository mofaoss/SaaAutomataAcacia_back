from __future__ import annotations

import re

from app.framework.i18n import tr
from app.framework.core.module_system.models import SchemaField


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
        return re.sub(r"^(SpinBox|ComboBox|CheckBox|LineEdit|DoubleSpinBox|Slider)_", "", str(param_name or ""))

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
        owner_match = re.search(r"(?:^|[./\\])modules[./\\]([a-z0-9_]+)(?:[./\\]|$)", owner_dir.lower())
        if owner_match:
            add(owner_match.group(1))

        module_name = getattr(self.module_meta, "name", "")
        add(self._snake_key(module_name, max_len=80))

        if not ids:
            add("module")
        return ids


    def _field_label_candidates(self, field: SchemaField) -> list[str]:
        stripped = self._strip_widget_prefix(field.param_name)
        ui_name = self._snake_key(stripped)
        full_ui_name = self._snake_key(field.param_name)
        candidates = [field.label_key]

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
            title_keys = [f"module.{module_id}.title" for module_id in self._module_i18n_ids()]
            translated_title = self._first_translated(title_keys)
            if translated_title:
                return translated_title
            return tr(title_keys[0], fallback=getattr(self.module_meta, "name", ""))

        group_key = self._snake_key(group_name, max_len=80)
        candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.group.{group_key}",
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
        candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.description",
                f"module.{module_id}.ui.description",
                f"module.{module_id}.ui.tips",
                f"module.{module_id}.ui.{description_key}",
                f"module.{module_id}.ui.tips_{description_key}",
            ])
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

