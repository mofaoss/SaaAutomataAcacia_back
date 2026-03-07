# coding:utf-8
import logging
import os.path
import subprocess
import sys
import html
from functools import partial

from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPixmap, QMovie
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication, QSizePolicy
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar
from qfluentwidgets import SettingCardGroup as CardGroup
from qfluentwidgets import (SwitchSettingCard, ScrollArea,
                            ComboBoxSettingCard, ExpandLayout, setTheme, setFont, MessageBox, ProgressBar,
                            LargeTitleLabel, SubtitleLabel, BodyLabel, PushButton, HyperlinkButton,
                            PushButton, FluentIcon as FIF
                            )

from ..common.config import config, isWin11, is_non_chinese_ui_language
from ..common.setting import QQ, REPO_URL
from ..common.signal_bus import signalBus
from ..common.style_sheet import StyleSheet
from .base_interface import BaseInterface
from utils.updater_utils import (
    get_local_version,
    resolve_batch_dir,
    get_best_update_candidate,
    get_binary_path,
    get_app_root,
)
from ..repackage.slider_setting_card import SliderSettingCard
from ..repackage.text_edit_card import TextEditCard
from utils.updater_utils import UpdateDownloadThread, get_best_update_candidate, get_local_version

logger = logging.getLogger(__name__)


class VersionCheckThread(QThread):

    finishedSignal = Signal(dict)

    def run(self):
        local_version = get_local_version() or "-"
        should_check_prerelease = bool(config.checkPrereleaseForStable.value)

        best = get_best_update_candidate(REPO_URL, local_version, should_check_prerelease)

        if best:
            payload = {
                "local_version": local_version,
                "latest_version": best.get("version") or "",
                "download_url": best.get("download_url") or "",
                "is_prerelease": best.get("is_prerelease") or False,
            }
        else:
            payload = {
                "local_version": local_version,
                "latest_version": "",
                "download_url": "",
                "is_prerelease": False,
            }

        self.finishedSignal.emit(payload)


class AboutHeaderWidget(QWidget, BaseInterface):

    def __init__(self, is_non_chinese_ui: bool = False, parent=None):
        super().__init__(parent=parent)
        self._is_non_chinese_ui = is_non_chinese_ui
        self.setMinimumHeight(140)

        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(24)

        self.logoLabel = QLabel(self)
        self.logoLabel.setFixedSize(80, 80)
        pixmap = QPixmap("app/resource/images/sun.png")
        if not pixmap.isNull():
            self.logoLabel.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logoLabel.setText("LOGO")
            self.logoLabel.setStyleSheet("background-color: #333; color: white; border-radius: 10px;")
        self.mainLayout.addWidget(self.logoLabel, 0, Qt.AlignmentFlag.AlignVCenter)

        self.rightLayout = QVBoxLayout()
        self.rightLayout.setSpacing(12)
        self.rightLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.mainLayout.addLayout(self.rightLayout)

        self.row1Layout = QHBoxLayout()
        self.row1Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.titleLabel = SubtitleLabel(self._ui_text("作者：Dr. Sun", "Author: mofaoss"), self)
        self.githubBtn = PushButton(self._ui_text("前往 GitHub", "Open GitHub"), self)
        self.githubBtn.setFixedSize(110, 30)

        self.row1Layout.addWidget(self.titleLabel)
        self.row1Layout.addSpacing(16)
        self.row1Layout.addWidget(self.githubBtn)
        self.rightLayout.addLayout(self.row1Layout)

        self.row2Layout = QHBoxLayout()
        self.row2Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.qqPrefix = BodyLabel(self._ui_text("获取更新 QQ群：", "Update QQ group: "), self)
        self.qqLink = HyperlinkButton("", "996710620", self)
        self.qqLink.setToolTip(self._ui_text("点击复制QQ群号", "Click to copy QQ group number"))

        self.githubPrefix = BodyLabel("GitHub:", self)
        self.downloadLink = HyperlinkButton("", self._ui_text("现在更新", "Update now"), self)

        self.downloadLink.setMinimumHeight(24)
        self.row2Layout.addWidget(self.qqPrefix)
        self.row2Layout.addWidget(self.qqLink)
        self.row2Layout.addSpacing(24)
        self.row2Layout.addWidget(self.githubPrefix)
        self.row2Layout.addWidget(self.downloadLink)
        self.rightLayout.addLayout(self.row2Layout)

        self.row3Layout = QHBoxLayout()
        self.row3Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        local_version = get_local_version() or "-"
        self.localVersionLabel = BodyLabel(self._ui_text(f"当前版本：{local_version}", f"Current version: {local_version}"), self)

        self.remoteVersionLabel = BodyLabel(self._ui_text("最新版本：正在检查...", "Latest version: checking..."), self)

        self.checkUpdateBtn = PushButton(FIF.UPDATE, self._ui_text("检查更新", "Check for updates"), self)
        self.checkUpdateBtn.setFixedHeight(32)
        self.checkUpdateBtn.setToolTip(self._ui_text("检查更新", "Check for updates"))
        self.checkUpdateBtn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.row3Layout.addWidget(self.localVersionLabel)
        self.row3Layout.addSpacing(24)
        self.row3Layout.addWidget(self.remoteVersionLabel)
        self.row3Layout.addSpacing(16)
        self.row3Layout.addWidget(self.checkUpdateBtn)
        self.rightLayout.addLayout(self.row3Layout)

        self.mainLayout.addStretch(1)

class SettingCardGroup(CardGroup):

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        setFont(self.titleLabel, 14, QFont.Weight.DemiBold)


class SettingInterface(ScrollArea, BaseInterface):
    """ Setting interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.parent = parent
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        self.progressBar = ProgressBar(self)
        self.progressBar.setVisible(False)
        self._is_dialog_open = False

        self.app_name = "SaaAutomataAcacia"
        self.startup_task_name = f"{self.app_name} {self._ui_text('开机自启', 'Startup')}"
        if getattr(sys, 'frozen', False):
            self.app_path = sys.executable
        else:
            self.app_path = sys.argv[0]

        # setting label
        self.settingLabel = LargeTitleLabel(self.tr("Settings"), self)
        self.aboutHeaderWidget = AboutHeaderWidget(self._is_non_chinese_ui, self.scrollWidget)
        self.versionCheckThread = None

        # core settings
        self.coreSettingsGroup = SettingCardGroup(
            self._ui_text("核心设置", "Core Settings"), self.scrollWidget)

        # personalization
        self.personalGroup = SettingCardGroup(
            self.tr('Personalization'), self.scrollWidget)
        self.micaCard = SwitchSettingCard(
            FIF.TRANSPARENT,
            self.tr('Mica effect'),
            self.tr('Apply semi transparent to windows and surfaces'),
            config.micaEnabled,
            self.personalGroup
        )
        self.themeCard = ComboBoxSettingCard(
            config.themeMode,
            FIF.BRUSH,
            self.tr('Application theme'),
            self.tr("Change the appearance of your application"),
            texts=[
                self.tr('Light'), self.tr('Dark'),
                self.tr('Use system setting')
            ],
            parent=self.personalGroup
        )
        self.enterCard = ComboBoxSettingCard(
            config.enter_interface,
            FIF.HOME,
            self._ui_text('启动时进入', 'Startup page'),
            self._ui_text("选择启动软件时直接进入哪个页面", "Choose which page to open on startup"),
            texts=[
                self._ui_text('首页', 'Home'), self._ui_text('日常', 'Daily'),
                self._ui_text('工具', 'Tools')
            ],
            parent=self.personalGroup
        )
        self.zoomCard = ComboBoxSettingCard(
            config.dpiScale,
            FIF.ZOOM,
            self.tr("Interface zoom"),
            self.tr("Change the size of widgets and fonts"),
            texts=[
                "100%", "125%", "150%", "175%", "200%",
                self.tr("Use system setting")
            ],
            parent=self.personalGroup
        )
        self.languageCard = ComboBoxSettingCard(
            config.language,
            FIF.LANGUAGE,
            self.tr('Language'),
            self.tr('Set your preferred language for UI'),
            texts=['简体中文', '繁體中文', 'English', self.tr('Use system setting')],
            parent=self.personalGroup
        )

        # about software
        self.aboutSoftwareGroup = SettingCardGroup(
            self._ui_text("功能相关", "About Software"), self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            self.tr('Check for updates when the application starts'),
            self._ui_text('如果开启，每次游戏版本更新会自动更新对应活动刷体力的坐标和安卡希雅更新提醒的链接',
                          'If enabled, coordinates and schedule reminder links update automatically after each game version update'),
            configItem=config.checkUpdateAtStartUp,
            parent=self.aboutSoftwareGroup
        )
        self.checkPrereleaseForStableCard = SwitchSettingCard(
            FIF.TAG,
            self._ui_text('检测测试版更新（正式版用户）', 'Check pre-release updates (stable users)'),
            self._ui_text('默认关闭。正式版用户开启后会同时检测正式版和测试版；测试版用户始终会同时检测两者',
                          'Disabled by default. When enabled, stable users will check both stable and pre-release; pre-release users always check both'),
            configItem=config.checkPrereleaseForStable,
            parent=self.aboutSoftwareGroup
        )

        # Core Settings Cards
        self.stealthModeCard = SwitchSettingCard(
            FIF.HIDE,
            self._ui_text('隐身模式', 'Stealth Mode'),
            self._ui_text('游戏完全隐身后台', 'Enable to run game in complete stealth mode in background'),
            configItem=config.windowTrackingInput,
            parent=self.coreSettingsGroup
        )
        self.serverCard = ComboBoxSettingCard(
            config.server_interface,
            FIF.GAME,
            self._ui_text('游戏渠道选择', 'Server channel'),
            self._ui_text("请选择你所在的区服", "Choose your server channel"),
            texts=[self._ui_text('官服', 'Official'), self._ui_text('b服', 'Bilibili'), self._ui_text('国际服', 'Global')],
            parent=self.coreSettingsGroup
        )
        self.gameLanguageCard = ComboBoxSettingCard(
            config.game_language,
            FIF.LANGUAGE,
            '游戏语言 / Game Language',
            'Used for automation OCR matching, supports only Simplified/Traditional Chinese'
            if is_non_chinese_ui_language() else '用于自动化OCR匹配，仅支持简体/繁体中文',
            texts=['简体中文 / Simplified Chinese', '繁體中文 / Traditional Chinese'],
            parent=self.coreSettingsGroup
        )

        self.windowTrackingAlphaCard = SliderSettingCard(
            configItem=config.windowTrackingAlpha,
            icon=FIF.HIDE,
            title=self._ui_text('隐身模式可见度', 'Stealth mode visibility'),
            content=self._ui_text('数值越低越隐形：1=极度隐藏，255=正常显示，建议设置1',
                                  'Lower value means more invisible: 1 = highly hidden, 255 = normal visibility. Recommended to set to 1'),
            parent=self.aboutSoftwareGroup,
            min_value=1,
            max_value=255,
        )
        self.saveScaleCacheCard = SwitchSettingCard(
            FIF.SAVE,
            self._ui_text('保存缩放比例数据', 'Save scaling cache'),
            self._ui_text('如果你的游戏窗口固定使用，可以选择保存，这样运行会匹配得更快，如果窗口大小经常变化则取消勾选',
                          'Enable if your game window size is stable for faster matching; disable if window size changes often'),
            configItem=config.saveScaleCache,
            parent=self.aboutSoftwareGroup
        )
        self.autoStartTask = SwitchSettingCard(
            FIF.PLAY,
            self._ui_text('自动开始任务', 'Auto start tasks'),
            self._ui_text('唤醒安卡希雅后自动开始运行日常，必须先勾选并配置好自动打开游戏',
                          'Automatically starts daily tasks when Acacia is called. Requires auto-open game to be enabled and configured first'),
            configItem=config.auto_start_task,
            parent=self.aboutSoftwareGroup
        )
        self.autoBootStartup = SwitchSettingCard(
            FIF.POWER_BUTTON,
            self._ui_text('开机自启', 'Start on boot'),
            self._ui_text('开机时自动唤醒安卡希雅', 'Call Acacia automatically when Windows starts'),
            configItem=config.auto_boot_startup,
            parent=self.aboutSoftwareGroup
        )
        self.informMessage = SwitchSettingCard(
            FIF.HISTORY,
            self._ui_text('消息通知', 'Notifications'),
            self._ui_text('是否打开体力恢复通知', 'Enable stamina recovery notifications'),
            configItem=config.inform_message,
            parent=self.aboutSoftwareGroup
        )
        self.proxyCard = TextEditCard(
            config.update_proxies,
            FIF.GLOBE,
            self._ui_text('代理端口', 'Proxy port'),
            self._ui_text("如‘7890’", "e.g. '7890'"),
            self._ui_text('如果选择开代理则需要填入代理端口，不开代理则置空',
                          'Fill proxy port when using proxy; leave empty when not using proxy'),
            self.aboutSoftwareGroup
        )

        # Developer Options (开发者选项)
        self.developerOptionsGroup = SettingCardGroup(
            self._ui_text("开发者选项", "Developer Options"), self.scrollWidget)

        self.isLogCard = SwitchSettingCard(
            FIF.DEVELOPER_TOOLS,
            self._ui_text('展示OCR识别结果', 'Show OCR results'),
            self._ui_text('打开将在日志中显示ocr识别结果，获得更详细的日志信息',
                          'Show OCR recognition results in logs for more detailed diagnostics'),
            configItem=config.isLog,
            parent=self.developerOptionsGroup
        )
        self.showScreenshotCard = SwitchSettingCard(
            FIF.PHOTO,
            self._ui_text('展示运行时的窗口截图', 'Show runtime screenshots'),
            self._ui_text('用于在查错时查看是否正确截取了游戏对应位置的画面，截取的所有画面会保存在SaaAutomataAcacia/temp下，需要手动删除',
                          'Used for troubleshooting capture regions. Screenshots are saved in SaaAutomataAcacia/temp and should be deleted manually'),
            configItem=config.showScreenshot,
            parent=self.developerOptionsGroup
        )
        self.isInputLogCard = SwitchSettingCard(
            FIF.COMMAND_PROMPT,
            self._ui_text('展示模拟输入日志', 'Show input action logs'),
            self._ui_text('打开将在日志中显示鼠标移动、点击、按键等模拟输入操作的详细信息',
                          'Show detailed logs of simulated mouse clicks and keystrokes'),
            configItem=config.isInputLog,
            parent=self.developerOptionsGroup
        )

        self.__initWidget()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 100, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName('settingInterface')

        # initialize style sheet
        setFont(self.settingLabel, 23, QFont.Weight.DemiBold)
        self.scrollWidget.setObjectName('scrollWidget')
        self.settingLabel.setObjectName('settingLabel')
        StyleSheet.SETTING_INTERFACE.apply(self)
        self.scrollWidget.setStyleSheet("QWidget{background:transparent}")

        self.micaCard.setEnabled(isWin11())

        # initialize layout
        self.__initLayout()
        self._connectSignalToSlot()
        self._start_about_header_version_check()

    def __initLayout(self):
        self.settingLabel.move(36, 50)

        self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.enterCard)
        self.personalGroup.addSettingCard(self.zoomCard)
        self.personalGroup.addSettingCard(self.languageCard)

        # Add Core Settings cards
        self.coreSettingsGroup.addSettingCard(self.stealthModeCard)
        self.coreSettingsGroup.addSettingCard(self.serverCard)
        self.coreSettingsGroup.addSettingCard(self.gameLanguageCard)

        self.aboutSoftwareGroup.addSettingCard(self.windowTrackingAlphaCard)
        self.aboutSoftwareGroup.addSettingCard(self.updateOnStartUpCard)
        self.aboutSoftwareGroup.addSettingCard(self.checkPrereleaseForStableCard)
        self.aboutSoftwareGroup.addSettingCard(self.saveScaleCacheCard)
        self.aboutSoftwareGroup.addSettingCard(self.autoStartTask)
        self.aboutSoftwareGroup.addSettingCard(self.autoBootStartup)
        self.aboutSoftwareGroup.addSettingCard(self.informMessage)
        self.aboutSoftwareGroup.addSettingCard(self.proxyCard)

        # Add Developer Options cards
        self.developerOptionsGroup.addSettingCard(self.isLogCard)
        self.developerOptionsGroup.addSettingCard(self.showScreenshotCard)
        self.developerOptionsGroup.addSettingCard(self.isInputLogCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.aboutHeaderWidget.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.expandLayout.addWidget(self.aboutHeaderWidget)
        headerSpacer = QWidget(self.scrollWidget)
        headerSpacer.setFixedHeight(6)
        self.expandLayout.addWidget(headerSpacer)
        self.expandLayout.addWidget(self.coreSettingsGroup)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.aboutSoftwareGroup)
        self.expandLayout.addWidget(self.developerOptionsGroup)

    def _showRestartTooltip(self):
        """ show restart tooltip """
        from ..common.config import is_non_chinese_ui_language
        is_english = is_non_chinese_ui_language()

        title = 'Updated successfully' if is_english else '更新成功'
        content = 'Configuration takes effect after restart' if is_english else '重启后配置生效'

        InfoBar.success(
            title,
            content,
            duration=2000,
            parent=self
        )

    def _connectSignalToSlot(self):
        """ connect signal to slot """
        config.appRestartSig.connect(self._showRestartTooltip)
        signalBus.windowTrackingStealthChanged.connect(self._sync_stealth_controls)

        # personalization
        config.themeChanged.connect(setTheme)
        self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)
        self.autoBootStartup.checkedChanged.connect(self.set_windows_start)

        if hasattr(self.aboutHeaderWidget, "githubBtn"):
            self.aboutHeaderWidget.githubBtn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        if hasattr(self.aboutHeaderWidget, "qqLink"):
            self.aboutHeaderWidget.qqLink.clicked.connect(self._copy_qq_group_number)
        if hasattr(self.aboutHeaderWidget, "checkUpdateBtn"):
            self.aboutHeaderWidget.checkUpdateBtn.clicked.connect(self._on_manual_update_clicked)

    def _on_manual_update_clicked(self):
        if not hasattr(self, 'aboutHeaderWidget') or not hasattr(self.aboutHeaderWidget, 'checkUpdateBtn'):
            return

        self.aboutHeaderWidget.checkUpdateBtn.setEnabled(False)
        self.manualCheckThread = VersionCheckThread(self)
        self.manualCheckThread.finishedSignal.connect(self._on_manual_check_finished)
        self.manualCheckThread.start()

    def _on_manual_check_finished(self, payload: dict):
        if hasattr(self, 'aboutHeaderWidget') and hasattr(self.aboutHeaderWidget, 'checkUpdateBtn'):
            self.aboutHeaderWidget.checkUpdateBtn.setEnabled(True)
            self.aboutHeaderWidget.checkUpdateBtn.setText(self._ui_text("检查更新", "Check for updates"))

        self._on_about_header_version_checked(payload)

        download_url = str(payload.get("download_url") or "").strip()
        if download_url:
            InfoBar.warning(
                self._ui_text("发现新版本", "New version available"),
                self._ui_text("请点击【现在更新】或前往QQ群获取", "Please click [Update now] or go to QQ group for update"),
                duration=3000,
                parent=self
            )
        else:
            InfoBar.success(
                self._ui_text("已是最新", "Up to date"),
                self._ui_text("", ""),
                duration=3000,
                parent=self
            )

    def _copy_qq_group_number(self):
        QApplication.clipboard().setText("996710620")
        InfoBar.success(
            self._ui_text('已复制QQ群号', 'QQ group number copied'),
            "996710620",
            duration=2000,
            parent=self
        )

    def _start_about_header_version_check(self):
        self.versionCheckThread = VersionCheckThread(self)
        self.versionCheckThread.finishedSignal.connect(self._on_about_header_version_checked)
        self.versionCheckThread.start()

    def _sync_stealth_controls(self, checked: bool, alpha: int):
        try:
            if hasattr(self, "windowTrackingAlphaCard") and self.windowTrackingAlphaCard is not None:
                self.windowTrackingAlphaCard.sync_from_config()
        except Exception:
            pass

    def set_windows_start(self, is_checked):
        if is_checked:
            self._enable_windows()
        else:
            self._disable_windows()

    def _enable_windows(self):
        try:
            app_dir = os.path.dirname(self.app_path)
            cmd_file_path = os.path.join(app_dir, "saa_startup.cmd")
            cmd_content = f'@echo off\ncd "{app_dir}"\nstart "" "{self.app_path}"'

            with open(cmd_file_path, 'w', encoding='utf-8') as f:
                f.write(cmd_content)

            task_command = [
                'schtasks', '/create',
                '/tn', self.startup_task_name,
                '/tr', f'cmd.exe /c "{cmd_file_path}"',
                '/sc', 'onlogon',
                '/rl', 'highest',
                '/f'
            ]

            subprocess.run(task_command, shell=True, check=True,
                           capture_output=True, text=True)

            InfoBar.success(
                self._ui_text('添加自启成功', 'Startup task added'),
                self._ui_text('已通过计划任务创建开机自启', 'Startup task has been created via Windows Task Scheduler'),
                isClosable=True,
                duration=2000,
                parent=self
            )
        except subprocess.CalledProcessError as e:
            InfoBar.error(
                self._ui_text('添加自启失败', 'Failed to add startup task'),
                self._ui_text("创建计划任务失败：", "Failed to create scheduled task: ") + f"{e.stderr}",
                isClosable=True,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                self._ui_text('添加自启失败', 'Failed to add startup task'),
                self._ui_text("创建启动文件失败：", "Failed to create startup script: ") + f"{e}",
                isClosable=True,
                duration=2000,
                parent=self
            )

    def _disable_windows(self):
        try:
            subprocess.run(['schtasks', '/delete', '/tn', self.startup_task_name, '/f'],
                           shell=True, check=True, capture_output=True, text=True)

            app_dir = os.path.dirname(self.app_path)
            cmd_file_path = os.path.join(app_dir, "saa_startup.cmd")
            if os.path.exists(cmd_file_path):
                os.remove(cmd_file_path)

            InfoBar.success(
                self._ui_text('删除自启成功', 'Startup task removed'),
                self._ui_text('已关闭开机自启', 'Start on boot has been disabled'),
                isClosable=True,
                duration=2000,
                parent=self
            )
        except subprocess.CalledProcessError as e:
            if "找不到系统指定的" in e.stderr or "cannot find" in e.stderr.lower():
                InfoBar.warning(
                    self._ui_text('任务不存在', 'Task not found'),
                    self._ui_text('计划任务可能已被删除', 'Scheduled task may have already been removed'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    self._ui_text('删除自启失败', 'Failed to remove startup task'),
                    self._ui_text("删除计划任务失败：", "Failed to delete scheduled task: ") + f"{e.stderr}",
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
        except Exception as e:
            InfoBar.error(
                self._ui_text('删除自启失败', 'Failed to remove startup task'),
                f"{e}",
                isClosable=True,
                duration=2000,
                parent=self
            )

    def _on_about_header_version_checked(self, payload: dict):
        local_version = str(payload.get("local_version") or get_local_version() or "-").strip()
        latest_version = str(payload.get("latest_version") or "").strip()
        download_url = str(payload.get("download_url") or "").strip()

        if not download_url:
            if hasattr(self.aboutHeaderWidget, "downloadLink"):
                try:
                    self.aboutHeaderWidget.downloadLink.clicked.disconnect()
                except Exception:
                    pass
                self.aboutHeaderWidget.downloadLink.setText(self._ui_text("已是最新", "Up to date"))
                self.aboutHeaderWidget.downloadLink.setUrl("")
                self.aboutHeaderWidget.downloadLink.clicked.connect(
                    lambda: InfoBar.success(
                        self._ui_text("已是最新", "Up to date"),
                        self._ui_text("", ""),
                        duration=2000,
                        parent=self
                    )
                )
        else:
            if hasattr(self.aboutHeaderWidget, "downloadLink"):
                try:
                    self.aboutHeaderWidget.downloadLink.setUrl("")
                    self.aboutHeaderWidget.downloadLink.clicked.disconnect()
                except Exception:
                    pass
                self.aboutHeaderWidget.downloadLink.setText(self._ui_text("现在更新", "Update now"))
                self.aboutHeaderWidget.downloadLink.clicked.connect(lambda: self.start_unified_download(download_url))

        if hasattr(self.aboutHeaderWidget, "localVersionLabel"):
            self.aboutHeaderWidget.localVersionLabel.setText(
                self._ui_text(f"当前版本：{local_version}", f"Current version: {local_version}")
            )

        if latest_version:
            if hasattr(self.aboutHeaderWidget, "remoteVersionLabel"):
                self.aboutHeaderWidget.remoteVersionLabel.setText(
                    self._ui_text(f"最新版本：{latest_version}", f"Latest version: {latest_version}")
                )
        else:
            if hasattr(self.aboutHeaderWidget, "remoteVersionLabel"):
                self.aboutHeaderWidget.remoteVersionLabel.setText(
                    self._ui_text(f"最新版本：{local_version}", f"Latest version: {local_version}")
                )

    def handle_download_fallback(self, title: str, content: str, download_url: str):
        self.progressBar.setVisible(False)
        message_box = MessageBox(title, content, self.parent.window())
        if message_box.exec():
            QDesktopServices.openUrl(QUrl(download_url))

    def start_unified_download(self, download_url: str):
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)

        self.download_thread = UpdateDownloadThread(download_url)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.update_finished)
        self.download_thread.fallback_signal.connect(
            lambda title, content: self.handle_download_fallback(title, content, download_url)
        )
        self.download_thread.start()

    def update_finished(self, downloaded_path: str):
        self.progressBar.setVisible(False)
        app_root = get_app_root()

        is_exe = os.path.isfile(downloaded_path) and downloaded_path.lower().endswith('.exe')

        title = self._ui_text('更新准备就绪', 'Update Ready')

        if is_exe:
            content = self._ui_text(
                "安卡希雅的新版本已下载完毕。<br/><br/>是否立即关闭并运行安装向导？",
                "New version of Acacia has been downloaded.<br/><br/>Close app and run installer now?"
            )
        else:
            content = self._ui_text(
                "新版本文件已解压准备就绪。<br/><br/>是否立即重启程序自动完成静默更新？",
                "Update files extracted.<br/><br/>Restart app to apply updates?"
            )

        message_box = MessageBox(title, content, self.parent.window())
        if message_box.exec():
            try:
                batch_dir = resolve_batch_dir(downloaded_path)
                os.makedirs(batch_dir, exist_ok=True)
                batch_path = os.path.join(batch_dir, "apply_update.bat")

                with open(batch_path, "w", encoding="gbk") as f:
                    f.write('@echo off\n')
                    f.write('echo 正在等待主程序关闭 (Waiting for app to close)...\n')
                    f.write('timeout /t 2 /nobreak > nul\n')

                    if is_exe:
                        f.write(f'start "" "{downloaded_path}"\n')
                    else:
                        f.write(f'xcopy "{downloaded_path}\\*" "{app_root}\\" /E /Y /C > nul\n')
                        f.write(f'start "" "{sys.executable}"\n')

                    f.write('del "%~f0"\n')

                subprocess.Popen(batch_path, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
                from PySide6.QtWidgets import QApplication
                QApplication.quit()

            except Exception as e:
                self.handle_download_fallback(
                    self._ui_text("应用更新失败", "Update Failed"),
                    f"覆盖脚本启动异常：{str(e)}",
                    REPO_URL
                )

    def update_progress(self, value):
        self.progressBar.setValue(value)

    def scrollToAboutCard(self):
        try:
            w = self.aboutHeaderWidget
            self.verticalScrollBar().setValue(w.y())
        except Exception as e:
            print(e)
