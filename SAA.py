# coding:utf-8
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTranslator, QSize, QObject, QThread, QTimer, Signal, QPoint, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QMovie, QPixmap, QFont
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from app.framework.infra.config.app_config import config, resolve_configured_locale
from app.framework.infra.runtime.paths import PROJECT_ROOT, ensure_runtime_dirs


LOGO_ASSETS_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "resources" / "logo"


class EarlySplash(QWidget):
    MAX_ANIMATION_SIZE = 220

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.movie = None
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

        self.resize(220, 220)
        self._setup_media()

    @staticmethod
    def _fit_size(size: QSize, max_edge: int) -> QSize:
        if size.width() <= 0 or size.height() <= 0:
            return QSize(max_edge, max_edge)

        if size.width() >= size.height():
            w = max_edge
            h = max(1, int(size.height() * max_edge / size.width()))
        else:
            h = max_edge
            w = max(1, int(size.width() * max_edge / size.height()))
        return QSize(w, h)

    def _setup_media(self):
        gif_candidates = [
            LOGO_ASSETS_DIR / 'logo_loading.gif',
            LOGO_ASSETS_DIR / 'loading.gif',
        ]

        gif_path = next((str(path) for path in gif_candidates if path.exists()), None)
        if gif_path:
            movie = QMovie(gif_path)
            if movie.isValid():
                movie.setCacheMode(QMovie.CacheMode.CacheAll)
                first_frame = movie.currentPixmap()
                if not first_frame.isNull():
                    display_size = self._fit_size(first_frame.size(), self.MAX_ANIMATION_SIZE)
                    movie.setScaledSize(display_size)
                    self.resize(display_size)
                    self.label.setFixedSize(display_size)
                else:
                    fallback_size = QSize(self.MAX_ANIMATION_SIZE, self.MAX_ANIMATION_SIZE)
                    movie.setScaledSize(fallback_size)
                    self.label.setFixedSize(fallback_size)
                self.movie = movie
                self.label.setMovie(self.movie)
                self.movie.start()
                return

        logo_candidates = [
            LOGO_ASSETS_DIR / 'logo.png',
        ]
        logo_path = next((str(path) for path in logo_candidates if path.exists()), None)
        if logo_path:
            pixmap = QPixmap(logo_path)
            display = pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.label.setPixmap(display)
            self.resize(display.size())
            self.label.setFixedSize(display.size())

    def show_centered(self, app: QApplication):
        target_screen = app.primaryScreen()
        position = config.position.value
        if position and len(position) >= 2:
            screen = app.screenAt(QPoint(int(position[0]), int(position[1])))
            if screen is not None:
                target_screen = screen

        screen = target_screen.availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )
        self.show()
        self.raise_()
        app.processEvents()

    def close_with_cleanup(self):
        if self.movie is not None:
            self.movie.stop()
            self.movie = None
        self.close()


class StartupController(QObject):
    def __init__(self, app: QApplication, splash: EarlySplash):
        super().__init__()
        self.app = app
        self.splash = splash
        self.window = None
        self.translator = None
        self.galleryTranslator = None
        self.importWorker = None
        self.app.aboutToQuit.connect(self._cleanup_threads)

        self._tasks = [
            self._install_translators,
            self._patch_localization,
            self._create_main_window,
            self._show_main_window,
            self._finish,
        ]

    def start(self):
        self.importWorker = RuntimeImportWorker()
        self.importWorker.setObjectName("startup_import_worker")
        self.importWorker.ready.connect(self._on_import_ready)
        self.importWorker.failed.connect(self._on_import_failed)
        self.importWorker.start()

    def _run_next_task(self):
        if not self._tasks:
            return

        task = self._tasks.pop(0)
        try:
            task()
        except Exception:
            self.splash.close_with_cleanup()
            raise

        QTimer.singleShot(0, self._run_next_task)

    def _on_import_ready(self, imported: dict):
        self.FluentTranslator = imported['FluentTranslator']
        self.patch_infobar_for_traditional = imported['patch_infobar_for_traditional']
        self.localize_widget_tree_for_traditional = imported['localize_widget_tree_for_traditional']
        from app.framework.ui.views.main_window import MainWindow
        self.MainWindow = MainWindow
        if self.importWorker is not None and not self.importWorker.isRunning():
            self.importWorker.deleteLater()
            self.importWorker = None
        QTimer.singleShot(0, self._run_next_task)

    def _on_import_failed(self, message: str):
        self.splash.close_with_cleanup()
        if self.importWorker is not None and not self.importWorker.isRunning():
            self.importWorker.deleteLater()
            self.importWorker = None
        raise RuntimeError(message)

    def _cleanup_threads(self):
        worker = self.importWorker
        if worker is None:
            return
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(2000)
        worker.deleteLater()
        self.importWorker = None

    def _install_translators(self):
        locale = resolve_configured_locale(config.get(config.language))
        self.translator = self.FluentTranslator(locale)
        self.galleryTranslator = QTranslator()
        self.galleryTranslator.load(locale, "app", ".", ":/resources/i18n")

        self.app.installTranslator(self.translator)
        self.app.installTranslator(self.galleryTranslator)

    def _patch_localization(self):
        self.patch_infobar_for_traditional()

    def _create_main_window(self):
        self.window = self.MainWindow()
        self.localize_widget_tree_for_traditional(self.window)

    def _show_main_window(self):
        self.window.show()

    def _finish(self):
        self.splash.close_with_cleanup()


class RuntimeImportWorker(QThread):
    ready = Signal(dict)
    failed = Signal(str)

    def run(self):
        try:
            if self.isInterruptionRequested():
                return
            from qfluentwidgets import FluentTranslator
            from app.framework.ui.shared.localizer import patch_infobar_for_traditional, localize_widget_tree_for_traditional

            if self.isInterruptionRequested():
                return
            self.ready.emit({
                'FluentTranslator': FluentTranslator,
                'patch_infobar_for_traditional': patch_infobar_for_traditional,
                'localize_widget_tree_for_traditional': localize_widget_tree_for_traditional,
            })
        except Exception as e:
            self.failed.emit(str(e))


def qt_message_handler(mode, context, message):
    if mode == QtMsgType.QtWarningMsg and "Point size <= 0" in message:
        return  # 遇到这句警告，直接丢弃，不打印到控制台
    print(message)


def main():
    qInstallMessageHandler(qt_message_handler)

    if config.get(config.dpiScale) != "Auto":
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_SCALE_FACTOR"] = str(config.get(config.dpiScale))
    else:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    global_font = app.font()
    if global_font.pointSize() <= 0:
        global_font.setPointSize(10)
        app.setFont(global_font)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    # 确保运行时目录存在 (log, temp 等)
    ensure_runtime_dirs()

    early_splash = EarlySplash()
    early_splash.show_centered(app)

    startup = StartupController(app, early_splash)
    startup.start()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
