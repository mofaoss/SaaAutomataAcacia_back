from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    PrimaryPushButton,
    PushButton,
    TextEdit,
)

from app.framework.ui.views.periodic_base import ModulePageBase


class CollectSuppliesPage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_3", parent=parent, host_context="periodic", use_default_layout=True)

        self.CheckBox_mail = CheckBox(self)
        self.CheckBox_mail.setObjectName("CheckBox_mail")
        self.CheckBox_fish_bait = CheckBox(self)
        self.CheckBox_fish_bait.setObjectName("CheckBox_fish_bait")
        self.CheckBox_dormitory = CheckBox(self)
        self.CheckBox_dormitory.setObjectName("CheckBox_dormitory")

        redeem_line = QHBoxLayout()
        self.CheckBox_redeem_code = CheckBox(self)
        self.CheckBox_redeem_code.setObjectName("CheckBox_redeem_code")
        self.PrimaryPushButton_import_codes = PrimaryPushButton(self)
        self.PrimaryPushButton_import_codes.setObjectName("PrimaryPushButton_import_codes")
        self.PushButton_reset_codes = PushButton(self)
        self.PushButton_reset_codes.setObjectName("PushButton_reset_codes")

        redeem_line.addWidget(self.CheckBox_redeem_code, 1)
        redeem_line.addWidget(self.PrimaryPushButton_import_codes)
        redeem_line.addWidget(self.PushButton_reset_codes)

        self.TextEdit_import_codes = TextEdit(self)
        self.TextEdit_import_codes.setObjectName("TextEdit_import_codes")
        self.TextEdit_import_codes.setMinimumHeight(60)
        self.TextEdit_import_codes.setMaximumHeight(120)

        self.BodyLabel_collect_supplies = BodyLabel(self)
        self.BodyLabel_collect_supplies.setObjectName("BodyLabel_collect_supplies")
        self.BodyLabel_collect_supplies.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_collect_supplies.setWordWrap(True)

        self.main_layout.addWidget(self.CheckBox_mail)
        self.main_layout.addWidget(self.CheckBox_fish_bait)
        self.main_layout.addWidget(self.CheckBox_dormitory)
        self.main_layout.addLayout(redeem_line)
        self.main_layout.addWidget(self.TextEdit_import_codes)
        self.main_layout.addWidget(self.BodyLabel_collect_supplies)
        self.finalize()
