from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SimpleCardWidget, StrongBodyLabel, SwitchButton, TitleLabel


class TriggerItemCard(SimpleCardWidget):
    def __init__(
        self,
        title_object_name: str,
        desc_object_name: str,
        switch_object_name: str,
        parent=None,
    ):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(11, 11, 11, 11)
        main_layout.setSpacing(6)

        text_layout = QVBoxLayout()
        title = StrongBodyLabel(self)
        title.setObjectName(title_object_name)
        desc = BodyLabel(self)
        desc.setObjectName(desc_object_name)
        text_layout.addWidget(title)
        text_layout.addWidget(desc)

        switch = SwitchButton(self)
        switch.setObjectName(switch_object_name)

        main_layout.addLayout(text_layout)
        main_layout.addStretch(1)
        main_layout.addWidget(switch)

        self.title_label = title
        self.desc_label = desc
        self.switch = switch


class TriggerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("trigger")

        self.gridLayout = QVBoxLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setSpacing(0)

        self.SimpleCardWidget = SimpleCardWidget(self)
        self.SimpleCardWidget.setObjectName("SimpleCardWidget")
        card_layout = QVBoxLayout(self.SimpleCardWidget)

        self.TitleLabel_trigger = TitleLabel(self.SimpleCardWidget)
        self.TitleLabel_trigger.setObjectName("TitleLabel_trigger")

        self.SimpleCardWidget_f = TriggerItemCard(
            title_object_name="StrongBodyLabel",
            desc_object_name="BodyLabel",
            switch_object_name="SwitchButton_f",
            parent=self.SimpleCardWidget,
        )
        self.SimpleCardWidget_f.setObjectName("SimpleCardWidget_f")

        self.SimpleCardWidget_f_2 = TriggerItemCard(
            title_object_name="StrongBodyLabel_2",
            desc_object_name="BodyLabel_2",
            switch_object_name="SwitchButton_e",
            parent=self.SimpleCardWidget,
        )
        self.SimpleCardWidget_f_2.setObjectName("SimpleCardWidget_f_2")

        self.BodyLabel_trigger_tip = BodyLabel(self.SimpleCardWidget)
        self.BodyLabel_trigger_tip.setObjectName("BodyLabel_trigger_tip")
        self.BodyLabel_trigger_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_trigger_tip.setWordWrap(True)

        card_layout.addWidget(self.TitleLabel_trigger)
        card_layout.addWidget(self.SimpleCardWidget_f)
        card_layout.addWidget(self.SimpleCardWidget_f_2)
        card_layout.addWidget(self.BodyLabel_trigger_tip)
        card_layout.addStretch(1)

        self.gridLayout.addWidget(self.SimpleCardWidget)

        self.StrongBodyLabel = self.SimpleCardWidget_f.title_label
        self.BodyLabel = self.SimpleCardWidget_f.desc_label
        self.SwitchButton_f = self.SimpleCardWidget_f.switch

        self.StrongBodyLabel_2 = self.SimpleCardWidget_f_2.title_label
        self.BodyLabel_2 = self.SimpleCardWidget_f_2.desc_label
        self.SwitchButton_e = self.SimpleCardWidget_f_2.switch
