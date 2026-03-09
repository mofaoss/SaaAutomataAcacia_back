from typing import Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel
from qfluentwidgets import SettingCard, qconfig, FluentIconBase, Slider


class SliderSettingCard(SettingCard):
    def __init__(self, configItem, icon: Union[str, QIcon, FluentIconBase], title, content=None,
                 parent=None, min_value=1, max_value=255):
        super().__init__(icon, title, content, parent)
        self.configItem = configItem
        self.min_value = min_value
        self.max_value = max_value

        self.slider = Slider(Qt.Orientation.Horizontal, self)
        self.slider.setMinimum(self.min_value)
        self.slider.setMaximum(self.max_value)
        self.slider.setFixedWidth(220)

        self.valueLabel = QLabel(self)
        self.valueLabel.setMinimumWidth(36)
        self.valueLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.hBoxLayout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.valueLabel, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self._set_current_value()
        self.slider.valueChanged.connect(self._on_value_changed)

    def _set_current_value(self):
        try:
            value = int(qconfig.get(self.configItem))
        except Exception:
            value = self.min_value
        value = max(self.min_value, min(self.max_value, value))
        self.slider.setValue(value)
        self.valueLabel.setText(str(value))

    def _on_value_changed(self, value: int):
        value = max(self.min_value, min(self.max_value, int(value)))
        self.valueLabel.setText(str(value))
        qconfig.set(self.configItem, value)

    def sync_from_config(self):
        self._set_current_value()
