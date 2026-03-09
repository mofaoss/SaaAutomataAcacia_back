from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import BodyLabel, CheckBox, LineEdit, StrongBodyLabel

from app.framework.ui.views.periodic_base import ModulePageBase


class PersonPage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_4", parent=parent, host_context="periodic", use_default_layout=True)

        self.StrongBodyLabel_3 = StrongBodyLabel(self)
        self.StrongBodyLabel_3.setObjectName("StrongBodyLabel_3")

        self.BodyLabel_3 = BodyLabel(self)
        self.BodyLabel_3.setObjectName("BodyLabel_3")
        self.LineEdit_c1 = LineEdit(self)
        self.LineEdit_c1.setObjectName("LineEdit_c1")

        self.BodyLabel_4 = BodyLabel(self)
        self.BodyLabel_4.setObjectName("BodyLabel_4")
        self.LineEdit_c2 = LineEdit(self)
        self.LineEdit_c2.setObjectName("LineEdit_c2")

        self.BodyLabel_5 = BodyLabel(self)
        self.BodyLabel_5.setObjectName("BodyLabel_5")
        self.LineEdit_c3 = LineEdit(self)
        self.LineEdit_c3.setObjectName("LineEdit_c3")

        self.BodyLabel_8 = BodyLabel(self)
        self.BodyLabel_8.setObjectName("BodyLabel_8")
        self.LineEdit_c4 = LineEdit(self)
        self.LineEdit_c4.setObjectName("LineEdit_c4")

        self.CheckBox_is_use_chip = CheckBox(self)
        self.CheckBox_is_use_chip.setObjectName("CheckBox_is_use_chip")

        self.BodyLabel_person_tip = BodyLabel(self)
        self.BodyLabel_person_tip.setObjectName("BodyLabel_person_tip")
        self.BodyLabel_person_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_person_tip.setWordWrap(True)

        self.main_layout.addWidget(self.StrongBodyLabel_3)
        self.main_layout.addLayout(self._line(self.BodyLabel_3, self.LineEdit_c1))
        self.main_layout.addLayout(self._line(self.BodyLabel_4, self.LineEdit_c2))
        self.main_layout.addLayout(self._line(self.BodyLabel_5, self.LineEdit_c3))
        self.main_layout.addLayout(self._line(self.BodyLabel_8, self.LineEdit_c4))
        self.main_layout.addWidget(self.CheckBox_is_use_chip)
        self.main_layout.addWidget(self.BodyLabel_person_tip)
        self.finalize()

    @staticmethod
    def _line(label, edit):
        line = QHBoxLayout()
        line.addWidget(label, 1)
        line.addWidget(edit, 2)
        return line
