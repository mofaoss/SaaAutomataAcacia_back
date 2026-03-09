from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QTextBrowser,
)
from qfluentwidgets import SegmentedWidget, SimpleCardWidget, TitleLabel

class OnDemandTasksView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("additional_features")

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(10, 10, 10, 10)
        self.gridLayout.setSpacing(12)

        self.SegmentedWidget = SegmentedWidget(self)
        self.SegmentedWidget.setObjectName("SegmentedWidget")
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setObjectName("stackedWidget")
        self.stackedWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.rightColumnWidget = QWidget(self)
        self.rightColumnWidget.setObjectName("rightColumnWidget")
        self.rightColumnWidget.setMinimumWidth(246)
        self.rightColumnWidget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.rightColumnLayout = QVBoxLayout(self.rightColumnWidget)
        self.rightColumnLayout.setContentsMargins(0, 0, 0, 0)
        self.rightColumnLayout.setSpacing(12)

        self.sharedLogCard = SimpleCardWidget(self.rightColumnWidget)
        self.sharedLogCard.setObjectName("sharedLogCard")
        self.sharedLogCard.setMinimumWidth(246)
        self.sharedLogCard.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sharedLogLayout = QVBoxLayout(self.sharedLogCard)
        self.sharedLogTitle = TitleLabel(self.sharedLogCard)
        self.sharedLogTitle.setObjectName("sharedLogTitle")
        self.textBrowser_shared_log = QTextBrowser(self.sharedLogCard)
        self.textBrowser_shared_log.setObjectName("textBrowser_shared_log")
        self.textBrowser_shared_log.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.sharedLogLayout.addWidget(self.sharedLogTitle)
        self.sharedLogLayout.addWidget(self.textBrowser_shared_log)

        self.gridLayout.setColumnStretch(0, 5)
        self.gridLayout.setColumnStretch(1, 2)
        self.gridLayout.setColumnMinimumWidth(1, 246)
        self.gridLayout.setRowStretch(0, 0)
        self.gridLayout.setRowStretch(1, 1)

        self.gridLayout.addWidget(self.SegmentedWidget, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.stackedWidget, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.rightColumnWidget, 0, 1, 2, 1)
        self.rightColumnLayout.addWidget(self.sharedLogCard)
        self.sharedLogTitle.setText(self.tr("共享日志"))
        self._external_sidebar_cards = []

    def add_page(self, widget: QWidget, object_name: str, text: str):
        widget.setObjectName(object_name)
        self.stackedWidget.addWidget(widget)
        self.SegmentedWidget.addItem(
            object_name,
            text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def _clear_right_column_layout(self):
        while self.rightColumnLayout.count():
            item = self.rightColumnLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def show_external_sidebar_cards(self, cards: list[QWidget]):
        self._clear_right_column_layout()
        self._external_sidebar_cards = list(cards)
        for card in self._external_sidebar_cards:
            self.rightColumnLayout.addWidget(card)

    def take_external_sidebar_cards(self) -> list[QWidget]:
        cards = list(self._external_sidebar_cards)
        for card in cards:
            self.rightColumnLayout.removeWidget(card)
            card.setParent(None)
        self._external_sidebar_cards = []
        return cards

    def show_internal_sidebar(self):
        self._clear_right_column_layout()
        self._external_sidebar_cards = []
        self.rightColumnLayout.addWidget(self.sharedLogCard)
