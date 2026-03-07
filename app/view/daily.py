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
from utils.ui_utils import get_all_children
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
        "en_name": "Mental Simulation",
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

    def __init__(self, tasks_to_run: list, parent=None):
        super().__init__(parent)
        self.tasks_to_run = tasks_to_run
        self.logger = logger
        self.session = AutomationSession(self.logger)
        self._is_running = True
        self._interrupted_reason = None

    def stop(self, reason=None):
        self._is_running = False
        if reason:
            self._interrupted_reason = reason
            self.logger.warning(f"检测到中断，停止自动任务：{reason}")
        if self.session.auto is not None:
            try:
                self.session.stop()
            except Exception as e:
                self.logger.warning(f"停止自动任务时发生异常，已忽略：{e}")

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
                self.logger.info(f"当前任务：{task_name}")

                self.task_started_signal.emit(task_id)

                module_class = meta["module_class"]
                module = module_class(auto, self.logger)
                module.run()

                if self._is_running:
                    self.task_completed_signal.emit(task_id)

                if not self._is_running:
                    normal_stop_flag = False
                    break

                if config.inform_message.value or '--toast-only' in sys.argv:
                    full_time = auto.calculate_power_time() if auto is not None else None
                    content = f'体力将在 {full_time} 完全恢复' if full_time else "体力计算出错"

                    app = QApplication.instance()
                    if app:
                        tray_icon = QSystemTrayIcon(QIcon(os.path.abspath("app/resource/images/logo.ico")), app)
                        tray_icon.show()
                        tray_icon.showMessage(
                            '已完成勾选任务',
                            content,
                            QIcon(os.path.abspath("app/resource/images/logo.ico")),
                            1000
                        )

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
            self._ui_text('拟境', 'Mental Simulation'),
            self._ui_text('奖励', 'Claim Rewards'),
            self._ui_text('常规训练', 'Operation'),
            self._ui_text('武器培养', 'Weapon'),
            self._ui_text('信源碎片', 'Shard Exchange'),
        ]

        self.person_dic = {
            "角色碎片": "item_person_0",
            "肴": "item_person_1",
            "安卡希雅": "item_person_2",
            "里芙": "item_person_3",
            "辰星": "item_person_4",
            "茉莉安": "item_person_5",
            "芬妮": "item_person_6",
            "芙提雅": "item_person_7",
            "瑟瑞斯": "item_person_8",
            "琴诺": "item_person_9",
            "猫汐尔": "item_person_10",
            "晴": "item_person_11",
            "恩雅": "item_person_12",
            "妮塔": "item_person_13",
        }
        self.person_dic_en = {
            "Character Shards": "item_person_0",
            "Yao": "item_person_1",
            "Acacia": "item_person_2",
            "Lyfe": "item_person_3",
            "Chenxing": "item_person_4",
            "Marian": "item_person_5",
            "Fenny": "item_person_6",
            "Fritia": "item_person_7",
            "Siris": "item_person_8",
            "Cherno": "item_person_9",
            "Mauxir": "item_person_10",
            "Haru": "item_person_11",
            "Enya": "item_person_12",
            "Nita": "item_person_13",
        }
        self.weapon_dic = {
            "武器": "item_weapon_0",
            "彩虹打火机": "item_weapon_1",
            "草莓蛋糕": "item_weapon_2",
            "深海呼唤": "item_weapon_3",
        }
        self.weapon_dic_en = {
            "Weapon": "item_weapon_0",
            "Prismatic Igniter": "item_weapon_1",
            "Strawberry Shortcake": "item_weapon_2",
            "Deep Sea's Call": "item_weapon_3",
        }
        self.person_text_to_key = {**self.person_dic, **self.person_dic_en}
        self.weapon_text_to_key = {**self.weapon_dic, **self.weapon_dic_en}

        self.ui = DailyView(self, is_non_chinese_ui=self._is_non_chinese_ui)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.task_widget_map: Dict[str, TaskItemWidget] = {}
        self._task_sequence_cache: List[Dict[str, Any]] = []
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

        self.redirectOutput(self.ui.textBrowser_log)

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(
            self._guard_running_game_window)

        # 核心：常驻后台心跳，每30秒检查一次
        self.loop_timer = QTimer(self)
        self.loop_timer.timeout.connect(self._check_and_run_loop_tasks)
        self.loop_timer.start(30000)

        self.checkbox_dic = None

        QTimer.singleShot(500, self._on_init_sync)

        if config.checkUpdateAtStartUp.value:
            self.update_online_cloudflare()
        else:
            self.get_tips()

    def _on_init_sync(self):
        self._auto_adjust_after_use_action()
        self._output_schedule_log()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _is_rule_day_matched(self, rule: dict, now: datetime) -> bool:
        """极简日期匹配器：检查今天是否符合执行规则"""
        exec_type = str(rule.get("type", "daily")).lower()

        if exec_type == "每周": exec_type = "weekly"
        elif exec_type == "每月": exec_type = "monthly"
        elif exec_type == "每天": exec_type = "daily"

        if exec_type == "weekly":
            return now.weekday() == int(rule.get("day", 0))
        elif exec_type == "monthly":
            return now.day == int(rule.get("day", 1))

        return True  # 每天都匹配

    def _check_and_run_loop_tasks(self):
        if self.is_running or self.is_launch_pending:
            return

        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        new_tasks_found = []
        sequence_updated = False

        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_id = task_cfg.get("id")

            if not task_cfg.get("use_periodic"):
                continue

            exec_rules = task_cfg.get("execution_config", [])
            for rule in exec_rules:
                if rule.get("time") == current_time_str:
                    if self._is_rule_day_matched(rule, now):
                        rule_progress = task_cfg.get("rule_progress", {})
                        rule_key = f"{rule.get('type')}_{rule.get('day')}_{current_time_str}"
                        prog = rule_progress.get(rule_key, 0)
                        last_trigger_ts = prog.get("last_run", 0) if isinstance(prog, dict) else prog

                        if int(now.timestamp()) - int(last_trigger_ts) > 60:
                            new_tasks_found.append(task_id)

                            if isinstance(prog, dict):
                                prog["last_run"] = int(now.timestamp())
                                rule_progress[rule_key] = prog
                            else:
                                rule_progress[rule_key] = int(now.timestamp())

                            task_cfg["rule_progress"] = rule_progress
                            sequence_updated = True
                            break

        if not new_tasks_found:
            return

        if sequence_updated:
            self._save_task_sequence(sequence)

        if getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False):
            self.logger.info(f"⏰ 到点触发计划: {current_time_str}，正在执行其他任务，已加入队列排队: {new_tasks_found}")
            for tid in new_tasks_found:
                if tid not in self.tasks_to_run:
                    self.tasks_to_run.append(tid)
                    task_item = self.task_widget_map.get(tid)
                    if task_item and hasattr(task_item, 'set_task_state'):
                        task_item.set_task_state('queued')
            return

        self.logger.info(f"⏰ 到点触发计划: {current_time_str}，执行列表: {new_tasks_found}")
        self._is_scheduled_run_flag = True
        tasks_to_run = new_tasks_found

        if "task_login" in tasks_to_run and tasks_to_run[0] != "task_login":
            tasks_to_run.remove("task_login")
            tasks_to_run.insert(0, "task_login")

        game_opened = is_exist_snowbreak()
        if not game_opened:
            if config.CheckBox_open_game_directly.value:
                if "task_login" not in tasks_to_run:
                    tasks_to_run.insert(0, "task_login")
                self.tasks_to_run = tasks_to_run
                self.open_game_directly()
            else:
                self.logger.warning(self._ui_text("⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。", "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!"))
                self.tasks_to_run = tasks_to_run
                self.after_start_button_click(tasks_to_run)
        else:
            self.tasks_to_run = tasks_to_run
            self.after_start_button_click(tasks_to_run)

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
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
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

    def _normalize_task_sequence(self, sequence):
        defaults = copy.deepcopy(config.daily_task_sequence.defaultValue)
        default_by_id = {item["id"]: item for item in defaults}
        normalized = []
        seen = set()

        for item in sequence or []:
            task_id = item.get("id")
            if task_id not in default_by_id:
                continue
            merged = copy.deepcopy(default_by_id[task_id])
            merged.update(item)
            activation_rules = merged.get("activation_config")
            if activation_rules is None:
                activation_rules = merged.get("refresh_config", {}) or {}
            if isinstance(activation_rules, dict):
                activation_rules = [activation_rules]
            if not activation_rules:
                activation_rules = [{
                    "type": "daily",
                    "day": 0,
                    "time": "00:00",
                    "max_runs": 1
                }]
            merged["activation_config"] = activation_rules
            merged.pop("refresh_config", None)

            execution_rules = merged.get("execution_config") or []
            if isinstance(execution_rules, dict):
                execution_rules = [execution_rules]
            if not execution_rules:
                execution_rules = [{
                    "type": "daily",
                    "day": 0,
                    "time": "00:00",
                    "max_runs": 1
                }]
            merged["execution_config"] = execution_rules
            normalized.append(merged)
            seen.add(task_id)

        for item in defaults:
            if item["id"] not in seen:
                normalized.append(copy.deepcopy(item))

        login_task = next((t for t in normalized if t["id"] == "task_login"), None)
        if login_task:
            normalized.remove(login_task)
            login_task["enabled"] = True
            normalized.insert(0, login_task)

        return normalized

    def _auto_adjust_after_use_action(self):
        if getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False):
            return

        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)

        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            task_item = self.task_widget_map.get(task_id)
            if not task_item: continue

            is_checked = bool(task_item.checkbox.isChecked())
            use_periodic = bool(task_cfg.get("use_periodic", False))

            if use_periodic:
                task_item.set_task_state('scheduled', is_enabled=is_checked)
            else:
                if getattr(task_item, 'current_state', 'idle') != 'completed':
                    task_item.set_task_state('idle', is_enabled=is_checked)
                else:
                    task_item.set_task_state('completed', is_enabled=is_checked)

    def _save_task_sequence(self, sequence):
        self._task_sequence_cache = sequence
        config.set(config.daily_task_sequence, copy.deepcopy(sequence))

    def _init_task_list_widgets(self):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        self._save_task_sequence(sequence)

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
            task_item.checkbox.setObjectName(meta["option_key"])
            self.ui.taskListWidget.add_task_item(task_item)
            self.task_widget_map[task_id] = task_item
            setattr(self, meta["option_key"], task_item.checkbox)

    def _sync_task_sequence_from_ui(self):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        task_by_id = {item["id"]: item for item in sequence}

        for task_id, task_item in self.task_widget_map.items():
            if task_id in task_by_id:
                task_by_id[task_id]["enabled"] = task_item.checkbox.isChecked()

        ordered = []
        for task_id in self.ui.taskListWidget.get_task_order():
            if task_id in task_by_id:
                ordered.append(task_by_id.pop(task_id))
        ordered.extend(task_by_id.values())
        self._save_task_sequence(ordered)

    def _load_initial_task_panel(self):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            if task_id in TASK_REGISTRY:
                self._on_task_settings_clicked(task_id)
                break

    def _on_task_order_changed(self, task_id_order: list):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        task_by_id = {item["id"]: item for item in sequence}
        ordered = []
        for task_id in task_id_order:
            if task_id in task_by_id:
                ordered.append(task_by_id.pop(task_id))
        ordered.extend(task_by_id.values())

        # 经过 normalized 格式化，login 会被自动置顶修复
        final_ordered = self._normalize_task_sequence(ordered)
        self._save_task_sequence(final_ordered)

        # 【防御机制】：如果用户硬是把别的任务拖到了第一个，直接刷新列表 UI 让它弹回原位
        if task_id_order and task_id_order[0] != "task_login":
            self._init_task_list_widgets()

    def _on_task_settings_clicked(self, task_id: str):
        meta = TASK_REGISTRY.get(task_id)
        if not meta:
            return

        page_index = meta.get("ui_page_index")
        if page_index is not None:
            self.set_current_index(page_index)

        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        task_cfg = next(
            (item for item in sequence if item.get("id") == task_id), None)
        if task_cfg is None:
            task_cfg = copy.deepcopy({
                "id":
                task_id,
                "enabled":
                True,
                "use_periodic":
                False,
                "activation_config": [{
                    "type": "daily",
                    "day": 0,
                    "time": "00:00",
                    "max_runs": 1
                }],
                "execution_config": [{
                    "type": "daily",
                    "day": 0,
                    "time": "00:00",
                    "max_runs": 1
                }],
                "last_run":
                0,
            })
            sequence.append(task_cfg)
            self._save_task_sequence(sequence)

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
                self.logger.error('通过cloudflare在线更新出错: 返回数据格式不正确')
                self.get_tips()
                return

            online_data = data["data"]
            required_fields = ['updateData', 'redeemCodes', 'version']
            update_data_fields = ['linkCatId', 'linkId', 'questName']

            for field in required_fields:
                if field not in online_data:
                    self.logger.error(f'通过cloudflare在线更新出错: 缺少必要字段 {field}')
                    self.get_tips()
                    return

            if 'updateData' in online_data:
                for field in update_data_fields:
                    if field not in online_data['updateData']:
                        self.logger.error(
                            f'通过cloudflare在线更新出错: updateData缺少必要字段 {field}')
                        self.get_tips()
                        return

            try:
                # 【核心修复】：不要用 ApiResponse(**data)，改用你写好的 from_dict 进行深层转换！
                response = ApiResponse.from_dict(data)
                self._handle_update_logic(data, online_data, response)
            except Exception as e:
                self.logger.error(f'解析API响应数据时出错: {str(e)}')
                traceback.print_exc()
                self._handle_update_logic_fallback(data, online_data)
        except Exception as e:
            self.logger.error(f'处理Cloudflare数据时出错: {str(e)}')
            self.get_tips()

    def _handle_update_logic(self, raw_data: Dict[str, Any],
                             online_data: Dict[str, Any], response: ApiResponse):
        local_config_data = parse_config_update_data(config.update_data.value)

        if not local_config_data:
            config.set(config.update_data, raw_data)
            if config.isLog.value:
                self.logger.info(f'获取到更新信息：{online_data}')

            # 现在 response.data 已经是真正的 ApiData 对象，可以用点号安全调用了
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
            self.get_tips(url=url)
            InfoBar.success(title='获取更新成功',
                            content="检测到新的 兑换码 活动信息",
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
                        self.logger.info(f'获取到更新信息：{online_data}')
                    config.set(config.update_data, raw_data)
                    config.set(config.task_name,
                               response.data.updateData.questName)
                    url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
                    self.get_tips(url=url)
                    InfoBar.success(title='获取更新成功',
                                    content=f"检测到新的{content}",
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
            InfoBar.success(title='获取更新成功',
                            content="检测到新的 兑换码 活动信息",
                            orient=Qt.Orientation.Horizontal,
                            isClosable=True,
                            position=InfoBarPosition.TOP_RIGHT,
                            duration=10000,
                            parent=self)
        else:
            if not isinstance(config.update_data.value, dict) or 'data' not in config.update_data.value:
                self.logger.error('本地配置数据格式不正确，使用在线数据')
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
                        self.logger.info(f'获取到更新信息：{online_data}')
                    config.set(config.update_data, data)
                    config.set(config.task_name, online_data["updateData"]["questName"])
                    catId = online_data["updateData"]["linkCatId"]
                    linkId = online_data["updateData"]["linkId"]
                    url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
                    self.get_tips(url=url)
                    InfoBar.success(title='获取更新成功',
                                    content=f"检测到新的{content}",
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

        InfoBar.success(title='重置成功',
                        content=f"已重置 导入展示 {content}",
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
            w.content.setPlaceholderText("一行一个兑换码")
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
                        content=f"点击“开始”按钮时{action}自动启动游戏",
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
            self.logger.error(f'出现报错: {e}')
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
        signalBus.sendHwnd.connect(self.set_hwnd)
        self._connect_to_save_changed()

    def _on_task_checkbox_changed(self, task_id: str, is_checked: bool):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["enabled"] = bool(is_checked)
                break
        self._save_task_sequence(sequence)
        self._on_task_settings_clicked(task_id)
        self._auto_adjust_after_use_action()

    def _on_shared_config_changed(self, task_id: str, new_config: dict):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
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

        self._save_task_sequence(sequence)
        self._auto_adjust_after_use_action()

    def _on_toggle_all_cycles_clicked(self, enable: bool):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_cfg["use_periodic"] = enable

        self._save_task_sequence(sequence)
        if getattr(self.ui, 'shared_scheduling_panel', None):
            self.ui.shared_scheduling_panel.enable_checkbox.blockSignals(True)
            self.ui.shared_scheduling_panel.enable_checkbox.setChecked(enable)
            self.ui.shared_scheduling_panel.enable_checkbox.blockSignals(False)

        self._auto_adjust_after_use_action()

    def _set_launch_pending_state(self, pending: bool):
        self.is_launch_pending = bool(pending)
        if self.is_launch_pending:
            self.set_checkbox_enable(False)
            self.ui.PushButton_start.setText(self._ui_text("停止", "Stop"))

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
            self.ui.PushButton_start.setText(
                self._ui_text("立即执行", "Execute Now"))
            self._auto_adjust_after_use_action()

    def handle_start(self, str_flag):
        try:
            if str_flag == 'start':
                self.is_running = True
                self._set_launch_pending_state(False)
                self.ui.PushButton_start.setText(self._ui_text("停止", "Stop"))

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

                # 【核心修改】不论任何情况，停止后按钮直接回到“立即执行”，因为挂机是隐形的
                self.ui.PushButton_start.setText(self._ui_text("立即执行", "Execute Now"))

                self._is_running_solo_flag = False
                self._is_scheduled_run_flag = False

                self._auto_adjust_after_use_action()

                if str_flag == 'end':
                    self.after_finish()
        except Exception as e:
            self.logger.error(f'处理任务状态变更时出现异常：{e}')
            self.is_running = False
            self.set_checkbox_enable(True)
            self._auto_adjust_after_use_action()

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
                self._ui_text(f"▶️ 开始单独执行任务: {task_name}",
                              f"▶️ Force running task: {task_name}"))

            tasks_to_run = [task_id]
            self._is_running_solo_flag = True
            self.tasks_to_run = tasks_to_run

            # 【智能拉起决策】
            game_opened = is_exist_snowbreak()
            if not game_opened:
                if config.CheckBox_open_game_directly.value:
                    if "task_login" not in tasks_to_run:
                        tasks_to_run.insert(0, "task_login")
                    self.tasks_to_run = tasks_to_run
                    self.open_game_directly()
                else:
                    self.logger.warning(
                        self._ui_text(
                            "⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。",
                            "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!"
                        ))
                    self.tasks_to_run = tasks_to_run
                    self.after_start_button_click(tasks_to_run)
            else:
                self.tasks_to_run = tasks_to_run
                self.after_start_button_click(tasks_to_run)

    def _on_task_play_from_here_clicked(self, start_task_id: str):
        if self.is_running or self.is_launch_pending:
            self._on_task_play_clicked(start_task_id)
            return

        self.logger.info(
            self._ui_text(f"⏬ 开始从指定位置向下批量执行已勾选任务",
                          f"⏬ Force running checked tasks from here"))

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

        self.tasks_to_run = tasks_to_run

        if "task_login" in tasks_to_run and tasks_to_run[0] != "task_login":
            tasks_to_run.remove("task_login")
            tasks_to_run.insert(0, "task_login")

        # 【智能拉起决策】
        game_opened = is_exist_snowbreak()
        if not game_opened:
            if config.CheckBox_open_game_directly.value:
                if "task_login" not in tasks_to_run:
                    tasks_to_run.insert(0, "task_login")
                self.tasks_to_run = tasks_to_run
                self.open_game_directly()
            else:
                self.logger.warning(
                    self._ui_text(
                        "⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！若稍后报错未找到句柄，请勾选该功能或手动启动游戏。",
                        "⚠️ Game is not running and 'Auto open game' is OFF. This may cause handle errors!"
                    ))
                self.tasks_to_run = tasks_to_run
                self.after_start_button_click(tasks_to_run)
        else:
            self.tasks_to_run = tasks_to_run
            self.after_start_button_click(tasks_to_run)

    def check_game_open(self):
        try:
            hwnd = self._is_game_window_open()
            if hwnd:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.info(f'已检测到游戏窗口：{hwnd}')
                self.after_start_button_click(getattr(self, 'tasks_to_run',
                                                      []))
                return

            if self.launch_process is not None and self.launch_process.poll(
            ) is not None:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.warning('启动流程已中断：检测到游戏进程退出，已取消本次自动任务')
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
                self.logger.warning('等待游戏窗口超时，已取消本次自动任务')
                InfoBar.warning(title=self._ui_text('等待超时', 'Launch timeout'),
                                content=self._ui_text(
                                    '已停止后续任务', 'Pending tasks cancelled.'),
                                orient=Qt.Orientation.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP_RIGHT,
                                duration=4000,
                                parent=self)
        except Exception as e:
            self.logger.error(f'检测游戏启动状态时出现异常：{e}')
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
                self.start_thread = StartThread(tasks_to_run, self)
                self.start_thread.is_running_signal.connect(self.handle_start)
                self.start_thread.task_completed_signal.connect(
                    self.record_task_completed)
                self.start_thread.task_started_signal.connect(
                    self._on_task_actually_started)

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

    def _guard_running_game_window(self):
        try:
            if not self.is_running:
                self._stop_running_guard()
                return

            if self._is_game_window_open():
                return

            self._stop_running_guard()
            self.logger.warning('检测到游戏窗口已关闭，正在停止当前自动任务')
            if self.start_thread is not None and self.start_thread.isRunning():
                self.start_thread.stop(reason=self._ui_text(
                    '用户中断：游戏窗口已关闭', 'Interrupted by user: game window closed'))
        except Exception as e:
            self.logger.error(f'运行中窗口守护检测异常：{e}')
            self._stop_running_guard()

    def start_from_homepage(self):
        """专供首页快捷卡片调用：如果已经在运行，则什么都不做，绝不终止任务"""
        if self.is_running or self.is_launch_pending:
            self.logger.info("任务已在运行，忽略首页启动请求。")
            return

        # 如果空闲，则复用普通的立即执行逻辑
        self.on_start_button_click()

    def on_start_button_click(self):
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
            if "task_login" in tasks_to_run and tasks_to_run[0] != "task_login":
                tasks_to_run.remove("task_login")
                tasks_to_run.insert(0, "task_login")

            game_opened = is_exist_snowbreak()
            if not game_opened:
                if config.CheckBox_open_game_directly.value:
                    if "task_login" not in tasks_to_run:
                        tasks_to_run.insert(0, "task_login")
                    self.tasks_to_run = tasks_to_run
                    self.open_game_directly()
                else:
                    self.logger.warning(self._ui_text("⚠️ 检测到游戏未运行，且未开启【自动打开游戏】！", "⚠️ Game is not running and 'Auto open game' is OFF."))
                    self.tasks_to_run = tasks_to_run
                    self.after_start_button_click(tasks_to_run)
            else:
                self.tasks_to_run = tasks_to_run
                self.after_start_button_click(tasks_to_run)
        else:
            InfoBar.error(title="队列为空", content="请至少勾选一个任务进行立即执行", parent=self)

    def after_finish(self):
        if getattr(self, '_is_running_solo_flag', False):
            self.logger.info("单独执行完毕，不触发全局后置动作。")
            return

        run_mode_idx = self.ui.ComboBox_run_mode.currentIndex()
        end_action_idx = self.ui.ComboBox_end_action.currentIndex()

        if end_action_idx in [1, 3] and self.game_hwnd:
            win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)

        # 【核心修改】调整新下拉菜单对应的索引处理
        if run_mode_idx == 0:  # 0变成了“挂机等待” (原先是无动作)
            self._auto_adjust_after_use_action()
            self.logger.info("轮次执行完毕，后台持续监控计划时间点中...")
        elif run_mode_idx == 1:  # 关闭程序
            if end_action_idx in [2, 3]: self.parent.close()
            return
        elif run_mode_idx == 2:  # 关闭电脑
            os.system('shutdown -s -t 60')
            self.parent.close()

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

    def record_task_completed(self, task_id: str):
        sequence = self._normalize_task_sequence(
            config.daily_task_sequence.value)

        meta = TASK_REGISTRY.get(task_id, {})
        task_name = meta.get("en_name", task_id) if getattr(
            self, '_is_non_chinese_ui', False) else meta.get(
                "zh_name", task_id)

        # 简单更新该任务的总体最后完成时间戳
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["last_run"] = int(time.time())
                break

        success_msg = f"✨ Task [{task_name}] completed!" if getattr(
            self, '_is_non_chinese_ui', False) else f"✨ {task_name} 执行完毕！"
        self.logger.info(success_msg)

        # UI 状态机置为已完成（绿色打勾）
        task_item = self.task_widget_map.get(task_id)
        if task_item and hasattr(task_item, 'set_task_state'):
            task_item.set_task_state('completed')

            # 【系统级检查修复】：如果全局队列还在运行（其他任务还在排队或执行），必须立刻把刚完成的任务重新软锁定！
            if getattr(self, 'is_running', False) or getattr(self, 'is_launch_pending', False):
                if hasattr(task_item, 'lock_ui_for_execution'):
                    task_item.lock_ui_for_execution()

        self._save_task_sequence(sequence)

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
                InfoBar.error(title='活动日程更新失败',
                              content=f"本地没有存储信息且未获取到url",
                              orient=Qt.Orientation.Horizontal,
                              isClosable=True,
                              position=InfoBarPosition.TOP_RIGHT,
                              duration=2000,
                              parent=self)
                return
            tips_dic = copy.deepcopy(config.date_tip.value)

        if config.isLog.value:
            self.logger.info("获取活动日程成功")

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
            self.logger.error(f"更新控件出错：{e}")

    def closeEvent(self, event):
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
