from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
)

from app.framework.ui.views.periodic_base import ModulePageBase


class EnterGamePage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_5", parent=parent, host_context="periodic", use_default_layout=True)

        top_line = QHBoxLayout()
        self.StrongBodyLabel_4 = StrongBodyLabel(self)
        self.StrongBodyLabel_4.setObjectName("StrongBodyLabel_4")
        self.PrimaryPushButton_path_tutorial = PrimaryPushButton(self)
        self.PrimaryPushButton_path_tutorial.setObjectName("PrimaryPushButton_path_tutorial")
        top_line.addWidget(self.StrongBodyLabel_4)
        top_line.addWidget(self.PrimaryPushButton_path_tutorial)

        self.LineEdit_game_directory = LineEdit(self)
        self.LineEdit_game_directory.setEnabled(False)
        self.LineEdit_game_directory.setObjectName("LineEdit_game_directory")

        action_line = QHBoxLayout()
        self.CheckBox_open_game_directly = CheckBox(self)
        self.CheckBox_open_game_directly.setObjectName("CheckBox_open_game_directly")
        self.PushButton_select_directory = PushButton(self)
        self.PushButton_select_directory.setObjectName("PushButton_select_directory")
        action_line.addWidget(self.CheckBox_open_game_directly, 1)
        action_line.addWidget(self.PushButton_select_directory)

        self.BodyLabel_enter_tip = BodyLabel(self)
        self.BodyLabel_enter_tip.setObjectName("BodyLabel_enter_tip")
        self.BodyLabel_enter_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_enter_tip.setWordWrap(True)

        self.main_layout.addLayout(top_line)
        self.main_layout.addWidget(self.LineEdit_game_directory)
        self.main_layout.addLayout(action_line)
        self.main_layout.addWidget(self.BodyLabel_enter_tip)
        self.finalize()
