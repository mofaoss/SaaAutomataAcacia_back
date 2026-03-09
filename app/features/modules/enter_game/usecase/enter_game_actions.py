from __future__ import annotations

from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import Flyout, FlyoutView

from app.framework.core.interfaces.game_environment import IGameEnvironment


class EnterGameActions:
    """Enter-game module actions hosted by periodic page."""

    def __init__(self, game_environment: IGameEnvironment):
        self.game_environment = game_environment

    def show_path_tutorial(self, host, anchor_widget):
        tutorial_title, tutorial_content = self.game_environment.get_tutorial_text()
        view = FlyoutView(
            title=tutorial_title,
            content=tutorial_content,
            image="asset/path_tutorial.png",
            isClosable=True,
        )
        view.widgetLayout.insertSpacing(1, 5)
        view.widgetLayout.addSpacing(5)
        flyout = Flyout.make(view, anchor_widget, host)
        view.closed.connect(flyout.close)

    @staticmethod
    def select_game_directory(parent, current_directory: str) -> str | None:
        folder = QFileDialog.getExistingDirectory(parent, "选择游戏文件夹", "./")
        if not folder or str(folder) == str(current_directory):
            return None
        return folder
