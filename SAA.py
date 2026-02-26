# coding:utf-8
import os
import sys
import time

from win11toast import toast

from PyQt5.QtCore import Qt, QTranslator, QLocale
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import FluentTranslator

from app.common.config import config
from app.view.main_window import MainWindow


def normalize_app_locale(locale):
    if not isinstance(locale, QLocale):
        locale = QLocale(str(locale))

    locale_name = locale.name().replace('-', '_')
    if locale_name in {"zh_HK", "zh_TW", "zh_MO", "zh_Hant", "zh_Hant_TW", "zh_Hant_HK", "zh_Hant_MO"} \
            or locale_name.startswith("zh_Hant"):
        return QLocale(QLocale.Chinese, QLocale.HongKong)
    if locale_name.startswith("zh"):
        return QLocale(QLocale.Chinese, QLocale.China)
    return locale


def resolve_configured_locale(language_config):
    if language_config == config.language.defaultValue:
        system_locale = QLocale.system()
        if system_locale.name().replace('-', '_').startswith("zh"):
            return normalize_app_locale(system_locale)
        return system_locale

    return normalize_app_locale(language_config.value)

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

# create main window
w = MainWindow()
w.show()

app.exec()
