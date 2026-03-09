import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CheckBox, ComboBox, LineEdit, PixmapLabel, 
                            PrimaryPushButton, PushButton, SimpleCardWidget, SpinBox, 
                            StrongBodyLabel, TitleLabel)
from app.framework.infra.config.app_config import config
from app.framework.infra.events.signal_bus import signalBus
from app.framework.ui.views.periodic_base import ModulePageBase
from app.features.modules.fishing.ui.subtask import AdjustColor

class FishingInterface(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page_fishing")
        self.adjust_color_thread = None

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
        # UI from FishingPage
        self.SimpleCardWidget_fish = SimpleCardWidget(self)
        fish_layout = QVBoxLayout(self.SimpleCardWidget_fish)

        self.BodyLabel_2 = BodyLabel(self.SimpleCardWidget_fish)
        self.ComboBox_fishing_mode = ComboBox(self.SimpleCardWidget_fish)
        self.ComboBox_fishing_mode.setObjectName("ComboBox_fishing_mode")
        fish_layout.addLayout(self._row(self.BodyLabel_2, self.ComboBox_fishing_mode))

        self.BodyLabel_21 = BodyLabel(self.SimpleCardWidget_fish)
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
        self.SpinBox_fish_times = SpinBox(self.SimpleCardWidget_fish)
        self.SpinBox_fish_times.setObjectName("SpinBox_fish_times")
        self.SpinBox_fish_times.setMinimum(1)
        self.SpinBox_fish_times.setMaximum(99999)
        fish_layout.addLayout(self._row(self.BodyLabel, self.SpinBox_fish_times))

        self.BodyLabel_23 = BodyLabel(self.SimpleCardWidget_fish)
        self.ComboBox_lure_type = ComboBox(self.SimpleCardWidget_fish)
        self.ComboBox_lure_type.setObjectName("ComboBox_lure_type")
        fish_layout.addLayout(self._row(self.BodyLabel_23, self.ComboBox_lure_type))

        self.StrongBodyLabel = StrongBodyLabel(self.SimpleCardWidget_fish)
        fish_layout.addWidget(self.StrongBodyLabel)

        self.BodyLabel_5 = BodyLabel(self.SimpleCardWidget_fish)
        self.LineEdit_fish_base = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_base.setObjectName("LineEdit_fish_base")
        self.LineEdit_fish_base.setEnabled(False)
        fish_layout.addLayout(self._row(self.BodyLabel_5, self.LineEdit_fish_base))

        self.BodyLabel_6 = BodyLabel(self.SimpleCardWidget_fish)
        self.LineEdit_fish_upper = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_upper.setObjectName("LineEdit_fish_upper")
        fish_layout.addLayout(self._row(self.BodyLabel_6, self.LineEdit_fish_upper))

        self.BodyLabel_7 = BodyLabel(self.SimpleCardWidget_fish)
        self.LineEdit_fish_lower = LineEdit(self.SimpleCardWidget_fish)
        self.LineEdit_fish_lower.setObjectName("LineEdit_fish_lower")
        fish_layout.addLayout(self._row(self.BodyLabel_7, self.LineEdit_fish_lower))

        btn_row = QHBoxLayout()
        self.PushButton_reset = PushButton(self.SimpleCardWidget_fish)
        self.PrimaryPushButton_get_color = PrimaryPushButton(self.SimpleCardWidget_fish)
        btn_row.addWidget(self.PushButton_reset)
        btn_row.addWidget(self.PrimaryPushButton_get_color)
        fish_layout.addLayout(btn_row)

        self.PixmapLabel = PixmapLabel(self.SimpleCardWidget_fish)
        self.PixmapLabel.setScaledContents(True)
        self.PixmapLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fish_layout.addWidget(self.PixmapLabel)

        self.BodyLabel_tip_fish = BodyLabel(self.SimpleCardWidget_fish)
        self.BodyLabel_tip_fish.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_fish.setWordWrap(True)
        fish_layout.addWidget(self.BodyLabel_tip_fish)
        fish_layout.addStretch(1)

        self.PushButton_start_fishing = PushButton(self)
        self.PushButton_start_fishing.setObjectName("PushButton_start_fishing")

        self.left_layout.addWidget(self.SimpleCardWidget_fish)
        self.left_layout.addWidget(self.PushButton_start_fishing)
        self.left_layout.addStretch(1)

        # Log card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        self.TitleLabel = TitleLabel(self.SimpleCardWidget_log)
        from PySide6.QtWidgets import QTextBrowser
        self.textBrowser_log_fishing = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log_fishing.setObjectName("textBrowser_log_fishing")
        self.textBrowser_log_fishing.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        log_layout.addWidget(self.TitleLabel)
        log_layout.addWidget(self.textBrowser_log_fishing)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

        # Connect internal logic
        self.PrimaryPushButton_get_color.clicked.connect(self.adjust_color)
        self.PushButton_reset.clicked.connect(self.reset_color)

    def _row(self, left: QWidget, right: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(left, 1)
        row.addWidget(right, 2)
        return row

    def apply_i18n(self):
        self.ComboBox_fishing_mode.clear()
        self.ComboBox_fishing_mode.addItems([
            self._ui_text("高性能（消耗性能高速判断，准确率高）", "High Performance (faster and more accurate, higher CPU usage)"),
            self._ui_text("低性能（超时自动拉杆，准确率较低）", "Low Performance (timeout-based auto reel, lower accuracy)")
        ])
        self.BodyLabel_tip_fish.setText(
            "### Tips\n* Side mouse buttons are not supported in background mode\n* Use analyst for fishing character, otherwise it may fail\n* Configure cast key, fishing times and lure type in game first\n* Daily limit: rare spot 25, epic spot 50, normal spot unlimited\n* Move to next fishing spot manually after one spot is exhausted\n* If yellow block detection is abnormal, recalibrate HSV color\n"
            if self._is_non_chinese_ui else
            "### 提示\n* 为实现纯后台，现已不支持鼠标侧键\n* 钓鱼角色选择分析员，否则无法正常工作\n* 根据游戏右下角手动设置好抛竿按键、钓鱼次数和鱼饵类型后再点开始\n* 珍奇钓点系统上限25次/天； 稀有钓点上限50次/天； 普通钓点无限制\n* 一个钓点钓完后需手动移动下一个钓鱼点再启动脚本\n* 黄色块异常时请校准HSV，钓鱼出现圆环时点`校准颜色`，再点黄色区域\n"
        )
        lure_type_items = [
            '万能鱼饵', '普通鱼饵', '豪华鱼饵', '至尊鱼饵', '重量级鱼类虫饵', '巨型鱼类虫饵', '重量级鱼类夜钓虫饵',
            '巨型鱼类夜钓虫饵'
        ] if not self._is_non_chinese_ui else [
            'Universal Bait', 'Normal Bait', 'Deluxe Bait', 'Supreme Bait',
            'Heavy Insect Bait', 'Giant Insect Bait', 'Heavy Night Insect Bait', 'Giant Night Insect Bait'
        ]
        self.ComboBox_lure_type.clear()
        self.ComboBox_lure_type.addItems(lure_type_items)

        self.PushButton_start_fishing.setText(self._ui_text('开始钓鱼', 'Start Fishing'))
        self.TitleLabel.setText(self._ui_text("日志", "Log"))
        self.CheckBox_is_save_fish.setText(self._ui_text("新纪录是否暂停", "Pause on new records"))
        self.BodyLabel_7.setText(self._ui_text("颜色查找下限", "Color lower bound"))
        self.PrimaryPushButton_get_color.setText(self._ui_text("校准颜色", "Calibrate Color"))
        self.BodyLabel.setText(self._ui_text("钓鱼次数：", "Fishing attempts:"))
        self.CheckBox_is_limit_time.setText(self._ui_text("是否限制单次收杆时间间隔上限", "Limit max reeling interval per attempt"))
        self.BodyLabel_21.setText(self._ui_text("自定义钓鱼键", "Custom fishing key"))
        self.StrongBodyLabel.setText(self._ui_text("校准完美收杆区域HSV（当收杆出错，日志说黄色块大于2时用）", "Calibrate perfect reeling HSV (use when logs report yellow block count > 2)"))
        self.LineEdit_fish_key.setPlaceholderText(self._ui_text("钓鱼键与尘白闪避键绑定", "Fishing key is bound to in-game dodge key"))
        self.BodyLabel_6.setText(self._ui_text("颜色查找上限", "Color upper bound"))
        self.BodyLabel_5.setText(self._ui_text("基准HSV值", "Base HSV"))
        self.BodyLabel_2.setText(self._ui_text("钓鱼模式", "Fishing mode"))
        self.PushButton_reset.setText(self._ui_text("重置", "Reset"))
        self.BodyLabel_23.setText(self._ui_text("鱼饵类型：", "Bait type:"))

    def update_label_color(self):
        hsv_value = [int(value) for value in config.LineEdit_fish_base.value.split(",")]
        hsv_array = np.uint8([[[hsv_value[0], hsv_value[1], hsv_value[2]]]])
        bgr_color = cv2.cvtColor(hsv_array, cv2.COLOR_HSV2BGR)[0][0]
        rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])
        rgb_color_str = f"#{rgb_color[0]:02X}{rgb_color[1]:02X}{rgb_color[2]:02X}"
        self.PixmapLabel.setStyleSheet(f"background-color: {rgb_color_str};border-radius: 5px;")

    def adjust_color(self):
        self.adjust_color_thread = AdjustColor()
        self.adjust_color_thread.color_changed.connect(self.reload_color_config)
        self.adjust_color_thread.start()

    def reload_color_config(self):
        self.LineEdit_fish_base.setText(config.LineEdit_fish_base.value)
        self.LineEdit_fish_upper.setText(config.LineEdit_fish_upper.value)
        self.LineEdit_fish_lower.setText(config.LineEdit_fish_lower.value)
        self.update_label_color()

    def reset_color(self):
        config.set(config.LineEdit_fish_base, config.LineEdit_fish_base.defaultValue)
        config.set(config.LineEdit_fish_upper, config.LineEdit_fish_upper.defaultValue)
        config.set(config.LineEdit_fish_lower, config.LineEdit_fish_lower.defaultValue)
        self.LineEdit_fish_base.setText(config.LineEdit_fish_base.value)
        self.LineEdit_fish_upper.setText(config.LineEdit_fish_upper.value)
        self.LineEdit_fish_lower.setText(config.LineEdit_fish_lower.value)
        self.update_label_color()

    def load_config(self):
        # Specific load logic for fishing if needed, 
        # but the host can also do generic loading by object name
        self.update_label_color()

