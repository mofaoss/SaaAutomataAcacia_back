from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidgetItem, QFrame, QHBoxLayout, QTreeWidgetItemIterator, QScrollArea, QApplication
from qfluentwidgets import TreeWidget, ScrollArea

from app.presentation.shared.style_sheet import StyleSheet


class Frame(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(0, 8, 0, 0)

        self.setObjectName('frame')
        StyleSheet.VIEW_INTERFACE.apply(self)

    def addWidget(self, widget):
        self.hBoxLayout.addWidget(widget)


class TreeFrame_person(Frame):
    itemStateChanged = Signal(int, int)

    def __init__(self, parent=None, enableCheck=False, is_non_chinese_ui=False):
        super().__init__(parent)
        self.parent = parent
        self.tree = TreeWidget(self.parent)
        self.addWidget(self.tree)

        title = 'Character Shards' if is_non_chinese_ui else '角色碎片'
        children = [
            "Yao", "Acacia", "Lyfe", "Chenxing", "Marian", "Fenny",
            "Fritia", "Siris", "Cherno", "Mauxir", "Haru", "Enya", "Nita",
        ] if is_non_chinese_ui else [
            "肴", "安卡希雅", "里芙", "辰星", "茉莉安", "芬妮",
            "芙提雅", "瑟瑞斯", "琴诺", "猫汐尔", "晴", "恩雅", "妮塔",
        ]

        item1 = QTreeWidgetItem([title])
        item1.addChildren([QTreeWidgetItem([name]) for name in children])
        self.tree.addTopLevelItem(item1)

        self.tree.setHeaderHidden(True)

        # 连接展开和收起信号到槽函数
        self.tree.itemExpanded.connect(self.adjustSizeToTree)
        self.tree.itemCollapsed.connect(self.adjustSizeToTree)
        # 禁用树状组件的滚动条
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setFixedSize(250, 45)

        if enableCheck:
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                # 这里的 setCheckState 语法是完全正确的
                it.value().setCheckState(0, Qt.CheckState.Unchecked)
                it += 1

        self.tree.itemChanged.connect(self.onItemChanged)

    def adjustSizeToTree(self):
        """
        调整 Frame 的大小以适应 QTreeWidget 的展开状态
        """
        # 获取树状结构的总行数
        total_height = 0
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            total_height += self.tree.sizeHintForIndex(self.tree.indexFromItem(item)).height()
            total_height += self._calculateHeightForChildren(item)

        # 调整当前窗口大小
        self.setFixedSize(250, total_height + 5)  # 适当增加额外的空间

    def _calculateHeightForChildren(self, item):
        """ 递归计算子节点的高度 """
        height = 0
        if item.isExpanded():
            for i in range(item.childCount()):
                child = item.child(i)
                height += self.tree.sizeHintForIndex(self.tree.indexFromItem(child)).height()
                height += self._calculateHeightForChildren(child)
        return height

    def onItemChanged(self, item, column):
        item_path = self.get_item_path(item)
        if len(item_path) == 1:
            index = item_path[0]
        else:
            index = item_path[1] + 1

        # ✨ 核心修复：加上 .value 将枚举(Qt.CheckState)转换为整数(int)，完美匹配 Signal(int, int)
        self.itemStateChanged.emit(index, item.checkState(0).value)

    def get_item_path(self, item):
        """
        获取指定 QTreeWidgetItem 的完整路径，返回层级中的所有行索引。
        """
        path = []
        current_item = item

        # 一直向上查找父项，直到到达顶层
        while current_item is not None:
            parent = current_item.parent()
            if parent is None:
                # 如果没有父级，说明是顶层项，使用 topLevelItemCount() 查找顶层项索引
                index = self.tree.indexOfTopLevelItem(current_item)
            else:
                # 如果有父级，使用父级的 indexOfChild() 方法找到相对于父级的索引
                index = parent.indexOfChild(current_item)

            # 在路径中记录当前层的索引
            path.insert(0, index)
            current_item = parent

        return path


class TreeFrame_weapon(Frame):
    itemStateChanged = Signal(int, int)

    def __init__(self, parent=None, enableCheck=False, is_non_chinese_ui=False):
        super().__init__(parent)
        self.parent = parent
        self.tree = TreeWidget(self.parent)
        self.addWidget(self.tree)

        title = 'Weapon' if is_non_chinese_ui else '武器'
        children = [
            "Prismatic Igniter",
            "Strawberry Shortcake",
            "Deep Sea's Call",
        ] if is_non_chinese_ui else [
            "彩虹打火机",
            "草莓蛋糕",
            "深海呼唤",
        ]

        item1 = QTreeWidgetItem([title])
        item1.addChildren([QTreeWidgetItem([name]) for name in children])
        self.tree.addTopLevelItem(item1)

        self.tree.setHeaderHidden(True)

        # 连接展开和收起信号到槽函数
        self.tree.itemExpanded.connect(self.adjustSizeToTree)
        self.tree.itemCollapsed.connect(self.adjustSizeToTree)
        # 禁用树状组件的滚动条
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
        """
        调整 Frame 的大小以适应 QTreeWidget 的展开状态
        """
        # 获取树状结构的总行数
        total_height = 0
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            total_height += self.tree.sizeHintForIndex(self.tree.indexFromItem(item)).height()
            total_height += self._calculateHeightForChildren(item)

        # 调整当前窗口大小
        self.setFixedSize(250, total_height + 5)  # 适当增加额外的空间

    def _calculateHeightForChildren(self, item):
        """ 递归计算子节点的高度 """
        height = 0
        if item.isExpanded():
            for i in range(item.childCount()):
                child = item.child(i)
                height += self.tree.sizeHintForIndex(self.tree.indexFromItem(child)).height()
                height += self._calculateHeightForChildren(child)
        return height

    def onItemChanged(self, item, column):
        item_path = self.get_item_path(item)
        if len(item_path) == 1:
            index = item_path[0]
        else:
            index = item_path[1] + 1

        # ✨ 核心修复：同样加上 .value
        self.itemStateChanged.emit(index, item.checkState(0).value)

    def get_item_path(self, item):
        """
        获取指定 QTreeWidgetItem 的完整路径，返回层级中的所有行索引。
        """
        path = []
        current_item = item

        # 一直向上查找父项，直到到达顶层
        while current_item is not None:
            parent = current_item.parent()
            if parent is None:
                # 如果没有父级，说明是顶层项，使用 topLevelItemCount() 查找顶层项索引
                index = self.tree.indexOfTopLevelItem(current_item)
            else:
                # 如果有父级，使用父级的 indexOfChild() 方法找到相对于父级的索引
                index = parent.indexOfChild(current_item)

            # 在路径中记录当前层的索引
            path.insert(0, index)
            current_item = parent

        return path

