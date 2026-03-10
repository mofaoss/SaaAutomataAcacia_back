import logging
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from app.framework.i18n import _, qt

from app.framework.infra.config.app_config import config
from app.framework.core.task_engine.threads import ModuleTaskThread
from app.framework.core.task_engine.base_task import BaseTask

logger = logging.getLogger(__name__)

class SubTask(ModuleTaskThread):
    def __init__(self, module, logger_instance=None):
        super().__init__(module, logger_instance or logger)


# 纯原生的 PySide6 取色对话框
class ColorPickDialog(QDialog):
    def __init__(self, img_np, parent=None):
        super().__init__(parent)
        self.setWindowTitle(qt(_("请点击图像上的黄色完美收杆区域 (提取颜色)")))

        # 【核心修复】：强制转换图像内存为连续的 C 风格内存块
        if not img_np.flags['C_CONTIGUOUS']:
            img_np = np.ascontiguousarray(img_np)

        self.img_np = img_np
        self.picked_hsv = None

        self.layout = QVBoxLayout(self)
        self.label = QLabel(self)
        self.layout.addWidget(self.label)

        # 将 numpy (BGR) 转换为 QPixmap
        height, width, channel = img_np.shape
        bytes_per_line = 3 * width

        # 现在传入 img_np.data 就绝对安全了
        qimg = QImage(img_np.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.label.setPixmap(QPixmap.fromImage(qimg))

        # 绑定鼠标点击事件
        self.label.mousePressEvent = self.on_image_clicked

    def on_image_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = event.pos().x(), event.pos().y()
            bgr_color = self.img_np[y, x]
            hsv_color = cv2.cvtColor(np.uint8([[bgr_color]]), cv2.COLOR_BGR2HSV)
            self.picked_hsv = hsv_color[0][0]
            self.accept()  # 点击后自动关闭对话框并返回成功状态


class AdjustColor(QThread, BaseTask):
    color_changed = Signal()
    # 【新增】发给主线程的 UI 渲染信号
    _show_ui_signal = Signal(object)

    def __init__(self):
        super().__init__()
        self.logger = logger
        # 将弹窗信号绑定到当前实例的方法（因该实例在主线程被创建，故此槽函数在主线程执行）
        self._show_ui_signal.connect(self._show_dialog)

    def run(self):
        if not self.init_auto('game'):
            self.logger.error(_("初始化自动化失败，无法打开颜色校准", msgid="init_automation_failed_unable_to_open_color_calibration"))
            return
        self.auto.take_screenshot()
        img_np = self.auto.get_crop_form_first_screenshot(crop=(1130 / 1920, 240 / 1080, 1500 / 1920, 570 / 1080), is_resize=False)

        # 取代 imshow：将截取好的图像发射给主线程弹出 UI
        self._show_ui_signal.emit(img_np)

    # 运行在主线程中的 UI 逻辑
    def _show_dialog(self, img_np):
        dialog = ColorPickDialog(img_np)
        if dialog.exec():  # 如果用户点击并成功提取了颜色
            hsv = dialog.picked_hsv
            self.logger.info(_(f"选定的HSV值: {hsv}"))
            self.save_color_to_config(hsv)
            self.color_changed.emit()

    def save_color_to_config(self, hsv_value):
        hue, sat, val = hsv_value
        lower_yellow = np.array([max(hue - 2, 0), max(sat - 35, 0), max(val - 10, 0)])
        upper_yellow = np.array([min(hue + 2, 179), min(sat + 35, 255), min(val + 10, 255)])
        base = f"{hue},{sat},{val}"
        upper = f"{upper_yellow[0]},{upper_yellow[1]},{upper_yellow[2]}"
        lower = f"{lower_yellow[0]},{lower_yellow[1]},{lower_yellow[2]}"
        config.set(config.LineEdit_fish_base, base)
        config.set(config.LineEdit_fish_upper, upper)
        config.set(config.LineEdit_fish_lower, lower)

