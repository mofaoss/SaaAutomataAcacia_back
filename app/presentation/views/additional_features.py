import re
from functools import partial

from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout
from rapidfuzz import process
from qfluentwidgets import SpinBox, CheckBox, ComboBox, LineEdit, Slider, InfoBar

from app.infrastructure.config.app_config import config
from app.infrastructure.events.signal_bus import signalBus
from app.presentation.shared.style_sheet import StyleSheet
from app.utils.ui import get_all_children

# 导入业务模块 UI
from app.modules.trigger.ui.trigger_interface import TriggerInterface
from app.modules.fishing.ui.fishing_interface import FishingInterface
from app.modules.operation_action.ui.operation_interface import OperationInterface
from app.modules.water_bomb.ui.water_bomb_interface import WaterBombInterface
from app.modules.alien_guardian.ui.alien_guardian_interface import AlienGuardianInterface
from app.modules.maze.ui.maze_interface import MazeInterface
from app.modules.drink.ui.drink_interface import DrinkInterface
from app.modules.capture_pals.ui.capture_pals_interface import CapturePalsInterface

from app.modules.trigger.usecase.auto_f_usecase import AutoFModule
from app.modules.trigger.usecase.nita_auto_e_usecase import NitaAutoEModule

from app.presentation.views.additional_features_view import AdditionalFeaturesView
from .base_interface import BaseInterface
from app.presentation.views.subtask import SubTask
from app.infrastructure.logging.gui_logger import setup_ui_logger
from app.core.event_bus.global_task_bus import global_task_bus
from app.application.tasks.task_registry import ADDITIONAL_TASKS


class Additional(QFrame, BaseInterface):

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        BaseInterface.__init__(self)
        self.ui = AdditionalFeaturesView(self)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent
        self.task_coordinator = global_task_bus

        # 实例化各个功能页面
        self.page_trigger = TriggerInterface(self)
        self.page_fishing = FishingInterface(self)
        self.page_action = OperationInterface(self)
        self.page_water_bomb = WaterBombInterface(self)
        self.page_alien_guardian = AlienGuardianInterface(self)
        self.page_maze = MazeInterface(self)
        self.page_card = DrinkInterface(self)
        self.page_capture_pals = CapturePalsInterface(self)

        # 注册页面到 View
        self.ui.add_page(self.page_trigger, "page_trigger", self._ui_text('自动辅助', 'Trigger'))
        self.ui.add_page(self.page_fishing, "page_fishing", self._ui_text('钓鱼', 'Fishing'))
        self.ui.add_page(self.page_action, "page_action", self._ui_text('常规训练', 'Operation'))
        self.ui.add_page(self.page_water_bomb, "page_water_bomb", self._ui_text('心动水弹', 'Water Bomb'))
        self.ui.add_page(self.page_alien_guardian, "page_alien_guardian", self._ui_text('异星守护', 'Alien Guardian'))
        self.ui.add_page(self.page_maze, "page_maze", self._ui_text('验证战场', 'Maze'))
        self.ui.add_page(self.page_card, "page_card", self._ui_text('猜心对局', 'Card Match'))
        self.ui.add_page(self.page_capture_pals, "page_capture_pals", self._ui_text('抓帕鲁', 'Capture Pals'))

        # 触发器（自动辅助）独立管理，不受互斥限制
        self.f_thread = None
        self.nita_e_thread = None

        # 全局互斥任务调度中心状态
        self.current_running_task_id: str | None = None
        self.current_task_thread: SubTask | None = None

        # 日志配置
        self.task_loggers = {
            'fishing': setup_ui_logger("logger_fishing", self.page_fishing.textBrowser_log_fishing),
            'action': setup_ui_logger("logger_action", self.page_action.textBrowser_log_action),
            'water_bomb': setup_ui_logger("logger_water_bomb", self.page_water_bomb.textBrowser_log_water_bomb),
            'alien_guardian': setup_ui_logger("logger_alien_guardian", self.page_alien_guardian.textBrowser_log_alien_guardian),
            'maze': setup_ui_logger("logger_maze", self.page_maze.textBrowser_log_maze),
            'drink': setup_ui_logger("logger_drink", self.page_card.textBrowser_log_drink),
            'capture_pals': setup_ui_logger("logger_capture_pals", self.page_capture_pals.textBrowser_log_capture_pals),
            'trigger': setup_ui_logger("logger_trigger", self.page_trigger.textBrowser_log_trigger)
        }

        self._load_config()
        self._connect_to_slot()
        
        self.SegmentedWidget.setCurrentItem(self.page_trigger.objectName())
        self.stackedWidget.setCurrentWidget(self.page_trigger)
        StyleSheet.ADDITIONAL_FEATURES_INTERFACE.apply(self)

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    # ---------------- 统一任务调度中心 ----------------

    def _get_task_metadata(self):
        """Build metadata from centralized task registry."""
        meta = {}
        for definition in ADDITIONAL_TASKS:
            page = getattr(self, definition.page_attr)
            card = getattr(page, definition.card_widget_attr)
            log_browser = getattr(page, definition.log_widget_attr)
            meta[definition.id] = (
                definition.module_class,
                card,
                log_browser,
                definition.zh_name,
                definition.en_name,
                definition.start_button_attr,
                definition.page_attr,
            )
        return meta

    def _handle_universal_start_stop(self, clicked_task_id: str):
        if getattr(self, 'is_global_running', False):
            self.task_coordinator.request_stop()
            return

        if self.current_running_task_id is not None:
            if self.current_task_thread and self.current_task_thread.isRunning():
                self.current_task_thread.stop()
            return

        meta = self._get_task_metadata().get(clicked_task_id)
        if not meta: return

        module_class, card_widget, log_browser, zh_name, en_name, start_button_attr, page_attr = meta
        self.current_running_task_id = clicked_task_id
        specific_logger = self.task_loggers.get(clicked_task_id, self.logger)
        self.current_task_thread = SubTask(module_class, logger_instance=specific_logger)
        self.current_task_thread.is_running.connect(self._sync_all_ui_state)
        self.current_task_thread.start()

    def _sync_all_ui_state(self, is_running: bool):
        meta_dict = self._get_task_metadata()
        for task_id, (mod, card, log, zh, en, start_button_attr, page_attr) in meta_dict.items():
            page = getattr(self, page_attr, None)
            btn = getattr(page, start_button_attr, None) if page is not None else None

            if not btn: continue

            if is_running and self.current_running_task_id is not None:
                running_zh = meta_dict[self.current_running_task_id][3]
                running_en = meta_dict[self.current_running_task_id][4]
                btn.setText(self._ui_text(f'停止 {running_zh} (F8)', f'Stop {running_en} (F8)'))
                self.set_simple_card_enable(card, False)
            else:
                btn.setText(self._ui_text(f'开始{zh}', f'Start {en}'))
                self.set_simple_card_enable(card, True)

        if is_running:
            zh = meta_dict[self.current_running_task_id][3]
            en = meta_dict[self.current_running_task_id][4]
            self.task_coordinator.publish_state(True, zh, en, "additional")
        else:
            self.task_coordinator.publish_state(False, "", "", "additional")
            self.current_running_task_id = None
            self.current_task_thread = None

    def start_current_visible_task(self):
        if self.stackedWidget.currentWidget() == self.page_trigger:
            return
        current_page_name = self.stackedWidget.currentWidget().objectName()
        task_id = current_page_name.replace("page_", "")
        if task_id == "card": task_id = "drink"
        if task_id in self._get_task_metadata():
            self._handle_universal_start_stop(task_id)

    def _on_global_state_changed(self, is_running: bool, zh_name: str, en_name: str, source: str):
        if source == "additional": return
        self.is_global_running = is_running
        meta_dict = self._get_task_metadata()
        for task_id, (mod, card, log, zh, en, start_button_attr, page_attr) in meta_dict.items():
            page = getattr(self, page_attr, None)
            if not page: continue
            btn = getattr(page, start_button_attr, None)
            if not btn: continue
            if is_running:
                btn.setText(self._ui_text(f'停止 {zh_name} (F8)', f'Stop {en_name} (F8)'))
                self.set_simple_card_enable(card, False)
            else:
                btn.setText(self._ui_text(f'开始{zh}', f'Start {en}'))
                self.set_simple_card_enable(card, True)

    def _on_global_stop_request(self):
        if self.current_running_task_id is not None:
            self._handle_universal_start_stop(self.current_running_task_id)

    def _connect_to_slot(self):
        self.task_coordinator.state_changed.connect(self._on_global_state_changed)
        self.task_coordinator.stop_requested.connect(self._on_global_stop_request)
        
        self.page_trigger.SwitchButton_f.checkedChanged.connect(self.on_f_toggled)
        self.page_trigger.SwitchButton_e.checkedChanged.connect(self.on_e_toggled)
        
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)

        # 统一分发信号到中枢
        for definition in ADDITIONAL_TASKS:
            page = getattr(self, definition.page_attr, None)
            if page is None:
                continue
            button = getattr(page, definition.start_button_attr, None)
            if button is None:
                continue
            button.clicked.connect(lambda checked=False, task_id=definition.id: self._handle_universal_start_stop(task_id))

        self._connect_to_save_changed()

        # 钓鱼专用
        self.page_fishing.LineEdit_fish_key.editingFinished.connect(
            lambda: self.update_fish_key(self.page_fishing.LineEdit_fish_key.text()))
        signalBus.updateFishKey.connect(self.update_fish_key)

    def _load_config(self):
        for widget in self.findChildren(QWidget):
            config_item = getattr(config, widget.objectName(), None)
            if config_item:
                if isinstance(widget, CheckBox):
                    widget.setChecked(config_item.value)
                elif isinstance(widget, ComboBox):
                    widget.setCurrentIndex(config_item.value)
                elif isinstance(widget, LineEdit):
                    widget.setText(config_item.value)
                elif isinstance(widget, SpinBox):
                    widget.setValue(config_item.value)
                elif isinstance(widget, Slider):
                    widget.setValue(config_item.value)
        
        # 特殊处理
        self.page_fishing.update_label_color()
        if hasattr(self.page_water_bomb, 'load_config'): self.page_water_bomb.load_config()

    def _connect_to_save_changed(self):
        children_list = get_all_children(self)
        for children in children_list:
            if isinstance(children, CheckBox):
                children.stateChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, ComboBox):
                children.currentIndexChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, SpinBox):
                children.valueChanged.connect(partial(self.save_changed, children))
            elif isinstance(children, LineEdit):
                children.editingFinished.connect(partial(self.save_changed, children))
            elif isinstance(children, Slider):
                children.valueChanged.connect(partial(self.save_changed, children))

    def save_changed(self, widget, *args, **kwargs):
        config_item = getattr(config, widget.objectName(), None)
        if not config_item: return

        if isinstance(widget, SpinBox):
            config.set(config_item, widget.value())
        elif isinstance(widget, CheckBox):
            config.set(config_item, widget.isChecked())
        elif isinstance(widget, LineEdit):
            if widget.objectName().split('_')[1] == 'fish' and widget.objectName().split('_')[2] != 'key':
                if self.is_valid_format(widget.text()):
                    config.set(config_item, widget.text())
            else:
                config.set(config_item, widget.text())
        elif isinstance(widget, ComboBox):
            config.set(config_item, widget.currentIndex())
        elif isinstance(widget, Slider):
            config.set(config_item, widget.value())
            if hasattr(self.page_water_bomb, 'load_config'): self.page_water_bomb.load_config()

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.SegmentedWidget.setCurrentItem(widget.objectName())

    def is_valid_format(self, input_string):
        pattern = r'^(\d+),(\d+),(\d+)$'
        match = re.match(pattern, input_string)
        if match:
            int_values = [int(match.group(1)), int(match.group(2)), int(match.group(3))]
            if all(0 <= value <= 255 for value in int_values):
                return True
        return False

    def update_fish_key(self, key):
        choices = ["ctrl", "space", "shift"]
        best_match = process.extractOne(key, choices)
        if best_match[1] > 60:
            key = best_match[0]
        self.page_fishing.LineEdit_fish_key.setText(key.lower())
        config.set(config.LineEdit_fish_key, key.lower())

    def set_simple_card_enable(self, simple_card, enable: bool):
        children = get_all_children(simple_card)
        for child in children:
            if isinstance(child, (CheckBox, LineEdit, SpinBox, ComboBox)):
                if child.objectName() == 'LineEdit_fish_base' and enable:
                    continue
                child.setEnabled(enable)

    def turn_off_e_switch(self, is_running):
        if not is_running:
            self.page_trigger.SwitchButton_e.setChecked(False)

    def turn_off_f_switch(self, is_running):
        if not is_running:
            self.page_trigger.SwitchButton_f.setChecked(False)

    def on_f_toggled(self, isChecked: bool):
        if isChecked:
            trigger_logger = self.task_loggers.get('trigger', self.logger)
            self.f_thread = SubTask(AutoFModule, logger_instance=trigger_logger)
            self.f_thread.is_running.connect(self.turn_off_f_switch)
            self.f_thread.start()
        else:
            if self.f_thread and self.f_thread.isRunning():
                self.f_thread.stop()
                InfoBar.success(self._ui_text('自动按F', 'Auto F'), self._ui_text('已关闭', 'Disabled'), isClosable=True, duration=2000, parent=self)

    def on_e_toggled(self, isChecked: bool):
        if isChecked:
            trigger_logger = self.task_loggers.get('trigger', self.logger)
            self.nita_e_thread = SubTask(NitaAutoEModule, logger_instance=trigger_logger)
            self.nita_e_thread.is_running.connect(self.turn_off_e_switch)
            self.nita_e_thread.start()
        else:
            if self.nita_e_thread and self.nita_e_thread.isRunning():
                self.nita_e_thread.stop()
                InfoBar.success(self._ui_text('妮塔自动E', 'Nita Auto E'), self._ui_text('已关闭', 'Disabled'), isClosable=True, duration=2000, parent=self)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()


