from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, ComboBox, PushButton, SimpleCardWidget, TitleLabel)
from app.framework.ui.views.periodic_base import ModulePageBase

class MazeInterface(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_maze")

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.left_layout = QVBoxLayout()
        self.left_layout.setSpacing(8)
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(8)

        self.main_layout.addLayout(self.left_layout, 2)
        self.main_layout.addLayout(self.right_layout, 1)

        self._init_ui()
        self.apply_i18n()

    def _init_ui(self):
        self.SimpleCardWidget_maze = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_maze)

        self.BodyLabel_27 = BodyLabel(self.SimpleCardWidget_maze)
        self.BodyLabel_27.setObjectName("BodyLabel_27")
        self.ComboBox_mode_maze = ComboBox(self.SimpleCardWidget_maze)
        self.ComboBox_mode_maze.setObjectName("ComboBox_mode_maze")

        row = QHBoxLayout()
        row.addWidget(self.BodyLabel_27, 1)
        row.addWidget(self.ComboBox_mode_maze, 2)
        layout.addLayout(row)

        self.BodyLabel_tip_maze = BodyLabel(self.SimpleCardWidget_maze)
        self.BodyLabel_tip_maze.setObjectName("BodyLabel_tip_maze")
        self.BodyLabel_tip_maze.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_maze.setWordWrap(True)
        layout.addWidget(self.BodyLabel_tip_maze)
        layout.addStretch(1)

        self.PushButton_start_maze = PushButton(self)
        self.PushButton_start_maze.setObjectName("PushButton_start_maze")

        self.left_layout.addWidget(self.SimpleCardWidget_maze)
        self.left_layout.addWidget(self.PushButton_start_maze)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel_5 = TitleLabel(self.SimpleCardWidget_log)
        self.TitleLabel_5.setObjectName("TitleLabel_5")
        self.textBrowser_log_maze = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_maze.setObjectName("textBrowser_log_maze")
        self.textBrowser_log_maze.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_5)
        log_layout.addWidget(self.textBrowser_log_maze)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def apply_i18n(self):
        self.BodyLabel_tip_maze.setText(
            _("### Tips\n* This feature only supports the new Buff Maze, not the old maze\n* Single Run is suitable for first 3 stages; Repeat Run keeps farming the last stage\n* Select buffs in team setup first, then click Start Maze in Acacia\n* Recommended buffs: Skill-Chain Lightning and Shield-Steal\n* Team must include Chenxing - Qiongxian in the middle slot\n* Bring a strong support unit to reduce sudden deaths", msgid='tips_this_feature_only_supports_the_new_buff_maze_not_the_old_maze_single_run_is')
        )
        self.BodyLabel_27.setText(_("Run mode", msgid='run_mode'))
        self.TitleLabel_5.setText(_("Log", msgid='log'))
        self.PushButton_start_maze.setText(_('Start Maze', msgid='start_maze'))

        self.ComboBox_mode_maze.clear()
        self.ComboBox_mode_maze.addItems(
            [_("Single Run", msgid='single_run'),
             _("Repeat Run", msgid='repeat_run')]
        )



