from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, PushButton, SimpleCardWidget, Slider, SpinBox, TitleLabel)
from app.framework.ui.views.periodic_base import ModulePageBase

class WaterBombInterface(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_water_bomb")

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.left_layout = QVBoxLayout()
        self.left_layout.setSpacing(8)
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(8)

        self.main_layout.addLayout(self.left_layout, 2)
        self.main_layout.addLayout(self.right_layout, 1)

        self._init_ui()
        self.apply_i18n()

    def _init_ui(self):
        self.SimpleCardWidget_water_bomb = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_water_bomb)

        self.BodyLabel_24 = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_24.setObjectName("BodyLabel_24")
        self.SpinBox_water_win_times = SpinBox(self.SimpleCardWidget_water_bomb)
        self.SpinBox_water_win_times.setObjectName("SpinBox_water_win_times")
        self.SpinBox_water_win_times.setValue(5)
        self.BodyLabel_26 = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_26.setObjectName("BodyLabel_26")
        win_row = QHBoxLayout()
        win_row.addWidget(self.BodyLabel_24)
        win_row.addWidget(self.SpinBox_water_win_times)
        win_row.addWidget(self.BodyLabel_26)
        layout.addLayout(win_row)

        self.BodyLabel_28 = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_28.setObjectName("BodyLabel_28")
        self.Slider_template_threshold = Slider(self.SimpleCardWidget_water_bomb)
        self.Slider_template_threshold.setObjectName("Slider_template_threshold")
        self.Slider_template_threshold.setOrientation(Qt.Orientation.Horizontal)
        self.BodyLabel_template_threshold = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_template_threshold.setObjectName("BodyLabel_template_threshold")
        r1 = QHBoxLayout()
        r1.addWidget(self.BodyLabel_28)
        r1.addWidget(self.Slider_template_threshold, 1)
        r1.addWidget(self.BodyLabel_template_threshold)
        layout.addLayout(r1)

        self.BodyLabel_29 = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_29.setObjectName("BodyLabel_29")
        self.Slider_count_threshold = Slider(self.SimpleCardWidget_water_bomb)
        self.Slider_count_threshold.setObjectName("Slider_count_threshold")
        self.Slider_count_threshold.setOrientation(Qt.Orientation.Horizontal)
        self.BodyLabel_count_threshold = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_count_threshold.setObjectName("BodyLabel_count_threshold")
        r2 = QHBoxLayout()
        r2.addWidget(self.BodyLabel_29)
        r2.addWidget(self.Slider_count_threshold, 1)
        r2.addWidget(self.BodyLabel_count_threshold)
        layout.addLayout(r2)

        self.BodyLabel_tip_water = BodyLabel(self.SimpleCardWidget_water_bomb)
        self.BodyLabel_tip_water.setObjectName("BodyLabel_tip_water")
        self.BodyLabel_tip_water.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_water.setWordWrap(True)
        layout.addWidget(self.BodyLabel_tip_water)
        layout.addStretch(1)

        self.PushButton_start_water_bomb = PushButton(self)
        self.PushButton_start_water_bomb.setObjectName("PushButton_start_water_bomb")

        self.left_layout.addWidget(self.SimpleCardWidget_water_bomb)
        self.left_layout.addWidget(self.PushButton_start_water_bomb)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel_3 = TitleLabel(self.SimpleCardWidget_log)
        self.TitleLabel_3.setObjectName("TitleLabel_3")
        self.textBrowser_log_water_bomb = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_water_bomb.setObjectName("textBrowser_log_water_bomb")
        self.textBrowser_log_water_bomb.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_3)
        log_layout.addWidget(self.textBrowser_log_water_bomb)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

        # Connect signals
        self.Slider_template_threshold.valueChanged.connect(lambda v: self.BodyLabel_template_threshold.setText(str(v)))
        self.Slider_count_threshold.valueChanged.connect(lambda v: self.BodyLabel_count_threshold.setText(str(v)))

    def apply_i18n(self):
        self.BodyLabel_tip_water.setText(
            _("### Tips\n* Stand at the Water Bomb entrance before starting\n* If items or HP are not recognized, lower the two confidence values above", msgid='tips_stand_at_the_water_bomb_entrance_before_starting_if_items_or_hp_are_not_rec'))
        self.BodyLabel_28.setText(_("Template confidence", msgid='template_confidence'))
        self.BodyLabel_29.setText(_("Count confidence", msgid='count_confidence'))
        self.BodyLabel_24.setText(_("Win streak", msgid='win_streak'))
        self.BodyLabel_26.setText(_("stop after wins", msgid='stop_after_wins'))
        self.TitleLabel_3.setText(_("Log", msgid='log'))
        self.PushButton_start_water_bomb.setText(_('Start Water Bomb', msgid='start_water_bomb'))

    def load_config(self):
        self.BodyLabel_template_threshold.setText(str(self.Slider_template_threshold.value()))
        self.BodyLabel_count_threshold.setText(str(self.Slider_count_threshold.value()))



