from qfluentwidgets import CheckBox

from app.framework.ui.views.periodic_base import ModulePageBase


class CloseGamePage(ModulePageBase):
    def __init__(self, parent=None):
        super().__init__("page_close_game", parent=parent, host_context="periodic", use_default_layout=True)

        self.CheckBox_close_game = CheckBox(self)
        self.CheckBox_close_game.setObjectName("CheckBox_close_game")
        self.CheckBox_close_proxy = CheckBox(self)
        self.CheckBox_close_proxy.setObjectName("CheckBox_close_proxy")
        self.CheckBox_shutdown = CheckBox(self)
        self.CheckBox_shutdown.setObjectName("CheckBox_shutdown")
        self.CheckBox_close_game.setText(_("Exit Game", msgid='exit_game'))
        self.CheckBox_close_proxy.setText(_("Exit SAA but don't shutdown", msgid='exit_saa_but_don_t_shutdown'))
        self.CheckBox_shutdown.setText(_("Shutdown PC", msgid='shutdown_pc'))

        self.main_layout.addWidget(self.CheckBox_close_game)
        self.main_layout.addWidget(self.CheckBox_close_proxy)
        self.main_layout.addWidget(self.CheckBox_shutdown)
        self.finalize()


