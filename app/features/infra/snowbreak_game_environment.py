from __future__ import annotations

from typing import Any

from app.features.modules.enter_game.usecase.enter_game_usecase import launch_game_with_guard
from app.features.utils.windows import is_exist_snowbreak
from app.framework.core.interfaces.game_environment import IGameEnvironment


class SnowbreakGameEnvironment(IGameEnvironment):
    """Snowbreak-specific game runtime implementation."""

    def __init__(self, is_non_chinese_ui: bool):
        self._is_non_chinese_ui = bool(is_non_chinese_ui)

    def is_running(self) -> bool:
        return bool(is_exist_snowbreak())

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

