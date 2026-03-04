from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QTextBrowser,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    ListWidget,
    PopUpAniStackedWidget,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SimpleCardWidget,
    SpinBox,
    StrongBodyLabel,
    TitleLabel,
    ToolButton,
)


class TaskListView(ListWidget):
    orderChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setStyleSheet(
            "TaskListView { background: transparent; border: none; outline: none; }"
            "TaskListView::item { background: transparent; }"
        )
        self.model().rowsMoved.connect(self._emit_order_changed)

    def _emit_order_changed(self):
        self.orderChanged.emit(self.get_task_order())

    def add_task_item(self, task_item_widget):
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(200, 38))
        item.setData(Qt.ItemDataRole.UserRole, task_item_widget.task_id)
        self.addItem(item)
        self.setItemWidget(item, task_item_widget)

    def get_task_order(self):
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
            if self.item(i).data(Qt.ItemDataRole.UserRole)
        ]


class TaskItemWidget(QWidget):
    checkbox_state_changed = Signal(str, bool)
    settings_clicked = Signal(str)

    def __init__(self, task_id, zh_name, en_name, is_enabled, is_non_chinese_ui, parent=None):
        super().__init__(parent)
        self.task_id = task_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.checkbox = CheckBox(parent=self)
        cb_font = self.checkbox.font()
        if cb_font.pointSize() <= 0:
            cb_font.setPointSize(10)
            self.checkbox.setFont(cb_font)
        self.checkbox.setChecked(is_enabled)
        self.checkbox.stateChanged.connect(
            lambda: self.checkbox_state_changed.emit(self.task_id, self.checkbox.isChecked())
        )

        self.label = BodyLabel(en_name if is_non_chinese_ui else zh_name, self)

        self.btn = ToolButton(self)
        self.btn.setIcon(FIF.SETTING)
        btn_font = self.btn.font()
        btn_font.setPointSize(10)
        self.btn.setFont(btn_font)
        self.btn.clicked.connect(lambda: self.settings_clicked.emit(self.task_id))

        layout.addWidget(self.checkbox, 0)
        layout.addWidget(self.label, 1)
        layout.addStretch(1)
        layout.addWidget(self.btn, 0)


class ExecutionRuleWidget(QWidget):
    deleted = Signal(QWidget)
    changed = Signal()

    def __init__(self, is_non_chinese_ui=False, parent=None):
        super().__init__(parent)
        self.is_non_chinese_ui = is_non_chinese_ui

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.freq_combo = ComboBox(self)
        self.freq_combo.addItems(
            ["Daily", "Weekly", "Monthly"] if is_non_chinese_ui else ["每天", "每周", "每月"]
        )
        self.week_combo = ComboBox(self)
        self.week_combo.addItems(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            if is_non_chinese_ui
            else ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        )
        self.month_combo = ComboBox(self)
        self.month_combo.addItems(
            [str(day) for day in range(1, 32)]
            if is_non_chinese_ui
            else [f"{day}日" for day in range(1, 32)]
        )
        self.month_combo.setFixedWidth(72)

        self.time_edit = LineEdit(self)
        self.time_edit.setText("05:00")
        self.time_edit.setFixedWidth(70)

        self.runs_spin = SpinBox(self)
        self.runs_spin.setRange(1, 99)
        self.runs_spin.setMinimumWidth(120)
        self.runs_spin.setPrefix("Count: " if is_non_chinese_ui else "次数: ")
        self.runs_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.delete_btn = ToolButton(self)
        self.delete_btn.setIcon(FIF.DELETE)

        for w in [self.freq_combo, self.week_combo, self.month_combo, self.time_edit, self.runs_spin, self.delete_btn]:
            font = w.font()
            font.setPointSize(10)
            w.setFont(font)

        layout.addWidget(self.freq_combo)
        layout.addWidget(self.week_combo)
        layout.addWidget(self.month_combo)
        time_label_text = "Time:" if is_non_chinese_ui else "时间:"
        layout.addWidget(BodyLabel(time_label_text, self))
        layout.addWidget(self.time_edit)
        layout.addWidget(BodyLabel("after" if is_non_chinese_ui else "后", self))
        layout.addWidget(self.runs_spin)
        layout.addWidget(self.delete_btn)
        layout.addStretch(1)

        self.freq_combo.currentIndexChanged.connect(self._update_visibility)
        self.delete_btn.clicked.connect(lambda: self.deleted.emit(self))

        for w in [self.freq_combo, self.week_combo, self.month_combo]:
            w.currentIndexChanged.connect(self.changed)
        for w in [self.runs_spin]:
            w.valueChanged.connect(self.changed)
        self.time_edit.editingFinished.connect(self.changed)

        self._update_visibility()

    def _update_visibility(self):
        idx = self.freq_combo.currentIndex()
        self.week_combo.setVisible(idx == 1)
        self.month_combo.setVisible(idx == 2)
        self.changed.emit()

    def set_data(self, data: dict):
        types = ["daily", "weekly", "monthly"]
        try:
            idx = types.index(data.get("type", "daily"))
            self.freq_combo.setCurrentIndex(idx)
            if idx == 1:
                self.week_combo.setCurrentIndex(data.get("day", 0))
            elif idx == 2:
                month_day = int(data.get("day", 1))
                month_day = max(1, min(31, month_day))
                self.month_combo.setCurrentIndex(month_day - 1)
            self.time_edit.setText(data.get("time", "05:00"))
            self.runs_spin.setValue(data.get("max_runs", 1))
        except Exception:
            pass
        self._update_visibility()

    def get_data(self):
        t = ["daily", "weekly", "monthly"]
        idx = self.freq_combo.currentIndex()
        day = self.week_combo.currentIndex() if idx == 1 else (self.month_combo.currentIndex() + 1)
        return {
            "type": t[idx],
            "day": day,
            "time": self.time_edit.text(),
            "max_runs": self.runs_spin.value(),
        }


class SharedSchedulingPanel(QWidget):
    config_changed = Signal(str, dict)

    def __init__(self, is_non_chinese_ui=False, parent=None):
        super().__init__(parent)
        self.task_id = None
        self.is_non_chinese_ui = is_non_chinese_ui
        self.setFixedHeight(220)

        self.setStyleSheet("SharedSchedulingPanel { border-top: 1px solid rgba(0,0,0,0.1); }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        activation_row = QHBoxLayout()
        activation_row.setContentsMargins(0, 0, 0, 0)
        activation_row.setSpacing(6)

        enable_text = "Enable Cycle" if is_non_chinese_ui else "启用周期"
        self.enable_checkbox = CheckBox(enable_text, self)
        font = self.enable_checkbox.font()
        font.setPointSize(10)
        self.enable_checkbox.setFont(font)
        activation_row.addWidget(self.enable_checkbox)
        activation_row.addStretch(1)

        activation_label_text = "Activation:" if is_non_chinese_ui else "生效周期："
        self.activation_label = StrongBodyLabel(activation_label_text, self)
        activation_row.addWidget(self.activation_label)
        activation_row.addSpacing(2)

        self.activation_widget = QWidget(self)
        self.activation_widget.setStyleSheet("background: transparent;")
        self.activation_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.activation_widget.setMaximumHeight(42)
        self.activation_layout = QVBoxLayout(self.activation_widget)
        self.activation_layout.setContentsMargins(0, 0, 0, 0)
        self.activation_layout.setSpacing(0)
        self.activation_layout.addStretch(1)
        activation_row.addWidget(self.activation_widget, 1)

        main_layout.addLayout(activation_row)

        exec_title = "Execution Triggers (Add multiple times)" if is_non_chinese_ui else "执行策略（可添加多个时间点）"
        main_layout.addWidget(StrongBodyLabel(exec_title, self))

        self.rules_scroll = ScrollArea(self)
        self.rules_scroll.setWidgetResizable(True)
        self.rules_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self.rules_widget = QWidget(self.rules_scroll)
        self.rules_widget.setStyleSheet("background: transparent;")
        self.rules_layout = QVBoxLayout(self.rules_widget)
        self.rules_layout.setContentsMargins(0, 0, 0, 0)
        self.rules_layout.setSpacing(6)
        self.rules_layout.addStretch(1)

        self.rules_scroll.setWidget(self.rules_widget)
        main_layout.addWidget(self.rules_scroll, 1)

        add_text = "Add Trigger" if is_non_chinese_ui else "添加时间"
        self.add_btn = PushButton(FIF.ADD, add_text, self)
        btn_font = self.add_btn.font()
        btn_font.setPointSize(10)
        self.add_btn.setFont(btn_font)
        self.add_btn.clicked.connect(lambda: self._add_rule({}))
        main_layout.addWidget(self.add_btn)

        self.enable_checkbox.stateChanged.connect(self._emit_change)

    def _iter_activation_rule_widgets(self):
        for i in range(self.activation_layout.count() - 1):
            widget = self.activation_layout.itemAt(i).widget()
            if isinstance(widget, ExecutionRuleWidget):
                yield widget

    def _add_activation_rule(self, data):
        w = ExecutionRuleWidget(self.is_non_chinese_ui, self)
        w.runs_spin.setVisible(False)
        w.runs_spin.setEnabled(False)
        w.runs_spin.setValue(1)
        w.delete_btn.setVisible(False)
        w.delete_btn.setEnabled(False)
        w.deleted.connect(self._remove_activation_rule)
        w.changed.connect(self._emit_change)
        if data:
            w.set_data(data)
        self.activation_layout.insertWidget(self.activation_layout.count() - 1, w)
        self._update_activation_delete_btns()
        self._emit_change()

    def _remove_activation_rule(self, w):
        if len(list(self._iter_activation_rule_widgets())) <= 1:
            return
        self.activation_layout.removeWidget(w)
        w.deleteLater()
        self._update_activation_delete_btns()
        self._emit_change()

    def _update_activation_delete_btns(self):
        rules = list(self._iter_activation_rule_widgets())
        for w in rules:
            w.delete_btn.setVisible(False)
            w.delete_btn.setEnabled(False)

    def _iter_rule_widgets(self):
        for i in range(self.rules_layout.count() - 1):
            widget = self.rules_layout.itemAt(i).widget()
            if isinstance(widget, ExecutionRuleWidget):
                yield widget

    def _add_rule(self, data):
        w = ExecutionRuleWidget(self.is_non_chinese_ui, self)
        w.deleted.connect(self._remove_rule)
        w.changed.connect(self._emit_change)
        if data:
            w.set_data(data)
        self.rules_layout.insertWidget(self.rules_layout.count() - 1, w)
        self._update_delete_btns()
        self._emit_change()

    def _remove_rule(self, w):
        if len(list(self._iter_rule_widgets())) <= 1:
            return
        self.rules_layout.removeWidget(w)
        w.deleteLater()
        self._update_delete_btns()
        self._emit_change()

    def _update_delete_btns(self):
        rules = list(self._iter_rule_widgets())
        can_delete = len(rules) > 1
        for w in rules:
            w.delete_btn.setVisible(can_delete)

    def load_task(self, task_id, config_dict):
        self.task_id = task_id

        self.enable_checkbox.blockSignals(True)

        self.enable_checkbox.setChecked(config_dict.get("use_periodic", True))

        self.enable_checkbox.blockSignals(False)

        while self.activation_layout.count() > 1:
            item = self.activation_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        activation_rules = config_dict.get("activation_config")
        if activation_rules is None:
            activation_rules = config_dict.get("refresh_config", {}) or {}
        if isinstance(activation_rules, dict):
            activation_rules = [activation_rules]
        if not activation_rules:
            activation_rules = [{"type": "daily", "time": "05:00", "max_runs": 1}]

        self._add_activation_rule(activation_rules[0])

        self._update_activation_delete_btns()

        while self.rules_layout.count() > 1:
            item = self.rules_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        rules = config_dict.get("execution_config", [{"type": "daily", "time": "05:00", "max_runs": 1}])
        if isinstance(rules, dict):
            rules = [rules]
        if not rules:
            rules = [{"type": "daily", "time": "05:00", "max_runs": 1}]

        for rule in rules:
            self._add_rule(rule)

        self._update_delete_btns()

    def _emit_change(self):
        if not self.task_id:
            return

        activation_rules = [w.get_data() for w in self._iter_activation_rule_widgets()]
        rules = [w.get_data() for w in self._iter_rule_widgets()]

        new_cfg = {
            "use_periodic": self.enable_checkbox.isChecked(),
            "activation_config": activation_rules,
            "execution_config": rules,
        }
        self.config_changed.emit(self.task_id, new_cfg)


class BaseDailyPage(QWidget):
    def __init__(self, object_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

    def finalize(self):
        self.main_layout.addStretch(1)


class EnterGamePage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_5", parent=parent)

        top_line = QHBoxLayout()
        self.StrongBodyLabel_4 = StrongBodyLabel(self)
        self.StrongBodyLabel_4.setObjectName("StrongBodyLabel_4")
        self.PrimaryPushButton_path_tutorial = PrimaryPushButton(self)
        self.PrimaryPushButton_path_tutorial.setObjectName("PrimaryPushButton_path_tutorial")
        top_line.addWidget(self.StrongBodyLabel_4)
        top_line.addWidget(self.PrimaryPushButton_path_tutorial)

        self.LineEdit_game_directory = LineEdit(self)
        self.LineEdit_game_directory.setEnabled(False)
        self.LineEdit_game_directory.setObjectName("LineEdit_game_directory")

        action_line = QHBoxLayout()
        self.CheckBox_open_game_directly = CheckBox(self)
        self.CheckBox_open_game_directly.setObjectName("CheckBox_open_game_directly")
        self.PushButton_select_directory = PushButton(self)
        self.PushButton_select_directory.setObjectName("PushButton_select_directory")
        action_line.addWidget(self.CheckBox_open_game_directly, 1)
        action_line.addWidget(self.PushButton_select_directory)

        self.BodyLabel_enter_tip = BodyLabel(self)
        self.BodyLabel_enter_tip.setObjectName("BodyLabel_enter_tip")
        self.BodyLabel_enter_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_enter_tip.setWordWrap(True)

        self.main_layout.addLayout(top_line)
        self.main_layout.addWidget(self.LineEdit_game_directory)
        self.main_layout.addLayout(action_line)
        self.main_layout.addWidget(self.BodyLabel_enter_tip)
        self.finalize()


class CollectSuppliesPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_3", parent=parent)

        self.CheckBox_mail = CheckBox(self)
        self.CheckBox_mail.setObjectName("CheckBox_mail")
        self.CheckBox_fish_bait = CheckBox(self)
        self.CheckBox_fish_bait.setObjectName("CheckBox_fish_bait")
        self.CheckBox_dormitory = CheckBox(self)
        self.CheckBox_dormitory.setObjectName("CheckBox_dormitory")

        redeem_line = QHBoxLayout()
        self.CheckBox_redeem_code = CheckBox(self)
        self.CheckBox_redeem_code.setObjectName("CheckBox_redeem_code")
        self.PrimaryPushButton_import_codes = PrimaryPushButton(self)
        self.PrimaryPushButton_import_codes.setObjectName("PrimaryPushButton_import_codes")
        self.PushButton_reset_codes = PushButton(self)
        self.PushButton_reset_codes.setObjectName("PushButton_reset_codes")
        redeem_line.addWidget(self.CheckBox_redeem_code, 1)
        redeem_line.addWidget(self.PrimaryPushButton_import_codes)
        redeem_line.addWidget(self.PushButton_reset_codes)

        self.textBrowser_import_codes = QTextBrowser(self)
        self.textBrowser_import_codes.setObjectName("textBrowser_import_codes")
        self.textBrowser_import_codes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.textBrowser_import_codes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.BodyLabel_collect_supplies = BodyLabel(self)
        self.BodyLabel_collect_supplies.setObjectName("BodyLabel_collect_supplies")
        self.BodyLabel_collect_supplies.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_collect_supplies.setWordWrap(True)

        self.main_layout.addWidget(self.CheckBox_mail)
        self.main_layout.addWidget(self.CheckBox_fish_bait)
        self.main_layout.addWidget(self.CheckBox_dormitory)
        self.main_layout.addLayout(redeem_line)
        self.main_layout.addWidget(self.textBrowser_import_codes)
        self.main_layout.addWidget(self.BodyLabel_collect_supplies)
        self.finalize()


class ShopPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_shop", parent=parent)

        self.ScrollArea = ScrollArea(self)
        self.ScrollArea.setObjectName("ScrollArea")
        self.ScrollArea.setWidgetResizable(True)

        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")

        self.gridLayout = QGridLayout(self.scrollAreaWidgetContents)
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)

        self.StrongBodyLabel = StrongBodyLabel(self.scrollAreaWidgetContents)
        self.StrongBodyLabel.setObjectName("StrongBodyLabel")
        self.gridLayout.addWidget(self.StrongBodyLabel, 0, 0, 1, 1)

        self.widget_2 = QWidget(self.scrollAreaWidgetContents)
        self.widget_2.setObjectName("widget_2")
        self.gridLayout.addWidget(self.widget_2, 1, 0, 1, 1)

        self.widget = QWidget(self.scrollAreaWidgetContents)
        self.widget.setObjectName("widget")
        self.gridLayout.addWidget(self.widget, 2, 0, 1, 1)

        buy_names = [
            "CheckBox_buy_3", "CheckBox_buy_4", "CheckBox_buy_5",
            "CheckBox_buy_6", "CheckBox_buy_7", "CheckBox_buy_8",
            "CheckBox_buy_9", "CheckBox_buy_10", "CheckBox_buy_11",
            "CheckBox_buy_12", "CheckBox_buy_13", "CheckBox_buy_14", "CheckBox_buy_15",
        ]

        row = 4
        for name in buy_names:
            checkbox = CheckBox(self.scrollAreaWidgetContents)
            checkbox.setObjectName(name)
            checkbox.setMinimumSize(QSize(29, 22))
            setattr(self, name, checkbox)
            self.gridLayout.addWidget(checkbox, row, 0, 1, 1)
            row += 1

        self.ScrollArea.setWidget(self.scrollAreaWidgetContents)
        self.main_layout.addWidget(self.ScrollArea)
        self.finalize()


class UsePowerPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_2", parent=parent)

        first_line = QHBoxLayout()
        self.CheckBox_is_use_power = CheckBox(self)
        self.CheckBox_is_use_power.setObjectName("CheckBox_is_use_power")
        self.ComboBox_power_day = ComboBox(self)
        self.ComboBox_power_day.setObjectName("ComboBox_power_day")
        self.BodyLabel_6 = BodyLabel(self)
        self.BodyLabel_6.setObjectName("BodyLabel_6")
        first_line.addWidget(self.CheckBox_is_use_power)
        first_line.addWidget(self.ComboBox_power_day)
        first_line.addWidget(self.BodyLabel_6)

        self.StrongBodyLabel_2 = StrongBodyLabel(self)
        self.StrongBodyLabel_2.setObjectName("StrongBodyLabel_2")
        self.ComboBox_power_usage = ComboBox(self)
        self.ComboBox_power_usage.setObjectName("ComboBox_power_usage")

        self.main_layout.addLayout(first_line)
        self.main_layout.addWidget(self.StrongBodyLabel_2)
        self.main_layout.addWidget(self.ComboBox_power_usage)
        self.finalize()


class PersonPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_4", parent=parent)

        self.StrongBodyLabel_3 = StrongBodyLabel(self)
        self.StrongBodyLabel_3.setObjectName("StrongBodyLabel_3")

        self.BodyLabel_3 = BodyLabel(self)
        self.BodyLabel_3.setObjectName("BodyLabel_3")
        self.LineEdit_c1 = LineEdit(self)
        self.LineEdit_c1.setObjectName("LineEdit_c1")

        self.BodyLabel_4 = BodyLabel(self)
        self.BodyLabel_4.setObjectName("BodyLabel_4")
        self.LineEdit_c2 = LineEdit(self)
        self.LineEdit_c2.setObjectName("LineEdit_c2")

        self.BodyLabel_5 = BodyLabel(self)
        self.BodyLabel_5.setObjectName("BodyLabel_5")
        self.LineEdit_c3 = LineEdit(self)
        self.LineEdit_c3.setObjectName("LineEdit_c3")

        self.BodyLabel_8 = BodyLabel(self)
        self.BodyLabel_8.setObjectName("BodyLabel_8")
        self.LineEdit_c4 = LineEdit(self)
        self.LineEdit_c4.setObjectName("LineEdit_c4")

        self.CheckBox_is_use_chip = CheckBox(self)
        self.CheckBox_is_use_chip.setObjectName("CheckBox_is_use_chip")

        self.BodyLabel_person_tip = BodyLabel(self)
        self.BodyLabel_person_tip.setObjectName("BodyLabel_person_tip")
        self.BodyLabel_person_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_person_tip.setWordWrap(True)

        self.main_layout.addWidget(self.StrongBodyLabel_3)
        self.main_layout.addLayout(self._line(self.BodyLabel_3, self.LineEdit_c1))
        self.main_layout.addLayout(self._line(self.BodyLabel_4, self.LineEdit_c2))
        self.main_layout.addLayout(self._line(self.BodyLabel_5, self.LineEdit_c3))
        self.main_layout.addLayout(self._line(self.BodyLabel_8, self.LineEdit_c4))
        self.main_layout.addWidget(self.CheckBox_is_use_chip)
        self.main_layout.addWidget(self.BodyLabel_person_tip)
        self.finalize()

    @staticmethod
    def _line(label, edit):
        line = QHBoxLayout()
        line.addWidget(label, 1)
        line.addWidget(edit, 2)
        return line


class ChasmPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_chasm", parent=parent)

        self.BodyLabel_chasm_tip = BodyLabel(self)
        self.BodyLabel_chasm_tip.setObjectName("BodyLabel_chasm_tip")
        self.BodyLabel_chasm_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_chasm_tip.setWordWrap(True)

        self.main_layout.addWidget(self.BodyLabel_chasm_tip)
        self.finalize()


class RewardPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_reward", parent=parent)

        self.BodyLabel_reward_tip = BodyLabel(self)
        self.BodyLabel_reward_tip.setObjectName("BodyLabel_reward_tip")
        self.BodyLabel_reward_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_reward_tip.setWordWrap(True)

        self.main_layout.addWidget(self.BodyLabel_reward_tip)
        self.finalize()


class DailyView(QWidget):
    def __init__(self, parent=None, is_non_chinese_ui=False):
        super().__init__(parent)
        self.setObjectName("daily")
        self.is_non_chinese_ui = is_non_chinese_ui

        self.gridLayout_2 = QGridLayout(self)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_2.setSpacing(0)

        self._build_option_card()
        self._build_action_card()
        self._build_setting_card()
        self._build_log_card()
        self._build_tips_card()

        # Force the top row to expand and the bottom row to stay compact
        self.gridLayout_2.setRowStretch(0, 1)
        self.gridLayout_2.setRowStretch(1, 0)

    def _build_option_card(self):
        self.SimpleCardWidget_option = SimpleCardWidget(self)
        self.SimpleCardWidget_option.setObjectName("SimpleCardWidget_option")
        self.SimpleCardWidget_option.setMinimumWidth(200)

        layout = QVBoxLayout(self.SimpleCardWidget_option)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)

        self.taskListWidget = TaskListView(self.SimpleCardWidget_option)
        self.taskListWidget.setObjectName("taskListWidget")
        layout.addWidget(self.taskListWidget, 1)

        btn_row = QHBoxLayout()
        hint_text = "Drag to reorder" if self.is_non_chinese_ui else "拖动可调整任务顺序"
        self.hint_label = BodyLabel(hint_text, self.SimpleCardWidget_option)
        self.hint_label.setObjectName("BodyLabel_drag_hint")
        btn_row.addWidget(self.hint_label, 1)
        btn_row.addStretch(1)
        self.PushButton_select_all = PushButton(self.SimpleCardWidget_option)
        self.PushButton_select_all.setObjectName("PushButton_select_all")
        self.PushButton_no_select = PushButton(self.SimpleCardWidget_option)
        self.PushButton_no_select.setObjectName("PushButton_no_select")
        btn_row.addWidget(self.PushButton_select_all)
        btn_row.addWidget(self.PushButton_no_select)

        layout.addSpacing(6)
        layout.addLayout(btn_row)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_option, 0, 0, 1, 1)

    def _build_action_card(self):
        self.SimpleCardWidget_3 = SimpleCardWidget(self)
        self.SimpleCardWidget_3.setObjectName("SimpleCardWidget_3")
        self.SimpleCardWidget_3.setMinimumWidth(237)
        self.SimpleCardWidget_3.setFixedHeight(220)

        layout = QVBoxLayout(self.SimpleCardWidget_3)
        self.BodyLabel = BodyLabel(self.SimpleCardWidget_3)
        self.BodyLabel.setObjectName("BodyLabel")
        self.ComboBox_after_use = ComboBox(self.SimpleCardWidget_3)
        self.ComboBox_after_use.setObjectName("ComboBox_after_use")
        self.PushButton_start = PushButton(self.SimpleCardWidget_3)
        self.PushButton_start.setObjectName("PushButton_start")
        self.PushButton_start.setMinimumSize(QSize(0, 60))
        self.PushButton_start.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum))

        layout.addStretch(1)
        layout.addWidget(self.BodyLabel)
        layout.addWidget(self.ComboBox_after_use)
        layout.addStretch(1)
        layout.addWidget(self.PushButton_start)
        layout.addStretch(1)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_3, 1, 0, 1, 1)

    def _build_setting_card(self):
        self.SimpleCardWidget_2 = SimpleCardWidget(self)
        self.SimpleCardWidget_2.setObjectName("SimpleCardWidget_2")
        self.SimpleCardWidget_2.setMinimumWidth(237)

        layout = QVBoxLayout(self.SimpleCardWidget_2)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(4)

        self.TitleLabel_setting = TitleLabel(self.SimpleCardWidget_2)
        self.TitleLabel_setting.setObjectName("TitleLabel_setting")

        self.PopUpAniStackedWidget = PopUpAniStackedWidget(self.SimpleCardWidget_2)
        self.PopUpAniStackedWidget.setObjectName("PopUpAniStackedWidget")

        self.page_enter = EnterGamePage(self.PopUpAniStackedWidget)
        self.page_collect = CollectSuppliesPage(self.PopUpAniStackedWidget)
        self.page_shop = ShopPage(self.PopUpAniStackedWidget)
        self.page_use_power = UsePowerPage(self.PopUpAniStackedWidget)
        self.page_person = PersonPage(self.PopUpAniStackedWidget)
        self.page_chasm = ChasmPage(self.PopUpAniStackedWidget)
        self.page_reward = RewardPage(self.PopUpAniStackedWidget)

        self.PopUpAniStackedWidget.addWidget(self.page_enter)
        self.PopUpAniStackedWidget.addWidget(self.page_collect)
        self.PopUpAniStackedWidget.addWidget(self.page_shop)
        self.PopUpAniStackedWidget.addWidget(self.page_use_power)
        self.PopUpAniStackedWidget.addWidget(self.page_person)
        self.PopUpAniStackedWidget.addWidget(self.page_chasm)
        self.PopUpAniStackedWidget.addWidget(self.page_reward)

        layout.addWidget(self.TitleLabel_setting)
        layout.addWidget(self.PopUpAniStackedWidget, 1)

        self.shared_scheduling_panel = SharedSchedulingPanel(self.is_non_chinese_ui, self.SimpleCardWidget_2)
        self.shared_scheduling_panel.setObjectName("shared_scheduling_panel")
        layout.addWidget(self.shared_scheduling_panel, 0)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_2, 0, 1, 2, 1)

        self._alias_page_widgets()

    def _alias_page_widgets(self):
        page_attrs = [
            "StrongBodyLabel_4", "PrimaryPushButton_path_tutorial", "CheckBox_open_game_directly",
            "LineEdit_game_directory", "PushButton_select_directory", "BodyLabel_enter_tip",
            "CheckBox_mail", "CheckBox_redeem_code", "CheckBox_dormitory", "CheckBox_fish_bait",
            "PushButton_reset_codes", "PrimaryPushButton_import_codes", "textBrowser_import_codes",
            "BodyLabel_collect_supplies",
            "ScrollArea", "scrollAreaWidgetContents", "gridLayout", "StrongBodyLabel", "widget", "widget_2",
            "CheckBox_buy_3", "CheckBox_buy_4", "CheckBox_buy_5", "CheckBox_buy_6", "CheckBox_buy_7",
            "CheckBox_buy_8", "CheckBox_buy_9", "CheckBox_buy_10", "CheckBox_buy_11", "CheckBox_buy_12",
            "CheckBox_buy_13", "CheckBox_buy_14", "CheckBox_buy_15",
            "ComboBox_power_usage", "StrongBodyLabel_2", "CheckBox_is_use_power", "ComboBox_power_day", "BodyLabel_6",
            "BodyLabel_8", "LineEdit_c4", "BodyLabel_person_tip", "BodyLabel_5", "LineEdit_c3",
            "CheckBox_is_use_chip", "BodyLabel_3", "LineEdit_c1", "StrongBodyLabel_3", "BodyLabel_4", "LineEdit_c2",
            "BodyLabel_chasm_tip", "BodyLabel_reward_tip",
        ]

        pages = [
            self.page_enter,
            self.page_collect,
            self.page_shop,
            self.page_use_power,
            self.page_person,
            self.page_chasm,
            self.page_reward,
        ]
        for attr in page_attrs:
            for page in pages:
                if hasattr(page, attr):
                    setattr(self, attr, getattr(page, attr))
                    break

    def _build_log_card(self):
        self.SimpleCardWidget = SimpleCardWidget(self)
        self.SimpleCardWidget.setObjectName("SimpleCardWidget")
        self.SimpleCardWidget.setMinimumWidth(246)
        self.SimpleCardWidget.setMinimumHeight(0)
        self.SimpleCardWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)

        layout = QVBoxLayout(self.SimpleCardWidget)
        layout.setSpacing(4)

        self.TitleLabel = TitleLabel(self.SimpleCardWidget)
        self.TitleLabel.setObjectName("TitleLabel")
        self.textBrowser_log = QTextBrowser(self.SimpleCardWidget)
        self.textBrowser_log.setObjectName("textBrowser_log")
        self.textBrowser_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(self.TitleLabel)
        layout.addWidget(self.textBrowser_log)

        self.gridLayout_2.addWidget(self.SimpleCardWidget, 0, 2, 1, 1)

    def _build_tips_card(self):
        self.SimpleCardWidget_tips = SimpleCardWidget(self)
        self.SimpleCardWidget_tips.setObjectName("SimpleCardWidget_tips")
        self.SimpleCardWidget_tips.setMinimumWidth(237)
        self.SimpleCardWidget_tips.setMinimumHeight(0)
        self.SimpleCardWidget_tips.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.SimpleCardWidget_tips.setFixedHeight(220)

        layout = QVBoxLayout(self.SimpleCardWidget_tips)
        layout.setSpacing(3)

        self.TitleLabel_3 = TitleLabel(self.SimpleCardWidget_tips)
        self.TitleLabel_3.setObjectName("TitleLabel_3")
        self.ScrollArea_tips = ScrollArea(self.SimpleCardWidget_tips)
        self.ScrollArea_tips.setObjectName("ScrollArea_tips")
        self.ScrollArea_tips.setWidgetResizable(True)

        self.scrollAreaWidgetContents_tips = QWidget()
        self.scrollAreaWidgetContents_tips.setObjectName("scrollAreaWidgetContents_tips")
        self.gridLayout_tips = QGridLayout(self.scrollAreaWidgetContents_tips)
        self.gridLayout_tips.setObjectName("gridLayout_tips")
        self.gridLayout_tips.setContentsMargins(0, 0, 0, 0)

        self.ScrollArea_tips.setWidget(self.scrollAreaWidgetContents_tips)

        layout.addWidget(self.TitleLabel_3)
        layout.addWidget(self.ScrollArea_tips)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_tips, 1, 2, 1, 1)
