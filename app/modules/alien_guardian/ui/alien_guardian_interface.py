from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, ComboBox, PushButton, SimpleCardWidget, TitleLabel)
from app.infrastructure.config.app_config import config
from app.presentation.views.base_feature_interface import BaseFeatureInterface

class AlienGuardianInterface(BaseFeatureInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_alien_guardian")

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
        self.SimpleCardWidget_alien_guardian = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_alien_guardian)

        self.BodyLabel_25 = BodyLabel(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_25.setObjectName("BodyLabel_25")
        self.ComboBox_mode = ComboBox(self.SimpleCardWidget_alien_guardian)
        self.ComboBox_mode.setObjectName("ComboBox_mode")

        row = QHBoxLayout()
        row.addWidget(self.BodyLabel_25, 1)
        row.addWidget(self.ComboBox_mode, 2)
        layout.addLayout(row)

        self.BodyLabel_tip_alien = BodyLabel(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_tip_alien.setObjectName("BodyLabel_tip_alien")
        self.BodyLabel_tip_alien.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_alien.setWordWrap(True)
        layout.addWidget(self.BodyLabel_tip_alien)
        layout.addStretch(1)

        self.PushButton_start_alien_guardian = PushButton(self)
        self.PushButton_start_alien_guardian.setObjectName("PushButton_start_alien_guardian")

        self.left_layout.addWidget(self.SimpleCardWidget_alien_guardian)
        self.left_layout.addWidget(self.PushButton_start_alien_guardian)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel_4 = TitleLabel(self.SimpleCardWidget_log)
        self.TitleLabel_4.setObjectName("TitleLabel_4")
        self.textBrowser_log_alien_guardian = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_alien_guardian.setObjectName("textBrowser_log_alien_guardian")
        self.textBrowser_log_alien_guardian.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_4)
        log_layout.addWidget(self.textBrowser_log_alien_guardian)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def apply_i18n(self):
        self.BodyLabel_tip_alien.setText(
            self._ui_text(
                "### 提示\n* 开始战斗后再点击开始\n* 常驻伙伴推荐带钢珠和炽热投手\n* 闯关模式为半自动一关一关打。需要手动开枪，手动选择下一关",
                "### Tips\n* Click Start after battle begins\n* Recommended support pals: Steel Shot and Blazing Pitcher\n* Stage mode is semi-automatic: manual shooting and manual next-stage selection are required"
            )
        )
        self.BodyLabel_25.setText(self._ui_text("运行模式", "Run mode"))
        self.TitleLabel_4.setText(self._ui_text("日志", "Log"))
        self.PushButton_start_alien_guardian.setText(self._ui_text('开始异星守护', 'Start Alien Guardian'))

        self.ComboBox_mode.clear()
        self.ComboBox_mode.addItems(
            [self._ui_text("无尽模式", "Endless Mode"),
             self._ui_text("闯关模式", "Stage Mode")]
        )

