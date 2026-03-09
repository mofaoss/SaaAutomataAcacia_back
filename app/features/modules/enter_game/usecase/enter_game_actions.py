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


class EnterGameActions:
    """Enter-game module actions hosted by periodic page."""

    def __init__(self, game_environment: IGameEnvironment):
        self.game_environment = game_environment

    def launch_game(self, logger=None) -> dict[str, Any]:
        """Compatibility wrapper for legacy callers."""
        return self.game_environment.launch(logger=logger)

    def show_path_tutorial(self, *, host, anchor_widget, tutorial_page=None):
        payload = None
        if tutorial_page is not None and hasattr(tutorial_page, "build_path_tutorial_payload"):
            payload = tutorial_page.build_path_tutorial_payload(getattr(host, "_is_non_chinese_ui", False))
        if not payload:
            from app.features.modules.enter_game.ui.enter_game_periodic_page import EnterGamePage

            payload = EnterGamePage.build_path_tutorial_payload(
                getattr(host, "_is_non_chinese_ui", False)
            )

        view = FlyoutView(
            title=payload.get("title", ""),
            content=payload.get("content", ""),
            image=payload.get("image", ""),
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
