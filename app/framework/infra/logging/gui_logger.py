import logging
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QTextBrowser

from app.framework.i18n.runtime import render_message


class HtmlFormatter(logging.Formatter):
    """Convert logging output to HTML and apply per-level i18n rendering policy."""

    formats = {
        logging.DEBUG: "gray",
        logging.INFO: "green",
        logging.WARNING: "orange",
        logging.ERROR: "red",
        logging.CRITICAL: "purple",
    }

    def __init__(self, fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        color = self.formats.get(record.levelno, "black")
        rendered = render_message(record.msg, context="log", levelno=record.levelno)
        cloned = logging.makeLogRecord(record.__dict__.copy())
        cloned.msg = rendered
        cloned.args = ()
        message = super().format(cloned)
        return f'<span style="color: {color};">{message}</span><br/>'


class LogSignal(QObject):
    """Signal object used to pass HTML logs across threads."""

    textWritten = Signal(str)


class UITextBrowserHandler(logging.Handler):
    """Thread-safe handler that writes HTML logs into QTextBrowser."""

    def __init__(self, text_browser: QTextBrowser):
        super().__init__()
        self.text_browser = text_browser
        self.signals = LogSignal()
        self.setFormatter(HtmlFormatter())
        self.signals.textWritten.connect(self._append_to_widget, Qt.ConnectionType.QueuedConnection)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signals.textWritten.emit(msg)
        except Exception:
            self.handleError(record)

    @Slot(str)
    def _append_to_widget(self, text):
        if self.text_browser is None:
            return
        try:
            self.text_browser.insertHtml(text)
            self.text_browser.ensureCursorVisible()
        except Exception:
            pass


def setup_ui_logger(name: str, text_browser: QTextBrowser) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    logger.handlers = [h for h in logger.handlers if not isinstance(h, UITextBrowserHandler)]

    if text_browser is not None:
        if hasattr(text_browser, "setOpenExternalLinks"):
            text_browser.setOpenExternalLinks(True)

        handler = UITextBrowserHandler(text_browser)
        logger.addHandler(handler)

    return logger
