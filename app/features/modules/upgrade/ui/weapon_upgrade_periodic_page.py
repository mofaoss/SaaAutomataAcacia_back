from PySide6.QtCore import Qt
from qfluentwidgets import BodyLabel

from app.framework.ui.views.periodic_base import ModulePageBase


class WeaponUpgradePage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_weapon", parent=parent, host_context="periodic", use_default_layout=True)

        self.BodyLabel_weapon_tip = BodyLabel(self)
        self.BodyLabel_weapon_tip.setObjectName("BodyLabel_weapon_tip")
        self.BodyLabel_weapon_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_weapon_tip.setWordWrap(True)
        self.main_layout.addWidget(self.BodyLabel_weapon_tip)
        self.finalize()
