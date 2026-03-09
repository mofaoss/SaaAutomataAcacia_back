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
    EditableComboBox,
    isDarkTheme,
)
from app.framework.application.modules import HostContext, get_periodic_module_specs
from app.features.scheduling.periodic_ui_texts import apply_periodic_module_texts


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

        # 彻底剥夺强制首位任务的拖拽能力
        if getattr(task_item_widget, "is_force_first", False):
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
    # 【新增】复制该条规则的信号，传递当前规则的字典数据
    copy_rule_clicked = Signal(dict)
    withdraw_rule_clicked = Signal(dict)

    def __init__(self, is_non_chinese_ui=False, parent=None):
        super().__init__(parent)
        self.is_non_chinese_ui = is_non_chinese_ui

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

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
        self.month_combo.setFixedWidth(68)

        self.time_edit = LineEdit(self)
        self.time_edit.setText("00:00")
        self.time_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_edit.setFixedWidth(58)

        self.runs_edit = LineEdit(self)
        self.runs_edit.setValidator(QIntValidator(1, 99, self))
        self.runs_edit.setText("1")
        self.runs_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.runs_edit.setMinimumWidth(35)
        self.runs_edit.setMaximumWidth(55)

        self.delete_btn = ToolButton(self)
        self.delete_btn.setIcon(FIF.DELETE)
        self.delete_btn.setFixedSize(26, 26)
        self.delete_btn.setIconSize(QSize(14, 14))

        # 【新增】单条规则的复制按钮
        self.copy_btn = ToolButton(self)
        self.copy_btn.setIcon(FIF.COPY)
        self.copy_btn.setToolTip("Copy to checked tasks" if is_non_chinese_ui else "将此时间复制给已勾选任务")
        self.copy_btn.setFixedSize(26, 26)
        self.copy_btn.setIconSize(QSize(14, 14))

        # 【新增】撤回按钮
        self.withdraw_btn = ToolButton(self)
        self.withdraw_btn.setIcon(FIF.CANCEL)
        self.withdraw_btn.setToolTip("Remove from checked tasks" if is_non_chinese_ui else "从已勾选任务中撤回此时间")
        self.withdraw_btn.setFixedSize(26, 26)
        self.withdraw_btn.setIconSize(QSize(14, 14))

        for w in [self.freq_combo, self.week_combo, self.month_combo, self.time_edit, self.runs_edit, self.delete_btn, self.copy_btn, self.withdraw_btn]:
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
        layout.addWidget(self.copy_btn) # 【新增】添加到布局
        layout.addWidget(self.withdraw_btn)
        layout.addStretch(1)

        self.freq_combo.currentIndexChanged.connect(self._update_visibility)
        self.delete_btn.clicked.connect(lambda: self.deleted.emit(self))
        # 【新增】绑定复制按钮点击事件
        self.copy_btn.clicked.connect(lambda: self.copy_rule_clicked.emit(self.get_data()))
        self.withdraw_btn.clicked.connect(lambda: self.withdraw_rule_clicked.emit(self.get_data()))

        for w in [self.freq_combo, self.week_combo, self.month_combo]:
            w.currentIndexChanged.connect(self.changed)

        self.runs_edit.textChanged.connect(self.changed)
        self.time_edit.textChanged.connect(self.changed)

        self._update_visibility()

    def set_runs_visible(self, visible: bool):
        self.label_after_time.setVisible(visible)
        self.runs_edit.setVisible(visible)
        self.label_times.setVisible(visible)
        # 【优化】如果隐藏了执行次数（比如生效起点），通常也不需要复制功能，一并隐藏
        self.copy_btn.setVisible(visible)
        self.withdraw_btn.setVisible(visible)

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

    def __init__(
        self,
        task_id,
        zh_name,
        en_name,
        is_enabled,
        is_non_chinese_ui,
        parent=None,
        *,
        is_mandatory: bool = False,
        is_force_first: bool = False,
    ):
        super().__init__(parent)
        self.task_id = task_id
        self._is_non_chinese_ui = is_non_chinese_ui
        self._original_text = en_name if is_non_chinese_ui else zh_name
        self.current_state = 'idle'  # 记录内部状态
        self.is_scheduled = False    # 独立记录是否启用了计划

        # 标记当前任务是否为强制底座（由注册中心定义）
        self.is_mandatory = bool(is_mandatory)
        self.is_force_first = bool(is_force_first)

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
        self.btn.setToolTip("单独重跑" if not is_non_chinese_ui else "Run only")
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

            base_text = f"📅 {self._original_text}" if self.is_scheduled else self._original_text

            self.btn.setVisible(True)
            self.btn_play_from_here.setVisible(True)

            if self.is_mandatory:
                self.checkbox.blockSignals(True)
                self.checkbox.setChecked(True)
                self.checkbox.setEnabled(False)
                self.checkbox.blockSignals(False)
            else:
                self.checkbox.setEnabled(True)

            self.btn.setIcon(self.solo_play_btns)
            self.btn.setToolTip("单独重跑" if not self._is_non_chinese_ui else "Run only")

            colors = {
                'running_queue': "#FF8C00",
                'running_solo': "#FF8C00",
                'running_scheduled': "#FF8C00",
                'completed': "#107C10",
                'queued': "#9370DB",
                'failed': "#D32F2F",
            }
            color = colors.get(state, "")

            suffix = self._get_state_suffix(state)

            # 只保留按钮和字体加粗的控制逻辑
            if state in ['running_queue', 'running_solo', 'running_scheduled']:
                self.btn.setIcon(getattr(FIF, "PAUSE", getattr(FIF, "CLOSE", FIF.PLAY)))
                self.btn.setToolTip("停止执行" if not self._is_non_chinese_ui else "Stop")
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)
                font.setBold(True)
            elif state == 'queued':
                self.btn.setVisible(False)
                self.btn_play_from_here.setVisible(False)
                if not self.is_mandatory: self.checkbox.setEnabled(False)

            # 闲置状态的颜色显式设定
            if state == 'idle':
                if not is_enabled and not self.is_mandatory:
                    color = "#888888" # 未勾选一律变灰
                else:
                    color = "white" if isDarkTheme() else "black"

            display_text = f"{base_text}{suffix}"
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

    def update_schedule_status(self, is_scheduled: bool):
        """在任务执行期间无感刷新计划图标📅，绝不触碰任何锁和按钮状态"""
        self.is_scheduled = is_scheduled

        base_text = f"📅 {self._original_text}" if self.is_scheduled else self._original_text

        suffix = self._get_state_suffix(self.current_state)

        display_text = f"{base_text}{suffix}"
        self.label.setText(display_text)
        self.label.repaint()

    def _get_state_suffix(self, state: str) -> str:
        """获取任务状态对应的文本后缀"""
        suffixes = {
            'running_queue': (" ▶️", "[执行]▶️"),
            'running_solo': (" 🔁", "[单跑]🔁"),
            'running_scheduled': (" ⏰", "[到点]⏰"),
            'completed': (" ✅", "[完成]✅"),
            'failed': (" ❌", "[失败]❌"),
            'queued': (" ⏳", "[队列]⏳")
        }

        if state in suffixes:
            en_suffix, zh_suffix = suffixes[state]
            return en_suffix if self._is_non_chinese_ui else zh_suffix

        return ""

class SharedSchedulingPanel(QWidget):
    config_changed = Signal(str, dict)
    toggle_all_cycles = Signal(bool)
    view_schedule_clicked = Signal()
    # 传递单条规则字典的信号
    copy_single_rule_clicked = Signal(dict)
    withdraw_single_rule_clicked = Signal(dict)

    def __init__(self, is_non_chinese_ui=False, parent=None):
        super().__init__(parent)
        self.task_id = None
        self.is_non_chinese_ui = is_non_chinese_ui
        self._is_loading = False

        self.setMinimumHeight(200)
        self.setMaximumHeight(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.setStyleSheet("SharedSchedulingPanel { border-top: 1px solid rgba(0,0,0,0.1); }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. 顶部：全局控制按钮行
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

        # 2. 中间：生效起点设置行
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

        # 3. 执行节点标题行
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

        # 4. 底部：执行节点滚动区域
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
        w.set_runs_visible(False) # 隐藏次数和复制按钮
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
        # 将子控件的复制信号透传给 Panel，Panel再通过 copy_single_rule_clicked 往外抛
        w.copy_rule_clicked.connect(lambda rule_data: self.copy_single_rule_clicked.emit(rule_data))
        w.withdraw_rule_clicked.connect(lambda rule_data: self.withdraw_single_rule_clicked.emit(rule_data))

        if data:
            w.set_data(data)

        self.rules_layout.insertWidget(self.rules_layout.count() - 1, w)
        self._update_delete_btns()
        self._emit_change()

    def _remove_rule(self, w):
        # 【修复】：移除数量小于等于1时拒绝删除的限制，允许彻底清空
        self.rules_layout.removeWidget(w)
        w.deleteLater()
        self._update_delete_btns()
        self._emit_change()

    def _update_delete_btns(self):
        rules = list(self._iter_rule_widgets())
        # 【修复】：不论剩下几条规则，都允许显示删除按钮
        for w in rules:
            w.delete_btn.setVisible(True)

    def load_task(self, task_id, config_dict):
        self._is_loading = True
        try:
            self.task_id = task_id
            self.enable_checkbox.blockSignals(True)
            self.enable_checkbox.setChecked(config_dict.get("use_periodic", False))
            self.enable_checkbox.blockSignals(False)

            # 清空现有的生效起点规则 (保留末尾的Stretch)
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

            # 清空现有的执行节点规则 (保留末尾的Stretch)
            while self.rules_layout.count() > 1:
                item = self.rules_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

            # 【修改点】：移除了执行节点原来强制读不到就兜底生成一个 00:00 的行为
            rules = config_dict.get("execution_config", [])
            if isinstance(rules, dict):
                rules = [rules]

            for rule in rules:
                self._add_rule(rule)

            self._update_delete_btns()
        finally:
            self._is_loading = False

    def _emit_change(self):
        if not self.task_id or self._is_loading:
            return

        activation_rules = [w.get_data() for w in self._iter_activation_rule_widgets()]
        rules = [w.get_data() for w in self._iter_rule_widgets()]

        new_cfg = {
            "use_periodic": self.enable_checkbox.isChecked(),
            "activation_config": activation_rules,
            "execution_config": rules,
        }
        self.config_changed.emit(self.task_id, new_cfg)


class PeriodicTasksView(ScrollArea):

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
        self._build_preset_card()
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

    def _build_preset_card(self):
        self.SimpleCardWidget_3 = SimpleCardWidget(self.content_widget)
        self.SimpleCardWidget_3.setObjectName("SimpleCardWidget_3")
        self.SimpleCardWidget_3.setMinimumHeight(190)
        self.SimpleCardWidget_3.setMaximumHeight(280)

        layout = QVBoxLayout(self.SimpleCardWidget_3)

        self.BodyLabel_preset = BodyLabel(self.SimpleCardWidget_3)

        preset_row = QHBoxLayout()
        self.ComboBox_presets = EditableComboBox(self.SimpleCardWidget_3)
        self.ComboBox_presets.setObjectName("ComboBox_presets")
        self.PushButton_add_preset = ToolButton(FIF.ADD, self.SimpleCardWidget_3)
        self.PushButton_save_preset = ToolButton(FIF.SAVE, self.SimpleCardWidget_3)
        self.PushButton_delete_preset = ToolButton(FIF.DELETE, self.SimpleCardWidget_3)

        preset_row.addWidget(self.ComboBox_presets, 1)
        preset_row.addWidget(self.PushButton_add_preset)
        preset_row.addWidget(self.PushButton_save_preset)
        preset_row.addWidget(self.PushButton_delete_preset)

        self.PushButton_start = PushButton(self.SimpleCardWidget_3)
        self.PushButton_start.setObjectName("PushButton_start")
        self.PushButton_start.setMinimumSize(QSize(0, 60))

        layout.addStretch(1)
        layout.addWidget(self.BodyLabel_preset)
        layout.addLayout(preset_row)
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
        self.periodic_module_specs = get_periodic_module_specs()
        self.periodic_pages_by_task_id = {}
        for spec in self.periodic_module_specs:
            page = spec.ui_factory(self.PopUpAniStackedWidget, HostContext.PERIODIC)
            if hasattr(page, "bind_host_context"):
                page.bind_host_context(HostContext.PERIODIC)
            self.periodic_pages_by_task_id[spec.id] = page
            bindings = spec.ui_bindings
            if bindings is not None and bindings.page_attr:
                setattr(self, bindings.page_attr, page)
            self.PopUpAniStackedWidget.addWidget(page)

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

        # CloseGamePage
        self.CheckBox_close_game = self.page_close_game.CheckBox_close_game
        self.CheckBox_close_proxy = self.page_close_game.CheckBox_close_proxy
        self.CheckBox_shutdown = self.page_close_game.CheckBox_shutdown

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
        self.BodyLabel_preset.setText(
            self._ui_text("任务勾选记录：", "Task Preset:"))
        self.PushButton_add_preset.setToolTip(self._ui_text("新建预设", "Create New Preset"))
        self.PushButton_save_preset.setToolTip(self._ui_text("保存当前勾选到预设", "Save current selection to preset"))
        self.PushButton_delete_preset.setToolTip(self._ui_text("删除当前预设", "Delete current preset"))
        self.PushButton_start.setText(self._ui_text("立即执行 (F8)", "Execute Now (F8)"))
        self.PushButton_start.setToolTip(
            self._ui_text("快捷键：F8", "Shortcut: F8"))

        self.TitleLabel.setText(self._ui_text("日志", "Log"))
        self.PushButton_select_all.setText(self._ui_text("全选", "All"))
        self.PushButton_no_select.setText(self._ui_text("清空", "Clear"))
        self.hint_label.setText(self._ui_text("拖动调整顺序", "Drag to sort"))
        self.TitleLabel_3.setText(self._ui_text("日程提醒", "Event Reminder"))

        apply_periodic_module_texts(
            self,
            is_non_chinese_ui=self.is_non_chinese_ui,
            ui_text_fn=self._ui_text,
        )
