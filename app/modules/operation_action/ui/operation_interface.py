from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, ComboBox, PushButton, SimpleCardWidget, SpinBox, TitleLabel)
from app.infrastructure.config.app_config import config
from app.presentation.views.base_feature_interface import BaseFeatureInterface

class OperationInterface(BaseFeatureInterface):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_action")

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
        self.SimpleCardWidget_action = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_action)

        self.BodyLabel_4 = BodyLabel(self.SimpleCardWidget_action)
        self.SpinBox_action_times = SpinBox(self.SimpleCardWidget_action)
        self.SpinBox_action_times.setObjectName("SpinBox_action_times")
        self.SpinBox_action_times.setValue(20)
        layout.addLayout(self._row(self.BodyLabel_4, self.SpinBox_action_times))

        self.BodyLabel_22 = BodyLabel(self.SimpleCardWidget_action)
        self.ComboBox_run = ComboBox(self.SimpleCardWidget_action)
        self.ComboBox_run.setObjectName("ComboBox_run")
        layout.addLayout(self._row(self.BodyLabel_22, self.ComboBox_run))

        self.BodyLabel_tip_action = BodyLabel(self.SimpleCardWidget_action)
        self.BodyLabel_tip_action.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(self.BodyLabel_tip_action)
        layout.addStretch(1)

        self.PushButton_start_action = PushButton(self)
        self.PushButton_start_action.setObjectName("PushButton_start_action")

        self.left_layout.addWidget(self.SimpleCardWidget_action)
        self.left_layout.addWidget(self.PushButton_start_action)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        from PySide6.QtWidgets import QTextBrowser
        self.TitleLabel_2 = TitleLabel(self.SimpleCardWidget_log)
        self.textBrowser_log_action = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_action.setObjectName("textBrowser_log_action")
        self.textBrowser_log_action.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_2)
        log_layout.addWidget(self.textBrowser_log_action)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def _row(self, left: QWidget, right: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        return row

    def apply_i18n(self):
        self.BodyLabel_tip_action.setText(
            "### Tips\n* Auto-run operation from the lobby page\n* Repeats the first training stage for specified times with no stamina cost\n* Useful for weekly pass mission count"
            if self._is_non_chinese_ui else
            "### 提示\n* 重复刷指定次数无需体力的实战训练第一关\n* 用于完成凭证20次常规行动周常任务"
        )
        run_items = ["切换疾跑", "按住疾跑"] if not self._is_non_chinese_ui else ["Toggle Sprint", "Hold Sprint"]
        self.ComboBox_run.clear()
        self.ComboBox_run.addItems(run_items)

        self.PushButton_start_action.setText(self._ui_text('开始常规训练', 'Start Operation'))
        self.BodyLabel_4.setText(self._ui_text("刷取次数", "Run count"))
        self.BodyLabel_22.setText(self._ui_text("疾跑方式", "Sprint mode"))
        self.TitleLabel_2.setText(self._ui_text("日志", "Log"))

