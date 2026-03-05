import re
from functools import partial

import cv2
import numpy as np
from PySide6.QtWidgets import QFrame, QWidget, QLabel, QVBoxLayout
from fuzzywuzzy import process
from qfluentwidgets import SpinBox, CheckBox, ComboBox, LineEdit, Slider

from app.common.config import config, is_non_chinese_ui_language
from app.common.signal_bus import signalBus
from app.common.style_sheet import StyleSheet
from utils.ui_utils import get_all_children
from app.modules.alien_guardian.alien_guardian import AlienGuardianModule
from app.modules.drink.drink import DrinkModule
from app.modules.fishing.fishing import FishingModule
from app.modules.maze.maze import MazeModule
from app.modules.operation_action.operation_action import OperationModule
from app.modules.water_bomb.water_bomb import WaterBombModule
from app.modules.capture_pals.capture_pals import CapturePalsModule
from app.view.additional_features_view import AdditionalFeaturesView
from .base_interface import BaseInterface
from app.view.subtask import AdjustColor, SubTask


class Additional(QFrame, BaseInterface):

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.setting_name_list = ['商店', '体力', '奖励']

        self.ui = AdditionalFeaturesView(self)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.ui)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.is_running_fish = False
        self.is_running_action = False
        self.is_running_water_bomb = False
        self.is_running_alien_guardian = False
        self.is_running_maze = False
        self.is_running_drink = False
        self.is_running_capture_pals = False
        self.color_pixmap = None
        self.hsv_value = None

        self._initWidget()
        self._load_config()
        self._connect_to_slot()

    def __getattr__(self, item):
        ui = self.__dict__.get('ui')
        if ui is not None and hasattr(ui, item):
            return getattr(ui, item)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

    def _initWidget(self):
        # 正向链接
        self.SegmentedWidget.addItem(self.page_fishing.objectName(),
                                     self._ui_text('钓鱼', 'Fishing'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_fishing))
        self.SegmentedWidget.addItem(self.page_action.objectName(),
                                     self._ui_text('常规教学', 'Operation'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_action))
        self.SegmentedWidget.addItem(self.page_water_bomb.objectName(),
                                     self._ui_text('心动水弹', 'Water Bomb'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_water_bomb))
        self.SegmentedWidget.addItem(
            self.page_alien_guardian.objectName(),
            self._ui_text('异星守护', 'Alien Guardian'),
            onClick=lambda: self.stackedWidget.setCurrentWidget(
                self.page_alien_guardian))
        self.SegmentedWidget.addItem(self.page_maze.objectName(),
                                     self._ui_text('验证战场', 'Maze'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_maze))
        self.SegmentedWidget.addItem(self.page_card.objectName(),
                                     self._ui_text('猜心对局', 'Card Match'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_card))
        self.SegmentedWidget.addItem(self.page_capture_pals.objectName(),
                                     self._ui_text('抓帕鲁', 'Capture Pals'),
                                     onClick=lambda: self.stackedWidget.
                                     setCurrentWidget(self.page_capture_pals))
        self.SegmentedWidget.setCurrentItem(self.page_fishing.objectName())
        self.stackedWidget.setCurrentIndex(0)
        self.ComboBox_fishing_mode.addItems(
            [
                self._ui_text("高性能（消耗性能高速判断，准确率高）", "High Performance (faster and more accurate, higher CPU usage)"),
                self._ui_text("低性能（超时自动拉杆，准确率较低）", "Low Performance (timeout-based auto reel, lower accuracy)")
            ])
        self.BodyLabel_tip_fish.setText(
            "### Tips\n* Side mouse buttons are not supported in background mode\n* Use analyst for fishing character, otherwise it may fail\n* Configure cast key, fishing times and lure type in game first\n* Daily limit: rare spot 25, epic spot 50, normal spot unlimited\n* Move to next fishing spot manually after one spot is exhausted\n* If yellow block detection is abnormal, recalibrate HSV color\n"
            if self._is_non_chinese_ui else
            "### 提示\n* 为实现纯后台，现已不支持鼠标侧键\n* 钓鱼角色选择分析员，否则无法正常工作\n* 根据游戏右下角手动设置好抛竿按键、钓鱼次数和鱼饵类型后再点开始\n* 珍奇钓点系统上限25次/天； 稀有钓点上限50次/天； 普通钓点无限制\n* 一个钓点钓完后需手动移动下一个钓鱼点再启动脚本\n* 黄色块异常时请校准HSV，钓鱼出现圆环时点`校准颜色`，再点黄色区域\n"
        )
        self.BodyLabel_tip_action.setText(
            "### Tips\n* Auto-run operation from the lobby page\n* Repeats the first training stage for specified times with no stamina cost\n* Useful for weekly pass mission count"
            if self._is_non_chinese_ui else
            "### 提示\n* 自动完成无体力常规教学\n* 重复刷指定次数实战训练第一关，不消耗体力\n* 用于完成凭证20次常规行动周常任务"
        )
        self.BodyLabel_tip_water.setText(
            self._ui_text(
                "### 提示\n* 站在水弹入口位置后再点开始\n* 当无法识别道具或者生命时，适当调低上面两个置信度参数",
                "### Tips\n* Stand at the Water Bomb entrance before starting\n* If items or HP are not recognized, lower the two confidence values above"
            ))
        self.BodyLabel_tip_alien.setText(
            self._ui_text(
                "### 提示\n* 开始战斗后再点击开始\n* 常驻伙伴推荐带钢珠和炽热投手\n* 闯关模式为半自动一关一关打。需要手动开枪，手动选择下一关",
                "### Tips\n* Click Start after battle begins\n* Recommended support pals: Steel Shot and Blazing Pitcher\n* Stage mode is semi-automatic: manual shooting and manual next-stage selection are required"
            )
        )
        self.BodyLabel_tip_maze.setText(
            self._ui_text(
                "### 提示\n* 本功能只适用于增益迷宫（新迷宫），而非老迷宫\n* 运行模式中单次运行适合打前3关，重复运行则是一直刷最后一关\n* 进配队界面选好增益后再让安卡希雅的开始迷宫\n* 增益推荐配技能-爆电和护盾-夺取\n* 配队必须要有辰星-琼弦，且把角色放在中间位\n* 辅助有豹豹上豹豹防止暴毙",
                "### Tips\n* This feature only supports the new Buff Maze, not the old maze\n* Single Run is suitable for first 3 stages; Repeat Run keeps farming the last stage\n* Select buffs in team setup first, then click Start Maze in Acacia\n* Recommended buffs: Skill-Chain Lightning and Shield-Steal\n* Team must include Chenxing - Qiongxian in the middle slot\n* Bring a strong support unit to reduce sudden deaths"
            )
        )
        self.BodyLabel_tip_card.setText(
            self._ui_text(
                "### 提示\n* 站在猜心对局入口位置后再点开始\n* 两种模式均无策略，目的均是为了快速结束对局刷下一把\n* 逻辑：有质疑直接质疑，轮到自己出牌时出中间的那一张\n* 实测有赢有输，挂着刷经验就行",
                "### Tips\n* Stand at the Card Match entrance before starting\n* Both modes prioritize ending matches quickly for fast farming\n* Logic: always challenge when possible; play the middle card on your turn\n* Win/loss may vary; it is designed for passive EXP farming"
            )
        )
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


        # 设置combobox选项
        lure_type_items = [
            '万能鱼饵', '普通鱼饵', '豪华鱼饵', '至尊鱼饵', '重量级鱼类虫饵', '巨型鱼类虫饵', '重量级鱼类夜钓虫饵',
            '巨型鱼类夜钓虫饵'
        ]
        run_items = ["切换疾跑", "按住疾跑"]
        mode_items = ["无尽模式", "闯关模式"]
        mode_maze_items = ["单次运行", "重复运行"]
        mode_card_items = ['标准模式（速刷经验）', '秘盒奇袭（刷经验成就）']
        if self._is_non_chinese_ui:
            lure_type_items = [
                'Universal Bait', 'Normal Bait', 'Deluxe Bait', 'Supreme Bait',
                'Heavy Insect Bait', 'Giant Insect Bait', 'Heavy Night Insect Bait', 'Giant Night Insect Bait'
            ]
            run_items = ["Toggle Sprint", "Hold Sprint"]
            mode_items = ["Endless Mode", "Stage Mode"]
            mode_maze_items = ["Single Run", "Repeat Run"]
            mode_card_items = ['Standard (fast EXP)', 'Mystery Box Raid (EXP/Achievements)']
        self.ComboBox_run.addItems(run_items)
        self.ComboBox_lure_type.addItems(lure_type_items)
        self.ComboBox_mode.addItems(mode_items)
        self.ComboBox_mode_maze.addItems(mode_maze_items)
        self.ComboBox_card_mode.addItems(mode_card_items)
        capture_pals_mode_items = ["定点抓帕鲁", "巡逻抓帕鲁"]
        if self._is_non_chinese_ui:
            capture_pals_mode_items = ["Fixed Point Capture", "Patrol Capture"]
        self.ComboBox_capture_pals_partner_mode.addItems(capture_pals_mode_items)
        self.ComboBox_capture_pals_adventure_mode.addItems(capture_pals_mode_items)

        self.PushButton_start_fishing.setText(self._ui_text('开始钓鱼', 'Start Fishing'))
        self.PushButton_start_action.setText(self._ui_text('开始行动', 'Start Operation'))
        self.PushButton_start_water_bomb.setText(self._ui_text('开始心动水弹', 'Start Water Bomb'))
        self.PushButton_start_alien_guardian.setText(self._ui_text('开始异星守护', 'Start Alien Guardian'))
        self.PushButton_start_maze.setText(self._ui_text('开始迷宫', 'Start Maze'))
        self.PushButton_start_drink.setText(self._ui_text('开始喝酒', 'Start Drink'))
        self.PushButton_start_capture_pals.setText(self._ui_text('开始抓帕鲁', 'Start Capture Pals'))
        self._apply_static_i18n()

        self.update_label_color()
        # self.color_pixmap = self.generate_pixmap_from_hsv(hsv_value)
        # self.PixmapLabel.setStyleSheet()
        # self.PixmapLabel.setPixmap(self.color_pixmap)
        StyleSheet.ADDITIONAL_FEATURES_INTERFACE.apply(self)

    def _connect_to_slot(self):
        # 反向链接
        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        # 按钮信号
        self.PushButton_start_fishing.clicked.connect(
            self.on_fishing_button_click)
        self.PushButton_start_action.clicked.connect(
            self.on_action_button_click)
        self.PushButton_start_water_bomb.clicked.connect(
            self.on_water_bomb_button_click)
        self.PushButton_start_alien_guardian.clicked.connect(
            self.on_alien_guardian_button_click)
        self.PushButton_start_maze.clicked.connect(self.on_maze_button_click)
        self.PushButton_start_drink.clicked.connect(self.on_drink_button_click)
        self.PushButton_start_capture_pals.clicked.connect(
            self.on_capture_pals_button_click)

        # 链接各种需要保存修改的控件
        self._connect_to_save_changed()

        self.PrimaryPushButton_get_color.clicked.connect(self.adjust_color)
        self.PushButton_reset.clicked.connect(self.reset_color)

        self.LineEdit_fish_key.editingFinished.connect(
            lambda: self.update_fish_key(self.LineEdit_fish_key.text()))

        signalBus.updateFishKey.connect(self.update_fish_key)

    def _load_config(self):
        for widget in self.findChildren(QWidget):
            # 动态获取 config 对象中与 widget.objectName() 对应的属性值
            config_item = getattr(config, widget.objectName(), None)
            if config_item:
                if isinstance(widget, CheckBox):
                    widget.setChecked(
                        config_item.value)  # 使用配置项的值设置 CheckBox 的状态
                elif isinstance(widget, ComboBox):
                    # widget.setPlaceholderText("未选择")
                    widget.setCurrentIndex(config_item.value)
                elif isinstance(widget, LineEdit):
                    if widget.objectName().split('_')[2] == 'key':
                        widget.setPlaceholderText(self._ui_text("例如空格输入‘space’，置空则自动识别",
                                                                "Example: input 'space' for Space key, leave empty for auto-detect"))
                    elif widget.objectName().split('_')[1] == 'fish':
                        widget.setPlaceholderText(self._ui_text("“int,int,int”", "int,int,int"))
                    widget.setText(config_item.value)
                elif isinstance(widget, SpinBox):
                    widget.setValue(config_item.value)
                elif isinstance(widget, Slider):
                    widget.setValue(config_item.value)
                    text_name = 'BodyLabel_' + widget.objectName().split(
                        '_')[1] + '_' + widget.objectName().split('_')[2]
                    text_widget = self.findChild(QLabel, name=text_name)
                    text_widget.setText(str(widget.value()))

    def _connect_to_save_changed(self):
        children_list = get_all_children(self)
        for children in children_list:
            # 此时不能用lambda，会使传参出错
            if isinstance(children, CheckBox):
                children.stateChanged.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, ComboBox):
                children.currentIndexChanged.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, SpinBox):
                children.valueChanged.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, LineEdit):
                children.editingFinished.connect(
                    partial(self.save_changed, children))
            elif isinstance(children, Slider):
                children.valueChanged.connect(
                    partial(self.save_changed, children))

    def save_changed(self, widget, *args, **kwargs):
        if isinstance(widget, SpinBox):
            config.set(getattr(config, widget.objectName(), None),
                       widget.value())
        elif isinstance(widget, CheckBox):
            config.set(getattr(config, widget.objectName(), None),
                       widget.isChecked())
        elif isinstance(widget, LineEdit):
            # 如果是钓鱼相关的lineEdit
            if widget.objectName().split('_')[1] == 'fish':
                # 钓鱼按键
                if widget.objectName().split('_')[2] == 'key':
                    config.set(getattr(config, widget.objectName(), None),
                               widget.text())
                else:
                    text = widget.text()
                    if self.is_valid_format(text):
                        config.set(getattr(config, widget.objectName(), None),
                                   text)
        elif isinstance(widget, ComboBox):
            config.set(getattr(config, widget.objectName(), None),
                       widget.currentIndex())
        elif isinstance(widget, Slider):
            config.set(getattr(config, widget.objectName(), 70),
                       widget.value())
            text_name = 'BodyLabel_' + widget.objectName().split(
                '_')[1] + '_' + widget.objectName().split('_')[2]
            text_widget = self.findChild(QLabel, name=text_name)
            text_widget.setText(str(widget.value()))

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.SegmentedWidget.setCurrentItem(widget.objectName())

    def is_valid_format(self, input_string):
        # 正则表达式匹配三个整数，用逗号分隔
        pattern = r'^(\d+),(\d+),(\d+)$'
        match = re.match(pattern, input_string)

        # 如果匹配成功，则继续检查数值范围
        if match:
            # 获取匹配到的三个整数,match.group(0)代表整个匹配的字符串
            int_values = [
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3))
            ]

            # 检查每个整数是否在0~255之间
            if all(0 <= value <= 255 for value in int_values):
                return True
            else:
                self.logger.error(self._ui_text("保存失败，int范围不在0~255之间", "Save failed: int values must be in 0~255"))
        else:
            self.logger.error(self._ui_text("保存失败，输入不符合“int,int,int”的格式", "Save failed: input format must be int,int,int"))
        return False

    def _apply_static_i18n(self):
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

        self.BodyLabel_4.setText(self._ui_text("刷取次数", "Run count"))
        self.BodyLabel_22.setText(self._ui_text("疾跑方式", "Sprint mode"))
        self.TitleLabel_2.setText(self._ui_text("日志", "Log"))

        self.BodyLabel_28.setText(self._ui_text("模版图置信度", "Template confidence"))
        self.BodyLabel_29.setText(self._ui_text("计数置信度", "Count confidence"))
        self.BodyLabel_24.setText(self._ui_text("连胜", "Win streak"))
        self.BodyLabel_26.setText(self._ui_text("次后停止", "stop after wins"))
        self.TitleLabel_3.setText(self._ui_text("日志", "Log"))

        self.BodyLabel_25.setText(self._ui_text("运行模式", "Run mode"))
        self.TitleLabel_4.setText(self._ui_text("日志", "Log"))
        self.BodyLabel_27.setText(self._ui_text("运行模式", "Run mode"))
        self.TitleLabel_5.setText(self._ui_text("日志", "Log"))

        self.BodyLabel_32.setText(self._ui_text("刷取次数(-1代表无限刷)", "Run count (-1 means infinite)"))
        self.BodyLabel_31.setText(self._ui_text("模式", "Mode"))
        self.CheckBox_is_speed_up.setText(self._ui_text("是否已手动开启倍速", "I have enabled speed-up manually"))
        self.TitleLabel_7.setText(self._ui_text("日志", "Log"))

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

    def update_label_color(self):
        """
        通过设置style的方式将颜色呈现在label上，这样可以随label缩放
        :return:
        """
        hsv_value = [
            int(value) for value in config.LineEdit_fish_base.value.split(",")
        ]
        # 使用 OpenCV 将 HSV 转换为 BGR
        hsv_array = np.uint8([[[hsv_value[0], hsv_value[1], hsv_value[2]]]])
        bgr_color = cv2.cvtColor(hsv_array, cv2.COLOR_HSV2BGR)[0][0]
        # 将 BGR 转换为 RGB 格式
        rgb_color = (bgr_color[2], bgr_color[1], bgr_color[0])  # BGR to RGB
        # 将 RGB 转换为 #RRGGBB 格式的字符串
        rgb_color_str = f"#{rgb_color[0]:02X}{rgb_color[1]:02X}{rgb_color[2]:02X}"
        # 使用 setStyleSheet 设置 QLabel 的背景颜色
        self.PixmapLabel.setStyleSheet(
            f"background-color: {rgb_color_str};border-radius: 5px;")

    def adjust_color(self):
        self.adjust_color_thread = AdjustColor()
        self.adjust_color_thread.color_changed.connect(
            self.reload_color_config)
        self.adjust_color_thread.start()

    def reload_color_config(self):
        self.LineEdit_fish_base.setText(config.LineEdit_fish_base.value)
        self.LineEdit_fish_upper.setText(config.LineEdit_fish_upper.value)
        self.LineEdit_fish_lower.setText(config.LineEdit_fish_lower.value)
        self.update_label_color()

    def reset_color(self):
        config.set(config.LineEdit_fish_base,
                   config.LineEdit_fish_base.defaultValue)
        config.set(config.LineEdit_fish_upper,
                   config.LineEdit_fish_upper.defaultValue)
        config.set(config.LineEdit_fish_lower,
                   config.LineEdit_fish_lower.defaultValue)
        self.LineEdit_fish_base.setText(config.LineEdit_fish_base.value)
        self.LineEdit_fish_upper.setText(config.LineEdit_fish_upper.value)
        self.LineEdit_fish_lower.setText(config.LineEdit_fish_lower.value)
        self.update_label_color()

    def update_fish_key(self, key):
        # 添加模糊查询
        choices = ["ctrl", "space", "shift"]
        best_match = process.extractOne(key, choices)
        if best_match[1] > 60:
            key = best_match[0]
        self.LineEdit_fish_key.setText(key.lower())
        self.save_changed(self.LineEdit_fish_key)

    def closeEvent(self, event):
        super().closeEvent(event)

    def set_simple_card_enable(self, simple_card, enable: bool):
        children = get_all_children(simple_card)
        for child in children:
            if isinstance(child, CheckBox) or isinstance(
                    child, LineEdit) or isinstance(
                        child, SpinBox) or isinstance(child, ComboBox):
                child.setEnabled(enable)

    def on_fishing_button_click(self):
        """钓鱼开始按键的信号处理"""
        if not self.is_running_fish:
            self.redirectOutput(self.textBrowser_log_fishing)
            self.fishing_task = SubTask(FishingModule)
            self.fishing_task.is_running.connect(self.handle_fishing)
            self.fishing_task.start()
        else:
            self.fishing_task.stop()

    def handle_fishing(self, is_running):
        """钓鱼线程开始与结束的信号处理"""
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_fish, False)
            self.PushButton_start_fishing.setText(self._ui_text('停止钓鱼', 'Stop Fishing'))
            self.is_running_fish = True
        else:
            children = get_all_children(self.SimpleCardWidget_fish)
            for child in children:
                if isinstance(child, CheckBox) or isinstance(child, SpinBox):
                    child.setEnabled(True)
                elif isinstance(child, LineEdit):
                    if not child.objectName() == 'LineEdit_fish_base':
                        child.setEnabled(True)
            self.PushButton_start_fishing.setText(self._ui_text('开始钓鱼', 'Start Fishing'))
            self.is_running_fish = False

    def on_action_button_click(self):
        """周常行动开始按键的信号处理"""
        if not self.is_running_action:
            self.redirectOutput(self.textBrowser_log_action)
            self.action_task = SubTask(OperationModule)
            self.action_task.is_running.connect(self.handle_action)
            self.action_task.start()
        else:
            self.action_task.stop()

    def handle_action(self, is_running):
        """周常行动线程开始与结束的信号处理"""
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_action, False)
            self.PushButton_start_action.setText(self._ui_text("停止行动", "Stop Operation"))
            self.is_running_action = True
        else:
            children = get_all_children(self.SimpleCardWidget_action)
            for child in children:
                if isinstance(child, CheckBox) or isinstance(child, SpinBox):
                    child.setEnabled(True)
                elif isinstance(child, LineEdit):
                    pass
            self.PushButton_start_action.setText(self._ui_text("开始行动", "Start Operation"))
            self.is_running_action = False

    def on_water_bomb_button_click(self):
        if not self.is_running_water_bomb:
            self.redirectOutput(self.textBrowser_log_water_bomb)
            self.water_bomb_task = SubTask(WaterBombModule)
            self.water_bomb_task.is_running.connect(self.handle_water_bomb)
            self.water_bomb_task.start()
        else:
            self.water_bomb_task.stop()

    def handle_water_bomb(self, is_running):
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_water_bomb,
                                        False)
            self.PushButton_start_water_bomb.setText(self._ui_text('停止心动水弹', 'Stop Water Bomb'))
            self.is_running_water_bomb = True
        else:
            self.set_simple_card_enable(self.SimpleCardWidget_water_bomb, True)
            self.PushButton_start_water_bomb.setText(self._ui_text('开始心动水弹', 'Start Water Bomb'))
            self.is_running_water_bomb = False

    def on_alien_guardian_button_click(self):
        if not self.is_running_alien_guardian:
            self.redirectOutput(self.textBrowser_log_alien_guardian)
            self.alien_guardian_task = SubTask(AlienGuardianModule)
            self.alien_guardian_task.is_running.connect(
                self.handle_alien_guardian)
            self.alien_guardian_task.start()
        else:
            self.alien_guardian_task.stop()

    def handle_alien_guardian(self, is_running):
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_alien_guardian,
                                        False)
            self.PushButton_start_alien_guardian.setText(self._ui_text('停止异星守护', 'Stop Alien Guardian'))
            self.is_running_alien_guardian = True
        else:
            self.set_simple_card_enable(self.SimpleCardWidget_alien_guardian,
                                        True)
            self.PushButton_start_alien_guardian.setText(self._ui_text('开始异星守护', 'Start Alien Guardian'))
            self.is_running_alien_guardian = False

    def on_maze_button_click(self):
        if not self.is_running_maze:
            self.redirectOutput(self.textBrowser_log_maze)
            self.maze_task = SubTask(MazeModule)
            self.maze_task.is_running.connect(self.handle_maze)
            self.maze_task.start()
        else:
            self.maze_task.stop()

    def handle_maze(self, is_running):
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_maze, False)
            self.PushButton_start_maze.setText(self._ui_text('停止迷宫', 'Stop Maze'))
            self.is_running_maze = True
        else:
            self.set_simple_card_enable(self.SimpleCardWidget_maze, True)
            self.PushButton_start_maze.setText(self._ui_text('开始迷宫', 'Start Maze'))
            self.is_running_maze = False

    def on_drink_button_click(self):
        """酒馆开始按键的信号处理"""
        if not self.is_running_drink:
            self.redirectOutput(self.textBrowser_log_drink)
            self.drink_task = SubTask(DrinkModule)
            self.drink_task.is_running.connect(self.handle_drink)
            self.drink_task.start()
        else:
            self.drink_task.stop()

    def handle_drink(self, is_running):
        """钓鱼线程开始与结束的信号处理"""
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_card, False)
            self.PushButton_start_drink.setText(self._ui_text('停止喝酒', 'Stop Drink'))
            self.is_running_drink = True
        else:
            self.set_simple_card_enable(self.SimpleCardWidget_card, True)
            self.PushButton_start_drink.setText(self._ui_text('开始喝酒', 'Start Drink'))
            self.is_running_drink = False

    def on_capture_pals_button_click(self):
        """抓帕鲁开始按键的信号处理"""
        if not self.is_running_capture_pals:
            self.redirectOutput(self.textBrowser_log_capture_pals)
            self.capture_pals_task = SubTask(CapturePalsModule)
            self.capture_pals_task.is_running.connect(self.handle_capture_pals)
            self.capture_pals_task.start()
        else:
            self.capture_pals_task.stop()

    def handle_capture_pals(self, is_running):
        """抓帕鲁线程开始与结束的信号处理"""
        if is_running:
            self.set_simple_card_enable(self.SimpleCardWidget_capture_pals, False)
            self.PushButton_start_capture_pals.setText(self._ui_text('停止抓帕鲁', 'Stop Capture Pals'))
            self.is_running_capture_pals = True
        else:
            self.set_simple_card_enable(self.SimpleCardWidget_capture_pals, True)
            self.PushButton_start_capture_pals.setText(self._ui_text('开始抓帕鲁', 'Start Capture Pals'))
            self.is_running_capture_pals = False

    def showEvent(self, event):
        super().showEvent(event)
        # 只要切回这个页面，就强制从 config 重新读取一次最新数据覆盖 UI
        self._load_config()
