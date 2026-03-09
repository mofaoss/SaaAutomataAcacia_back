# coding: utf-8
from enum import Enum

from PySide6.QtCore import QFile

from qfluentwidgets import StyleSheetBase, Theme, qconfig
from app.framework.infra.runtime.paths import PROJECT_ROOT


class StyleSheet(StyleSheetBase, Enum):
    """ Style sheet  """

    # TODO: Add your qss here
    LINK_CARD = "link_card"
    SAMPLE_CARD = "sample_card"
    SETTING_INTERFACE = "setting_interface"
    VIEW_INTERFACE = "view_interface"
    DISPLAY_INTERFACE = "display_interface"
    PERIODIC_TASKS_INTERFACE = "periodic_tasks_interface"
    ON_DEMAND_TASKS_INTERFACE = "on_demand_tasks_interface"
    HELP_INTERFACE = "help_interface"
    OCR_TABLE = "ocr_table"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        qrc_path = f":/resources/qss/{theme.value.lower()}/{self.value}.qss"
        if QFile.exists(qrc_path):
            return qrc_path

        file_path = PROJECT_ROOT / "resources" / "qss" / theme.value.lower() / f"{self.value}.qss"
        return str(file_path)
