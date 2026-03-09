# coding: utf-8
import os.path
import re
import sys
import datetime
import traceback
import logging
import threading
import time
from pathlib import Path
from PySide6.QtCore import QSize, QTimer, QThread, Qt, QPoint
from PySide6.QtGui import QIcon, QImage, QPixmap, QAction
from PySide6.QtWidgets import QApplication, QFrame, QSystemTrayIcon, QMenu
from qfluentwidgets import FluentIcon as FIF, SystemThemeListener, MessageBox, InfoBar, InfoBarPosition
from qfluentwidgets import NavigationItemPosition, FluentWindow, setThemeColor

from app.framework.infra.config.app_config import config
from app.framework.infra.config.app_config import is_non_chinese_ui_language, is_traditional_ui_language
from app.framework.ui.shared.icon import Icon
from app.framework.infra.vision.matcher import matcher
from app.framework.infra.config.setting import REPO_URL
from app.framework.infra.runtime.paths import LOG_DIR, TEMP_DIR, APPDATA_DIR, ensure_runtime_dirs
from app.framework.infra.events.signal_bus import signalBus
from app.framework.core.event_bus.global_task_bus import global_task_bus
from app.framework.core.observability import AppErrorCode, capture_exception
from app.framework.core.task_engine.hotkey_poller import GlobalHotkeyPoller
from app.framework.application.hotkey.routing import resolve_f8_action, HotkeyAction
from app.framework.application.startup.interface_plan import (
    build_deferred_interface_keys,
    build_initial_interface_keys,
)
from app.framework.application.modules import configure_module_spec_providers
from .periodic_base import BaseInterface
from app.framework.infra.update.updater import (
    get_best_update_candidate,
    get_local_version,
)
from app.framework.ui.widgets.custom_message_box import CustomMessageBox
from app.framework.ui.resources import resource_qrc  # don't delete


logger = logging.getLogger(__name__)
SIDEBAR_EXPAND_THRESHOLD = 60 # 侧边栏展开判定的阈值像素
task_coordinator = global_task_bus


class InstallOcr(QThread):

    def __init__(self, ocr_installer, parent=None):
        super().__init__()
        self.ocr_installer = ocr_installer
        self.parent = parent

    def run(self):
        self.ocr_installer.install_ocr()


class MainWindow(FluentWindow, BaseInterface):

    SPLASH_ICON_SIZE = QSize(150, 150)
    SPLASH_MOVIE_SIZE = QSize(160, 160)
    SPLASH_PREFERRED_MIN_MS = 1200
    DEFAULT_WINDOW_WIDTH = 1080
    DEFAULT_WINDOW_HEIGHT = 800
    _ui_text_use_qt_tr = True

    def __init__(self):
        super().__init__()
        BaseInterface.__init__(self)
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
        self.helpInterface = None
        self.tableInterface = None
        self.settingInterface = None
        self.ocr_module = None
        self.numpy_module = None
        self.cv2_module = None
        self._deferred_init_tasks = []
        self._deferred_initialized = False
        self._has_shown_update_popup = False
        self._startup_target_index = int(config.enter_interface.value)
        self._nav_registered = {
            'display': False,
            'home': False,
            'additional': False,
            'table': False,
            'help': False,
            'setting': False,
        }
        self._shared_task_sidebar_cards = None

        # 【新增】全局任务运行状态
        self.global_is_running = False
        task_coordinator.state_changed.connect(self._on_global_task_state_changed)

        # 【新增】将 F8 监听提升到主窗口 (100ms轮询)
        self._hotkey_poller = GlobalHotkeyPoller(
            vk_code=0x77,  # F8
            on_pressed=self._on_global_hotkey_pressed,
        )
        self.hotkey_timer = QTimer(self)
        self.hotkey_timer.timeout.connect(self._check_global_hotkey)
        self.hotkey_timer.start(100)

        self._configure_module_registry()
        self.initWindow()
        self.initSystemTray()  # 初始化系统托盘
        setup_global_exception_hook()

        self._init_tasks = self._build_initial_init_tasks() + [
            self.connectSignalToSlot,
            self.initNavigation,
            self._finalize_startup,
        ]
        QTimer.singleShot(0, self._run_next_init_task)

    @staticmethod
    def _resolve_app_icon() -> QIcon:
        qrc_path = ":/app/framework/ui/resources/logo/logo.png"
        icon = QIcon(qrc_path)
        if not icon.isNull():
            return icon

        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        file_candidates = [
            base_dir / "app" / "framework" / "ui" / "resources" / "logo" / "logo.png",
            base_dir / "app" / "framework" / "ui" / "resources" / "logo" / "logo.ico",
        ]
        for candidate in file_candidates:
            if candidate.exists():
                fallback = QIcon(str(candidate))
                if not fallback.isNull():
                    return fallback
        return QIcon()

    def initSystemTray(self):
        """初始化系统托盘图标和菜单"""
        self.tray_icon = QSystemTrayIcon(self)
        icon = self._resolve_app_icon()
        if icon.isNull():
            logger.warning("system tray icon is null; tray may be invisible")
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(self._ui_text("安卡小助手", "SaaAssistantAca"))

        # 创建托盘菜单
        tray_menu = QMenu(self)

        # 显示主窗口动作
        show_action = QAction(self._ui_text("显示主窗口", "Show Window"), self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        # 彻底退出动作
        quit_action = QAction(self._ui_text("彻底退出", "Quit"), self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # 双击托盘图标恢复窗口
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        # 仅响应双击事件
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def show_from_tray(self):
        """从托盘恢复窗口显示"""
        self.show()
        self.activateWindow()
        if self.isMinimized():
            self.showNormal()

    def quit_app(self):
        """彻底退出程序，跳过托盘拦截"""
        # 标记一个强制退出状态，供 closeEvent 判断
        self._force_quit = True
        self.close()  # 触发 closeEvent 进行保存配置等收尾工作

        # 显式通知应用程序彻底结束事件循环
        QApplication.quit()

        # 针对 VSCode 等调试环境的终极保险，强杀残留的 Python 守护线程
        import sys
        sys.exit(0)

    def _on_global_task_state_changed(self, is_running, zh_name, en_name, source):
        self.global_is_running = is_running

    def _resolve_hotkey_context(self) -> str:
        current_widget = self.stackedWidget.currentWidget()
        if current_widget == self.homeInterface:
            return "home"
        if current_widget == self.additionalInterface:
            return "on_demand"
        return "other"

    def _on_global_hotkey_pressed(self):
        logger.info("MainWindow: 检测到全局快捷键 F8 被按下")
        action = resolve_f8_action(
            global_is_running=self.global_is_running,
            context=self._resolve_hotkey_context(),
        )

        if action == HotkeyAction.REQUEST_STOP:
            task_coordinator.request_stop()
            return
        if action == HotkeyAction.START_DAILY:
            self.homeInterface.on_start_button_click()
            return
        if action == HotkeyAction.START_ON_DEMAND:
            self.additionalInterface.start_current_visible_task()

    def _check_global_hotkey(self):
        try:
            self._hotkey_poller.poll()
        except Exception as exc:
            capture_exception(
                exc,
                code=AppErrorCode.UNEXPECTED_EXCEPTION,
                context={"module": "main_window", "operation": "check_global_hotkey"},
            )

    def _to_traditional_if_needed(self, text):
        if not isinstance(text, str) or not is_traditional_ui_language():
            return text
        try:
            from app.framework.ui.shared.localizer import _to_traditional
            return _to_traditional(text)
        except Exception:
            return text

    def _localize_widget_if_needed(self, widget):
        if widget is None or not is_traditional_ui_language():
            return
        try:
            from app.framework.ui.shared.localizer import localize_widget_tree_for_traditional
            localize_widget_tree_for_traditional(widget)
        except Exception:
            pass

    def _build_initial_init_tasks(self):
        keys = build_initial_interface_keys(
            startup_target_index=self._startup_target_index,
            auto_start_task=bool(config.auto_start_task.value),
        )
        return [lambda key=key: self._create_interface_by_key(key) for key in keys]

    @staticmethod
    def _configure_module_registry():
        from app.features.modules.module_specs import (
            get_on_demand_module_specs as _get_feature_on_demand_specs,
        )
        from app.features.modules.module_specs import (
            get_periodic_module_specs as _get_feature_periodic_specs,
        )

        configure_module_spec_providers(
            periodic_provider=_get_feature_periodic_specs,
            on_demand_provider=lambda: _get_feature_on_demand_specs(include_passive=True),
        )

    def _create_display_interface(self):
        from .display import DisplayInterface
        self.displayInterface = DisplayInterface(self)
        self._localize_widget_if_needed(self.displayInterface)

    def _create_home_interface(self):
        from .periodic_tasks_page import PeriodicTasksPage
        from app.features.modules.collect_supplies.usecase.collect_supplies_actions import (
            CollectSuppliesActions,
        )
        from app.features.modules.enter_game.usecase.enter_game_actions import (
            EnterGameActions,
            SnowbreakGameEnvironment,
        )
        from app.features.modules.event_tips.usecase.event_tips_usecase import (
            EventTipsActions,
            EventTipsUseCase,
        )
        from app.features.modules.redeem_codes.ui.ui_view import RedeemCodesView
        from app.features.modules.redeem_codes.usecase.redeem_codes_usecase import (
            RedeemCodesUseCase,
        )
        from app.features.modules.shopping.usecase.shopping_usecase import (
            ShoppingSelectionUseCase,
        )
        from app.features.scheduling.periodic_ui_texts import apply_periodic_module_texts
        from app.framework.application.tasks.periodic_task_profile import (
            get_periodic_task_profile,
        )
        from app.features.utils.home_navigation import back_to_home
        from app.features.utils.network import start_cloudflare_update

        self.homeInterface = PeriodicTasksPage(
            'Periodic Tasks',
            self,
            game_environment=SnowbreakGameEnvironment(self._is_non_chinese_ui),
            home_sync=back_to_home,
            task_profile_provider=get_periodic_task_profile,
            create_shopping_selection_usecase=lambda is_non_chinese_ui: ShoppingSelectionUseCase(is_non_chinese_ui),
            create_enter_game_actions=lambda game_environment: EnterGameActions(game_environment),
            create_collect_supplies_actions=lambda settings_usecase: CollectSuppliesActions(
                redeem_codes_usecase=RedeemCodesUseCase(settings_usecase),
                redeem_codes_view=RedeemCodesView(),
            ),
            create_event_tips_actions=lambda settings_usecase, is_non_chinese_ui, ui_text_fn: EventTipsActions(
                EventTipsUseCase(
                    settings_usecase,
                    is_non_chinese_ui=is_non_chinese_ui,
                    ui_text_fn=ui_text_fn,
                )
            ),
            startup_update_hook=start_cloudflare_update,
            module_text_applier=apply_periodic_module_texts,
        )
        self._localize_widget_if_needed(self.homeInterface)
        self._sync_task_workspace_sidebar()

    def _create_additional_interface(self):
        from .on_demand_tasks_page import OnDemandTasksPage
        from app.features.modules.trigger.usecase.auto_f_usecase import AutoFModule
        from app.features.modules.trigger.usecase.nita_auto_e_usecase import NitaAutoEModule
        from app.framework.core.task_engine.threads import ModuleTaskThread
        shared_log_browser = None
        if self.homeInterface is not None and hasattr(self.homeInterface, "textBrowser_log"):
            shared_log_browser = self.homeInterface.textBrowser_log
        self.additionalInterface = OnDemandTasksPage(
            'On Demand Tasks',
            self,
            shared_log_browser=shared_log_browser,
            auto_f_module_cls=AutoFModule,
            auto_e_module_cls=NitaAutoEModule,
            module_thread_cls=ModuleTaskThread,
        )
        self._localize_widget_if_needed(self.additionalInterface)
        self._sync_task_workspace_sidebar()

    def _sync_task_workspace_sidebar(self):
        if self.homeInterface is None or self.additionalInterface is None:
            return

        current_widget = self.stackedWidget.currentWidget()

        if current_widget == self.additionalInterface:
            cards = self.homeInterface.detach_shared_sidebar_cards()
            self._shared_task_sidebar_cards = cards
            self.additionalInterface.set_shared_sidebar_cards(
                cards,
                shared_log_browser=self.homeInterface.textBrowser_log,
            )
            return

        if current_widget == self.homeInterface:
            cards = self.additionalInterface.release_shared_sidebar_cards(
                shared_log_browser=self.homeInterface.textBrowser_log
            )
            if not cards:
                cards = self._shared_task_sidebar_cards
            self.homeInterface.attach_shared_sidebar_cards(cards)
            return

    def _create_help_interface(self):
        from .help import Help
        self.helpInterface = Help('Help Interface', self)
        self._localize_widget_if_needed(self.helpInterface)

    def _create_table_interface(self):
        from .ocr_replacement_table import OcrReplacementTable
        self.tableInterface = OcrReplacementTable('Table Interface', self)
        self._localize_widget_if_needed(self.tableInterface)

    def _create_setting_interface(self):
        from .setting_view import SettingInterface
        self.settingInterface = SettingInterface(self)
        self._localize_widget_if_needed(self.settingInterface)

    def _create_interface_by_key(self, key: str):
        creator_map = {
            "display": self._create_display_interface,
            "home": self._create_home_interface,
            "additional": self._create_additional_interface,
            "table": self._create_table_interface,
            "help": self._create_help_interface,
            "setting": self._create_setting_interface,
        }
        creator = creator_map.get(key)
        if creator is not None:
            creator()

    def _run_next_init_task(self):
        if not self._init_tasks:
            return
        task = self._init_tasks.pop(0)
        task()
        QTimer.singleShot(16, self._run_next_init_task)

    def _run_next_deferred_init_task(self):
        if not self._deferred_init_tasks:
            self._deferred_initialized = True
            return
        task = self._deferred_init_tasks.pop(0)
        task()
        QTimer.singleShot(16, self._run_next_deferred_init_task)

    def _defer_load_remaining_interfaces(self):
        self._deferred_init_tasks = [
            (lambda key=key: self._load_and_register_interface(key))
            for key in build_deferred_interface_keys()
        ]
        QTimer.singleShot(0, self._run_next_deferred_init_task)

    def _register_nav_item(self, key, interface, *args, **kwargs):
        if interface is None or self._nav_registered.get(key, False):
            return
        transformed_args = tuple(self._to_traditional_if_needed(arg) if isinstance(arg, str) else arg for arg in args)
        self.addSubInterface(interface, *transformed_args, **kwargs)
        self._nav_registered[key] = True

    def _load_and_register_interface(self, key: str):
        if key == "display":
            if self.displayInterface is None:
                self._create_display_interface()
            self._register_nav_item("display", self.displayInterface, FIF.HOME, self._ui_text('首页', 'Home'))
            return

        if key == "home":
            if self.homeInterface is None:
                self._create_home_interface()
            self._register_nav_item("home", self.homeInterface, FIF.PLAY, self._ui_text('日常', 'Daily'))
            return

        if key == "additional":
            if self.additionalInterface is None:
                self._create_additional_interface()
            self._register_nav_item("additional", self.additionalInterface, FIF.DEVELOPER_TOOLS, self._ui_text('工具', 'Tools'))
            return

        if key == "table":
            if self.tableInterface is None:
                self._create_table_interface()
            self._register_nav_item(
                "table",
                self.tableInterface,
                FIF.BOOK_SHELF,
                self._ui_text('词表', 'OCR'),
                position=NavigationItemPosition.BOTTOM,
            )
            return

        if key == "help":
            if self.helpInterface is None:
                self._create_help_interface()
            self._register_nav_item(
                "help",
                self.helpInterface,
                FIF.HELP,
                self._ui_text('帮助', 'Help'),
                position=NavigationItemPosition.BOTTOM,
            )
            return

        if key == "setting":
            if self.settingInterface is None:
                self._create_setting_interface()
            self._register_nav_item(
                "setting",
                self.settingInterface,
                Icon.SETTINGS,
                self.tr('Settings'),
                position=NavigationItemPosition.BOTTOM,
            )

    def _finalize_startup(self):
        if self.homeInterface is None:
            self._create_home_interface()

        if config.auto_start_task.value or '--auto' in sys.argv:
            if self.homeInterface is None:
                self._load_and_register_interface("home")

            if self.homeInterface.CheckBox_open_game_directly.isChecked():
                if config.LineEdit_game_directory.value == './':
                    logger.warning(f"未配置游戏路径，请先根据教程配置路径")
                else:
                    logger.info(f"开始自动运行日常")
                    self.homeInterface.on_start_button_click()
            else:
                logger.warning(f'未勾选"自动打开游戏"')

        self._finish_splash_screen()
        if config.checkUpdateAtStartUp.value:
            QTimer.singleShot(0, self._show_update_popup_if_needed)
        self._defer_load_remaining_interfaces()

    def _show_update_popup_if_needed(self):
        if not config.checkUpdateAtStartUp.value:
            return

        if self._has_shown_update_popup:
            return
        self._has_shown_update_popup = True

        local_version = get_local_version() or "N/A"
        # 直接调用 app/utils/updater.py 中的集中化验证逻辑
        best = get_best_update_candidate(REPO_URL, local_version)

        if not best:
            InfoBar.success(
                title=self._ui_text("已是最新", "Up to date"),
                content=self._ui_text("", ""),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=800,
                parent=self,
            )
            return

        download_url = str((best or {}).get("download_url") or "").strip()
        download_link_text = self._ui_text("现在更新", "Update now")
        content_html = self._ui_text(
            f"<a href=\"#\">{download_link_text}</a>",
            f"<a href=\"#\">{download_link_text}</a>"
        )
        info_bar = InfoBar.warning(
            title=self._ui_text("检测到新版本", "New version available"),
            content=content_html,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

        if hasattr(info_bar, "contentLabel") and info_bar.contentLabel is not None:
            info_bar.contentLabel.setTextFormat(Qt.TextFormat.RichText)
            info_bar.contentLabel.setOpenExternalLinks(False)

            def _on_link_activated(_):
                if download_url:
                    # 将视图切换至设置页并启动统一化的高速下载机制
                    if self.settingInterface is None:
                        self._load_and_register_interface("setting")
                    self.stackedWidget.setCurrentWidget(self.settingInterface, False)
                    self.settingInterface.scrollToAboutCard()
                    self.settingInterface.start_unified_download(download_url)

            info_bar.contentLabel.linkActivated.connect(_on_link_activated)
            info_bar.contentLabel.setText(content_html)

    def isSidebarExpanded(self) -> bool:
        """统一判断侧边栏当前是否处于展开状态"""
        if not hasattr(self, "navigationInterface") or self.navigationInterface is None:
            return False
        return self.navigationInterface.width() > SIDEBAR_EXPAND_THRESHOLD

    def connectSignalToSlot(self):
        signalBus.micaEnableChanged.connect(self.setMicaEffectEnabled)
        signalBus.switchToSampleCard.connect(self.switchToSample)
        signalBus.showMessageBox.connect(self.showMessageBox)
        signalBus.showScreenshot.connect(self.showScreenshot)
        signalBus.requestExitApp.connect(self.quit_app)
        self.stackedWidget.currentChanged.connect(lambda _: self._sync_task_workspace_sidebar())

    def initNavigation(self):
        self.navigationInterface.setCollapsible(True)

        if self._is_non_chinese_ui:
            self.navigationInterface.setExpandWidth(130)
        else:
            self.navigationInterface.setExpandWidth(100)

        def _restore_nav_state():
            should_be_expanded = bool(config.nav_expanded.value)
            if self.isSidebarExpanded() != should_be_expanded:
                self.navigationInterface.expand() if should_be_expanded else self.navigationInterface.collapse()

        QTimer.singleShot(50, _restore_nav_state)

        if self._startup_target_index == 2:
            self._load_and_register_interface("additional")
            self.stackedWidget.setCurrentWidget(self.additionalInterface, False)
        elif self._startup_target_index == 1:
            self._load_and_register_interface("home")
            self.stackedWidget.setCurrentWidget(self.homeInterface, False)
        else:
            self._load_and_register_interface("display")
            self.stackedWidget.setCurrentWidget(self.displayInterface, False)

    def init_ocr(self):
        from app.features.modules.ocr import ocr
        self.ocr_module = ocr

        def benchmark(ocr_func, img, runs=30):
            for _ in range(10):
                ocr_func(img, is_log=False)
            start = time.time()
            for _ in range(runs):
                ocr_func(img, is_log=False)
            return (time.time() - start) / runs

        ocr.instance_ocr()

    def initWindow(self):
        position = config.position.value
        if hasattr(config, "ocr_use_gpu") and config.ocr_use_gpu.value:
            config.set(config.ocr_use_gpu, False)
        target_screen = None

        if position:
            target_screen = QApplication.screenAt(QPoint(position[0], position[1]))

        if target_screen is None:
            target_screen = QApplication.primaryScreen()

        target_geo = target_screen.availableGeometry()

        self.resize(int(target_geo.width() * 0.58), int(target_geo.height() * 0.8))
        self.setMinimumSize(int(target_geo.width() * 0.5), int(target_geo.height() * 0.6))

        self.setWindowIcon(self._resolve_app_icon())
        self.setWindowTitle(self._ui_text('安卡小助手', 'SaaAssistantAca'))
        setThemeColor("#009FAA")
        self.setMicaEffectEnabled(False)
        self.navigationInterface.setReturnButtonVisible(False)

        if position and target_screen == QApplication.screenAt(QPoint(position[0], position[1])):
            self.move(*position)
        else:
            rect = self.frameGeometry()
            rect.moveCenter(target_geo.center())
            self.move(rect.topLeft())

        self.show()
        QApplication.processEvents()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, 'splashScreen') and self.splashMovieLabel is not None:
            self.splashScreen.resize(self.size())
            self.splashMovieLabel.resize(self.splashScreen.size())

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

        ocr_thread = threading.Thread(target=self.init_ocr)
        ocr_thread.daemon = True
        ocr_thread.start()

    def yes_click(self):
        self.check_ocr_thread = InstallOcr(self.ocr_installer)
        try:
            self.check_ocr_thread.start()
        except Exception as e:
            print(e)

    def cancel_click(self):
        self.close()

    def switchToSample(self, routeKey, index):
        if routeKey == "Home-Start-Now":
            if self.homeInterface is None:
                self._load_and_register_interface("home")
            self.stackedWidget.setCurrentWidget(self.homeInterface, False)
            QTimer.singleShot(0, self.homeInterface.start_from_homepage)
            return

        interfaces = self.findChildren(QFrame)
        for w in interfaces:
            if w.objectName() == routeKey:
                self.stackedWidget.setCurrentWidget(w, False)

    def save_log(self):
        """保存所有log到html中"""

        def is_empty_html(content):
            empty_html_pattern = re.compile(r'<p[^>]*>\s*(<br\s*/?>)?\s*</p>', re.IGNORECASE)
            body_content = re.sub(r'<!DOCTYPE[^>]*>|<html[^>]*>|<head[^>]*>.*?</head>|<body[^>]*>|</body>|</html>', '',
                                  content, flags=re.DOTALL)
            return bool(empty_html_pattern.fullmatch(body_content.strip()))

        def save_html(path, content):
            if not content or is_empty_html(content):
                return
            with open(path, "w", encoding='utf-8') as file:
                file.write(content)

        def clean_old_logs(log_dir, max_files=30):
            if not os.path.exists(log_dir):
                return

            all_logs = [
                f for f in os.listdir(log_dir)
                if f.endswith('.html') and os.path.isfile(os.path.join(log_dir, f))
            ]

            if len(all_logs) <= max_files:
                return

            all_logs.sort(key=lambda x: os.path.getctime(os.path.join(log_dir, x)))
            for file_to_remove in all_logs[:len(all_logs) - max_files]:
                os.remove(os.path.join(log_dir, file_to_remove))

        log_configs = []
        if self.homeInterface is not None:
            log_configs.append((str(LOG_DIR / "home"), self.homeInterface.textBrowser_log, "home"))
        if self.additionalInterface is not None:
            shared_log_browser = None
            if hasattr(self.additionalInterface, "get_shared_log_browser"):
                shared_log_browser = self.additionalInterface.get_shared_log_browser()
            elif hasattr(self.additionalInterface, "ui") and hasattr(self.additionalInterface.ui, "textBrowser_shared_log"):
                shared_log_browser = self.additionalInterface.ui.textBrowser_shared_log
            if shared_log_browser is not None:
                log_configs.append((str(LOG_DIR / "on_demand"), shared_log_browser, "on_demand"))

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for log_dir, text_browser, prefix in log_configs:
            os.makedirs(log_dir, exist_ok=True)
            clean_old_logs(log_dir)
            log_content = text_browser.toHtml()
            filename = f"{prefix}_{timestamp}.html"
            save_html(os.path.join(log_dir, filename), log_content)

    def save_position(self):
        geometry = self.geometry()
        position = (geometry.left(), geometry.top())
        config.set(config.position, position)

    def closeEvent(self, a0):
        # 如果不是彻底退出，且开启了最小化到托盘，则拦截关闭事件并隐藏窗口
        if not getattr(self, "_force_quit", False) and config.minimizeToTray.value:
            a0.ignore()  # 忽略关闭事件
            self.hide()  # 隐藏窗口

            # 显示一个气泡提示，告诉用户程序跑到托盘去了 (只提示一次避免烦人，可以根据需要保留)
            if not getattr(self, "_has_shown_tray_tip", False):
                self.tray_icon.showMessage(
                    self._ui_text("已最小化", "Minimized"),
                    self._ui_text("安卡希雅已隐藏到系统托盘，后台计划依然生效哦！",
                                  "Acacia is running in the system tray. Background tasks are still active!"),
                    QSystemTrayIcon.MessageIcon.Information,
                    2000
                )
                self._has_shown_tray_tip = True
            return

        # 如果是真的要关闭程序，执行收尾工作
        if self.ocr_module is not None:
            self.ocr_module.stop_ocr()
        self.themeListener.terminate()
        self.themeListener.deleteLater()
        if hasattr(self, "navigationInterface") and self.navigationInterface is not None:
            config.set(config.nav_expanded, self.isSidebarExpanded())
        try:
            self.save_log()
            self.save_position()
            if config.saveScaleCache.value:
                matcher.save_scale_cache()
        except Exception as e:
            logger.error(e)

        # 彻底销毁释放托盘图标系统资源，防止进程阻塞
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
            self.tray_icon.deleteLater()

        super().closeEvent(a0)

    def changeEvent(self, event):
        super().changeEvent(event)

    def _onThemeChangedFinished(self):
        super()._onThemeChangedFinished()

    def showMessageBox(self, title, content):
        massage = MessageBox(title, content, self)
        if massage.exec():
            if self.settingInterface is None:
                self._load_and_register_interface("setting")
            w = self.settingInterface
            self.stackedWidget.setCurrentWidget(w, False)
            w.scrollToAboutCard()

            local_version = get_local_version() or "N/A"
            best = get_best_update_candidate(REPO_URL, local_version)

            if best and best.get("download_url"):
                w.start_unified_download(best["download_url"])
            else:
                logger.warning("未能获取到有效的更新下载链接")

    def showScreenshot(self, screenshot):
        def ndarray_to_qpixmap(ndarray):
            import numpy as np
            import cv2
            if ndarray.ndim == 2:
                ndarray = np.expand_dims(ndarray, axis=-1)
                ndarray = np.repeat(ndarray, 3, axis=-1)

            height, width, channel = ndarray.shape
            bytes_per_line = 3 * width
            ndarray = cv2.cvtColor(ndarray, cv2.COLOR_BGR2RGB)
            qimage = QImage(ndarray.data, width, height, bytes_per_line, QImage.Format_RGB888)
            return QPixmap.fromImage(qimage)

        def save_screenshot(ndarray):
            if self.cv2_module is None:
                import cv2
                self.cv2_module = cv2

            ensure_runtime_dirs()
            self.cv2_module.imwrite(str(TEMP_DIR / f"{time.time()}.png"), ndarray)

        save_screenshot(screenshot)

        if not isinstance(self.message_window, CustomMessageBox):
            self.message_window = CustomMessageBox(self, '当前截图', 'image')
        screenshot_pixmap = ndarray_to_qpixmap(screenshot)
        scaled_pixmap = screenshot_pixmap.scaled(
            200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.message_window.content.setPixmap(scaled_pixmap)
        if self.message_window.exec():
            pass
        else:
            pass


def setup_global_exception_hook():
    """将未捕获的严重报错弹窗显示并记录本地日志"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        capture_exception(logger, exc_value, AppErrorCode.TASK_EXECUTION_FAILED, context="global_exception_hook")

        # 1. 打印在控制台 / 写入 crash.log
        print(f"发生致命错误:\n{error_msg}")
        try:
            ensure_runtime_dirs()
            with open(APPDATA_DIR / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now()}] \n{error_msg}\n")
        except Exception as log_error:
            logger.error(f"写入 crash.log 失败: {log_error}")

        # 2. 调用主窗口弹窗警报
        try:
            # 拿到 Qt 正在运行的主窗口实例
            main_win = QApplication.activeWindow()
            if main_win:
                MessageBox("系统崩溃保护", f"程序发生了未捕获的严重异常，已将报错存入 crash.log，请截图反馈群管：\n\n{exc_value}", main_win).exec()
        except Exception as dialog_error:
            logger.error(f"崩溃弹窗失败: {dialog_error}")

    sys.excepthook = handle_exception


