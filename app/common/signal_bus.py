# coding: utf-8
from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """ Signal bus """

    checkUpdateSig = Signal(int)
    micaEnableChanged = Signal(bool)
    switchToSampleCard = Signal(str, int)
    updatePiecesNum = Signal(dict)
    jigsawDisplaySignal = Signal(list)
    showMessageBox = Signal(str, str)
    updateFishKey = Signal(str)
    showScreenshot = Signal(object)
    sendHwnd = Signal(int)
    windowTrackingStealthChanged = Signal(bool, int)

    globalTaskStateChanged = Signal(bool, str, str, str)

    # 【新增】全局停止请求总线 (当按下F8且有任务运行时触发)
    globalStopRequest = Signal()



signalBus = SignalBus()
