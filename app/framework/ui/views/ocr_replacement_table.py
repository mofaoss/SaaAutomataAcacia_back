import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QTableWidgetItem
from qfluentwidgets import InfoBar, InfoBarPosition

from app.framework.infra.config.app_config import is_non_chinese_ui_language
from app.framework.ui.shared.style_sheet import StyleSheet
from app.framework.infra.runtime.paths import APPDATA_DIR, ensure_runtime_dirs
from .periodic_base import BaseInterface
from app.framework.ui.views.ocr_replacement_table_view import OcrReplacementTableView
from app.framework.i18n import _


class OcrReplacementTable(QFrame, BaseInterface):
    def __init__(self, text: str, parent=None):
        super().__init__()
        BaseInterface.__init__(self)

        self.ui = OcrReplacementTableView(self)
        self._is_non_chinese_ui = is_non_chinese_ui_language()
        self.setObjectName(text.replace(' ', '-'))
        self.parent = parent

        self.old_type = None
        self.old_key = None
        self.old_value = None

        self._initWidget()
        self._connect_to_slot()

    def __getattr__(self, name):
        if "ui" in self.__dict__ and hasattr(self.ui, name):
            return getattr(self.ui, name)
        raise AttributeError(f"{self.__class__.__name__} object has no attribute '{name}'")

    def _initWidget(self):
        self.BodyLabel.setText(_('replacement type'))
        self.BodyLabel_2.setText(_('Before replacement'))
        self.BodyLabel_3.setText(_('After replacement'))
        self.PushButton_delete.setText(_('Delete selected row'))
        self.PrimaryPushButton_add.setText(_('New'))

        self.BodyLabel_tips.setText(
            _('### Tips\n* This is a replacement table for OCR recognition issues\n* Double-click a cell to edit\n* Fill the fields above and click Add to create a new replacement rule\n* Wrong Text: OCR-recognized incorrect text. If missing, enable OCR result display in Settings\n* Correct Text: expected in-game text\n* To delete, select a row first and then click Delete'))

        power_usage_items = [_('direct replacement'), _('Conditional replacement')]
        self.ComboBox_type.addItems(power_usage_items)
        self.LineEdit_before.setPlaceholderText(_('error text'))
        self.LineEdit_after.setPlaceholderText(_('correct text'))

        # 新增路径属性
        self.json_path = self.get_json_path()

        self.TableWidget_ocr_table.setBorderVisible(True)
        self.TableWidget_ocr_table.setBorderRadius(8)
        self.TableWidget_ocr_table.verticalHeader().hide()
        self.TableWidget_ocr_table.horizontalHeader().show()
        self.TableWidget_ocr_table.setHorizontalHeaderLabels([
            _('type'),
            _('Before replacement'),
            _('After replacement')
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
        ensure_runtime_dirs()
        json_path = str(APPDATA_DIR / "ocr_replacements.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        return json_path

    def enter_cell(self, row, col):
        cell_text = self.TableWidget_ocr_table.item(row, 0).text()
        self.old_type = 'direct' if cell_text in ["直接替换", "Direct Replace"] else 'conditional'
        self.old_key = self.TableWidget_ocr_table.item(row, 1).text()
        self.old_value = self.TableWidget_ocr_table.item(row, 2).text()

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
                        title=_('type error'),
                        content=_('Type values support "direct replacement" or "conditional replacement"'),
                        orient=Qt.Orientation.Horizontal,
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
                title=_('Modification successful'),
                content=_('The corresponding replacement rule has been modified successfully'),
                orient=Qt.Orientation.Horizontal,
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
                    title=_('Replacement text cannot be empty'),
                    content=_('Enter the text before and after that needs to be replaced'),
                    orient=Qt.Orientation.Horizontal,
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
                title=_('Added successfully'),
                content=_('New replacement rule added successfully'),
                orient=Qt.Orientation.Horizontal,
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
                    print(_('Error: File is not writable!'))
                    raise PermissionError(_('File cannot be written'))
            print(_('The file is writable!'))
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving JSON: {str(e)}, path:{self.json_path}")
            InfoBar.error(
                title=_('Save failed'),
                content=_('Unable to write to configuration file:') + f"{str(e)}",
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
                        title=_('Delete failed'),
                        content=_('{key_type} is not in JSON!').format(key_type=key_type),
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,  # disable close button
                        position=InfoBarPosition.TOP_RIGHT,
                        duration=2000,
                        parent=self
                    )
                    return
                if key_to_delete not in data[key_type]:
                    InfoBar.error(
                        title=_('Delete failed'),
                        content=_("Key '{key_to_delete}' does not exist in {key_type}!").format(key_to_delete=key_to_delete, key_type=key_type),
                        orient=Qt.Orientation.Horizontal,
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
                    title=_('Deleted'),
                    content=_('The corresponding row has been deleted'),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,  # disable close button
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title=_('The rows that need to be deleted are not selected'),
                    content=_('Select the rows you want to delete and click Delete'),
                    orient=Qt.Orientation.Horizontal,
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
        self.TableWidget_ocr_table.clearSpans()
        self.TableWidget_ocr_table.setRowCount(total_rows)

        row_index = 0
        for key, value in direct_dic.items():
            self.TableWidget_ocr_table.setItem(row_index, 0, QTableWidgetItem(_('direct replacement')))
            self.TableWidget_ocr_table.setItem(row_index, 1, QTableWidgetItem(key))
            self.TableWidget_ocr_table.setItem(row_index, 2, QTableWidgetItem(value))
            row_index += 1
        for key, value in conditional_dic.items():
            self.TableWidget_ocr_table.setItem(row_index, 0, QTableWidgetItem(_('Conditional replacement')))
            self.TableWidget_ocr_table.setItem(row_index, 1, QTableWidgetItem(key))
            self.TableWidget_ocr_table.setItem(row_index, 2, QTableWidgetItem(value))
            row_index += 1

        if total_rows == 0:
            self.TableWidget_ocr_table.setRowCount(1)
            empty_item = QTableWidgetItem(_('No replacement rules yet'))
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.TableWidget_ocr_table.setItem(0, 0, empty_item)
            self.TableWidget_ocr_table.setSpan(0, 0, 1, 3)

        self.TableWidget_ocr_table.resizeColumnsToContents()
        # self.resize(self.parent.width(), self.parent.height())
