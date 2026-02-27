import json
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QTableWidgetItem
from qfluentwidgets import InfoBar, InfoBarPosition

from app.common.config import is_non_chinese_ui_language
from app.common.style_sheet import StyleSheet
from app.ui.ocr_replacement_table import Ui_ocrtable


class OcrReplacementTable(QFrame, Ui_ocrtable):
    def __init__(self, text: str, parent=None):
        super().__init__()

        self.setupUi(self)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.old_type = None
        self.old_key = None
        self.old_value = None

        self._initWidget()
        self._connect_to_slot()

    def _initWidget(self):
        self.BodyLabel.setText(self._ui_text("替换类型", "Replacement Type"))
        self.BodyLabel_2.setText(self._ui_text("替换前", "Before"))
        self.BodyLabel_3.setText(self._ui_text("替换后", "After"))
        self.PushButton_delete.setText(self._ui_text("删除选中行", "Delete Selected Row"))
        self.PrimaryPushButton_add.setText(self._ui_text("新增", "Add"))

        self.BodyLabel_tips.setText(
            self._ui_text(
                "### 提示\n* 双击单元格可修改\n* 填好上面对应的内容后点击“新增”按钮可以添加新的替换规则\n* 错误文本：ocr识别出来的错误内容，如果看不到去设置那开启显示ocr识别结果。正确文本：游戏中对应的正确文字\n* 删除需要先选中你需要删除的行，然后再点删除按钮",
                "### Tips\n* Double-click a cell to edit\n* Fill the fields above and click Add to create a new replacement rule\n* Wrong Text: OCR-recognized incorrect text. If missing, enable OCR result display in Settings. Correct Text: expected in-game text\n* To delete, select a row first and then click Delete"
            ))

        power_usage_items = [self._ui_text('直接替换', 'Direct Replace'), self._ui_text('条件替换', 'Conditional Replace')]
        self.ComboBox_type.addItems(power_usage_items)
        self.LineEdit_before.setPlaceholderText(self._ui_text("错误文本", "Wrong Text"))
        self.LineEdit_after.setPlaceholderText(self._ui_text("正确文本", "Correct Text"))

        # 新增路径属性
        self.json_path = self.get_json_path()

        self.TableWidget_ocr_table.setBorderVisible(True)
        self.TableWidget_ocr_table.setBorderRadius(8)
        self.TableWidget_ocr_table.verticalHeader().hide()
        self.TableWidget_ocr_table.setHorizontalHeaderLabels([
            self._ui_text('类型', 'Type'),
            self._ui_text('替换前', 'Before'),
            self._ui_text('替换后', 'After')
        ])

        self.load_table()
        StyleSheet.OCR_TABLE.apply(self)

    def _connect_to_slot(self):
        self.PrimaryPushButton_add.clicked.connect(self.on_add_button_click)
        self.PushButton_delete.clicked.connect(self.delete_row)
        self.TableWidget_ocr_table.cellChanged.connect(self.change_row)
        self.TableWidget_ocr_table.cellDoubleClicked.connect(self.enter_cell)

    def get_json_path(self):
        """获取JSON文件的绝对路径"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        # 组合完整路径
        json_path = os.path.join(base_dir, "AppData", "ocr_replacements.json")

        # 如果AppData目录不存在则创建
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        # print(json_path)
        return json_path

    def enter_cell(self, row, col):
        cell_text = self.TableWidget_ocr_table.item(row, 0).text()
        self.old_type = 'direct' if cell_text in ["直接替换", "Direct Replace"] else 'conditional'
        self.old_key = self.TableWidget_ocr_table.item(row, 1).text()
        self.old_value = self.TableWidget_ocr_table.item(row, 2).text()

    def _ui_text(self, zh_text: str, en_text: str) -> str:
        return en_text if self._is_non_chinese_ui else zh_text

    def change_row(self, row, col):
        # 临时断开信号
        # self.TableWidget_ocr_table.cellChanged.disconnect(self.change_row)
        self.TableWidget_ocr_table.blockSignals(True)
        try:
            item = self.TableWidget_ocr_table.item(row, col)
            if not item:
                return
            if not (self.old_type and self.old_key and self.old_value):
                return
            data = self.load_json()
            if col == 0:
                print(item.text())
                if item.text() not in ["直接替换", "条件替换", "Direct Replace", "Conditional Replace"]:
                    InfoBar.error(
                        title=self._ui_text('类型错误', 'Type Error'),
                        content=self._ui_text("类型值支持“直接替换”或“条件替换”", "Type supports only 'Direct Replace' or 'Conditional Replace'"),
                        orient=Qt.Horizontal,
                        isClosable=True,  # disable close button
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    self.load_table()
                    return
                key_type = 'direct' if item.text() in ["直接替换", "Direct Replace"] else 'conditional'
                if key_type == self.old_type:
                    return
                if key_type == 'direct':
                    data[key_type][self.old_key] = self.old_value
                    del data['conditional'][self.old_key]
                else:
                    data[key_type][self.old_key] = self.old_value
                    del data['direct'][self.old_key]
            elif col == 1:
                if item.text() == self.old_key:
                    return
                data[self.old_type][item.text()] = self.old_value
                del data[self.old_type][self.old_key]
            else:
                if item.text() == self.old_value:
                    return
                data[self.old_type][self.old_key] = item.text()
            self.save_data(data)
            self.load_table()
            InfoBar.info(
                title=self._ui_text('修改成功', 'Updated'),
                content=self._ui_text("已成功修改对应的替换规则", "Replacement rule updated successfully"),
                orient=Qt.Horizontal,
                isClosable=True,  # disable close button
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
        finally:
            # 重新连接信号
            # self.TableWidget_ocr_table.cellChanged.connect(self.change_row)
            self.TableWidget_ocr_table.blockSignals(True)

    def on_add_button_click(self):
        try:
            # 临时断开信号
            # self.TableWidget_ocr_table.cellChanged.disconnect(self.change_row)
            self.TableWidget_ocr_table.blockSignals(True)
            replace_type = 'direct' if self.ComboBox_type.currentIndex() == 0 else 'conditional'
            original_text = self.LineEdit_before.text()
            replacement_text = self.LineEdit_after.text()

            if original_text == '' or replacement_text == '':
                InfoBar.error(
                    title=self._ui_text('替换文本不能为空', 'Text cannot be empty'),
                    content=self._ui_text("输入需要替换的前后文本", "Please input both before and after text"),
                    orient=Qt.Horizontal,
                    isClosable=True,  # disable close button
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
                return

            # 读取现有 JSON 文件
            data = self.load_json()
            # 添加新规则
            data[replace_type][original_text] = replacement_text
            # 写回 JSON 文件
            self.save_data(data)
            self.load_table()
            InfoBar.info(
                title=self._ui_text('添加成功', 'Added'),
                content=self._ui_text("已成功添加新的替换规则", "New replacement rule added successfully"),
                orient=Qt.Horizontal,
                isClosable=True,  # disable close button
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
        except Exception as e:
            print(e)
        finally:
            # 重新连接信号
            # self.TableWidget_ocr_table.cellChanged.connect(self.change_row)
            self.TableWidget_ocr_table.blockSignals(False)

    def load_json(self):
        # 确保文件存在
        if not os.path.exists(self.json_path):
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump({'direct': {}, 'conditional': {}}, f, indent=4)

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {str(e)}, path:{self.json_path}")
            return {'direct': {}, 'conditional': {}}

    def save_data(self, data):
        try:
            # 检查文件是否可写
            if os.path.exists(self.json_path):
                if not os.access(self.json_path, os.W_OK):
                    print(self._ui_text("错误：文件不可写！", "Error: file is not writable!"))
                    raise PermissionError(self._ui_text("文件不可写", "File is not writable"))
            print(self._ui_text("文件可写！", "File is writable!"))
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving JSON: {str(e)}, path:{self.json_path}")
            InfoBar.error(
                title=self._ui_text('保存失败', 'Save Failed'),
                content=self._ui_text("无法写入配置文件：", "Unable to write config file: ") + f"{str(e)}",
                isClosable=True,  # disable close button
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )

    def delete_row(self):
        try:
            # 临时断开信号
            # self.TableWidget_ocr_table.cellChanged.disconnect(self.change_row)

            # 阻断信号传送
            self.TableWidget_ocr_table.blockSignals(True)
            select_row = self.TableWidget_ocr_table.currentRow()
            if select_row >= 0:
                key_type = 'direct' if self.TableWidget_ocr_table.item(select_row,
                                                                       0).text() in ['直接替换', 'Direct Replace'] else 'conditional'
                key_to_delete = self.TableWidget_ocr_table.item(select_row, 1).text()
                data = self.load_json()
                if key_type not in data:
                    InfoBar.error(
                        title=self._ui_text('删除失败', 'Delete Failed'),
                        content=self._ui_text(f"{key_type} 不在 JSON 中！", f"{key_type} is not in JSON!"),
                        orient=Qt.Horizontal,
                        isClosable=True,  # disable close button
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    return
                if key_to_delete not in data[key_type]:
                    InfoBar.error(
                        title=self._ui_text('删除失败', 'Delete Failed'),
                        content=self._ui_text(f"键 '{key_to_delete}' 不存在于 {key_type} 中！",
                                              f"Key '{key_to_delete}' does not exist in {key_type}!"),
                        orient=Qt.Horizontal,
                        isClosable=True,  # disable close button
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    return
                del data[key_type][key_to_delete]
                self.save_data(data)
                self.load_table()
                InfoBar.info(
                    title=self._ui_text('删除成功', 'Deleted'),
                    content=self._ui_text("已删除对应行", "Selected row deleted"),
                    orient=Qt.Horizontal,
                    isClosable=True,  # disable close button
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title=self._ui_text('未选中需要删除的行', 'No row selected'),
                    content=self._ui_text("选中需要删除的行之后再点击删除", "Select a row to delete first, then click Delete"),
                    orient=Qt.Horizontal,
                    isClosable=True,  # disable close button
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
        except Exception as e:
            print(e)
        finally:
            # 重新连接信号
            # self.TableWidget_ocr_table.cellChanged.connect(self.change_row)
            self.TableWidget_ocr_table.blockSignals(False)

    def load_table(self):
        replacements = self.load_json()
        direct_dic = replacements['direct']
        conditional_dic = replacements['conditional']
        total_rows = len(direct_dic) + len(conditional_dic)
        self.TableWidget_ocr_table.setRowCount(total_rows)

        row_index = 0
        for key, value in direct_dic.items():
            self.TableWidget_ocr_table.setItem(row_index, 0, QTableWidgetItem(self._ui_text('直接替换', 'Direct Replace')))
            self.TableWidget_ocr_table.setItem(row_index, 1, QTableWidgetItem(key))
            self.TableWidget_ocr_table.setItem(row_index, 2, QTableWidgetItem(value))
            row_index += 1
        for key, value in conditional_dic.items():
            self.TableWidget_ocr_table.setItem(row_index, 0, QTableWidgetItem(self._ui_text('条件替换', 'Conditional Replace')))
            self.TableWidget_ocr_table.setItem(row_index, 1, QTableWidgetItem(key))
            self.TableWidget_ocr_table.setItem(row_index, 2, QTableWidgetItem(value))
            row_index += 1

        self.TableWidget_ocr_table.resizeColumnsToContents()
        # self.resize(self.parent.width(), self.parent.height())
