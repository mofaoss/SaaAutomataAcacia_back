from __future__ import annotations

from enum import Enum
import colorsys
import inspect
import json
import logging
import re
from typing import Any, get_args, get_origin, Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QFormLayout,
    QPlainTextEdit,
)
from qfluentwidgets import (
    BodyLabel, 
    ComboBox, 
    DoubleSpinBox, 
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget, 
    SpinBox, 
    StrongBodyLabel,
    ScrollArea,
    Slider,
    SwitchButton,
    LineEdit,
)

from app.framework.i18n import _, tr
from app.framework.infra.config.app_config import config
from app.framework.core.module_system.models import SchemaField
from app.framework.core.module_system.naming import humanize_name
from app.framework.ui.auto_page.i18n_mixin import AutoPageI18nMixin


class AutoPageBase(AutoPageI18nMixin, QWidget):
    """Battle-hardened AutoPage: Guaranteed type safety and pixel-perfect layout."""

    def __init__(self, parent=None, *, module_meta=None, host_context=None):
        super().__init__(parent)
        self.module_meta = module_meta
        self.host_context = host_context
        self.field_widgets: dict[str, QWidget] = {}
        self.action_buttons: dict[str, PushButton] = {}
        self._action_instances: dict[type, object] = {}
        self._is_running = False
        self._rendered_group_keys: set[str] = set()
        self._color_previews: list[dict[str, Any]] = []
        self._resolved_action_specs: list[dict[str, Any]] = []
        self.PushButton_start: PrimaryPushButton | None = None
        self.SimpleCardWidget_log: SimpleCardWidget | None = None
        self.textBrowser_log: QTextBrowser | None = None

        module_id = getattr(module_meta, 'id', 'unknown')
        self.setObjectName(f"page_{module_id}")

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(16)

        # Left Panel (Stretch 2)
        self.left_panel = QWidget()
        self.left_panel_layout = QVBoxLayout(self.left_panel)
        self.left_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.left_panel_layout.setSpacing(12)

        # Scroll Area
        self.scroll_area = ScrollArea(self.left_panel)
        self.settings_container = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_container)
        self.settings_layout.setContentsMargins(0, 0, 12, 0)
        self.settings_layout.setSpacing(8)
        self.settings_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.settings_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("ScrollArea {background: transparent; border: none}")
        self.scroll_area.viewport().setStyleSheet("background: transparent")

        self.left_panel_layout.addWidget(self.scroll_area, 1)

        # Optional custom module actions (e.g., calibration helpers)
        self.actions_bar = QWidget(self.left_panel)
        self.actions_layout = QHBoxLayout(self.actions_bar)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(8)
        self.actions_bar.setVisible(False)
        self.left_panel_layout.addWidget(self.actions_bar)

        if self._should_show_start_button():
            self.PushButton_start = self._create_start_button(module_id)
            self.left_panel_layout.addWidget(self.PushButton_start)

        self.main_layout.addWidget(self.left_panel, 2)

        if self._should_show_log_panel():
            self.SimpleCardWidget_log = self._create_log_panel(module_id)
            self.main_layout.addWidget(self.SimpleCardWidget_log, 1)
        else:
            self.main_layout.setStretch(0, 1)

        self._build_from_schema(getattr(module_meta, "config_schema", []))
        self._build_actions()
        self._load_values()
        self._update_button_state(False)

    def _should_show_start_button(self) -> bool:
        return True

    def _should_show_log_panel(self) -> bool:
        return True

    def _create_start_button(self, module_id: str) -> PrimaryPushButton:
        button = PrimaryPushButton(self.left_panel)
        button.setObjectName(f"PushButton_start_{module_id}")
        button.setFixedHeight(45)
        button.clicked.connect(self._handle_start_click)
        # Compatibility alias for legacy host bindings that resolve by attribute names.
        setattr(self, f"PushButton_start_{module_id}", button)
        return button

    def _create_log_panel(self, module_id: str) -> SimpleCardWidget:
        card = SimpleCardWidget(self)
        log_inner_layout = QVBoxLayout(card)
        self.log_title = StrongBodyLabel(tr("framework.ui.log", fallback="Log"), card)
        log_inner_layout.addWidget(self.log_title)
        self.textBrowser_log = QTextBrowser(card)
        self.textBrowser_log.setObjectName(f"textBrowser_log_{module_id}")
        self.textBrowser_log.setStyleSheet("border: none; background: transparent")
        # Compatibility alias for legacy host bindings that resolve by attribute names.
        setattr(self, f"textBrowser_log_{module_id}", self.textBrowser_log)
        log_inner_layout.addWidget(self.textBrowser_log)
        return card

    def _handle_start_click(self):
        if not self._is_running:
            self._save_values()

    def set_running_state(self, is_running: bool):
        self._is_running = is_running
        self._update_button_state(is_running)

    def _update_button_state(self, is_running: bool):
        if self.PushButton_start is None:
            return

        module_id = getattr(self.module_meta, 'id', 'unknown')
        if is_running:
            stop_text = tr(f"module.{module_id}.ui.stop_{module_id}")
            if stop_text == f"module.{module_id}.ui.stop_{module_id}":
                stop_text = tr('framework.ui.stop', fallback='Stop')
            self.PushButton_start.setText(stop_text)
        else:
            start_text = tr(f"module.{module_id}.ui.start_{module_id}")
            if start_text == f"module.{module_id}.ui.start_{module_id}":
                start_text = tr('framework.ui.run', fallback='Run')
            self.PushButton_start.setText(start_text)

    def __getattr__(self, name: str) -> QWidget:
        # Generic proxy: Allow access to auto-generated widgets as if they were attributes.
        # This maintains compatibility with code expecting manual UI attribute naming.
        if "field_widgets" in self.__dict__ and name in self.field_widgets:
            return self.field_widgets[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def _iter_action_specs(self) -> list[dict[str, Any]]:
        actions = getattr(self.module_meta, "actions", None) or {}
        if not isinstance(actions, dict):
            return []

        specs: list[dict[str, Any]] = []
        for raw_label, raw_spec in actions.items():
            label = str(raw_label or "").strip()
            if not label:
                continue

            method_name = ""
            group_name: str | None = None
            order = 100
            primary: bool | None = None

            if isinstance(raw_spec, str):
                method_name = raw_spec.strip()
            elif isinstance(raw_spec, dict):
                method_name = str(raw_spec.get("method") or raw_spec.get("name") or "").strip()
                raw_group = raw_spec.get("group")
                if isinstance(raw_group, str) and raw_group.strip():
                    group_name = raw_group.strip()
                raw_order = raw_spec.get("order")
                if isinstance(raw_order, (int, float)):
                    order = int(raw_order)
                raw_primary = raw_spec.get("primary")
                if isinstance(raw_primary, bool):
                    primary = raw_primary
            else:
                continue

            if not method_name:
                continue

            specs.append(
                {
                    "label": label,
                    "method": method_name,
                    "group": group_name,
                    "order": order,
                    "primary": primary,
                }
            )

        return sorted(
            specs,
            key=lambda s: (
                self._normalize_group_key(s.get("group")),
                int(s.get("order", 100)),
                str(s.get("label", "")),
            ),
        )

    def _group_tokens(self, group_name: str | None, fields: list[SchemaField]) -> set[str]:
        tokens = self._tokenize_for_match(str(group_name or ""))
        for field in fields:
            tokens.update(self._tokenize_for_match(self._strip_widget_prefix(field.param_name)))
            tokens.update(self._tokenize_for_match(field.field_id))
        return tokens

    @staticmethod
    def _token_overlap_score(left: set[str], right: set[str]) -> int:
        if not left or not right:
            return 0
        return len(left & right)

    def _resolve_action_groups(self, group_entries: list[tuple[str | None, list[SchemaField]]]) -> list[dict[str, Any]]:
        specs = self._iter_action_specs()
        if not specs:
            return []

        group_meta: list[dict[str, Any]] = []
        for group_name, fields in group_entries:
            key = self._normalize_group_key(group_name)
            if not key:
                continue
            group_meta.append(
                {
                    "name": group_name,
                    "key": key,
                    "tokens": self._group_tokens(group_name, fields),
                    "is_general": key in {"general", "game_settings"},
                }
            )

        if not group_meta:
            return specs

        for spec in specs:
            raw_group = spec.get("group")
            if isinstance(raw_group, str) and raw_group.strip():
                continue

            action_tokens = self._tokenize_for_match(f"{spec.get('label', '')} {spec.get('method', '')}")
            scored = [
                (self._token_overlap_score(action_tokens, meta["tokens"]), meta)
                for meta in group_meta
            ]
            scored.sort(key=lambda item: (item[0], 0 if item[1]["is_general"] else 1), reverse=True)
            if scored and scored[0][0] > 0:
                spec["group"] = scored[0][1]["name"]

        assigned_non_general = {
            self._normalize_group_key(spec.get("group"))
            for spec in specs
            if spec.get("group") and self._normalize_group_key(spec.get("group")) not in {"", "general", "game_settings"}
        }

        fallback_group_name: str | None = None
        if len(assigned_non_general) == 1:
            fallback_key = next(iter(assigned_non_general))
            fallback_meta = next((meta for meta in group_meta if meta["key"] == fallback_key), None)
            fallback_group_name = fallback_meta["name"] if fallback_meta is not None else None
        elif len(group_meta) == 1:
            fallback_group_name = group_meta[0]["name"]

        if fallback_group_name is not None:
            for spec in specs:
                if not spec.get("group"):
                    spec["group"] = fallback_group_name

        return specs

    def _action_is_primary(self, spec: dict[str, Any], *, prefer_primary: bool) -> bool:
        raw = spec.get("primary")
        if isinstance(raw, bool):
            return raw
        if not prefer_primary:
            return False
        probe = f"{spec.get('label', '')} {spec.get('method', '')}".lower()
        return any(token in probe for token in ("start", "run", "test", "open", "apply"))

    def _create_action_button(self, spec: dict[str, Any], parent: QWidget, *, prefer_primary: bool) -> PushButton:
        button_cls = PrimaryPushButton if self._action_is_primary(spec, prefer_primary=prefer_primary) else PushButton
        button = button_cls(parent)
        method_name = str(spec.get("method", "")).strip()
        label = str(spec.get("label", "")).strip() or method_name
        button.setText(self._action_label(label, method_name))
        button.setObjectName(f"PushButton_action_{self._snake_key(method_name)}")
        button.clicked.connect(
            lambda _checked=False, m=method_name, b=button: self._invoke_action(m, b)
        )
        self.action_buttons[method_name] = button
        return button

    def _group_actions_for(self, group_name: str | None) -> list[dict[str, Any]]:
        target = self._normalize_group_key(group_name)
        if not target:
            return []
        return [
            spec
            for spec in self._resolved_action_specs
            if self._normalize_group_key(spec.get("group")) == target
        ]

    def _build_actions(self) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        specs = list(self._resolved_action_specs)
        if not specs:
            self.actions_bar.setVisible(False)
            return

        orphan_specs: list[dict[str, Any]] = []
        for spec in specs:
            group_key = self._normalize_group_key(spec.get("group"))
            if not group_key or group_key not in self._rendered_group_keys:
                orphan_specs.append(spec)

        if not orphan_specs:
            self.actions_bar.setVisible(False)
            return

        self.actions_bar.setVisible(True)
        for spec in orphan_specs:
            button = self._create_action_button(spec, self.actions_bar, prefer_primary=False)
            self.actions_layout.addWidget(button)
        self.actions_layout.addStretch(1)

    def _build_action_instance(self, module_class: type):
        ctor = inspect.signature(module_class)
        kwargs: dict[str, Any] = {}
        action_logger = logging.getLogger(f"auto_page.action.{getattr(self.module_meta, 'id', 'module')}")

        for name, param in ctor.parameters.items():
            if name == "self":
                continue
            if name in {"auto", "automation"}:
                kwargs[name] = None
                continue
            if name == "logger":
                kwargs[name] = action_logger
                continue
            if name in {"app_config", "config_provider"}:
                kwargs[name] = config
                continue

            cfg_item = getattr(config, name, None)
            if cfg_item is not None and hasattr(cfg_item, "value"):
                kwargs[name] = cfg_item.value
                continue

            if param.default is not inspect._empty:
                kwargs[name] = param.default
                continue

            kwargs[name] = None

        return module_class(**kwargs)

    @staticmethod
    def _invoke_with_supported_kwargs(callable_obj, available_kwargs: dict[str, Any]):
        sig = inspect.signature(callable_obj)
        supports_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if supports_kwargs:
            return callable_obj(**available_kwargs)

        selected: dict[str, Any] = {}
        for name in sig.parameters:
            if name in available_kwargs:
                selected[name] = available_kwargs[name]
        return callable_obj(**selected)

    def _invoke_action(self, method_name: str, button: PushButton | None = None) -> None:
        module_class = getattr(self.module_meta, "module_class", None)
        if module_class is None:
            self.textBrowser_log.append(f"Action '{method_name}' unavailable: no module class")
            return

        try:
            raw_callable = getattr(module_class, method_name)
        except Exception:
            self.textBrowser_log.append(f"Action '{method_name}' not found on module class")
            return

        callable_obj = raw_callable
        if inspect.isfunction(raw_callable):
            params = list(inspect.signature(raw_callable).parameters.values())
            if params and params[0].name == "self":
                instance = self._action_instances.get(module_class)
                if instance is None:
                    instance = self._build_action_instance(module_class)
                    self._action_instances[module_class] = instance
                callable_obj = getattr(instance, method_name)

        context_kwargs = {
            "page": self,
            "host": self.parent(),
            "module_meta": self.module_meta,
            "config": config,
            "logger": logging.getLogger(f"auto_page.action.{getattr(self.module_meta, 'id', 'module')}"),
            "button": button,
            "field_widgets": self.field_widgets,
        }

        try:
            self._save_values()
            result = self._invoke_with_supported_kwargs(callable_obj, context_kwargs)
            if isinstance(result, str) and result.strip():
                self.textBrowser_log.append(result)
            self._load_values()
        except Exception as exc:
            logging.getLogger(__name__).exception("AutoPage action failed: %s", method_name)
            self.textBrowser_log.append(str(_("Action failed: {error}", msgid="action_failed_error", error=str(exc))))

    def _label_for(self, field: SchemaField) -> str:
        translated = self._first_translated(self._field_label_candidates(field))
        if translated:
            return translated

        fallback = tr(field.label_default, fallback=field.label_default)
        if fallback != field.label_default:
            return fallback

        stripped = self._strip_widget_prefix(field.param_name)
        return humanize_name(stripped) or str(field.label_default)
    def _config_item(self, field: SchemaField):
        return getattr(config, field.param_name, None)

    @staticmethod
    def _iterable_default_options(default_value: Any) -> list[Any]:
        if default_value is None:
            return []
        if isinstance(default_value, (str, bytes, dict)):
            return []
        if isinstance(default_value, range):
            return list(default_value)
        if isinstance(default_value, (list, tuple, set)):
            return list(default_value)
        return []

    @staticmethod
    def _strip_optional_hint(type_hint: Any) -> Any:
        if type_hint is inspect._empty:
            return None
        origin = get_origin(type_hint)
        if origin is None:
            return type_hint
        if origin in (Literal,):
            return type_hint
        args = [arg for arg in get_args(type_hint) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
        return type_hint

    def _field_hint_and_default(self, field: SchemaField) -> tuple[Any, Any]:
        cfg_item = self._config_item(field)
        cfg_default = getattr(cfg_item, "defaultValue", None) if cfg_item is not None else None
        default_value = cfg_default if cfg_default is not None else field.default

        hint = self._strip_optional_hint(field.type_hint)
        if hint is None and default_value is not None:
            hint = type(default_value)
        return hint, default_value

    def _field_widget_kind(self, field: SchemaField) -> str:
        name = str(getattr(field, "param_name", "") or "")
        prefix = name.split("_", 1)[0]
        forced_line_edit = prefix == "LineEdit"
        if prefix in {"ComboBox", "CheckBox", "Slider", "TextEdit"}:
            return prefix
        if prefix == "DoubleSpinBox":
            return "DoubleSpinBox"

        hint, default_value = self._field_hint_and_default(field)
        if prefix == "SpinBox":
            if hint is float or isinstance(default_value, float):
                return "DoubleSpinBox"
            return "SpinBox"

        if self._config_options(field):
            return "ComboBox"

        origin = get_origin(hint)
        if origin in (Literal,) or (isinstance(hint, type) and issubclass(hint, Enum)):
            return "ComboBox"
        if hint in (dict,) or origin in (dict,) or isinstance(default_value, dict):
            return "TextEdit"
        if hint in (list, tuple, set) or origin in (list, tuple, set) or isinstance(default_value, (list, tuple, set)):
            default_options = self._iterable_default_options(default_value)
            if default_options:
                return "ComboBox"
            return "LineEdit" if forced_line_edit else "TextEdit"
        if forced_line_edit:
            return "LineEdit"
        if hint is bool:
            return "CheckBox"
        if hint is float:
            return "DoubleSpinBox"
        if hint is int:
            return "SpinBox"
        if isinstance(default_value, float):
            return "DoubleSpinBox"
        if isinstance(default_value, int) and not isinstance(default_value, bool):
            return "SpinBox"
        if isinstance(default_value, str) and "\n" in default_value:
            return "TextEdit"
        return "LineEdit"

    @staticmethod
    def _config_options(field: SchemaField) -> list[Any]:
        cfg_item = getattr(config, field.param_name, None)
        candidates = []
        if cfg_item is not None:
            candidates.append(getattr(cfg_item, "options", None))
            validator = getattr(cfg_item, "validator", None)
            candidates.append(getattr(validator, "options", None) if validator is not None else None)

        for raw in candidates:
            if raw is None:
                continue
            if isinstance(raw, range):
                return list(raw)
            if isinstance(raw, (list, tuple, set)):
                return list(raw)
            try:
                return list(raw)
            except Exception:
                continue

        hint = AutoPageBase._strip_optional_hint(field.type_hint)
        origin = get_origin(hint)
        if origin in (Literal,):
            return list(get_args(hint))
        if isinstance(hint, type) and issubclass(hint, Enum):
            return [item.value for item in hint]
        return []

    @staticmethod
    def _normalize_option(raw_option: Any) -> tuple[Any, str | None]:
        if isinstance(raw_option, dict):
            if "value" in raw_option:
                value = raw_option.get("value")
                label = raw_option.get("label")
                return value, str(label) if label is not None else None
            if len(raw_option) == 1:
                value, label = next(iter(raw_option.items()))
                return value, str(label)

        if isinstance(raw_option, (tuple, list)) and len(raw_option) == 2:
            first, second = raw_option
            if isinstance(first, str) and not isinstance(second, str):
                return second, first
            if isinstance(second, str):
                return first, second
            return first, None

        return raw_option, None


    def _option_label(self, field: SchemaField, option: Any) -> str:
        option_raw = str(option)
        option_key = self._snake_key(option_raw, max_len=48)
        param_key = self._snake_key(field.param_name, max_len=64)
        field_key = self._snake_key(field.field_id, max_len=64)
        stripped_key = self._snake_key(self._strip_widget_prefix(field.param_name), max_len=64)

        candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            candidates.extend([
                f"module.{module_id}.field.{field.field_id}.option.{option_raw}",
                f"module.{module_id}.field.{field.param_name}.option.{option_raw}",
                f"module.{module_id}.field.{stripped_key}.option.{option_raw}",
                f"module.{module_id}.option.{field_key}.{option_raw}",
                f"module.{module_id}.option.{param_key}.{option_raw}",
                f"module.{module_id}.option.{stripped_key}.{option_raw}",
                f"module.{module_id}.ui.{field_key}_{option_raw}",
                f"module.{module_id}.ui.{param_key}_{option_raw}",
                f"module.{module_id}.ui.{stripped_key}_{option_raw}",
            ])
            if option_key and option_key != option_raw:
                candidates.extend([
                    f"module.{module_id}.field.{field.field_id}.option.{option_key}",
                    f"module.{module_id}.field.{field.param_name}.option.{option_key}",
                    f"module.{module_id}.field.{stripped_key}.option.{option_key}",
                    f"module.{module_id}.option.{field_key}.{option_key}",
                    f"module.{module_id}.option.{param_key}.{option_key}",
                    f"module.{module_id}.option.{stripped_key}.{option_key}",
                    f"module.{module_id}.ui.{field_key}_{option_key}",
                    f"module.{module_id}.ui.{param_key}_{option_key}",
                    f"module.{module_id}.ui.{stripped_key}_{option_key}",
                ])

        translated = self._first_translated(candidates)
        if translated:
            return translated
        return tr(option_raw, fallback=option_raw)

    def _combo_items(self, field: SchemaField) -> list[tuple[Any, str]]:
        options = self._config_options(field)
        if not options:
            options = self._iterable_default_options(field.default)
        if not options and field.default is not None:
            options = [field.default]

        combo_items: list[tuple[Any, str]] = []
        seen: set[str] = set()
        for option in options:
            value, explicit_label = self._normalize_option(option)
            dedupe_key = f"{type(value).__name__}:{value!r}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            if explicit_label is not None and explicit_label.strip():
                explicit_key = self._snake_key(explicit_label, max_len=80)
                explicit_candidates = [explicit_label]
                for module_id in self._module_i18n_ids():
                    explicit_candidates.append(f"module.{module_id}.ui.{explicit_key}")
                label = self._first_translated(explicit_candidates)
                if not label:
                    label = tr(explicit_label, fallback=explicit_label)
            else:
                label = self._option_label(field, value)
            combo_items.append((value, label))
        return combo_items

    def _numeric_bounds(self, field: SchemaField, *, is_float: bool = False, is_slider: bool = False) -> tuple[float, float]:
        cfg_item = self._config_item(field)
        default_min = 0.0 if is_slider else (-1_000_000.0 if is_float else -999999999.0)
        default_max = 100.0 if is_slider else (1_000_000.0 if is_float else 999999999.0)

        candidate_min = None
        candidate_max = None

        if cfg_item is not None:
            validator = getattr(cfg_item, "validator", None)
            for owner in (validator, cfg_item):
                if owner is None:
                    continue
                for attr in ("min", "minimum", "bottom"):
                    if hasattr(owner, attr):
                        raw = getattr(owner, attr)
                        if isinstance(raw, (int, float)):
                            candidate_min = float(raw)
                            break
                for attr in ("max", "maximum", "top"):
                    if hasattr(owner, attr):
                        raw = getattr(owner, attr)
                        if isinstance(raw, (int, float)):
                            candidate_max = float(raw)
                            break

            options = getattr(cfg_item, "options", None)
            if isinstance(options, range) and options:
                candidate_min = float(min(options))
                candidate_max = float(max(options))

        if candidate_min is None:
            candidate_min = default_min
        if candidate_max is None:
            candidate_max = default_max
        if candidate_max < candidate_min:
            candidate_min, candidate_max = candidate_max, candidate_min
        return candidate_min, candidate_max

    @staticmethod
    def _textify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        if isinstance(value, (list, tuple, set)):
            normalized = list(value) if isinstance(value, set) else value
            try:
                return json.dumps(normalized, ensure_ascii=False)
            except Exception:
                return ", ".join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _parse_text_to_default_type(text: str, default_value: Any):
        if default_value is None:
            return text

        try:
            if isinstance(default_value, bool):
                lowered = str(text).strip().lower()
                return lowered in {"1", "true", "yes", "on"}
            if isinstance(default_value, int) and not isinstance(default_value, bool):
                return int(float(text))
            if isinstance(default_value, float):
                return float(text)
            if isinstance(default_value, str):
                return str(text)
            if isinstance(default_value, dict):
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else default_value
            if isinstance(default_value, list):
                stripped = str(text).strip()
                if not stripped:
                    return []
                if stripped.startswith("[") and stripped.endswith("]"):
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return parsed
                return [part.strip() for part in re.split(r"[\n,]", stripped) if part.strip()]
            if isinstance(default_value, tuple):
                arr = AutoPageBase._parse_text_to_default_type(text, list(default_value))
                return tuple(arr) if isinstance(arr, list) else default_value
            if isinstance(default_value, set):
                arr = AutoPageBase._parse_text_to_default_type(text, list(default_value))
                return set(arr) if isinstance(arr, list) else default_value
        except Exception:
            return default_value

        return text

    @staticmethod
    def _coerce_enum_value(enum_type: type[Enum], value: Any, default_value: Any):
        if isinstance(value, enum_type):
            return value
        for item in enum_type:
            if item.value == value or item.name == str(value) or str(item.value) == str(value):
                return item
        return default_value if isinstance(default_value, enum_type) else value

    @staticmethod
    def _coerce_literal_value(value: Any, candidates: tuple[Any, ...], default_value: Any):
        if not candidates:
            return value
        for candidate in candidates:
            if candidate == value or str(candidate) == str(value):
                return candidate
        return default_value if default_value in candidates else candidates[0]

    def _coerce_value_for_config(self, field: SchemaField, value: Any) -> Any:
        hint, default_value = self._field_hint_and_default(field)
        origin = get_origin(hint)

        if isinstance(hint, type) and issubclass(hint, Enum):
            return self._coerce_enum_value(hint, value, default_value)
        if origin in (Literal,):
            return self._coerce_literal_value(value, tuple(get_args(hint)), default_value)

        if isinstance(value, str):
            if default_value is not None:
                return self._parse_text_to_default_type(value, default_value)
            if hint in (bool, int, float, str):
                sample = {bool: False, int: 0, float: 0.0, str: ""}[hint]
                return self._parse_text_to_default_type(value, sample)
            if origin in (dict,):
                return self._parse_text_to_default_type(value, {})
            if origin in (list,):
                return self._parse_text_to_default_type(value, [])
            if origin in (tuple,):
                return self._parse_text_to_default_type(value, ())
            if origin in (set,):
                return self._parse_text_to_default_type(value, set())
            return value

        if default_value is not None:
            try:
                if isinstance(default_value, bool):
                    return bool(value)
                if isinstance(default_value, int) and not isinstance(default_value, bool):
                    return int(value)
                if isinstance(default_value, float):
                    return float(value)
            except Exception:
                return default_value

        if hint in (bool, int, float, str):
            try:
                return hint(value)
            except Exception:
                pass

        return value

    def _widget_for_field(self, field: SchemaField, parent: QWidget) -> QWidget:
        kind = self._field_widget_kind(field)

        if kind == "CheckBox":
            return SwitchButton(parent)

        if kind == "ComboBox":
            widget = ComboBox(parent)
            combo_items = self._combo_items(field)
            values: list[Any] = []
            labels: list[str] = []
            for value, label in combo_items:
                widget.addItem(label)
                values.append(value)
                labels.append(label)
            widget.setProperty("_auto_option_values", values)
            widget.setProperty("_auto_option_labels", labels)
            return widget

        if kind == "Slider":
            widget = Slider(Qt.Orientation.Horizontal, parent)
            lo, hi = self._numeric_bounds(field, is_slider=True)
            widget.setRange(int(lo), int(hi))
            return widget

        if kind == "DoubleSpinBox":
            widget = DoubleSpinBox(parent)
            lo, hi = self._numeric_bounds(field, is_float=True)
            widget.setRange(float(lo), float(hi))
            widget.setDecimals(4)
            return widget

        if kind == "SpinBox":
            widget = SpinBox(parent)
            lo, hi = self._numeric_bounds(field, is_float=False)
            widget.setRange(int(lo), int(hi))
            return widget

        if kind == "TextEdit":
            return QPlainTextEdit(parent)

        return LineEdit(parent)

    @staticmethod
    def _value_matches(left: Any, right: Any) -> bool:
        if left == right:
            return True
        try:
            return str(left) == str(right)
        except Exception:
            return False

    def _set_widget_value(self, field: SchemaField, widget: QWidget, value: Any):
        if isinstance(widget, SwitchButton):
            widget.setChecked(bool(value))
            return

        if isinstance(widget, SpinBox):
            try:
                widget.setValue(int(float(value)))
            except Exception:
                widget.setValue(0)
            return

        if isinstance(widget, DoubleSpinBox):
            try:
                widget.setValue(float(value))
            except Exception:
                widget.setValue(0.0)
            return

        if isinstance(widget, Slider):
            try:
                widget.setValue(int(float(value)))
            except Exception:
                widget.setValue(widget.minimum())
            return

        if isinstance(widget, ComboBox):
            values = widget.property("_auto_option_values")
            if isinstance(values, list) and values:
                for idx, option in enumerate(values):
                    if self._value_matches(option, value):
                        widget.setCurrentIndex(idx)
                        return

            value_text = str(value)
            idx = widget.findText(value_text)
            if idx < 0:
                idx = widget.findText(tr(value_text, fallback=value_text))
            if idx >= 0:
                widget.setCurrentIndex(idx)
            return

        if isinstance(widget, QPlainTextEdit):
            if value is None:
                widget.setPlainText("")
                return
            hint, default_value = self._field_hint_and_default(field)
            origin = get_origin(hint)
            if isinstance(default_value, (dict, list, tuple, set)) or origin in (dict, list, tuple, set):
                normalized = list(value) if isinstance(value, set) else value
                try:
                    widget.setPlainText(json.dumps(normalized, ensure_ascii=False, indent=2))
                except Exception:
                    widget.setPlainText(self._textify(value))
            else:
                widget.setPlainText(self._textify(value))
            return

        if hasattr(widget, "setText"):
            widget.setText(self._textify(value))

    def _get_widget_value(self, field: SchemaField, widget: QWidget) -> Any:
        if isinstance(widget, SwitchButton):
            return widget.isChecked()
        if isinstance(widget, SpinBox):
            return int(widget.value())
        if isinstance(widget, DoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, Slider):
            return int(widget.value())
        if isinstance(widget, ComboBox):
            idx = int(widget.currentIndex())
            values = widget.property("_auto_option_values")
            if isinstance(values, list) and 0 <= idx < len(values):
                return values[idx]
            return widget.currentText()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if hasattr(widget, "text"):
            return widget.text()
        return None

    def _group_rank(self, group_name: str | None) -> tuple[int, str]:
        key = self._normalize_group_key(group_name)
        if key in {"general", "game_settings"}:
            return 0, key
        if "calibration" in key:
            return 1, key
        if key.endswith("_settings") or key.endswith("settings"):
            return 2, key
        return 3, key

    @staticmethod
    def _parse_color_triplet(value: Any) -> tuple[int, int, int] | None:
        parts: list[int] = []
        if isinstance(value, str):
            tokens = [chunk.strip() for chunk in value.replace(";", ",").split(",")]
            for token in tokens:
                if not token:
                    continue
                try:
                    parts.append(int(float(token)))
                except Exception:
                    continue
        elif isinstance(value, (list, tuple)):
            for item in value:
                try:
                    parts.append(int(float(item)))
                except Exception:
                    continue

        if len(parts) < 3:
            return None
        return parts[0], parts[1], parts[2]

    @staticmethod
    def _triplet_to_hex(triplet: tuple[int, int, int], *, mode: str) -> str:
        a, b, c = triplet
        if mode == "hsv":
            h = int(max(0, a))
            s = max(0, min(255, int(b))) / 255.0
            v = max(0, min(255, int(c))) / 255.0
            if h <= 179:
                h_norm = h / 179.0 if 179 else 0.0
            elif h <= 360:
                h_norm = h / 360.0
            else:
                h_norm = (h % 360) / 360.0
            r, g, b = colorsys.hsv_to_rgb(h_norm, s, v)
            return f"#{int(r * 255):02X}{int(g * 255):02X}{int(b * 255):02X}"

        r = max(0, min(255, int(a)))
        g = max(0, min(255, int(b)))
        b = max(0, min(255, int(c)))
        return f"#{r:02X}{g:02X}{b:02X}"

    def _triplet_from_config_name(self, name: str) -> tuple[int, int, int] | None:
        cfg_item = getattr(config, name, None)
        if cfg_item is None:
            return None

        triplet = self._parse_color_triplet(getattr(cfg_item, "value", None))
        if triplet is not None:
            return triplet
        return self._parse_color_triplet(getattr(cfg_item, "defaultValue", None))

    @staticmethod
    def _field_stem(name: str) -> tuple[str, str | None]:
        lower = str(name).lower()
        for suffix in ("_upper", "_lower", "_min", "_max", "_base", "_current", "_preview"):
            if lower.endswith(suffix):
                return name[: -len(suffix)], suffix
        return name, None

    def _triplet_candidates_for_group(self, fields: list[SchemaField]) -> list[tuple[str, tuple[int, int, int]]]:
        names: list[str] = []
        seen: set[str] = set()

        for field in fields:
            name = str(field.param_name)
            if name not in seen:
                names.append(name)
                seen.add(name)

            stem, suffix = self._field_stem(name)
            if suffix in {"_upper", "_lower", "_min", "_max"}:
                for candidate_suffix in ("_base", "_current", "_preview"):
                    candidate = f"{stem}{candidate_suffix}"
                    if candidate not in seen and hasattr(config, candidate):
                        names.append(candidate)
                        seen.add(candidate)

        candidates: list[tuple[str, tuple[int, int, int]]] = []
        for name in names:
            triplet = self._triplet_from_config_name(name)
            if triplet is not None:
                candidates.append((name, triplet))
        return candidates

    @staticmethod
    def _infer_triplet_mode(triplet: tuple[int, int, int]) -> str:
        h, s, v = triplet
        if 0 <= h <= 179 and 0 <= s <= 255 and 0 <= v <= 255:
            return "hsv"
        return "rgb"

    def _choose_preview_source(self, candidates: list[tuple[str, tuple[int, int, int]]]) -> tuple[str, str] | None:
        if not candidates:
            return None

        def sort_key(item: tuple[str, tuple[int, int, int]]):
            name = item[0].lower()
            if name.endswith("_base"):
                priority = 0
            elif name.endswith("_current"):
                priority = 1
            elif name.endswith("_preview"):
                priority = 2
            else:
                priority = 3
            return (priority, name)

        source_name, triplet = sorted(candidates, key=sort_key)[0]
        return source_name, self._infer_triplet_mode(triplet)

    def _register_color_preview(self, swatch: QWidget, source_name: str, mode: str) -> None:
        self._color_previews.append({"widget": swatch, "source": source_name, "mode": mode})

    def _update_color_previews(self) -> None:
        for binding in self._color_previews:
            swatch = binding.get("widget")
            source_name = str(binding.get("source") or "")
            mode = str(binding.get("mode") or "hsv")
            if not isinstance(swatch, QWidget) or not source_name:
                continue

            cfg_item = getattr(config, source_name, None)
            raw_value = getattr(cfg_item, "value", None) if cfg_item is not None else None
            triplet = self._parse_color_triplet(raw_value)
            if triplet is None and cfg_item is not None:
                triplet = self._parse_color_triplet(getattr(cfg_item, "defaultValue", None))

            if triplet is None:
                swatch.setStyleSheet("background: transparent; border: 1px solid rgba(127,127,127,0.5); border-radius: 6px;")
                continue

            color_hex = self._triplet_to_hex(triplet, mode=mode)
            swatch.setStyleSheet(f"background: {color_hex}; border: 1px solid rgba(20,20,20,0.35); border-radius: 6px;")

    def _build_from_schema(self, schema: list[SchemaField]):
        module_id = getattr(self.module_meta, 'id', 'module')
        self._rendered_group_keys.clear()
        self._color_previews.clear()
        self.action_buttons.clear()

        # 1. Tips
        description = getattr(self.module_meta, 'description', "")
        if description:
            tips_card = SimpleCardWidget(self)
            tips_layout = QVBoxLayout(tips_card)
            tips_layout.setContentsMargins(12, 12, 12, 12)
            tips_label = BodyLabel(tips_card)
            tips_label.setTextFormat(Qt.TextFormat.MarkdownText)
            tips_label.setWordWrap(True)
            tips_label.setText(self._tips_text(str(description)))
            tips_layout.addWidget(tips_label)
            self.settings_layout.addWidget(tips_card)

        # 2. Group Fields
        groups: dict[str | None, list[SchemaField]] = {}
        for field in schema:
            groups.setdefault(field.group, []).append(field)

        ordered_groups = sorted(groups.items(), key=lambda item: self._group_rank(item[0]))
        self._resolved_action_specs = self._resolve_action_groups(ordered_groups)

        for group_name, fields in ordered_groups:
            display_name = self._group_label(group_name)
            self._rendered_group_keys.add(self._normalize_group_key(group_name))

            header = StrongBodyLabel(display_name, self.settings_container)
            self.settings_layout.addWidget(header)

            group_card = SimpleCardWidget(self.settings_container)
            group_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

            form_layout = QFormLayout(group_card)
            form_layout.setContentsMargins(16, 12, 16, 12)
            form_layout.setSpacing(12)
            form_layout.setHorizontalSpacing(16)
            form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
            form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

            pending_half_field = None
            for field in fields:
                widget = self._widget_for_field(field, group_card)
                widget.setObjectName(field.param_name)
                self.field_widgets[field.param_name] = widget
                label = BodyLabel(self._label_for(field), group_card)

                if field.layout == "half":
                    if pending_half_field is None:
                        row_w = QWidget()
                        h_layout = QHBoxLayout(row_w)
                        h_layout.setContentsMargins(0, 0, 0, 0)
                        h_layout.setSpacing(24)
                        h_layout.addWidget(label)
                        h_layout.addWidget(widget)
                        h_layout.addStretch(1)
                        form_layout.addRow(row_w)
                        pending_half_field = h_layout
                    else:
                        pending_half_field.takeAt(pending_half_field.count() - 1)
                        pending_half_field.addWidget(label)
                        pending_half_field.addWidget(widget)
                        pending_half_field.addStretch(1)
                        pending_half_field = None
                else:
                    pending_half_field = None
                    form_layout.addRow(label, widget)

            group_actions = self._group_actions_for(group_name)
            if group_actions:
                actions_row = QWidget(group_card)
                actions_layout = QHBoxLayout(actions_row)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_layout.setSpacing(8)
                for spec in group_actions:
                    button = self._create_action_button(spec, group_card, prefer_primary=True)
                    actions_layout.addWidget(button)
                actions_layout.addStretch(1)
                form_layout.addRow(actions_row)

            preview_candidates = self._triplet_candidates_for_group(fields)
            chosen_preview = self._choose_preview_source(preview_candidates)
            if chosen_preview is not None:
                source_name, mode = chosen_preview
                preview_host = QWidget(group_card)
                preview_layout = QHBoxLayout(preview_host)
                preview_layout.setContentsMargins(0, 0, 0, 0)
                preview_layout.setSpacing(8)

                swatch = QWidget(preview_host)
                swatch.setObjectName(f"ColorPreview_{self._snake_key(source_name, max_len=64)}")
                swatch.setFixedSize(88, 24)
                preview_layout.addWidget(swatch)
                preview_layout.addStretch(1)

                preview_label = BodyLabel(tr("framework.ui.current_color", fallback="Current Color"), group_card)
                form_layout.addRow(preview_label, preview_host)
                self._register_color_preview(swatch, source_name, mode)

            self.settings_layout.addWidget(group_card)
            self.settings_layout.addSpacing(4)

        self.settings_layout.addStretch(1)

    def _load_values(self):
        for field in getattr(self.module_meta, "config_schema", []):
            widget = self.field_widgets.get(field.param_name)
            if widget is None:
                continue
            cfg_item = getattr(config, field.param_name, None)
            val = cfg_item.value if cfg_item is not None and hasattr(cfg_item, "value") else field.default
            self._set_widget_value(field, widget, val)
        self._update_color_previews()

    def _save_values(self):
        for field in getattr(self.module_meta, "config_schema", []):
            widget = self.field_widgets.get(field.param_name)
            if widget is None: continue
            cfg_item = getattr(config, field.param_name, None)
            if cfg_item is not None:
                raw_value = self._get_widget_value(field, widget)
                typed_value = self._coerce_value_for_config(field, raw_value)
                config.set(cfg_item, typed_value)
















