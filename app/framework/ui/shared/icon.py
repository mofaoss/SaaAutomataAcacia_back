# coding: utf-8
from enum import Enum

from qfluentwidgets import FluentIconBase, getIconColor, Theme
from resources import resource_qrc  # noqa: F401 - ensure qrc resources are loaded


class Icon(FluentIconBase, Enum):

    # TODO: Add your icons here

    SETTINGS = "Settings"
    SETTINGS_FILLED = "SettingsFilled"

    def path(self, theme=Theme.AUTO):
        return f":/resources/icons/{self.value}_{getIconColor(theme)}.svg"
