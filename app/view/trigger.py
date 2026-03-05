from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import InfoBar

from app.common.config import is_non_chinese_ui_language
from app.modules.trigger.auto_f import AutoFModule
from app.modules.trigger.nita_auto_e import NitaAutoEModule
from .base_interface import BaseInterface
from app.view.subtask import SubTask
from app.view.trigger_view import TriggerView


class Trigger(QFrame, BaseInterface):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.ui = TriggerView(self)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.collect_thread = None
        self.collect_thread_running = False

        self._initWidget()
        self._connect_to_slot()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _initWidget(self):
        self.TitleLabel_trigger.setText(self._ui_text("自动辅助", "Trigger List"))
        self.StrongBodyLabel.setText(self._ui_text("自动采集或劝降", "Auto Collect"))
        self.BodyLabel.setText(self._ui_text("按钮出现时就按下F键", "Automatically press F when collect prompt appears"))
        self.StrongBodyLabel_2.setText(self._ui_text("自动妮塔悸响qte", "Nita E Auto QTE"))
        self.BodyLabel_2.setText(self._ui_text("到qte时机就按下E键", "Automatically press E during QTE stage"))
        self.BodyLabel_trigger_tip.setText(
            self._ui_text(
                "### 提示\n* 先启动游戏再开启本功能\n* 开启后，遇到符合的情况就自动触发\n* 不影响手动游玩",
                "### Tips\n* Launch the game before enabling this feature\n* These are toggle switches. Once enabled, detection keeps running and triggers automatically when conditions match\n* It does not block manual gameplay, acting as semi-automation assistance"
            ))

    def _connect_to_slot(self):
        self.SwitchButton_f.checkedChanged.connect(self.on_f_toggled)
        self.SwitchButton_e.checkedChanged.connect(self.on_e_toggled)

    def turn_off_e_switch(self, is_running):
        if not is_running:
            self.SwitchButton_e.setChecked(False)

    def turn_off_f_switch(self, is_running):
        if not is_running:
            self.SwitchButton_f.setChecked(False)

    def on_f_toggled(self, isChecked: bool):
        """自动采集 F"""
        if isChecked:
            self.f_thread = SubTask(AutoFModule)
            self.f_thread.is_running.connect(self.turn_off_f_switch)
            self.f_thread.start()
        else:
            # ✅ 修复：使用官方的 isRunning() 方法判断，而不是访问自定义的属性
            if hasattr(self, 'f_thread') and self.f_thread.isRunning():
                self.f_thread.stop()
                InfoBar.success(
                    self._ui_text('自动按F', 'Auto F'),
                    self._ui_text('已关闭', 'Disabled'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    self._ui_text('错误', 'Error'),
                    self._ui_text('游戏未打开或任务未运行', 'Game/Task is not running'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )

    def on_e_toggled(self, isChecked: bool):
        """妮塔自动 E"""
        if isChecked:
            self.nita_e_thread = SubTask(NitaAutoEModule)
            self.nita_e_thread.is_running.connect(self.turn_off_e_switch)
            self.nita_e_thread.start()
        else:
            # ✅ 修复：同上
            if hasattr(self, 'nita_e_thread') and self.nita_e_thread.isRunning():
                self.nita_e_thread.stop()
                InfoBar.success(
                    self._ui_text('妮塔自动E', 'Nita Auto E'),
                    self._ui_text('已关闭', 'Disabled'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    self._ui_text('错误', 'Error'),
                    self._ui_text('游戏未打开或任务未运行', 'Game/Task is not running'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
