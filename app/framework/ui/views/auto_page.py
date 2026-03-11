from __future__ import annotations

from enum import Enum
from typing import Any, get_args, get_origin, Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QGridLayout,
)
from qfluentwidgets import (
    BodyLabel, 
    CheckBox, 
    ComboBox, 
    DoubleSpinBox, 
    LineEdit, 
    PushButton, 
    SimpleCardWidget, 
    SpinBox, 
    StrongBodyLabel,
    ScrollArea,
    SettingCardGroup,
    SwitchButton,
)

from app.framework.i18n import tr
from app.framework.infra.config.app_config import config
from app.framework.core.module_system.models import SchemaField
from app.framework.core.module_system.naming import humanize_name


class AutoPage(QWidget):
    """Refined generated module settings page with semantic grouping and grid layout."""

    def __init__(self, parent=None, *, module_meta=None, host_context=None):
        super().__init__(parent)
        self.module_meta = module_meta
        self.host_context = host_context
        self.field_widgets: dict[str, QWidget] = {}

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(12)

        # Left: Settings (Scrollable)
        self.left_container = QWidget()
        self.left_layout = QVBoxLayout(self.left_container)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(12)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidget(self.left_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("ScrollArea {background: transparent; border: none}")
        self.scroll_area.viewport().setStyleSheet("background: transparent")
        
        self.main_layout.addWidget(self.scroll_area, 2)

        # Right: Log & Actions
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(12)
        self.main_layout.addLayout(self.right_layout, 1)

        # Log Card
        self.SimpleCardWidget_log = SimpleCardWidget(self)
        self.SimpleCardWidget_log.setObjectName("SimpleCardWidget_log")
        self.SimpleCardWidget_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_inner_layout = QVBoxLayout(self.SimpleCardWidget_log)
        
        self.log_title = StrongBodyLabel(tr("framework.ui.log", fallback="Log"), self.SimpleCardWidget_log)
        log_inner_layout.addWidget(self.log_title)
        
        self.textBrowser_log = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log.setObjectName("textBrowser_log")
        self.textBrowser_log.setStyleSheet("border: none; background: transparent")
        log_inner_layout.addWidget(self.textBrowser_log)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

        # Actions Card
        self.SimpleCardWidget_actions = SimpleCardWidget(self)
        actions_layout = QVBoxLayout(self.SimpleCardWidget_actions)
        
        self.PushButton_start = PushButton(tr('framework.ui.run', fallback='Run'), self.SimpleCardWidget_actions)
        self.PushButton_start.setObjectName("PushButton_start")
        self.PushButton_start.setMinimumHeight(40)
        
        self.PushButton_save = PushButton(tr('framework.ui.save', fallback='Save'), self.SimpleCardWidget_actions)
        self.PushButton_save.clicked.connect(self._save_values)
        
        actions_layout.addWidget(self.PushButton_start)
        actions_layout.addWidget(self.PushButton_save)
        self.right_layout.addWidget(self.SimpleCardWidget_actions)

        self._build_from_schema(getattr(module_meta, "config_schema", []))
        self._load_values()

    def _label_for(self, field: SchemaField) -> str:
        return tr(field.label_key, fallback=field.label_default or humanize_name(field.param_name))

    def _widget_for_field(self, field: SchemaField, parent: QWidget) -> QWidget:
        hint = field.type_hint
        origin = get_origin(hint)

        if hint is bool:
            return SwitchButton(parent)
        if hint is int:
            w = SpinBox(parent)
            w.setRange(-999999999, 999999999)
            return w
        if hint is float:
            w = DoubleSpinBox(parent)
            w.setRange(-1_000_000.0, 1_000_000.0)
            w.setDecimals(4)
            return w
        if origin in (Literal,):
            w = ComboBox(parent)
            for item in get_args(hint):
                w.addItem(str(item))
            return w
        if isinstance(hint, type) and issubclass(hint, Enum):
            w = ComboBox(parent)
            for item in hint:
                w.addItem(str(item.value))
            return w
        return LineEdit(parent)

    def _set_widget_value(self, widget: QWidget, value: Any):
        if isinstance(widget, SwitchButton):
            widget.setChecked(bool(value))
        elif isinstance(widget, SpinBox):
            widget.setValue(int(value or 0))
        elif isinstance(widget, DoubleSpinBox):
            widget.setValue(float(value or 0.0))
        elif isinstance(widget, ComboBox):
            value_text = str(value)
            idx = widget.findText(value_text)
            if idx >= 0:
                widget.setCurrentIndex(idx)
        elif isinstance(widget, LineEdit):
            widget.setText("" if value is None else str(value))

    def _get_widget_value(self, widget: QWidget) -> Any:
        if isinstance(widget, SwitchButton):
            return widget.isChecked()
        if isinstance(widget, SpinBox):
            return widget.value()
        if isinstance(widget, DoubleSpinBox):
            return widget.value()
        if isinstance(widget, ComboBox):
            return widget.currentText()
        if isinstance(widget, LineEdit):
            return widget.text()
        return None

    def _build_from_schema(self, schema: list[SchemaField]):
        module_id = getattr(self.module_meta, 'id', 'module')
        module_name = getattr(self.module_meta, 'name', 'Module')
        
        # 1. Tips section if description exists
        description = getattr(self.module_meta, 'description', "")
        if description:
            tips_card = SimpleCardWidget(self)
            tips_layout = QVBoxLayout(tips_card)
            tips_label = BodyLabel(tips_card)
            tips_label.setTextFormat(Qt.TextFormat.MarkdownText)
            tips_label.setWordWrap(True)
            # Use tr for localized description if possible
            desc_tr = tr(f"module.{module_id}.description", fallback=description)
            tips_label.setText(desc_tr)
            tips_layout.addWidget(tips_label)
            self.left_layout.addWidget(tips_card)

        # 2. Group fields
        groups: dict[str | None, list[SchemaField]] = {}
        for field in schema:
            groups.setdefault(field.group, []).append(field)

        # 3. Create widgets per group
        for group_name, fields in groups.items():
            display_group_name = group_name if group_name else tr(f"module.{module_id}.title", fallback=module_name)
            group_widget = SettingCardGroup(display_group_name, self.left_container)
            
            # Use a grid layout inside a container to allow half-width items
            content_container = QWidget()
            grid_layout = QGridLayout(content_container)
            grid_layout.setContentsMargins(16, 8, 16, 16)
            grid_layout.setSpacing(12)
            
            current_row = 0
            current_col = 0
            
            for field in fields:
                field_widget = self._widget_for_field(field, content_container)
                field_widget.setObjectName(field.param_name)
                self.field_widgets[field.param_name] = field_widget
                
                label = BodyLabel(self._label_for(field), content_container)
                
                # Determine spans based on layout hint
                if field.layout == "half":
                    grid_layout.addWidget(label, current_row, current_col * 2)
                    grid_layout.addWidget(field_widget, current_row, current_col * 2 + 1)
                    current_col += 1
                    if current_col >= 2:
                        current_row += 1
                        current_col = 0
                else:
                    # If we have a pending half-col, move to next row
                    if current_col != 0:
                        current_row += 1
                        current_col = 0
                    
                    grid_layout.addWidget(label, current_row, 0)
                    grid_layout.addWidget(field_widget, current_row, 1, 1, 3) # Span across
                    current_row += 1
            
            group_widget.addSettingCard(content_container)
            self.left_layout.addWidget(group_widget)

        self.left_layout.addStretch(1)

    def _load_values(self):
        for field in getattr(self.module_meta, "config_schema", []):
            widget = self.field_widgets.get(field.param_name)
            if widget is None:
                continue
            cfg_item = getattr(config, field.param_name, None)
            if cfg_item is not None and hasattr(cfg_item, "value"):
                value = cfg_item.value
            else:
                value = field.default
            self._set_widget_value(widget, value)

    def _save_values(self):
        for field in getattr(self.module_meta, "config_schema", []):
            widget = self.field_widgets.get(field.param_name)
            if widget is None:
                continue
            cfg_item = getattr(config, field.param_name, None)
            if cfg_item is None:
                continue
            config.set(cfg_item, self._get_widget_value(widget))
