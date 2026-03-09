import logging
from PySide6.QtCore import QObject, Signal, Slot, Qt
from PySide6.QtWidgets import QTextBrowser

class HtmlFormatter(logging.Formatter):
    """将 logging 的输出转换为适合控件显示的 HTML 格式，根据级别赋予颜色"""
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

class LogSignal(QObject):
    """用于跨线程传递日志文本的信号对象"""
    textWritten = Signal(str)

class UITextBrowserHandler(logging.Handler):
    """专门向 QTextBrowser 投递 HTML 日志的 Handler，彻底跨线程安全"""
    def __init__(self, text_browser: QTextBrowser):
        super().__init__()
        self.text_browser = text_browser
        self.signals = LogSignal()
        self.setFormatter(HtmlFormatter())
        # 使用 QueuedConnection 确保即使在后台线程写日志，UI更新也是在主线程
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
    """
    【工厂方法】创建一个绑定到指定 UI 控件的独立 Logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # 关键：切断向上传播，防止日志在控制台/其他地方重复打印
    logger.propagate = False

    # 清理可能存在的旧 UITextBrowserHandler，防止热重载时重复绑定
    logger.handlers = [h for h in logger.handlers if not isinstance(h, UITextBrowserHandler)]

    if text_browser is not None:
        # 如果需要打开超链接，顺手开启配置
        if hasattr(text_browser, "setOpenExternalLinks"):
            text_browser.setOpenExternalLinks(True)

        handler = UITextBrowserHandler(text_browser)
        logger.addHandler(handler)

    return logger