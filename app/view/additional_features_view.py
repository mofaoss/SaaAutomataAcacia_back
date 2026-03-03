from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QLabel,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    LineEdit,
    PixmapLabel,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SimpleCardWidget,
    Slider,
    SpinBox,
    StrongBodyLabel,
    TitleLabel,
)


class BaseFeaturePage(QWidget):
    def __init__(self, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        self.left_layout = QVBoxLayout()
        self.left_layout.setSpacing(8)
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(8)

        self.main_layout.addLayout(self.left_layout, 2)
        self.main_layout.addLayout(self.right_layout, 1)

    @staticmethod
    def create_log_card(parent: QWidget, title_name: str, browser_name: str) -> tuple[SimpleCardWidget, TitleLabel, QTextBrowser]:
        card = SimpleCardWidget(parent)
        layout = QVBoxLayout(card)
        title = TitleLabel(card)
        title.setObjectName(title_name)
        browser = QTextBrowser(card)
        browser.setObjectName(browser_name)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(title)
        layout.addWidget(browser)
        return card, title, browser


class FishingPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_fishing", parent)

        self.SimpleCardWidget_fish = SimpleCardWidget(self)
        fish_layout = QVBoxLayout(self.SimpleCardWidget_fish)

        self.BodyLabel_2 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_2.setObjectName("BodyLabel_2")
        self.ComboBox_fishing_mode = ComboBox(self.SimpleCardWidget_fish)
        self.ComboBox_fishing_mode.setObjectName("ComboBox_fishing_mode")
        fish_layout.addLayout(self._row(self.BodyLabel_2, self.ComboBox_fishing_mode))

        self.BodyLabel_21 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_21.setObjectName("BodyLabel_21")
        self.LineEdit_fish_key = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_key.setObjectName("LineEdit_fish_key")
        fish_layout.addLayout(self._row(self.BodyLabel_21, self.LineEdit_fish_key))

        self.CheckBox_is_save_fish = CheckBox(self.SimpleCardWidget_fish)
        self.CheckBox_is_save_fish.setObjectName("CheckBox_is_save_fish")
        self.CheckBox_is_limit_time = CheckBox(self.SimpleCardWidget_fish)
        self.CheckBox_is_limit_time.setObjectName("CheckBox_is_limit_time")
        fish_layout.addWidget(self.CheckBox_is_save_fish)
        fish_layout.addWidget(self.CheckBox_is_limit_time)

        self.BodyLabel = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel.setObjectName("BodyLabel")
        self.SpinBox_fish_times = SpinBox(self.SimpleCardWidget_fish)
        self.SpinBox_fish_times.setObjectName("SpinBox_fish_times")
        self.SpinBox_fish_times.setMinimum(1)
        self.SpinBox_fish_times.setMaximum(99999)
        fish_layout.addLayout(self._row(self.BodyLabel, self.SpinBox_fish_times))

        self.BodyLabel_23 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_23.setObjectName("BodyLabel_23")
        self.ComboBox_lure_type = ComboBox(self.SimpleCardWidget_fish)
        self.ComboBox_lure_type.setObjectName("ComboBox_lure_type")
        fish_layout.addLayout(self._row(self.BodyLabel_23, self.ComboBox_lure_type))

        self.StrongBodyLabel = StrongBodyLabel(self.SimpleCardWidget_fish)
        self.StrongBodyLabel.setObjectName("StrongBodyLabel")
        fish_layout.addWidget(self.StrongBodyLabel)

        self.BodyLabel_5 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_5.setObjectName("BodyLabel_5")
        self.LineEdit_fish_base = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_base.setObjectName("LineEdit_fish_base")
        self.LineEdit_fish_base.setEnabled(False)
        fish_layout.addLayout(self._row(self.BodyLabel_5, self.LineEdit_fish_base))

        self.BodyLabel_6 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_6.setObjectName("BodyLabel_6")
        self.LineEdit_fish_upper = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_upper.setObjectName("LineEdit_fish_upper")
        fish_layout.addLayout(self._row(self.BodyLabel_6, self.LineEdit_fish_upper))

        self.BodyLabel_7 = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_7.setObjectName("BodyLabel_7")
        self.LineEdit_fish_lower = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_lower.setObjectName("LineEdit_fish_lower")
        fish_layout.addLayout(self._row(self.BodyLabel_7, self.LineEdit_fish_lower))

        btn_row = QHBoxLayout()
        self.PushButton_reset = PushButton(self.SimpleCardWidget_fish)
        self.PushButton_reset.setObjectName("PushButton_reset")
        self.PrimaryPushButton_get_color = PrimaryPushButton(self.SimpleCardWidget_fish)
        self.PrimaryPushButton_get_color.setObjectName("PrimaryPushButton_get_color")
        btn_row.addWidget(self.PushButton_reset)
        btn_row.addWidget(self.PrimaryPushButton_get_color)
        fish_layout.addLayout(btn_row)

        self.PixmapLabel = PixmapLabel(self.SimpleCardWidget_fish)
        self.PixmapLabel.setObjectName("PixmapLabel")
        self.PixmapLabel.setScaledContents(True)
        self.PixmapLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fish_layout.addWidget(self.PixmapLabel)

        self.BodyLabel_tip_fish = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_tip_fish.setObjectName("BodyLabel_tip_fish")
        self.BodyLabel_tip_fish.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_fish.setWordWrap(True)
        fish_layout.addWidget(self.BodyLabel_tip_fish)
        fish_layout.addStretch(1)

        self.PushButton_start_fishing = PushButton(self)
        self.PushButton_start_fishing.setObjectName("PushButton_start_fishing")

        self.left_layout.addWidget(self.SimpleCardWidget_fish)
        self.left_layout.addWidget(self.PushButton_start_fishing)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget, self.TitleLabel, self.textBrowser_log_fishing = self.create_log_card(
            self,
            "TitleLabel",
            "textBrowser_log_fishing",
        )
        self.SimpleCardWidget.setObjectName("SimpleCardWidget")
        self.right_layout.addWidget(self.SimpleCardWidget)

    @staticmethod
    def _row(left: QWidget, right: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        return row


class ActionPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_action", parent)

        self.SimpleCardWidget_action = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_action)

        self.BodyLabel_4 = BodyLabel(self.SimpleCardWidget_action)
        self.BodyLabel_4.setObjectName("BodyLabel_4")
        self.SpinBox_action_times = SpinBox(self.SimpleCardWidget_action)
        self.SpinBox_action_times.setObjectName("SpinBox_action_times")
        self.SpinBox_action_times.setValue(20)
        layout.addLayout(FishingPage._row(self.BodyLabel_4, self.SpinBox_action_times))

        self.BodyLabel_22 = BodyLabel(self.SimpleCardWidget_action)
        self.BodyLabel_22.setObjectName("BodyLabel_22")
        self.ComboBox_run = ComboBox(self.SimpleCardWidget_action)
        self.ComboBox_run.setObjectName("ComboBox_run")
        layout.addLayout(FishingPage._row(self.BodyLabel_22, self.ComboBox_run))

        self.BodyLabel_tip_action = BodyLabel(self.SimpleCardWidget_action)
        self.BodyLabel_tip_action.setObjectName("BodyLabel_tip_action")
        self.BodyLabel_tip_action.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(self.BodyLabel_tip_action)
        layout.addStretch(1)

        self.PushButton_start_action = PushButton(self)
        self.PushButton_start_action.setObjectName("PushButton_start_action")

        self.left_layout.addWidget(self.SimpleCardWidget_action)
        self.left_layout.addWidget(self.PushButton_start_action)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget_2, self.TitleLabel_2, self.textBrowser_log_action = self.create_log_card(
            self,
            "TitleLabel_2",
            "textBrowser_log_action",
        )
        self.SimpleCardWidget_2.setObjectName("SimpleCardWidget_2")
        self.right_layout.addWidget(self.SimpleCardWidget_2)


class WaterBombPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_water_bomb", parent)

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

        self.SimpleCardWidget_4, self.TitleLabel_3, self.textBrowser_log_water_bomb = self.create_log_card(
            self,
            "TitleLabel_3",
            "textBrowser_log_water_bomb",
        )
        self.SimpleCardWidget_4.setObjectName("SimpleCardWidget_4")
        self.right_layout.addWidget(self.SimpleCardWidget_4)


class AlienGuardianPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_alien_guardian", parent)

        self.SimpleCardWidget_alien_guardian = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_25 = BodyLabel(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_25.setObjectName("BodyLabel_25")
        self.ComboBox_mode = ComboBox(self.SimpleCardWidget_alien_guardian)
        self.ComboBox_mode.setObjectName("ComboBox_mode")
        layout.addLayout(FishingPage._row(self.BodyLabel_25, self.ComboBox_mode))

        self.BodyLabel_tip_action_3 = BodyLabel(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_tip_action_3.setObjectName("BodyLabel_tip_action_3")
        self.BodyLabel_tip_action_3.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_alien = BodyLabel(self.SimpleCardWidget_alien_guardian)
        self.BodyLabel_tip_alien.setObjectName("BodyLabel_tip_alien")
        self.BodyLabel_tip_alien.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(self.BodyLabel_tip_action_3)
        layout.addWidget(self.BodyLabel_tip_alien)
        layout.addStretch(1)

        self.PushButton_start_alien_guardian = PushButton(self)
        self.PushButton_start_alien_guardian.setObjectName("PushButton_start_alien_guardian")
        self.left_layout.addWidget(self.SimpleCardWidget_alien_guardian)
        self.left_layout.addWidget(self.PushButton_start_alien_guardian)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget_5, self.TitleLabel_4, self.textBrowser_log_alien_guardian = self.create_log_card(
            self,
            "TitleLabel_4",
            "textBrowser_log_alien_guardian",
        )
        self.SimpleCardWidget_5.setObjectName("SimpleCardWidget_5")
        self.right_layout.addWidget(self.SimpleCardWidget_5)


class MazePage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_maze", parent)

        self.SimpleCardWidget_maze = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_maze)
        self.BodyLabel_27 = BodyLabel(self.SimpleCardWidget_maze)
        self.BodyLabel_27.setObjectName("BodyLabel_27")
        self.ComboBox_mode_maze = ComboBox(self.SimpleCardWidget_maze)
        self.ComboBox_mode_maze.setObjectName("ComboBox_mode_maze")
        layout.addLayout(FishingPage._row(self.BodyLabel_27, self.ComboBox_mode_maze))

        self.BodyLabel_tip_action_4 = BodyLabel(self.SimpleCardWidget_maze)
        self.BodyLabel_tip_action_4.setObjectName("BodyLabel_tip_action_4")
        self.BodyLabel_tip_action_4.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_maze = BodyLabel(self.SimpleCardWidget_maze)
        self.BodyLabel_tip_maze.setObjectName("BodyLabel_tip_maze")
        self.BodyLabel_tip_maze.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(self.BodyLabel_tip_action_4)
        layout.addWidget(self.BodyLabel_tip_maze)
        layout.addStretch(1)

        self.PushButton_start_maze = PushButton(self)
        self.PushButton_start_maze.setObjectName("PushButton_start_maze")
        self.left_layout.addWidget(self.SimpleCardWidget_maze)
        self.left_layout.addWidget(self.PushButton_start_maze)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget_6, self.TitleLabel_5, self.textBrowser_log_maze = self.create_log_card(
            self,
            "TitleLabel_5",
            "textBrowser_log_maze",
        )
        self.SimpleCardWidget_6.setObjectName("SimpleCardWidget_6")
        self.right_layout.addWidget(self.SimpleCardWidget_6)


class CardPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_card", parent)

        self.SimpleCardWidget_card = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_card)
        self.BodyLabel_31 = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_31.setObjectName("BodyLabel_31")
        self.ComboBox_card_mode = ComboBox(self.SimpleCardWidget_card)
        self.ComboBox_card_mode.setObjectName("ComboBox_card_mode")
        layout.addLayout(FishingPage._row(self.BodyLabel_31, self.ComboBox_card_mode))

        self.BodyLabel_32 = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_32.setObjectName("BodyLabel_32")
        self.SpinBox_drink_times = SpinBox(self.SimpleCardWidget_card)
        self.SpinBox_drink_times.setObjectName("SpinBox_drink_times")
        self.SpinBox_drink_times.setMinimum(-1)
        layout.addLayout(FishingPage._row(self.BodyLabel_32, self.SpinBox_drink_times))

        self.CheckBox_is_speed_up = CheckBox(self.SimpleCardWidget_card)
        self.CheckBox_is_speed_up.setObjectName("CheckBox_is_speed_up")
        layout.addWidget(self.CheckBox_is_speed_up)

        self.BodyLabel_tip_action_6 = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_tip_action_6.setObjectName("BodyLabel_tip_action_6")
        self.BodyLabel_tip_action_6.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_card = BodyLabel(self.SimpleCardWidget_card)
        self.BodyLabel_tip_card.setObjectName("BodyLabel_tip_card")
        self.BodyLabel_tip_card.setTextFormat(Qt.TextFormat.MarkdownText)
        layout.addWidget(self.BodyLabel_tip_action_6)
        layout.addWidget(self.BodyLabel_tip_card)
        layout.addStretch(1)

        self.PushButton_start_drink = PushButton(self)
        self.PushButton_start_drink.setObjectName("PushButton_start_drink")
        self.left_layout.addWidget(self.SimpleCardWidget_card)
        self.left_layout.addWidget(self.PushButton_start_drink)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget_8, self.TitleLabel_7, self.textBrowser_log_drink = self.create_log_card(
            self,
            "TitleLabel_7",
            "textBrowser_log_drink",
        )
        self.SimpleCardWidget_8.setObjectName("SimpleCardWidget_8")
        self.right_layout.addWidget(self.SimpleCardWidget_8)


class CapturePalsPage(BaseFeaturePage):
    def __init__(self, parent=None):
        super().__init__("page_capture_pals", parent)

        self.SimpleCardWidget_capture_pals = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_capture_pals)

        self.BodyLabel_capture_pals_partner_mode = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_partner_mode.setObjectName("BodyLabel_capture_pals_partner_mode")
        self.ComboBox_capture_pals_partner_mode = ComboBox(self.SimpleCardWidget_capture_pals)
        self.ComboBox_capture_pals_partner_mode.setObjectName("ComboBox_capture_pals_partner_mode")
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_partner_mode, self.ComboBox_capture_pals_partner_mode))

        self.BodyLabel_capture_pals_adventure_mode = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_mode.setObjectName("BodyLabel_capture_pals_adventure_mode")
        self.ComboBox_capture_pals_adventure_mode = ComboBox(self.SimpleCardWidget_capture_pals)
        self.ComboBox_capture_pals_adventure_mode.setObjectName("ComboBox_capture_pals_adventure_mode")
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_adventure_mode, self.ComboBox_capture_pals_adventure_mode))

        self.StrongBodyLabel_capture_pals_island = StrongBodyLabel(self.SimpleCardWidget_capture_pals)
        self.StrongBodyLabel_capture_pals_island.setObjectName("StrongBodyLabel_capture_pals_island")
        layout.addWidget(self.StrongBodyLabel_capture_pals_island)

        self.CheckBox_capture_pals_partner = CheckBox(self.SimpleCardWidget_capture_pals)
        self.CheckBox_capture_pals_partner.setObjectName("CheckBox_capture_pals_partner")
        self.CheckBox_capture_pals_adventure = CheckBox(self.SimpleCardWidget_capture_pals)
        self.CheckBox_capture_pals_adventure.setObjectName("CheckBox_capture_pals_adventure")
        self.CheckBox_capture_pals_sync = CheckBox(self.SimpleCardWidget_capture_pals)
        self.CheckBox_capture_pals_sync.setObjectName("CheckBox_capture_pals_sync")
        layout.addWidget(self.CheckBox_capture_pals_partner)
        layout.addWidget(self.CheckBox_capture_pals_adventure)
        layout.addWidget(self.CheckBox_capture_pals_sync)

        self.BodyLabel_capture_pals_sync_every = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_sync_every.setObjectName("BodyLabel_capture_pals_sync_every")
        layout.addWidget(self.BodyLabel_capture_pals_sync_every)

        self.StrongBodyLabel_capture_pals_partner = StrongBodyLabel(self.SimpleCardWidget_capture_pals)
        self.StrongBodyLabel_capture_pals_partner.setObjectName("StrongBodyLabel_capture_pals_partner")
        layout.addWidget(self.StrongBodyLabel_capture_pals_partner)

        self.BodyLabel_capture_pals_partner_fixed = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_partner_fixed.setObjectName("BodyLabel_capture_pals_partner_fixed")
        self.SpinBox_capture_pals_partner_fixed_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_partner_fixed_interval.setObjectName("SpinBox_capture_pals_partner_fixed_interval")
        self.SpinBox_capture_pals_partner_fixed_interval.setMinimum(1)
        self.SpinBox_capture_pals_partner_fixed_interval.setMaximum(999999)
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_partner_fixed, self.SpinBox_capture_pals_partner_fixed_interval))

        self.BodyLabel_capture_pals_partner_patrol = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_partner_patrol.setObjectName("BodyLabel_capture_pals_partner_patrol")
        self.SpinBox_capture_pals_partner_patrol_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_partner_patrol_interval.setObjectName("SpinBox_capture_pals_partner_patrol_interval")
        self.SpinBox_capture_pals_partner_patrol_interval.setMinimum(1)
        self.SpinBox_capture_pals_partner_patrol_interval.setMaximum(999999)
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_partner_patrol, self.SpinBox_capture_pals_partner_patrol_interval))

        self.StrongBodyLabel_capture_pals_adventure = StrongBodyLabel(self.SimpleCardWidget_capture_pals)
        self.StrongBodyLabel_capture_pals_adventure.setObjectName("StrongBodyLabel_capture_pals_adventure")
        layout.addWidget(self.StrongBodyLabel_capture_pals_adventure)

        self.BodyLabel_capture_pals_adventure_fixed = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_fixed.setObjectName("BodyLabel_capture_pals_adventure_fixed")
        self.SpinBox_capture_pals_adventure_fixed_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_adventure_fixed_interval.setObjectName("SpinBox_capture_pals_adventure_fixed_interval")
        self.SpinBox_capture_pals_adventure_fixed_interval.setMinimum(1)
        self.SpinBox_capture_pals_adventure_fixed_interval.setMaximum(999999)
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_adventure_fixed, self.SpinBox_capture_pals_adventure_fixed_interval))

        self.BodyLabel_capture_pals_adventure_patrol = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_patrol.setObjectName("BodyLabel_capture_pals_adventure_patrol")
        self.SpinBox_capture_pals_adventure_patrol_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_adventure_patrol_interval.setObjectName("SpinBox_capture_pals_adventure_patrol_interval")
        self.SpinBox_capture_pals_adventure_patrol_interval.setMinimum(1)
        self.SpinBox_capture_pals_adventure_patrol_interval.setMaximum(999999)
        layout.addLayout(FishingPage._row(self.BodyLabel_capture_pals_adventure_patrol, self.SpinBox_capture_pals_adventure_patrol_interval))

        self.BodyLabel_tip_capture_pals = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_tip_capture_pals.setObjectName("BodyLabel_tip_capture_pals")
        self.BodyLabel_tip_capture_pals.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_capture_pals.setWordWrap(True)
        layout.addWidget(self.BodyLabel_tip_capture_pals)
        layout.addStretch(1)

        self.PushButton_start_capture_pals = PushButton(self)
        self.PushButton_start_capture_pals.setObjectName("PushButton_start_capture_pals")
        self.left_layout.addWidget(self.SimpleCardWidget_capture_pals)
        self.left_layout.addWidget(self.PushButton_start_capture_pals)
        self.left_layout.addStretch(1)

        self.SimpleCardWidget_log_capture_pals, self.TitleLabel_log_capture_pals, self.textBrowser_log_capture_pals = self.create_log_card(
            self,
            "TitleLabel_log_capture_pals",
            "textBrowser_log_capture_pals",
        )
        self.SimpleCardWidget_log_capture_pals.setObjectName("SimpleCardWidget_log_capture_pals")
        self.right_layout.addWidget(self.SimpleCardWidget_log_capture_pals)


class AdditionalFeaturesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("additional_features")

        self.gridLayout = QVBoxLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 3)
        self.gridLayout.setSpacing(6)

        self.SegmentedWidget = SegmentedWidget(self)
        self.SegmentedWidget.setObjectName("SegmentedWidget")
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setObjectName("stackedWidget")

        self.page_fishing = FishingPage(self.stackedWidget)
        self.page_action = ActionPage(self.stackedWidget)
        self.page_water_bomb = WaterBombPage(self.stackedWidget)
        self.page_alien_guardian = AlienGuardianPage(self.stackedWidget)
        self.page_maze = MazePage(self.stackedWidget)
        self.page_card = CardPage(self.stackedWidget)
        self.page_capture_pals = CapturePalsPage(self.stackedWidget)

        for page in (
            self.page_fishing,
            self.page_action,
            self.page_water_bomb,
            self.page_alien_guardian,
            self.page_maze,
            self.page_card,
            self.page_capture_pals,
        ):
            self.stackedWidget.addWidget(page)

        self.gridLayout.addWidget(self.SegmentedWidget)
        self.gridLayout.addWidget(self.stackedWidget, 1)

        self._alias_widgets()
        self.stackedWidget.setCurrentIndex(0)

    def _alias_widgets(self):
        for page in (
            self.page_fishing,
            self.page_action,
            self.page_water_bomb,
            self.page_alien_guardian,
            self.page_maze,
            self.page_card,
            self.page_capture_pals,
        ):
            for name in dir(page):
                if name.startswith("__"):
                    continue
                if hasattr(self, name):
                    continue
                value = getattr(page, name)
                if isinstance(value, (QWidget, QLayout, QLabel, QTextBrowser)):
                    setattr(self, name, value)
