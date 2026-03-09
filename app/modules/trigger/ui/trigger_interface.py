from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QFrame
from qfluentwidgets import (BodyLabel, SimpleCardWidget, StrongBodyLabel, SwitchButton)
from app.infrastructure.config.app_config import config
from app.presentation.views.base_feature_interface import BaseFeatureInterface

class TriggerInterface(BaseFeatureInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_trigger")
        self.item_count = 0

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
        self.SimpleCardWidget_trigger = SimpleCardWidget(self)
        self.card_layout = QVBoxLayout(self.SimpleCardWidget_trigger)

        self._add_switch_item(
            title_obj_name="StrongBodyLabel_trigger_f",
            desc_obj_name="BodyLabel_trigger_f",
            switch_obj_name="SwitchButton_f"
        )

        self._add_switch_item(
            title_obj_name="StrongBodyLabel_trigger_e",
            desc_obj_name="BodyLabel_trigger_e",
            switch_obj_name="SwitchButton_e"
        )

        self.BodyLabel_trigger_tip = BodyLabel(self.SimpleCardWidget_trigger)
        self.BodyLabel_trigger_tip.setObjectName("BodyLabel_trigger_tip")
        self.BodyLabel_trigger_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_trigger_tip.setWordWrap(True)
        self.BodyLabel_trigger_tip.setStyleSheet("margin-top: 10px;")
        self.card_layout.addWidget(self.BodyLabel_trigger_tip)
        self.card_layout.addStretch(1)

        self.left_layout.addWidget(self.SimpleCardWidget_trigger)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        from qfluentwidgets import TitleLabel
        from PySide6.QtWidgets import QTextBrowser
        self.TitleLabel_trigger_log = TitleLabel(self.SimpleCardWidget_log)
        self.textBrowser_log_trigger = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_trigger.setObjectName("textBrowser_log_trigger")
        self.textBrowser_log_trigger.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_trigger_log)
        log_layout.addWidget(self.textBrowser_log_trigger)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def _add_switch_item(self, title_obj_name: str, desc_obj_name: str, switch_obj_name: str):
        if self.item_count > 0:
            separator = QFrame(self.SimpleCardWidget_trigger)
            separator.setFrameShape(QFrame.Shape.HLine)
            separator.setStyleSheet(
                "QFrame { background-color: rgba(128, 128, 128, 0.2); border: none; max-height: 1px; margin-top: 8px; margin-bottom: 8px; }"
            )
            self.card_layout.addWidget(separator)

        row = QHBoxLayout()
        text_layout = QVBoxLayout()

        title_label = StrongBodyLabel(self.SimpleCardWidget_trigger)
        title_label.setObjectName(title_obj_name)
        desc_label = BodyLabel(self.SimpleCardWidget_trigger)
        desc_label.setObjectName(desc_obj_name)

        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)

        switch_btn = SwitchButton(self.SimpleCardWidget_trigger)
        switch_btn.setObjectName(switch_obj_name)

        row.addLayout(text_layout)
        row.addStretch(1)
        row.addWidget(switch_btn)

        self.card_layout.addLayout(row)

        setattr(self, title_obj_name, title_label)
        setattr(self, desc_obj_name, desc_label)
        setattr(self, switch_obj_name, switch_btn)

        self.item_count += 1

    def apply_i18n(self):
        self.StrongBodyLabel_trigger_f.setText(self._ui_text("自动采集或劝降", "Auto Collect"))
        self.BodyLabel_trigger_f.setText(self._ui_text("按钮出现时就按下F键", "Automatically press F when collect prompt appears"))
        self.StrongBodyLabel_trigger_e.setText(self._ui_text("自动妮塔悸响qte", "Nita E Auto QTE"))
        self.BodyLabel_trigger_e.setText(self._ui_text("到qte时机就按下E键", "Automatically press E during QTE stage"))
        self.TitleLabel_trigger_log.setText(self._ui_text("日志", "Log"))
        self.BodyLabel_trigger_tip.setText(
            self._ui_text(
                "### 提示\n* 先启动游戏再开启本功能\n* 开启后，遇到符合的情况就自动触发\n* 不影响手动游玩",
                "### Tips\n* Launch the game before enabling this feature\n* These are toggle switches. Once enabled, detection keeps running and triggers automatically when conditions match\n* It does not block manual gameplay, acting as semi-automation assistance"
            ))

