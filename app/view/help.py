import os

from PyQt5.QtWidgets import QFrame

from app.common.config import is_non_chinese_ui_language
from app.common.style_sheet import StyleSheet
from app.ui.help_interface import Ui_help


class Help(QFrame, Ui_help):
    def __init__(self, text: str, parent=None):
        super().__init__()
        self._is_non_chinese_ui = is_non_chinese_ui_language()

        self.setupUi(self)
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self._initWidget()
        self._connect_to_slot()

    def _initWidget(self):
        self.load_markdown()
        StyleSheet.HELP_INTERFACE.apply(self)

    def _connect_to_slot(self):
        pass

    def load_markdown(self):
        markdown_path = './docs/help_en.md' if self._is_non_chinese_ui else './docs/help.md'
        if not os.path.exists(markdown_path):
            markdown_path = './docs/help.md'
        with open(markdown_path, 'r', encoding='utf-8') as file:
            text = file.read()
            self.TextEdit_markdown.setMarkdown(text)
