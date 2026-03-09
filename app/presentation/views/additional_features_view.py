from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from qfluentwidgets import SegmentedWidget

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

        self.gridLayout.addWidget(self.SegmentedWidget)
        self.gridLayout.addWidget(self.stackedWidget, 1)

    def add_page(self, widget: QWidget, object_name: str, text: str):
        widget.setObjectName(object_name)
        self.stackedWidget.addWidget(widget)
        self.SegmentedWidget.addItem(
            object_name,
            text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )
