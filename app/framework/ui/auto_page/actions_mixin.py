from __future__ import annotations

import inspect
import logging
from typing import Any

from PySide6.QtWidgets import QWidget
from qfluentwidgets import PrimaryPushButton, PushButton

from app.framework.core.module_system.models import SchemaField
from app.framework.i18n import _
from app.framework.infra.config.app_config import config


class AutoPageActionsMixin:
    """Action button rendering and invocation behavior shared by auto pages."""

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

        if not self._should_show_actions():
            self.actions_bar.setVisible(False)
            return

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

    def _append_action_log(self, message: str) -> None:
        browser = getattr(self, "textBrowser_log", None)
        if browser is not None:
            browser.append(message)

    def _resolve_action_host_widget(self) -> QWidget:
        """Resolve action host to page-level container instead of inner AutoPage column."""
        cursor: QWidget | None = self if isinstance(self, QWidget) else None
        while cursor is not None:
            class_name = type(cursor).__name__
            if class_name in {"PeriodicTasksPage", "OnDemandTasksPage"}:
                return cursor
            if hasattr(cursor, "task_coordinator") and hasattr(cursor, "ui"):
                return cursor
            cursor = cursor.parentWidget()

        window = self.window() if isinstance(self, QWidget) else None
        if isinstance(window, QWidget):
            return window
        return self.parent() if isinstance(self.parent(), QWidget) else self

    def _invoke_action(self, method_name: str, button: PushButton | None = None) -> None:
        module_class = getattr(self.module_meta, "module_class", None)
        if module_class is None:
            self._append_action_log(f"Action '{method_name}' unavailable: no module class")
            return

        try:
            raw_callable = getattr(module_class, method_name)
        except Exception:
            self._append_action_log(f"Action '{method_name}' not found on module class")
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
            "host": self._resolve_action_host_widget(),
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
                self._append_action_log(result)
            self._load_values()
        except Exception as exc:
            logging.getLogger(__name__).exception("AutoPage action failed: %s", method_name)
            self._append_action_log(str(_("Action failed: {error}", msgid="action_failed_error", error=str(exc))))
