from __future__ import annotations

from enum import Enum
from typing import Any, get_args, get_origin, Literal

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CheckBox, ComboBox, DoubleSpinBox, LineEdit, PushButton, SimpleCardWidget, SpinBox

from app.framework.i18n import tr
from app.framework.infra.config.app_config import config
from app.framework.core.module_system.models import SchemaField
from app.framework.core.module_system.naming import humanize_name


class AutoPage(QWidget):
    """Default generated module settings page from module schema."""

    def __init__(self, parent=None, *, module_meta=None, host_context=None):
        super().__init__(parent)
        self.module_meta = module_meta
        self.host_context = host_context
        self.field_widgets: dict[str, QWidget] = {}

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(10)
        self.left_layout = QVBoxLayout()
        self.right_layout = QVBoxLayout()
        self.main_layout.addLayout(self.left_layout, 1)
        self.main_layout.addLayout(self.right_layout, 0)

        self.SimpleCardWidget_option = SimpleCardWidget(self)
        self.SimpleCardWidget_option.setObjectName("SimpleCardWidget_option")
        option_layout = QVBoxLayout(self.SimpleCardWidget_option)
        self.title_label = BodyLabel(self.SimpleCardWidget_option)
        option_layout.addWidget(self.title_label)

        self.form_widget = QWidget(self.SimpleCardWidget_option)
        self.form_layout = QFormLayout(self.form_widget)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        option_layout.addWidget(self.form_widget)

        action_row = QHBoxLayout()
        self.PushButton_save = PushButton(tr('framework.ui.save', fallback='Save'), self.SimpleCardWidget_option)
        self.PushButton_start = PushButton(tr('framework.ui.run', fallback='Run'), self.SimpleCardWidget_option)
        self.PushButton_start.setObjectName("PushButton_start")
        self.PushButton_save.clicked.connect(self._save_values)
        action_row.addWidget(self.PushButton_save)
        action_row.addWidget(self.PushButton_start)
        action_row.addStretch(1)
        option_layout.addLayout(action_row)

        self.left_layout.addWidget(self.SimpleCardWidget_option)

        self.SimpleCardWidget_log = SimpleCardWidget(self)
        self.SimpleCardWidget_log.setObjectName("SimpleCardWidget_log")
        self.SimpleCardWidget_log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        log_layout = QVBoxLayout(self.SimpleCardWidget_log)
        log_layout.addWidget(BodyLabel(tr("framework.ui.log", fallback="Log"), self.SimpleCardWidget_log))
        self.textBrowser_log = QTextBrowser(self.SimpleCardWidget_log)
        self.textBrowser_log.setObjectName("textBrowser_log")
        log_layout.addWidget(self.textBrowser_log)
        self.right_layout.addWidget(self.SimpleCardWidget_log)

        self._build_from_schema(getattr(module_meta, "config_schema", []))
        self._load_values()

    def bind_host_context(self, host_context):
        self.host_context = host_context

    def _label_for(self, field: SchemaField) -> str:
        return tr(field.label_key, fallback=field.label_default or humanize_name(field.param_name))

    def _widget_for_field(self, field: SchemaField) -> QWidget:
        hint = field.type_hint
        origin = get_origin(hint)

        if hint is bool:
            return CheckBox(self.form_widget)
        if hint is int:
            w = SpinBox(self.form_widget)
            w.setRange(-999999999, 999999999)
            return w
        if hint is float:
            w = DoubleSpinBox(self.form_widget)
            w.setRange(-1_000_000.0, 1_000_000.0)
            w.setDecimals(4)
            return w
        if origin in (Literal,):
            w = ComboBox(self.form_widget)
            for item in get_args(hint):
                w.addItem(str(item))
            return w
        if isinstance(hint, type) and issubclass(hint, Enum):
            w = ComboBox(self.form_widget)
            for item in hint:
                w.addItem(str(item.value))
            return w
        return LineEdit(self.form_widget)

    def _set_widget_value(self, widget: QWidget, value: Any):
        if isinstance(widget, CheckBox):
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
        if isinstance(widget, CheckBox):
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
        self.title_label.setText(tr(f"module.{module_id}.title", fallback=module_name))
        for field in schema:
            widget = self._widget_for_field(field)
            widget.setObjectName(field.param_name)
            self.field_widgets[field.param_name] = widget
            self.form_layout.addRow(self._label_for(field), widget)

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
