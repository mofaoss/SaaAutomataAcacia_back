# coding: utf-8
import datetime
import os.path
import re
import sys
import threading
import time
from pathlib import Path
from PyQt5.QtCore import QSize, QTimer, QThread, Qt
from PyQt5.QtGui import QIcon, QImage, QPixmap, QMovie
from PyQt5.QtWidgets import QApplication, QFrame, QLabel
from qfluentwidgets import FluentIcon as FIF, SystemThemeListener, isDarkTheme, MessageBox
from qfluentwidgets import NavigationItemPosition, MSFluentWindow, NavigationBarPushButton, FlyoutView, \
    Flyout, setThemeColor

from ..common.config import config
from ..common.config import is_non_chinese_ui_language, is_traditional_ui_language
from ..common.icon import Icon
from ..common.logger import logger
from ..common.matcher import matcher
from ..common.signal_bus import signalBus
from ..common.utils import get_gitee_text, get_local_version, get_cloudflare_data, launch_game_with_guard
from ..repackage.custom_message_box import CustomMessageBox
from ..common import resource  # don't delete


class InstallOcr(QThread):

    def __init__(self, ocr_installer, parent=None):
        super().__init__()
        self.ocr_installer = ocr_installer
        self.parent = parent

    def run(self):
        self.ocr_installer.install_ocr()


class MainWindow(MSFluentWindow):

    SPLASH_ICON_SIZE = QSize(150, 150)
    SPLASH_MOVIE_SIZE = QSize(160, 160)
    SPLASH_PREFERRED_MIN_MS = 1200

    def __init__(self):
        super().__init__()
        self.splashMovie = None
        self.splashMovieLabel = None
        self.splashMovieFallbackTimer = None
        self._splashFrameRendered = False
        self.splashShownAt = None
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.updater = None
        self.message_window = None

        self.themeListener = SystemThemeListener(self)

        self.displayInterface = None
        self.homeInterface = None
        self.additionalInterface = None
        self.triggerInterface = None
        self.helpInterface = None
        self.tableInterface = None
        self.settingInterface = None
        self.support_button = None
        self.ocr_module = None
        self.numpy_module = None
        self.cv2_module = None
        self._deferred_init_tasks = []
        self._deferred_initialized = False
        self._startup_target_index = int(config.enter_interface.value)
        self._nav_registered = {
            'display': False,
            'home': False,
            'additional': False,
            'trigger': False,
            'table': False,
            'help': False,
            'setting': False,
        }

        self.initWindow()
        self._init_tasks = self._build_initial_init_tasks() + [
            self._create_support_button,
            self.connectSignalToSlot,
            self.initNavigation,
            self._finalize_startup,
        ]
        QTimer.singleShot(0, self._run_next_init_task)

    def _to_traditional_if_needed(self, text):
        if not isinstance(text, str) or not is_traditional_ui_language():
            return text
        try:
            from ..common.ui_localizer import _to_traditional
            return _to_traditional(text)
        except Exception:
            return text

    def _localize_widget_if_needed(self, widget):
        if widget is None or not is_traditional_ui_language():
            return
        try:
            from ..common.ui_localizer import localize_widget_tree_for_traditional
            localize_widget_tree_for_traditional(widget)
        except Exception:
            pass

    def _build_initial_init_tasks(self):
        task_map = {
            0: self._create_display_interface,
            1: self._create_home_interface,
            2: self._create_additional_interface,
        }

        ordered = [task_map.get(self._startup_target_index, self._create_display_interface)]

        if config.auto_start_task.value:
            ordered.append(self._create_home_interface)

        unique = []
        seen = set()
        for task in ordered:
            name = task.__name__
            if name in seen:
                continue
            seen.add(name)
            unique.append(task)

        return unique

    def _create_display_interface(self):
        from ..ui.display_interface import DisplayInterface
        self.displayInterface = DisplayInterface(self)
        self._localize_widget_if_needed(self.displayInterface)

    def _create_home_interface(self):
        from .home import Home
        self.homeInterface = Home('Home Interface', self)
        self._localize_widget_if_needed(self.homeInterface)

    def _create_additional_interface(self):
        from .additional_features import Additional
        self.additionalInterface = Additional('Additional Interface', self)
        self._localize_widget_if_needed(self.additionalInterface)

    def _create_trigger_interface(self):
        from .trigger import Trigger
        self.triggerInterface = Trigger('Trigger Interface', self)
        self._localize_widget_if_needed(self.triggerInterface)

    def _create_help_interface(self):
        from .help import Help
        self.helpInterface = Help('Help Interface', self)
        self._localize_widget_if_needed(self.helpInterface)

    def _create_table_interface(self):
        from .ocr_replacement_table import OcrReplacementTable
        self.tableInterface = OcrReplacementTable('Table Interface', self)
        self._localize_widget_if_needed(self.tableInterface)

    def _create_setting_interface(self):
        from .setting_interface import SettingInterface
        self.settingInterface = SettingInterface(self)
        self._localize_widget_if_needed(self.settingInterface)

    def _create_support_button(self):
        self.support_button = NavigationBarPushButton(
            FIF.HEART,
            self._to_traditional_if_needed(self._ui_text('赞赏', 'Support')),
            isSelectable=False
        )

    def _run_next_init_task(self):
        if not self._init_tasks:
            return

        task = self._init_tasks.pop(0)
        task()
        QApplication.processEvents()
        QTimer.singleShot(0, self._run_next_init_task)

    def _run_next_deferred_init_task(self):
        if not self._deferred_init_tasks:
            self._deferred_initialized = True
            return

        task = self._deferred_init_tasks.pop(0)
        task()
        QApplication.processEvents()
        QTimer.singleShot(0, self._run_next_deferred_init_task)

    def _defer_load_remaining_interfaces(self):
        self._deferred_init_tasks = [
            self._create_display_and_add_nav,
            self._create_home_and_add_nav,
            self._create_additional_and_add_nav,
            self._create_trigger_and_add_nav,
            self._create_table_and_add_nav,
            self._create_help_and_add_nav,
            self._create_setting_and_add_nav,
        ]
        QTimer.singleShot(0, self._run_next_deferred_init_task)

    def _register_nav_item(self, key, interface, *args, **kwargs):
        if interface is None or self._nav_registered.get(key, False):
            return
        transformed_args = tuple(self._to_traditional_if_needed(arg) if isinstance(arg, str) else arg for arg in args)
        self.addSubInterface(interface, *transformed_args, **kwargs)
        self._nav_registered[key] = True

    def _create_display_and_add_nav(self):
        if self.displayInterface is None:
            self._create_display_interface()
        self._register_nav_item('display', self.displayInterface, FIF.PHOTO, self._ui_text('展示页', 'Display'))

    def _create_home_and_add_nav(self):
        if self.homeInterface is None:
            self._create_home_interface()
        self._register_nav_item('home', self.homeInterface, FIF.HOME, self._ui_text('主页', 'Home'), FIF.HOME_FILL)

    def _create_additional_and_add_nav(self):
        if self.additionalInterface is None:
            self._create_additional_interface()
        self._register_nav_item('additional', self.additionalInterface, FIF.APPLICATION, self._ui_text('小工具', 'Tools'))

    def _create_trigger_and_add_nav(self):
        if self.triggerInterface is None:
            self._create_trigger_interface()
        self._register_nav_item('trigger', self.triggerInterface, FIF.COMPLETED, self._ui_text('触发器', 'Trigger'))

    def _create_table_and_add_nav(self):
        if self.tableInterface is None:
            self._create_table_interface()
        self._register_nav_item('table', self.tableInterface, FIF.SYNC, self._ui_text('替换表', 'Replacement'))

    def _create_help_and_add_nav(self):
        if self.helpInterface is None:
            self._create_help_interface()
        self._register_nav_item(
            'help',
            self.helpInterface,
            FIF.HELP,
            self._ui_text('帮助', 'Help'),
            position=NavigationItemPosition.BOTTOM,
        )

    def _create_setting_and_add_nav(self):
        if self.settingInterface is None:
            self._create_setting_interface()
        self._register_nav_item(
            'setting',
            self.settingInterface,
            Icon.SETTINGS,
            self.tr('Settings'),
            Icon.SETTINGS_FILLED,
            NavigationItemPosition.BOTTOM,
        )

    def _finalize_startup(self):
        self.themeListener.start()

        ocr_thread = threading.Thread(target=self.init_ocr)
        ocr_thread.daemon = True
        ocr_thread.start()

        if config.auto_start_task.value or '--auto' in sys.argv:
            if self.homeInterface is None:
                self._create_home_and_add_nav()

            if self.homeInterface.CheckBox_open_game_directly.isChecked():
                if config.LineEdit_game_directory.value == './':
                    logger.warn(f"未配置游戏路径，请先根据教程配置路径")
                else:
                    logger.info(f"开始自动运行日常")
                    self.homeInterface.on_start_button_click()
            else:
                logger.warn(f'未勾选"自动打开游戏"')

        self._finish_splash_screen()
        self._defer_load_remaining_interfaces()

    def open_game_directly(self):
        """直接启动游戏（兼容 Steam/Epic 与国服等不同目录结构）"""
        try:
            result = launch_game_with_guard(logger=logger)
            if not result.get("ok"):
                logger.error(result.get("error", "启动游戏失败"))

        except Exception as e:
            logger.error(f"出现报错: {e}")

    def connectSignalToSlot(self):
        signalBus.micaEnableChanged.connect(self.setMicaEffectEnabled)
        signalBus.switchToSampleCard.connect(self.switchToSample)
        signalBus.showMessageBox.connect(self.showMessageBox)
        signalBus.showScreenshot.connect(self.showScreenshot)
        # signalBus.check_ocr_progress.connect(self.update_ring)

    def initNavigation(self):
        # self.navigationInterface.setAcrylicEnabled(True)

        # TODO: add navigation items
        startup_top_interface = None
        if self._startup_target_index == 2 and self.additionalInterface is not None:
            startup_top_interface = (self.additionalInterface, FIF.APPLICATION, self._ui_text('小工具', 'Tools'))
        elif self._startup_target_index == 1 and self.homeInterface is not None:
            startup_top_interface = (self.homeInterface, FIF.HOME, self._ui_text('主页', 'Home'), FIF.HOME_FILL)
        elif self.displayInterface is not None:
            startup_top_interface = (self.displayInterface, FIF.PHOTO, self._ui_text('展示页', 'Display'))
        elif self.homeInterface is not None:
            startup_top_interface = (self.homeInterface, FIF.HOME, self._ui_text('主页', 'Home'), FIF.HOME_FILL)
        elif self.additionalInterface is not None:
            startup_top_interface = (self.additionalInterface, FIF.APPLICATION, self._ui_text('小工具', 'Tools'))

        if startup_top_interface is not None:
            key = 'display'
            if self._startup_target_index == 2:
                key = 'additional'
            elif self._startup_target_index == 1:
                key = 'home'
            self._register_nav_item(key, startup_top_interface[0], *startup_top_interface[1:])

        # add custom widget to bottom
        self.navigationInterface.addWidget(
            'avatar',
            self.support_button,
            self.onSupport,
            NavigationItemPosition.BOTTOM
        )
        if self._startup_target_index == 2 and self.additionalInterface is not None:
            self.stackedWidget.setCurrentWidget(self.additionalInterface, False)
        elif self._startup_target_index == 1 and self.homeInterface is not None:
            self.stackedWidget.setCurrentWidget(self.homeInterface, False)
        elif self.displayInterface is not None:
            self.stackedWidget.setCurrentWidget(self.displayInterface, False)

    def init_ocr(self):
        from ..modules.ocr import ocr
        self.ocr_module = ocr

        def benchmark(ocr_func, img, runs=30):
            # 预热
            for _ in range(10):
                ocr_func(img, is_log=False)

            # 正式测试
            start = time.time()
            for _ in range(runs):
                ocr_func(img, is_log=False)
            return (time.time() - start) / runs

        ocr.instance_ocr()
        # logger.info(f"区域截图识别每次平均耗时：{benchmark(ocr.run, 'app/resource/images/start_game/age.png')}")

    def initWindow(self):
        self.resize(960, 860)
        self.setMinimumWidth(760)
        base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
        head_icon_path = base_dir / 'app/resource/images/logo.png'
        self.setWindowIcon(QIcon(str(head_icon_path)))
        self.setWindowTitle(self._ui_text('安卡希雅·自律姬', 'SaaAutomataAcacia'))

        setThemeColor("#009FAA")

        # 触发重绘，使一开始的背景颜色正确
        # self.setCustomBackgroundColor(QColor(240, 244, 249), QColor(32, 32, 32))
        # self.setBackgroundColor(QColor(240, 244, 249))
        self.setMicaEffectEnabled(config.get(config.micaEnabled))

        position = config.position.value
        if position:
            self.move(position[0], position[1])
            self.show()
        else:
            desktop = QApplication.primaryScreen().availableGeometry()
            w, h = desktop.width(), desktop.height()
            self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
            self.show()
        QApplication.processEvents()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen') and self.splashMovieLabel is not None:
            self.splashScreen.resize(self.size())
            self.splashMovieLabel.resize(self.splashScreen.size())

    def _setup_splash_animation(self):
        if not self._start_splash_movie_from_source(':/app/resource/images/logo_loading.gif'):
            if not self._start_splash_movie_from_source(':/app/resource/images/loading.gif'):
                base_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
                file_candidates = [
                    base_dir / 'app/resource/images/logo_loading.gif',
                    base_dir / 'app/resource/images/loading.gif',
                    Path('app/resource/images/logo_loading.gif'),
                    Path('app/resource/images/loading.gif'),
                ]

                gif_path = next((str(path) for path in file_candidates if path.exists()), None)
                if not gif_path:
                    return

                self._start_splash_movie_from_source(gif_path)

    def _start_splash_movie_from_source(self, source: str) -> bool:
        movie = QMovie(source)
        if not movie.isValid():
            return False
        movie.setCacheMode(QMovie.CacheNone)
        movie.setScaledSize(self.SPLASH_MOVIE_SIZE)

        self.splashMovie = movie
        self._splashFrameRendered = False

        self.splashScreen.setIconSize(QSize(0, 0))
        self.splashScreen.iconWidget.hide()
        self.splashMovieLabel = QLabel(self.splashScreen)
        self.splashMovieLabel.setAlignment(Qt.AlignCenter)
        self.splashMovieLabel.resize(self.splashScreen.size())
        self.splashMovieLabel.setMinimumSize(self.SPLASH_MOVIE_SIZE)
        self.splashMovieLabel.setMovie(self.splashMovie)

        self.splashMovie.frameChanged.connect(self._on_splash_movie_frame_changed)
        self.splashMovie.error.connect(self._on_splash_movie_error)

        self.splashMovieFallbackTimer = QTimer(self)
        self.splashMovieFallbackTimer.setSingleShot(True)
        self.splashMovieFallbackTimer.timeout.connect(self._on_splash_movie_timeout)

        self.splashMovie.start()
        self.splashMovieFallbackTimer.start(1200)
        self.splashMovieLabel.raise_()
        self.splashMovieLabel.show()
        logger.info(f'启动动画已启用：{source}')
        return True

    def _on_splash_movie_frame_changed(self, frame_number):
        if frame_number >= 0 and not self._splashFrameRendered:
            self._splashFrameRendered = True
            if self.splashMovieFallbackTimer is not None and self.splashMovieFallbackTimer.isActive():
                self.splashMovieFallbackTimer.stop()

    def _on_splash_movie_error(self, _error):
        self._fallback_to_static_splash('GIF 播放错误')

    def _on_splash_movie_timeout(self):
        if not self._splashFrameRendered:
            self._fallback_to_static_splash('GIF 首帧超时')

    def _fallback_to_static_splash(self, reason: str):
        if self.splashMovieFallbackTimer is not None:
            self.splashMovieFallbackTimer.stop()
            self.splashMovieFallbackTimer.deleteLater()
            self.splashMovieFallbackTimer = None

        if self.splashMovie is not None:
            self.splashMovie.stop()
            self.splashMovie = None

        if self.splashMovieLabel is not None:
            self.splashMovieLabel.hide()
            self.splashMovieLabel.deleteLater()
            self.splashMovieLabel = None

        self._splashFrameRendered = False
        self.splashScreen.iconWidget.show()
        self.splashScreen.setIconSize(self.SPLASH_ICON_SIZE)
        logger.warn(f'启动动画不可用，已回退静态 logo：{reason}')

    def _finish_splash_screen(self):
        if self.splashMovie is not None and self.splashShownAt is not None:
            elapsed_ms = int((time.perf_counter() - self.splashShownAt) * 1000)
            remain_ms = self.SPLASH_PREFERRED_MIN_MS - elapsed_ms
            if remain_ms > 0:
                QTimer.singleShot(remain_ms, self._close_splash_screen_now)
                return

        self._close_splash_screen_now()

    def _close_splash_screen_now(self):
        if self.splashMovieFallbackTimer is not None:
            self.splashMovieFallbackTimer.stop()
            self.splashMovieFallbackTimer.deleteLater()
            self.splashMovieFallbackTimer = None

        if self.splashMovie is not None:
            self.splashMovie.stop()
            self.splashMovie = None

        if self.splashMovieLabel is not None:
            self.splashMovieLabel.hide()
            self.splashMovieLabel.deleteLater()
            self.splashMovieLabel = None

        self._splashFrameRendered = False
        self.splashShownAt = None
        if hasattr(self, 'splashScreen'):
            self.splashScreen.finish()

    # def update_ring(self, value, speed):
    #     self.progressRing.setValue(value)
    #     self.speed.setText(speed)

    def yes_click(self):
        self.check_ocr_thread = InstallOcr(self.ocr_installer)
        try:
            # self.content.setVisible(False)
            # self.progressRing.setVisible(True)
            # self.speed.setVisible(True)
            self.check_ocr_thread.start()
        except Exception as e:
            print(e)
            # traceback.print_exc()

    def cancel_click(self):
        self.close()

    def onSupport(self):
        support_image = "asset/support.jpg"
        if self._is_non_chinese_ui or is_traditional_ui_language():
            support_image = "asset/support_kofi.png"
        view = FlyoutView(
            title=self._ui_text("赞助作者", "Support Author"),
            content=self._ui_text("如果这个助手帮助到你，可以考虑赞助作者一杯奶茶(>ω･* )ﾉ",
                                  "If this assistant helps you, consider buying the author a coffee (>ω･* )ﾉ"),
            image=support_image,
            isClosable=True,
        )
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)

        w = Flyout.make(view, self.support_button, self)
        view.closed.connect(w.close)

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else self.tr(zh_text)

    def switchToSample(self, routeKey, index):
        """
        用于跳转到指定页面
        :param routeKey: 跳转路径
        :param index:
        :return:
        """
        interfaces = self.findChildren(QFrame)
        for w in interfaces:
            if w.objectName() == routeKey:
                self.stackedWidget.setCurrentWidget(w, False)
                # w.scrollToCard(index)

    def save_log(self):
        """保存所有log到html中"""

        def is_empty_html(content):
            """
            判断 HTML 内容是否为空
            """
            # 使用正则表达式匹配空的段落 (<p>) 或者换行 (<br />)
            empty_html_pattern = re.compile(r'<p[^>]*>\s*(<br\s*/?>)?\s*</p>', re.IGNORECASE)

            # 去掉默认的头部信息后，检查是否只剩下空的段落
            body_content = re.sub(r'<!DOCTYPE[^>]*>|<html[^>]*>|<head[^>]*>.*?</head>|<body[^>]*>|</body>|</html>', '',
                                  content, flags=re.DOTALL)
            return bool(empty_html_pattern.fullmatch(body_content.strip()))

        def save_html(path, content):
            """保存HTML内容，如果是空内容则跳过"""
            if not content or is_empty_html(content):
                return
            with open(path, "w", encoding='utf-8') as file:
                file.write(content)

        def clean_old_logs(log_dir, max_files=30):
            """清理旧日志文件，保留最多max_files个"""
            if not os.path.exists(log_dir):
                return

            all_logs = [
                f for f in os.listdir(log_dir)
                if f.endswith('.html') and os.path.isfile(os.path.join(log_dir, f))
            ]

            if len(all_logs) <= max_files:
                return

            # 按创建时间排序并删除最旧的文件
            all_logs.sort(key=lambda x: os.path.getctime(os.path.join(log_dir, x)))
            for file_to_remove in all_logs[:len(all_logs) - max_files]:
                os.remove(os.path.join(log_dir, file_to_remove))

        # 日志配置：目录、UI组件、文件名前缀
        log_configs = []
        if self.homeInterface is not None:
            log_configs.append(("./log/home", self.homeInterface.textBrowser_log, "home"))
        if self.additionalInterface is not None:
            log_configs.extend([
                ("./log/fishing", self.additionalInterface.textBrowser_log_fishing, "fishing"),
                ("./log/action", self.additionalInterface.textBrowser_log_action, "action"),
                ("./log/jigsaw", self.additionalInterface.textBrowser_log_jigsaw, "jigsaw"),
                ("./log/water_bomb", self.additionalInterface.textBrowser_log_water_bomb, "water_bomb"),
                ("./log/alien_guardian", self.additionalInterface.textBrowser_log_alien_guardian, "alien_guardian"),
                ("./log/maze", self.additionalInterface.textBrowser_log_maze, "maze"),
                ("./log/massaging", self.additionalInterface.textBrowser_log_massaging, "massaging"),
                ("./log/drink", self.additionalInterface.textBrowser_log_drink, "drink"),
            ])

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for log_dir, text_browser, prefix in log_configs:
            # 确保日志目录存在
            os.makedirs(log_dir, exist_ok=True)

            # 清理旧日志
            clean_old_logs(log_dir)

            # 获取并保存日志内容
            log_content = text_browser.toHtml()
            filename = f"{prefix}_{timestamp}.html"
            save_html(os.path.join(log_dir, filename), log_content)

    def save_position(self):
        # 获取当前窗口的位置和大小
        geometry = self.geometry()
        position = (geometry.left(), geometry.top())
        config.set(config.position, position)

    def closeEvent(self, a0):
        if self.ocr_module is not None:
            self.ocr_module.stop_ocr()
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        try:
            # 保存日志到文件
            self.save_log()
            self.save_position()
            # 保存缩放数据
            if config.saveScaleCache.value:
                matcher.save_scale_cache()
        except Exception as e:
            logger.error(e)
            # traceback.print_exc()
        super().closeEvent(a0)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()

        # retry
        if self.isMicaEffectEnabled():
            QTimer.singleShot(100, lambda: self.windowEffect.setMicaEffect(self.winId(), isDarkTheme()))

    def showMessageBox(self, title, content):
        massage = MessageBox(title, content, self)
        if massage.exec():
            if self.settingInterface is None:
                self._create_setting_and_add_nav()
            w = self.settingInterface
            self.stackedWidget.setCurrentWidget(w, False)
            w.scrollToAboutCard()
            if self.updater:
                self.settingInterface.start_download(self.updater)
        else:
            pass

    def showScreenshot(self, screenshot):
        """
        展示当前截图
        :param screenshot:
        :return:
        """
        def ndarray_to_qpixmap(ndarray):
            if self.numpy_module is None:
                import numpy as np
                self.numpy_module = np
            if self.cv2_module is None:
                import cv2
                self.cv2_module = cv2

            np = self.numpy_module
            cv2 = self.cv2_module

            # 确保ndarray是3维的 (height, width, channels)
            if ndarray.ndim == 2:
                ndarray = np.expand_dims(ndarray, axis=-1)
                ndarray = np.repeat(ndarray, 3, axis=-1)

            height, width, channel = ndarray.shape
            bytes_per_line = 3 * width
            # 显示需要rgb格式
            ndarray = cv2.cvtColor(ndarray, cv2.COLOR_BGR2RGB)

            # 将ndarray转换为QImage
            qimage = QImage(ndarray.data, width, height, bytes_per_line, QImage.Format_RGB888)

            # 将QImage转换为QPixmap
            return QPixmap.fromImage(qimage)

        def save_screenshot(ndarray):
            if self.cv2_module is None:
                import cv2
                self.cv2_module = cv2

            # 检查 temp 目录是否存在，如果不存在则创建
            if not os.path.exists('temp'):
                os.makedirs('temp')
            # cv2保存是bgr格式
            self.cv2_module.imwrite(f'temp/{time.time()}.png', ndarray)

        save_screenshot(screenshot)

        if not isinstance(self.message_window, CustomMessageBox):
            self.message_window = CustomMessageBox(self, '当前截图', 'image')
        screenshot_pixmap = ndarray_to_qpixmap(screenshot)
        # 按比例缩放图像
        scaled_pixmap = screenshot_pixmap.scaled(
            200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.message_window.content.setPixmap(scaled_pixmap)
        if self.message_window.exec():
            pass
        else:
            pass
