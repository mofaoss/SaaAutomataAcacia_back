from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from qfluentwidgets import CheckBox, InfoBar, InfoBarPosition

from app.framework.application.periodic.periodic_orchestration import (
    collect_checked_tasks,
    collect_checked_tasks_from,
    collect_checked_task_ids_for_rule,
    upsert_rule_to_tasks,
    withdraw_rule_from_tasks,
)
from app.framework.i18n import _


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
        preset_index = index
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
            title=_('Saved', msgid='saved'),
            content=_(f"Preset '{preset_name}' saved", msgid='preset_preset_name_saved'),
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
                title=_('Cannot Delete', msgid='cannot_delete'),
                content=_('At least one preset must remain', msgid='at_least_one_preset_must_remain'),
                parent=host,
            )
            return

        idx = host.ui.ComboBox_presets.findText(preset_name)
        if idx >= 0:
            host.ui.ComboBox_presets.removeItem(idx)
        host.ui.ComboBox_presets.setCurrentIndex(0)

        InfoBar.success(
            title=_('Deleted', msgid='deleted'),
            content=_(f"Preset '{preset_name}' deleted", msgid='preset_preset_name_deleted'),
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
                title=_('No Target Selected', msgid='no_target_selected'),
                content=_('Please check tasks in the left list first', msgid='please_check_tasks_in_the_left_list_first'),
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
            title=_('Rule Copied Successfully', msgid='rule_copied_successfully'),
            content=_(f'Rule added to {len(checked_task_ids)} checked tasks\nand enabled their scheduling', msgid='rule_added_to_value_checked_tasks_and_enabled_th'),
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
                title=_('No Target Selected', msgid='no_target_selected'),
                content=_('Please check tasks in the left list first', msgid='please_check_tasks_in_the_left_list_first'),
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
            title=_('Withdraw Successful', msgid='withdraw_successful'),
            content=_(f'Removed trigger from {modified_count} tasks', msgid='removed_trigger_from_modified_count_tasks'),
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
            host.ui.PushButton_start.setText(_("Stop (F8)"))

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
            host.ui.PushButton_start.setText(_("Execute Now (F8)"))
            host._auto_adjust_after_use_action()

    @staticmethod
    def initiate_task_run(host, tasks_to_run):
        requested_task_ids = list(tasks_to_run or [])
        if requested_task_ids:
            requested_names = []
            for task_id in requested_task_ids:
                meta = host.task_registry.get(task_id, {})
                display_name = host._task_display_name(meta, task_id)
                requested_names.append(display_name)
            host.logger.info(
                _('Requested tasks: {task_names}').format(task_names=', '.join(requested_names))
            )

        game_opened = host._is_game_window_open()
        plan = host.periodic_controller.build_run_plan(
            task_ids=tasks_to_run,
            game_opened=bool(game_opened),
            auto_open_game_enabled=host.settings_usecase.is_auto_open_game_enabled(),
        )
        host.tasks_to_run = plan.final_tasks
        primary_task_id = getattr(host, "primary_task_id", None)
        if (
            primary_task_id
            and primary_task_id in host.tasks_to_run
            and primary_task_id not in requested_task_ids
            and plan.should_launch_game
        ):
            host.logger.info(
                _('Game not running, auto-login task inserted at queue head')
            )

        if not host.tasks_to_run:
            host.logger.warning(_('Task queue is empty, run not started'))
            return

        queued_names = []
        for task_id in host.tasks_to_run:
            meta = host.task_registry.get(task_id, {})
            display_name = host._task_display_name(meta, task_id)
            queued_names.append(display_name)
        host.logger.info(
            _('Final queued tasks: {var_0}').format(var_0=', '.join(queued_names))
        )

        if plan.should_launch_game:
            host.open_game_directly()
            return

        if plan.should_warn_game_not_open:
            host.logger.warning(
                _("[Schedule] Game is not running and 'Auto open game' is OFF. This may cause handle errors!")
            )
        host.after_start_button_click(host.tasks_to_run)

    @staticmethod
    def handle_start(host, str_flag):
        try:
            transition = host.periodic_controller.apply_thread_flag(str_flag)

            if transition.started:
                host._set_launch_pending_state(False)
                host.ui.PushButton_start.setText(_("Stop (F8)"))
                host.task_coordinator.publish_state(
                    True,
                    _("Daily Tasks"),
                    "framework.daily_tasks.title",
                    "daily",
                )

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
                host.ui.PushButton_start.setText(_("Execute Now (F8)"))
                host._is_running_solo_flag = False
                host._is_scheduled_run_flag = False
                host._auto_adjust_after_use_action()
                host.task_coordinator.publish_state(False, "", "", "daily")

                if transition.should_after_finish:
                    host.after_finish()
        except Exception as e:
            host.logger.error(
                _('Error occurred while handling task state change: {e}').format(e=e)
            )
            host.is_running = False
            PeriodicRuntimeActions.set_checkbox_enable(host, True)
            host._auto_adjust_after_use_action()
            host.task_coordinator.publish_state(False, "", "", "daily")

    @staticmethod
    def on_task_play_clicked(host, task_id: str):
        def _stop_local():
            host.logger.info(_('Current task has been manually aborted'))
            if host.is_launch_pending:
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)

            host.periodic_controller.stop_running_thread(
                reason=_('The user clicked the manual kill button')
            )

        def _start_local(selected_task_id: str):
            meta = host.task_registry.get(selected_task_id, {})
            task_name = host._task_display_name(meta, selected_task_id)
            host.logger.info(
                _('Force running task: {task_name}').format(task_name=task_name)
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
            _("Force running checked tasks from here")
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
            host.logger.warning(_('There are no checked tasks below to perform!'))
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
                host.logger.info(_('Game window detected', msgid='game_window_detected'))
                host.after_start_button_click(getattr(host, "tasks_to_run", []))
                return

            if launch_state == "process_exited":
                host._clear_launch_watch_state()
                host._set_launch_pending_state(False)
                host.logger.warning(
                    _('The startup process has been interrupted: The game process has been detected to have exited, and this automatic task has been cancelled.')
                )
                InfoBar.warning(
                    title=_('Game startup interrupted'),
                    content=_('Subsequent tasks have been stopped'),
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
                    _('The waiting game window has timed out and this automatic task has been cancelled.')
                )
                InfoBar.warning(
                    title=_('Wait timeout'),
                    content=_('Subsequent tasks have been stopped'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=host,
                )
        except Exception as e:
            host.logger.error(
                _('Error occurred while checking game launch status: {e}').format(e=e)
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
            title=_('No tasks'),
            content=_('No task selected or not in the effective period'),
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
                _('Detected that the game window has been closed, stopping the current automatic task')
            )
            host.periodic_controller.stop_running_thread(
                reason=_('User Interrupt: Game window has been closed')
            )
        except Exception as e:
            host.logger.error(
                _('Error occurred while monitoring running game window: {e}').format(e=e)
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
            title=_('No Tasks Selected', msgid='no_tasks_selected'),
            content=_('Please check at least one task for immediate execution'),
            parent=host,
        )
        host.logger.warning(_('No runnable task selected, execution cancelled'))

    @staticmethod
    def on_global_state_changed(host, is_running: bool, task_name: str, task_name_msgid: str, source: str):
        if source == "daily":
            return

        host.periodic_controller.set_global_running(is_running)

        if is_running:
            PeriodicRuntimeActions.set_checkbox_enable(host, False)
            external_name = host._state_display_name(task_name, task_name_msgid, source=source)
            btn_text = (
                _("Stop {external_name} (F8)", msgid="stop_external_name_f8").format(external_name=external_name)
            )
            host.ui.PushButton_start.setText(btn_text)
            return

        PeriodicRuntimeActions.set_checkbox_enable(host, True)
        host.ui.PushButton_start.setText(_('Execute immediately (F8)'))
        pending_tasks = host.periodic_controller.consume_pending_queue_on_external_release()
        if pending_tasks:
            host.logger.info(
                _('External task finished, waking up queued daily tasks...', msgid='external_task_finished_waking_up_queued_daily_ta')
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
                _('The solo rerun is completed and has returned to the idle state...')
            )
            return

        host._auto_adjust_after_use_action()
        host.logger.info(
            _('All tasks have completed, and the assistant is now in idle monitoring mode...')
        )

    @staticmethod
    def record_task_failed(host, task_id: str):
        meta = host.task_registry.get(task_id, {})
        task_name = host._task_display_name(meta, task_id)
        fail_msg = (
            _("⚠️ Task [{task_name}] skipped!", msgid="task_skipped").format(task_name=task_name)
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
        task_name = host._task_display_name(meta, task_id)

        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["last_run"] = int(time.time())
                break
        host.scheduler.save_task_sequence(sequence)

        success_msg = (
            _("✨ Task [{task_name}] completed!", msgid="task_completed").format(task_name=task_name)
        )
        host.logger.info(success_msg)

        task_item = host.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, "set_task_state"):
            task_item.set_task_state("completed")
            if getattr(host, "is_running", False) or getattr(host, "is_launch_pending", False):
                if hasattr(task_item, "lock_ui_for_execution"):
                    task_item.lock_ui_for_execution()
