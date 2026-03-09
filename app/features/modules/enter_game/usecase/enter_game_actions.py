from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import Flyout, FlyoutView, InfoBar, InfoBarPosition

from app.framework.core.interfaces.game_environment import IGameEnvironment
from app.framework.ui.shared.text import ui_text

from .game_window_probe import is_snowbreak_running
from .launch_service import launch_game_with_guard


class SnowbreakGameEnvironment(IGameEnvironment):
    """Snowbreak-specific game runtime implementation."""

    def __init__(self, is_non_chinese_ui: bool):
        self._is_non_chinese_ui = bool(is_non_chinese_ui)

    def is_running(self) -> bool:
        return bool(is_snowbreak_running())

    def launch(self, logger=None) -> dict[str, Any]:
        return launch_game_with_guard(logger=logger)

    def get_tutorial_text(self) -> tuple[str, str]:
        title = "How to find the game path" if self._is_non_chinese_ui else "如何查找对应游戏路径"
        content = (
            'No matter which server/channel you play, first select your server in Settings.\n'
            'For global server, choose a path like "E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK".\n'
            'For CN/Bilibili server, open the Snowbreak launcher and find launcher settings.\n'
            'Then choose the game installation path shown there.'
            if self._is_non_chinese_ui
            else
            '不管你是哪个渠道服的玩家，第一步都应该先去设置里选服\n国际服选完服之后选择类似"E:\\SteamLibrary\\steamapps\\common\\SNOWBREAK"的路径\n官服和b服的玩家打开尘白启动器，新版或者旧版启动器都找到启动器里对应的设置\n在下面的路径选择中找到并选择刚才你看到的路径'
        )
        return title, content


class EnterGameActions:
    """Enter-game module actions hosted by periodic page."""

    def __init__(self, game_environment: IGameEnvironment):
        self.game_environment = game_environment

    def launch_game(self, logger=None) -> dict[str, Any]:
        """Compatibility wrapper for legacy callers."""
        return self.game_environment.launch(logger=logger)

    def show_path_tutorial(self, host, anchor_widget):
        tutorial_title, tutorial_content = self.game_environment.get_tutorial_text()
        view = FlyoutView(
            title=tutorial_title,
            content=tutorial_content,
            image="app/features/assets/enter_game/path_tutorial.png",
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

    def on_select_directory_click(self, *, host, line_edit, settings_usecase) -> None:
        folder = self.select_game_directory(
            parent=host,
            current_directory=line_edit.text(),
        )
        if not folder or settings_usecase.is_same_game_directory(folder):
            return
        line_edit.setText(folder)
        line_edit.editingFinished.emit()

    @staticmethod
    def on_auto_open_toggled(*, host, state: int) -> None:
        status = "已开启" if state == 2 else "已关闭"
        action = "将" if state == 2 else "不会"
        InfoBar.success(
            title=status,
            content=ui_text(
                f"点击“开始”按钮时{action}自动启动游戏",
                f"Clicking the 'Start' button will {action}automatically launch the game",
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host,
        )
