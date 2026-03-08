import copy
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from functools import partial
from typing import Dict, Any, List

import win32con
import win32gui
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItemIterator, QFileDialog, QVBoxLayout, QSystemTrayIcon, QApplication
from qfluentwidgets import FluentIcon as FIF, InfoBar, InfoBarPosition, CheckBox, ComboBox, LineEdit, \
    BodyLabel, ProgressBar, FlyoutView, Flyout, SpinBox

from app.common.config import config, is_non_chinese_ui_language
from app.common.data_models import ApiResponse, parse_config_update_data
from app.common.signal_bus import signalBus
from app.common.style_sheet import StyleSheet
from utils.game_launcher import launch_game_with_guard
from utils.net_utils import get_cloudflare_data, get_date_from_api
from utils.ui_utils import get_all_children, ui_text
from utils.win_utils import is_exist_snowbreak

# 导入业务模块
from app.modules.base_task.base_task import BaseTask
from app.modules.chasm.chasm import ChasmModule
from app.modules.collect_supplies.collect_supplies import CollectSuppliesModule
from app.modules.enter_game.enter_game import EnterGameModule
from app.modules.get_reward.get_reward import GetRewardModule
from app.modules.ocr import ocr
from app.modules.person.person import PersonModule
from app.modules.shopping.shopping import ShoppingModule
from app.modules.use_power.use_power import UsePowerModule
from app.repackage.custom_message_box import CustomMessageBox
from app.repackage.tree import TreeFrame_person, TreeFrame_weapon
from app.modules.operation_action.operation_action import OperationModule
from app.modules.upgrade.weapon import WeaponUpgradeModule
from app.modules.jigsaw.shards import ShardExchangeModule
from app.common.constants import get_person_text_to_key_map, get_weapon_text_to_key_map
from app.common.scheduler import Scheduler
from app.common.gui_logger import setup_ui_logger

# 导入视图与基类
from app.view.daily_view import DailyView, TaskItemWidget
from .base_interface import BaseInterface

logger = logging.getLogger(__name__)

TASK_REGISTRY = {
    "task_login": {
        "module_class": EnterGameModule,
        "ui_page_index": 0,
        "option_key": "CheckBox_entry_1",
        "zh_name": "自动登录",
        "en_name": "Auto Login",
    },
    "task_supplies": {
        "module_class": CollectSuppliesModule,
        "ui_page_index": 1,
        "option_key": "CheckBox_stamina_2",
        "zh_name": "领取福利",
        "en_name": "Collect Supplies",
    },
    "task_shop": {
        "module_class": ShoppingModule,
        "ui_page_index": 2,
        "option_key": "CheckBox_shop_3",
        "zh_name": "商店购买",
        "en_name": "Shop",
    },
    "task_stamina": {
        "module_class": UsePowerModule,
        "ui_page_index": 3,
        "option_key": "CheckBox_use_power_4",
        "zh_name": "体力扫荡",
        "en_name": "Use Stamina",
    },
    "task_shards": {
        "module_class": PersonModule,
        "ui_page_index": 4,
        "option_key": "CheckBox_person_5",
        "zh_name": "角色碎片",
        "en_name": "Character Shards",
    },
    "task_chasm": {
        "module_class": ChasmModule,
        "ui_page_index": 5,
        "option_key": "CheckBox_chasm_6",
        "zh_name": "精神拟境",
        "en_name": "Neural Sim",
    },
    "task_reward": {
        "module_class": GetRewardModule,
        "ui_page_index": 6,
        "option_key": "CheckBox_reward_7",
        "zh_name": "收取奖励",
        "en_name": "Claim Rewards",
    },
    "task_operation": {
        "module_class": OperationModule,
        "ui_page_index": 7,
        "option_key": "CheckBox_operation_8",
        "zh_name": "常规训练",
        "en_name": "Operation",
    },
    "task_weapon": {
        "module_class": WeaponUpgradeModule,
        "ui_page_index": 8,
        "option_key": "CheckBox_weapon_8",
        "zh_name": "武器升级",
        "en_name": "Weapon Upgrade",
    },
    "task_shard_exchange": {
        "module_class": ShardExchangeModule,
        "ui_page_index": 9,
        "option_key": "CheckBox_shard_exchange_9",
        "zh_name": "信源碎片",
        "en_name": "Shard Exchange",
    },
}

# ==========================================
# Model 层：专门负责纯数据与逻辑计算
# ==========================================
class DailyModel:
    @staticmethod
    def calculate_time_difference(date_due: str):
        current_year = datetime.now().year
        start_date_str, end_date_str = date_due.split('-')
        start_time = datetime.strptime(f"{current_year}.{start_date_str}", "%Y.%m.%d")
        end_time = datetime.strptime(f"{current_year}.{end_date_str}", "%Y.%m.%d")

        if end_time < start_time:
            end_time = datetime.strptime(f"{current_year + 1}.{end_date_str}", "%Y.%m.%d")

        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total_day = (end_time - start_time).days + 1

        if now < start_time:
            days_to_start = (start_time - now).days
            return days_to_start, total_day, 1
        elif now > end_time:
            return 0, total_day, -1
        else:
            days_remaining = (end_time - now).days + 1
            return days_remaining, total_day, 0

# ==========================================
# 线程与后台任务类
# ==========================================
class CloudflareUpdateThread(QThread):
    update_finished = Signal(dict)
    update_failed = Signal(str)

    def run(self):
        try:
            data = get_cloudflare_data()
            if 'error' in data:
                self.update_failed.emit(data["error"])
            else:
                self.update_finished.emit(data)
        except Exception as e:
            self.update_failed.emit(f"网络请求异常: {str(e)}")

class AutomationSession:
    def __init__(self, logger_instance):
        self.logger = logger_instance
        self._task_context = BaseTask()
        self._task_context.logger = self.logger

        from app.modules.ocr import ocr
        ocr.logger = self.logger

    @property
    def auto(self):
        return self._task_context.auto

    def prepare(self):
        ok = self._task_context.init_auto('game')
        if not ok:
            return False
        if self.auto is not None:
            self.auto.reset()
        return True

    def stop(self):
        if self.auto is None:
            return
        self.auto.stop()


class StartThread(QThread):
    is_running_signal = Signal(str)
    stop_signal = Signal()
    task_completed_signal = Signal(str)
    task_started_signal = Signal(str)
    task_failed_signal = Signal(str)  # 【新增】任务失败/跳过信号
    show_tray_message_signal = Signal(str, str)

    def __init__(self, tasks_to_run: list, logger_instance, parent=None):
        super().__init__(parent)
        self.tasks_to_run = tasks_to_run
        # 接管传入的专属 logger
        self.logger = logger_instance
        self.session = AutomationSession(self.logger)
        self._is_running = True
        self._interrupted_reason = None

    def stop(self, reason=None):
        self._is_running = False
        if reason:
            self._interrupted_reason = reason
            self.logger.warning(ui_text(f"检测到中断，停止自动任务：{reason}", f"Interrupt detected, stopping automatic task: {reason}"))
        if self.session.auto is not None:
            try:
                self.session.stop()
            except Exception as e:
                self.logger.warning(ui_text(f"停止自动任务时发生异常，已忽略：{e}", f"Exception occurred while stopping automatic task, ignored: {e}"))

    def run(self):
        self.is_running_signal.emit('start')
        normal_stop_flag = True
        try:
            if self.tasks_to_run:
                if not self.session.prepare():
                    normal_stop_flag = False
                    return

            auto = self.session.auto

            for task_id in self.tasks_to_run:
                if not self._is_running:
                    normal_stop_flag = False
                    break

                meta = TASK_REGISTRY.get(task_id)
                if not meta:
                    continue

                task_name = meta["en_name"] if is_non_chinese_ui_language() else meta["zh_name"]
                self.logger.info(ui_text(f"当前任务：{task_name}", f"Current task: {task_name}"))
                self.task_started_signal.emit(task_id)

                # =================【核心新增：前置校验】=================
                task_success = True
                if task_id != "task_login":
                    self.logger.info(ui_text(f"正在准备 {task_name}，尝试返回主界面...", f"Preparing {task_name}, returning to home..."))

                    if not auto.back_to_home():
                        # err_msg = f"[{task_name}] Failed to return to home before start, skipping." if is_non_chinese_ui_language() else f"[{task_name}] 开始前返回主界面失败，跳过该任务"
                        self.logger.error(ui_text(f"[{task_name}] 开始前返回主界面失败，跳过该任务", f"[{task_name}] Failed to return to home before start, skipping."))
                        task_success = False
                # ========================================================

                # 只有前置校验通过，才执行业务逻辑
                if task_success:
                    module_class = meta["module_class"]
                    module = module_class(auto, self.logger)
                    module.run()

                    # =================【核心新增：后置复位】=================
                    if task_id != "task_login" and self._is_running:
                        msg = ui_text(f"{task_name} 执行完毕，正在返回主界面...", f"{task_name} finished, returning to home...")
                        self.logger.info(msg)
                        auto.back_to_home()
                    # ========================================================

                # 根据是否成功发射不同的信号
                if self._is_running:
                    if task_success:
                        self.task_completed_signal.emit(task_id)
                    else:
                        self.task_failed_signal.emit(task_id)

                if not self._is_running:
                    normal_stop_flag = False
                    break

                if config.inform_message.value or '--toast-only' in sys.argv:
                    full_time = auto.calculate_power_time() if auto is not None else None
                    content = f'体力将在 {full_time} 完全恢复' if full_time else "体力计算出错"

                    self.show_tray_message_signal.emit('已完成勾选任务', content)

        except Exception as e:
            if str(e) != '已停止':
                self.logger.warning(e)
        finally:
            if self.session.auto is not None:
                self.session.stop()
            if normal_stop_flag and self._is_running:
                self.is_running_signal.emit('end')
            else:
                if self._interrupted_reason:
                    self.is_running_signal.emit('interrupted')
                else:
                    self.is_running_signal.emit('no_auto')


def select_all(widget):
    for checkbox in widget.findChildren(CheckBox):
        checkbox.setChecked(True)

def no_select(widget):
    for checkbox in widget.findChildren(CheckBox):
        # 保护机制：如果是“自动登录”对应的 checkbox 选项名，绝对不执行取消勾选
        if checkbox.objectName() != "CheckBox_entry_1":
            checkbox.setChecked(False)

# ==========================================
# Controller 层
# ==========================================
class Daily(QFrame, BaseInterface):

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        BaseInterface.__init__(self)

        self._is_non_chinese_ui = is_non_chinese_ui_language()

        self.setting_name_list = [
            self._ui_text('登录', 'Login'),
            self._ui_text('福利', 'Supplies'),
            self._ui_text('商店', 'Shop'),
            self._ui_text('体力', 'Stamina'),
            self._ui_text('碎片', 'Shards'),
            self._ui_text('拟境', 'Neural Sim'),
            self._ui_text('奖励', 'Claim Rewards'),
            self._ui_text('常规训练', 'Operation'),
            self._ui_text('武器培养', 'Weapon'),
            self._ui_text('信源碎片', 'Shard Exchange'),
        ]

        self.person_text_to_key = get_person_text_to_key_map(self._is_non_chinese_ui)
        self.weapon_text_to_key = get_weapon_text_to_key_map(self._is_non_chinese_ui)

        self.ui = DailyView(self, is_non_chinese_ui=self._is_non_chinese_ui)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.scheduler = Scheduler(self)

        self.task_widget_map: Dict[str, TaskItemWidget] = {}
        self._init_task_list_widgets()

        self.is_running = False

        self.select_person = TreeFrame_person(
            parent=self.ui.ScrollArea,
            enableCheck=True,
            is_non_chinese_ui=self._is_non_chinese_ui)
        self.select_weapon = TreeFrame_weapon(
            parent=self.ui.ScrollArea,
            enableCheck=True,
            is_non_chinese_ui=self._is_non_chinese_ui)

        self.game_hwnd = None
        self.start_thread = None
        self.launch_process = None
        self.launch_deadline = 0.0
        self.is_launch_pending = False
        self._is_dialog_open = False

        self._is_running_solo_flag = False
        self._is_scheduled_run_flag = False

        self._initWidget()
        self._connect_to_slot()

        self.logger = setup_ui_logger("logger_daily", self.ui.textBrowser_log)

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(
            self._guard_running_game_window)

        self._f8_pressed = False

        self.checkbox_dic = None

        QTimer.singleShot(500, self._on_init_sync)

        if config.checkUpdateAtStartUp.value:
            self.update_online_cloudflare()
        else:
            self.get_tips()

        self.scheduler.start()

    def _on_init_sync(self):
        self._auto_adjust_after_use_action()
        self._output_schedule_log()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _on_scheduled_tasks_due(self, new_tasks_found: List[str]):
        """
        Slot for the scheduler's `tasks_due` signal.
        Handles queuing or immediate execution of scheduled tasks.
        """
        # If the game is in the process of launching, do nothing and wait for the next cycle.
        if getattr(self, 'is_launch_pending', False):
            return

        current_time_str = datetime.now().strftime("%H:%M")
        is_self_running = getattr(self, 'is_running', False)
        is_external_running = getattr(self, 'is_global_running', False)

        # If the system is busy (either this module or another is running), queue the tasks.
        if is_self_running or is_external_running:
            self.logger.info(ui_text(f"⏰ 到点触发计划: {current_time_str}，系统正忙，已加入队列排队: {new_tasks_found}",
                                     f"⏰ Scheduled task triggered at {current_time_str}, system is busy, added to queue: {new_tasks_found}"))

            if not hasattr(self, 'tasks_to_run') or self.tasks_to_run is None:
                self.tasks_to_run = []

            for tid in new_tasks_found:
                self.tasks_to_run.append(tid)
                task_item = self.task_widget_map.get(tid)
                if task_item and hasattr(task_item, 'set_task_state'):
                    task_item.set_task_state('queued')

            # If an external task is running, set a flag to auto-run queued tasks when it finishes.
            if is_external_running and not is_self_running:
                self._waiting_for_external_to_finish = True
            return

        # If the system is idle, execute the tasks immediately.
        self.logger.info(ui_text(f"⏰ 到点触发计划: {current_time_str}，执行列表: {new_tasks_found}",
                                 f"⏰ Scheduled task triggered at {current_time_str}, executing tasks: {new_tasks_found}"))
        self._is_scheduled_run_flag = True
        self._initiate_task_run(new_tasks_found)

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

        StyleSheet.HOME_INTERFACE.apply(self)
        self.ui.ScrollArea.enableTransparentBackground()
        self.ui.ScrollArea_tips.enableTransparentBackground()

        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget)
        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget_tips)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget, 0, 2, 1, 1)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget_tips, 1, 2, 1,
                                       1)

    def _output_schedule_log(self):
        sequence = self.scheduler.get_task_sequence()
        schedule_logs = []
        color_task, color_type, color_time = "#00BFFF", "#32CD32", "#FFA500"

        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            if task_cfg.get("use_periodic", False):
                meta = TASK_REGISTRY.get(task_id, {})
                task_name = meta.get(
                    "en_name",
                    task_id) if self._is_non_chinese_ui else meta.get(
                        "zh_name", task_id)
                rules = task_cfg.get("execution_config", [])
                rule_strs = []
                for r in rules:
                    r_type = str(r.get("type", "daily")).lower()
                    r_time = r.get("time", "00:00")
                    r_day = int(r.get("day", 0))
                    colored_time = f'<span style="color: {color_time};"><b>{r_time}</b></span>'

                    if r_type in ["daily", "每天"]:
                        t_str = "Daily" if self._is_non_chinese_ui else "每天"
                        rule_strs.append(
                            f'<span style="color: {color_type};">{t_str}</span> {colored_time}'
                        )
                    elif r_type in ["weekly", "每周"]:
                        days = [
                            "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"
                        ] if self._is_non_chinese_ui else [
                            "周一", "周二", "周三", "周四", "周五", "周六", "周日"
                        ]
                        rule_strs.append(
                            f'<span style="color: {color_type};">{days[r_day]}</span> {colored_time}'
                        )
                    elif r_type in ["monthly", "每月"]:
                        t_str = f"Day {r_day}" if self._is_non_chinese_ui else f"每月{r_day}日"
                        rule_strs.append(
                            f'<span style="color: {color_type};">{t_str}</span> {colored_time}'
                        )

                if rule_strs:
                    schedule_logs.append(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='color: {color_task};'><b>[{task_name}]</b></span> ➔ {', '.join(rule_strs)}"
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
            use_periodic = bool(task_cfg.get("use_periodic", False))

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
            meta = TASK_REGISTRY.get(task_id)
            if not meta:
                continue

            task_item = TaskItemWidget(
                task_id=task_id,
                zh_name=meta["zh_name"],
                en_name=meta["en_name"],
                is_enabled=bool(task_cfg.get("enabled", True)),
                is_non_chinese_ui=self._is_non_chinese_ui,
                parent=self.ui.taskListWidget,
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
            if task_id in TASK_REGISTRY:
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

        # If a task other than 'task_login' is dragged to the top, refresh the UI to correct its position.
        if task_id_order and task_id_order[0] != "task_login":
            self._init_task_list_widgets()

    def _on_task_settings_clicked(self, task_id: str):
        meta = TASK_REGISTRY.get(task_id)
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
        for widget in self.ui.findChildren(QWidget):
            config_item = getattr(config, widget.objectName(), None)
            if config_item:
                if isinstance(widget, CheckBox):
                    widget.setChecked(config_item.value)
                elif isinstance(widget, ComboBox):
                    widget.setCurrentIndex(config_item.value)
                elif isinstance(widget, LineEdit):
                    widget.setText(str(config_item.value))
                elif isinstance(widget, SpinBox):
                    widget.setValue(config_item.value)
        self._load_item_config()

    def _load_item_config(self):
        item = QTreeWidgetItemIterator(self.select_person.tree)
        while item.value():
            item_key = self.person_text_to_key.get(item.value().text(0))
            config_item = getattr(config, item_key, None) if item_key else None
            if config_item is not None:
                item.value().setCheckState(
                    0, Qt.CheckState.Checked
                    if config_item.value else Qt.CheckState.Unchecked)
            item += 1

        item2 = QTreeWidgetItemIterator(self.select_weapon.tree)
        while item2.value():
            item_key2 = self.weapon_text_to_key.get(item2.value().text(0))
            config_item2 = getattr(config, item_key2,
                                   None) if item_key2 else None
            if config_item2 is not None:
                item2.value().setCheckState(
                    0, Qt.CheckState.Checked
                    if config_item2.value else Qt.CheckState.Unchecked)
            item2 += 1

    def _connect_to_save_changed(self):
        self.select_person.itemStateChanged.connect(self.save_item_changed)
        self.select_weapon.itemStateChanged.connect(self.save_item2_changed)

        children_list = get_all_children(self.ui)
        for children in children_list:
            if isinstance(children, CheckBox):
                children.stateChanged.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, ComboBox):
                children.currentIndexChanged.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, LineEdit):
                children.editingFinished.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, SpinBox):
                children.valueChanged.connect(
                    partial(self.save_changed, children))

    def set_hwnd(self, hwnd):
        self.game_hwnd = hwnd

    def on_path_tutorial_click(self):
        tutorial_title = "How to find the game path" if self._is_non_chinese_ui else "如何查找对应游戏路径"
        tutorial_content = (
            'No matter which server/channel you play, first select your server in Settings.\n'
            'For global server, choose a path like "E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK".\n'
            'For CN/Bilibili server, open the Snowbreak launcher and find launcher settings.\n'
            'Then choose the game installation path shown there.'
            if self._is_non_chinese_ui else
            '不管你是哪个渠道服的玩家，第一步都应该先去设置里选服\n国际服选完服之后选择类似"E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK"的路径\n官服和b服的玩家打开尘白启动器，新版或者旧版启动器都找到启动器里对应的设置\n在下面的路径选择中找到并选择刚才你看到的路径'
        )
        view = FlyoutView(title=tutorial_title,
                          content=tutorial_content,
                          image="asset/path_tutorial.png",
                          isClosable=True)
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)
        w = Flyout.make(view, self.ui.PrimaryPushButton_path_tutorial, self)
        view.closed.connect(w.close)

    def update_online_cloudflare(self):
        self.cloudflare_thread = CloudflareUpdateThread()
        self.cloudflare_thread.update_finished.connect(
            self._handle_cloudflare_success)
        self.cloudflare_thread.update_failed.connect(
            self._handle_cloudflare_error)
        self.cloudflare_thread.start()

    def _handle_cloudflare_success(self, data):
        try:
            if 'data' not in data:
                self.logger.error(ui_text('通过cloudflare在线更新出错: 返回数据格式不正确', 'Error occurred while updating through Cloudflare: Incorrect data format returned'))
                self.get_tips()
                return

            online_data = data["data"]
            required_fields = ['updateData', 'redeemCodes', 'version']
            update_data_fields = ['linkCatId', 'linkId', 'questName']

            for field in required_fields:
                if field not in online_data:
                    self.logger.error(ui_text(f'通过cloudflare在线更新出错: 缺少必要字段 {field}', f'Error occurred while updating through Cloudflare: Missing required field {field} in updateData'))
                    self.get_tips()
                    return

            if 'updateData' in online_data:
                for field in update_data_fields:
                    if field not in online_data['updateData']:
                        self.logger.error(
                            ui_text(f'通过cloudflare在线更新出错: updateData缺少必要字段 {field}', f'Error occurred while updating through Cloudflare: Missing required field {field} in updateData'))
                        self.get_tips()
                        return

            try:
                response = ApiResponse.from_dict(data)
                self._handle_update_logic(data, online_data, response)
            except Exception as e:
                self.logger.error(ui_text(f'解析API响应数据时出错: {str(e)}', f'Error occurred while parsing API response data: {str(e)}'))
                traceback.print_exc()
                self._handle_update_logic_fallback(data, online_data)
        except Exception as e:
            self.logger.error(ui_text(f'处理Cloudflare数据时出错: {str(e)}', f'Error occurred while processing Cloudflare data: {str(e)}'))
            self.get_tips()

    def _handle_update_logic(self, raw_data: Dict[str, Any],
                             online_data: Dict[str, Any], response: ApiResponse):
        local_config_data = parse_config_update_data(config.update_data.value)

        if not local_config_data:
            config.set(config.update_data, raw_data)
            if config.isLog.value:
                self.logger.info(ui_text(f'获取到更新信息：{online_data}', f'Obtained update information: {online_data}'))

            # 现在 response.data 已经是真正的 ApiData 对象，可以用点号安全调用了
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
            self.get_tips(url=url)
            InfoBar.success(title=ui_text('获取更新成功', 'Update Successful'),
                            content=ui_text("检测到新的 兑换码 活动信息", "New redeem code event information detected"),
                            orient=Qt.Orientation.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=10000,
                            parent=self)
        else:
            if online_data != local_config_data.data.model_dump():
                content = ''
                local_redeem_codes = [
                    code.model_dump()
                    for code in local_config_data.data.redeemCodes
                ]

                if online_data['redeemCodes'] != [] and online_data['redeemCodes'] != local_redeem_codes:
                    new_used_codes = []
                    old_used_codes = config.used_codes.value
                    # 安全遍历数据模型对象
                    for code in response.data.redeemCodes:
                        if code.code in old_used_codes:
                            new_used_codes.append(code.code)
                    config.set(config.used_codes, new_used_codes)
                    content += ' 兑换码 '

                if online_data['updateData'] != local_config_data.data.updateData.model_dump():
                    content += ' 活动信息 '

                if content:
                    if config.isLog.value:
                        self.logger.info(ui_text(f'获取到更新信息：{online_data}', f'Obtained update information: {online_data}'))
                    config.set(config.update_data, raw_data)
                    config.set(config.task_name,
                               response.data.updateData.questName)
                    url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
                    self.get_tips(url=url)
                    InfoBar.success(title=ui_text('获取更新成功', 'Update Successful'),
                                    content=ui_text(f"检测到新的{content}", f"New {content} detected"),
                                    orient=Qt.Orientation.Horizontal,
                                    isClosable=True,
                                    position=InfoBarPosition.TOP_RIGHT,
                                    duration=10000,
                                    parent=self)
                else:
                    self.get_tips()
            else:
                self.get_tips()

    def _handle_update_logic_fallback(self, data, online_data):
        # Fallback 继续沿用之前的纯字典保险策略
        if not config.update_data.value:
            config.set(config.update_data, data)
            if config.isLog.value:
                self.logger.info(f'获取到更新信息：{online_data}')
            catId = online_data["updateData"]["linkCatId"]
            linkId = online_data["updateData"]["linkId"]
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
            self.get_tips(url=url)
            InfoBar.success(title=ui_text('获取更新成功', 'Update Successful'),
                            content=ui_text("检测到新的 兑换码 活动信息", "New redeem code event information detected"),
                            orient=Qt.Orientation.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=10000,
                            parent=self)
        else:
            if not isinstance(config.update_data.value, dict) or 'data' not in config.update_data.value:
                self.logger.error(ui_text('本地配置数据格式不正确，使用在线数据', 'Local configuration data format is incorrect, using online data'))
                config.set(config.update_data, data)
                config.set(config.task_name, online_data["updateData"]["questName"])
                catId = online_data["updateData"]["linkCatId"]
                linkId = online_data["updateData"]["linkId"]
                url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
                self.get_tips(url=url)
                return

            local_data = config.update_data.value["data"]
            if online_data != local_data:
                content = ''
                if online_data['redeemCodes'] != local_data['redeemCodes']:
                    new_used_codes = []
                    old_used_codes = config.used_codes.value
                    for code in online_data['redeemCodes']:
                        if code['code'] in old_used_codes:
                            new_used_codes.append(code['code'])
                    config.set(config.used_codes, new_used_codes)
                    content += ' 兑换码 '
                if online_data['updateData'] != local_data['updateData']:
                    content += ' 活动信息 '

                if content:
                    if config.isLog.value:
                        self.logger.info(ui_text(f'获取到更新信息：{online_data}', f'Obtained update information: {online_data}'))
                    config.set(config.update_data, data)
                    config.set(config.task_name, online_data["updateData"]["questName"])
                    catId = online_data["updateData"]["linkCatId"]
                    linkId = online_data["updateData"]["linkId"]
                    url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
                    self.get_tips(url=url)
                    InfoBar.success(title=ui_text('获取更新成功', 'Update Successful'),
                                    content=ui_text(f"检测到新的{content}", f"New {content} detected"),
                                    orient=Qt.Orientation.Horizontal,
                                    isClosable=True,
                                    position=InfoBarPosition.TOP_RIGHT,
                                    duration=10000,
                                    parent=self)
                else:
                    self.get_tips()
            else:
                self.get_tips()

    def _handle_cloudflare_error(self, error_msg):
        self.logger.error(f'通过cloudflare在线更新出错: {error_msg}')
        self.get_tips()


    def on_select_directory_click(self):
        folder = QFileDialog.getExistingDirectory(self, '选择游戏文件夹', "./")
        if not folder or config.LineEdit_game_directory.value == folder:
            return
        self.ui.LineEdit_game_directory.setText(folder)
        self.ui.LineEdit_game_directory.editingFinished.emit()

    def on_reset_codes_click(self):
        content = ''
        if self.ui.TextEdit_import_codes.toPlainText():
            self.ui.TextEdit_import_codes.setText("")
        if config.import_codes.value:
            config.set(config.import_codes, [])
            content += ' 导入 '
        if config.used_codes.value:
            config.set(config.used_codes, [])
            content += ' 已使用 '

        InfoBar.success(title=ui_text('重置成功', 'Reset Successful'),
                        content=ui_text(f"已重置 导入展示 {content}", f"Successfully reset import and display {content}"),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self)

    def on_import_codes_click(self):

        def filter_codes(text):
            lines = text.splitlines()
            result = []
            for line in lines:
                stripped_line = line.strip()
                if ':' in stripped_line:
                    result.append(stripped_line.split(':')[-1])
                elif '：' in stripped_line:
                    result.append(stripped_line.split('：')[-1])
                else:
                    result.append(stripped_line)
            self.ui.TextEdit_import_codes.setText("\n".join(result))
            return result

        if self._is_dialog_open:
            return

        self._is_dialog_open = True
        try:
            w = CustomMessageBox(self, "导入兑换码", "text_edit")
            w.content.setEnabled(True)
            w.content.setPlaceholderText(ui_text("一行一个兑换码", "One code per line"))
            if w.exec():
                raw_codes = w.content.toPlainText()
                codes = filter_codes(raw_codes)
                config.set(config.import_codes, codes)
        finally:
            self._is_dialog_open = False

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
            result = launch_game_with_guard(logger=self.logger)
            if not result.get("ok"):
                self.logger.error(result.get("error", "启动游戏失败"))
                self._set_launch_pending_state(False)
                return

            self.launch_process = result.get("process")
            self.launch_deadline = time.time() + 90
            self.check_game_window_timer.start(500)
            self._set_launch_pending_state(True)
        except Exception as e:
            self.logger.error(ui_text(f'出现报错: {e}', f'Error occurred: {e}'))
            self._set_launch_pending_state(False)

    def _is_game_window_open(self):
        return is_exist_snowbreak()

    def _clear_launch_watch_state(self):
        self.check_game_window_timer.stop()
        self.launch_deadline = 0.0
        self.launch_process = None

    def _stop_running_guard(self):
        self.running_game_guard_timer.stop()

    def _connect_to_slot(self):
        self.ui.PushButton_start.clicked.connect(self.on_start_button_click)
        self.ui.PrimaryPushButton_path_tutorial.clicked.connect(
            self.on_path_tutorial_click)
        self.ui.PushButton_select_all.clicked.connect(
            lambda: select_all(self.ui.SimpleCardWidget_option))
        self.ui.PushButton_no_select.clicked.connect(
            lambda: no_select(self.ui.SimpleCardWidget_option))
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

        self.scheduler.tasks_due.connect(self._on_scheduled_tasks_due)
        self.scheduler.sequence_updated.connect(self._auto_adjust_after_use_action)

        signalBus.sendHwnd.connect(self.set_hwnd)

        signalBus.globalTaskStateChanged.connect(self._on_global_state_changed)
        signalBus.globalStopRequest.connect(self._on_global_stop_request)
        self._connect_to_save_changed()

    def _on_global_state_changed(self, is_running: bool, zh_name: str, en_name: str, source: str):
        if source == "daily": return # 忽略自己发出的信号

        # 记录是否有外部任务在运行
        self.is_global_running = is_running

        if is_running:
            self.set_checkbox_enable(False)
            btn_text = f"停止 {zh_name} (F8)" if not self._is_non_chinese_ui else f"Stop {en_name} (F8)"
            self.ui.PushButton_start.setText(btn_text)
        else:
            self.set_checkbox_enable(True)
            self.ui.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))

            # 【新增：排队唤醒机制】如果外部任务结束了，并且我们有积压的排队任务在等，立刻唤醒执行！
            if getattr(self, '_waiting_for_external_to_finish', False):
                self._waiting_for_external_to_finish = False

                # 检查积压的队列里还有没有任务
                pending_tasks = getattr(self, 'tasks_to_run', [])
                if pending_tasks and not self.is_running:
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
        self.is_launch_pending = bool(pending)
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
        game_opened = is_exist_snowbreak()
        should_launch_game = not game_opened and config.CheckBox_open_game_directly.value

        final_tasks = list(tasks_to_run)

        # Determine if task_login is required and enforce it at the start of the list
        if should_launch_game or "task_login" in final_tasks:
            # Remove all instances of task_login to avoid duplicates, then add one at the start.
            final_tasks = [t for t in final_tasks if t != "task_login"]
            final_tasks.insert(0, "task_login")

        self.tasks_to_run = final_tasks

        if not self.tasks_to_run:
            return

        if should_launch_game:
            self.open_game_directly()
        else:
            # If game isn't open and we are not launching it, issue a warning.
            if not game_opened:
                self.logger.warning(self._ui_text("⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。", "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!"))
            self.after_start_button_click(self.tasks_to_run)

    def handle_start(self, str_flag):
        try:
            if str_flag == 'start':
                self.is_running = True
                self._set_launch_pending_state(False)
                self.ui.PushButton_start.setText(self._ui_text("停止 (F8)", "Stop (F8)"))
                signalBus.globalTaskStateChanged.emit(True, "日常任务", "Daily Tasks", "daily")

                for tid, task_item in self.task_widget_map.items():
                    if tid in getattr(self, 'tasks_to_run', []):
                        if hasattr(task_item, 'set_task_state'):
                            task_item.set_task_state('queued')
                    else:
                        if hasattr(task_item, 'lock_ui_for_execution'):
                            task_item.lock_ui_for_execution()

                if not self.running_game_guard_timer.isActive():
                    self.running_game_guard_timer.start(1000)

            elif str_flag in ['end', 'no_auto', 'interrupted']:
                self.is_running = False
                self._set_launch_pending_state(False)
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)

                # 不论任何情况，停止后按钮直接回到“立即执行”，因为挂机是隐形的
                self.ui.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))

                self._is_running_solo_flag = False
                self._is_scheduled_run_flag = False

                self._auto_adjust_after_use_action()

                signalBus.globalTaskStateChanged.emit(False, "", "", "daily")

                if str_flag == 'end':
                    self.after_finish()
        except Exception as e:
            self.logger.error(ui_text(f'处理任务状态变更时出现异常：{e}', f'Error occurred while handling task state change: {e}'))
            self.is_running = False
            self.set_checkbox_enable(True)
            self._auto_adjust_after_use_action()
            # 异常时也要广播释放
            signalBus.globalTaskStateChanged.emit(False, "", "", "daily")

    def _on_task_play_clicked(self, task_id: str):
        if self.is_running or self.is_launch_pending:
            self.logger.info(
                self._ui_text("已手动中止当前任务", "Task manually stopped"))
            if self.is_launch_pending:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)

            if self.start_thread is not None and self.start_thread.isRunning():
                self.start_thread.stop(reason=self._ui_text(
                    '用户点击了手动终止按钮', 'User clicked stop button'))
        else:
            meta = TASK_REGISTRY.get(task_id, {})
            task_name = meta.get("en_name", task_id) if getattr(
                self, '_is_non_chinese_ui', False) else meta.get(
                    "zh_name", task_id)
            self.logger.info(
                self._ui_text(f"开始单独执行任务: {task_name}",
                              f"Force running task: {task_name}"))

            tasks_to_run = [task_id]
            self._is_running_solo_flag = True
            self._initiate_task_run(tasks_to_run)

    def _on_task_play_from_here_clicked(self, start_task_id: str):
        if self.is_running or self.is_launch_pending:
            self._on_task_play_clicked(start_task_id)
            return

        self.logger.info(
            self._ui_text(f"开始从指定位置向下批量执行已勾选任务",
                          f"Force running checked tasks from here"))

        tasks_to_run = []
        start_adding = False

        ordered_task_ids = self.ui.taskListWidget.get_task_order()

        for task_id in ordered_task_ids:
            if task_id == start_task_id:
                start_adding = True

            if start_adding:
                task_item = self.task_widget_map.get(task_id)
                is_checked = bool(
                    task_item.checkbox.isChecked()) if task_item else False
                if is_checked:
                    tasks_to_run.append(task_id)

        if not tasks_to_run:
            self.logger.warning(
                self._ui_text("⚠️ 下方没有已勾选的任务可执行！",
                              "⚠️ No checked tasks found below!"))
            return

        self._initiate_task_run(tasks_to_run)

    def _on_copy_single_rule_to_checked(self, rule_data: dict):
        if not rule_data:
            return

        # 1. 找出所有已勾选的任务 ID
        checked_task_ids = []
        ordered_ids = self.ui.taskListWidget.get_task_order()
        for tid in ordered_ids:
            item = self.task_widget_map.get(tid)
            if item and item.checkbox.isChecked():
                checked_task_ids.append(tid)

        if not checked_task_ids:
            InfoBar.warning(
                title=ui_text("无生效目标", "No Target Selected"),
                content=ui_text("请先在左侧列表中勾选需要应用此规则的任务", "Please check tasks in the left list first"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )
            return

        # 2. 读取当前序列
        sequence = self.scheduler.get_task_sequence()

        # 3. 遍历覆盖（仅针对勾选的任务，并确保不给 task_login 加计划）
        for task_cfg in sequence:
            if task_cfg["id"] in checked_task_ids and task_cfg["id"] != "task_login":
                # 开启任务的计划使能开关
                task_cfg["use_periodic"] = True

                # 获取该任务原有的执行规则列表
                existing_rules = task_cfg.get("execution_config", [])
                if not isinstance(existing_rules, list):
                    existing_rules = []

                # 检查是否已经存在完全一模一样的规则，避免重复添加
                is_duplicate = False
                for er in existing_rules:
                    if er.get("type") == rule_data["type"] and \
                       er.get("day") == rule_data["day"] and \
                       er.get("time") == rule_data["time"]:
                        # 如果类型、天数、时间都一样，只更新执行次数
                        er["max_runs"] = rule_data["max_runs"]
                        is_duplicate = True
                        break

                if not is_duplicate:
                    existing_rules.append(copy.deepcopy(rule_data))

                task_cfg["execution_config"] = existing_rules

        # 4. 保存配置
        self.scheduler.save_task_sequence(sequence)

        # 5. 重新加载当前正在查看的任务的UI（以防当前任务刚好是被勾选的任务，UI需要刷新显示新追加的规则）
        current_task_id = self.ui.shared_scheduling_panel.task_id
        if current_task_id:
            task_cfg = next((item for item in sequence if item.get("id") == current_task_id), None)
            if task_cfg:
                self.ui.shared_scheduling_panel.load_task(current_task_id, task_cfg)

        self._auto_adjust_after_use_action()

        # 6. 成功提示
        rule_desc = f"{rule_data['type']} {rule_data['time']} ({rule_data['max_runs']}次)"
        InfoBar.success(
            title=ui_text("规则下发成功", "Rule Copied Successfully"),
            content=ui_text(f"已将此时间节点追加给 {len(checked_task_ids)} 个已勾选任务\n并自动启用了它们的计划",
                            f"Added this trigger to {len(checked_task_ids)} checked tasks and enabled their schedules"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def check_game_open(self):
        try:
            hwnd = self._is_game_window_open()
            if hwnd:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.info(self._ui_text(f'已检测到游戏窗口：{hwnd}', f'Game window detected: {hwnd}'))
                self.after_start_button_click(getattr(self, 'tasks_to_run',
                                                      []))
                return

            if self.launch_process is not None and self.launch_process.poll(
            ) is not None:
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

            if self.launch_deadline and time.time() > self.launch_deadline:
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
                self.start_thread = StartThread(tasks_to_run, self.logger, self)
                self.start_thread.is_running_signal.connect(self.handle_start)
                self.start_thread.task_completed_signal.connect(self.record_task_completed)
                self.start_thread.task_started_signal.connect(self._on_task_actually_started)
                self.start_thread.task_failed_signal.connect(self.record_task_failed)

                self.start_thread.show_tray_message_signal.connect(self._show_tray_message)

                self.start_thread.start()
            else:
                self.start_thread.stop()
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
        # 尝试复用主窗口的托盘图标（防止多次创建导致系统托盘出现“幽灵图标”）
        main_win = self.window()
        if hasattr(main_win, 'tray_icon') and main_win.tray_icon:
            main_win.tray_icon.showMessage(
                title, content,
                QIcon(os.path.abspath("app/resource/images/logo.ico")), 1000
            )
        else:
            # 如果没获取到主窗口的托盘，临时创建一个（后备方案）
            app = QApplication.instance()
            if app:
                tray_icon = QSystemTrayIcon(QIcon(os.path.abspath("app/resource/images/logo.ico")), app)
                tray_icon.show()
                tray_icon.showMessage(
                    title, content,
                    QIcon(os.path.abspath("app/resource/images/logo.ico")), 1000
                )

    def _guard_running_game_window(self):
        try:
            if not self.is_running:
                self._stop_running_guard()
                return

            if self._is_game_window_open():
                return

            self._stop_running_guard()
            self.logger.warning(self._ui_text('检测到游戏窗口已关闭，正在停止当前自动任务', 'Game window closed, stopping current automatic task'))
            if self.start_thread is not None and self.start_thread.isRunning():
                self.start_thread.stop(reason=self._ui_text(
                    '用户中断：游戏窗口已关闭', 'Interrupted by user: game window closed'))
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
            signalBus.globalStopRequest.emit()
            return

        if self.is_running:
            if self.start_thread and self.start_thread.isRunning():
                self.start_thread.stop(reason="User Stop")
            return

        tasks_to_run = []
        ordered_ids = self.ui.taskListWidget.get_task_order()
        for tid in ordered_ids:
            item = self.task_widget_map.get(tid)
            if item and item.checkbox.isChecked():
                tasks_to_run.append(tid)

        if tasks_to_run:
            self._initiate_task_run(tasks_to_run)
        else:
            InfoBar.error(title="队列为空", content=self._ui_text("请至少勾选一个任务进行立即执行", "Please select at least one task to run immediately"), parent=self)

    def after_finish(self):
        if getattr(self, '_is_running_solo_flag', False):
            self.logger.info(self._ui_text("单独执行完毕，已返回空闲状态...", "Solo execution completed, returned to idle state..."))
            return

        run_mode_idx = self.ui.ComboBox_run_mode.currentIndex()
        end_action_idx = self.ui.ComboBox_end_action.currentIndex()

        # 1. 处理游戏窗口关闭
        # 索引 1: 退出游戏, 3: 退出游戏和代理
        if end_action_idx in [1, 3] and self.game_hwnd:
            self.logger.info(self._ui_text("正在关闭游戏窗口...", "Closing game window..."))
            win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)

        # 2. 处理“安卡小助手”自身的后续动作
        if run_mode_idx == 0:  # 挂机等待
            self._auto_adjust_after_use_action()
            self.logger.info(self._ui_text("所有任务执行完毕，助手已进入挂机监控模式...", "All tasks completed, assistant entered monitoring mode..."))

        elif run_mode_idx == 1:  # 关闭程序
            self.logger.info(self._ui_text("执行完毕，正在退出安卡小助手...", "Execution completed, exiting Anka Assistant..."))
            self.scheduler.stop()

            main_window = self.window()
            if hasattr(main_window, 'quit_app'):
                main_window.quit_app()
            else:
                QApplication.quit()
                os._exit(0)

        elif run_mode_idx == 2:  # 关闭电脑
            self.logger.info(self._ui_text("执行完毕，系统将于60秒后关机...", "Execution completed, system will shut down in 60 seconds..."))
            os.system('shutdown -s -t 60')

            self.scheduler.stop()

    def set_checkbox_enable(self, enable: bool):
        for checkbox in self.ui.findChildren(CheckBox):
            # 保护机制：全局 UI 解锁时，永远不要解锁“登录”选项
            if checkbox.objectName() == "CheckBox_entry_1":
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
        meta = TASK_REGISTRY.get(task_id, {})
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

        meta = TASK_REGISTRY.get(task_id, {})
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
        config_item = getattr(config, widget.objectName(), None)
        if config_item is None:
            return

        if isinstance(widget, CheckBox):
            config.set(config_item, widget.isChecked())
            if widget.objectName() == 'CheckBox_is_use_power':
                self.ui.ComboBox_power_day.setEnabled(widget.isChecked())
        elif isinstance(widget, ComboBox):
            config.set(config_item, widget.currentIndex())
        elif isinstance(widget, SpinBox):
            config.set(config_item, widget.value())
        elif isinstance(widget, LineEdit):
            if 'x1' in widget.objectName() or 'x2' in widget.objectName(
            ) or 'y1' in widget.objectName() or 'y2' in widget.objectName():
                config.set(config_item, int(widget.text()))
            else:
                config.set(config_item, widget.text())

    def save_item_changed(self, index, check_state):
        config.set(getattr(config, f"item_person_{index}", None),
                   False if check_state == 0 else True)

    def save_item2_changed(self, index, check_state):
        config.set(getattr(config, f"item_weapon_{index}", None),
                   False if check_state == 0 else True)

    def get_tips(self, url=None):
        if url:
            tips_dic = get_date_from_api(url)
            if "error" in tips_dic.keys():
                self.logger.error(tips_dic["error"])
                return
            config.set(config.date_tip, tips_dic)
        else:
            if not config.date_tip.value:
                InfoBar.error(title=ui_text('活动日程更新失败', 'Failed to update event schedule'),
                              content=ui_text(f"本地没有存储信息且未获取到url", f"No local information stored and no URL fetched"),
                              orient=Qt.Orientation.Horizontal,
                              isClosable=True,
                              position=InfoBarPosition.TOP_RIGHT,
                              duration=2000,
                              parent=self)
                return
            tips_dic = copy.deepcopy(config.date_tip.value)

        if config.isLog.value:
            self.logger.info(ui_text("获取活动日程成功", "Successfully fetched event schedule"))

        for key, value in tips_dic.items():
            tips_dic[key] = DailyModel.calculate_time_difference(value)

        max_total_days = 1
        for key, value in tips_dic.items():
            days, total_day, status = value
            if status == 0 and total_day > max_total_days:
                max_total_days = total_day

        index = 0
        items_list = []
        try:
            for key, value in tips_dic.items():
                if self.ui.scrollAreaWidgetContents_tips.findChild(
                        BodyLabel, name=f"BodyLabel_tip_{index + 1}"):
                    BodyLabel_tip = self.ui.scrollAreaWidgetContents_tips.findChild(
                        BodyLabel, name=f"BodyLabel_tip_{index + 1}")
                else:
                    BodyLabel_tip = BodyLabel(
                        self.ui.scrollAreaWidgetContents_tips)
                    BodyLabel_tip.setObjectName(f"BodyLabel_tip_{index + 1}")

                if self.ui.scrollAreaWidgetContents_tips.findChild(
                        ProgressBar, name=f"ProgressBar_tip{index + 1}"):
                    ProgressBar_tip = self.ui.scrollAreaWidgetContents_tips.findChild(
                        ProgressBar, name=f"ProgressBar_tip{index + 1}")
                else:
                    ProgressBar_tip = ProgressBar(
                        self.ui.scrollAreaWidgetContents_tips)
                    ProgressBar_tip.setObjectName(
                        f"ProgressBar_tip{index + 1}")

                days, total_day, status = value

                if status == -1:
                    BodyLabel_tip.setText(
                        f"{key} {self._ui_text('已结束', 'finished')}")
                    sort_weight = 99999
                    ProgressBar_tip.setValue(0)
                elif status == 1:
                    BodyLabel_tip.setText(
                        self._ui_text(f"{key} 还有 {days} 天开始",
                                      f"{key} in {days}d(s)"))
                    sort_weight = 10000 + days
                    ProgressBar_tip.setValue(0)
                else:
                    BodyLabel_tip.setText(
                        self._ui_text(f"{key}剩：{days}天",
                                      f"{key}: {days}d(s) left"))
                    sort_weight = days

                    normalized_percent = int((days / max_total_days) * 100)
                    ProgressBar_tip.setValue(normalized_percent)

                items_list.append(
                    [BodyLabel_tip, ProgressBar_tip, sort_weight])
                index += 1

            items_list.sort(key=lambda x: x[2])

            for i in range(len(items_list)):
                self.ui.gridLayout_tips.addWidget(items_list[i][0], i + 1, 0,
                                                  1, 1)
                self.ui.gridLayout_tips.addWidget(items_list[i][1], i + 1, 1,
                                                  1, 1)

        except Exception as e:
            self.logger.error(ui_text(f"更新控件出错：{e}", f"Error occurred while updating controls: {e}"))

    def closeEvent(self, event):
        super().closeEvent(event)
        self.scheduler.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
