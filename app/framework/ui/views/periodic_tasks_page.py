import logging
from typing import Callable, Dict, List

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout
from qfluentwidgets import CheckBox

from app.framework.infra.config.app_config import is_non_chinese_ui_language
from app.framework.ui.shared.style_sheet import StyleSheet

from app.framework.core.task_engine.scheduler import Scheduler
from app.framework.core.interfaces.game_environment import IGameEnvironment
from app.framework.core.interfaces.periodic_ports import (
    CollectSuppliesActionsFactory,
    EnterGameActionsFactory,
    EventTipsActionsFactory,
    TaskProfileProvider,
    ShoppingSelectionFactory,
)
from app.framework.infra.logging.gui_logger import setup_ui_logger
from app.framework.application.periodic.periodic_controller import PeriodicController
from app.framework.application.periodic.periodic_settings_usecase import PeriodicSettingsUseCase
from app.framework.application.periodic.periodic_ui_binding_usecase import PeriodicUiBindingUseCase
from app.framework.core.event_bus.global_task_bus import global_task_bus
from app.framework.application.periodic.periodic_dispatcher import PeriodicDispatcher
from app.framework.application.periodic.on_demand_runner import SingleTaskToggle
from app.framework.application.periodic.periodic_orchestration import (
    build_active_schedule_lines,
)
from app.framework.application.periodic.periodic_page_actions import (
    PeriodicPresetActions,
    PeriodicRuleActions,
    PeriodicRuntimeActions,
)

# 导入视图与基类
from app.framework.ui.views.periodic_tasks_view import PeriodicTasksView, TaskItemWidget
from .periodic_base import BaseInterface

logger = logging.getLogger(__name__)

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

    def __init__(
        self,
        text: str,
        parent=None,
        *,
        game_environment: IGameEnvironment | None = None,
        home_sync=None,
        task_profile_provider: TaskProfileProvider | None = None,
        create_shopping_selection_usecase: ShoppingSelectionFactory | None = None,
        create_enter_game_actions: EnterGameActionsFactory | None = None,
        create_collect_supplies_actions: CollectSuppliesActionsFactory | None = None,
        create_event_tips_actions: EventTipsActionsFactory | None = None,
        startup_update_hook: Callable[[object], None] | None = None,
        module_text_applier: Callable | None = None,
    ):
        super().__init__(parent)
        BaseInterface.__init__(self)

        self._is_non_chinese_ui = is_non_chinese_ui_language()
        if task_profile_provider is None:
            raise ValueError("PeriodicTasksPage requires injected task_profile_provider")
        if create_shopping_selection_usecase is None:
            raise ValueError("PeriodicTasksPage requires injected create_shopping_selection_usecase")
        if create_enter_game_actions is None:
            raise ValueError("PeriodicTasksPage requires injected create_enter_game_actions")
        if create_collect_supplies_actions is None:
            raise ValueError("PeriodicTasksPage requires injected create_collect_supplies_actions")
        if create_event_tips_actions is None:
            raise ValueError("PeriodicTasksPage requires injected create_event_tips_actions")

        self.task_profile = task_profile_provider()
        self.task_registry = self.task_profile.task_registry
        self.primary_task_id = self.task_profile.primary_task_id
        self.mandatory_task_ids = set(self.task_profile.mandatory_task_ids)
        self.primary_option_key = self.task_profile.primary_option_key

        self.setting_name_list = self._build_setting_name_list()

        if game_environment is None:
            raise ValueError("PeriodicTasksPage requires an injected game_environment")
        self.game_environment = game_environment
        self.home_sync = home_sync or (lambda _auto, _logger: True)
        self.startup_update_hook = startup_update_hook
        self.shopping_selection_usecase = create_shopping_selection_usecase(self._is_non_chinese_ui)

        self.ui = PeriodicTasksView(
            self,
            is_non_chinese_ui=self._is_non_chinese_ui,
            module_text_applier=module_text_applier,
        )
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent
        self.task_coordinator = global_task_bus

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
        self.enter_game_actions = create_enter_game_actions(self.game_environment)
        self.collect_supplies_actions = create_collect_supplies_actions(self.settings_usecase)
        self.event_tips_actions = create_event_tips_actions(
            self.settings_usecase,
            self._is_non_chinese_ui,
            self._ui_text,
        )

        self.task_widget_map: Dict[str, TaskItemWidget] = {}
        self._init_task_list_widgets()

        self.is_running = False

        self.start_thread = None
        self.launch_process = None
        self.launch_deadline = 0.0
        self.is_launch_pending = False
        self._is_running_solo_flag = False
        self._is_scheduled_run_flag = False

        self._initWidget()
        self._connect_to_slot()

        self.logger = setup_ui_logger("logger_daily", self.ui.textBrowser_log)
        self.event_tips_actions.bind(ui=self.ui, logger=self.logger, host=self)
        self.refresh_tips = self.event_tips_actions.refresh_tips
        self.periodic_dispatcher = PeriodicDispatcher(self.logger, self._ui_text)
        self.single_task_toggle = SingleTaskToggle()

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(
            self._guard_running_game_window)

        self._shared_sidebar_cards = [
            self.ui.SimpleCardWidget,
            self.ui.SimpleCardWidget_tips,
        ]
        self._shared_sidebar_detached = False

        QTimer.singleShot(500, self._on_init_sync)

        if self.settings_usecase.should_check_update_on_startup():
            if callable(self.startup_update_hook):
                self.startup_update_hook(self)
            else:
                self.refresh_tips()
        else:
            self.refresh_tips()

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
        if ui is not None and hasattr(ui, "get_module_widget"):
            widget = ui.get_module_widget(item)
            if widget is not None:
                return widget
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

        self._load_config()
        self._sync_task_sequence_from_ui()
        self._load_initial_task_panel()

        combo_power_day = self.ui.require_module_widget("ComboBox_power_day")
        check_use_power = self.ui.require_module_widget("CheckBox_is_use_power")
        combo_power_day.setEnabled(check_use_power.isChecked())

        StyleSheet.PERIODIC_TASKS_INTERFACE.apply(self)
        shop_scroll_area = self.ui.get_module_widget("ScrollArea")
        if shop_scroll_area is not None and hasattr(shop_scroll_area, "enableTransparentBackground"):
            shop_scroll_area.enableTransparentBackground()
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
            root_widget=self.ui,
        )

    def _connect_to_save_changed(self):
        self.ui_binding_usecase.connect_config_bindings(
            root_widget=self.ui,
            on_widget_change=self.save_changed,
        )
        self.shopping_selection_usecase.connect_selector_bindings(
            root_widget=self.ui,
            settings_usecase=self.settings_usecase,
        )

    def open_game_directly(self):
        try:
            result = self.enter_game_actions.launch_game(logger=self.logger)
            if not result.get("ok"):
                self.logger.error(result.get("error", "启动游戏失败"))
                self._set_launch_pending_state(False)
                return

            self.launch_process = result.get("process")
            self.periodic_controller.mark_launch_started(self.launch_process, timeout_seconds=90)
            self.check_game_window_timer.start(500)
            self._set_launch_pending_state(True)
        except Exception as e:
            self.logger.error(self._ui_text(f'出现报错: {e}', f'Error occurred: {e}'))
            self._set_launch_pending_state(False)

    def _is_game_window_open(self):
        return self.game_environment.is_running()

    def _clear_launch_watch_state(self):
        self.check_game_window_timer.stop()
        self.periodic_controller.clear_launch_watch_state()

    def _stop_running_guard(self):
        self.running_game_guard_timer.stop()

    def _connect_to_slot(self):
        tutorial_button = self.ui.require_module_widget("PrimaryPushButton_path_tutorial")
        select_directory_button = self.ui.require_module_widget("PushButton_select_directory")
        game_directory_line_edit = self.ui.require_module_widget("LineEdit_game_directory")
        import_codes_button = self.ui.require_module_widget("PrimaryPushButton_import_codes")
        reset_codes_button = self.ui.require_module_widget("PushButton_reset_codes")
        import_codes_text_edit = self.ui.require_module_widget("TextEdit_import_codes")
        auto_open_checkbox = self.ui.require_module_widget("CheckBox_open_game_directly")

        self.ui.PushButton_start.clicked.connect(self.on_start_button_click)
        tutorial_button.clicked.connect(
            lambda: self.enter_game_actions.show_path_tutorial(
                host=self,
                anchor_widget=tutorial_button,
            ))
        self.ui.PushButton_select_all.clicked.connect(
            lambda: select_all(self.ui.SimpleCardWidget_option))
        self.ui.PushButton_no_select.clicked.connect(
            lambda: no_select(self.ui.SimpleCardWidget_option, self.primary_option_key))
        select_directory_button.clicked.connect(
            lambda: self.enter_game_actions.on_select_directory_click(
                host=self,
                line_edit=game_directory_line_edit,
                settings_usecase=self.settings_usecase,
            ))
        import_codes_button.clicked.connect(
            lambda: self.collect_supplies_actions.on_import_codes_click(
                host=self,
                text_edit=import_codes_text_edit,
            ))
        reset_codes_button.clicked.connect(
            lambda: self.collect_supplies_actions.on_reset_codes_click(
                host=self,
                text_edit=import_codes_text_edit,
            ))

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
        auto_open_checkbox.stateChanged.connect(
            lambda state: self.enter_game_actions.on_auto_open_toggled(host=self, state=state))

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

        self.task_coordinator.state_changed.connect(self._on_global_state_changed)
        self.task_coordinator.stop_requested.connect(self._on_global_stop_request)
        self._connect_to_save_changed()

    def _on_global_state_changed(self, is_running: bool, zh_name: str, en_name: str, source: str):
        PeriodicRuntimeActions.on_global_state_changed(self, is_running, zh_name, en_name, source)

    # 【新增】响应全局的停止请求 (F8)
    def _on_global_stop_request(self):
        PeriodicRuntimeActions.on_global_stop_request(self)

    def _on_task_checkbox_changed(self, task_id: str, is_checked: bool):
        PeriodicRuntimeActions.on_task_checkbox_changed(self, task_id, is_checked)

    def _on_shared_config_changed(self, task_id: str, new_config: dict):
        PeriodicRuntimeActions.on_shared_config_changed(self, task_id, new_config)

    def _on_toggle_all_cycles_clicked(self, enable: bool):
        PeriodicRuntimeActions.on_toggle_all_cycles_clicked(self, enable)

    def _set_launch_pending_state(self, pending: bool):
        PeriodicRuntimeActions.set_launch_pending_state(self, pending)

    def _initiate_task_run(self, tasks_to_run: List[str]):
        PeriodicRuntimeActions.initiate_task_run(self, tasks_to_run)

    def handle_start(self, str_flag):
        PeriodicRuntimeActions.handle_start(self, str_flag)

    def _on_task_play_clicked(self, task_id: str):
        PeriodicRuntimeActions.on_task_play_clicked(self, task_id)

    def _on_task_play_from_here_clicked(self, start_task_id: str):
        PeriodicRuntimeActions.on_task_play_from_here_clicked(self, start_task_id)

    def _on_copy_single_rule_to_checked(self, rule_data: dict):
        PeriodicRuleActions.copy_single_rule_to_checked(self, rule_data)

    def _on_withdraw_single_rule_from_checked(self, rule_data: dict):
        PeriodicRuleActions.withdraw_single_rule_from_checked(self, rule_data)

    def check_game_open(self):
        PeriodicRuntimeActions.check_game_open(self)

    def _on_task_actually_started(self, task_id: str):
        PeriodicRuntimeActions.on_task_actually_started(self, task_id)

    def after_start_button_click(self, tasks_to_run):
        PeriodicRuntimeActions.after_start_button_click(self, tasks_to_run)

    # 【新增】运行在主线程的槽函数，用于安全地调用 UI
    def _show_tray_message(self, title, content):
        PeriodicRuntimeActions.show_tray_message(self, title, content)

    def _guard_running_game_window(self):
        PeriodicRuntimeActions.guard_running_game_window(self)

    def start_from_homepage(self):
        """专供首页快捷卡片调用：如果已经在运行，则什么都不做，绝不终止任务"""
        if self.is_running or self.is_launch_pending:
            self.logger.info(self._ui_text("任务已在运行，忽略首页启动请求。", "Task is already running, ignoring homepage launch request."))
            return

        # 如果空闲，则复用普通的立即执行逻辑
        self.on_start_button_click()

    def on_start_button_click(self):
        PeriodicRuntimeActions.on_start_button_click(self)

    def after_finish(self):
        PeriodicRuntimeActions.after_finish(self)

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


    def save_changed(self, widget, *args):
        maybe_power_enabled = self.settings_usecase.persist_widget_change(widget)
        if maybe_power_enabled is not None:
            self.ui.require_module_widget("ComboBox_power_day").setEnabled(bool(maybe_power_enabled))

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



