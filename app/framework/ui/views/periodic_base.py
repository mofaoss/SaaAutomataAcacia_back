import logging

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

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
