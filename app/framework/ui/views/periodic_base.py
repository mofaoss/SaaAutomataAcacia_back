import logging
import re

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from app.framework.application.modules.name_resolver import (
    resolve_state_display_name,
    resolve_task_display_name,
)
from app.framework.infra.config.app_config import is_non_chinese_ui_language


class BaseInterface:
    _ui_text_use_qt_tr = False

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.auto = None
        self._is_non_chinese_ui = is_non_chinese_ui_language()

    def toggle_button(self, running):
        pass

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        if getattr(self, "_is_non_chinese_ui", False):
            return en_text

        if getattr(self, "_ui_text_use_qt_tr", False):
            translate = getattr(self, "tr", None)
            if callable(translate):
                return translate(zh_text)

        return zh_text

    @staticmethod
    def _task_display_name(meta: dict, task_id: str) -> str:
        return resolve_task_display_name(meta, task_id)

    @staticmethod
    def _state_display_name(task_name: str, task_name_msgid: str, source: str = "") -> str:
        return resolve_state_display_name(task_name, task_name_msgid, source=source)

    def load_config(self):
        """Load configuration into UI elements. Override in subclass."""
        pass

    def apply_i18n(self):
        """Apply internationalization to UI elements. Override in subclass."""
        pass


class ModulePageBase(QWidget, BaseInterface):
    def __init__(
        self,
        object_name: str | None = None,
        parent=None,
        *,
        host_context: str | None = None,
        use_default_layout: bool = False,
    ):
        # Backward-compatible call style: super().__init__(parent)
        if object_name is not None and not isinstance(object_name, str):
            parent = object_name
            object_name = None

        QWidget.__init__(self, parent)
        BaseInterface.__init__(self)

        if object_name:
            self.setObjectName(object_name)

        self.main_layout: QVBoxLayout | None = None
        if use_default_layout:
            self.ensure_main_layout()

        resolved_context = host_context or ("periodic" if use_default_layout else "on_demand")
        self.bind_host_context(resolved_context)

    def bind_host_context(self, host_context):
        context_value = getattr(host_context, "value", host_context)
        if not context_value:
            return

        context_value = str(context_value)
        self.setProperty("hostContext", context_value)

        if context_value == "periodic":
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.setMinimumWidth(320)
        elif context_value == "on_demand":
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.setMinimumWidth(0)

        self.updateGeometry()

    def ensure_main_layout(self):
        if self.main_layout is None:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(8)
        return self.main_layout

    def finalize(self):
        self.ensure_main_layout().addStretch(1)

    def apply_declared_field_texts(self, module_id: str) -> None:
        module_key = str(module_id or "").strip()
        if not module_key:
            return

        try:
            from app.framework.core.module_system.registry import get_module
            from app.framework.i18n import tr
        except Exception:
            return

        meta = get_module(module_key)
        if meta is None:
            return

        owner_module = ""
        module_path = str(getattr(self.__class__, "__module__", "") or "")
        owner_match = re.search(r"app\.features\.modules\.([a-z0-9_]+)(?:\.|$)", module_path)
        if owner_match:
            owner_module = owner_match.group(1)

        for field in list(getattr(meta, "config_schema", []) or []):
            param_name = str(getattr(field, "param_name", "") or "").strip()
            if not param_name:
                continue
            widget = self.findChild(QWidget, param_name)
            if widget is None or not hasattr(widget, "setText"):
                continue

            field_id = str(getattr(field, "field_id", "") or param_name).strip() or param_name
            fallback = str(getattr(field, "label_default", "") or param_name).strip() or param_name

            candidate_keys: list[str] = []
            if owner_module:
                candidate_keys.extend(
                    [
                        f"module.{owner_module}.field.{param_name}.label",
                        f"module.{owner_module}.field.{field_id}.label",
                    ]
                )
            candidate_keys.extend(
                [
                    f"module.{module_key}.field.{param_name}.label",
                    f"module.{module_key}.field.{field_id}.label",
                ]
            )

            label_key = str(getattr(field, "label_key", "") or "").strip()
            if label_key:
                candidate_keys.append(label_key)

            text = fallback
            seen: set[str] = set()
            for key in candidate_keys:
                key = str(key or "").strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                localized = tr(key, fallback=key)
                if localized != key:
                    text = localized
                    break

            try:
                widget.setText(text)
            except Exception:
                continue


class PeriodicPageBase(ModulePageBase):
    def __init__(self, object_name: str, parent=None):
        super().__init__(
            object_name=object_name,
            parent=parent,
            host_context="periodic",
            use_default_layout=True,
        )


class OnDemandTaskBase(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            host_context="on_demand",
            use_default_layout=False,
        )
