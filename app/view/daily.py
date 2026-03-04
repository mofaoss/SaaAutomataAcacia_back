import copy
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
from qfluentwidgets import FluentIcon as FIF, InfoBar, InfoBarPosition, CheckBox, ComboBox, ToolButton, LineEdit, \
    BodyLabel, ProgressBar, FlyoutView, Flyout
from win11toast import toast

from app.common.config import config, is_non_chinese_ui_language
from app.common.data_models import Coordinates, UpdateData, RedeemCode, ApiData, ApiResponse, parse_config_update_data
from app.common.logger import logger
from app.common.signal_bus import signalBus
from app.common.style_sheet import StyleSheet
from utils.game_launcher import launch_game_with_guard
from utils.net_utils import get_cloudflare_data, get_date_from_api
from utils.ui_utils import get_all_children
from utils.updater_utils import get_gitee_text
from utils.win_utils import is_exist_snowbreak
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
from app.view.daily_view import DailyView, TaskItemWidget
from app.view.base_interface import BaseInterface


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
        "zh_name": "领取物资",
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
        "zh_name": "刷体力",
        "en_name": "Use Stamina",
    },
    "task_shards": {
        "module_class": PersonModule,
        "ui_page_index": 4,
        "option_key": "CheckBox_person_5",
        "zh_name": "人物碎片",
        "en_name": "Character Shards",
    },
    "task_chasm": {
        "module_class": ChasmModule,
        "ui_page_index": 5,
        "option_key": "CheckBox_chasm_6",
        "zh_name": "精神拟境",
        "en_name": "Neural Simulation",
    },
    "task_reward": {
        "module_class": GetRewardModule,
        "ui_page_index": 6,
        "option_key": "CheckBox_reward_7",
        "zh_name": "领取奖励",
        "en_name": "Claim Rewards",
    },
}


class CloudflareUpdateThread(QThread):
    """异步获取Cloudflare数据的线程"""
    update_finished = Signal(dict)  # 成功获取数据
    update_failed = Signal(str)  # 获取失败

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
    stop_signal = Signal()  # 添加停止信号

    def __init__(self, checkbox_dic, parent=None):
        super().__init__(parent)
        self.checkbox_dic = checkbox_dic
        self.logger = logger
        self.session = AutomationSession(self.logger)
        self._is_running = True
        self._interrupted_reason = None
        self.name_list_zh = ['自动登录', '领取物资', '商店购买', '刷体力', '人物碎片', '精神拟境', '领取奖励']
        self.name_list_en = ['Auto Login', 'Collect Supplies', 'Shop', 'Use Stamina', 'Character Shards',
                             'Neural Simulation', 'Claim Rewards']

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
            has_enabled_task = any(self.checkbox_dic.values())
            if has_enabled_task:
                if not self.session.prepare():
                    normal_stop_flag = False
                    return

            auto = self.session.auto

            for key, value in self.checkbox_dic.items():
                if not self._is_running:
                    normal_stop_flag = False
                    break
                if value:
                    index = int(re.search(r'\d+', key).group()) - 1
                    task_name = self.name_list_en[index] if is_non_chinese_ui_language() else self.name_list_zh[index]
                    self.logger.info(f"当前任务：{task_name}")
                    if index == 0:
                        module = EnterGameModule(auto, self.logger)
                        module.run()
                    elif index == 1:
                        module = CollectSuppliesModule(auto, self.logger)
                        module.run()
                    elif index == 2:
                        module = ShoppingModule(auto, self.logger)
                        module.run()
                    elif index == 3:
                        module = UsePowerModule(auto, self.logger)
                        module.run()
                    elif index == 4:
                        module = PersonModule(auto, self.logger)
                        module.run()
                    elif index == 5:
                        module = ChasmModule(auto, self.logger)
                        module.run()
                    elif index == 6:
                        module = GetRewardModule(auto, self.logger)
                        module.run()

                    if not self._is_running:
                        normal_stop_flag = False
                        break
                else:
                    # 如果value为false则进行下一个任务的判断
                    continue
            # 体力通知
            if config.inform_message.value or '--toast-only' in sys.argv:
                def empty_func(args):
                    pass

                full_time = auto.calculate_power_time() if auto is not None else None
                if full_time:
                    content = f'体力将在 {full_time} 完全恢复'
                else:
                    content = f"体力计算出错"
                toast(
                    '已完成勾选任务', content, on_dismissed=empty_func,
                    icon=os.path.abspath("app/resource/images/logo.ico"),
                )
        except Exception as e:
            ocr.stop_ocr()
            if str(e) != '已停止':
                self.logger.warning(e)
            # traceback.print_exc()
        finally:
            if self.session.auto is not None:
                self.session.stop()
            # 运行完成
            if normal_stop_flag and self._is_running:
                self.is_running_signal.emit('end')
            else:
                if self._interrupted_reason:
                    self.is_running_signal.emit('interrupted')
                else:
                    # 未成功创建auto，没开游戏或屏幕比例不对
                    self.is_running_signal.emit('no_auto')


def select_all(widget):
    # 遍历 widget 的所有子控件
    for checkbox in widget.findChildren(CheckBox):
        checkbox.setChecked(True)


def no_select(widget):
    # 遍历 widget 的所有子控件
    for checkbox in widget.findChildren(CheckBox):
        checkbox.setChecked(False)


class Daily(QFrame, BaseInterface):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.setting_name_list = [
            self._ui_text('登录', 'Login'),
            self._ui_text('物资', 'Supplies'),
            self._ui_text('商店', 'Shop'),
            self._ui_text('体力', 'Stamina'),
            self._ui_text('碎片', 'Shards'),
            self._ui_text('精神拟境', 'Neural Simulation'),
            self._ui_text('领取奖励', 'Claim Rewards'),
        ]
        self.person_dic = {
            "人物碎片": "item_person_0",
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
        self.logger = logger
        self.task_widget_map: Dict[str, TaskItemWidget] = {}
        self._task_sequence_cache: List[Dict[str, Any]] = []
        self._init_task_list_widgets()

        self.is_running = False
        self.select_person = TreeFrame_person(
            parent=self.ScrollArea,
            enableCheck=True,
            is_non_chinese_ui=self._is_non_chinese_ui,
        )
        self.select_weapon = TreeFrame_weapon(
            parent=self.ScrollArea,
            enableCheck=True,
            is_non_chinese_ui=self._is_non_chinese_ui,
        )

        self.game_hwnd = None
        self.start_thread = None
        self.launch_process = None
        self.launch_deadline = 0.0
        self.is_launch_pending = False
        self._is_dialog_open = False

        self._initWidget()
        self._connect_to_slot()
        self.redirectOutput(self.textBrowser_log)

        self.check_game_window_timer = QTimer()
        self.check_game_window_timer.timeout.connect(self.check_game_open)
        self.running_game_guard_timer = QTimer()
        self.running_game_guard_timer.timeout.connect(self._guard_running_game_window)
        self.checkbox_dic = None

        # self.get_tips()
        if config.checkUpdateAtStartUp.value:
            # self.update_online()
            self.update_online_cloudflare()
        else:
            self.get_tips()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _initWidget(self):
        self._apply_home_i18n()

        container_font = self.SimpleCardWidget_option.font()
        if container_font.pointSize() <= 0:
            container_font.setPointSize(10)
            self.SimpleCardWidget_option.setFont(container_font)

        for tool_button in self.SimpleCardWidget_option.findChildren(ToolButton):
            tool_button.setIcon(FIF.SETTING)
            btn_font = tool_button.font()
            if btn_font.pointSize() <= 0:
                btn_font.setPointSize(10)
                tool_button.setFont(btn_font)

        # 设置combobox选项
        after_use_items = [
            self._ui_text('无动作', 'Do Nothing'),
            self._ui_text('退出游戏和代理', 'Exit Game and Assistant'),
            self._ui_text('退出代理', 'Exit Assistant'),
            self._ui_text('退出游戏', 'Exit Game')
        ]
        power_day_items = ['1', '2', '3', '4', '5', '6']
        power_usage_items = [
            self._ui_text('活动材料本', 'Event Stages'),
            self._ui_text('刷常规后勤', 'Operation Logistics')
        ]
        self.ComboBox_after_use.addItems(after_use_items)
        self.ComboBox_power_day.addItems(power_day_items)
        self.ComboBox_power_usage.addItems(power_usage_items)
        self.LineEdit_c1.setPlaceholderText(self._ui_text("未输入", "Not set"))
        self.LineEdit_c2.setPlaceholderText(self._ui_text("未输入", "Not set"))
        self.LineEdit_c3.setPlaceholderText(self._ui_text("未输入", "Not set"))
        self.LineEdit_c4.setPlaceholderText(self._ui_text("未输入", "Not set"))

        self.BodyLabel_enter_tip.setText(
            "### Tips\n* Select your server in Settings\n* Enable \"Auto open game\" and select the correct game path by the tutorial above\n* Click \"Start\" to launch and run automatically"
            if self._is_non_chinese_ui else
            "### 提示\n* 去设置里选择你的区服\n* 建议勾选“自动打开游戏”，勾选后根据上方教程选择好对应的路径\n* 点击“开始”按钮会自动打开游戏")
        self.BodyLabel_person_tip.setText(
            "### Tips\n* Enter codename instead of full name, e.g. use \"朝翼\" (Dawnwing) for \"凯茜娅-朝翼\" (Katya-Dawnwing)"
            if self._is_non_chinese_ui else
            "### 提示\n* 输入代号而非全名，比如想要刷“凯茜娅-朝翼”，就输入“朝翼”")
        self.BodyLabel_collect_supplies.setText(
            "### Tips\n* Enable \"Redeem Code\" to fetch and redeem online codes automatically\n* Online codes are maintained by developers and may not always be updated in time\n* You can import a txt file for batch redeem (one code per line)"
            if self._is_non_chinese_ui else
            "### 提示\n* 勾选“领取兑换码”会自动拉取在线兑换码进行兑换\n* 在线兑换码由开发者维护，更新不一定及时\n* 导入txt文本文件可以批量使用用户兑换码，txt需要一行一个兑换码")
        self.BodyLabel_chasm_tip.setText(
            "### Tips\n* Neural Simulation opens every Tuesday at 10:00"
            if self._is_non_chinese_ui else
            "### 提示\n* 拟境每周2的10:00开启"
        )
        self.BodyLabel_reward_tip.setText(
            "### Tips\n* Claim monthly card and daily rewards"
            if self._is_non_chinese_ui else
            "### 提示\n* 领取大月卡和日常奖励"
        )
        self.PopUpAniStackedWidget.setCurrentIndex(0)
        self.TitleLabel_setting.setText(self._ui_text("设置", "Settings") + "-" + self.setting_name_list[
            self.PopUpAniStackedWidget.currentIndex()])
        self.PushButton_start.setShortcut("F1")
        self.PushButton_start.setToolTip(self._ui_text("快捷键：F1", "Shortcut: F1"))

        self.gridLayout.addWidget(self.select_person, 1, 0)
        self.gridLayout.addWidget(self.select_weapon, 2, 0)

        self._load_config()
        self._sync_task_sequence_from_ui()
        self._load_initial_task_panel()
        # 和其他控件有相关状态判断的，要放在load_config后
        self.ComboBox_power_day.setEnabled(self.CheckBox_is_use_power.isChecked())
        self.PushButton_select_directory.setEnabled(self.CheckBox_open_game_directly.isChecked())

        StyleSheet.HOME_INTERFACE.apply(self)
        # 使背景透明，适应主题
        self.ScrollArea.enableTransparentBackground()
        self.ScrollArea_tips.enableTransparentBackground()

        # 将“日程提醒”整个卡片移动到日志栏下方，保持原边框与高度
        self.gridLayout_2.removeWidget(self.SimpleCardWidget)
        self.gridLayout_2.removeWidget(self.SimpleCardWidget_tips)
        self.gridLayout_2.addWidget(self.SimpleCardWidget, 0, 2, 1, 1)
        self.gridLayout_2.addWidget(self.SimpleCardWidget_tips, 1, 2, 1, 1)

    def _connect_to_slot(self):
        self.PushButton_start.clicked.connect(self.on_start_button_click)
        self.PrimaryPushButton_path_tutorial.clicked.connect(self.on_path_tutorial_click)
        self.PushButton_select_all.clicked.connect(lambda: select_all(self.SimpleCardWidget_option))
        self.PushButton_no_select.clicked.connect(lambda: no_select(self.SimpleCardWidget_option))
        self.PushButton_select_directory.clicked.connect(self.on_select_directory_click)
        self.PrimaryPushButton_import_codes.clicked.connect(self.on_import_codes_click)
        self.PushButton_reset_codes.clicked.connect(self.on_reset_codes_click)

        for task_id, task_item in self.task_widget_map.items():
            task_item.settings_clicked.connect(self._on_task_settings_clicked)
            task_item.checkbox_state_changed.connect(self._on_task_checkbox_changed)

        self.taskListWidget.orderChanged.connect(self._on_task_order_changed)
        self.ui.shared_scheduling_panel.config_changed.connect(self._on_shared_config_changed)

        self.CheckBox_open_game_directly.stateChanged.connect(self.change_auto_open)

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

        self.taskListWidget.clear()
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
                parent=self.taskListWidget,
            )
            task_item.checkbox.setObjectName(meta["option_key"])
            self.taskListWidget.add_task_item(task_item)
            self.task_widget_map[task_id] = task_item
            setattr(self, meta["option_key"], task_item.checkbox)

    def _sync_task_sequence_from_ui(self):
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        task_by_id = {item["id"]: item for item in sequence}

        for task_id, task_item in self.task_widget_map.items():
            if task_id in task_by_id:
                task_by_id[task_id]["enabled"] = task_item.checkbox.isChecked()

        ordered = []
        for task_id in self.taskListWidget.get_task_order():
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
        for widget in self.findChildren(QWidget):
            # 动态获取 config 对象中与 widget.objectName() 对应的属性值
            config_item = getattr(config, widget.objectName(), None)
            if config_item:
                if isinstance(widget, CheckBox):
                    widget.setChecked(config_item.value)  # 使用配置项的值设置 CheckBox 的状态
                elif isinstance(widget, ComboBox):
                    # widget.setPlaceholderText("未选择")
                    widget.setCurrentIndex(config_item.value)
                elif isinstance(widget, LineEdit):
                    widget.setText(str(config_item.value))
        self._load_item_config()

    def _load_item_config(self):
        item = QTreeWidgetItemIterator(self.select_person.tree)
        while item.value():
            item_key = self.person_text_to_key.get(item.value().text(0))
            config_item = getattr(config, item_key, None) if item_key else None
            if config_item is not None:
                item.value().setCheckState(
                    0,
                    Qt.CheckState.Checked if config_item.value else Qt.CheckState.Unchecked,
                )
            item += 1

        item2 = QTreeWidgetItemIterator(self.select_weapon.tree)
        while item2.value():
            item_key2 = self.weapon_text_to_key.get(item2.value().text(0))
            config_item2 = getattr(config, item_key2, None) if item_key2 else None
            if config_item2 is not None:
                item2.value().setCheckState(
                    0,
                    Qt.CheckState.Checked if config_item2.value else Qt.CheckState.Unchecked,
                )
            item2 += 1

    def _connect_to_save_changed(self):
        # 人物和武器的单独保存
        self.select_person.itemStateChanged.connect(self.save_item_changed)
        self.select_weapon.itemStateChanged.connect(self.save_item2_changed)

        children_list = get_all_children(self)
        for children in children_list:
            # 此时不能用lambda，会使传参出错
            if isinstance(children, CheckBox):
                # children.stateChanged.connect(lambda: save_changed(children))
                children.stateChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, ComboBox):
                children.currentIndexChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, LineEdit):
                children.editingFinished.connect(partial(self.save_changed, children))

    def set_hwnd(self, hwnd):
        self.game_hwnd = hwnd

    def on_path_tutorial_click(self):
        """查找启动器路径教程，记得添加进build路径"""
        tutorial_title = "How to find the game path" if self._is_non_chinese_ui else "如何查找对应游戏路径"
        tutorial_content = (
            'No matter which server/channel you play, first select your server in Settings.\n'
            'For global server, choose a path like "E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK".\n'
            'For CN/Bilibili server, open the Snowbreak launcher and find launcher settings.\n'
            'Then choose the game installation path shown there.'
            if self._is_non_chinese_ui else
            '不管你是哪个渠道服的玩家，第一步都应该先去设置里选服\n国际服选完服之后选择类似"E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK"的路径\n官服和b服的玩家打开尘白启动器，新版或者旧版启动器都找到启动器里对应的设置\n在下面的路径选择中找到并选择刚才你看到的路径'
        )
        view = FlyoutView(
            title=tutorial_title,
            content=tutorial_content,
            image="asset/path_tutorial.png",
            isClosable=True,
        )
        # 调整布局
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)

        w = Flyout.make(view, self.PrimaryPushButton_path_tutorial, self)
        view.closed.connect(w.close)

    def update_online(self):
        """通过gitee在线更新(停用)"""
        text = get_gitee_text("update_data.txt")
        # 返回字典说明必定出现报错了
        if isinstance(text, dict):
            logger.error(text["error"])
            return
        # 只有在获得新内容的时候才做更新动作,text[0]为第一行：坐标等数据
        if text[0] != config.update_data.value or not config.date_tip.value:
            if config.isLog.value:
                logger.info(f'获取到更新信息：{text[0]}')
            # 更新配置
            config.set(config.update_data, text[0])

            data = text[0].split("_")
            # 设置任务名
            config.set(config.task_name, data[9])
            # 更新链活动提醒
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={data[10]}&id={data[11]}"

            self.get_tips(url=url)
            # 更新材料和深渊位置在use_power.py
        else:
            # 获取本地保存的信息
            self.get_tips()

    def update_online_cloudflare(self):
        """通过cloudflare在线更新（异步）更新内容包括版本号，版本坐标，兑换码"""
        # 创建异步网络请求线程
        self.cloudflare_thread = CloudflareUpdateThread()
        self.cloudflare_thread.update_finished.connect(self._handle_cloudflare_success)
        self.cloudflare_thread.update_failed.connect(self._handle_cloudflare_error)
        self.cloudflare_thread.start()

    def _handle_cloudflare_success(self, data):
        """处理Cloudflare数据获取成功"""
        try:
            # 检查数据结构是否正确
            if 'data' not in data:
                logger.error('通过cloudflare在线更新出错: 返回数据格式不正确')
                self.get_tips()
                return

            online_data = data["data"]

            # 检查必要的字段是否存在
            required_fields = ['updateData', 'redeemCodes', 'version']
            update_data_fields = ['linkCatId', 'linkId', 'questName']

            for field in required_fields:
                if field not in online_data:
                    logger.error(f'通过cloudflare在线更新出错: 缺少必要字段 {field}')
                    self.get_tips()
                    return

            if 'updateData' in online_data:
                for field in update_data_fields:
                    if field not in online_data['updateData']:
                        logger.error(f'通过cloudflare在线更新出错: updateData缺少必要字段 {field}')
                        self.get_tips()
                        return

            # 解析为结构化数据对象
            try:
                # 直接用Pydantic解析整个响应
                response = ApiResponse(**data)

                # 处理更新逻辑
                self._handle_update_logic(data, online_data, response)

            except Exception as e:
                logger.error(f'解析API响应数据时出错: {str(e)}')
                traceback.print_exc()
                # 如果解析失败，回退到原始处理方式
                self._handle_update_logic_fallback(data, online_data)

        except Exception as e:
            logger.error(f'处理Cloudflare数据时出错: {str(e)}')
            self.get_tips()

    def _handle_cloudflare_error(self, error_msg):
        """处理Cloudflare数据获取失败"""
        logger.error(f'通过cloudflare在线更新出错: {error_msg}')
        # 获取本地保存的信息
        self.get_tips()

    def _handle_update_logic(self, raw_data: Dict[str, Any], online_data: Dict[str, Any], response: ApiResponse):
        """处理更新数据的业务逻辑"""
        local_config_data = parse_config_update_data(config.update_data.value)

        if not local_config_data:
            # 首次获取数据或本地数据格式不正确
            config.set(config.update_data, raw_data)
            if config.isLog.value:
                logger.info(f'获取到更新信息：{online_data}')
            # 更新链活动提醒
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={response.data.updateData.linkCatId}&id={response.data.updateData.linkId}"
            self.get_tips(url=url)
            InfoBar.success(
                title='获取更新成功',
                content=f"检测到新的 兑换码 活动信息",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=10000,
                parent=self
            )
        else:
            # 比较在线数据和本地数据
            if online_data != local_config_data.data.model_dump():
                content = ''
                # 出现了兑换码数据的更新
                local_redeem_codes = [code.model_dump() for code in local_config_data.data.redeemCodes]
                if online_data['redeemCodes'] != [] and online_data['redeemCodes'] != local_redeem_codes:
                    new_used_codes = []
                    old_used_codes = config.used_codes.value
                    for code in response.data.redeemCodes:
                        if code.code in old_used_codes:
                            new_used_codes.append(code.code)
                    config.set(config.used_codes, new_used_codes)  # 更新以用兑换码的列表
                    content += ' 兑换码 '

                if online_data['updateData'] != local_config_data.data.updateData.model_dump():
                    content += ' 活动信息 '

                if config.isLog.value:
                    logger.info(f'获取到更新信息：{online_data}')
                config.set(config.update_data, raw_data)
                config.set(config.task_name, response.data.updateData.questName)
                # 更新链活动提醒
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
                self.get_tips()  # 获取本地保存的信息

    def _handle_update_logic_fallback(self, data, online_data):
        """原始的数据处理逻辑（回退方案）"""
        if not config.update_data.value:
            config.set(config.update_data, data)
            if config.isLog.value:
                logger.info(f'获取到更新信息：{online_data}')
            # 更新链活动提醒
            catId = online_data["updateData"]["linkCatId"]
            linkId = online_data["updateData"]["linkId"]
            url = f"https://www.cbjq.com/api.php?op=search_api&action=get_article_detail&catid={catId}&id={linkId}"
            self.get_tips(url=url)
            InfoBar.success(
                title='获取更新成功',
                content=f"检测到新的 兑换码 活动信息",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=10000,
                parent=self
            )
        else:
            # 检查本地数据结构是否正确
            if not isinstance(config.update_data.value, dict) or 'data' not in config.update_data.value:
                logger.error('本地配置数据格式不正确，使用在线数据')
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
                # 出现了兑换码数据的更新
                if online_data['redeemCodes'] != local_data['redeemCodes']:
                    new_used_codes = []
                    old_used_codes = config.used_codes.value
                    for code in online_data['redeemCodes']:
                        if code['code'] in old_used_codes:
                            new_used_codes.append(code['code'])
                    config.set(config.used_codes, new_used_codes)  # 更新以用兑换码的列表
                    content += ' 兑换码 '
                if online_data['updateData'] != local_data['updateData']:
                    content += ' 活动信息 '
                if config.isLog.value:
                    logger.info(f'获取到更新信息：{online_data}')
                config.set(config.update_data, data)
                config.set(config.task_name, online_data["updateData"]["questName"])
                # 更新链活动提醒
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
                self.get_tips()  # 获取本地保存的信息

    def on_select_directory_click(self):
        """ 选择启动器路径 """
        # file_path, _ = QFileDialog.getOpenFileName(self, "选择启动器", config.LineEdit_game_directory.value,
        #                                            "Executable Files (*.exe);;All Files (*)")
        folder = QFileDialog.getExistingDirectory(self, '选择游戏文件夹', "./")
        if not folder or config.LineEdit_game_directory.value == folder:
            return
        self.LineEdit_game_directory.setText(folder)
        self.LineEdit_game_directory.editingFinished.emit()

    def on_reset_codes_click(self):
        content = ''
        if self.textBrowser_import_codes.toPlainText():
            self.textBrowser_import_codes.setText("")
        # 重置导入
        if config.import_codes.value:
            config.set(config.import_codes, [])
            content += ' 导入 '
        # 重置已使用
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
        """点击了导入兑换码按钮"""
        def filter_codes(text):
            lines = text.splitlines()
            result = []
            for line in lines:
                # 去除行首尾空白字符
                stripped_line = line.strip()
                # 检查是否以"卡号："开头
                if ':' in stripped_line:
                    code = stripped_line.split(':')[-1]
                    result.append(code)
                elif '：' in stripped_line:
                    code = stripped_line.split('：')[-1]
                    result.append(code)
                else:
                    # 如果没有冒号
                    result.append(stripped_line)
            # 将结果重新组合成每行一个的字符串并设置显示
            self.textBrowser_import_codes.setText("\n".join(result))
            # 返回列表
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
        if state == 2:
            InfoBar.success(
                title='已开启',
                content=f"点击“开始”按钮时将自动启动游戏",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
        else:
            InfoBar.success(
                title='已关闭',
                content=f"点击“开始”按钮时不会自动启动游戏",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )

    def open_game_directly(self):
        """直接启动游戏"""
        try:
            result = launch_game_with_guard(logger=logger)
            if not result.get("ok"):
                logger.error(result.get("error", "启动游戏失败"))
                self._set_launch_pending_state(False)
                return

            self.launch_process = result.get("process")

            self.launch_deadline = time.time() + 90
            self.check_game_window_timer.start(500)
            self._set_launch_pending_state(True)
        except Exception as e:
            logger.error(f'出现报错: {e}')
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
            self.PushButton_start.setText(self._ui_text("停止", "Stop"))
            return

        if not self.is_running:
            self.set_checkbox_enable(True)
            self.PushButton_start.setText(self._ui_text("开始", "Start"))

    def _stop_running_guard(self):
        self.running_game_guard_timer.stop()

    def check_game_open(self):
        try:
            hwnd = self._is_game_window_open()
            if hwnd:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                logger.info(f'已检测到游戏窗口：{hwnd}')
                self.after_start_button_click(self.checkbox_dic)
                return

            if self.launch_process is not None and self.launch_process.poll() is not None:
                self._clear_launch_watch_state()
                self._set_launch_pending_state(False)
                logger.warning('启动流程已中断：检测到游戏进程退出，已取消本次自动任务')
                InfoBar.warning(
                    title=self._ui_text('启动已中断', 'Launch interrupted'),
                    content=self._ui_text('检测到游戏被关闭或启动失败，已停止后续任务。',
                                          'Game was closed or failed to launch. Pending tasks were cancelled.'),
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
                logger.warning('等待游戏窗口超时，已取消本次自动任务')
                InfoBar.warning(
                    title=self._ui_text('等待超时', 'Launch timeout'),
                    content=self._ui_text('长时间未检测到游戏窗口，已停止后续任务。',
                                          'Game window not detected in time. Pending tasks were cancelled.'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=self
                )
        except Exception as e:
            logger.error(f'检测游戏启动状态时出现异常：{e}')
            self._clear_launch_watch_state()
            self._set_launch_pending_state(False)

    def on_start_button_click(self):
        """点击开始按钮后的逻辑"""
        if self.is_launch_pending:
            self._clear_launch_watch_state()
            self._set_launch_pending_state(False)
            logger.info(self._ui_text("已取消等待游戏启动", "Cancelled waiting for game launch"))
            return

        checkbox_dic = {}
        login_task_checked = False
        sequence = self._normalize_task_sequence(config.daily_task_sequence.value)
        for task_cfg in sequence:
            task_id = task_cfg.get("id")
            meta = TASK_REGISTRY.get(task_id)
            if not meta:
                continue
            option_key = meta["option_key"]
            task_item = self.task_widget_map.get(task_id)
            is_checked = bool(task_item.checkbox.isChecked()) if task_item else False
            if task_id == "task_login":
                login_task_checked = is_checked
                checkbox_dic[option_key] = is_checked
            else:
                checkbox_dic[option_key] = is_checked and self.should_run_task(task_cfg)

        # 开启游戏:勾选了自动登录、游戏窗口未打开且勾选了自动登录游戏
        if config.CheckBox_open_game_directly.value and not is_exist_snowbreak() and login_task_checked:
            self.checkbox_dic = checkbox_dic
            self.open_game_directly()
        else:
            self.after_start_button_click(checkbox_dic)

    def after_start_button_click(self, checkbox_dic):
        if any(checkbox_dic.values()):
            if not self.is_running:
                self.start_thread = StartThread(checkbox_dic, self)
                self.start_thread.is_running_signal.connect(self.handle_start)
                self.start_thread.start()
            else:
                self.start_thread.stop()
        else:
            # logger.error("需要至少勾选一项任务才能开始")
            InfoBar.error(
                title=self._ui_text('未勾选工作', 'No task selected'),
                content=self._ui_text("需要至少勾选一项工作才能开始", "Select at least one task before starting"),
                orient=Qt.Orientation.Horizontal,
                isClosable=False,  # disable close button
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )

    def handle_start(self, str_flag):
        """设置按钮"""
        try:
            if str_flag == 'start':
                self._set_launch_pending_state(False)
                self.is_running = True
                self.set_checkbox_enable(False)
                self.PushButton_start.setText(self._ui_text("停止", "Stop"))
                if not self.running_game_guard_timer.isActive():
                    self.running_game_guard_timer.start(1000)
            elif str_flag == 'end':
                self._set_launch_pending_state(False)
                self.is_running = False
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)
                self.PushButton_start.setText(self._ui_text("开始", "Start"))
                # 后处理
                self.after_finish()
            elif str_flag == 'no_auto':
                self._set_launch_pending_state(False)
                self.is_running = False
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)
                self.PushButton_start.setText(self._ui_text("开始", "Start"))
            elif str_flag == 'interrupted':
                self._set_launch_pending_state(False)
                self.is_running = False
                self.running_game_guard_timer.stop()
                self.set_checkbox_enable(True)
                self.PushButton_start.setText(self._ui_text("开始", "Start"))
                InfoBar.warning(
                    title=self._ui_text('任务已停止', 'Task stopped'),
                    content=self._ui_text('检测到游戏窗口关闭，任务终止。',
                                          'Game window was closed. Current task stopped gracefully.'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=4000,
                    parent=self
                )
        except Exception as e:
            logger.error(f'处理任务状态变更时出现异常：{e}')
            self._set_launch_pending_state(False)
            self.is_running = False
            self.running_game_guard_timer.stop()
            self.set_checkbox_enable(True)
            self.PushButton_start.setText(self._ui_text("开始", "Start"))

    def _guard_running_game_window(self):
        try:
            if not self.is_running:
                self._stop_running_guard()
                return

            if self._is_game_window_open():
                return

            self._stop_running_guard()
            logger.warning('检测到游戏窗口已关闭，正在停止当前自动任务')
            if self.start_thread is not None and self.start_thread.isRunning():
                self.start_thread.stop(reason=self._ui_text('用户中断：游戏窗口已关闭',
                                                            'Interrupted by user: game window closed'))
        except Exception as e:
            logger.error(f'运行中窗口守护检测异常：{e}')
            self._stop_running_guard()

    def after_finish(self):
        # 任务结束后的后处理
        if self.ComboBox_after_use.currentIndex() == 0:
            return
        elif self.ComboBox_after_use.currentIndex() == 1:
            if self.game_hwnd:
                win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)
            else:
                self.logger.warning('home未获取窗口句柄，无法关闭游戏')
            self.parent.close()
        elif self.ComboBox_after_use.currentIndex() == 2:
            self.parent.close()
        elif self.ComboBox_after_use.currentIndex() == 3:
            if self.game_hwnd:
                win32gui.SendMessage(self.game_hwnd, win32con.WM_CLOSE, 0, 0)
            else:
                self.logger.warning('home未获取窗口句柄，无法关闭游戏')

    def set_checkbox_enable(self, enable: bool):
        for checkbox in self.findChildren(CheckBox):
            checkbox.setEnabled(enable)

    def set_current_index(self, index):
        try:
            if index < 0 or index >= len(self.setting_name_list):
                return
            self.TitleLabel_setting.setText(self._ui_text("设置", "Settings") + "-" + self.setting_name_list[index])
            self.PopUpAniStackedWidget.setCurrentIndex(index)
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

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else zh_text

    def _apply_home_i18n(self):
        self.TitleLabel.setText(self._ui_text("日志", "Log"))
        self.PushButton_select_all.setText(self._ui_text("全选", "Select All"))
        self.PushButton_no_select.setText(self._ui_text("清空", "Clear"))
        self.hint_label.setText(self._ui_text("拖动可调整任务顺序", "Drag to reorder"))
        self.BodyLabel.setText(self._ui_text("结束后进行", "After Finish"))
        self.PushButton_start.setText(self._ui_text("开始", "Start"))
        self.PrimaryPushButton_path_tutorial.setText(self._ui_text("查看教程", "Tutorial"))
        self.StrongBodyLabel_4.setText(self._ui_text("启动器中查看游戏路径", "Find game path in launcher"))
        self.CheckBox_open_game_directly.setText(self._ui_text("自动打开游戏", "Auto open game"))
        self.PushButton_select_directory.setText(self._ui_text("选择", "Browse"))
        self.CheckBox_mail.setText(self._ui_text("领取邮件", "Claim Mail"))
        self.CheckBox_fish_bait.setText(self._ui_text("领取鱼饵", "Claim Bait"))
        self.CheckBox_dormitory.setText(self._ui_text("宿舍碎片", "Dorm Shards"))
        self.CheckBox_redeem_code.setText(self._ui_text("领取兑换码", "Redeem Codes"))
        self.PrimaryPushButton_import_codes.setText(self._ui_text("导入", "Import"))
        self.PushButton_reset_codes.setText(self._ui_text("重置", "Reset"))
        self.StrongBodyLabel.setText(self._ui_text("选择要购买的商品", "Select items to buy"))
        self.StrongBodyLabel_2.setText(self._ui_text("选择体力使用方式", "Stamina usage mode"))
        self.CheckBox_is_use_power.setText(self._ui_text("自动使用期限", "Auto use expiring"))
        self.BodyLabel_6.setText(self._ui_text("天内的体力药", "day potion"))
        self.StrongBodyLabel_3.setText(self._ui_text("选择需要刷碎片的角色", "Select characters for shards"))
        self.BodyLabel_3.setText(self._ui_text("角色1：", "Character 1:"))
        self.BodyLabel_4.setText(self._ui_text("角色2：", "Character 2:"))
        self.BodyLabel_5.setText(self._ui_text("角色3：", "Character 3:"))
        self.BodyLabel_8.setText(self._ui_text("角色4：", "Character 4:"))
        self.CheckBox_is_use_chip.setText(self._ui_text("是否使用记忆嵌片", "Use memory chip"))
        self.TitleLabel_3.setText(self._ui_text("日程提醒", "Schedule"))

        self.CheckBox_buy_3.setText(self._ui_text("通用强化套件", "Universal Enhancement Kit"))
        self.CheckBox_buy_4.setText(self._ui_text("优选强化套件", "Premium Enhancement Kit"))
        self.CheckBox_buy_5.setText(self._ui_text("精致强化套件", "Exquisite Enhancement Kit"))
        self.CheckBox_buy_6.setText(self._ui_text("新手战斗记录", "Beginner Battle Record"))
        self.CheckBox_buy_7.setText(self._ui_text("普通战斗记录", "Standard Battle Record"))
        self.CheckBox_buy_8.setText(self._ui_text("优秀战斗记录", "Advanced Battle Record"))
        self.CheckBox_buy_9.setText(self._ui_text("初级职级认证", "Junior Rank Certification"))
        self.CheckBox_buy_10.setText(self._ui_text("中级职级认证", "Intermediate Rank Certification"))
        self.CheckBox_buy_11.setText(self._ui_text("高级职级认证", "Senior Rank Certification"))
        self.CheckBox_buy_12.setText(self._ui_text("合成颗粒", "Synthetic Particles"))
        self.CheckBox_buy_13.setText(self._ui_text("芳烃塑料", "Hydrocarbon Plastic"))
        self.CheckBox_buy_14.setText(self._ui_text("单极纤维", "Monopolar Fibers"))
        self.CheckBox_buy_15.setText(self._ui_text("光纤轴突", "Fiber Axon"))

        for task_id, task_item in self.task_widget_map.items():
            meta = TASK_REGISTRY.get(task_id)
            if not meta:
                continue
            task_item.label.setText(meta["en_name"] if self._is_non_chinese_ui else meta["zh_name"])

    def save_changed(self, widget, *args):
        # logger.debug(f"触发save_changed:{widget.objectName()}")
        # 当与配置相关的控件状态改变时调用此函数保存配置
        config_item = getattr(config, widget.objectName(), None)
        if config_item is None:
            return

        if isinstance(widget, CheckBox):
            config.set(config_item, widget.isChecked())
            if widget.objectName() == 'CheckBox_is_use_power':
                self.ComboBox_power_day.setEnabled(widget.isChecked())
            elif widget.objectName() == 'CheckBox_open_game_directly':
                self.PushButton_select_directory.setEnabled(widget.isChecked())
        elif isinstance(widget, ComboBox):
            config.set(config_item, widget.currentIndex())
        elif isinstance(widget, LineEdit):
            # 对坐标进行数据转换处理
            if 'x1' in widget.objectName() or 'x2' in widget.objectName() or 'y1' in widget.objectName() or 'y2' in widget.objectName():
                config.set(config_item, int(widget.text()))
            else:
                config.set(config_item, widget.text())

    def save_item_changed(self, index, check_state):
        # print(index, check_state)
        config.set(getattr(config, f"item_person_{index}", None), False if check_state == 0 else True)

    def save_item2_changed(self, index, check_state):
        # print(index, check_state)
        config.set(getattr(config, f"item_weapon_{index}", None), False if check_state == 0 else True)

    def get_time_difference(self, date_due: str):
        """
        通过给入终止时间获取剩余时间差和时间百分比
        :param date_due: 持续时间，格式'03.06-04.17'
        :return:如果活动过期，则返回None,否则返回时间差，剩余百分比
        """
        current_year = datetime.now().year
        start_time = datetime.strptime(f"{current_year}.{date_due.split('-')[0]}", "%Y.%m.%d")
        end_time = datetime.strptime(f"{current_year}.{date_due.split('-')[1]}", "%Y.%m.%d")
        if end_time.month < start_time.month:
            end_time = datetime.strptime(f"{current_year + 1}.{date_due.split('-')[1]}", "%Y.%m.%d")
        # 获取当前日期和时间
        now = datetime.now()

        total_difference = end_time - start_time
        total_day = total_difference.days + 1
        if now < start_time:
            # 将当前日期替换成开始日期
            now = start_time
        time_difference = end_time - now
        days_remaining = time_difference.days + 1
        if days_remaining < 0:
            return 0, 0

        return days_remaining, (days_remaining / total_day) * 100, days_remaining == total_day

    def get_tips(self, url=None):
        if url:
            tips_dic = get_date_from_api(url)
            if "error" in tips_dic.keys():
                logger.error(tips_dic["error"])
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
            logger.info("获取活动日程成功")
        for key, value in tips_dic.items():
            tips_dic[key] = self.get_time_difference(value)

        index = 0
        items_list = []
        try:
            for key, value in tips_dic.items():
                if self.scrollAreaWidgetContents_tips.findChild(BodyLabel, name=f"BodyLabel_tip_{index + 1}"):
                    BodyLabel_tip = self.scrollAreaWidgetContents_tips.findChild(BodyLabel, name=f"BodyLabel_tip_{index + 1}")
                else:
                    # 创建label
                    BodyLabel_tip = BodyLabel(self.scrollAreaWidgetContents_tips)
                    BodyLabel_tip.setObjectName(f"BodyLabel_tip_{index + 1}")
                if self.scrollAreaWidgetContents_tips.findChild(ProgressBar, name=f"ProgressBar_tip{index + 1}"):
                    ProgressBar_tip = self.scrollAreaWidgetContents_tips.findChild(ProgressBar,
                                                                           name=f"ProgressBar_tip{index + 1}")
                else:
                    # 创建进度条
                    ProgressBar_tip = ProgressBar(self.scrollAreaWidgetContents_tips)
                    ProgressBar_tip.setObjectName(f"ProgressBar_tip{index + 1}")
                if value[0] == 0:
                    BodyLabel_tip.setText(
                        f"{key} {self._ui_text('已结束', 'finished')}"
                    )
                else:
                    if value[2]:
                        BodyLabel_tip.setText(
                            f"{key} {self._ui_text('未开始', 'not started')}"
                        )
                    else:
                        BodyLabel_tip.setText(
                            self._ui_text(f"{key}剩余：{value[0]}天", f"{key} remaining: {value[0]} day(s)")
                        )
                ProgressBar_tip.setValue(int(value[1]))
                items_list.append([BodyLabel_tip, ProgressBar_tip, value[1]])

                index += 1
            items_list.sort(key=lambda x: x[2])
            for i in range(len(items_list)):
                self.gridLayout_tips.addWidget(items_list[i][0], i + 1, 0, 1, 1)
                self.gridLayout_tips.addWidget(items_list[i][1], i + 1, 1, 1, 1)

        except Exception as e:
            logger.error(f"更新控件出错：{e}")

    def closeEvent(self, event):
        super().closeEvent(event)
