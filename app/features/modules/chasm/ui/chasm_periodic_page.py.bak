from PySide6.QtCore import Qt
from qfluentwidgets import BodyLabel

from app.framework.ui.views.periodic_base import ModulePageBase


class ChasmPage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_chasm", parent=parent, host_context="periodic", use_default_layout=True)

        self.BodyLabel_chasm_tip = BodyLabel(self)
        self.BodyLabel_chasm_tip.setObjectName("BodyLabel_chasm_tip")
        self.BodyLabel_chasm_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_chasm_tip.setWordWrap(True)
        self.BodyLabel_chasm_tip.setText(
            "### Tips\n* Neural Simulation opens every Tuesday at 10:00"
            if self._is_non_chinese_ui
            else "### 提示\n* 拟境每周2的10:00开启"
        )

        self.main_layout.addWidget(self.BodyLabel_chasm_tip)
        self.finalize()

