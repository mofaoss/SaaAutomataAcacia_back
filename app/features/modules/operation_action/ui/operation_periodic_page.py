from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, ComboBox, SpinBox

from app.framework.ui.views.periodic_base import ModulePageBase


class OperationPage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_operation", parent=parent, host_context="periodic", use_default_layout=True)

        self.BodyLabel_7 = BodyLabel(self)
        self.BodyLabel_7.setObjectName("BodyLabel_7")
        self.SpinBox_action_times = SpinBox(self)
        self.SpinBox_action_times.setObjectName("SpinBox_action_times")
        self.SpinBox_action_times.setRange(1, 999)

        self.BodyLabel_22 = BodyLabel(self)
        self.BodyLabel_22.setObjectName("BodyLabel_22")
        self.ComboBox_run = ComboBox(self)
        self.ComboBox_run.setObjectName("ComboBox_run")

        self.BodyLabel_tip_action = BodyLabel(self)
        self.BodyLabel_tip_action.setObjectName("BodyLabel_tip_action")
        self.BodyLabel_tip_action.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_action.setWordWrap(True)

        self.main_layout.addLayout(self._row(self.BodyLabel_7, self.SpinBox_action_times))
        self.main_layout.addLayout(self._row(self.BodyLabel_22, self.ComboBox_run))
        self.main_layout.addWidget(self.BodyLabel_tip_action)
        self.finalize()

    @staticmethod
    def _row(label, edit):
        line = QHBoxLayout()
        line.addWidget(label, 1)
        line.addWidget(edit, 2)
        return line
