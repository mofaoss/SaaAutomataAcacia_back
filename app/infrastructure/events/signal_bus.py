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

    requestExitApp = Signal()



signalBus = SignalBus()
