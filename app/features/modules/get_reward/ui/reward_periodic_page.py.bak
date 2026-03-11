from PySide6.QtCore import Qt
from qfluentwidgets import BodyLabel

from app.framework.ui.views.periodic_base import ModulePageBase


class RewardPage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_reward", parent=parent, host_context="periodic", use_default_layout=True)

        self.BodyLabel_reward_tip = BodyLabel(self)
        self.BodyLabel_reward_tip.setObjectName("BodyLabel_reward_tip")
        self.BodyLabel_reward_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_reward_tip.setWordWrap(True)
        self.BodyLabel_reward_tip.setText(
            "### Tips\n* Claim monthly card and daily rewards"
            if self._is_non_chinese_ui
            else "### 提示\n* 领取大月卡和日常奖励"
        )

        self.main_layout.addWidget(self.BodyLabel_reward_tip)
        self.finalize()

