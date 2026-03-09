import re
from functools import partial

from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout
from rapidfuzz import process
from qfluentwidgets import SpinBox, CheckBox, ComboBox, LineEdit, Slider, InfoBar

from app.framework.infra.config.app_config import config
from app.framework.infra.events.signal_bus import signalBus
from app.framework.ui.shared.style_sheet import StyleSheet
from app.features.utils.ui import get_all_children

from app.features.modules.trigger.usecase.auto_f_usecase import AutoFModule
from app.features.modules.trigger.usecase.nita_auto_e_usecase import NitaAutoEModule

from app.framework.ui.views.additional_features_view import AdditionalFeaturesView
from .base_interface import BaseInterface
from app.features.modules.fishing.ui.subtask import SubTask
from app.framework.infra.logging.gui_logger import setup_ui_logger
from app.framework.core.event_bus.global_task_bus import global_task_bus
from app.framework.application.modules import HostContext, get_on_demand_module_specs
from app.framework.application.scheduling.on_demand_runner import OnDemandRunner


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

        self.module_specs = get_on_demand_module_specs(include_passive=True)
        self.module_pages = {}
        self._task_metadata = {}
        self._page_name_to_task_id = {}
        self._mount_module_pages()
        self._build_task_metadata()

        # 触发器（自动辅助）独立管理，不受互斥限制
        self.f_thread = None
        self.nita_e_thread = None

        # 全局互斥任务调度中心状态
        self.on_demand_runner = OnDemandRunner()

        # 所有 additional 模块统一共享日志
        self.shared_logger = setup_ui_logger(
            "logger_additional_shared",
            self.ui.textBrowser_shared_log,
        )
        self.task_loggers = {
            spec.id: self.shared_logger for spec in self.module_specs
        }

        self._load_config()
        self._connect_to_slot()
        self.ui.sharedLogTitle.setText(self._ui_text("共享日志", "Shared Log"))

        if hasattr(self, "page_trigger"):
            self.SegmentedWidget.setCurrentItem(self.page_trigger.objectName())
            self.stackedWidget.setCurrentWidget(self.page_trigger)
        elif self.stackedWidget.count() > 0:
            first_page = self.stackedWidget.widget(0)
            self.SegmentedWidget.setCurrentItem(first_page.objectName())
            self.stackedWidget.setCurrentWidget(first_page)
        StyleSheet.ADDITIONAL_FEATURES_INTERFACE.apply(self)

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    # ---------------- 统一任务调度中心 ----------------

    def _mount_module_pages(self):
        for spec in self.module_specs:
            page = spec.ui_factory(self, HostContext.ON_DEMAND)
            page_name = page.objectName()
            self.module_pages[spec.id] = page

            self.ui.add_page(
                page,
                page_name,
                self._ui_text(spec.zh_name, spec.en_name),
            )

            bindings = spec.ui_bindings
            if bindings is not None and bindings.page_attr:
                setattr(self, bindings.page_attr, page)

            # additional 统一共享日志，模块内日志卡片不再作为独立日志出口
            local_log_card = getattr(page, "SimpleCardWidget_log", None)
            if local_log_card is not None:
                local_log_card.setVisible(False)

            if not spec.passive and spec.module_class is not None:
                self._page_name_to_task_id[page_name] = spec.id

    def _build_task_metadata(self):
        for spec in self.module_specs:
            if spec.passive or spec.module_class is None:
                continue
            bindings = spec.ui_bindings
            if bindings is None:
                continue
            page = getattr(self, bindings.page_attr, None)
            if page is None:
                continue

            self._task_metadata[spec.id] = {
                "module_class": spec.module_class,
                "zh_name": spec.zh_name,
                "en_name": spec.en_name,
                "page_attr": bindings.page_attr,
                "start_button_attr": bindings.start_button_attr,
                "card_widget_attr": bindings.card_widget_attr,
            }

    def _get_task_metadata(self):
        return self._task_metadata

    def _handle_universal_start_stop(self, clicked_task_id: str):
        self.on_demand_runner.toggle(
            clicked_task_id,
            is_global_running=getattr(self, "is_global_running", False),
            request_global_stop=self.task_coordinator.request_stop,
            get_module_class=lambda task_id: (
                self._get_task_metadata().get(task_id, {}).get("module_class")
            ),
            get_logger=lambda task_id: self.task_loggers.get(task_id, self.logger),
            build_thread=lambda module_class, logger: SubTask(module_class, logger_instance=logger),
            on_thread_state_changed=self._sync_all_ui_state,
        )

    def _sync_all_ui_state(self, is_running: bool):
        meta_dict = self._get_task_metadata()
        running_task_id = self.on_demand_runner.state.current_task_id
        for task_id, meta in meta_dict.items():
            page = getattr(self, meta["page_attr"], None)
            btn = getattr(page, meta["start_button_attr"], None) if page is not None else None
            card = getattr(page, meta["card_widget_attr"], None) if page is not None else None

            if not btn:
                continue

            if is_running and running_task_id is not None:
                running_zh = meta_dict[running_task_id]["zh_name"]
                running_en = meta_dict[running_task_id]["en_name"]
                btn.setText(self._ui_text(f'停止 {running_zh} (F8)', f'Stop {running_en} (F8)'))
                if card is not None:
                    self.set_simple_card_enable(card, False)
            else:
                btn.setText(self._ui_text(f'开始{meta["zh_name"]}', f'Start {meta["en_name"]}'))
                if card is not None:
                    self.set_simple_card_enable(card, True)

        if is_running and running_task_id is not None:
            zh = meta_dict[running_task_id]["zh_name"]
            en = meta_dict[running_task_id]["en_name"]
            self.task_coordinator.publish_state(True, zh, en, "additional")
        else:
            self.task_coordinator.publish_state(False, "", "", "additional")
            self.on_demand_runner.clear()

    def start_current_visible_task(self):
        current_page = self.stackedWidget.currentWidget()
        if current_page is None:
            return
        if hasattr(self, "page_trigger") and current_page == self.page_trigger:
            return
        current_page_name = current_page.objectName()
        task_id = self._page_name_to_task_id.get(current_page_name)
        if task_id in self._get_task_metadata():
            self._handle_universal_start_stop(task_id)

    def _on_global_state_changed(self, is_running: bool, zh_name: str, en_name: str, source: str):
        if source == "additional":
            return
        self.is_global_running = is_running
        meta_dict = self._get_task_metadata()
        for _, meta in meta_dict.items():
            page = getattr(self, meta["page_attr"], None)
            if not page:
                continue
            btn = getattr(page, meta["start_button_attr"], None)
            card = getattr(page, meta["card_widget_attr"], None)
            if not btn:
                continue
            if is_running:
                btn.setText(self._ui_text(f'停止 {zh_name} (F8)', f'Stop {en_name} (F8)'))
                if card is not None:
                    self.set_simple_card_enable(card, False)
            else:
                btn.setText(self._ui_text(f'开始{meta["zh_name"]}', f'Start {meta["en_name"]}'))
                if card is not None:
                    self.set_simple_card_enable(card, True)

    def _on_global_stop_request(self):
        if self.on_demand_runner.state.current_task_id is not None:
            self.on_demand_runner.stop_current()

    def _connect_to_slot(self):
        self.task_coordinator.state_changed.connect(self._on_global_state_changed)
        self.task_coordinator.stop_requested.connect(self._on_global_stop_request)

        if hasattr(self, "page_trigger"):
            self.page_trigger.SwitchButton_f.checkedChanged.connect(self.on_f_toggled)
            self.page_trigger.SwitchButton_e.checkedChanged.connect(self.on_e_toggled)
        
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)

        # 统一分发信号到中枢
        for task_id, meta in self._get_task_metadata().items():
            page = getattr(self, meta["page_attr"], None)
            if page is None:
                continue
            button = getattr(page, meta["start_button_attr"], None)
            if button is None:
                continue
            button.clicked.connect(
                lambda checked=False, selected_task_id=task_id: self._handle_universal_start_stop(selected_task_id)
            )

        self._connect_to_save_changed()

        # 钓鱼专用
        if hasattr(self, "page_fishing"):
            self.page_fishing.LineEdit_fish_key.editingFinished.connect(
                lambda: self.update_fish_key(self.page_fishing.LineEdit_fish_key.text())
            )
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
        
        for page in self.module_pages.values():
            if hasattr(page, 'update_label_color'):
                page.update_label_color()
            if hasattr(page, 'load_config'):
                page.load_config()

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
            if hasattr(self, "page_water_bomb") and hasattr(self.page_water_bomb, 'load_config'):
                self.page_water_bomb.load_config()

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
        if not hasattr(self, "page_fishing"):
            return
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
        if not is_running and hasattr(self, "page_trigger"):
            self.page_trigger.SwitchButton_e.setChecked(False)

    def turn_off_f_switch(self, is_running):
        if not is_running and hasattr(self, "page_trigger"):
            self.page_trigger.SwitchButton_f.setChecked(False)

    def on_f_toggled(self, isChecked: bool):
        if isChecked:
            trigger_logger = self.shared_logger
            self.f_thread = SubTask(AutoFModule, logger_instance=trigger_logger)
            self.f_thread.is_running.connect(self.turn_off_f_switch)
            self.f_thread.start()
        else:
            if self.f_thread and self.f_thread.isRunning():
                self.f_thread.stop()
                InfoBar.success(self._ui_text('自动按F', 'Auto F'), self._ui_text('已关闭', 'Disabled'), isClosable=True, duration=2000, parent=self)

    def on_e_toggled(self, isChecked: bool):
        if isChecked:
            trigger_logger = self.shared_logger
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

    def get_shared_log_browser(self):
        return self.ui.textBrowser_shared_log


