from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import (BodyLabel, CheckBox, ComboBox, PushButton, SimpleCardWidget, SpinBox, StrongBodyLabel, TitleLabel)
from app.framework.infra.config.app_config import config
from app.framework.ui.views.periodic_base import ModulePageBase

class CapturePalsInterface(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_capture_pals")

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
        self.SimpleCardWidget_capture_pals = SimpleCardWidget(self)
        layout = QVBoxLayout(self.SimpleCardWidget_capture_pals)

        self.BodyLabel_capture_pals_partner_mode = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_partner_mode.setObjectName("BodyLabel_capture_pals_partner_mode")
        self.ComboBox_capture_pals_partner_mode = ComboBox(self.SimpleCardWidget_capture_pals)
        self.ComboBox_capture_pals_partner_mode.setObjectName("ComboBox_capture_pals_partner_mode")
        layout.addLayout(self._row(self.BodyLabel_capture_pals_partner_mode, self.ComboBox_capture_pals_partner_mode))

        self.BodyLabel_capture_pals_adventure_mode = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_mode.setObjectName("BodyLabel_capture_pals_adventure_mode")
        self.ComboBox_capture_pals_adventure_mode = ComboBox(self.SimpleCardWidget_capture_pals)
        self.ComboBox_capture_pals_adventure_mode.setObjectName("ComboBox_capture_pals_adventure_mode")
        layout.addLayout(self._row(self.BodyLabel_capture_pals_adventure_mode, self.ComboBox_capture_pals_adventure_mode))

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
        layout.addLayout(self._row(self.BodyLabel_capture_pals_partner_fixed, self.SpinBox_capture_pals_partner_fixed_interval))

        self.BodyLabel_capture_pals_partner_patrol = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_partner_patrol.setObjectName("BodyLabel_capture_pals_partner_patrol")
        self.SpinBox_capture_pals_partner_patrol_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_partner_patrol_interval.setObjectName("SpinBox_capture_pals_partner_patrol_interval")
        self.SpinBox_capture_pals_partner_patrol_interval.setMinimum(1)
        self.SpinBox_capture_pals_partner_patrol_interval.setMaximum(999999)
        layout.addLayout(self._row(self.BodyLabel_capture_pals_partner_patrol, self.SpinBox_capture_pals_partner_patrol_interval))

        self.StrongBodyLabel_capture_pals_adventure = StrongBodyLabel(self.SimpleCardWidget_capture_pals)
        self.StrongBodyLabel_capture_pals_adventure.setObjectName("StrongBodyLabel_capture_pals_adventure")
        layout.addWidget(self.StrongBodyLabel_capture_pals_adventure)

        self.BodyLabel_capture_pals_adventure_fixed = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_fixed.setObjectName("BodyLabel_capture_pals_adventure_fixed")
        self.SpinBox_capture_pals_adventure_fixed_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_adventure_fixed_interval.setObjectName("SpinBox_capture_pals_adventure_fixed_interval")
        self.SpinBox_capture_pals_adventure_fixed_interval.setMinimum(1)
        self.SpinBox_capture_pals_adventure_fixed_interval.setMaximum(999999)
        layout.addLayout(self._row(self.BodyLabel_capture_pals_adventure_fixed, self.SpinBox_capture_pals_adventure_fixed_interval))

        self.BodyLabel_capture_pals_adventure_patrol = BodyLabel(self.SimpleCardWidget_capture_pals)
        self.BodyLabel_capture_pals_adventure_patrol.setObjectName("BodyLabel_capture_pals_adventure_patrol")
        self.SpinBox_capture_pals_adventure_patrol_interval = SpinBox(self.SimpleCardWidget_capture_pals)
        self.SpinBox_capture_pals_adventure_patrol_interval.setObjectName("SpinBox_capture_pals_adventure_patrol_interval")
        self.SpinBox_capture_pals_adventure_patrol_interval.setMinimum(1)
        self.SpinBox_capture_pals_adventure_patrol_interval.setMaximum(999999)
        layout.addLayout(self._row(self.BodyLabel_capture_pals_adventure_patrol, self.SpinBox_capture_pals_adventure_patrol_interval))

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

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel_log_capture_pals = TitleLabel(self.SimpleCardWidget_log)
        self.TitleLabel_log_capture_pals.setObjectName("TitleLabel_log_capture_pals")
        self.textBrowser_log_capture_pals = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_capture_pals.setObjectName("textBrowser_log_capture_pals")
        self.textBrowser_log_capture_pals.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel_log_capture_pals)
        log_layout.addWidget(self.textBrowser_log_capture_pals)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

    def _row(self, left: QWidget, right: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        return row

    def apply_i18n(self):
        self.BodyLabel_tip_capture_pals.setText(
            "### Tips\n"
            "* Auto-capture pals based on community strategy\n"
            "* Configure support skill key to C before running\n"
            "* Ensure full-screen 16:9 and stay on Partner/Adventure island selection page\n"
            "* Patrol mode exits and re-enters map each cycle to refresh targets\n"
            if self._is_non_chinese_ui else
            "### 提示\n"
            "* 通过视频BV1SV8wzjEpE和BV1SV8wzjEpE的抓捕思路实现\n"
            "* 需要携带有高伤害满级召雷+碎冰冰/布防的帕鲁如武装，爆破会员来秒杀\n"
            "* 抓帕鲁前请确保已在游戏内设置好狂猎支援技快捷键为 C 键\n"
            "* 启动前请确保当前是全屏模式16：9并且界面在选择伙伴岛/探险岛页面\n"
            "* 定点抓帕鲁：进图后按狂猎支援技C再尝试按 F 进行抓取；按设定间隔循环\n"
            "* 巡逻抓帕鲁：每次抓完会 ESC 退出地图并重新进入，以刷新巡逻帕鲁\n"
            "* 同步抓帕鲁：双岛同时勾选，按“各自周期”在两岛间切换；一岛结束会只刷另一岛\n"
        )

        self.BodyLabel_capture_pals_partner_mode.setText(self._ui_text("伙伴岛模式", "Partner Island mode"))
        self.BodyLabel_capture_pals_adventure_mode.setText(self._ui_text("探险岛模式", "Adventure Island mode"))
        self.StrongBodyLabel_capture_pals_island.setText(self._ui_text("选择岛屿", "Select islands"))
        self.CheckBox_capture_pals_partner.setText(self._ui_text("伙伴岛", "Partner Island"))
        self.CheckBox_capture_pals_adventure.setText(self._ui_text("探险岛", "Adventure Island"))
        self.CheckBox_capture_pals_sync.setText(self._ui_text("同步抓帕鲁", "Sync capture"))
        self.StrongBodyLabel_capture_pals_partner.setText(self._ui_text("伙伴岛参数", "Partner Island settings"))
        self.BodyLabel_capture_pals_partner_fixed.setText(self._ui_text("定点间隔(秒)", "Fixed interval (s)"))
        self.BodyLabel_capture_pals_partner_patrol.setText(self._ui_text("巡逻间隔(秒)", "Patrol interval (s)"))
        self.StrongBodyLabel_capture_pals_adventure.setText(self._ui_text("探险岛参数", "Adventure Island settings"))
        self.BodyLabel_capture_pals_adventure_fixed.setText(self._ui_text("定点间隔(秒)", "Fixed interval (s)"))
        self.BodyLabel_capture_pals_adventure_patrol.setText(self._ui_text("巡逻间隔(秒)", "Patrol interval (s)"))
        self.TitleLabel_log_capture_pals.setText(self._ui_text("日志", "Log"))
        self.PushButton_start_capture_pals.setText(self._ui_text('开始抓帕鲁', 'Start Capture Pals'))

        capture_pals_mode_items = [
            self._ui_text("定点抓帕鲁", "Fixed Point Capture"),
            self._ui_text("巡逻抓帕鲁", "Patrol Capture")
        ]
        self.ComboBox_capture_pals_partner_mode.clear()
        self.ComboBox_capture_pals_partner_mode.addItems(capture_pals_mode_items)
        self.ComboBox_capture_pals_adventure_mode.clear()
        self.ComboBox_capture_pals_adventure_mode.addItems(capture_pals_mode_items)

