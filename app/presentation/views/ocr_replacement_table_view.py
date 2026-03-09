from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QSpacerItem
from qfluentwidgets import BodyLabel, ComboBox, LineEdit, PrimaryPushButton, PushButton, TableWidget


class OcrReplacementTableView:
    def __init__(self, parent):
        self._parent = parent
        self.setup_ui(parent)

    def setup_ui(self, parent):
        parent.setObjectName("ocrtable")

        self.gridLayout = QGridLayout(parent)
        self.gridLayout.setContentsMargins(5, 5, 5, 5)
        self.gridLayout.setObjectName("gridLayout")

        self.BodyLabel_3 = BodyLabel(parent)
        self.BodyLabel_3.setObjectName("BodyLabel_3")
        self.gridLayout.addWidget(self.BodyLabel_3, 0, 5, 1, 1)

        self.BodyLabel = BodyLabel(parent)
        self.BodyLabel.setObjectName("BodyLabel")
        self.gridLayout.addWidget(self.BodyLabel, 0, 1, 1, 1)

        self.BodyLabel_2 = BodyLabel(parent)
        self.BodyLabel_2.setObjectName("BodyLabel_2")
        self.gridLayout.addWidget(self.BodyLabel_2, 0, 3, 1, 1)

        self.TableWidget_ocr_table = TableWidget(parent)
        self.TableWidget_ocr_table.setShowGrid(False)
        self.TableWidget_ocr_table.setWordWrap(False)
        self.TableWidget_ocr_table.setColumnCount(3)
        self.TableWidget_ocr_table.setObjectName("TableWidget_ocr_table")
        self.TableWidget_ocr_table.setRowCount(0)
        self.gridLayout.addWidget(self.TableWidget_ocr_table, 0, 0, 5, 1)

        self.ComboBox_type = ComboBox(parent)
        self.ComboBox_type.setObjectName("ComboBox_type")
        self.gridLayout.addWidget(self.ComboBox_type, 0, 2, 1, 1)

        self.LineEdit_before = LineEdit(parent)
        self.LineEdit_before.setObjectName("LineEdit_before")
        self.gridLayout.addWidget(self.LineEdit_before, 0, 4, 1, 1)

        self.LineEdit_after = LineEdit(parent)
        self.LineEdit_after.setObjectName("LineEdit_after")
        self.gridLayout.addWidget(self.LineEdit_after, 0, 6, 1, 1)

        spacer_item = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.gridLayout.addItem(spacer_item, 4, 1, 1, 1)

        self.BodyLabel_tips = BodyLabel(parent)
        self.BodyLabel_tips.setTextFormat(Qt.TextFormat.MarkdownText)
        self.BodyLabel_tips.setWordWrap(True)
        self.BodyLabel_tips.setObjectName("BodyLabel_tips")
        self.gridLayout.addWidget(self.BodyLabel_tips, 3, 1, 1, 6)

        self.PushButton_delete = PushButton(parent)
        self.PushButton_delete.setObjectName("PushButton_delete")
        self.gridLayout.addWidget(self.PushButton_delete, 1, 1, 1, 3)

        self.PrimaryPushButton_add = PrimaryPushButton(parent)
        self.PrimaryPushButton_add.setObjectName("PrimaryPushButton_add")
        self.gridLayout.addWidget(self.PrimaryPushButton_add, 1, 4, 1, 3)

        self.gridLayout.setColumnStretch(0, 7)
        self.gridLayout.setColumnStretch(1, 1)
        self.gridLayout.setColumnStretch(2, 1)
        self.gridLayout.setColumnStretch(3, 1)
        self.gridLayout.setColumnStretch(4, 2)
        self.gridLayout.setColumnStretch(5, 1)
        self.gridLayout.setColumnStretch(6, 2)
