from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from qfluentwidgets import CheckBox, InfoBar, InfoBarPosition

from app.framework.ui.shared.text import ui_text
from app.framework.application.periodic.periodic_orchestration import (
    collect_checked_tasks,
    collect_checked_tasks_from,
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


class PeriodicRuntimeActions:
    @staticmethod
    def set_checkbox_enable(host, enable: bool):
        for checkbox in host.ui.findChildren(CheckBox):
            if checkbox.objectName() == host.primary_option_key:
                checkbox.setEnabled(False)
            else:
                checkbox.setEnabled(enable)

    @staticmethod
    def set_launch_pending_state(host, pending: bool):
        host.periodic_controller.update_launch_pending(pending)
        if host.is_launch_pending:
            PeriodicRuntimeActions.set_checkbox_enable(host, False)
            host.ui.PushButton_start.setText(host._ui_text("停止 (F8)", "Stop (F8)"))

            for tid, task_item in host.task_widget_map.items():
                if tid in getattr(host, "tasks_to_run", []):
                    if hasattr(task_item, "set_task_state"):
                        task_item.set_task_state("queued")
                else:
                    if hasattr(task_item, "lock_ui_for_execution"):
                        task_item.lock_ui_for_execution()
            return

        if not host.is_running:
            PeriodicRuntimeActions.set_checkbox_enable(host, True)
            host.ui.PushButton_start.setText(host._ui_text("立即执行 (F8)", "Execute Now (F8)"))
            host._auto_adjust_after_use_action()

    @staticmethod
    def initiate_task_run(host, tasks_to_run):
        game_opened = host._is_game_window_open()
        plan = host.periodic_controller.build_run_plan(
            task_ids=tasks_to_run,
            game_opened=bool(game_opened),
            auto_open_game_enabled=host.settings_usecase.is_auto_open_game_enabled(),
        )
        host.tasks_to_run = plan.final_tasks

        if not host.tasks_to_run:
            return

        if plan.should_launch_game:
            host.open_game_directly()
            return

        if plan.should_warn_game_not_open:
            host.logger.warning(
                host._ui_text(
                    "⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。",
                    "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!",
                )
            )
        host.after_start_button_click(host.tasks_to_run)

    @staticmethod
    def handle_start(host, str_flag):
        try:
            transition = host.periodic_controller.apply_thread_flag(str_flag)

            if transition.started:
                host._set_launch_pending_state(False)
                host.ui.PushButton_start.setText(host._ui_text("停止 (F8)", "Stop (F8)"))
                host.task_coordinator.publish_state(True, "日常任务", "Daily Tasks", "daily")

                for tid, task_item in host.task_widget_map.items():
                    if tid in getattr(host, "tasks_to_run", []):
                        if hasattr(task_item, "set_task_state"):
                            task_item.set_task_state("queued")
                    else:
                        if hasattr(task_item, "lock_ui_for_execution"):
                            task_item.lock_ui_for_execution()

                if not host.running_game_guard_timer.isActive():
                    host.running_game_guard_timer.start(1000)
                return

            if transition.stopped:
                host._set_launch_pending_state(False)
                host.running_game_guard_timer.stop()
                PeriodicRuntimeActions.set_checkbox_enable(host, True)
                host.ui.PushButton_start.setText(host._ui_text("立即执行 (F8)", "Execute Now (F8)"))
                host._is_running_solo_flag = False
                host._is_scheduled_run_flag = False
                host._auto_adjust_after_use_action()
                host.task_coordinator.publish_state(False, "", "", "daily")

                if transition.should_after_finish:
                    host.after_finish()
        except Exception as e:
            host.logger.error(
                host._ui_text(
                    f"处理任务状态变更时出现异常：{e}",
                    f"Error occurred while handling task state change: {e}",
                )
            )
            host.is_running = False
            PeriodicRuntimeActions.set_checkbox_enable(host, True)
            host._auto_adjust_after_use_action()
            host.task_coordinator.publish_state(False, "", "", "daily")

    @staticmethod
    def on_task_play_clicked(host, task_id: str):
        def _stop_local():
            host.logger.info(host._ui_text("已手动中止当前任务", "Task manually stopped"))
            if host.is_launch_pending:
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)

            host.periodic_controller.stop_running_thread(
                reason=host._ui_text("用户点击了手动终止按钮", "User clicked stop button")
            )

        def _start_local(selected_task_id: str):
            meta = host.task_registry.get(selected_task_id, {})
            task_name = (
                meta.get("en_name", selected_task_id)
                if getattr(host, "_is_non_chinese_ui", False)
                else meta.get("zh_name", selected_task_id)
            )
            host.logger.info(
                host._ui_text(
                    f"开始单独重跑任务: {task_name}",
                    f"Force running task: {task_name}",
                )
            )
            host._is_running_solo_flag = True
            host._initiate_task_run([selected_task_id])

        host.single_task_toggle.toggle(
            task_id,
            is_global_running=bool(getattr(host, "is_global_running", False)),
            request_global_stop=host.task_coordinator.request_stop,
            is_local_running=bool(host.is_running or host.is_launch_pending),
            stop_local=_stop_local,
            start_local=_start_local,
        )

    @staticmethod
    def on_task_play_from_here_clicked(host, start_task_id: str):
        if host.is_running or host.is_launch_pending:
            host._on_task_play_clicked(start_task_id)
            return

        host.logger.info(
            host._ui_text(
                "开始从指定位置向下批量执行已勾选任务",
                "Force running checked tasks from here",
            )
        )

        ordered_task_ids = host.ui.taskListWidget.get_task_order()
        tasks_to_run = collect_checked_tasks_from(
            task_order=ordered_task_ids,
            start_task_id=start_task_id,
            is_checked=lambda task_id: bool(host.task_widget_map.get(task_id).checkbox.isChecked())
            if host.task_widget_map.get(task_id)
            else False,
        )

        if not tasks_to_run:
            host.logger.warning(host._ui_text("⚠️ 下方没有已勾选的任务可执行！", "⚠️ No checked tasks found below!"))
            return
        host._initiate_task_run(tasks_to_run)

    @staticmethod
    def check_game_open(host):
        try:
            hwnd = host._is_game_window_open()
            launch_state = host.periodic_controller.check_launch_tick(game_window_open=bool(hwnd))

            if launch_state == "detected":
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)
                host.logger.info(host._ui_text(f"已检测到游戏窗口：{hwnd}", f"Game window detected: {hwnd}"))
                host.after_start_button_click(getattr(host, "tasks_to_run", []))
                return

            if launch_state == "process_exited":
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)
                host.logger.warning(
                    host._ui_text(
                        "启动流程已中断：检测到游戏进程退出，已取消本次自动任务",
                        "Launch process interrupted: Game process exited, pending tasks cancelled.",
                    )
                )
                InfoBar.warning(
                    title=host._ui_text("游戏启动已中断", "Game launch interrupted"),
                    content=host._ui_text("已停止后续任务", "Pending tasks cancelled."),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=host,
                )
                return

            if launch_state == "timeout":
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)
                host.logger.warning(
                    host._ui_text(
                        "等待游戏窗口超时，已取消本次自动任务",
                        "Waiting for game window timed out, pending tasks cancelled.",
                    )
                )
                InfoBar.warning(
                    title=host._ui_text("等待超时", "Launch timeout"),
                    content=host._ui_text("已停止后续任务", "Pending tasks cancelled."),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=host,
                )
        except Exception as e:
            host.logger.error(
                host._ui_text(
                    f"检测游戏启动状态时出现异常：{e}",
                    f"Error occurred while checking game launch status: {e}",
                )
            )
            host._clear_launch_watch_state()
            host._set_launch_pending_state(False)

    @staticmethod
    def after_start_button_click(host, tasks_to_run):
        if len(tasks_to_run) > 1 or (tasks_to_run and not hasattr(host, "_is_running_solo_flag")):
            host._is_running_solo_flag = False

        if tasks_to_run:
            if not host.is_running:
                host.tasks_to_run = list(tasks_to_run)
                host.start_thread = host.periodic_controller.create_and_start_thread(
                    parent=host,
                    logger_instance=host.logger,
                    home_sync=getattr(host, "home_sync", None),
                    on_state_changed=host.handle_start,
                    on_task_completed=lambda task_id: PeriodicRuntimeActions.record_task_completed(host, task_id),
                    on_task_started=host._on_task_actually_started,
                    on_task_failed=lambda task_id: PeriodicRuntimeActions.record_task_failed(host, task_id),
                    on_show_tray_message=host._show_tray_message,
                )
            else:
                host.periodic_controller.stop_running_thread()
            return

        InfoBar.error(
            title=host._ui_text("无任务", "No task"),
            content=host._ui_text("未选择任务或不在生效周期", "No task selected or not in active period"),
            orient=Qt.Orientation.Horizontal,
            isClosable=False,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host,
        )

    @staticmethod
    def show_tray_message(host, title, content):
        tray_icon = QIcon(":/resources/logo/logo.png")
        main_win = host.window()
        if hasattr(main_win, "tray_icon") and main_win.tray_icon:
            main_win.tray_icon.showMessage(title, content, tray_icon, 1000)
            return

        app = QApplication.instance()
        if app:
            fallback_tray = QSystemTrayIcon(tray_icon, app)
            fallback_tray.show()
            fallback_tray.showMessage(title, content, tray_icon, 1000)

    @staticmethod
    def guard_running_game_window(host):
        try:
            if not host.is_running:
                host._stop_running_guard()
                return

            if not host.periodic_controller.should_stop_for_window_closed(bool(host._is_game_window_open())):
                return

            host._stop_running_guard()
            host.logger.warning(
                host._ui_text(
                    "检测到游戏窗口已关闭，正在停止当前自动任务",
                    "Game window closed, stopping current automatic task",
                )
            )
            host.periodic_controller.stop_running_thread(
                reason=host._ui_text("用户中断：游戏窗口已关闭", "Interrupted by user: game window closed")
            )
        except Exception as e:
            host.logger.error(
                host._ui_text(
                    f"运行中窗口守护检测异常：{e}",
                    f"Error occurred while monitoring running game window: {e}",
                )
            )
            host._stop_running_guard()

    @staticmethod
    def on_start_button_click(host):
        if getattr(host, "is_global_running", False):
            host.task_coordinator.request_stop()
            return

        if host.is_running:
            host.periodic_controller.stop_running_thread(reason="User Stop")
            return

        tasks_to_run = collect_checked_tasks(
            task_order=host.ui.taskListWidget.get_task_order(),
            is_checked=lambda task_id: bool(host.task_widget_map.get(task_id).checkbox.isChecked())
            if host.task_widget_map.get(task_id)
            else False,
        )

        if tasks_to_run:
            host._initiate_task_run(tasks_to_run)
            return

        InfoBar.error(
            title="队列为空",
            content=host._ui_text("请至少勾选一个任务进行立即执行", "Please select at least one task to run immediately"),
            parent=host,
        )

    @staticmethod
    def on_global_state_changed(host, is_running: bool, zh_name: str, en_name: str, source: str):
        if source == "daily":
            return

        host.periodic_controller.set_global_running(is_running)

        if is_running:
            PeriodicRuntimeActions.set_checkbox_enable(host, False)
            btn_text = (
                f"停止 {zh_name} (F8)"
                if not host._is_non_chinese_ui
                else f"Stop {en_name} (F8)"
            )
            host.ui.PushButton_start.setText(btn_text)
            return

        PeriodicRuntimeActions.set_checkbox_enable(host, True)
        host.ui.PushButton_start.setText(host._ui_text("立即执行 (F8)", "Execute Now (F8)"))
        pending_tasks = host.periodic_controller.consume_pending_queue_on_external_release()
        if pending_tasks:
            host.logger.info(
                ui_text(
                    "外部任务已结束，正在唤醒积压的日常排队任务...",
                    "External task finished, waking up queued daily tasks...",
                )
            )
            host.after_start_button_click(pending_tasks)

    @staticmethod
    def on_global_stop_request(host):
        if host.is_running or host.is_launch_pending:
            host.on_start_button_click()

    @staticmethod
    def on_task_checkbox_changed(host, task_id: str, is_checked: bool):
        sequence = host.scheduler.get_task_sequence()
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["enabled"] = bool(is_checked)
                break
        host.scheduler.save_task_sequence(sequence)
        host._on_task_settings_clicked(task_id)
        host._auto_adjust_after_use_action()

    @staticmethod
    def on_shared_config_changed(host, task_id: str, new_config: dict):
        sequence = host.scheduler.get_task_sequence()
        updated = False
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg.update(new_config)
                updated = True
                break

        if not updated:
            task_cfg = {"id": task_id, "enabled": True, "last_run": 0}
            task_cfg.update(new_config)
            sequence.append(task_cfg)

        host.scheduler.save_task_sequence(sequence)
        host._auto_adjust_after_use_action()

    @staticmethod
    def on_toggle_all_cycles_clicked(host, enable: bool):
        sequence = host.scheduler.get_task_sequence()
        for task_cfg in sequence:
            task_cfg["use_periodic"] = enable

        host.scheduler.save_task_sequence(sequence)
        if getattr(host.ui, "shared_scheduling_panel", None):
            host.ui.shared_scheduling_panel.enable_checkbox.blockSignals(True)
            host.ui.shared_scheduling_panel.enable_checkbox.setChecked(enable)
            host.ui.shared_scheduling_panel.enable_checkbox.blockSignals(False)

        host._auto_adjust_after_use_action()

    @staticmethod
    def on_task_actually_started(host, task_id: str):
        is_solo_run = getattr(host, "_is_running_solo_flag", False)
        is_scheduled_run = getattr(host, "_is_scheduled_run_flag", False)

        for tid, item in host.task_widget_map.items():
            if not hasattr(item, "set_task_state"):
                continue
            if tid != task_id:
                continue
            if is_scheduled_run:
                state = "running_scheduled"
            elif is_solo_run:
                state = "running_solo"
            else:
                state = "running_queue"
            item.set_task_state(state)

    @staticmethod
    def after_finish(host):
        if getattr(host, "_is_running_solo_flag", False):
            host.logger.info(
                host._ui_text(
                    "单独重跑完毕，已返回空闲状态...",
                    "Solo execution completed, returned to idle state...",
                )
            )
            return

        host._auto_adjust_after_use_action()
        host.logger.info(
            host._ui_text(
                "所有任务执行完毕，助手已进入挂机监控模式...",
                "All tasks completed, assistant entered monitoring mode...",
            )
        )

    @staticmethod
    def record_task_failed(host, task_id: str):
        meta = host.task_registry.get(task_id, {})
        task_name = (
            meta.get("en_name", task_id)
            if getattr(host, "_is_non_chinese_ui", False)
            else meta.get("zh_name", task_id)
        )
        fail_msg = (
            f"⚠️ Task [{task_name}] skipped!"
            if getattr(host, "_is_non_chinese_ui", False)
            else f"⚠️ {task_name} 未能成功执行，已跳过！"
        )
        host.logger.warning(fail_msg)

        task_item = host.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, "set_task_state"):
            task_item.set_task_state("failed")
            if getattr(host, "is_running", False) or getattr(host, "is_launch_pending", False):
                if hasattr(task_item, "lock_ui_for_execution"):
                    task_item.lock_ui_for_execution()

    @staticmethod
    def record_task_completed(host, task_id: str):
        sequence = host.scheduler.get_task_sequence()
        meta = host.task_registry.get(task_id, {})
        task_name = (
            meta.get("en_name", task_id)
            if getattr(host, "_is_non_chinese_ui", False)
            else meta.get("zh_name", task_id)
        )

        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["last_run"] = int(time.time())
                break
        host.scheduler.save_task_sequence(sequence)

        success_msg = (
            f"✨ Task [{task_name}] completed!"
            if getattr(host, "_is_non_chinese_ui", False)
            else f"✨ {task_name} 执行完毕！"
        )
        host.logger.info(success_msg)

        task_item = host.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, "set_task_state"):
            task_item.set_task_state("completed")
            if getattr(host, "is_running", False) or getattr(host, "is_launch_pending", False):
                if hasattr(task_item, "lock_ui_for_execution"):
                    task_item.lock_ui_for_execution()
