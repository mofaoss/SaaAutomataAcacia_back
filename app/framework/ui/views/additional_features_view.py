from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget, QTextBrowser
from qfluentwidgets import SegmentedWidget, SimpleCardWidget, TitleLabel

class AdditionalFeaturesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("additional_features")

        self.gridLayout = QVBoxLayout(self)
        self.gridLayout.setContentsMargins(0, 0, 0, 3)
        self.gridLayout.setSpacing(6)

        self.SegmentedWidget = SegmentedWidget(self)
        self.SegmentedWidget.setObjectName("SegmentedWidget")
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setObjectName("stackedWidget")
        self.sharedLogCard = SimpleCardWidget(self)
        self.sharedLogCard.setObjectName("sharedLogCard")
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

        self.gridLayout.addWidget(self.SegmentedWidget)
        self.gridLayout.addWidget(self.stackedWidget, 1)
        self.gridLayout.addWidget(self.sharedLogCard)
        self.sharedLogTitle.setText(self.tr("共享日志"))

    def add_page(self, widget: QWidget, object_name: str, text: str):
        widget.setObjectName(object_name)
        self.stackedWidget.addWidget(widget)
        self.SegmentedWidget.addItem(
            object_name,
            text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )
