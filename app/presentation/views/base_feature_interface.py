from PySide6.QtWidgets import QWidget
from .base_interface import BaseInterface

class BaseFeatureInterface(QWidget, BaseInterface):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        BaseInterface.__init__(self)

    def load_config(self):
        """Load configuration into UI elements. Override in subclass."""
        pass

    def apply_i18n(self):
        """Apply internationalization to UI elements. Override in subclass."""
        pass
