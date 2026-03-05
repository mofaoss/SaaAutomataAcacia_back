# coding:utf-8
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsOpacityEffect

from qfluentwidgets import IconWidget, TextWrap, FlowLayout, CardWidget, FluentIcon, SwitchButton
from ..common.signal_bus import signalBus
from ..common.style_sheet import StyleSheet


class SampleCard(CardWidget):
    """ Sample card """

    def __init__(self, icon, title, content, routeKey, index, parent=None):
        super().__init__(parent=parent)
        self.index = index
        self.routekey = routeKey

        self.iconWidget = IconWidget(icon, self)
        self.iconOpacityEffect = QGraphicsOpacityEffect(self.iconWidget)
        self.iconOpacityEffect.setOpacity(0.8)
        self.iconWidget.setGraphicsEffect(self.iconOpacityEffect)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: 500;")
        self.titleOpacityEffect = QGraphicsOpacityEffect(self.titleLabel)
        self.titleOpacityEffect.setOpacity(0.8)
        self.titleLabel.setGraphicsEffect(self.titleOpacityEffect)

        self.contentLabel = QLabel(TextWrap.wrap(content, 45, False)[0], self)
        self.contentOpacityEffect = QGraphicsOpacityEffect(self.contentLabel)
        self.contentOpacityEffect.setOpacity(0.8)
        self.contentLabel.setGraphicsEffect(self.contentOpacityEffect)

        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        self.setFixedSize(360, 90)
        self.iconWidget.setFixedSize(48, 48)

        self.hBoxLayout.setSpacing(28)
        self.hBoxLayout.setContentsMargins(20, 0, 0, 0)
        self.vBoxLayout.setSpacing(2)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.iconWidget)
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.contentLabel)
        self.vBoxLayout.addStretch(1)

        self.titleLabel.setObjectName('titleLabel')
        self.contentLabel.setObjectName('contentLabel')

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        signalBus.switchToSampleCard.emit(self.routekey, self.index)

    def enterEvent(self, event):
        super().enterEvent(event)

        self.iconOpacityEffect.setEnabled(False)
        self.titleOpacityEffect.setEnabled(False)
        self.contentOpacityEffect.setEnabled(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event):
        super().leaveEvent(event)

        self.iconOpacityEffect.setEnabled(True)
        self.titleOpacityEffect.setEnabled(True)
        self.contentOpacityEffect.setEnabled(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)


class SampleCard_URL(CardWidget):
    """ Sample card """

    def __init__(self, icon, title, content, url, parent=None):
        super().__init__(parent=parent)
        self.url = QUrl(url)

        self.iconWidget = IconWidget(icon, self)
        self.iconOpacityEffect = QGraphicsOpacityEffect(self.iconWidget)
        self.iconOpacityEffect.setOpacity(0.8)
        self.iconWidget.setGraphicsEffect(self.iconOpacityEffect)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: 500;")
        self.titleOpacityEffect = QGraphicsOpacityEffect(self.titleLabel)
        self.titleOpacityEffect.setOpacity(0.8)
        self.titleLabel.setGraphicsEffect(self.titleOpacityEffect)

        self.contentLabel = QLabel(TextWrap.wrap(content, 45, False)[0], self)
        self.contentOpacityEffect = QGraphicsOpacityEffect(self.contentLabel)
        self.contentOpacityEffect.setOpacity(0.8)
        self.contentLabel.setGraphicsEffect(self.contentOpacityEffect)

        self.urlWidget = IconWidget(FluentIcon.LINK, self)
        self.urlWidget.setFixedSize(16, 16)
        self.urlOpacityEffect = QGraphicsOpacityEffect(self.urlWidget)
        self.urlOpacityEffect.setOpacity(0.8)
        self.urlWidget.setGraphicsEffect(self.urlOpacityEffect)

        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        self.setFixedSize(360, 90)
        self.iconWidget.setFixedSize(48, 48)

        self.hBoxLayout.setSpacing(28)
        self.hBoxLayout.setContentsMargins(20, 0, 0, 0)
        self.vBoxLayout.setSpacing(2)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.iconWidget)
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.hBoxLayout.addStretch(2)
        self.hBoxLayout.addWidget(self.urlWidget)
        self.hBoxLayout.addStretch(1)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.contentLabel)
        self.vBoxLayout.addStretch(1)

        self.titleLabel.setObjectName('titleLabel')
        self.contentLabel.setObjectName('contentLabel')

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        QDesktopServices.openUrl(self.url)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.iconOpacityEffect.setEnabled(False)
        self.titleOpacityEffect.setEnabled(False)
        self.contentOpacityEffect.setEnabled(False)
        self.urlOpacityEffect.setEnabled(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.iconOpacityEffect.setEnabled(True)
        self.titleOpacityEffect.setEnabled(True)
        self.contentOpacityEffect.setEnabled(True)
        self.urlOpacityEffect.setEnabled(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)


class SampleCard_Switch(CardWidget):
    """Sample card with a right-side switch"""

    def __init__(self, icon, title, content, checked, on_toggle, parent=None):
        super().__init__(parent=parent)
        self.on_toggle = on_toggle

        self.iconWidget = IconWidget(icon, self)
        self.iconOpacityEffect = QGraphicsOpacityEffect(self.iconWidget)
        self.iconOpacityEffect.setOpacity(0.8)
        self.iconWidget.setGraphicsEffect(self.iconOpacityEffect)

        self.titleLabel = QLabel(title, self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: 500;")
        self.titleOpacityEffect = QGraphicsOpacityEffect(self.titleLabel)
        self.titleOpacityEffect.setOpacity(0.8)
        self.titleLabel.setGraphicsEffect(self.titleOpacityEffect)

        self.contentLabel = QLabel(TextWrap.wrap(content, 45, False)[0], self)
        self.contentOpacityEffect = QGraphicsOpacityEffect(self.contentLabel)
        self.contentOpacityEffect.setOpacity(0.8)
        self.contentLabel.setGraphicsEffect(self.contentOpacityEffect)

        self.switchButton = SwitchButton(self)
        self.switchButton.setChecked(bool(checked))
        self.switchButton.checkedChanged.connect(self._on_checked_changed)

        self.hBoxLayout = QHBoxLayout(self)
        self.vBoxLayout = QVBoxLayout()

        self.setFixedSize(360, 90)
        self.iconWidget.setFixedSize(48, 48)

        self.hBoxLayout.setSpacing(28)
        self.hBoxLayout.setContentsMargins(20, 0, 14, 0)
        self.vBoxLayout.setSpacing(2)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.hBoxLayout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.hBoxLayout.addWidget(self.iconWidget)
        self.hBoxLayout.addLayout(self.vBoxLayout)
        self.hBoxLayout.addStretch(2)
        self.hBoxLayout.addWidget(self.switchButton)
        self.vBoxLayout.addStretch(1)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addWidget(self.contentLabel)
        self.vBoxLayout.addStretch(1)

        self.titleLabel.setObjectName('titleLabel')
        self.contentLabel.setObjectName('contentLabel')

    def _on_checked_changed(self, checked):
        if self.on_toggle:
            self.on_toggle(bool(checked))

    def setChecked(self, checked: bool, emit: bool = False):
        if emit:
            self.switchButton.setChecked(bool(checked))
            return
        old_state = self.switchButton.blockSignals(True)
        self.switchButton.setChecked(bool(checked))
        self.switchButton.blockSignals(old_state)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.switchButton.setChecked(not self.switchButton.isChecked())

    def enterEvent(self, event):
        super().enterEvent(event)
        self.iconOpacityEffect.setEnabled(False)
        self.titleOpacityEffect.setEnabled(False)
        self.contentOpacityEffect.setEnabled(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.iconOpacityEffect.setEnabled(True)
        self.titleOpacityEffect.setEnabled(True)
        self.contentOpacityEffect.setEnabled(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)


class SampleCardView(QWidget):
    """ Sample card view """

    def __init__(self, title: str, parent=None):
        super().__init__(parent=parent)
        self.titleLabel = QLabel(title, self)
        self.vBoxLayout = QVBoxLayout(self)
        self.flowLayout = FlowLayout()

        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)
        self.vBoxLayout.setSpacing(10)
        self.flowLayout.setContentsMargins(0, 0, 0, 0)
        self.flowLayout.setHorizontalSpacing(12)
        self.flowLayout.setVerticalSpacing(12)

        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addLayout(self.flowLayout, 1)

        self.titleLabel.setObjectName('viewTitleLabel')
        StyleSheet.SAMPLE_CARD.apply(self)

    def addSampleCard(self, icon, title, content, routeKey, index):
        """ add sample card """
        card = SampleCard(icon, title, content, routeKey, index, self)
        self.flowLayout.addWidget(card)

    def addSampleCard_URL(self, icon, title, content, url):
        """ add sample card """
        card = SampleCard_URL(icon, title, content, url, self)
        self.flowLayout.addWidget(card)

    def addSampleCard_Switch(self, icon, title, content, checked, on_toggle):
        """ add sample switch card """
        card = SampleCard_Switch(icon, title, content, checked, on_toggle, self)
        self.flowLayout.addWidget(card)
        return card