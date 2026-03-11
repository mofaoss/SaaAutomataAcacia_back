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
        self.apply_i18n()
        self.finalize()

    def apply_i18n(self):
        self.CheckBox_mail.setText(_("Claim Mail", msgid='claim_mail'))
        self.CheckBox_fish_bait.setText(_("Claim Bait", msgid='claim_bait'))
        self.CheckBox_dormitory.setText(_("Dorm Shards", msgid='dorm_shards'))
        self.CheckBox_redeem_code.setText(_("Redeem Codes", msgid='redeem_codes'))
        self.PrimaryPushButton_import_codes.setText(_("Import", msgid='import'))
        self.PushButton_reset_codes.setText(_("Reset", msgid='reset'))
        self.BodyLabel_collect_supplies.setText(
            "### Tips\n* Default: Always claim Supply Station stamina and friend stamina \n* Enable \"Redeem Code\" to fetch and redeem online codes automatically\n* Online codes are maintained by developers and may not always be updated in time\n* You can import a txt file for batch redeem (one code per line)"
            if self._is_non_chinese_ui
            else "### 提示 \n* 默认必领供应站体力和好友体力\n* 勾选“领取兑换码”会自动拉取在线兑换码进行兑换\n* 在线兑换码由开发者维护，更新不一定及时\n* 导入txt文本文件可以批量使用用户兑换码，txt需要一行一个兑换码"
        )


