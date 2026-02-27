# coding:utf-8
import os
import sys
import time

from win11toast import toast

from PyQt5.QtCore import Qt, QTranslator
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentTranslator

from app.common.config import config, resolve_configured_locale
from app.common.ui_localizer import patch_infobar_for_traditional, localize_widget_tree_for_traditional
from app.view.main_window import MainWindow

# enable dpi scale
if config.get(config.dpiScale) != "Auto":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    os.environ["QT_SCALE_FACTOR"] = str(config.get(config.dpiScale))
else:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

# create application
app = QApplication(sys.argv)
app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

# internationalization
locale = resolve_configured_locale(config.get(config.language))
translator = FluentTranslator(locale)
galleryTranslator = QTranslator()
galleryTranslator.load(locale, "app", ".", ":/app/resource/i18n")

app.installTranslator(translator)
app.installTranslator(galleryTranslator)

patch_infobar_for_traditional()

# create main window
w = MainWindow()
localize_widget_tree_for_traditional(w)
w.show()

app.exec()
