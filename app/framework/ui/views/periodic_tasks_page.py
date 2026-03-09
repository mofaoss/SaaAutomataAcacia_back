import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List

import win32con
import win32gui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout, QSystemTrayIcon, QApplication
from qfluentwidgets import FluentIcon as FIF, InfoBar, InfoBarPosition, CheckBox

from app.framework.infra.config.app_config import is_non_chinese_ui_language
from app.framework.infra.events.signal_bus import signalBus
from app.framework.ui.shared.style_sheet import StyleSheet
from app.features.utils.ui import ui_text

from app.features.modules.collect_supplies.usecase.collect_supplies_actions import CollectSuppliesActions
from app.features.infra.snowbreak_game_environment import SnowbreakGameEnvironment
from app.features.modules.enter_game.usecase.enter_game_actions import EnterGameActions
from app.features.modules.event_tips.usecase.event_tips_usecase import EventTipsUseCase
from app.features.modules.shopping.usecase.shopping_usecase import ShoppingSelectionUseCase
from app.framework.core.task_engine.scheduler import Scheduler
from app.framework.core.interfaces.game_environment import IGameEnvironment
from app.framework.infra.logging.gui_logger import setup_ui_logger
from app.framework.application.periodic.periodic_controller import PeriodicController
from app.framework.application.periodic.periodic_settings_usecase import PeriodicSettingsUseCase
from app.framework.application.periodic.periodic_ui_binding_usecase import PeriodicUiBindingUseCase
from app.framework.core.event_bus.global_task_bus import global_task_bus
from app.framework.application.periodic.periodic_dispatcher import PeriodicDispatcher
from app.framework.application.periodic.on_demand_runner import SingleTaskToggle
from app.framework.application.periodic.periodic_orchestration import (
    build_active_schedule_lines,
    collect_checked_tasks,
    collect_checked_tasks_from,
)
from app.framework.application.periodic.periodic_page_actions import (
    PeriodicPresetActions,
    PeriodicRuleActions,
)
from app.features.scheduling.task_profile import get_periodic_task_profile

# 导入视图与基类
from app.framework.ui.views.periodic_tasks_view import PeriodicTasksView, TaskItemWidget
from .periodic_base import BaseInterface

logger = logging.getLogger(__name__)

task_coordinator = global_task_bus

def select_all(widget):
    for checkbox in widget.findChildren(CheckBox):
        checkbox.setChecked(True)

def no_select(widget, primary_option_key: str):
    for checkbox in widget.findChildren(CheckBox):
        # 保护机制：主任务对应 checkbox 绝不执行取消勾选
        if checkbox.objectName() != primary_option_key:
            checkbox.setChecked(False)

# ==========================================
# Controller 层
# ==========================================
class PeriodicTasksPage(QFrame, BaseInterface):
    """Periodic task host: supports scheduled, queue, and manual run strategies."""

    def __init__(self, text: str, parent=None, *, game_environment: IGameEnvironment | None = None):
        super().__init__(parent)
        BaseInterface.__init__(self)

        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.task_profile = get_periodic_task_profile()
        self.task_registry = self.task_profile.task_registry
        self.primary_task_id = self.task_profile.primary_task_id
        self.mandatory_task_ids = set(self.task_profile.mandatory_task_ids)
        self.primary_option_key = self.task_profile.primary_option_key

        self.setting_name_list = self._build_setting_name_list()

        self.game_environment = game_environment or SnowbreakGameEnvironment(self._is_non_chinese_ui)
        self.shopping_selection_usecase = ShoppingSelectionUseCase(self._is_non_chinese_ui)
        self.person_text_to_key, self.weapon_text_to_key = self.shopping_selection_usecase.get_text_to_key_maps()

        self.ui = PeriodicTasksView(self, is_non_chinese_ui=self._is_non_chinese_ui)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.scheduler = Scheduler(
            self,
            primary_task_id=self.primary_task_id,
            mandatory_task_ids=self.mandatory_task_ids,
        )
        self.periodic_controller = PeriodicController(
            task_registry=self.task_registry,
            primary_task_id=self.primary_task_id,
        )
        self.settings_usecase = PeriodicSettingsUseCase()
        self.ui_binding_usecase = PeriodicUiBindingUseCase()
        self.enter_game_actions = EnterGameActions(self.game_environment)
        self.collect_supplies_actions = CollectSuppliesActions(self.settings_usecase)
        self.event_tips_usecase = EventTipsUseCase(
            self.settings_usecase,
            is_non_chinese_ui=self._is_non_chinese_ui,
            ui_text_fn=self._ui_text,
        )

        self.task_widget_map: Dict[str, TaskItemWidget] = {}
        self._init_task_list_widgets()

        self.is_running = False

        self.select_person, self.select_weapon = self.shopping_selection_usecase.create_selectors(
            parent=self.ui.ScrollArea
        )

        self.game_hwnd = None
        self.start_thread = None
        self.launch_process = None
        self.launch_deadline = 0.0
        self.is_launch_pending = False
        self._is_running_solo_flag = False
        self._is_scheduled_run_flag = False

        self._initWidget()
        self._connect_to_slot()

        self.logger = setup_ui_logger("logger_daily", self.ui.textBrowser_log)
        self.periodic_dispatcher = PeriodicDispatcher(self.logger, self._ui_text)
        self.single_task_toggle = SingleTaskToggle()

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(
            self._guard_running_game_window)

        self._f8_pressed = False

        self.checkbox_dic = None
        self._shared_sidebar_cards = [
            self.ui.SimpleCardWidget,
            self.ui.SimpleCardWidget_tips,
        ]
        self._shared_sidebar_detached = False

        QTimer.singleShot(500, self._on_init_sync)

        if self.settings_usecase.should_check_update_on_startup():
            from app.features.utils.network import start_cloudflare_update
            start_cloudflare_update(self)
        else:
            self.get_tips()

        self.scheduler.start()

    def detach_shared_sidebar_cards(self):
        if self._shared_sidebar_detached:
            return list(self._shared_sidebar_cards)

        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget)
        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget_tips)
        self._shared_sidebar_detached = True
        return list(self._shared_sidebar_cards)

    def attach_shared_sidebar_cards(self, cards=None):
        target_cards = list(cards) if cards else list(self._shared_sidebar_cards)
        if len(target_cards) < 2:
            return

        self.ui.gridLayout_2.addWidget(target_cards[0], 0, 2, 1, 1)
        self.ui.gridLayout_2.addWidget(target_cards[1], 1, 2, 1, 1)
        self._shared_sidebar_detached = False

    def _build_setting_name_list(self) -> list[str]:
        ordered_metas = sorted(
            (
                meta
                for meta in self.task_registry.values()
                if meta.get("ui_page_index") is not None
            ),
            key=lambda item: item.get("ui_page_index", 0),
        )
        return [
            self._ui_text(meta.get("zh_name", ""), meta.get("en_name", ""))
            for meta in ordered_metas
        ]

    def _on_init_sync(self):
        self._load_presets()
        self._auto_adjust_after_use_action()
        self._output_schedule_log()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'")

    @property
    def is_running(self) -> bool:
        return self.periodic_controller.state.is_running

    @is_running.setter
    def is_running(self, value: bool):
        self.periodic_controller.state.is_running = bool(value)

    @property
    def is_launch_pending(self) -> bool:
        return self.periodic_controller.state.is_launch_pending

    @is_launch_pending.setter
    def is_launch_pending(self, value: bool):
        self.periodic_controller.state.is_launch_pending = bool(value)

    @property
    def is_global_running(self) -> bool:
        return self.periodic_controller.state.is_global_running

    @is_global_running.setter
    def is_global_running(self, value: bool):
        self.periodic_controller.state.is_global_running = bool(value)

    @property
    def _waiting_for_external_to_finish(self) -> bool:
        return self.periodic_controller.state.waiting_for_external_to_finish

    @_waiting_for_external_to_finish.setter
    def _waiting_for_external_to_finish(self, value: bool):
        self.periodic_controller.state.waiting_for_external_to_finish = bool(value)

    @property
    def tasks_to_run(self) -> List[str]:
        return self.periodic_controller.state.tasks_to_run

    @tasks_to_run.setter
    def tasks_to_run(self, value: List[str]):
        self.periodic_controller.state.tasks_to_run = list(value or [])

    @property
    def launch_process(self):
        return self.periodic_controller.state.launch_process

    @launch_process.setter
    def launch_process(self, value):
        self.periodic_controller.state.launch_process = value

    @property
    def launch_deadline(self) -> float:
        return self.periodic_controller.state.launch_deadline

    @launch_deadline.setter
    def launch_deadline(self, value: float):
        self.periodic_controller.state.launch_deadline = float(value or 0.0)

    @property
    def _is_running_solo_flag(self) -> bool:
        return self.periodic_controller.state.is_running_solo

    @_is_running_solo_flag.setter
    def _is_running_solo_flag(self, value: bool):
        self.periodic_controller.state.is_running_solo = bool(value)

    @property
    def _is_scheduled_run_flag(self) -> bool:
        return self.periodic_controller.state.is_scheduled_run

    @_is_scheduled_run_flag.setter
    def _is_scheduled_run_flag(self, value: bool):
        self.periodic_controller.state.is_scheduled_run = bool(value)

    @property
    def start_thread(self):
        return self.periodic_controller.start_thread

    @start_thread.setter
    def start_thread(self, value):
        self.periodic_controller.start_thread = value

    def _on_scheduled_tasks_due(self, new_tasks_found: List[str]):
        self.periodic_dispatcher.handle_due_tasks(
            new_tasks_found,
            is_launch_pending=getattr(self, "is_launch_pending", False),
            is_self_running=getattr(self, "is_running", False),
            is_external_running=getattr(self, "is_global_running", False),
            queue_tasks=self.periodic_controller.queue_tasks,
            mark_task_queued=self._mark_task_queued,
            mark_waiting_for_external_finish=self.periodic_controller.mark_waiting_for_external_finish,
            run_now=self._run_scheduled_tasks_now,
        )

    def _mark_task_queued(self, task_id: str):
        task_item = self.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, "set_task_state"):
            task_item.set_task_state("queued")

    def _run_scheduled_tasks_now(self, task_ids: List[str]):
        self._is_scheduled_run_flag = True
        self._initiate_task_run(task_ids)

    def _initWidget(self):

        self.ui.PopUpAniStackedWidget.setCurrentIndex(0)
        self.ui.TitleLabel_setting.setText(
            self._ui_text("设置", "Settings") + "-" + self.setting_name_list[
                self.ui.PopUpAniStackedWidget.currentIndex()])

        self.ui.gridLayout.addWidget(self.select_person, 1, 0)
        self.ui.gridLayout.addWidget(self.select_weapon, 2, 0)

        self._load_config()
        self._sync_task_sequence_from_ui()
        self._load_initial_task_panel()

        self.ui.ComboBox_power_day.setEnabled(
            self.ui.CheckBox_is_use_power.isChecked())

        StyleSheet.PERIODIC_TASKS_INTERFACE.apply(self)
        self.ui.ScrollArea.enableTransparentBackground()
        self.ui.ScrollArea_tips.enableTransparentBackground()

        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget)
        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget_tips)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget, 0, 2, 1, 1)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget_tips, 1, 2, 1,
                                       1)

    def _output_schedule_log(self):
        sequence = self.scheduler.get_task_sequence()
        schedule_logs = build_active_schedule_lines(
            sequence=sequence,
            task_registry=self.task_registry,
            is_non_chinese_ui=self._is_non_chinese_ui,
        )

        if schedule_logs:
            header = "<b>📅 当前已激活的自动执行日程表：</b>" if not self._is_non_chinese_ui else "<b>📅 Active Schedules:</b>"
            self.logger.info(f"{header}<br/>" + "<br/>".join(schedule_logs))
        else:
            self.logger.info("📅 当前未启用任何计划任务。" if not self._is_non_chinese_ui
                             else "📅 No active schedules.")

    def _auto_adjust_after_use_action(self, sequence=None):
        # 检查当前是否在全局执行状态
        is_globally_running = getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False)

        if sequence is None:
            sequence = self.scheduler.get_task_sequence()

        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            task_item = self.task_widget_map.get(task_id)
            if not task_item: continue

            is_checked = bool(task_item.checkbox.isChecked())
            use_periodic = bool(task_cfg.get("use_periodic", False)) and bool(task_cfg.get("execution_config"))

            if is_globally_running:
                # 任务执行期间，仅使用无痕方法刷新 📅 图标，绝对不触发状态机和解锁逻辑！
                if hasattr(task_item, 'update_schedule_status'):
                    task_item.update_schedule_status(use_periodic)
            else:
                # 非执行期间，正常走状态机更新
                task_item.is_scheduled = use_periodic
                curr_state = getattr(task_item, 'current_state', 'idle')
                if curr_state not in ['completed', 'failed']:
                    task_item.set_task_state('idle', is_enabled=is_checked)
                else:
                    task_item.set_task_state(curr_state, is_enabled=is_checked)

    def _init_task_list_widgets(self):
        sequence = self.scheduler.get_task_sequence()
        self.ui.taskListWidget.clear()
        self.task_widget_map.clear()

        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            meta = self.task_registry.get(task_id)
            if not meta:
                continue

            task_item = TaskItemWidget(
                task_id=task_id,
                zh_name=meta["zh_name"],
                en_name=meta["en_name"],
                is_enabled=bool(task_cfg.get("enabled", True)),
                is_non_chinese_ui=self._is_non_chinese_ui,
                parent=self.ui.taskListWidget,
                is_mandatory=bool(meta.get("is_mandatory", False)),
                is_force_first=bool(meta.get("force_first", False)),
            )

            # 初始化时传入任务的调度状态
            task_item.is_scheduled = bool(task_cfg.get("use_periodic", False))

            task_item.checkbox.setObjectName(meta["option_key"])
            self.ui.taskListWidget.add_task_item(task_item)
            self.task_widget_map[task_id] = task_item
            setattr(self, meta["option_key"], task_item.checkbox)

    def _sync_task_sequence_from_ui(self):
        sequence = self.scheduler.get_task_sequence()
        task_by_id = {item["id"]: item for item in sequence}

        for task_id, task_item in self.task_widget_map.items():
            if task_id in task_by_id:
                task_by_id[task_id]["enabled"] = task_item.checkbox.isChecked()

        ordered = []
        for task_id in self.ui.taskListWidget.get_task_order():
            if task_id in task_by_id:
                ordered.append(task_by_id.pop(task_id))
        ordered.extend(task_by_id.values())
        self.scheduler.save_task_sequence(ordered)

    def _load_initial_task_panel(self):
        sequence = self.scheduler.get_task_sequence()
        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            if task_id in self.task_registry:
                self._on_task_settings_clicked(task_id)
                break

    def _on_task_order_changed(self, task_id_order: list):
        sequence = self.scheduler.get_task_sequence()
        task_by_id = {item["id"]: item for item in sequence}
        ordered = []
        for task_id in task_id_order:
            if task_id in task_by_id:
                ordered.append(task_by_id.pop(task_id))
        ordered.extend(task_by_id.values())

        final_ordered = self.scheduler.normalize_task_sequence(ordered)
        self.scheduler.save_task_sequence(final_ordered)

        # If a task other than primary task is dragged to the top, refresh the UI to correct its position.
        if task_id_order and task_id_order[0] != self.primary_task_id:
            self._init_task_list_widgets()

    def _on_task_settings_clicked(self, task_id: str):
        meta = self.task_registry.get(task_id)
        if not meta:
            return

        page_index = meta.get("ui_page_index")
        if page_index is not None:
            self.set_current_index(page_index)

        sequence = self.scheduler.get_task_sequence()
        task_cfg = next((item for item in sequence if item.get("id") == task_id), None)

        # This should theoretically not happen after the scheduler normalization, but as a fallback:
        if task_cfg is None:
            normalized = self.scheduler.normalize_task_sequence(sequence)
            self.scheduler.save_task_sequence(normalized)
            task_cfg = next((item for item in normalized if item.get("id") == task_id), {})

        self.ui.shared_scheduling_panel.load_task(task_id, task_cfg)

    def _load_config(self):
        self.settings_usecase.apply_config_to_widgets(self.ui.findChildren(QWidget))
        self.shopping_selection_usecase.load_item_config(
            settings_usecase=self.settings_usecase,
            select_person=self.select_person,
            select_weapon=self.select_weapon,
            person_text_to_key=self.person_text_to_key,
            weapon_text_to_key=self.weapon_text_to_key,
        )

    def _connect_to_save_changed(self):
        self.ui_binding_usecase.connect_config_bindings(
            root_widget=self.ui,
            person_selector=self.select_person,
            weapon_selector=self.select_weapon,
            on_widget_change=self.save_changed,
            on_person_item_state_change=lambda index, check_state: self.shopping_selection_usecase.save_person_item(
                settings_usecase=self.settings_usecase,
                index=index,
                check_state=check_state,
            ),
            on_weapon_item_state_change=lambda index, check_state: self.shopping_selection_usecase.save_weapon_item(
                settings_usecase=self.settings_usecase,
                index=index,
                check_state=check_state,
            ),
        )

    def set_hwnd(self, hwnd):
        self.game_hwnd = hwnd

    def on_path_tutorial_click(self):
        self.enter_game_actions.show_path_tutorial(
            host=self,
            anchor_widget=self.ui.PrimaryPushButton_path_tutorial,
        )

    def on_select_directory_click(self):
        folder = self.enter_game_actions.select_game_directory(
            parent=self,
            current_directory=self.ui.LineEdit_game_directory.text(),
        )
        if not folder or self.settings_usecase.is_same_game_directory(folder):
            return
        self.ui.LineEdit_game_directory.setText(folder)
        self.ui.LineEdit_game_directory.editingFinished.emit()

    def on_reset_codes_click(self):
        self.collect_supplies_actions.on_reset_codes_click(
            host=self,
            text_edit=self.ui.TextEdit_import_codes,
        )

    def on_import_codes_click(self):
        self.collect_supplies_actions.on_import_codes_click(
            host=self,
            text_edit=self.ui.TextEdit_import_codes,
        )

    def change_auto_open(self, state):
        status = '已开启' if state == 2 else '已关闭'
        action = '将' if state == 2 else '不会'
        InfoBar.success(title=status,
                        content=ui_text(f"点击“开始”按钮时{action}自动启动游戏", f"Clicking the 'Start' button will {action}automatically launch the game"),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self)

    def open_game_directly(self):
        try:
            result = self.game_environment.launch(logger=self.logger)
            if not result.get("ok"):
                self.logger.error(result.get("error", "启动游戏失败"))
                self._set_launch_pending_state(False)
                return

            self.launch_process = result.get("process")
            self.periodic_controller.mark_launch_started(self.launch_process, timeout_seconds=90)
            self.check_game_window_timer.start(500)
            self._set_launch_pending_state(True)
        except Exception as e:
            self.logger.error(ui_text(f'出现报错: {e}', f'Error occurred: {e}'))
            self._set_launch_pending_state(False)

    def _is_game_window_open(self):
        return self.game_environment.is_running()

    def _clear_launch_watch_state(self):
        self.check_game_window_timer.stop()
        self.periodic_controller.clear_launch_watch_state()

    def _stop_running_guard(self):
        self.running_game_guard_timer.stop()

    def _connect_to_slot(self):
        self.ui.PushButton_start.clicked.connect(self.on_start_button_click)
        self.ui.PrimaryPushButton_path_tutorial.clicked.connect(
            self.on_path_tutorial_click)
        self.ui.PushButton_select_all.clicked.connect(
            lambda: select_all(self.ui.SimpleCardWidget_option))
        self.ui.PushButton_no_select.clicked.connect(
            lambda: no_select(self.ui.SimpleCardWidget_option, self.primary_option_key))
        self.ui.PushButton_select_directory.clicked.connect(
            self.on_select_directory_click)
        self.ui.PrimaryPushButton_import_codes.clicked.connect(
            self.on_import_codes_click)
        self.ui.PushButton_reset_codes.clicked.connect(
            self.on_reset_codes_click)

        self.ui.shared_scheduling_panel.toggle_all_cycles.connect(
            self._on_toggle_all_cycles_clicked)
        self.ui.shared_scheduling_panel.view_schedule_clicked.connect(
            self._output_schedule_log)

        for task_id, task_item in self.task_widget_map.items():
            task_item.settings_clicked.connect(self._on_task_settings_clicked)
            task_item.checkbox_state_changed.connect(
                self._on_task_checkbox_changed)
            task_item.play_clicked.connect(self._on_task_play_clicked)
            task_item.play_from_here_clicked.connect(
                self._on_task_play_from_here_clicked)

        self.ui.taskListWidget.orderChanged.connect(
            self._on_task_order_changed)
        self.ui.shared_scheduling_panel.config_changed.connect(
            self._on_shared_config_changed)
        self.ui.CheckBox_open_game_directly.stateChanged.connect(
            self.change_auto_open)

        self.ui.shared_scheduling_panel.copy_single_rule_clicked.connect(
            self._on_copy_single_rule_to_checked)
        self.ui.shared_scheduling_panel.withdraw_single_rule_clicked.connect(
            self._on_withdraw_single_rule_from_checked)

        self.ui.PushButton_add_preset.clicked.connect(self._on_add_preset_clicked)
        self.ui.PushButton_save_preset.clicked.connect(self._save_current_preset)
        self.ui.PushButton_delete_preset.clicked.connect(self._delete_current_preset)
        self.ui.ComboBox_presets.currentIndexChanged.connect(self._on_preset_changed)

        self.scheduler.tasks_due.connect(self._on_scheduled_tasks_due)
        self.scheduler.sequence_updated.connect(self._auto_adjust_after_use_action)

        signalBus.sendHwnd.connect(self.set_hwnd)

        task_coordinator.state_changed.connect(self._on_global_state_changed)
        task_coordinator.stop_requested.connect(self._on_global_stop_request)
        self._connect_to_save_changed()

    def _on_global_state_changed(self, is_running: bool, zh_name: str, en_name: str, source: str):
        if source == "daily": return # 忽略自己发出的信号

        # 记录是否有外部任务在运行
        self.periodic_controller.set_global_running(is_running)

        if is_running:
            self.set_checkbox_enable(False)
            btn_text = f"停止 {zh_name} (F8)" if not self._is_non_chinese_ui else f"Stop {en_name} (F8)"
            self.ui.PushButton_start.setText(btn_text)
        else:
            self.set_checkbox_enable(True)
            self.ui.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))

            # 【新增：排队唤醒机制】如果外部任务结束了，并且我们有积压的排队任务在等，立刻唤醒执行！
            pending_tasks = self.periodic_controller.consume_pending_queue_on_external_release()
            if pending_tasks:
                self.logger.info(ui_text("外部任务已结束，正在唤醒积压的日常排队任务...",
                                         "External task finished, waking up queued daily tasks..."))
                # 重新触发执行
                self.after_start_button_click(pending_tasks)

    # 【新增】响应全局的停止请求 (F8)
    def _on_global_stop_request(self):
        if self.is_running or self.is_launch_pending:
            self.on_start_button_click() # 复用现有的停止逻辑

    def _on_task_checkbox_changed(self, task_id: str, is_checked: bool):
        sequence = self.scheduler.get_task_sequence()
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["enabled"] = bool(is_checked)
                break
        self.scheduler.save_task_sequence(sequence)
        self._on_task_settings_clicked(task_id)
        self._auto_adjust_after_use_action()

    def _on_shared_config_changed(self, task_id: str, new_config: dict):
        sequence = self.scheduler.get_task_sequence()
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

        self.scheduler.save_task_sequence(sequence)
        self._auto_adjust_after_use_action()

    def _on_toggle_all_cycles_clicked(self, enable: bool):
        sequence = self.scheduler.get_task_sequence()
        for task_cfg in sequence:
            task_cfg["use_periodic"] = enable

        self.scheduler.save_task_sequence(sequence)
        if getattr(self.ui, 'shared_scheduling_panel', None):
            self.ui.shared_scheduling_panel.enable_checkbox.blockSignals(True)
            self.ui.shared_scheduling_panel.enable_checkbox.setChecked(enable)
            self.ui.shared_scheduling_panel.enable_checkbox.blockSignals(False)

        self._auto_adjust_after_use_action()

    def _set_launch_pending_state(self, pending: bool):
        self.periodic_controller.update_launch_pending(pending)
        if self.is_launch_pending:
            self.set_checkbox_enable(False)
            self.ui.PushButton_start.setText(self._ui_text("停止 (F8)", "Stop (F8)"))

            for tid, task_item in self.task_widget_map.items():
                if tid in getattr(self, 'tasks_to_run', []):
                    if hasattr(task_item, 'set_task_state'):
                        task_item.set_task_state('queued')
                else:
                    if hasattr(task_item, 'lock_ui_for_execution'):
                        task_item.lock_ui_for_execution()
            return

        if not self.is_running:
            self.set_checkbox_enable(True)
            self.ui.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))
            self._auto_adjust_after_use_action()

    def _initiate_task_run(self, tasks_to_run: List[str]):
        """
        Centralized method to start a task sequence.
        It checks if the game is running and decides whether to launch it
        or proceed directly with the automation thread.
        """
        game_opened = self._is_game_window_open()
        plan = self.periodic_controller.build_run_plan(
            task_ids=tasks_to_run,
            game_opened=bool(game_opened),
            auto_open_game_enabled=self.settings_usecase.is_auto_open_game_enabled(),
        )
        final_tasks = plan.final_tasks

        self.tasks_to_run = final_tasks

        if not self.tasks_to_run:
            return

        if plan.should_launch_game:
            self.open_game_directly()
        else:
            # If game isn't open and we are not launching it, issue a warning.
            if plan.should_warn_game_not_open:
                self.logger.warning(self._ui_text("⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。", "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!"))
            self.after_start_button_click(self.tasks_to_run)

    def handle_start(self, str_flag):
        try:
            transition = self.periodic_controller.apply_thread_flag(str_flag)

            if transition.started:
                self._set_launch_pending_state(False)
                self.ui.PushButton_start.setText(self._ui_text("停止 (F8)", "Stop (F8)"))
                task_coordinator.publish_state(True, "日常任务", "Daily Tasks", "daily")

                for tid, task_item in self.task_widget_map.items():
                    if tid in getattr(self, 'tasks_to_run', []):
                        if hasattr(task_item, 'set_task_state'):
                            task_item.set_task_state('queued')
                    else:
                        if hasattr(task_item, 'lock_ui_for_execution'):
                            task_item.lock_ui_for_execution()

                if not self.running_game_guard_timer.isActive():
                    self.running_game_guard_timer.start(1000)

            elif transition.stopped:
                self._set_launch_pending_state(False)
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)

                # 不论任何情况，停止后按钮直接回到“立即执行”，因为挂机是隐形的
                self.ui.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))

                self._is_running_solo_flag = False
                self._is_scheduled_run_flag = False

                self._auto_adjust_after_use_action()

                task_coordinator.publish_state(False, "", "", "daily")

                if transition.should_after_finish:
                    self.after_finish()
        except Exception as e:
            self.logger.error(ui_text(f'处理任务状态变更时出现异常：{e}', f'Error occurred while handling task state change: {e}'))
            self.is_running = False
            self.set_checkbox_enable(True)
            self._auto_adjust_after_use_action()
            # 异常时也要广播释放
            task_coordinator.publish_state(False, "", "", "daily")

    def _on_task_play_clicked(self, task_id: str):
        def _stop_local():
            self.logger.info(
                self._ui_text("已手动中止当前任务", "Task manually stopped"))
            if self.is_launch_pending:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)

            self.periodic_controller.stop_running_thread(
                reason=self._ui_text('用户点击了手动终止按钮', 'User clicked stop button')
            )

        def _start_local(selected_task_id: str):
            meta = self.task_registry.get(selected_task_id, {})
            task_name = meta.get("en_name", selected_task_id) if getattr(
                self, '_is_non_chinese_ui', False) else meta.get(
                    "zh_name", selected_task_id)
            self.logger.info(
                self._ui_text(f"开始单独重跑任务: {task_name}",
                              f"Force running task: {task_name}"))

            tasks_to_run = [selected_task_id]
            self._is_running_solo_flag = True
            self._initiate_task_run(tasks_to_run)

        self.single_task_toggle.toggle(
            task_id,
            is_global_running=bool(getattr(self, "is_global_running", False)),
            request_global_stop=task_coordinator.request_stop,
            is_local_running=bool(self.is_running or self.is_launch_pending),
            stop_local=_stop_local,
            start_local=_start_local,
        )

    def _on_task_play_from_here_clicked(self, start_task_id: str):
        if self.is_running or self.is_launch_pending:
            self._on_task_play_clicked(start_task_id)
            return

        self.logger.info(
            self._ui_text(f"开始从指定位置向下批量执行已勾选任务",
                          f"Force running checked tasks from here"))

        ordered_task_ids = self.ui.taskListWidget.get_task_order()
        tasks_to_run = collect_checked_tasks_from(
            task_order=ordered_task_ids,
            start_task_id=start_task_id,
            is_checked=lambda task_id: bool(
                self.task_widget_map.get(task_id).checkbox.isChecked()
            ) if self.task_widget_map.get(task_id) else False,
        )

        if not tasks_to_run:
            self.logger.warning(
                self._ui_text("⚠️ 下方没有已勾选的任务可执行！",
                              "⚠️ No checked tasks found below!"))
            return

        self._initiate_task_run(tasks_to_run)

    def _on_copy_single_rule_to_checked(self, rule_data: dict):
        PeriodicRuleActions.copy_single_rule_to_checked(self, rule_data)

    def _on_withdraw_single_rule_from_checked(self, rule_data: dict):
        PeriodicRuleActions.withdraw_single_rule_from_checked(self, rule_data)

    def check_game_open(self):
        try:
            hwnd = self._is_game_window_open()
            launch_state = self.periodic_controller.check_launch_tick(game_window_open=bool(hwnd))

            if launch_state == "detected":
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.info(self._ui_text(f'已检测到游戏窗口：{hwnd}', f'Game window detected: {hwnd}'))
                self.after_start_button_click(getattr(self, 'tasks_to_run',
                                                      []))
                return

            if launch_state == "process_exited":
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.warning(self._ui_text('启动流程已中断：检测到游戏进程退出，已取消本次自动任务',
                                                  'Launch process interrupted: Game process exited, pending tasks cancelled.'))
                InfoBar.warning(title=self._ui_text('游戏启动已中断',
                                                    'Game launch interrupted'),
                                content=self._ui_text(
                                    '已停止后续任务', 'Pending tasks cancelled.'),
                                orient=Qt.Orientation.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP_RIGHT,
                                duration=4000,
                                parent=self)
                return

            if launch_state == "timeout":
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.warning(self._ui_text('等待游戏窗口超时，已取消本次自动任务',
                                                  'Waiting for game window timed out, pending tasks cancelled.'))
                InfoBar.warning(title=self._ui_text('等待超时', 'Launch timeout'),
                                content=self._ui_text(
                                    '已停止后续任务', 'Pending tasks cancelled.'),
                                orient=Qt.Orientation.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP_RIGHT,
                                duration=4000,
                                parent=self)
        except Exception as e:
            self.logger.error(self._ui_text(f'检测游戏启动状态时出现异常：{e}', f'Error occurred while checking game launch status: {e}'))
            self._clear_launch_watch_state()
            self._set_launch_pending_state(False)

    def _on_task_actually_started(self, task_id: str):
        is_solo_run = getattr(self, '_is_running_solo_flag', False)
        is_scheduled_run = getattr(self, '_is_scheduled_run_flag', False)

        for tid, item in self.task_widget_map.items():
            if hasattr(item, 'set_task_state'):
                if tid == task_id:
                    if is_scheduled_run:
                        state = 'running_scheduled'
                    elif is_solo_run:
                        state = 'running_solo'
                    else:
                        state = 'running_queue'
                    item.set_task_state(state)
                else:
                    pass

    def after_start_button_click(self, tasks_to_run):
        if len(tasks_to_run) > 1 or (
                tasks_to_run and not hasattr(self, '_is_running_solo_flag')):
            self._is_running_solo_flag = False

        if tasks_to_run:
            if not self.is_running:
                self.tasks_to_run = list(tasks_to_run)
                self.start_thread = self.periodic_controller.create_and_start_thread(
                    parent=self,
                    logger_instance=self.logger,
                    on_state_changed=self.handle_start,
                    on_task_completed=self.record_task_completed,
                    on_task_started=self._on_task_actually_started,
                    on_task_failed=self.record_task_failed,
                    on_show_tray_message=self._show_tray_message,
                )
            else:
                self.periodic_controller.stop_running_thread()
        else:
            InfoBar.error(title=self._ui_text('无任务', 'No task'),
                          content=self._ui_text(
                              "未选择任务或不在生效周期",
                              "No task selected or not in active period"),
                          orient=Qt.Orientation.Horizontal,
                          isClosable=False,
                          position=InfoBarPosition.TOP_RIGHT,
                          duration=2000,
                          parent=self)

    # 【新增】运行在主线程的槽函数，用于安全地调用 UI
    def _show_tray_message(self, title, content):
        tray_icon = QIcon(":/app/framework/ui/resources/images/logo.png")
        # 尝试复用主窗口的托盘图标（防止多次创建导致系统托盘出现“幽灵图标”）
        main_win = self.window()
        if hasattr(main_win, 'tray_icon') and main_win.tray_icon:
            main_win.tray_icon.showMessage(
                title, content, tray_icon, 1000
            )
        else:
            # 如果没获取到主窗口的托盘，临时创建一个（后备方案）
            app = QApplication.instance()
            if app:
                fallback_tray = QSystemTrayIcon(tray_icon, app)
                fallback_tray.show()
                fallback_tray.showMessage(title, content, tray_icon, 1000)

    def _guard_running_game_window(self):
        try:
            if not self.is_running:
                self._stop_running_guard()
                return

            if not self.periodic_controller.should_stop_for_window_closed(bool(self._is_game_window_open())):
                return

            self._stop_running_guard()
            self.logger.warning(self._ui_text('检测到游戏窗口已关闭，正在停止当前自动任务', 'Game window closed, stopping current automatic task'))
            self.periodic_controller.stop_running_thread(
                reason=self._ui_text('用户中断：游戏窗口已关闭', 'Interrupted by user: game window closed')
            )
        except Exception as e:
            self.logger.error(self._ui_text(f'运行中窗口守护检测异常：{e}', f'Error occurred while monitoring running game window: {e}'))
            self._stop_running_guard()

    def start_from_homepage(self):
        """专供首页快捷卡片调用：如果已经在运行，则什么都不做，绝不终止任务"""
        if self.is_running or self.is_launch_pending:
            self.logger.info(self._ui_text("任务已在运行，忽略首页启动请求。", "Task is already running, ignoring homepage launch request."))
            return

        # 如果空闲，则复用普通的立即执行逻辑
        self.on_start_button_click()

    def on_start_button_click(self):
        # 拦截：如果全局有外部任务在跑，只允许点击停止！绝不允许手动新增或启动。
        if getattr(self, 'is_global_running', False):
            task_coordinator.request_stop()
            return

        if self.is_running:
            self.periodic_controller.stop_running_thread(reason="User Stop")
            return

        tasks_to_run = collect_checked_tasks(
            task_order=self.ui.taskListWidget.get_task_order(),
            is_checked=lambda task_id: bool(
                self.task_widget_map.get(task_id).checkbox.isChecked()
            ) if self.task_widget_map.get(task_id) else False,
        )

        if tasks_to_run:
            self._initiate_task_run(tasks_to_run)
        else:
            InfoBar.error(title="队列为空", content=self._ui_text("请至少勾选一个任务进行立即执行", "Please select at least one task to run immediately"), parent=self)

    def after_finish(self):
        if getattr(self, '_is_running_solo_flag', False):
            self.logger.info(self._ui_text("单独重跑完毕，已返回空闲状态...", "Solo execution completed, returned to idle state..."))
            return

        self._auto_adjust_after_use_action()
        self.logger.info(self._ui_text("所有任务执行完毕，助手已进入挂机监控模式...", "All tasks completed, assistant entered monitoring mode..."))

    def set_checkbox_enable(self, enable: bool):
        for checkbox in self.ui.findChildren(CheckBox):
            # 保护机制：全局 UI 解锁时，永远不要解锁主任务选项
            if checkbox.objectName() == self.primary_option_key:
                checkbox.setEnabled(False)
            else:
                checkbox.setEnabled(enable)

    def set_current_index(self, index):
        try:
            if index < 0 or index >= len(self.setting_name_list):
                return
            self.ui.TitleLabel_setting.setText(
                self._ui_text("设置", "Settings") + "-" +
                self.setting_name_list[index])
            self.ui.PopUpAniStackedWidget.setCurrentIndex(index)
        except Exception as e:
            self.logger.error(e)

    def record_task_failed(self, task_id: str):
        meta = self.task_registry.get(task_id, {})
        task_name = meta.get("en_name", task_id) if getattr(self, '_is_non_chinese_ui', False) else meta.get("zh_name", task_id)

        fail_msg = f"⚠️ Task [{task_name}] skipped!" if getattr(self, '_is_non_chinese_ui', False) else f"⚠️ {task_name} 未能成功执行，已跳过！"
        self.logger.warning(fail_msg)

        # UI 状态机置为未成功（红色红叉），并且不更新它的 last_run 时间，下次触发还能重试
        task_item = self.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, 'set_task_state'):
            task_item.set_task_state('failed')

            # 如果还在连跑队列里，立刻把这个失败的任务重新软锁定，防止 UI 被用户误点
            if getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False):
                if hasattr(task_item, 'lock_ui_for_execution'):
                    task_item.lock_ui_for_execution()

    def record_task_completed(self, task_id: str):
        sequence = self.scheduler.get_task_sequence()

        meta = self.task_registry.get(task_id, {})
        task_name = meta.get("en_name", task_id) if getattr(
            self, '_is_non_chinese_ui', False) else meta.get(
                "zh_name", task_id)

        # 简单更新该任务的总体最后完成时间戳
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["last_run"] = int(time.time())
                break
        self.scheduler.save_task_sequence(sequence)

        success_msg = f"✨ Task [{task_name}] completed!" if getattr(
            self, '_is_non_chinese_ui', False) else f"✨ {task_name} 执行完毕！"
        self.logger.info(success_msg)

        # UI 状态机置为已完成（绿色打勾）
        task_item = self.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, 'set_task_state'):
            task_item.set_task_state('completed')

            # 如果全局队列还在运行（其他任务还在排队或执行），必须立刻把刚完成的任务重新软锁定！
            if getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False):
                if hasattr(task_item, 'lock_ui_for_execution'):
                    task_item.lock_ui_for_execution()

    def save_changed(self, widget, *args):
        maybe_power_enabled = self.settings_usecase.persist_widget_change(widget)
        if maybe_power_enabled is not None:
            self.ui.ComboBox_power_day.setEnabled(bool(maybe_power_enabled))

    def get_tips(self, url=None):
        try:
            self.event_tips_usecase.refresh_tips_panel(
                ui=self.ui,
                logger=self.logger,
                host=self,
                url=url,
            )
        except Exception as e:
            self.logger.error(ui_text(f"更新控件出错：{e}", f"Error occurred while updating controls: {e}"))

    def _load_presets(self):
        PeriodicPresetActions.load_presets(self)

    def _on_preset_changed(self, index):
        PeriodicPresetActions.on_preset_changed(self, index)

    def _on_add_preset_clicked(self):
        PeriodicPresetActions.on_add_preset_clicked(self)

    def _save_current_preset(self):
        PeriodicPresetActions.save_current_preset(self)

    def _delete_current_preset(self):
        PeriodicPresetActions.delete_current_preset(self)

    def closeEvent(self, event):
        super().closeEvent(event)
        self.scheduler.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()



