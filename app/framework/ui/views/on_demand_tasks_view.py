from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QSizePolicy,
    QStackedWidget,
    QWidget,
    QTextBrowser,
    QVBoxLayout,
)
from qfluentwidgets import SegmentedWidget, SimpleCardWidget, TitleLabel

class OnDemandTasksView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("on_demand_tasks")

        self.gridLayout = QGridLayout(self)
        self.gridLayout.setContentsMargins(10, 10, 10, 10)
        self.gridLayout.setSpacing(12)

        self.leftPane = QWidget(self)
        self.leftPane.setObjectName("leftPane")
        self.leftPaneLayout = QVBoxLayout(self.leftPane)
        self.leftPaneLayout.setContentsMargins(0, 0, 0, 0)
        self.leftPaneLayout.setSpacing(8)

        self.SegmentedWidget = SegmentedWidget(self)
        self.SegmentedWidget.setObjectName("SegmentedWidget")
        self.SegmentedWidget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.SegmentedWidget.setMaximumHeight(44)
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setObjectName("stackedWidget")
        self.stackedWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.leftPaneLayout.addWidget(self.SegmentedWidget, 0)
        self.leftPaneLayout.addWidget(self.stackedWidget, 1)

        self.sharedLogCard = SimpleCardWidget(self)
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
        self.gridLayout.setRowStretch(0, 1)
        self.gridLayout.setRowStretch(1, 0)

        self.gridLayout.addWidget(self.leftPane, 0, 0, 2, 1)
        self.gridLayout.addWidget(self.sharedLogCard, 0, 1, 2, 1)
        self.sharedLogTitle.setText(self.tr("共享日志"))
        self._external_sidebar_cards = []
        self._right_column_cards = [self.sharedLogCard]

    def add_page(self, widget: QWidget, object_name: str, text: str):
        widget.setObjectName(object_name)
        self.stackedWidget.addWidget(widget)
        self.SegmentedWidget.addItem(
            object_name,
            text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def _clear_right_column_layout(self):
        for card in self._right_column_cards:
            self.gridLayout.removeWidget(card)
            card.setParent(None)
        self._right_column_cards = []

    def _mount_right_cards(self, cards: list[QWidget]):
        if not cards:
            return

        self._right_column_cards = list(cards)
        if len(cards) >= 2:
            self.gridLayout.setRowStretch(0, 1)
            self.gridLayout.setRowStretch(1, 0)
            self.gridLayout.addWidget(cards[0], 0, 1, 1, 1)
            self.gridLayout.addWidget(cards[1], 1, 1, 1, 1)
            for card in cards[2:]:
                self.gridLayout.addWidget(card, 1, 1, 1, 1)
            return

        self.gridLayout.setRowStretch(0, 1)
        self.gridLayout.setRowStretch(1, 1)
        self.gridLayout.addWidget(cards[0], 0, 1, 2, 1)

    def show_external_sidebar_cards(self, cards: list[QWidget]):
        self._clear_right_column_layout()
        self._external_sidebar_cards = list(cards)
        self._mount_right_cards(self._external_sidebar_cards)

    def take_external_sidebar_cards(self) -> list[QWidget]:
        cards = list(self._external_sidebar_cards)
        self._clear_right_column_layout()
        self._external_sidebar_cards = []
        return cards

    def show_internal_sidebar(self):
        self._clear_right_column_layout()
        self._external_sidebar_cards = []
        self._mount_right_cards([self.sharedLogCard])
