import logging
from app.infrastructure.config.app_config import is_non_chinese_ui_language

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

