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
from PySide6.QtGui import QIntValidator
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
    TextEdit,
    isDarkTheme,
)


class TaskListView(ListWidget):
    orderChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        # 【修复】：追加 hover 和 selected 的透明属性
        self.setStyleSheet(
            "TaskListView { background: transparent; border: none; outline: none; }"
            "TaskListView::item { background: transparent; }"
            "TaskListView::item:hover { background: transparent; }"
            "TaskListView::item:selected { background: transparent; }"
        )
        self.model().rowsMoved.connect(self._emit_order_changed)

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

        # 【新增】：彻底剥夺“启动游戏”项的被拖拽能力
        if task_item_widget.task_id == "task_login":
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)

        self.addItem(item)
        self.setItemWidget(item, task_item_widget)

    def get_task_order(self):
        return [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
            if self.item(i).data(Qt.ItemDataRole.UserRole)
        ]


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
        self.time_edit.setText("00:00")
        self.time_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_edit.setFixedWidth(64)

        self.runs_edit = LineEdit(self)
        self.runs_edit.setValidator(QIntValidator(1, 99, self))
        self.runs_edit.setText("1")
        self.runs_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.runs_edit.setMinimumWidth(40)
        self.runs_edit.setMaximumWidth(60)

        self.delete_btn = ToolButton(self)
        self.delete_btn.setIcon(FIF.DELETE)

        for w in [self.freq_combo, self.week_combo, self.month_combo, self.time_edit, self.runs_edit, self.delete_btn]:
            font = w.font()
            font.setPointSize(10)
            w.setFont(font)

        self.label_after_time = BodyLabel("run" if is_non_chinese_ui else "执行", self)
        self.label_times = BodyLabel("time(s)" if is_non_chinese_ui else "次", self)

        layout.addWidget(self.freq_combo)
        layout.addWidget(self.week_combo)
        layout.addWidget(self.month_combo)
        layout.addWidget(BodyLabel("Time:" if is_non_chinese_ui else "时间:", self))
        layout.addWidget(self.time_edit)

        layout.addWidget(self.label_after_time)
        layout.addWidget(self.runs_edit)
        layout.addWidget(self.label_times)
        layout.addWidget(self.delete_btn)
        layout.addStretch(1)

        self.freq_combo.currentIndexChanged.connect(self._update_visibility)
        self.delete_btn.clicked.connect(lambda: self.deleted.emit(self))

        for w in [self.freq_combo, self.week_combo, self.month_combo]:
            w.currentIndexChanged.connect(self.changed)

        self.runs_edit.textChanged.connect(self.changed)
        self.time_edit.textChanged.connect(self.changed)

        self._update_visibility()

    def set_runs_visible(self, visible: bool):
        self.label_after_time.setVisible(visible)
        self.runs_edit.setVisible(visible)
        self.label_times.setVisible(visible)

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
            self.time_edit.setText(data.get("time", "00:00"))
            self.runs_edit.setText(str(data.get("max_runs", 1)))
        except Exception:
            pass
        self._update_visibility()

    def get_data(self):
        t = ["daily", "weekly", "monthly"]
        idx = self.freq_combo.currentIndex()
        day = self.week_combo.currentIndex() if idx == 1 else (self.month_combo.currentIndex() + 1)
        runs_text = self.runs_edit.text()
        runs_val = int(runs_text) if runs_text.isdigit() else 1

        return {
            "type": t[idx],
            "day": day,
            "time": self.time_edit.text(),
            "max_runs": runs_val,
        }


class TaskItemWidget(QWidget):
    checkbox_state_changed = Signal(str, bool)
    settings_clicked = Signal(str)
    play_clicked = Signal(str)
    play_from_here_clicked = Signal(str)

    def __init__(self, task_id, zh_name, en_name, is_enabled, is_non_chinese_ui, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self._is_non_chinese_ui = is_non_chinese_ui
        self._original_text = en_name if is_non_chinese_ui else zh_name
        self.current_state = 'idle'  # 记录内部状态

        # 【新增】：标记当前任务是否为强制底座（登录）
        self.is_mandatory = (self.task_id == "task_login")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        self.checkbox = CheckBox(parent=self)

        # 【物理锁死初始化】：如果是强制任务，永远为True；普通任务读配置
        self.checkbox.setChecked(True if self.is_mandatory else is_enabled)

        # 【物理锁死交互】：强制任务永远禁用点击（变灰）
        if self.is_mandatory:
            self.checkbox.setEnabled(False)

        self.checkbox.setFixedWidth(28)
        self.checkbox.stateChanged.connect(
            lambda: self.checkbox_state_changed.emit(self.task_id, self.checkbox.isChecked())
        )

        self.label = BodyLabel(self._original_text, self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        left_layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left_layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


        self.solo_play_btns = FIF.SYNC
        self.btn = ToolButton(self)
        self.btn.setIcon(self.solo_play_btns)
        self.btn.setToolTip("单独执行" if not is_non_chinese_ui else "Run only")
        self.btn.setFixedSize(28, 28)

        btn_font = self.btn.font()
        btn_font.setPointSize(10)
        self.btn.setFont(btn_font)
        self.btn.clicked.connect(lambda: self.play_clicked.emit(self.task_id))

        self.btn_play_from_here = ToolButton(self)
        self.btn_play_from_here.setIcon(FIF.PLAY)
        self.btn_play_from_here.setToolTip("此处开始" if not is_non_chinese_ui else "Run from here")
        self.btn_play_from_here.setFixedSize(28, 28)
        self.btn_play_from_here.setFont(btn_font)
        self.btn_play_from_here.clicked.connect(lambda: self.play_from_here_clicked.emit(self.task_id))

        layout.addLayout(left_layout, 0)
        layout.addStretch(1)
        # 保持视觉位置不变：先加左边的 btn (倒三角)，再加右边的 btn_play_from_here (PLAY)
        layout.addWidget(self.btn, 0)
        layout.addWidget(self.btn_play_from_here, 0)
        # ============================================

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_task_state(self, state: str, is_enabled: bool = True):
        try:
            self.current_state = state
            font = self.label.font()
            font.setBold(False)
            display_text = self._original_text

            self.btn.setVisible(True)
            self.btn_play_from_here.setVisible(True)

            # 【物理锁死状态机】：确保强制任务无论如何刷新，都是打钩且禁用的
            if self.is_mandatory:
                self.checkbox.blockSignals(True)
                self.checkbox.setChecked(True)
                self.checkbox.setEnabled(False)
                self.checkbox.blockSignals(False)
            else:
                self.checkbox.setEnabled(True)

            self.btn.setIcon(self.solo_play_btns)

            colors = {
                'running_queue': "#FF8C00",
                'running_solo': "#FF8C00",
                'running_scheduled': "#FF8C00",
                'completed': "#107C10",
                'scheduled': "#0078D4",
                'queued': "#9370DB",
                'failed': "#D32F2F",
            }

            color = colors.get(state, "")

            if state == 'running_queue':
                self.btn.setIcon(getattr(FIF, "PAUSE", getattr(FIF, "CLOSE", FIF.PLAY)))
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)
                font.setBold(True)
                prefix = "▶️ " if self._is_non_chinese_ui else "▶️ [执行中] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'running_solo':
                self.btn.setIcon(getattr(FIF, "PAUSE", getattr(FIF, "CLOSE", FIF.PLAY)))
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)
                font.setBold(True)
                prefix = "🔁 " if self._is_non_chinese_ui else "🔁 [单独跑] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'running_scheduled':
                self.btn.setIcon(getattr(FIF, "PAUSE", getattr(FIF, "CLOSE", FIF.PLAY)))
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)
                font.setBold(True)
                prefix = "⏰ " if self._is_non_chinese_ui else "⏰ [执行中] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'completed':
                prefix = "✓ " if self._is_non_chinese_ui else "✓ [已完成] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'failed':
                prefix = "❌ " if self._is_non_chinese_ui else "❌ [未成功] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'scheduled':
                prefix = "📅 " if self._is_non_chinese_ui else "📅 [计划内] "
                display_text = f"{prefix}{self._original_text}"

            elif state == 'queued':
                self.btn.setVisible(False)
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)
                prefix = "⏳ " if self._is_non_chinese_ui else "⏳ [队列中] "
                display_text = f"{prefix}{self._original_text}"

            # 【核心修复】：闲置状态的颜色显式设定
            if state == 'idle':
                if not is_enabled and not self.is_mandatory:
                    color = "#888888" # 未勾选一律变灰
                else:
                    color = "white" if isDarkTheme() else "black"

            self.label.setText(display_text)
            self.label.setStyleSheet(f"color: {color};" if color else "")
            self.label.setFont(font)
            self.label.repaint()
        except Exception:
            pass

    def lock_ui_for_execution(self):
        """UI 软锁定：用于他人正在执行时。禁止勾选，隐藏所有按钮，保留文字色彩。"""
        self.checkbox.setEnabled(False)
        self.btn.setVisible(False)
        self.btn_play_from_here.setVisible(False)
        # 仅将原本是 idle 且没勾选的任务变灰，其他诸如“计划内”、“已完成”必须保留原色
        if self.current_state == 'idle' and not self.checkbox.isChecked():
            self.label.setStyleSheet("color: #888888;")

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.settings_clicked.emit(self.task_id)

class SharedSchedulingPanel(QWidget):
    config_changed = Signal(str, dict)
    toggle_all_cycles = Signal(bool)
    view_schedule_clicked = Signal()

    def __init__(self, is_non_chinese_ui=False, parent=None):
        super().__init__(parent)
        self.task_id = None
        self.is_non_chinese_ui = is_non_chinese_ui

        self.setMinimumHeight(200)
        self.setMaximumHeight(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setStyleSheet("SharedSchedulingPanel { border-top: 1px solid rgba(0,0,0,0.1); }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        checkbox_row = QHBoxLayout()
        enable_text = "Cycle" if is_non_chinese_ui else "启用计划"
        self.enable_checkbox = CheckBox(enable_text, self)
        font = self.enable_checkbox.font()
        font.setPointSize(10)
        self.enable_checkbox.setFont(font)

        checkbox_row.addWidget(self.enable_checkbox)

        self.btn_enable_all = PushButton("All On" if is_non_chinese_ui else "全部启用", self)
        self.btn_disable_all = PushButton("All Off" if is_non_chinese_ui else "全部关闭", self)
        self.btn_view_schedule = PushButton("Schedule" if is_non_chinese_ui else "日程表", self)

        self.btn_enable_all.setFixedHeight(28)
        self.btn_disable_all.setFixedHeight(28)
        self.btn_view_schedule.setFixedHeight(28)

        self.btn_enable_all.clicked.connect(lambda: self.toggle_all_cycles.emit(True))
        self.btn_disable_all.clicked.connect(lambda: self.toggle_all_cycles.emit(False))
        self.btn_view_schedule.clicked.connect(lambda: self.view_schedule_clicked.emit())

        checkbox_row.addSpacing(15)
        checkbox_row.addWidget(self.btn_enable_all)
        checkbox_row.addWidget(self.btn_disable_all)
        checkbox_row.addWidget(self.btn_view_schedule)
        checkbox_row.addStretch(1)

        main_layout.addLayout(checkbox_row)

        activation_row = QHBoxLayout()
        activation_row.setContentsMargins(0, 0, 0, 0)
        activation_row.setSpacing(6)

        activation_label_text = "Activation:" if is_non_chinese_ui else "生效起点："
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

        exec_title_layout = QHBoxLayout()
        exec_title_layout.setContentsMargins(0, 0, 0, 0)
        exec_title_layout.setSpacing(8)

        exec_title_text = "Execution Triggers" if is_non_chinese_ui else "执行节点："
        self.exec_title_label = StrongBodyLabel(exec_title_text, self)

        self.add_btn = ToolButton(FIF.ADD, self)
        self.add_btn.setToolTip("Add Trigger" if is_non_chinese_ui else "添加时间")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.clicked.connect(lambda: self._add_rule({}))

        exec_title_layout.addWidget(self.exec_title_label)
        exec_title_layout.addWidget(self.add_btn)
        exec_title_layout.addStretch(1)

        main_layout.addLayout(exec_title_layout)

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

        self.enable_checkbox.stateChanged.connect(self._emit_change)

    def _iter_activation_rule_widgets(self):
        for i in range(self.activation_layout.count() - 1):
            item = self.activation_layout.itemAt(i)
            widget = item.widget() if item is not None and hasattr(item, "widget") else None
            if widget is not None and isinstance(widget, ExecutionRuleWidget):
                yield widget

    def _add_activation_rule(self, data):
        w = ExecutionRuleWidget(self.is_non_chinese_ui, self)
        w.set_runs_visible(False)
        w.runs_edit.setText("1")
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
            item = self.rules_layout.itemAt(i)
            widget = item.widget() if item is not None and hasattr(item, "widget") else None
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
        self.enable_checkbox.setChecked(config_dict.get("use_periodic", False))
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
            activation_rules = [{"type": "daily", "time": "00:00", "max_runs": 1}]

        self._add_activation_rule(activation_rules[0])
        self._update_activation_delete_btns()

        while self.rules_layout.count() > 1:
            item = self.rules_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        rules = config_dict.get("execution_config", [{"type": "daily", "time": "00:00", "max_runs": 1}])
        if isinstance(rules, dict):
            rules = [rules]
        if not rules:
            rules = [{"type": "daily", "time": "00:00", "max_runs": 1}]

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


# ===== 页面基类以及各子页面必须在这里定义 =====

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

        self.TextEdit_import_codes = TextEdit(self)
        self.TextEdit_import_codes.setObjectName("TextEdit_import_codes")
        self.TextEdit_import_codes.setMinimumHeight(60)
        self.TextEdit_import_codes.setMaximumHeight(120)

        self.BodyLabel_collect_supplies = BodyLabel(self)
        self.BodyLabel_collect_supplies.setObjectName("BodyLabel_collect_supplies")
        self.BodyLabel_collect_supplies.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_collect_supplies.setWordWrap(True)

        self.main_layout.addWidget(self.CheckBox_mail)
        self.main_layout.addWidget(self.CheckBox_fish_bait)
        self.main_layout.addWidget(self.CheckBox_dormitory)
        self.main_layout.addLayout(redeem_line)
        self.main_layout.addWidget(self.TextEdit_import_codes)
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


class OperationPage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_operation", parent=parent)

        self.BodyLabel_7 = BodyLabel(self)
        self.BodyLabel_7.setObjectName("BodyLabel_7")
        self.SpinBox_action_times = SpinBox(self)
        self.SpinBox_action_times.setObjectName("SpinBox_action_times")
        self.SpinBox_action_times.setRange(1, 999)

        self.BodyLabel_22 = BodyLabel(self)
        self.BodyLabel_22.setObjectName("BodyLabel_22")
        self.ComboBox_run = ComboBox(self)
        self.ComboBox_run.setObjectName("ComboBox_run")

        self.BodyLabel_tip_action = BodyLabel(self)
        self.BodyLabel_tip_action.setObjectName("BodyLabel_tip_action")
        self.BodyLabel_tip_action.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tip_action.setWordWrap(True)

        self.main_layout.addLayout(self._row(self.BodyLabel_7, self.SpinBox_action_times))
        self.main_layout.addLayout(self._row(self.BodyLabel_22, self.ComboBox_run))
        self.main_layout.addWidget(self.BodyLabel_tip_action)

        self.finalize()

    @staticmethod
    def _row(label, edit):
        line = QHBoxLayout()
        line.addWidget(label, 1)
        line.addWidget(edit, 2)
        return line


class WeaponUpgradePage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_weapon", parent=parent)

        self.BodyLabel_weapon_tip = BodyLabel(self)
        self.BodyLabel_weapon_tip.setObjectName("BodyLabel_weapon_tip")
        self.BodyLabel_weapon_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_weapon_tip.setWordWrap(True)
        self.main_layout.addWidget(self.BodyLabel_weapon_tip)
        self.finalize()


class ShardExchangePage(BaseDailyPage):
    def __init__(self, parent=None):
        super().__init__("page_shard_exchange", parent=parent)

        self.CheckBox_receive_shards = CheckBox(self)
        self.CheckBox_receive_shards.setObjectName("enable_receive_shards")

        self.CheckBox_gift_shards = CheckBox(self)
        self.CheckBox_gift_shards.setObjectName("enable_gift_shards")

        self.CheckBox_recycle_shards = CheckBox(self)
        self.CheckBox_recycle_shards.setObjectName("enable_recycle_shards")

        self.BodyLabel_shard_tip = BodyLabel(self)
        self.BodyLabel_shard_tip.setObjectName("BodyLabel_shard_tip")
        self.BodyLabel_shard_tip.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_shard_tip.setWordWrap(True)

        self.main_layout.addWidget(self.CheckBox_receive_shards)
        self.main_layout.addWidget(self.CheckBox_gift_shards)
        self.main_layout.addWidget(self.CheckBox_recycle_shards)
        self.main_layout.addWidget(self.BodyLabel_shard_tip)
        self.finalize()


class DailyView(ScrollArea):

    def __init__(self, parent=None, is_non_chinese_ui=False):
        super().__init__(parent)
        self.setObjectName("daily")
        self.is_non_chinese_ui = is_non_chinese_ui

        self.setWidgetResizable(True)
        self.setStyleSheet(
            "QScrollArea#daily { border: none; background: transparent; }")

        self.content_widget = QWidget()
        self.content_widget.setObjectName("daily_content_widget")
        self.content_widget.setStyleSheet("background: transparent;")

        self.gridLayout_2 = QGridLayout(self.content_widget)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.gridLayout_2.setContentsMargins(10, 10, 10, 10)
        self.gridLayout_2.setSpacing(12)

        self._build_option_card()
        self._build_action_card()
        self._build_setting_card()
        self._build_log_card()
        self._build_tips_card()

        self.gridLayout_2.setRowStretch(0, 1)
        self.gridLayout_2.setRowStretch(1, 0)

        self.gridLayout_2.setColumnStretch(0, 2)
        self.gridLayout_2.setColumnStretch(1, 3)
        self.gridLayout_2.setColumnStretch(2, 2)

        self.setWidget(self.content_widget)

        self._apply_ui_settings()

    def _build_option_card(self):
        self.SimpleCardWidget_option = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget_option.setObjectName("SimpleCardWidget_option")
        self.SimpleCardWidget_option.setMinimumWidth(200)
        # self.SimpleCardWidget_option.setMaximumWidth(350)
        self.SimpleCardWidget_option.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self.SimpleCardWidget_option)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)

        self.taskListWidget = TaskListView(self.SimpleCardWidget_option)
        self.taskListWidget.setObjectName("taskListWidget")
        layout.addWidget(self.taskListWidget, 1)

        btn_row = QHBoxLayout()
        hint_text = "Drag to reorder" if self.is_non_chinese_ui else "拖动调整顺序"
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
        self.SimpleCardWidget_3 = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget_3.setObjectName("SimpleCardWidget_3")
        self.SimpleCardWidget_3.setMinimumHeight(190)
        self.SimpleCardWidget_3.setMaximumHeight(280)

        layout = QVBoxLayout(self.SimpleCardWidget_3)

        self.BodyLabel_run_mode = BodyLabel(self.SimpleCardWidget_3)
        self.ComboBox_run_mode = ComboBox(self.SimpleCardWidget_3)
        self.ComboBox_run_mode.setObjectName("ComboBox_run_mode")

        self.BodyLabel_end_action = BodyLabel(self.SimpleCardWidget_3)
        self.ComboBox_end_action = ComboBox(self.SimpleCardWidget_3)
        self.ComboBox_end_action.setObjectName("ComboBox_end_action")

        self.PushButton_start = PushButton(self.SimpleCardWidget_3)
        self.PushButton_start.setObjectName("PushButton_start")
        self.PushButton_start.setMinimumSize(QSize(0, 60))

        layout.addStretch(1)
        layout.addWidget(self.BodyLabel_run_mode)
        layout.addWidget(self.ComboBox_run_mode)
        layout.addSpacing(6)
        layout.addWidget(self.BodyLabel_end_action)
        layout.addWidget(self.ComboBox_end_action)
        layout.addStretch(1)
        layout.addWidget(self.PushButton_start)
        layout.addStretch(1)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_3, 1, 0, 1, 1)

    def _build_setting_card(self):
        self.SimpleCardWidget_2 = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget_2.setObjectName("SimpleCardWidget_2")
        self.SimpleCardWidget_2.setMinimumWidth(300)
        # self.SimpleCardWidget_2.setMaximumWidth(700)
        self.SimpleCardWidget_2.setSizePolicy(QSizePolicy.Policy.Expanding,
                                              QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self.SimpleCardWidget_2)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(4)

        self.TitleLabel_setting = TitleLabel(self.SimpleCardWidget_2)
        self.TitleLabel_setting.setObjectName("TitleLabel_setting")

        self.PopUpAniStackedWidget = PopUpAniStackedWidget(
            self.SimpleCardWidget_2)
        self.PopUpAniStackedWidget.setObjectName("PopUpAniStackedWidget")

        self.page_enter = EnterGamePage(self.PopUpAniStackedWidget)
        self.page_collect = CollectSuppliesPage(self.PopUpAniStackedWidget)
        self.page_shop = ShopPage(self.PopUpAniStackedWidget)
        self.page_use_power = UsePowerPage(self.PopUpAniStackedWidget)
        self.page_person = PersonPage(self.PopUpAniStackedWidget)
        self.page_chasm = ChasmPage(self.PopUpAniStackedWidget)
        self.page_reward = RewardPage(self.PopUpAniStackedWidget)
        self.page_operation = OperationPage(self.PopUpAniStackedWidget)
        self.page_weapon = WeaponUpgradePage(self.PopUpAniStackedWidget)
        self.page_shard_exchange = ShardExchangePage(
            self.PopUpAniStackedWidget)

        self.PopUpAniStackedWidget.addWidget(self.page_enter)
        self.PopUpAniStackedWidget.addWidget(self.page_collect)
        self.PopUpAniStackedWidget.addWidget(self.page_shop)
        self.PopUpAniStackedWidget.addWidget(self.page_use_power)
        self.PopUpAniStackedWidget.addWidget(self.page_person)
        self.PopUpAniStackedWidget.addWidget(self.page_chasm)
        self.PopUpAniStackedWidget.addWidget(self.page_reward)
        self.PopUpAniStackedWidget.addWidget(self.page_operation)
        self.PopUpAniStackedWidget.addWidget(self.page_weapon)
        self.PopUpAniStackedWidget.addWidget(self.page_shard_exchange)

        layout.addWidget(self.TitleLabel_setting)
        layout.addWidget(self.PopUpAniStackedWidget, 1)

        self.shared_scheduling_panel = SharedSchedulingPanel(
            self.is_non_chinese_ui, self.SimpleCardWidget_2)
        self.shared_scheduling_panel.setObjectName("shared_scheduling_panel")
        layout.addWidget(self.shared_scheduling_panel, 0)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_2, 0, 1, 2, 1)
        self._alias_page_widgets()

    def _alias_page_widgets(self):
        # EnterGamePage
        self.StrongBodyLabel_4 = self.page_enter.StrongBodyLabel_4
        self.PrimaryPushButton_path_tutorial = self.page_enter.PrimaryPushButton_path_tutorial
        self.CheckBox_open_game_directly = self.page_enter.CheckBox_open_game_directly
        self.LineEdit_game_directory = self.page_enter.LineEdit_game_directory
        self.PushButton_select_directory = self.page_enter.PushButton_select_directory
        self.BodyLabel_enter_tip = self.page_enter.BodyLabel_enter_tip

        # CollectSuppliesPage
        self.CheckBox_mail = self.page_collect.CheckBox_mail
        self.CheckBox_redeem_code = self.page_collect.CheckBox_redeem_code
        self.CheckBox_dormitory = self.page_collect.CheckBox_dormitory
        self.CheckBox_fish_bait = self.page_collect.CheckBox_fish_bait
        self.PushButton_reset_codes = self.page_collect.PushButton_reset_codes
        self.PrimaryPushButton_import_codes = self.page_collect.PrimaryPushButton_import_codes
        self.TextEdit_import_codes = self.page_collect.TextEdit_import_codes
        self.BodyLabel_collect_supplies = self.page_collect.BodyLabel_collect_supplies

        # ShopPage
        self.ScrollArea = self.page_shop.ScrollArea
        self.scrollAreaWidgetContents = self.page_shop.scrollAreaWidgetContents
        self.gridLayout = self.page_shop.gridLayout
        self.StrongBodyLabel = self.page_shop.StrongBodyLabel
        self.widget = self.page_shop.widget
        self.widget_2 = self.page_shop.widget_2
        for i in range(3, 16):
            name = f"CheckBox_buy_{i}"
            setattr(self, name, getattr(self.page_shop, name))

        # UsePowerPage
        self.ComboBox_power_usage = self.page_use_power.ComboBox_power_usage
        self.StrongBodyLabel_2 = self.page_use_power.StrongBodyLabel_2
        self.CheckBox_is_use_power = self.page_use_power.CheckBox_is_use_power
        self.ComboBox_power_day = self.page_use_power.ComboBox_power_day
        self.BodyLabel_6 = self.page_use_power.BodyLabel_6

        # PersonPage
        self.BodyLabel_8 = self.page_person.BodyLabel_8
        self.LineEdit_c4 = self.page_person.LineEdit_c4
        self.BodyLabel_person_tip = self.page_person.BodyLabel_person_tip
        self.BodyLabel_5 = self.page_person.BodyLabel_5
        self.LineEdit_c3 = self.page_person.LineEdit_c3
        self.CheckBox_is_use_chip = self.page_person.CheckBox_is_use_chip
        self.BodyLabel_3 = self.page_person.BodyLabel_3
        self.LineEdit_c1 = self.page_person.LineEdit_c1
        self.StrongBodyLabel_3 = self.page_person.StrongBodyLabel_3
        self.BodyLabel_4 = self.page_person.BodyLabel_4
        self.LineEdit_c2 = self.page_person.LineEdit_c2

        # ChasmPage & RewardPage
        self.BodyLabel_chasm_tip = self.page_chasm.BodyLabel_chasm_tip
        self.BodyLabel_reward_tip = self.page_reward.BodyLabel_reward_tip

        # OperationPage
        self.BodyLabel_22 = self.page_operation.BodyLabel_22
        self.ComboBox_run = self.page_operation.ComboBox_run
        self.BodyLabel_7 = self.page_operation.BodyLabel_7
        self.SpinBox_action_times = self.page_operation.SpinBox_action_times
        self.BodyLabel_tip_action = self.page_operation.BodyLabel_tip_action

        # WeaponUpgradePage
        self.BodyLabel_weapon_tip = self.page_weapon.BodyLabel_weapon_tip

        # ShardExchangePage
        self.CheckBox_receive_shards = self.page_shard_exchange.CheckBox_receive_shards
        self.CheckBox_gift_shards = self.page_shard_exchange.CheckBox_gift_shards
        self.CheckBox_recycle_shards = self.page_shard_exchange.CheckBox_recycle_shards
        self.BodyLabel_shard_tip = self.page_shard_exchange.BodyLabel_shard_tip

    def _build_log_card(self):
        self.SimpleCardWidget = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget.setObjectName("SimpleCardWidget")
        self.SimpleCardWidget.setMinimumWidth(246)
        # self.SimpleCardWidget.setMaximumWidth(450)
        self.SimpleCardWidget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                            QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self.SimpleCardWidget)
        layout.setSpacing(4)

        self.TitleLabel = TitleLabel(self.SimpleCardWidget)
        self.TitleLabel.setObjectName("TitleLabel")
        self.textBrowser_log = QTextBrowser(self.SimpleCardWidget)
        self.textBrowser_log.setObjectName("textBrowser_log")
        self.textBrowser_log.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        layout.addWidget(self.TitleLabel)
        layout.addWidget(self.textBrowser_log)

        self.gridLayout_2.addWidget(self.SimpleCardWidget, 0, 2, 1, 1)

    def _build_tips_card(self):
        self.SimpleCardWidget_tips = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget_tips.setObjectName("SimpleCardWidget_tips")
        self.SimpleCardWidget_tips.setMinimumWidth(237)
        # self.SimpleCardWidget_tips.setMaximumWidth(450)
        self.SimpleCardWidget_tips.setMinimumHeight(150)
        self.SimpleCardWidget_tips.setMaximumHeight(250)
        self.SimpleCardWidget_tips.setSizePolicy(QSizePolicy.Policy.Expanding,
                                                 QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self.SimpleCardWidget_tips)
        layout.setSpacing(3)

        self.TitleLabel_3 = TitleLabel(self.SimpleCardWidget_tips)
        self.TitleLabel_3.setObjectName("TitleLabel_3")
        self.ScrollArea_tips = ScrollArea(self.SimpleCardWidget_tips)
        self.ScrollArea_tips.setObjectName("ScrollArea_tips")
        self.ScrollArea_tips.setWidgetResizable(True)

        self.scrollAreaWidgetContents_tips = QWidget()
        self.scrollAreaWidgetContents_tips.setObjectName(
            "scrollAreaWidgetContents_tips")
        self.gridLayout_tips = QGridLayout(self.scrollAreaWidgetContents_tips)
        self.gridLayout_tips.setObjectName("gridLayout_tips")
        self.gridLayout_tips.setContentsMargins(0, 0, 0, 0)

        self.ScrollArea_tips.setWidget(self.scrollAreaWidgetContents_tips)

        layout.addWidget(self.TitleLabel_3)
        layout.addWidget(self.ScrollArea_tips)

        self.gridLayout_2.addWidget(self.SimpleCardWidget_tips, 1, 2, 1, 1)

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self.is_non_chinese_ui else zh_text

    def _apply_ui_settings(self):
        self.ComboBox_run_mode.addItems([
            self._ui_text('挂机等待', 'Loop & Wait'),
            self._ui_text('关闭程序', 'Exit Program'),
            self._ui_text('关闭电脑', 'Shutdown'),
        ])

        self.ComboBox_end_action.addItems([
            self._ui_text('无动作', 'Do Nothing'),
            self._ui_text('退出游戏', 'Exit Game'),
            self._ui_text('退出代理', 'Exit Assistant'),
            self._ui_text('退出游戏和代理', 'Exit Game and Assistant'),
        ])

        self.BodyLabel_run_mode.setText(
            self._ui_text("执行结束后，安卡小助手:", "After Execution, Acacia Action:"))
        self.BodyLabel_end_action.setText(
            self._ui_text("执行结束后，尘白禁区将:", "After Execution, Game Action:"))
        self.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))

        self.ComboBox_power_day.addItems(['1', '2', '3', '4', '5', '6'])
        self.ComboBox_power_usage.addItems([
            self._ui_text('活动材料本', 'Event Stages'),
            self._ui_text('刷常规后勤', 'Operation Logistics')
        ])
        self.ComboBox_run.addItems(["Toggle Sprint", "Hold Sprint"] if self.
                                   is_non_chinese_ui else ["切换疾跑", "按住疾跑"])

        for line_edit in [
                self.LineEdit_c1, self.LineEdit_c2, self.LineEdit_c3,
                self.LineEdit_c4
        ]:
            line_edit.setPlaceholderText(self._ui_text("未输入", "Not set"))

        self.PushButton_start.setToolTip(
            self._ui_text("快捷键：F8", "Shortcut: F8"))

        self.BodyLabel_enter_tip.setText(
            "### Tips\n* Select your server in Settings\n* Enable \"Auto open game\" and select the correct game path by the tutorial above\n* Click \"Start\" to launch and run automatically"
            if self.is_non_chinese_ui else
            "### 提示\n* 去设置里选择你的区服\n* 建议勾选“自动打开游戏”，勾选后根据上方教程选择好对应的路径\n* 点击“开始”按钮会自动打开游戏"
        )
        self.BodyLabel_person_tip.setText(
            "### Tips\n* Enter codename instead of full name, e.g. use \"朝翼\" (Dawnwing) for \"凯茜娅-朝翼\" (Katya-Dawnwing)"
            if self.
            is_non_chinese_ui else "### 提示\n* 输入代号而非全名，比如想要刷“凯茜娅-朝翼”，就输入“朝翼”")
        self.BodyLabel_collect_supplies.setText(
            "### Tips\n* Default: Always claim Supply Station stamina and friend stamina \n* Enable \"Redeem Code\" to fetch and redeem online codes automatically\n* Online codes are maintained by developers and may not always be updated in time\n* You can import a txt file for batch redeem (one code per line)"
            if self.is_non_chinese_ui else
            "### 提示 \n* 默认必领供应站体力和好友体力\n* 勾选“领取兑换码”会自动拉取在线兑换码进行兑换\n* 在线兑换码由开发者维护，更新不一定及时\n* 导入txt文本文件可以批量使用用户兑换码，txt需要一行一个兑换码"
        )
        self.BodyLabel_chasm_tip.setText(
            "### Tips\n* Mental Simulation Realm opens every Tuesday at 10:00"
            if self.is_non_chinese_ui else "### 提示\n* 拟境每周2的10:00开启")
        self.BodyLabel_reward_tip.setText(
            "### Tips\n* Claim monthly card and daily rewards" if self.
            is_non_chinese_ui else "### 提示\n* 领取大月卡和日常奖励")
        self.BodyLabel_weapon_tip.setText(
            "### Tips\n* Automatically identifies and consumes upgrade materials\n* Stops when weapon reaches max level"
            if self.is_non_chinese_ui else
            "### 提示\n* 自动从背包选择第一把武器进行强化\n* 自动识别并消耗升级材料，直到武器等级提升或满级")
        self.BodyLabel_shard_tip.setText(
            "### Tips\n* Auto receive, gift, and recycle puzzle shards\n* Retains at least 15 of each shard when recycling"
            if self.is_non_chinese_ui else
            "### 提示\n* 自动进行基地信源碎片的接收、赠送和回收\n* 回收时每种碎片默认至少保留15个")

        self.TitleLabel.setText(self._ui_text("日志", "Log"))
        self.PushButton_select_all.setText(self._ui_text("全选", "All"))
        self.PushButton_no_select.setText(self._ui_text("清空", "Clear"))
        self.hint_label.setText(self._ui_text("拖动调整顺序", "Drag to sort"))
        self.PrimaryPushButton_path_tutorial.setText(
            self._ui_text("查看教程", "Tutorial"))
        self.StrongBodyLabel_4.setText(
            self._ui_text("启动器中查看游戏路径", "Find game path in launcher"))
        self.CheckBox_open_game_directly.setText(
            self._ui_text("自动打开游戏", "Auto open game"))
        self.PushButton_select_directory.setText(self._ui_text("选择", "Browse"))
        self.CheckBox_mail.setText(self._ui_text("领取邮件", "Claim Mail"))
        self.CheckBox_fish_bait.setText(self._ui_text("领取鱼饵", "Claim Bait"))
        self.CheckBox_dormitory.setText(self._ui_text("宿舍碎片", "Dorm Shards"))
        self.CheckBox_redeem_code.setText(
            self._ui_text("领取兑换码", "Redeem Codes"))
        self.CheckBox_receive_shards.setText(
            self._ui_text("一键接收", "Auto Receive"))
        self.CheckBox_gift_shards.setText(self._ui_text("一键赠送", "Auto Gift"))
        self.CheckBox_recycle_shards.setText(
            self._ui_text("智能回收", "Smart Recycle"))
        self.PrimaryPushButton_import_codes.setText(
            self._ui_text("导入", "Import"))
        self.PushButton_reset_codes.setText(self._ui_text("重置", "Reset"))
        self.StrongBodyLabel.setText(
            self._ui_text("选择要购买的商品", "Select items to buy"))
        self.StrongBodyLabel_2.setText(
            self._ui_text("选择体力使用方式", "Stamina usage mode"))
        self.CheckBox_is_use_power.setText(
            self._ui_text("自动使用期限", "Auto use expiring"))
        self.BodyLabel_6.setText(self._ui_text("天内的体力药", "day potion"))
        self.StrongBodyLabel_3.setText(
            self._ui_text("选择需要刷碎片的角色", "Select characters for shards"))
        self.BodyLabel_3.setText(self._ui_text("角色1：", "Character 1:"))
        self.BodyLabel_4.setText(self._ui_text("角色2：", "Character 2:"))
        self.BodyLabel_5.setText(self._ui_text("角色3：", "Character 3:"))
        self.BodyLabel_8.setText(self._ui_text("角色4：", "Character 4:"))
        self.CheckBox_is_use_chip.setText(
            self._ui_text("记忆嵌片不足时自动使用2片", "Auto use 2 chips when not enough"))
        self.TitleLabel_3.setText(self._ui_text("日程提醒", "Schedule"))
        self.BodyLabel_22.setText(self._ui_text("疾跑方式", "Sprint mode"))
        self.BodyLabel_7.setText(self._ui_text("刷取次数", "Run count"))
        self.BodyLabel_tip_action.setText(
            "### Tips\n* Auto-run operation \n* Repeats the first training stage for specified times with no stamina cost\n* Useful for weekly pass mission count"
            if self.is_non_chinese_ui else
            "### 提示\n* 重复刷指定次数无需体力的实战训练第一关\n* 用于完成凭证20次常规行动周常任务")

        shop_items = [
            ("CheckBox_buy_3", "通用强化套件", "Universal Enhancement Kit"),
            ("CheckBox_buy_4", "优选强化套件", "Premium Enhancement Kit"),
            ("CheckBox_buy_5", "精致强化套件", "Exquisite Enhancement Kit"),
            ("CheckBox_buy_6", "新手战斗记录", "Beginner Battle Record"),
            ("CheckBox_buy_7", "普通战斗记录", "Standard Battle Record"),
            ("CheckBox_buy_8", "优秀战斗记录", "Advanced Battle Record"),
            ("CheckBox_buy_9", "初级职级认证", "Junior Rank Certification"),
            ("CheckBox_buy_10", "中级职级认证", "Intermediate Rank Certification"),
            ("CheckBox_buy_11", "高级职级认证", "Senior Rank Certification"),
            ("CheckBox_buy_12", "合成颗粒", "Synthetic Particles"),
            ("CheckBox_buy_13", "芳烃塑料", "Hydrocarbon Plastic"),
            ("CheckBox_buy_14", "单极纤维", "Monopolar Fibers"),
            ("CheckBox_buy_15", "光纤轴突", "Fiber Axon")
        ]
        for attr, zh, en in shop_items:
            getattr(self, attr).setText(self._ui_text(zh, en))
