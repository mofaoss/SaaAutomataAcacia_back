import re
import importlib
from functools import lru_cache

from PySide6.QtWidgets import QWidget, QComboBox, QTabWidget
from qfluentwidgets import InfoBar

from app.infrastructure.config.app_config import is_traditional_ui_language

_CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def _contains_chinese(text):
    return isinstance(text, str) and bool(_CHINESE_RE.search(text))


@lru_cache(maxsize=1)
def _build_s2t_converter():
    try:
        OpenCC = importlib.import_module("opencc").OpenCC
        return OpenCC("s2t")
    except Exception:
        return None


def _to_traditional(text):
    if not _contains_chinese(text):
        return text

    converter = _build_s2t_converter()
    if converter is not None:
        try:
            return converter.convert(text)
        except Exception:
            return text

    return text


def _safe_transform_text(widget):
    if hasattr(widget, "text") and callable(widget.text) and hasattr(widget, "setText") and callable(widget.setText):
        text = widget.text()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setText(transformed)

    if hasattr(widget, "windowTitle") and callable(widget.windowTitle) and hasattr(widget, "setWindowTitle"):
        text = widget.windowTitle()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setWindowTitle(transformed)

    if hasattr(widget, "toolTip") and callable(widget.toolTip) and hasattr(widget, "setToolTip"):
        text = widget.toolTip()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setToolTip(transformed)

    if hasattr(widget, "statusTip") and callable(widget.statusTip) and hasattr(widget, "setStatusTip"):
        text = widget.statusTip()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setStatusTip(transformed)

    if hasattr(widget, "whatsThis") and callable(widget.whatsThis) and hasattr(widget, "setWhatsThis"):
        text = widget.whatsThis()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setWhatsThis(transformed)

    if hasattr(widget, "placeholderText") and callable(widget.placeholderText) and hasattr(widget, "setPlaceholderText"):
        text = widget.placeholderText()
        transformed = _to_traditional(text)
        if transformed != text:
            widget.setPlaceholderText(transformed)

    if isinstance(widget, QComboBox):
        for index in range(widget.count()):
            text = widget.itemText(index)
            transformed = _to_traditional(text)
            if transformed != text:
                widget.setItemText(index, transformed)

    if isinstance(widget, QTabWidget):
        for index in range(widget.count()):
            text = widget.tabText(index)
            transformed = _to_traditional(text)
            if transformed != text:
                widget.setTabText(index, transformed)


def patch_infobar_for_traditional():
    if not is_traditional_ui_language():
        return
    if getattr(InfoBar, "_tc_patch_installed", False):
        return

    def _wrap(method_name):
        original = getattr(InfoBar, method_name)

        def wrapper(*args, **kwargs):
            args = list(args)
            if len(args) > 0 and isinstance(args[0], str):
                args[0] = _to_traditional(args[0])
            if len(args) > 1 and isinstance(args[1], str):
                args[1] = _to_traditional(args[1])

            if "title" in kwargs and isinstance(kwargs["title"], str):
                kwargs["title"] = _to_traditional(kwargs["title"])
            if "content" in kwargs and isinstance(kwargs["content"], str):
                kwargs["content"] = _to_traditional(kwargs["content"])

            return original(*args, **kwargs)

        return wrapper

    InfoBar.success = _wrap("success")
    InfoBar.error = _wrap("error")
    InfoBar.warning = _wrap("warning")
    InfoBar.info = _wrap("info")
    InfoBar._tc_patch_installed = True


def localize_widget_tree_for_traditional(root: QWidget):
    if not is_traditional_ui_language() or root is None:
        return

    _safe_transform_text(root)
    for child in root.findChildren(QWidget):
        _safe_transform_text(child)

