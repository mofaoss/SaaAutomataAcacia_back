from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, ComboBox, PushButton, SimpleCardWidget, TitleLabel)
from app.infrastructure.config.app_config import config
from app.presentation.views.base_feature_interface import BaseFeatureInterface

class MazeInterface(BaseFeatureInterface):
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
            self._ui_text(
                "### 提示\n* 本功能只适用于增益迷宫（新迷宫），而非老迷宫\n* 运行模式中单次运行适合打前3关，重复运行则是一直刷最后一关\n* 进配队界面选好增益后再让安卡希雅的开始迷宫\n* 增益推荐配技能-爆电和护盾-夺取\n* 配队必须要有辰星-琼弦，且把角色放在中间位\n* 辅助有豹豹上豹豹防止暴毙",
                "### Tips\n* This feature only supports the new Buff Maze, not the old maze\n* Single Run is suitable for first 3 stages; Repeat Run keeps farming the last stage\n* Select buffs in team setup first, then click Start Maze in Acacia\n* Recommended buffs: Skill-Chain Lightning and Shield-Steal\n* Team must include Chenxing - Qiongxian in the middle slot\n* Bring a strong support unit to reduce sudden deaths"
            )
        )
        self.BodyLabel_27.setText(self._ui_text("运行模式", "Run mode"))
        self.TitleLabel_5.setText(self._ui_text("日志", "Log"))
        self.PushButton_start_maze.setText(self._ui_text('开始迷宫', 'Start Maze'))

        self.ComboBox_mode_maze.clear()
        self.ComboBox_mode_maze.addItems(
            [self._ui_text("单次运行", "Single Run"),
             self._ui_text("重复运行", "Repeat Run")]
        )

