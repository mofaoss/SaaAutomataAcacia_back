from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PrimaryPushButton, SimpleCardWidget


class MassagingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("page_massaging")

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        self.left_layout = QVBoxLayout()
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)

        self.SimpleCardWidget_massaging = SimpleCardWidget(self)
        card_layout = QVBoxLayout(self.SimpleCardWidget_massaging)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(8)

        title = BodyLabel("按摩模块参数由配置项控制", self.SimpleCardWidget_massaging)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.PushButton_start_massaging = PrimaryPushButton("开始按摩", self.SimpleCardWidget_massaging)
        self.PushButton_start_massaging.setObjectName("PushButton_start_massaging")

        card_layout.addWidget(title)
        card_layout.addWidget(self.PushButton_start_massaging)
        card_layout.addStretch(1)

        self.left_layout.addWidget(self.SimpleCardWidget_massaging)
        self.left_layout.addStretch(1)

        self.right_layout = QVBoxLayout()
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

        self.main_layout.addLayout(self.left_layout, 1)
        self.main_layout.addLayout(self.right_layout, 0)

    def bind_host_context(self, _host_context):
        return None

