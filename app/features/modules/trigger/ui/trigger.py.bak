from PySide6.QtWidgets import QFrame, QVBoxLayout
from qfluentwidgets import InfoBar

from app.framework.infra.config.app_config import is_non_chinese_ui_language
from app.features.modules.trigger.usecase.auto_f_usecase import AutoFModule
from app.features.modules.trigger.usecase.nita_auto_e_usecase import NitaAutoEModule
from app.framework.ui.views.periodic_base import BaseInterface
from app.features.modules.fishing.ui.subtask import SubTask
from .trigger_view import TriggerView


class Trigger(QFrame, BaseInterface):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        BaseInterface.__init__(self)
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
        self.TitleLabel_trigger.setText(_("Trigger List", msgid='trigger_list'))
        self.StrongBodyLabel.setText(_("Auto Collect", msgid='auto_collect'))
        self.BodyLabel.setText(_("Automatically press F when collect prompt appears", msgid='automatically_press_f_when_collect_prompt_appears'))
        self.StrongBodyLabel_2.setText(_("Nita E Auto QTE", msgid='nita_e_auto_qte'))
        self.BodyLabel_2.setText(_("Automatically press E during QTE stage", msgid='automatically_press_e_during_qte_stage'))
        self.BodyLabel_trigger_tip.setText(
            _("### Tips\n* Launch the game before enabling this feature\n* These are toggle switches. Once enabled, detection keeps running and triggers automatically when conditions match\n* It does not block manual gameplay, acting as semi-automation assistance", msgid='tips_launch_the_game_before_enabling_this_feature_these_are_toggle_switches_once'))

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
            if hasattr(self, 'f_thread') and self.f_thread.isRunning():
                self.f_thread.stop()
                InfoBar.success(
                    _('Auto F', msgid='auto_f'),
                    _('Disabled', msgid='disabled'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    _('Error', msgid='error'),
                    _('Game/Task is not running', msgid='game_task_is_not_running'),
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
            if hasattr(self, 'nita_e_thread') and self.nita_e_thread.isRunning():
                self.nita_e_thread.stop()
                InfoBar.success(
                    _('Nita Auto E', msgid='nita_auto_e'),
                    _('Disabled', msgid='disabled'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    _('Error', msgid='error'),
                    _('Game/Task is not running', msgid='game_task_is_not_running'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )



