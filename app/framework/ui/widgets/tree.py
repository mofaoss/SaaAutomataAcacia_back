from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QTreeWidgetItem, QTreeWidgetItemIterator
from qfluentwidgets import TreeWidget

from app.framework.ui.shared.style_sheet import StyleSheet


class Frame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(0, 8, 0, 0)

        self.setObjectName("frame")
        StyleSheet.VIEW_INTERFACE.apply(self)

    def addWidget(self, widget):
        self.hBoxLayout.addWidget(widget)


class _BaseTreeFrame(Frame):
    itemStateChanged = Signal(int, int)

    def __init__(self, parent=None, enableCheck=False, title="", children: Iterable[str] | None = None):
        super().__init__(parent)
        self.parent = parent
        self.tree = TreeWidget(self.parent)
        self.addWidget(self.tree)

        node = QTreeWidgetItem([str(title)])
        for name in list(children or []):
            node.addChild(QTreeWidgetItem([str(name)]))
        self.tree.addTopLevelItem(node)
        self.tree.setHeaderHidden(True)

        self.tree.itemExpanded.connect(self.adjustSizeToTree)
        self.tree.itemCollapsed.connect(self.adjustSizeToTree)
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedSize(250, 45)

        if enableCheck:
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                it.value().setCheckState(0, Qt.CheckState.Unchecked)
                it += 1

        self.tree.itemChanged.connect(self.onItemChanged)

    def adjustSizeToTree(self):
        total_height = 0
        for idx in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(idx)
            total_height += self.tree.sizeHintForIndex(self.tree.indexFromItem(item)).height()
            total_height += self._calculateHeightForChildren(item)
        self.setFixedSize(250, total_height + 5)

    def _calculateHeightForChildren(self, item):
        height = 0
        if item.isExpanded():
            for idx in range(item.childCount()):
                child = item.child(idx)
                height += self.tree.sizeHintForIndex(self.tree.indexFromItem(child)).height()
                height += self._calculateHeightForChildren(child)
        return height

    def onItemChanged(self, item, column):
        _ = column
        path = self.get_item_path(item)
        index = path[0] if len(path) == 1 else path[1] + 1
        self.itemStateChanged.emit(index, item.checkState(0).value)

    def get_item_path(self, item):
        path = []
        current_item = item
        while current_item is not None:
            parent = current_item.parent()
            if parent is None:
                index = self.tree.indexOfTopLevelItem(current_item)
            else:
                index = parent.indexOfChild(current_item)
            path.insert(0, index)
            current_item = parent
        return path


class TreeFrame_person(_BaseTreeFrame):
    itemStateChanged = Signal(int, int)

    def __init__(self, parent=None, enableCheck=False, is_non_chinese_ui=False, title=None, children=None):
        if title is None:
            title = "Character Shards" if is_non_chinese_ui else "角色碎片"
        if children is None:
            children = (
                [
                    "Yao",
                    "Acacia",
                    "Lyfe",
                    "Chenxing",
                    "Marian",
                    "Fenny",
                    "Fritia",
                    "Siris",
                    "Cherno",
                    "Mauxir",
                    "Haru",
                    "Enya",
                    "Nita",
                ]
                if is_non_chinese_ui
                else [
                    "肴",
                    "安卡希雅",
                    "里芙",
                    "辰星",
                    "茉莉安",
                    "芬妮",
                    "芙提雅",
                    "瑟瑞斯",
                    "琴诺",
                    "猫汐尔",
                    "晴",
                    "恩雅",
                    "妮塔",
                ]
            )
        super().__init__(parent=parent, enableCheck=enableCheck, title=title, children=children)


class TreeFrame_weapon(_BaseTreeFrame):
    itemStateChanged = Signal(int, int)

    def __init__(self, parent=None, enableCheck=False, is_non_chinese_ui=False, title=None, children=None):
        if title is None:
            title = "Weapon" if is_non_chinese_ui else "武器"
        if children is None:
            children = (
                [
                    "Prismatic Igniter",
                    "Strawberry Shortcake",
                    "Deep Sea's Call",
                ]
                if is_non_chinese_ui
                else [
                    "彩虹打火机",
                    "草莓蛋糕",
                    "深海呼唤",
                ]
            )
        super().__init__(parent=parent, enableCheck=enableCheck, title=title, children=children)
