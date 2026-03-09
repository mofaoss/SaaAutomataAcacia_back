from app.framework.infra.system.windows import get_hwnd, is_fullscreen
from app.features.modules.enter_game.usecase.enter_game_usecase import (
    is_snowbreak_running,
)


def is_exist_snowbreak(server_interface: int = None):
    """Compatibility wrapper. Prefer `is_snowbreak_running` in enter_game module."""
    return is_snowbreak_running(server_interface)

