# coding:utf-8
import copy
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget
from qfluentwidgets import CheckBox, ComboBox, LineEdit, SpinBox

from app.framework.infra.config.app_config import config


class DailySettingsUseCase:
    """Typed boundary for daily settings read/write and preset persistence."""

    @staticmethod
    def should_check_update_on_startup() -> bool:
        return bool(config.checkUpdateAtStartUp.value)

    @staticmethod
    def is_auto_open_game_enabled() -> bool:
        return bool(config.CheckBox_open_game_directly.value)

    @staticmethod
    def is_same_game_directory(folder: str) -> bool:
        return str(config.LineEdit_game_directory.value) == str(folder)

    @staticmethod
    def apply_config_to_widgets(widgets: Iterable[Any]) -> None:
        for widget in widgets:
            config_item = getattr(config, widget.objectName(), None)
            if config_item is None:
                continue

            if isinstance(widget, CheckBox):
                widget.setChecked(bool(config_item.value))
            elif isinstance(widget, ComboBox):
                widget.setCurrentIndex(int(config_item.value))
            elif isinstance(widget, LineEdit):
                widget.setText(str(config_item.value))
            elif isinstance(widget, SpinBox):
                widget.setValue(int(config_item.value))

    @staticmethod
    def apply_tree_selection(tree: QTreeWidget, text_to_key: Dict[str, str]) -> None:
        from PySide6.QtWidgets import QTreeWidgetItemIterator

        item = QTreeWidgetItemIterator(tree)
        while item.value():
            text = item.value().text(0)
            item_key = text_to_key.get(text)
            config_item = getattr(config, item_key, None) if item_key else None
            if config_item is not None:
                item.value().setCheckState(
                    0,
                    Qt.CheckState.Checked if bool(config_item.value) else Qt.CheckState.Unchecked,
                )
            item += 1

    @staticmethod
    def persist_widget_change(widget: Any) -> Optional[bool]:
        config_item = getattr(config, widget.objectName(), None)
        if config_item is None:
            return None

        if isinstance(widget, CheckBox):
            checked = bool(widget.isChecked())
            config.set(config_item, checked)
            if widget.objectName() == "CheckBox_is_use_power":
                return checked
            return None

        if isinstance(widget, ComboBox):
            config.set(config_item, int(widget.currentIndex()))
            return None

        if isinstance(widget, SpinBox):
            config.set(config_item, int(widget.value()))
            return None

        if isinstance(widget, LineEdit):
            name = widget.objectName()
            text = widget.text()
            if any(token in name for token in ("x1", "x2", "y1", "y2")):
                try:
                    config.set(config_item, int(text))
                except ValueError:
                    return None
            else:
                config.set(config_item, text)
            return None

        return None

    @staticmethod
    def persist_indexed_item(prefix: str, index: int, check_state: int) -> None:
        config_item = getattr(config, f"{prefix}{index}", None)
        if config_item is not None:
            config.set(config_item, check_state != 0)

    @staticmethod
    def reset_redeem_codes() -> str:
        content = ""
        if config.import_codes.value:
            config.set(config.import_codes, [])
            content += " 导入 "
        if config.used_codes.value:
            config.set(config.used_codes, [])
            content += " 已使用 "
        return content

    @staticmethod
    def parse_import_codes(raw_text: str) -> List[str]:
        lines = (raw_text or "").splitlines()
        result = []
        for line in lines:
            stripped_line = line.strip()
            if ":" in stripped_line:
                result.append(stripped_line.split(":")[-1])
            elif "：" in stripped_line:
                result.append(stripped_line.split("：")[-1])
            else:
                result.append(stripped_line)
        return result

    @staticmethod
    def save_import_codes(codes: List[str]) -> None:
        config.set(config.import_codes, list(codes))

    @staticmethod
    def save_date_tip(tips: Dict[str, Any]) -> None:
        config.set(config.date_tip, tips)

    @staticmethod
    def load_date_tip() -> Optional[Dict[str, Any]]:
        if not config.date_tip.value:
            return None
        return copy.deepcopy(config.date_tip.value)

    @staticmethod
    def is_log_enabled() -> bool:
        return bool(config.isLog.value)

    @staticmethod
    def load_presets() -> Dict[str, List[str]]:
        presets = config.task_presets.value
        if not presets:
            presets = {"Default": []}
            config.set(config.task_presets, presets)
        return dict(presets)

    @staticmethod
    def get_enabled_tasks_for_preset(preset_name: str) -> List[str]:
        presets = DailySettingsUseCase.load_presets()
        return list(presets.get(preset_name, []))

    @staticmethod
    def save_preset(preset_name: str, enabled_tasks: List[str]) -> bool:
        presets = DailySettingsUseCase.load_presets()
        is_new = preset_name not in presets
        presets[preset_name] = list(enabled_tasks)
        config.set(config.task_presets, presets)
        return is_new

    @staticmethod
    def delete_preset(preset_name: str) -> Tuple[bool, str]:
        presets = DailySettingsUseCase.load_presets()
        if preset_name not in presets:
            return False, "not_found"
        if len(presets) <= 1:
            return False, "min_one_required"
        del presets[preset_name]
        config.set(config.task_presets, presets)
        return True, "deleted"
