import sys
import os
# from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QTextBrowser
# from PySide6.QtGui import QIcon

from pathlib import Path


def app_dir():
    """Returns the base application path."""
    if hasattr(sys, "frozen"):
        # Handles PyInstaller
        return Path(sys.executable).parent  # 使用pyinstaller打包后的exe目录
    return Path(__file__).resolve().parent.parent  # 没打包前的项目根目录


class Config:
    app_ver = "2.3.1"
    app_name = "SaaAutomataAcacia"
    app_exec = "SAA"
    app_publisher = "mofaoss"
    app_url = "https://github.com/mofaoss/SaaAutomataAcacia"
    app_icon = "app/resource/images/logo.ico"
    app_dir = os.getenv("SAA_APP_DIR", str(app_dir()))

# class MainWindow(QDialog):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         # self.setWindowFlags(Qt.WindowCloseButtonHint)  # 只显示关闭按钮
#         self.setFixedSize(400, 300)
#
#         self.setWindowTitle("HELLO")
#         layout = QVBoxLayout(self)
#         purpose = QTextBrowser()
#         purpose.setText("Perfect Build!\n" * 50)
#         purpose.setReadOnly(True)  # 设置为只读，防止用户编辑文本
#         layout.addWidget(purpose)
#         self.setLayout(layout)
#
#
# if __name__ == "__main__":
#     app = QApplication([])
#     window = MainWindow()
#     window.setWindowIcon(QIcon(Config.app_icon))
#     window.show()
#     app.exec()
