# coding:utf-8
import os.path
import subprocess
import sys
import html
from functools import partial

from PySide6.QtCore import Qt, QUrl, QThread
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QWidget, QLabel
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar
from qfluentwidgets import SettingCardGroup as CardGroup
from qfluentwidgets import (SwitchSettingCard, PrimaryPushSettingCard, ScrollArea,
                            ComboBoxSettingCard, ExpandLayout, setTheme, setFont, MessageBox, ProgressBar,
                            )

from ..common.config import config, isWin11, is_non_chinese_ui_language
from ..common.logger import logger
from ..common.setting import QQ, REPO_URL
from ..common.signal_bus import signalBus
from ..common.style_sheet import StyleSheet
from utils.updater_utils import get_local_version, get_github_release_channels, is_remote_version_newer, is_prerelease_version
from ..repackage.slider_setting_card import SliderSettingCard
from ..repackage.text_edit_card import TextEditCard


class UpdatingThread(QThread):

    def __init__(self, updater):
        super().__init__()
        self.updater = updater

    def run(self):
        self.updater.run()


class SettingCardGroup(CardGroup):

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        setFont(self.titleLabel, 14, QFont.Weight.DemiBold)


class SettingInterface(ScrollArea):
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
        # 获取当前应用路径
        if getattr(sys, 'frozen', False):
            # 打包后的可执行文件
            self.app_path = sys.executable
        else:
            # 脚本运行模式
            self.app_path = sys.argv[0]

        # setting label
        self.settingLabel = QLabel(self.tr("Settings"), self)

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
                self._ui_text('展示页', 'Display'), self._ui_text('日常', 'Daily'),
                self._ui_text('小工具', 'Tools')
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

        # update software
        self.aboutSoftwareGroup = SettingCardGroup(
            self._ui_text("软件相关", "Software"), self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            self.tr('Check for updates when the application starts'),
            self._ui_text('如果开启，每次游戏版本更新会自动更新对应活动刷体力的坐标和安卡希雅·自律姬提醒的链接',
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
        self.serverCard = ComboBoxSettingCard(
            config.server_interface,
            FIF.GAME,
            self._ui_text('游戏渠道选择', 'Server channel'),
            self._ui_text("请选择你所在的区服", "Choose your server channel"),
            texts=[self._ui_text('官服', 'Official'), self._ui_text('b服', 'Bilibili'), self._ui_text('国际服', 'Global')],
            parent=self.aboutSoftwareGroup
        )
        self.gameLanguageCard = ComboBoxSettingCard(
            config.game_language,
            FIF.LANGUAGE,
            '游戏语言 / Game Language',
            'Used for automation OCR matching, supports only Simplified/Traditional Chinese'
            if is_non_chinese_ui_language() else '用于自动化OCR匹配，仅支持简体/繁体中文',
            texts=['简体中文 / Simplified Chinese', '繁體中文 / Traditional Chinese'],
            parent=self.aboutSoftwareGroup
        )
        self.isLogCard = SwitchSettingCard(
            FIF.DEVELOPER_TOOLS,
            self._ui_text('展示OCR识别结果', 'Show OCR results'),
            self._ui_text('打开将在日志中显示ocr识别结果，获得更详细的日志信息',
                          'Show OCR recognition results in logs for more detailed diagnostics'),
            configItem=config.isLog,
            parent=self.aboutSoftwareGroup
        )
        self.showScreenshotCard = SwitchSettingCard(
            FIF.PHOTO,
            self._ui_text('展示运行时的窗口截图', 'Show runtime screenshots'),
            self._ui_text('用于在查错时查看是否正确截取了游戏对应位置的画面，截取的所有画面会保存在SaaAutomataAcacia/temp下，需要手动删除',
                          'Used for troubleshooting capture regions. Screenshots are saved in SaaAutomataAcacia/temp and should be deleted manually'),
            configItem=config.showScreenshot,
            parent=self.aboutSoftwareGroup
        )
        self.windowTrackingInputCard = SwitchSettingCard(
            FIF.MOVE,
            self._ui_text('后台不抢鼠标', 'Don\'t take mouse control'),
            self._ui_text('开启后后台点击和滚轮尽量不影响你当前鼠标操作',
                          'Enable background input that minimizes interference with your current mouse actions'),
            configItem=config.windowTrackingInput,
            parent=self.aboutSoftwareGroup
        )
        self.windowTrackingAlphaCard = SliderSettingCard(
            configItem=config.windowTrackingAlpha,
            icon=FIF.HIDE,
            title=self._ui_text('窗口追踪透明度', 'Tracking window opacity'),
            content=self._ui_text('数值越低越隐形：1=极度隐藏，255=正常显示',
                                  'Lower value means more invisible: 1 = highly hidden, 255 = normal visibility'),
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
        self.autoScaling = SwitchSettingCard(
            FIF.BACK_TO_WINDOW,
            self._ui_text('自动缩放比例', 'Auto scaling'),
            self._ui_text('默认开启，在启动安卡希雅·自律姬时如果发现游戏窗口比例不是16:9会自动缩放成1920*1080',
                          'Enabled by default. If the game is not 16:9, it auto-resizes to 1920*1080 on startup'),
            configItem=config.autoScaling,
            parent=self.aboutSoftwareGroup
        )
        self.autoStartTask = SwitchSettingCard(
            FIF.PLAY,
            self._ui_text('自动开始任务', 'Auto start tasks'),
            self._ui_text('打开安卡希雅·自律姬自动开始运行日常，必须先勾选并配置好自动打开游戏',
                          'Automatically starts daily tasks when SaaAutomataAcacia launches. Requires auto-open game to be enabled and configured first'),
            configItem=config.auto_start_task,
            parent=self.aboutSoftwareGroup
        )
        self.autoBootStartup = SwitchSettingCard(
            FIF.POWER_BUTTON,
            self._ui_text('开机自启', 'Start on boot'),
            self._ui_text('开机时自动打开安卡希雅·自律姬', 'Launch SaaAutomataAcacia automatically when Windows starts'),
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

        # application
        self.aboutGroup = SettingCardGroup(self.tr('About'), self.scrollWidget)
        self.proxyCard = TextEditCard(
            config.update_proxies,
            FIF.GLOBE,
            self._ui_text('代理端口', 'Proxy port'),
            self._ui_text("如‘7890’", "e.g. '7890'"),
            self._ui_text('如果选择开代理则需要填入代理端口，不开代理则置空',
                          'Fill proxy port when using proxy; leave empty when not using proxy'),
            self.aboutGroup
        )
        self.feedbackCard = PrimaryPushSettingCard(
            self._ui_text('前往GitHub', 'Open GitHub'),
            FIF.FEEDBACK,
            self._ui_text('提供反馈', 'Feedback'),
            self._ui_text('GitHub作者：mofaoss，QQ群：', 'GitHub author: mofaoss, QQ group: ') + QQ,
            self.aboutGroup
        )
        self.aboutCard = PrimaryPushSettingCard(
            self.tr('Check update'),
            "app/resource/images/logo.png",
            self.tr('About'),
            self._ui_text("本助手免费开源，当前版本：", "This assistant is free and open source. Current version: ") + get_local_version(),
            self.aboutGroup
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

    def __initLayout(self):
        self.settingLabel.move(36, 50)

        self.aboutCard.vBoxLayout.addWidget(self.progressBar)

        self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.enterCard)
        self.personalGroup.addSettingCard(self.zoomCard)
        self.personalGroup.addSettingCard(self.languageCard)

        self.aboutSoftwareGroup.addSettingCard(self.windowTrackingAlphaCard)
        self.aboutSoftwareGroup.addSettingCard(self.windowTrackingInputCard)
        self.aboutSoftwareGroup.addSettingCard(self.updateOnStartUpCard)
        self.aboutSoftwareGroup.addSettingCard(self.checkPrereleaseForStableCard)
        self.aboutSoftwareGroup.addSettingCard(self.serverCard)
        self.aboutSoftwareGroup.addSettingCard(self.gameLanguageCard)
        self.aboutSoftwareGroup.addSettingCard(self.isLogCard)
        self.aboutSoftwareGroup.addSettingCard(self.showScreenshotCard)
        self.aboutSoftwareGroup.addSettingCard(self.saveScaleCacheCard)
        self.aboutSoftwareGroup.addSettingCard(self.autoScaling)
        self.aboutSoftwareGroup.addSettingCard(self.autoStartTask)
        self.aboutSoftwareGroup.addSettingCard(self.autoBootStartup)
        self.aboutSoftwareGroup.addSettingCard(self.informMessage)

        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.proxyCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        # add setting card group to layout
        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.aboutSoftwareGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def _showRestartTooltip(self):
        """ show restart tooltip """
        InfoBar.success(
            self._ui_text('更新成功', 'Updated successfully'),
            self._ui_text('重启后配置生效', 'Configuration takes effect after restart'),
            duration=2000,
            parent=self
        )

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else zh_text

    def _connectSignalToSlot(self):
        """ connect signal to slot """
        config.appRestartSig.connect(self._showRestartTooltip)
        signalBus.windowTrackingStealthChanged.connect(self._sync_stealth_controls)

        # personalization
        config.themeChanged.connect(setTheme)
        self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)
        self.autoBootStartup.checkedChanged.connect(self.set_windows_start)

        # check update
        self.aboutCard.clicked.connect(self.check_update)
        # self.aboutCard.button.setEnabled(False)

        # about
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))

    def _sync_stealth_controls(self, checked: bool, alpha: int):
        try:
            self.windowTrackingInputCard.setChecked(bool(checked), emit=False)
        except Exception:
            pass
        try:
            if hasattr(self, "windowTrackingAlphaCard") and self.windowTrackingAlphaCard is not None:
                self.windowTrackingAlphaCard.sync_from_config()
        except Exception:
            pass

    def _select_update_candidate(self, local_version: str, release_channels: dict):
        stable = release_channels.get("latest") if isinstance(release_channels, dict) else None
        prerelease = release_channels.get("prerelease") if isinstance(release_channels, dict) else None
        should_check_prerelease = is_prerelease_version(local_version) or bool(config.checkPrereleaseForStable.value)

        candidates = []
        for channel_name, release_data in (("latest", stable), ("prerelease", prerelease)):
            if channel_name == "prerelease" and not should_check_prerelease:
                continue
            if not release_data:
                continue
            remote_version = release_data.get("version")
            if not remote_version:
                continue
            if is_remote_version_newer(local_version, remote_version):
                candidates.append({
                    "channel": channel_name,
                    "version": remote_version,
                    "download_url": release_data.get("download_url"),
                    "is_prerelease": channel_name == "prerelease"
                })

        if not candidates:
            return None

        best = candidates[0]
        for candidate in candidates[1:]:
            if is_remote_version_newer(best["version"], candidate["version"]):
                best = candidate

        return best

    def _log_clickable_update_links(self, best: dict, local_version: str):
        download_url = str(best.get("download_url") or "").strip()
        update_tag_zh = "测试版" if best.get("is_prerelease") else "新版本"
        update_tag_en = "pre-release" if best.get("is_prerelease") else "update"

        if download_url:
            download_anchor = f"<a href=\"{html.escape(download_url, quote=True)}\">{self._ui_text('点击下载最新', 'Click to download latest')}</a>"
            logger.warning(self._ui_text(
                f"【检查更新】发现{update_tag_zh} {local_version} → {best['version']}\n"
                f"{download_anchor}",
                f"[Check Update] New {update_tag_en} found {local_version} -> {best['version']}\n"
                f"{download_anchor}"
            ))
            return

        logger.warning(self._ui_text(
            f"【检查更新】发现{update_tag_zh} {local_version} → {best['version']}\n"
            f"暂未找到可直接下载的安装包链接",
            f"[Check Update] New {update_tag_en} found {local_version} -> {best['version']}\n"
            f"No direct downloadable installer URL found"
        ))

    def set_windows_start(self, is_checked):
        if is_checked:
            self._enable_windows()
        else:
            self._disable_windows()

    def _enable_windows(self):
        """Windows 启用自启"""
        try:
            # 获取应用程序所在目录
            app_dir = os.path.dirname(self.app_path)
            cmd_file_path = os.path.join(app_dir, "saa_startup.cmd")

            # 创建 cmd 文件内容
            cmd_content = f'@echo off\ncd "{app_dir}"\nstart "" "{self.app_path}"'

            # 写入 cmd 文件
            with open(cmd_file_path, 'w', encoding='utf-8') as f:
                f.write(cmd_content)

            # 创建计划任务
            task_command = [
                'schtasks', '/create',
                '/tn', self.startup_task_name,
                '/tr', f'cmd.exe /c "{cmd_file_path}"',  # 要执行的命令
                '/sc', 'onlogon',  # 触发条件：用户登录时
                '/rl', 'highest',  # 使用最高权限
                '/f'  # 强制创建（如果已存在则覆盖）
            ]

            result = subprocess.run(task_command, shell=True, check=True,
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
        """Windows 禁用自启"""
        try:
            # 删除计划任务
            result = subprocess.run(['schtasks', '/delete', '/tn', self.startup_task_name, '/f'],
                                  shell=True, check=True, capture_output=True, text=True)

            # 删除 cmd 文件
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

    def check_update(self):
        local_version = get_local_version()
        release_channels = get_github_release_channels(REPO_URL)
        stable = release_channels.get("latest") if isinstance(release_channels, dict) else None
        prerelease = release_channels.get("prerelease") if isinstance(release_channels, dict) else None
        best = self._select_update_candidate(local_version, release_channels)

        if best is None:
            if not stable and not prerelease:
                InfoBar.error(
                    self._ui_text('检查更新失败', 'Update check failed'),
                    self._ui_text('未获取到仓库版本信息，请稍后重试', 'No repository release data found. Please try again later'),
                    isClosable=True,
                    duration=5000,
                    parent=self
                )
                logger.warning(self._ui_text(
                    "【检查更新】未获取到仓库 release 版本（latest/prerelease）",
                    "[Check Update] No repository release versions found (latest/prerelease)"
                ))
            return

        self._log_clickable_update_links(best, local_version)
        InfoBar.warning(
            self._ui_text('发现测试版' if best.get("is_prerelease") else '发现新版本',
                          'Pre-release available' if best.get("is_prerelease") else 'Update available'),
            self._ui_text('请在日志中点击“点击下载最新”以下载安装包',
                          'Click "Click to download latest" in log to download installer'),
            isClosable=True,
            duration=8000,
            parent=self
        )

    def start_download(self, updater):
        self.progressBar.setValue(0)
        self.progressBar.setVisible(True)
        self.updating_thread = UpdatingThread(updater)
        signalBus.checkUpdateSig.connect(self.update_progress)
        self.updating_thread.finished.connect(partial(self.update_finished, updater.download_file_path))
        self.updating_thread.start()

    def update_progress(self, value):
        """ Update the progress bar """
        self.progressBar.setValue(value)

    def update_finished(self, zip_path):
        """ Hide progress bar and show completion message """
        self.progressBar.setVisible(False)
        if os.path.exists(zip_path):
            if self._is_dialog_open:
                return
            title = self._ui_text('更新完成', 'Update ready')
            content = self._ui_text(f'压缩包已下载至{zip_path}，即将重启更新',
                                    f'Package downloaded to {zip_path}. Restarting to update')
            self._is_dialog_open = True
            try:
                message_box = MessageBox(title, content, self.parent.window())
                message_box.cancelButton.setVisible(False)
                if message_box.exec():
                    subprocess.Popen([sys.executable, 'update.py', zip_path])
                    self.parent.close()
            finally:
                self._is_dialog_open = False
        else:
            InfoBar.error(
                self._ui_text('更新下载失败', 'Update download failed'),
                self._ui_text(f'请前往 {REPO_URL}/releases或者{QQ} 群下载更新包',
                              f'Please download update package from {REPO_URL}/releases or QQ group {QQ}'),
                isClosable=True,
                duration=-1,
                parent=self
            )

    def scrollToAboutCard(self):
        """ scroll to example card """
        try:
            w = self.aboutCard
            self.verticalScrollBar().setValue(w.y())
        except Exception as e:
            print(e)
