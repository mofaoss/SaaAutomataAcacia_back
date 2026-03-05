import os
import random
import sys
from pathlib import Path

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
from .base_interface import BaseInterface
from utils.updater_utils import get_local_version

from app.repackage.samplecardview import SampleCardView


def _resolve_display_image_dir() -> Path:
    candidates = []

    compiled_info = globals().get("__compiled__")
    containing_dir = getattr(compiled_info, "containing_dir", None)
    if containing_dir:
        candidates.append(Path(containing_dir))

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass))

    nuitka_onefile_temp = os.environ.get("NUITKA_ONEFILE_TEMP")
    if nuitka_onefile_temp:
        candidates.append(Path(nuitka_onefile_temp))

    candidates.append(Path(__file__).resolve().parents[2])

    if getattr(sys, "frozen", False):
        try:
            candidates.append(Path(sys.executable).resolve().parent)
        except Exception:
            pass

    try:
        candidates.append(Path(sys.argv[0]).resolve().parent)
    except Exception:
        pass

    candidates.append(Path.cwd())

    seen = set()
    for base in candidates:
        key = str(base)
        if key in seen:
            continue
        seen.add(key)

        display_dir = base / "app" / "resource" / "images" / "display"
        if display_dir.exists() and display_dir.is_dir():
            return display_dir

    return Path("app") / "resource" / "images" / "display"


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

        self.basedir = _resolve_display_image_dir()
        self.banner = self._load_random_banner()
        self.galleryLabel.setObjectName("galleryLabel")

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 0)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def _load_random_banner(self) -> QPixmap:
        candidates = self._get_banner_candidates()
        if candidates:
            selected = random.choice(candidates)
            pixmap = QPixmap(str(selected))
            if not pixmap.isNull():
                return pixmap

        fallback = self.basedir / "background_1.jpg"
        return QPixmap(str(fallback))

    def _get_banner_candidates(self):
        if not self.basedir.exists() or not self.basedir.is_dir():
            return []

        allowed_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        return sorted([
            path
            for path in self.basedir.iterdir()
            if path.is_file() and path.suffix.lower() in allowed_suffixes
            ], key=lambda item: item.name.lower())

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


class DisplayInterface(ScrollArea, BaseInterface):
    """Display interface"""

    _ui_text_use_qt_tr = True

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.basedir = str(_resolve_display_image_dir())
        self.windowTrackingQuickSwitchCard = None

        # 1. 搭建骨架
        self._setup_ui()
        # 2. 穿上衣服（国际化翻译）
        self._apply_i18n()
        # 3. 添加动态内容（卡片与信号绑定）
        self._load_samples()

    def _setup_ui(self):
        """专门负责创建控件、设置布局和样式（视图层职责）"""
        self.setObjectName("displayInterface")
        StyleSheet.DISPLAY_INTERFACE.apply(self)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)

        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.setWidget(self.view)

        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 36)
        self.vBoxLayout.setSpacing(40)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.banner = BannerWidget(self)
        self.vBoxLayout.addWidget(self.banner)

        # 语言提示卡片初始化
        self.gameLanguageNoticeCard = CardWidget(self.view)
        self.gameLanguageNoticeCard.setFixedHeight(45)
        self.gameLanguageNoticeLayout = QVBoxLayout(self.gameLanguageNoticeCard)
        self.gameLanguageNoticeLayout.setContentsMargins(12, 8, 12, 8)
        self.gameLanguageNoticeLayout.setSpacing(2)

        self.gameLanguageNoticeTitle = QLabel(self.gameLanguageNoticeCard)
        self.gameLanguageNoticeTitle.setStyleSheet("font-size: 16px; font-weight: 500;")

        self.gameLanguageNoticeLabel = QLabel(self.gameLanguageNoticeCard)
        self.gameLanguageNoticeLabel.setStyleSheet("color: red;")
        self.gameLanguageNoticeLabel.setWordWrap(True)

        self.gameLanguageNoticeLayout.addWidget(self.gameLanguageNoticeTitle)
        self.gameLanguageNoticeLayout.addWidget(self.gameLanguageNoticeLabel)

        # 仅在非中文环境下显示提示卡片
        self.gameLanguageNoticeCard.setVisible(self._is_non_chinese_ui)
        self.vBoxLayout.addWidget(self.gameLanguageNoticeCard)

    def _apply_i18n(self):
        """专门负责文本和多语言翻译（视图层职责）"""
        self.gameLanguageNoticeLabel.setText(
            "Note: Game language for automation supports only Simplified/Traditional Chinese."
            if self._is_non_chinese_ui
            else self.tr("注意：自动化识别的游戏语言目前仅支持简体中文与繁体中文。")
        )

    def _load_samples(self):
        """负责组装快速跳转卡片及绑定业务逻辑（控制层职责）"""
        jump_title = "Quick Access" if self._is_non_chinese_ui else self.tr("快捷跳转")
        quick_jump = SampleCardView(jump_title, self.view)

        # 1. 设置卡片
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "setting.svg"),
            title="Settings" if self._is_non_chinese_ui else "核心设置",
            content="Please confirm the settings when you first download" if self._is_non_chinese_ui else self.tr("首次下载，请先确认"),
            routeKey="settingInterface",
            index=0,
        )

        # 2. 自律卡片
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "play.svg"),
            title="Start Daily" if self._is_non_chinese_ui else "开始自律",
            content="Acacia, Let's go!" if self._is_non_chinese_ui else self.tr("安卡希雅，Let's go!"),
            routeKey="Home-Start-Now",
            index=0,
        )

        # 3. 教程卡片
        quick_jump.addSampleCard(
            icon=os.path.join(self.basedir, "explain.svg"),
            title="Tutorial" if self._is_non_chinese_ui else "使用教程",
            content="Read the guide to get started quickly" if self._is_non_chinese_ui else self.tr("查看教程，答疑解惑"),
            routeKey="Help-Interface",
            index=0,
        )

        # 4. 隐身模式开关卡片
        stealth_on = bool(config.windowTrackingInput.value) and int(config.windowTrackingAlpha.value) == 1
        self.windowTrackingQuickSwitchCard = quick_jump.addSampleCard_Switch(
            icon=os.path.join(self.basedir, "electronics.svg"),
            title="Stealth Mode" if self._is_non_chinese_ui else "隐身模式",
            content="Make the game completely invisible in the background" if self._is_non_chinese_ui else self.tr("游戏隐身，完全后台"),
            checked=stealth_on,
            on_toggle=self._toggle_stealth_mode,
        )

        self.vBoxLayout.addWidget(quick_jump)

    def _sync_window_tracking_quick_switch(self):
        """业务状态同步逻辑"""
        if self.windowTrackingQuickSwitchCard is not None:
            stealth_on = bool(config.windowTrackingInput.value) and int(config.windowTrackingAlpha.value) == 1
            self.windowTrackingQuickSwitchCard.setChecked(stealth_on, emit=False)

    def _toggle_stealth_mode(self, checked: bool):
        """业务执行逻辑"""
        alpha = 1 if checked else 255
        config.set(config.windowTrackingInput, checked)
        config.set(config.windowTrackingAlpha, alpha)
        signalBus.windowTrackingStealthChanged.emit(bool(checked), int(alpha))

    def showEvent(self, event):
        """生命周期事件"""
        super().showEvent(event)
        self._sync_window_tracking_quick_switch()
