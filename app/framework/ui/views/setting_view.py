# coding:utf-8
import logging
import os.path
import subprocess
from pathlib import Path
import sys
from app.framework.i18n import _

from PySide6.QtCore import Qt, QUrl, QThread, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QApplication, QSizePolicy, QFileDialog
from qfluentwidgets import (
    BodyLabel,
    ComboBoxSettingCard,
    ExpandGroupSettingCard,
    ExpandLayout,
    FluentIcon as FIF,
    HyperlinkButton,
    InfoBar,
    LargeTitleLabel,
    MessageBox,
    ProgressBar,
    PushButton,
    ScrollArea,
    PushSettingCard,
    SettingCardGroup as CardGroup,
    SubtitleLabel,
    SwitchSettingCard,
    setFont,
    setTheme,
)

from app.framework.infra.config.app_config import config, isWin11, is_non_chinese_ui_language
from app.framework.infra.config.setting import REPO_URL
from app.framework.infra.runtime.paths import RUNTIME_DIR
from app.framework.infra.events.signal_bus import signalBus
from app.framework.infra.update.updater import (
    UpdateDownloadThread,
    get_app_root,
    get_best_update_candidate,
    get_local_version,
    resolve_batch_dir,
)
from app.framework.infra.runtime.paths import copy_user_data
from app.framework.ui.shared.style_sheet import StyleSheet
from .periodic_base import BaseInterface
from app.framework.ui.widgets.slider_setting_card import SliderSettingCard
from app.framework.ui.widgets.text_edit_card import TextEditCard
from app.framework.i18n import _

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
        BaseInterface.__init__(self)
        self._is_non_chinese_ui = is_non_chinese_ui
        self.setMinimumHeight(140)

        self.mainLayout = QHBoxLayout(self)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(24)

        self.logoLabel = QLabel(self)
        self.logoLabel.setFixedSize(80, 80)
        pixmap = QPixmap(":/resources/logo/sun.png")
        if not pixmap.isNull():
            self.logoLabel.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logoLabel.setText(_("LOGO"))
            self.logoLabel.setStyleSheet("background-color: #333; color: white; border-radius: 10px;")
        self.mainLayout.addWidget(self.logoLabel, 0, Qt.AlignmentFlag.AlignVCenter)

        self.rightLayout = QVBoxLayout()
        self.rightLayout.setSpacing(12)
        self.rightLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.mainLayout.addLayout(self.rightLayout)

        self.row1Layout = QHBoxLayout()
        self.row1Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.titleLabel = SubtitleLabel(_('Author: mofaoss'), self)

        star_text = _(' Visit GitHub ⭐')

        self.githubBtn = PushButton(FIF.GITHUB, star_text, self)

        self.githubBtn.setFixedSize(145, 28)
        self.githubBtn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.row1Layout.addWidget(self.titleLabel)
        self.row1Layout.addSpacing(16)
        self.row1Layout.addWidget(self.githubBtn)
        self.rightLayout.addLayout(self.row1Layout)

        self.row2Layout = QHBoxLayout()
        self.row2Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.qqPrefix = BodyLabel(_('Update QQ group: '), self)
        self.qqLink = HyperlinkButton("", "996710620", self)
        self.qqLink.setToolTip(_('Click to copy QQ group number'))

        self.githubPrefix = BodyLabel("GitHub:", self)
        self.downloadLink = HyperlinkButton("", _('Update now'), self)

        self.downloadLink.setMinimumHeight(24)

        # 2. 核心修复：强行撑开控件内部的留白，给文字底部留出 5 像素的空间 (左, 上, 右, 下)
        # self.downloadLink.setContentsMargins(0, 0, 0, 5)

        # 3. 微调字号：稍微把字号调小一丁点，防止字体溢出绘制框
        font = self.downloadLink.font()
        font.setPointSize(9)  # 默认通常是10
        self.downloadLink.setFont(font)

        # self.downloadLink.setMinimumHeight(24)
        self.row2Layout.addWidget(self.qqPrefix)
        self.row2Layout.addWidget(self.qqLink)
        self.row2Layout.addSpacing(24)
        self.row2Layout.addWidget(self.githubPrefix)
        self.row2Layout.addWidget(self.downloadLink)
        self.rightLayout.addLayout(self.row2Layout)

        self.row3Layout = QHBoxLayout()
        self.row3Layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        local_version = get_local_version() or "-"
        self.localVersionLabel = BodyLabel(_('Current version: {local_version}').format(local_version=local_version), self)

        self.remoteVersionLabel = BodyLabel(_('Latest version: Checking...'), self)

        self.checkUpdateBtn = PushButton(FIF.UPDATE, _('Check for updates'), self)
        self.checkUpdateBtn.setFixedHeight(28)
        self.checkUpdateBtn.setToolTip(_('Check for updates'))
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
        BaseInterface.__init__(self)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.parent = parent
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        self.progressBar = ProgressBar(self)
        self.progressBar.setVisible(False)
        self._is_dialog_open = False

        self.app_name = "SaaAssistantAca"
        self.startup_task_name = f"{self.app_name} {_('Start automatically at boot')}"
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
            _('core settings'), self.scrollWidget)

        # personalization
        self.personalGroup = SettingCardGroup(
            self.tr('Personalization'), self.scrollWidget)
        self.minimizeToTrayCard = SwitchSettingCard(
            FIF.MINIMIZE,
            _('Shrink to tray on close'),
            _('Once enabled, clicking the Close button will hide the program in the system tray instead of exiting the program.'),
            configItem=config.minimizeToTray,
            parent=self.personalGroup
        )
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
            _('Enter at startup'),
            _('Choose which page to enter directly when starting the software'),
            texts=[
                _('Home', msgid="home"), _('Daily', msgid="daily"),
                _('APPs', msgid="apps")
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

        self.backgroundImageCard = PushSettingCard(
            _('Choose picture'),
            FIF.PHOTO,
            _('Background Image'),
            _('Set a custom background image for the main window'),
            parent=self.personalGroup
        )
        self.backgroundImagesRandomButton = PushButton(_('Choose pictures'), self.backgroundImageCard)
        self.backgroundImagesRandomButton.setToolTip(_('Choose multiple images and use one at random on startup'))
        button_index = self.backgroundImageCard.hBoxLayout.indexOf(self.backgroundImageCard.button)
        self.backgroundImageCard.hBoxLayout.insertWidget(
            button_index,
            self.backgroundImagesRandomButton,
            0,
            Qt.AlignmentFlag.AlignRight
        )
        self.backgroundImageCard.hBoxLayout.insertSpacing(
            self.backgroundImageCard.hBoxLayout.indexOf(self.backgroundImageCard.button),
            8
        )
        self.backgroundOpacityCard = SliderSettingCard(
            configItem=config.backgroundOpacity,
            icon=FIF.BRUSH,
            title=_('Background Opacity'),
            content=_('Adjust the opacity of the background image (0-100)'),
            parent=self.personalGroup,
            min_value=0,
            max_value=100
        )

        # about software
        self.aboutSoftwareGroup = SettingCardGroup(
            _('Function related'), self.scrollWidget)
        self.updateOnStartUpCard = SwitchSettingCard(
            FIF.UPDATE,
            self.tr('Check for updates when the application starts'),
            _('If turned on, each time the game version is updated, the coordinates corresponding to the physical activity and the link to the Ancathiya update reminder will be automatically updated.'),
            configItem=config.checkUpdateAtStartUp,
            parent=self.aboutSoftwareGroup
        )
        self.checkPrereleaseForStableCard = SwitchSettingCard(
            FIF.TAG,
            _('Detect beta version updates (official version users)'),
            _('Off by default. After users of the official version turn it on, they will detect both the official version and the test version at the same time; users of the test version will always detect both at the same time.'),
            configItem=config.checkPrereleaseForStable,
            parent=self.aboutSoftwareGroup
        )

        # Core Settings Cards
        self.stealthModeCard = SwitchSettingCard(
            FIF.HIDE,
            _('Stealth mode'),
            _('The game is completely invisible in the background'),
            configItem=config.windowTrackingInput,
            parent=self.coreSettingsGroup
        )
        self.serverCard = ComboBoxSettingCard(
            config.server_interface,
            FIF.GAME,
            _('Game channel selection'),
            _('Please select your regional server'),
            texts=[_('official uniform'), _('Bilibili'), _('International server')],
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
            title=_('Incognito mode visibility'),
            content=_('The lower the value, the more invisible it is: 1=extremely hidden, 255=normal display, it is recommended to set 1'),
            parent=self.scrollWidget,
            min_value=1,
            max_value=255,
        )
        self.saveScaleCacheCard = SwitchSettingCard(
            FIF.SAVE,
            _('Save scaling data'),
            _('If your game window is used permanently, you can choose to save it, so that the running will match faster. If the window size changes frequently, uncheck it.'),
            configItem=config.saveScaleCache,
            parent=self.aboutSoftwareGroup
        )
        self.autoStartTask = SwitchSettingCard(
            FIF.PLAY,
            _('Start task automatically'),
            _('After waking up Ancaxia, it will automatically start running the daily routine. You must first check and configure the automatic opening of the game.'),
            configItem=config.auto_start_task,
            parent=self.aboutSoftwareGroup
        )
        self.autoBootStartup = SwitchSettingCard(
            FIF.POWER_BUTTON,
            _('Start automatically at boot'),
            _('Automatically wake up Ancasia when booting'),
            configItem=config.auto_boot_startup,
            parent=self.aboutSoftwareGroup
        )
        self.informMessage = SwitchSettingCard(
            FIF.HISTORY,
            _('Message notification'),
            _('Whether to turn on physical recovery notifications'),
            configItem=config.inform_message,
            parent=self.aboutSoftwareGroup
        )
        self.proxyCard = TextEditCard(
            config.update_proxies,
            FIF.GLOBE,
            _('proxy port'),
            _("Such as '7890'"),
            _('If you choose to enable a proxy, you need to fill in the proxy port. If you do not enable a proxy, leave it blank.'),
            self.aboutSoftwareGroup
        )

        # Developer Options (开发者选项)
        self.developerOptionsExpandCard = ExpandGroupSettingCard(
            FIF.DEVELOPER_TOOLS,
            _('Developer options'),
            _('Advanced options for diagnostics'),
            self.scrollWidget
        )

        self.isLogCard = SwitchSettingCard(
            FIF.DEVELOPER_TOOLS,
            _('Display image recognition log'),
            _('Show OCR results and OpenCV errors in logs for detailed diagnostics'),
            configItem=config.isLog,
            parent=self.scrollWidget
        )
        self.showScreenshotCard = SwitchSettingCard(
            FIF.PHOTO,
            _('Screenshot of window showing runtime'),
            _('Used for troubleshooting capture regions. Screenshots are saved in SaaAssistantAca/temp and should be deleted manually'),
            configItem=config.showScreenshot,
            parent=self.scrollWidget
        )
        self.isInputLogCard = SwitchSettingCard(
            FIF.COMMAND_PROMPT,
            _('Display simulation input log'),
            _('Opening will display detailed information on simulated input operations such as mouse movements, clicks, key presses, etc. in the log.'),
            configItem=config.isInputLog,
            parent=self.scrollWidget
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

        self._refresh_background_image_card_content()
        if self.parent and self._has_background_image_config():
            self.parent._update_background_image()


        # initialize layout
        self.__initLayout()
        self._connectSignalToSlot()
        self._start_about_header_version_check()

    def __initLayout(self):
        self.settingLabel.move(36, 50)

        self.personalGroup.addSettingCard(self.minimizeToTrayCard)
        self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.enterCard)
        self.personalGroup.addSettingCard(self.zoomCard)
        self.personalGroup.addSettingCard(self.languageCard)
        self.personalGroup.addSettingCard(self.backgroundImageCard)
        self.personalGroup.addSettingCard(self.backgroundOpacityCard)

        # Add Core Settings cards
        self.coreSettingsGroup.addSettingCard(self.stealthModeCard)
        self.coreSettingsGroup.addSettingCard(self.serverCard)
        self.coreSettingsGroup.addSettingCard(self.gameLanguageCard)

        self.aboutSoftwareGroup.addSettingCard(self.updateOnStartUpCard)
        self.aboutSoftwareGroup.addSettingCard(self.checkPrereleaseForStableCard)
        self.aboutSoftwareGroup.addSettingCard(self.saveScaleCacheCard)
        self.aboutSoftwareGroup.addSettingCard(self.autoStartTask)
        self.aboutSoftwareGroup.addSettingCard(self.autoBootStartup)
        self.aboutSoftwareGroup.addSettingCard(self.informMessage)
        self.aboutSoftwareGroup.addSettingCard(self.proxyCard)

        # Add Developer Options cards
        self.developerOptionsExpandCard.addGroupWidget(self.windowTrackingAlphaCard)
        self.developerOptionsExpandCard.addGroupWidget(self.isLogCard)
        self.developerOptionsExpandCard.addGroupWidget(self.showScreenshotCard)
        self.developerOptionsExpandCard.addGroupWidget(self.isInputLogCard)
        self.developerOptionsExpandCard.setExpand(False)

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
        self.expandLayout.addWidget(self.developerOptionsExpandCard)

    def _showRestartTooltip(self):
        """ show restart tooltip """
        # from app.framework.infra.config.app_config import is_non_chinese_ui_language
        # is_english = is_non_chinese_ui_language()

        # title = 'Updated successfully' if is_english else '更新成功'
        # content = 'Configuration takes effect after restart' if is_english else '重启后配置生效'

        InfoBar.success(
            _('Updated successfully'),
            _('Configuration takes effect after restart'),
            duration=2000,
            parent=self
        )

    def _connectSignalToSlot(self):
        """ connect signal to slot """
        config.appRestartSig.connect(self._showRestartTooltip)
        signalBus.windowTrackingStealthChanged.connect(self._sync_stealth_controls)
        self.stealthModeCard.checkedChanged.connect(self._on_stealth_mode_toggled)

        # personalization
        config.themeChanged.connect(setTheme)
        self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)
        self.backgroundImageCard.clicked.connect(self._on_choose_background_image)
        self.backgroundImagesRandomButton.clicked.connect(self._on_choose_random_background_images)
        self.autoBootStartup.checkedChanged.connect(self.set_windows_start)

        if hasattr(self.aboutHeaderWidget, "githubBtn"):
            self.aboutHeaderWidget.githubBtn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        if hasattr(self.aboutHeaderWidget, "qqLink"):
            self.aboutHeaderWidget.qqLink.clicked.connect(self._copy_qq_group_number)
        if hasattr(self.aboutHeaderWidget, "checkUpdateBtn"):
            self.aboutHeaderWidget.checkUpdateBtn.clicked.connect(self._on_manual_update_clicked)

    def _on_choose_background_image(self):
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self, _("Select Background Image", msgid="select_background_image"), "", "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)"
        )
        if not file_path:
            return

        self._backup_background_images([file_path])
        resolved_path = self._resolve_background_path(file_path) or file_path
        config.set(config.backgroundImages, [])
        config.set(config.backgroundImage, resolved_path)
        self._refresh_background_image_card_content()

        if self.parent:
            self.parent._update_background_image()

    def _on_choose_random_background_images(self):
        file_paths, _selected_filter = QFileDialog.getOpenFileNames(
            self, _("Select Background Images", msgid="select_background_images"), "", "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)"
        )
        normalized_paths = self._normalize_background_paths(file_paths)
        if not normalized_paths:
            return

        self._backup_background_images(normalized_paths)
        resolved_paths = [self._resolve_background_path(path) or path for path in normalized_paths]
        config.set(config.backgroundImages, resolved_paths)
        config.set(config.backgroundImage, resolved_paths[0])
        self._refresh_background_image_card_content()

        if self.parent:
            self.parent._update_background_image()

    @staticmethod
    def _normalize_background_paths(paths):
        normalized = []
        for path in paths or []:
            path = str(path or "").strip()
            if path:
                normalized.append(path)

        return list(dict.fromkeys(normalized))

    @staticmethod
    def _background_backup_dir() -> Path:
        return RUNTIME_DIR / "backgrounds"

    def _backup_background_images(self, file_paths):
        backup_dir = self._background_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        for file_path in self._normalize_background_paths(file_paths):
            path = Path(file_path)
            if path.exists():
                copy_user_data(path, backup_dir=backup_dir)

    def _resolve_background_path(self, file_path: str) -> str:
        file_path = str(file_path or "").strip()
        if not file_path:
            return ""

        if os.path.exists(file_path):
            return file_path

        backup_path = self._background_backup_dir() / Path(file_path).name
        if backup_path.exists():
            return str(backup_path)

        return ""

    def _get_random_background_paths(self):
        return self._normalize_background_paths(config.backgroundImages.value)

    def _has_background_image_config(self) -> bool:
        return bool(self._get_random_background_paths() or str(config.backgroundImage.value or "").strip())

    def _refresh_background_image_card_content(self):
        random_paths = self._get_random_background_paths()
        if random_paths:
            self.backgroundImageCard.setContent(
                _('Random background ({count} images)').format(count=len(random_paths))
            )
            return

        self.backgroundImageCard.setContent(str(config.backgroundImage.value or ""))

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
            self.aboutHeaderWidget.checkUpdateBtn.setText(_('Check for updates'))

        self._on_about_header_version_checked(payload)

        download_url = str(payload.get("download_url") or "").strip()
        if download_url:
            InfoBar.warning(
                _('New version detected'),
                _('Please click [Update now] or go to QQ group for update'),
                duration=3000,
                parent=self
            )
        else:
            InfoBar.success(
                _('Already the latest'),
                "",
                duration=3000,
                parent=self
            )

    def _copy_qq_group_number(self):
        QApplication.clipboard().setText(_("996710620"))
        InfoBar.success(
            _('QQ group number copied'),
            _("996710620"),
            duration=2000,
            parent=self
        )

    def _start_about_header_version_check(self):
        self.versionCheckThread = VersionCheckThread(self)
        self.versionCheckThread.finishedSignal.connect(self._on_about_header_version_checked)
        self.versionCheckThread.start()

    def _on_stealth_mode_toggled(self, checked: bool):
        alpha = 1 if checked else 255
        config.set(config.windowTrackingInput, bool(checked))
        config.set(config.windowTrackingAlpha, alpha)
        signalBus.windowTrackingStealthChanged.emit(bool(checked), int(alpha))

    def _set_stealth_switch_visual_state(self, checked: bool):
        switch_button = getattr(getattr(self, "stealthModeCard", None), "switchButton", None)
        if switch_button is None:
            return
        old_state = switch_button.blockSignals(True)
        switch_button.setChecked(bool(checked))
        switch_button.setText(self.tr('On') if checked else self.tr('Off'))
        switch_button.blockSignals(old_state)

    def _sync_stealth_controls(self, checked: bool, alpha: int):
        try:
            self._set_stealth_switch_visual_state(bool(checked))
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
                _('Added self-start successfully'),
                _('Auto-start has been created through a scheduled task'),
                isClosable=True,
                duration=2000,
                parent=self
            )
        except subprocess.CalledProcessError as e:
            InfoBar.error(
                _('Adding auto-start failed'),
                _('Failed to create scheduled task:') + f"{e.stderr}",
                isClosable=True,
                duration=2000,
                parent=self
            )
        except Exception as e:
            InfoBar.error(
                _('Adding auto-start failed'),
                _('Failed to create startup file:') + f"{e}",
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
                _('Deletion started successfully'),
                _('Autostart is turned off'),
                isClosable=True,
                duration=2000,
                parent=self
            )
        except subprocess.CalledProcessError as e:
            if "找不到系统指定的" in e.stderr or "cannot find" in e.stderr.lower():
                InfoBar.warning(
                    _('Task does not exist'),
                    _('The scheduled task may have been deleted'),
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    _('Delete auto-start failed'),
                    _('Failed to delete scheduled task:') + f"{e.stderr}",
                    isClosable=True,
                    duration=2000,
                    parent=self
                )
        except Exception as e:
            InfoBar.error(
                _('Delete auto-start failed'),
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
                self.aboutHeaderWidget.downloadLink.setText(_('Already the latest'))
                self.aboutHeaderWidget.downloadLink.setUrl("")
                self.aboutHeaderWidget.downloadLink.clicked.connect(
                    lambda: InfoBar.success(
                        _('Already the latest'),
                        (""),
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
                self.aboutHeaderWidget.downloadLink.setText(_('Update now'))
                self.aboutHeaderWidget.downloadLink.clicked.connect(lambda: self.start_unified_download(download_url))

        if hasattr(self.aboutHeaderWidget, "localVersionLabel"):
            self.aboutHeaderWidget.localVersionLabel.setText(
                _('Current version: {local_version}').format(local_version=local_version)
            )

        if latest_version:
            if hasattr(self.aboutHeaderWidget, "remoteVersionLabel"):
                self.aboutHeaderWidget.remoteVersionLabel.setText(
                    _('Latest version: {latest_version}').format(latest_version=latest_version)
                )
        else:
            if hasattr(self.aboutHeaderWidget, "remoteVersionLabel"):
                self.aboutHeaderWidget.remoteVersionLabel.setText(
                    _('Latest version: {local_version}').format(local_version=local_version)
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

        title = _('Update ready')

        if is_exe:
            content = _('New version of SaaAssistantAca has been downloaded.<br/><br/>Close app and run installer now?')
        else:
            content = _('Update files extracted.<br/><br/>Restart app to apply updates?')

        message_box = MessageBox(title, content, self.parent.window())
        if message_box.exec():
            try:
                batch_dir = resolve_batch_dir(downloaded_path)
                os.makedirs(batch_dir, exist_ok=True)
                batch_path = os.path.join(batch_dir, "apply_update.bat")

                with open(batch_path, "w", encoding="gbk") as f:
                    f.write('@echo off\n')
                    f.write('echo Waiting for app to close...\n')
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
                    _('Application update failed'),
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
