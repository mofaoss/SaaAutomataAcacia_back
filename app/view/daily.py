import copy
import logging
import os
import re
import sys
import time
import traceback
from datetime import datetime
from functools import partial
from typing import Dict, Any, List

import win32con
import win32gui
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import QFrame, QWidget, QTreeWidgetItemIterator, QFileDialog, QVBoxLayout
from qfluentwidgets import FluentIcon as FIF, InfoBar, InfoBarPosition, CheckBox, ComboBox, LineEdit, \
    BodyLabel, ProgressBar, FlyoutView, Flyout, SpinBox
from win11toast import toast

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
        "zh_name": "常规教学",
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
        """
        通过给入终止时间获取剩余时间差和状态
        :param date_due: 持续时间，格式'03.06-04.17'
        :return: (days, total_day, status)
                 status: 0 正在进行, 1 未开始, -1 已结束
                 days: 正在进行返回剩余天数，未开始返回距离开始的天数，已结束返回0
                 total_day: 该活动的总持续天数（用于统一标尺）
        """
        current_year = datetime.now().year
        start_date_str, end_date_str = date_due.split('-')
        start_time = datetime.strptime(f"{current_year}.{start_date_str}", "%Y.%m.%d")
        end_time = datetime.strptime(f"{current_year}.{end_date_str}", "%Y.%m.%d")

        # 跨年处理
        if end_time < start_time:
            end_time = datetime.strptime(f"{current_year + 1}.{end_date_str}", "%Y.%m.%d")

        # 抹平具体的时分秒，避免时间差因为小时原因少算一天
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total_day = (end_time - start_time).days + 1

        if now < start_time:
            # 未开始
            days_to_start = (start_time - now).days
            return days_to_start, total_day, 1
        elif now > end_time:
            # 已结束
            return 0, total_day, -1
        else:
            # 正在进行
            days_remaining = (end_time - now).days + 1
            return days_remaining, total_day, 0

# ==========================================
# 线程与后台任务类保持不变
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

    # 1. 接收的参数改为 tasks_to_run 列表
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

            # 2. 直接遍历排好序的任务 ID
            for task_id in self.tasks_to_run:
                if not self._is_running:
                    normal_stop_flag = False
                    break

                meta = TASK_REGISTRY.get(task_id)
                if not meta:
                    continue

                task_name = meta["en_name"] if is_non_chinese_ui_language() else meta["zh_name"]
                self.logger.info(f"当前任务：{task_name}")

                module_class = meta["module_class"]
                module = module_class(auto, self.logger)
                module.run()

                if not self._is_running:
                    normal_stop_flag = False
                    break

            if config.inform_message.value or '--toast-only' in sys.argv:
                def empty_func(args): pass
                full_time = auto.calculate_power_time() if auto is not None else None
                content = f'体力将在 {full_time} 完全恢复' if full_time else "体力计算出错"
                toast('已完成勾选任务', content, on_dismissed=empty_func, icon=os.path.abspath("app/resource/images/logo.ico"))
        except Exception as e:
            ocr.stop_ocr()
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
        checkbox.setChecked(False)

# ==========================================
# Controller 层：负责连接视图与模型，处理用户交互和业务逻辑
# ==========================================
class Daily(QFrame, BaseInterface):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        BaseInterface.__init__(self)  # 正确初始化 BaseInterface

        self._is_non_chinese_ui = is_non_chinese_ui_language()

        # 定义翻译字典
        self.setting_name_list = [
            self._ui_text('登录', 'Login'), self._ui_text('福利', 'Supplies'),
            self._ui_text('商店', 'Shop'), self._ui_text('体力', 'Stamina'),
            self._ui_text('碎片', 'Shards'), self._ui_text('拟境', 'Mental Simulation'),
            self._ui_text('奖励', 'Claim Rewards'),
            self._ui_text('常规教学', 'Operation'),
            self._ui_text('武器培养', 'Weapon'),
            self._ui_text('信源碎片', 'Shard Exchange'),
        ]

        self.person_dic = {
            "角色碎片": "item_person_0", "肴": "item_person_1", "安卡希雅": "item_person_2",
            "里芙": "item_person_3", "辰星": "item_person_4", "茉莉安": "item_person_5",
            "芬妮": "item_person_6", "芙提雅": "item_person_7", "瑟瑞斯": "item_person_8",
            "琴诺": "item_person_9", "猫汐尔": "item_person_10", "晴": "item_person_11",
            "恩雅": "item_person_12", "妮塔": "item_person_13",
        }
        self.person_dic_en = {
            "Character Shards": "item_person_0", "Yao": "item_person_1", "Acacia": "item_person_2",
            "Lyfe": "item_person_3", "Chenxing": "item_person_4", "Marian": "item_person_5",
            "Fenny": "item_person_6", "Fritia": "item_person_7", "Siris": "item_person_8",
            "Cherno": "item_person_9", "Mauxir": "item_person_10", "Haru": "item_person_11",
            "Enya": "item_person_12", "Nita": "item_person_13",
        }
        self.weapon_dic = {
            "武器": "item_weapon_0", "彩虹打火机": "item_weapon_1",
            "草莓蛋糕": "item_weapon_2", "深海呼唤": "item_weapon_3",
        }
        self.weapon_dic_en = {
            "Weapon": "item_weapon_0", "Prismatic Igniter": "item_weapon_1",
            "Strawberry Shortcake": "item_weapon_2", "Deep Sea's Call": "item_weapon_3",
        }
        self.person_text_to_key = {**self.person_dic, **self.person_dic_en}
        self.weapon_text_to_key = {**self.weapon_dic, **self.weapon_dic_en}

        # 挂载 View 视图层
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

        self.select_person = TreeFrame_person(parent=self.ui.ScrollArea, enableCheck=True, is_non_chinese_ui=self._is_non_chinese_ui)
        self.select_weapon = TreeFrame_weapon(parent=self.ui.ScrollArea, enableCheck=True, is_non_chinese_ui=self._is_non_chinese_ui)

        self.game_hwnd = None
        self.start_thread = None
        self.launch_process = None
        self.launch_deadline = 0.0
        self.is_launch_pending = False
        self._is_dialog_open = False

        self._initWidget()
        self._connect_to_slot()

        # 继承自 BaseInterface 的日志重定向
        self.redirectOutput(self.ui.textBrowser_log)

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(self._guard_running_game_window)
        self.checkbox_dic = None

        if config.checkUpdateAtStartUp.value:
            self.update_online_cloudflare()
        else:
            self.get_tips()

    def __getattr__(self, item):
        """过渡方案：允许 Controller 暂时像以前一样直接访问 View 里的 UI 控件"""
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _initWidget(self):

        self.ui.PopUpAniStackedWidget.setCurrentIndex(0)
        self.ui.TitleLabel_setting.setText(self._ui_text("设置", "Settings") + "-" + self.setting_name_list[self.ui.PopUpAniStackedWidget.currentIndex()])

        self.ui.gridLayout.addWidget(self.select_person, 1, 0)
        self.ui.gridLayout.addWidget(self.select_weapon, 2, 0)

        self._load_config()
        self._sync_task_sequence_from_ui()
        self._load_initial_task_panel()

        self.ui.ComboBox_power_day.setEnabled(self.ui.CheckBox_is_use_power.isChecked())
        self.ui.PushButton_select_directory.setEnabled(self.ui.CheckBox_open_game_directly.isChecked())

        StyleSheet.HOME_INTERFACE.apply(self)
        self.ui.ScrollArea.enableTransparentBackground()
        self.ui.ScrollArea_tips.enableTransparentBackground()

        # 调整日程面板布局
        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget)
        self.ui.gridLayout_2.removeWidget(self.ui.SimpleCardWidget_tips)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget, 0, 2, 1, 1)
        self.ui.gridLayout_2.addWidget(self.ui.SimpleCardWidget_tips, 1, 2, 1, 1)

    def _connect_to_slot(self):
        self.ui.PushButton_start.clicked.connect(self.on_start_button_click)
        self.ui.PrimaryPushButton_path_tutorial.clicked.connect(self.on_path_tutorial_click)
        self.ui.PushButton_select_all.clicked.connect(lambda: select_all(self.ui.SimpleCardWidget_option))
        self.ui.PushButton_no_select.clicked.connect(lambda: no_select(self.ui.SimpleCardWidget_option))
        self.ui.PushButton_select_directory.clicked.connect(self.on_select_directory_click)
        self.ui.PrimaryPushButton_import_codes.clicked.connect(self.on_import_codes_click)
        self.ui.PushButton_reset_codes.clicked.connect(self.on_reset_codes_click)

        for task_id, task_item in self.task_widget_map.items():
            task_item.settings_clicked.connect(self._on_task_settings_clicked)
            task_item.checkbox_state_changed.connect(self._on_task_checkbox_changed)

        self.ui.taskListWidget.orderChanged.connect(self._on_task_order_changed)
        self.ui.shared_scheduling_panel.config_changed.connect(self._on_shared_config_changed)
        self.ui.CheckBox_open_game_directly.stateChanged.connect(self.change_auto_open)
        signalBus.sendHwnd.connect(self.set_hwnd)
        self._connect_to_save_changed()

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
                activation_rules = [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}]
            merged["activation_config"] = activation_rules
            merged.pop("refresh_config", None)

            execution_rules = merged.get("execution_config") or []
            if isinstance(execution_rules, dict):
                execution_rules = [execution_rules]
            if not execution_rules:
                execution_rules = [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}]
            merged["execution_config"] = execution_rules
            normalized.append(merged)
            seen.add(task_id)

        for item in defaults:
            if item["id"] not in seen:
                normalized.append(copy.deepcopy(item))

        return normalized

    def _save_task_sequence(self, sequence):
        self._task_sequence_cache = sequence
        config.set(config.daily_task_sequence, sequence)

    def _init_task_list_widgets(self):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
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
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
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
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            if task_id in TASK_REGISTRY:
                self._on_task_settings_clicked(task_id)
                break

    def _on_task_checkbox_changed(self, task_id: str, is_checked: bool):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        for task_cfg in sequence:
            if task_cfg.get("id") == task_id:
                task_cfg["enabled"] = bool(is_checked)
                break
        self._save_task_sequence(sequence)

    def _on_task_order_changed(self, task_id_order: list):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        task_by_id = {item["id"]: item for item in sequence}
        ordered = []
        for task_id in task_id_order:
            if task_id in task_by_id:
                ordered.append(task_by_id.pop(task_id))
        ordered.extend(task_by_id.values())
        self._save_task_sequence(ordered)

    def _on_task_settings_clicked(self, task_id: str):
        meta = TASK_REGISTRY.get(task_id)
        if not meta:
            return

        page_index = meta.get("ui_page_index")
        if page_index is not None:
            self.set_current_index(page_index)

        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        task_cfg = next((item for item in sequence if item.get("id") == task_id), None)
        if task_cfg is None:
            task_cfg = copy.deepcopy({
                "id": task_id,
                "enabled": True,
                "use_periodic": True,
                "activation_config": [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}],
                "execution_config": [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}],
                "last_run": 0,
            })
            sequence.append(task_cfg)
            self._save_task_sequence(sequence)

        self.ui.shared_scheduling_panel.load_task(task_id, task_cfg)

    def _on_shared_config_changed(self, task_id: str, new_config: dict):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
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

    def _load_config(self):
        # 此时可以用 findChildren 安全地查找 ui 中的控件
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
                item.value().setCheckState(0, Qt.CheckState.Checked if config_item.value else Qt.CheckState.Unchecked)
            item += 1

        item2 = QTreeWidgetItemIterator(self.select_weapon.tree)
        while item2.value():
            item_key2 = self.weapon_text_to_key.get(item2.value().text(0))
            config_item2 = getattr(config, item_key2, None) if item_key2 else None
            if config_item2 is not None:
                item2.value().setCheckState(0, Qt.CheckState.Checked if config_item2.value else Qt.CheckState.Unchecked)
            item2 += 1

    def _connect_to_save_changed(self):
        self.select_person.itemStateChanged.connect(self.save_item_changed)
        self.select_weapon.itemStateChanged.connect(self.save_item2_changed)

        children_list = get_all_children(self.ui)
        for children in children_list:
            if isinstance(children, CheckBox):
                children.stateChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, ComboBox):
                children.currentIndexChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, LineEdit):
                children.editingFinished.connect(partial(self.save_changed, children))
            elif isinstance(children, SpinBox):
                children.valueChanged.connect(partial(self.save_changed, children))

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
        view = FlyoutView(title=tutorial_title, content=tutorial_content, image="asset/path_tutorial.png", isClosable=True)
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)
        w = Flyout.make(view, self.ui.PrimaryPushButton_path_tutorial, self)
        view.closed.connect(w.close)

    def update_online_cloudflare(self):
        self.cloudflare_thread = CloudflareUpdateThread()
        self.cloudflare_thread.update_finished.connect(self._handle_cloudflare_success)
        self.cloudflare_thread.update_failed.connect(self._handle_cloudflare_error)
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
                        self.logger.error(f'通过cloudflare在线更新出错: updateData缺少必要字段 {field}')
                        self.get_tips()
                        return

            try:
                response = ApiResponse(**data)
                self._handle_update_logic(data, online_data, response)
            except Exception as e:
                self.logger.error(f'解析API响应数据时出错: {str(e)}')
                traceback.print_exc()
                self._handle_update_logic_fallback(data, online_data)
        except Exception as e:
            self.logger.error(f'处理Cloudflare数据时出错: {str(e)}')
            self.get_tips()

    def _handle_cloudflare_error(self, error_msg):
        self.logger.error(f'通过cloudflare在线更新出错: {error_msg}')
        self.get_tips()

    def _handle_update_logic(self, raw_data: Dict[str, Any], online_data: Dict[str, Any], response: ApiResponse):
        local_config_data = parse_config_update_data(config.update_data.value)
        if not local_config_data:
            config.set(config.update_data, raw_data)
            if config.isLog.value:
                self.logger.info(f'获取到更新信息：{online_data}')
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
            self.get_tips(url=url)
            InfoBar.success(
                title='获取更新成功',
                content="检测到新的 兑换码 活动信息",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=10000,
                parent=self
            )
        else:
            if online_data != local_config_data.data.model_dump():
                content = ''
                local_redeem_codes = [code.model_dump() for code in local_config_data.data.redeemCodes]
                if online_data['redeemCodes'] != [] and online_data['redeemCodes'] != local_redeem_codes:
                    new_used_codes = []
                    old_used_codes = config.used_codes.value
                    for code in response.data.redeemCodes:
                        if code.code in old_used_codes:
                            new_used_codes.append(code.code)
                    config.set(config.used_codes, new_used_codes)
                    content += ' 兑换码 '

                if online_data['updateData'] != local_config_data.data.updateData.model_dump():
                    content += ' 活动信息 '

                if config.isLog.value:
                    self.logger.info(f'获取到更新信息：{online_data}')
                config.set(config.update_data, raw_data)
                config.set(config.task_name, response.data.updateData.questName)
                url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
                self.get_tips(url=url)
                InfoBar.success(
                    title='获取更新成功',
                    content=f"检测到新的{content}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=10000,
                    parent=self
                )
            else:
                self.get_tips()

    def _handle_update_logic_fallback(self, data, online_data):
        if not config.update_data.value:
            config.set(config.update_data, data)
            if config.isLog.value:
                self.logger.info(f'获取到更新信息：{online_data}')
            catId = online_data["updateData"]["linkCatId"]
            linkId = online_data["updateData"]["linkId"]
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
            self.get_tips(url=url)
            InfoBar.success(
                title='获取更新成功',
                content="检测到新的 兑换码 活动信息",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=10000,
                parent=self
            )
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
                if config.isLog.value:
                    self.logger.info(f'获取到更新信息：{online_data}')
                config.set(config.update_data, data)
                config.set(config.task_name, online_data["updateData"]["questName"])
                catId = online_data["updateData"]["linkCatId"]
                linkId = online_data["updateData"]["linkId"]
                url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
                self.get_tips(url=url)
                InfoBar.success(
                    title='获取更新成功',
                    content=f"检测到新的{content}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=10000,
                    parent=self
                )
            else:
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

        InfoBar.success(
            title='重置成功',
            content=f"已重置 导入展示 {content}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self
        )

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
        InfoBar.success(
            title=status,
            content=f"点击“开始”按钮时{action}自动启动游戏",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self
        )

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

    def _set_launch_pending_state(self, pending: bool):
        self.is_launch_pending = bool(pending)
        if self.is_launch_pending:
            self.set_checkbox_enable(False)
            self.ui.PushButton_start.setText(self._ui_text("停止", "Stop"))
            return

        if not self.is_running:
            self.set_checkbox_enable(True)
            self.ui.PushButton_start.setText(self._ui_text("开始", "Start"))

    def _stop_running_guard(self):
        self.running_game_guard_timer.stop()

    def check_game_open(self):
        try:
            hwnd = self._is_game_window_open()
            if hwnd:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.info(f'已检测到游戏窗口：{hwnd}')
                # 这里改为传入刚才存下来的 tasks_to_run
                self.after_start_button_click(getattr(self, 'tasks_to_run', []))
                return

            if self.launch_process is not None and self.launch_process.poll() is not None:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.warning('启动流程已中断：检测到游戏进程退出，已取消本次自动任务')
                InfoBar.warning(
                    title=self._ui_text('启动已中断', 'Launch interrupted'),
                    content=self._ui_text('检测到游戏被关闭或启动失败，已停止后续任务。', 'Game was closed or failed to launch. Pending tasks were cancelled.'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=self
                )
                return

            if self.launch_deadline and time.time() > self.launch_deadline:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                self.logger.warning('等待游戏窗口超时，已取消本次自动任务')
                InfoBar.warning(
                    title=self._ui_text('等待超时', 'Launch timeout'),
                    content=self._ui_text('长时间未检测到游戏窗口，已停止后续任务。', 'Game window not detected in time. Pending tasks were cancelled.'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=self
                )
        except Exception as e:
            self.logger.error(f'检测游戏启动状态时出现异常：{e}')
            self._clear_launch_watch_state()
            self._set_launch_pending_state(False)

    def on_start_button_click(self):
        if self.is_launch_pending:
            self._clear_launch_watch_state()
            self._set_launch_pending_state(False)
            self.logger.info(self._ui_text("已取消等待游戏启动", "Cancelled waiting for game launch"))
            return

        # 变更为一个有序的任务列表
        tasks_to_run = []
        login_task_checked = False

        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            task_item = self.task_widget_map.get(task_id)
            is_checked = bool(task_item.checkbox.isChecked()) if task_item else False

            if task_id == "task_login":
                login_task_checked = is_checked
                if is_checked:
                    tasks_to_run.append(task_id)
            else:
                # 只有被勾选且满足周期执行条件的，才加入待执行列表
                if is_checked and self.should_run_task(task_cfg):
                    tasks_to_run.append(task_id)

        if config.CheckBox_open_game_directly.value and not is_exist_snowbreak() and login_task_checked:
            self.tasks_to_run = tasks_to_run  # 存入实例变量，供检测到窗口后调用
            self.open_game_directly()
        else:
            self.after_start_button_click(tasks_to_run)

    def after_start_button_click(self, tasks_to_run):
        if tasks_to_run: # 只要列表不为空，就说明有任务
            if not self.is_running:
                self.start_thread = StartThread(tasks_to_run, self)
                self.start_thread.is_running_signal.connect(self.handle_start)
                self.start_thread.start()
            else:
                self.start_thread.stop()
        else:
            InfoBar.error(
                title=self._ui_text('无执行任务', 'No task selected'),
                content=self._ui_text("没有勾选任务，或当前不在任务的生效周期内", "No task is selected or within valid schedule"),
                orient=Qt.Orientation.Horizontal,
                isClosable=False,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )

    def handle_start(self, str_flag):
        try:
            if str_flag == 'start':
                self._set_launch_pending_state(False)
                self.is_running = True
                self.set_checkbox_enable(False)
                self.ui.PushButton_start.setText(self._ui_text("停止", "Stop"))
                if not self.running_game_guard_timer.isActive():
                    self.running_game_guard_timer.start(1000)
            elif str_flag in ['end', 'no_auto', 'interrupted']:
                self._set_launch_pending_state(False)
                self.is_running = False
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)
                self.ui.PushButton_start.setText(self._ui_text("开始", "Start"))

                if str_flag == 'end':
                    self.after_finish()
                elif str_flag == 'interrupted':
                    InfoBar.warning(
                        title=self._ui_text('任务已停止', 'Task stopped'),
                        content=self._ui_text('检测到游戏窗口关闭，任务终止。', 'Game window was closed. Current task stopped gracefully.'),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=4000,
                        parent=self
                    )
        except Exception as e:
            self.logger.error(f'处理任务状态变更时出现异常：{e}')
            self._set_launch_pending_state(False)
            self.is_running = False
            self.running_game_guard_timer.stop()
            self.set_checkbox_enable(True)
            self.ui.PushButton_start.setText(self._ui_text("开始", "Start"))

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
                self.start_thread.stop(reason=self._ui_text('用户中断：游戏窗口已关闭', 'Interrupted by user: game window closed'))
        except Exception as e:
            self.logger.error(f'运行中窗口守护检测异常：{e}')
            self._stop_running_guard()

    def after_finish(self):
        idx = self.ui.ComboBox_after_use.currentIndex()
        if idx == 0:
            return
        elif idx == 1:
            if self.game_hwnd:
                win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)
            else:
                self.logger.warning('home未获取窗口句柄，无法关闭游戏')
            self.parent.close()
        elif idx == 2:
            self.parent.close()
        elif idx == 3:
            if self.game_hwnd:
                win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)
            else:
                self.logger.warning('home未获取窗口句柄，无法关闭游戏')

    def set_checkbox_enable(self, enable: bool):
        for checkbox in self.ui.findChildren(CheckBox):
            checkbox.setEnabled(enable)

    def set_current_index(self, index):
        try:
            if index < 0 or index >= len(self.setting_name_list):
                return
            self.ui.TitleLabel_setting.setText(self._ui_text("设置", "Settings") + "-" + self.setting_name_list[index])
            self.ui.PopUpAniStackedWidget.setCurrentIndex(index)
        except Exception as e:
            self.logger.error(e)

    def should_run_task(self, task_config: Dict[str, Any], now: datetime = None) -> bool:
        if not task_config.get("enabled", False):
            return False
        if not task_config.get("use_periodic", True):
            return True

        if now is None:
            now = datetime.now()

        def _normalize_rules(value, default_rules):
            if value is None:
                return copy.deepcopy(default_rules)
            if isinstance(value, dict):
                value = [value]
            if not value:
                return copy.deepcopy(default_rules)
            return value

        def _minutes_from_rule(rule):
            rule_time = str(rule.get("time", "00:00"))
            parts = rule_time.split(":")
            if len(parts) != 2:
                return None
            try:
                hour = int(parts[0])
                minute = int(parts[1])
            except ValueError:
                return None
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                return None
            return hour * 60 + minute

        def _is_rule_matched(rule):
            rule_type = str(rule.get("type", "daily")).lower()
            if rule_type not in {"daily", "weekly", "monthly"}:
                rule_type = "daily"

            target_minutes = _minutes_from_rule(rule)
            if target_minutes is None:
                return False

            now_minutes = now.hour * 60 + now.minute
            if now_minutes < target_minutes:
                return False

            if rule_type == "weekly":
                try:
                    return now.weekday() == int(rule.get("day", 0))
                except (TypeError, ValueError):
                    return False

            if rule_type == "monthly":
                try:
                    return now.day == int(rule.get("day", 1))
                except (TypeError, ValueError):
                    return False

            return True

        default_rules = [{"type": "daily", "day": 0, "time": "05:00", "max_runs": 1}]
        activation_config = task_config.get("activation_config")
        if activation_config is None:
            activation_config = task_config.get("refresh_config")
        activation_rules = _normalize_rules(activation_config, default_rules)

        if not any(_is_rule_matched(rule) for rule in activation_rules):
            return False

        execution_rules = _normalize_rules(task_config.get("execution_config"), default_rules)
        return any(_is_rule_matched(rule) for rule in execution_rules)

    def save_changed(self, widget, *args):
        config_item = getattr(config, widget.objectName(), None)
        if config_item is None:
            return

        if isinstance(widget, CheckBox):
            config.set(config_item, widget.isChecked())
            if widget.objectName() == 'CheckBox_is_use_power':
                self.ui.ComboBox_power_day.setEnabled(widget.isChecked())
            elif widget.objectName() == 'CheckBox_open_game_directly':
                self.ui.PushButton_select_directory.setEnabled(widget.isChecked())
        elif isinstance(widget, ComboBox):
            config.set(config_item, widget.currentIndex())
        elif isinstance(widget, SpinBox):
            config.set(config_item, widget.value())
        elif isinstance(widget, LineEdit):
            if 'x1' in widget.objectName() or 'x2' in widget.objectName() or 'y1' in widget.objectName() or 'y2' in widget.objectName():
                config.set(config_item, int(widget.text()))
            else:
                config.set(config_item, widget.text())

    def save_item_changed(self, index, check_state):
        config.set(getattr(config, f"item_person_{index}", None), False if check_state == 0 else True)

    def save_item2_changed(self, index, check_state):
        config.set(getattr(config, f"item_weapon_{index}", None), False if check_state == 0 else True)

    def get_tips(self, url=None):
        if url:
            tips_dic = get_date_from_api(url)
            if "error" in tips_dic.keys():
                self.logger.error(tips_dic["error"])
                return
            config.set(config.date_tip, tips_dic)
        else:
            if not config.date_tip.value:
                InfoBar.error(
                    title='活动日程更新失败',
                    content=f"本地没有存储信息且未获取到url",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
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
                if self.ui.scrollAreaWidgetContents_tips.findChild(BodyLabel, name=f"BodyLabel_tip_{index + 1}"):
                    BodyLabel_tip = self.ui.scrollAreaWidgetContents_tips.findChild(BodyLabel, name=f"BodyLabel_tip_{index + 1}")
                else:
                    BodyLabel_tip = BodyLabel(self.ui.scrollAreaWidgetContents_tips)
                    BodyLabel_tip.setObjectName(f"BodyLabel_tip_{index + 1}")

                if self.ui.scrollAreaWidgetContents_tips.findChild(ProgressBar, name=f"ProgressBar_tip{index + 1}"):
                    ProgressBar_tip = self.ui.scrollAreaWidgetContents_tips.findChild(ProgressBar, name=f"ProgressBar_tip{index + 1}")
                else:
                    ProgressBar_tip = ProgressBar(self.ui.scrollAreaWidgetContents_tips)
                    ProgressBar_tip.setObjectName(f"ProgressBar_tip{index + 1}")

                # 接收修改后的返回值
                days, total_day, status = value

                if status == -1: # 已结束
                    BodyLabel_tip.setText(f"{key} {self._ui_text('已结束', 'finished')}")
                    sort_weight = 99999
                    ProgressBar_tip.setValue(0)
                elif status == 1: # 未开始
                    BodyLabel_tip.setText(self._ui_text(f"{key} 还有 {days} 天开始", f"{key} starts in {days} day(s)"))
                    sort_weight = 10000 + days
                    ProgressBar_tip.setValue(0)
                else: # 正在进行
                    BodyLabel_tip.setText(self._ui_text(f"{key}剩余：{days}天", f"{key} remaining: {days} day(s)"))
                    sort_weight = days

                    normalized_percent = int((days / max_total_days) * 100)
                    ProgressBar_tip.setValue(normalized_percent)

                items_list.append([BodyLabel_tip, ProgressBar_tip, sort_weight])
                index += 1

            items_list.sort(key=lambda x: x[2])

            for i in range(len(items_list)):
                self.ui.gridLayout_tips.addWidget(items_list[i][0], i + 1, 0, 1, 1)
                self.ui.gridLayout_tips.addWidget(items_list[i][1], i + 1, 1, 1, 1)

        except Exception as e:
            self.logger.error(f"更新控件出错：{e}")

    def closeEvent(self, event):
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # 只要切回这个页面，就强制从 config 重新读取一次最新数据覆盖 UI
        self._load_config()
