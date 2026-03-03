import os

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGraphicsDropShadowEffect,
)
from qfluentwidgets import ScrollArea, CardWidget

from app.common.config import config, is_non_chinese_ui_language
from app.common.signal_bus import signalBus
from app.common.style_sheet import StyleSheet
from utils.updater_utils import get_local_version

from app.repackage.samplecardview import SampleCardView


class BannerWidget(QWidget):
    """Banner widget"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedHeight(350)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel(
            f'安卡希雅·自律姬 {get_local_version()}\nSaaAutomataAcacia', self
        )
        self.galleryLabel.setStyleSheet(
            "color: #ECF9F8;font-size: 30px; font-weight: 600;"
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(1.2, 1.2)

        self.galleryLabel.setGraphicsEffect(shadow)

        self.basedir = "app/resource/images/display"
        banner_path = os.path.join(self.basedir, "101.png")
        self.banner = QPixmap(banner_path)
        self.galleryLabel.setObjectName("galleryLabel")

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        try:
            painter.setRenderHints(
                QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing
            )
            painter.setPen(Qt.PenStyle.NoPen)

            path = QPainterPath()
            path.setFillRule(Qt.FillRule.WindingFill)
            w, h = self.width(), 200
            path.addRoundedRect(QRectF(0, 0, w, h), 10, 10)
            path.addRect(QRectF(0, h - 50, 50, 50))
            path.addRect(QRectF(w - 50, 0, 50, 50))
            path.addRect(QRectF(w - 50, h - 50, 50, 50))
            path = path.simplified()

            pixmap = QPixmap()
            if not self.banner.isNull() and self.banner.width() > 0:
                image_height = self.width() * self.banner.height() // self.banner.width()
                pixmap = self.banner.scaled(
                    self.width(),
                    image_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            path.addRect(QRectF(0, h, w, self.height() - h))
            painter.fillPath(path, QBrush(pixmap))
        finally:
            painter.end()


class DisplayInterface(ScrollArea):
    """Display interface"""

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

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        quick_jump = SampleCardView("Quick Access" if self._is_non_chinese_ui else self.tr("快捷跳转"), self.view)
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "setting.svg"),
            title="Settings" if self._is_non_chinese_ui else "设置",
            content="Please set up the automata acacia settings first" if self._is_non_chinese_ui else self.tr("首次下载请先设置自律姬"),
            routeKey="settingInterface",
            index=0,
        )
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "play.svg"),
            title="Start Daily" if self._is_non_chinese_ui else "立刻日常",
            content="SAA handles daily tasks in one click" if self._is_non_chinese_ui else self.tr("自律姬帮你一键种草。"),
            routeKey="Home-Start-Now",
            index=0,
        )
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
