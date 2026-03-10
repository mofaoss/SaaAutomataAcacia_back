from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, CheckBox, ComboBox, PushButton, SimpleCardWidget, SpinBox, TitleLabel)
from app.framework.ui.views.periodic_base import ModulePageBase

class DrinkInterface(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_card")

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
        self.SimpleCardWidget_card = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_card)

        self.BodyLabel_31 = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_31.setObjectName("BodyLabel_31")
        self.ComboBox_card_mode = ComboBox(self.SimpleCardWidget_card)
        self.ComboBox_card_mode.setObjectName("ComboBox_card_mode")
        row1 = QHBoxLayout()
        row1.addWidget(self.BodyLabel_31, 1)
        row1.addWidget(self.ComboBox_card_mode, 2)
        layout.addLayout(row1)

        self.BodyLabel_32 = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_32.setObjectName("BodyLabel_32")
        self.SpinBox_drink_times = SpinBox(self.SimpleCardWidget_card)
        self.SpinBox_drink_times.setObjectName("SpinBox_drink_times")
        self.SpinBox_drink_times.setMinimum(-1)
        row2 = QHBoxLayout()
        row2.addWidget(self.BodyLabel_32, 1)
        row2.addWidget(self.SpinBox_drink_times, 2)
        layout.addLayout(row2)

        self.CheckBox_is_speed_up = CheckBox(self.SimpleCardWidget_card)
        self.CheckBox_is_speed_up.setObjectName("CheckBox_is_speed_up")
        layout.addWidget(self.CheckBox_is_speed_up)

        self.BodyLabel_tip_card = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_tip_card.setObjectName("BodyLabel_tip_card")
        self.BodyLabel_tip_card.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_card.setWordWrap(True)
        layout.addWidget(self.BodyLabel_tip_card)
        layout.addStretch(1)

        self.PushButton_start_drink = PushButton(self)
        self.PushButton_start_drink.setObjectName("PushButton_start_drink")

        self.left_layout.addWidget(self.SimpleCardWidget_card)
        self.left_layout.addWidget(self.PushButton_start_drink)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel_7 = TitleLabel(self.SimpleCardWidget_log)
        self.TitleLabel_7.setObjectName("TitleLabel_7")
        self.textBrowser_log_drink = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_drink.setObjectName("textBrowser_log_drink")
        self.textBrowser_log_drink.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_7)
        log_layout.addWidget(self.textBrowser_log_drink)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def apply_i18n(self):
        self.BodyLabel_tip_card.setText(
            _("### Tips\n* Stand at the Card Match entrance before starting\n* Both modes prioritize ending matches quickly for fast farming\n* Logic: always challenge when possible; play the middle card on your turn\n* Win/loss may vary; it is designed for passive EXP farming", msgid='tips_stand_at_the_card_match_entrance_before_starting_both_modes_prioritize_endi')
        )
        self.BodyLabel_31.setText(_("Mode", msgid='mode'))
        self.BodyLabel_32.setText(_("Run count (-1 means infinite)", msgid='run_count_1_means_infinite'))
        self.CheckBox_is_speed_up.setText(_("I have enabled speed-up manually", msgid='i_have_enabled_speed_up_manually'))
        self.TitleLabel_7.setText(_("Log", msgid='log'))
        self.PushButton_start_drink.setText(_('Start Drink', msgid='start_drink'))

        self.ComboBox_card_mode.clear()
        self.ComboBox_card_mode.addItems(
            [_('Standard (fast EXP)', msgid='standard_fast_exp'),
             _('Mystery Box Raid (EXP/Achievements)', msgid='mystery_box_raid_exp_achievements')]
        )



