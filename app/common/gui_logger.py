import sys
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, Qt

import app.common.logger as common_logger


class LogEmitter(QObject):
    textWritten = Signal(str)

    def __init__(self, original_stream=None):
        super().__init__()
        self._original_stream = original_stream

    def write(self, text):
        message = str(text)
        if self._original_stream is not None:
            try:
                self._original_stream.write(message)
            except Exception:
                pass
        self.textWritten.emit(message)

    def flush(self):
        if self._original_stream is not None:
            try:
                self._original_stream.flush()
            except Exception:
                pass


class GuiLogRouter(QObject):
    def __init__(self):
        super().__init__()
        self._active_widget = None
        self._stdout_emitter = LogEmitter(common_logger.original_stdout)
        self._stderr_emitter = LogEmitter(common_logger.original_stderr)

        self._stdout_emitter.textWritten.connect(self._append_to_active_widget, Qt.ConnectionType.QueuedConnection)
        self._stderr_emitter.textWritten.connect(self._append_to_active_widget, Qt.ConnectionType.QueuedConnection)

    def bind_widget(self, log_widget):
        self._active_widget = log_widget
        if hasattr(log_widget, "setOpenExternalLinks"):
            log_widget.setOpenExternalLinks(True)
        self.install()

    def install(self):
        sys.stdout = self._stdout_emitter
        sys.stderr = self._stderr_emitter
        if hasattr(common_logger, "handler") and common_logger.handler is not None:
            common_logger.handler.text_stream = self._stdout_emitter

    @Slot(str)
    def _append_to_active_widget(self, text):
        if not text:
            return
        widget = self._active_widget
        if widget is None:
            return

        message = str(text)
        try:
            if "<span style=" in message or "<br" in message:
                widget.insertHtml(message)
            else:
                widget.insertPlainText(message)
            widget.ensureCursorVisible()
        except Exception:
            pass


_gui_log_router: Optional[GuiLogRouter] = None


def get_gui_log_router() -> GuiLogRouter:
    global _gui_log_router
    if _gui_log_router is None:
        _gui_log_router = GuiLogRouter()
    return _gui_log_router


def bind_log_widget(log_widget):
    get_gui_log_router().bind_widget(log_widget)
