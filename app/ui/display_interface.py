import os
import random

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath, QBrush
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
)
from qfluentwidgets import ScrollArea, FluentIcon, CardWidget, FlyoutView, Flyout

from app.common.config import config, is_non_chinese_ui_language, Language, resolve_configured_locale
from app.common.signal_bus import signalBus
from app.common.setting import REPO_URL
from app.common.style_sheet import StyleSheet
from app.common.utils import get_local_version, get_github_release_channels, is_remote_version_newer, is_prerelease_version

from app.repackage.link_card import LinkCardView
from app.repackage.samplecardview import SampleCardView


class BannerWidget(QWidget):
    """Banner widget"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(350)
        self._is_simplified_ui = self._is_simplified_ui_language()
        self._is_non_chinese_ui = is_non_chinese_ui_language()

        self.vBoxLayout = QVBoxLayout(self)
        # 大标题
        self.galleryLabel = QLabel(
            f'安卡希雅·自律姬 {get_local_version()}\nSaaAutomataAcacia', self
        )
        self.galleryLabel.setStyleSheet(
            "color: #ECF9F8;font-size: 30px; font-weight: 600;"
        )

        # 创建阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)  # 阴影模糊半径
        shadow.setColor(Qt.black)  # 阴影颜色
        shadow.setOffset(1.2, 1.2)  # 阴影偏移量

        # 将阴影效果应用于小部件
        self.galleryLabel.setGraphicsEffect(shadow)

        self.basedir = "app/resource/images/display"
        random_number = random.randint(1, 9)
        # banner_path = os.path.join(self.basedir, f"background_{random_number}.jpg")
        banner_path = os.path.join(self.basedir, f"101.png")
        self.banner = QPixmap(banner_path)
        # 超链接卡片
        self.linkCardView = LinkCardView(self)
        # 设置边界
        self.linkCardView.setContentsMargins(0, 0, 0, 36)
        self.galleryLabel.setObjectName("galleryLabel")
        # 纵向布局
        linkCardLayout = QHBoxLayout()
        linkCardLayout.addWidget(self.linkCardView)
        linkCardLayout.setAlignment(Qt.AlignBottom)
        # 设置横向布局使靠左上显示
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addLayout(linkCardLayout)
        self.vBoxLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.linkCardView.addCard(
            FluentIcon.GITHUB,
            self._ui_text("GitHub地址", "GitHub"),
            self._ui_text("你的星星\n就是我的动力|･ω･)", "Your stars\nkeep me motivated |･ω･)"),
            REPO_URL,
        )
        self.linkCardView.addCard(
            FluentIcon.INFO,
            self._ui_text("支持作者", "Support Author"),
            self._ui_text("点击查看\n赞助二维码", "Click to view\nsupport QR") if self._is_simplified_ui else self._ui_text("前往 Ko-fi\n支持作者", "Visit Ko-fi\nto support"),
            "" if self._is_simplified_ui else "https://ko-fi.com/mofa",
            on_click=self._show_support_qr if self._is_simplified_ui else None,
        )
        self._add_update_card()

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

    def _add_update_card(self):
        local_version = get_local_version() or "N/A"
        release_channels = get_github_release_channels(REPO_URL)
        best = self._select_update_candidate(local_version, release_channels)
        is_prerelease = bool(best and best.get("is_prerelease"))

        if best and best.get("download_url"):
            title = self._ui_text("更新提示", "Update")
            content = self._ui_text(
                f"{'测试版 ' if is_prerelease else ''}{local_version} → {best['version']}\n点击下载最新",
                f"{'Pre-release ' if is_prerelease else ''}{local_version} -> {best['version']}\nClick to download latest"
            )
            url = best.get("download_url")
        elif best:
            title = self._ui_text("更新提示", "Update")
            content = self._ui_text(
                f"{'测试版 ' if is_prerelease else ''}{local_version} → {best['version']}\n暂未找到直链",
                f"{'Pre-release ' if is_prerelease else ''}{local_version} -> {best['version']}\nDirect download unavailable"
            )
            url = ""
        else:
            title = self._ui_text("更新提示", "Update")
            content = self._ui_text(
                f"当前已是最新\n版本 {local_version}",
                f"You're up to date\nVersion {local_version}"
            )
            url = ""

        self.linkCardView.addCard(
            FluentIcon.DOWNLOAD,
            title,
            content,
            url,
        )

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else self.tr(zh_text)

    @staticmethod
    def _is_simplified_ui_language():
        language = config.language.value
        if language == Language.CHINESE_SIMPLIFIED:
            return True
        if language != Language.AUTO:
            return False

        locale_name = resolve_configured_locale(language).name().replace('-', '_')
        return locale_name in {"zh_CN", "zh_SG"} or locale_name.startswith("zh_Hans")

    def _show_support_qr(self, source_widget):
        view = FlyoutView(
            title=self._ui_text("赞助作者", "Support Author"),
            content=self._ui_text("如果这个助手帮助到你，可以考虑赞助作者一杯奶茶(>ω･* )ﾉ",
                                  "If this assistant helps you, consider buying the author a coffee (>ω･* )ﾉ"),
            image="asset/support.jpg",
            isClosable=True,
        )
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)

        flyout = Flyout.make(view, source_widget, self)
        view.closed.connect(flyout.close)

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        # 提示指示 QPainter 在缩放像素图（pixmap）时应该使用平滑的像素变换 | 开启了抗锯齿
        painter.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        # 指示不使用任何笔进行绘制，通常用于当你只想填充形状而不绘制它们的边界时
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        # 表示使用交叉数法则，即从任意方向绘制一条线，与多边形相交的次数奇数时填充，偶数时不填充
        path.setFillRule(Qt.WindingFill)
        w, h = self.width(), 200
        path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
        path.addRect(QRectF(0, h - 50, 50, 50))
        path.addRect(QRectF(w - 50, 0, 50, 50))
        path.addRect(QRectF(w - 50, h - 50, 50, 50))
        path = path.simplified()
        # 计算图片的高度
        try:
            image_height = self.width() * self.banner.height() // self.banner.width()
            pixmap = self.banner.scaled(
                self.width(),
                image_height,
                aspectRatioMode=Qt.KeepAspectRatio,
                transformMode=Qt.SmoothTransformation,
            )
        except ZeroDivisionError as e:
            print(f"图片加载失败:{e}")
            # logging.error(f"图片加载失败:{e}")
        path.addRect(QRectF(0, h, w, self.height() - h))
        painter.fillPath(path, QBrush(pixmap))


class DisplayInterface(ScrollArea):
    """Home interface"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.windowTrackingQuickSwitchCard = None
        self.gameLanguageNoticeCard = CardWidget(self.view)
        self.gameLanguageNoticeLayout = QVBoxLayout(self.gameLanguageNoticeCard)
        self.gameLanguageNoticeTitle = QLabel("Language Notice", self.gameLanguageNoticeCard)
        self.gameLanguageNoticeLabel = QLabel(self.gameLanguageNoticeCard)
        self.basedir = "app/resource/images/display"

        self.__initWidget()
        self.loadSamples()

    def __initWidget(self):
        self.view.setObjectName("view")
        self.setObjectName("displayInterface")
        StyleSheet.DISPLAY_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.addWidget(self.banner)
        self.gameLanguageNoticeCard.setFixedHeight(90)
        self.gameLanguageNoticeLayout.setContentsMargins(24, 14, 24, 14)
        self.gameLanguageNoticeLayout.setSpacing(4)
        self.gameLanguageNoticeTitle.setStyleSheet("font-size: 16px; font-weight: 500;")
        self.gameLanguageNoticeTitle.setText(
            "Language Notice" if self._is_non_chinese_ui else self.tr("语言提示")
        )
        self.gameLanguageNoticeLabel.setText(
            "Note: Game language for automation supports only Simplified/Traditional Chinese."
            if self._is_non_chinese_ui
            else self.tr("注意：自动化识别的游戏语言目前仅支持简体中文与繁体中文。")
        )
        self.gameLanguageNoticeLabel.setStyleSheet("color: red;")
        self.gameLanguageNoticeLabel.setWordWrap(True)
        self.gameLanguageNoticeLayout.addWidget(self.gameLanguageNoticeTitle)
        self.gameLanguageNoticeLayout.addWidget(self.gameLanguageNoticeLabel)
        self.gameLanguageNoticeCard.setVisible(is_non_chinese_ui_language())
        self.vBoxLayout.addWidget(self.gameLanguageNoticeCard)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else self.tr(zh_text)

    def _sync_window_tracking_quick_switch(self):
        if self.windowTrackingQuickSwitchCard is not None:
            stealth_on = bool(config.windowTrackingInput.value) and int(config.windowTrackingAlpha.value) == 1
            self.windowTrackingQuickSwitchCard.setChecked(stealth_on, emit=False)

    def _toggle_stealth_mode(self, checked: bool):
        alpha = 1 if checked else 255
        config.set(config.windowTrackingInput, checked)
        config.set(config.windowTrackingAlpha, alpha)
        signalBus.windowTrackingStealthChanged.emit(bool(checked), int(alpha))

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_window_tracking_quick_switch()

    def loadSamples(self):
        """load samples"""

        quick_jump = SampleCardView("Quick Access" if self._is_non_chinese_ui else self.tr("快捷跳转"), self.view)
        # 跳转设置
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "setting.svg"),
            title="Settings" if self._is_non_chinese_ui else "设置",
            content="App settings" if self._is_non_chinese_ui else self.tr("软件相关设置"),
            routeKey="settingInterface",
            index=0,
        )
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "play.svg"),
            title="Main Tasks" if self._is_non_chinese_ui else "功能界面",
            content="Configure quickly and run with one click" if self._is_non_chinese_ui else self.tr("简单设置后一键种草！"),
            routeKey="Home-Interface",
            index=0,
        )
        # 使用教程跳转
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "explain.svg"),
            title="Tutorial" if self._is_non_chinese_ui else "使用教程",
            content="Read the guide to get started quickly" if self._is_non_chinese_ui else self.tr("查看教程快速使用"),
            routeKey="Help-Interface",
            index=0,
        )
        self.windowTrackingQuickSwitchCard = quick_jump.addSampleCard_Switch(
            icon=os.path.join(self.basedir, "electronics.svg"),
            title="Stealth Mode" if self._is_non_chinese_ui else "隐身模式",
            content="ON: no-mouse-steal + opacity=1; OFF: normal display + disable no-mouse-steal"
            if self._is_non_chinese_ui else self.tr("完全后台隐身运行游戏"),
            checked=bool(config.windowTrackingInput.value) and int(config.windowTrackingAlpha.value) == 1,
            on_toggle=self._toggle_stealth_mode,
        )
        self._sync_window_tracking_quick_switch()
        self.vBoxLayout.addWidget(quick_jump)
