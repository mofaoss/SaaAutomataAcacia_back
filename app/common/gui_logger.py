import sys
import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QTextBrowser

class HtmlFormatter(logging.Formatter):
    """
    将 logging 的输出转换为适合控件显示的 HTML 格式，根据级别赋予颜色。
    """
    formats = {
        logging.DEBUG: "gray",
        logging.INFO: "green",
        logging.WARNING: "orange",
        logging.ERROR: "red",
        logging.CRITICAL: "purple"
    }

    def __init__(self, fmt="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"):
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        color = self.formats.get(record.levelno, "black")
        message = super().format(record)
        return f'<span style="color: {color};">{message}</span><br/>'


class SignaledStream(QObject):
    """
    自定义输出流，拦截 sys.stdout 和 sys.stderr，并转换为 Qt 信号。
    """
    textWritten = Signal(str)

    def __init__(self, original_stream):
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


class LogMessageHandler(logging.Handler):
    """
    Python logging 模块的 Handler，将日志格式化为 HTML 并写入我们的自定义流。
    """
    def __init__(self, text_stream: SignaledStream):
        super().__init__()
        self.text_stream = text_stream
        self.setFormatter(HtmlFormatter())

    def emit(self, record):
        msg = self.format(record)
        self.text_stream.write(msg)


class GuiLogRouter(QObject):
    """
    全局的 GUI 日志路由器，负责管理标准输出的重定向和 UI 更新。
    """
    def __init__(self):
        super().__init__()
        self._active_widget: Optional[QTextBrowser] = None

        # 1. 拦截标准输出和错误输出（捕获 print 和报错）
        self._stdout_stream = SignaledStream(sys.stdout)
        self._stderr_stream = SignaledStream(sys.stderr)

        # 2. 使用 QueuedConnection 确保跨线程调用时，UI 更新始终在主线程执行
        self._stdout_stream.textWritten.connect(self._append_to_active_widget, Qt.ConnectionType.QueuedConnection)
        self._stderr_stream.textWritten.connect(self._append_to_active_widget, Qt.ConnectionType.QueuedConnection)

        self._install()

    def _install(self):
        # 重定向系统输出
        sys.stdout = self._stdout_stream
        sys.stderr = self._stderr_stream

        # 配置 Python 标准 logger
        handler = LogMessageHandler(self._stdout_stream)
        logger = logging.getLogger()

        # 防止重复添加 Handler
        if not any(isinstance(h, LogMessageHandler) for h in logger.handlers):
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # 屏蔽一些第三方库的啰嗦日志
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)

    def bind_widget(self, log_widget: QTextBrowser):
        """绑定接收日志的 QTextBrowser 控件"""
        self._active_widget = log_widget
        if hasattr(log_widget, "setOpenExternalLinks"):
            log_widget.setOpenExternalLinks(True)

    @Slot(str)
    def _append_to_active_widget(self, text):
        """将文本插入到控件中（仅在主线程触发）"""
        if not text or self._active_widget is None:
            return

        message = str(text)
        try:
            # 区分是普通的 print (纯文本) 还是 logger 格式化出来的 HTML
            if "<span style=" in message or "<br" in message:
                self._active_widget.insertHtml(message)
            else:
                self._active_widget.insertPlainText(message)
            self._active_widget.ensureCursorVisible()
        except Exception:
            pass

# --- 全局单例模式 ---
_gui_log_router: Optional[GuiLogRouter] = None

def get_gui_log_router() -> GuiLogRouter:
    global _gui_log_router
    if _gui_log_router is None:
        _gui_log_router = GuiLogRouter()
    return _gui_log_router

def bind_log_widget(log_widget: QTextBrowser):
    """暴露给外部调用的快捷绑定方法"""
    get_gui_log_router().bind_widget(log_widget)
