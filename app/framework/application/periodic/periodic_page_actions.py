from __future__ import annotations

from PySide6.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from app.features.utils.ui import ui_text
from app.framework.application.periodic.periodic_orchestration import (
    collect_checked_task_ids_for_rule,
    upsert_rule_to_tasks,
    withdraw_rule_from_tasks,
)


class PeriodicPresetActions:
    @staticmethod
    def load_presets(host):
        presets = host.settings_usecase.load_presets()
        host.ui.ComboBox_presets.blockSignals(True)
        host.ui.ComboBox_presets.clear()
        host.ui.ComboBox_presets.addItems(list(presets.keys()))
        host.ui.ComboBox_presets.setCurrentIndex(0)
        host.ui.ComboBox_presets.blockSignals(False)
        host._on_preset_changed(0)

    @staticmethod
    def on_preset_changed(host, index):
        _ = index
        preset_name = host.ui.ComboBox_presets.currentText()
        enabled_tasks = host.settings_usecase.get_enabled_tasks_for_preset(preset_name)
        for task_id, item in host.task_widget_map.items():
            item.checkbox.setChecked(task_id in enabled_tasks)

    @staticmethod
    def on_add_preset_clicked(host):
        host.ui.ComboBox_presets.blockSignals(True)
        host.ui.ComboBox_presets.setCurrentIndex(-1)
        host.ui.ComboBox_presets.setCurrentText("")
        host.ui.ComboBox_presets.blockSignals(False)
        host.ui.ComboBox_presets.setFocus()

    @staticmethod
    def save_current_preset(host):
        preset_name = host.ui.ComboBox_presets.currentText().strip()
        if not preset_name:
            return

        enabled_tasks = [
            task_id
            for task_id, item in host.task_widget_map.items()
            if item.checkbox.isChecked()
        ]
        host.settings_usecase.save_preset(preset_name, enabled_tasks)

        if host.ui.ComboBox_presets.findText(preset_name) == -1:
            host.ui.ComboBox_presets.addItem(preset_name)
        host.ui.ComboBox_presets.setCurrentIndex(host.ui.ComboBox_presets.findText(preset_name))

        InfoBar.success(
            title=ui_text("保存成功", "Saved"),
            content=ui_text(f"预设 '{preset_name}' 已保存", f"Preset '{preset_name}' saved"),
            parent=host,
        )

    @staticmethod
    def delete_current_preset(host):
        preset_name = host.ui.ComboBox_presets.currentText().strip()
        deleted, reason = host.settings_usecase.delete_preset(preset_name)
        if not deleted and reason == "not_found":
            return
        if not deleted and reason == "min_one_required":
            InfoBar.warning(
                title=ui_text("无法删除", "Cannot Delete"),
                content=ui_text("至少保留一个预设", "At least one preset must remain"),
                parent=host,
            )
            return

        idx = host.ui.ComboBox_presets.findText(preset_name)
        if idx >= 0:
            host.ui.ComboBox_presets.removeItem(idx)
        host.ui.ComboBox_presets.setCurrentIndex(0)

        InfoBar.success(
            title=ui_text("删除成功", "Deleted"),
            content=ui_text(f"预设 '{preset_name}' 已删除", f"Preset '{preset_name}' deleted"),
            parent=host,
        )


class PeriodicRuleActions:
    @staticmethod
    def copy_single_rule_to_checked(host, rule_data: dict):
        if not rule_data:
            return

        checked_task_ids = collect_checked_task_ids_for_rule(
            task_order=host.ui.taskListWidget.get_task_order(),
            is_checked=lambda task_id: bool(host.task_widget_map.get(task_id).checkbox.isChecked())
            if host.task_widget_map.get(task_id)
            else False,
            primary_task_id=host.primary_task_id,
            current_panel_task_id=host.ui.shared_scheduling_panel.task_id,
            allow_primary_when_current=False,
        )

        if not checked_task_ids:
            InfoBar.warning(
                title=ui_text("无生效目标", "No Target Selected"),
                content=ui_text("请先在左侧列表中勾选需要应用此规则的任务", "Please check tasks in the left list first"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=host,
            )
            return

        sequence = host.scheduler.get_task_sequence()
        upsert_rule_to_tasks(
            sequence=sequence,
            target_task_ids=set(checked_task_ids),
            primary_task_id=host.primary_task_id,
            rule_data=rule_data,
        )
        host.scheduler.save_task_sequence(sequence)

        current_task_id = host.ui.shared_scheduling_panel.task_id
        if current_task_id:
            task_cfg = next((item for item in sequence if item.get("id") == current_task_id), None)
            if task_cfg:
                host.ui.shared_scheduling_panel.load_task(current_task_id, task_cfg)

        host._auto_adjust_after_use_action()
        InfoBar.success(
            title=ui_text("规则下发成功", "Rule Copied Successfully"),
            content=ui_text(
                f"已追加给 {len(checked_task_ids)} 个已勾选任务\n并启用了它们的计划",
                f"Rule added to {len(checked_task_ids)} checked tasks\nand enabled their scheduling",
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3500,
            parent=host,
        )

    @staticmethod
    def withdraw_single_rule_from_checked(host, rule_data: dict):
        if not rule_data:
            return

        current_panel_task_id = host.ui.shared_scheduling_panel.task_id
        checked_task_ids = collect_checked_task_ids_for_rule(
            task_order=host.ui.taskListWidget.get_task_order(),
            is_checked=lambda task_id: bool(host.task_widget_map.get(task_id).checkbox.isChecked())
            if host.task_widget_map.get(task_id)
            else False,
            primary_task_id=host.primary_task_id,
            current_panel_task_id=current_panel_task_id,
            allow_primary_when_current=True,
        )

        if not checked_task_ids:
            InfoBar.warning(
                title=ui_text("无生效目标", "No Target Selected"),
                content=ui_text("请先在左侧列表中勾选需要撤回规则的任务", "Please check tasks in the left list first"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=host,
            )
            return

        sequence = host.scheduler.get_task_sequence()
        modified_count = withdraw_rule_from_tasks(
            sequence=sequence,
            target_task_ids=set(checked_task_ids),
            rule_data=rule_data,
        )
        host.scheduler.save_task_sequence(sequence)

        current_task_id = host.ui.shared_scheduling_panel.task_id
        if current_task_id:
            task_cfg = next((item for item in sequence if item.get("id") == current_task_id), None)
            if task_cfg:
                host.ui.shared_scheduling_panel.load_task(current_task_id, task_cfg)

        host._auto_adjust_after_use_action()
        InfoBar.success(
            title=ui_text("撤回成功", "Withdraw Successful"),
            content=ui_text(
                f"已从 {modified_count} 个任务中移除该时间节点",
                f"Removed trigger from {modified_count} tasks",
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=host,
        )

