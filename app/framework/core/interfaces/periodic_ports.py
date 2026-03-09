from __future__ import annotations

from typing import Any, Callable, Protocol

from app.framework.core.interfaces.game_environment import IGameEnvironment


class PeriodicTaskProfilePort(Protocol):
    task_registry: dict[str, dict[str, Any]]
    primary_task_id: str
    mandatory_task_ids: list[str]
    primary_option_key: str


class ShoppingSelectionPort(Protocol):
    def load_item_config(self, *, settings_usecase, root_widget) -> None:
        ...

    def connect_selector_bindings(self, *, root_widget, settings_usecase) -> None:
        ...


class EnterGameActionsPort(Protocol):
    def launch_game(self, *, logger=None) -> dict[str, Any]:
        ...

    def show_path_tutorial(self, *, host, anchor_widget, tutorial_page=None) -> None:
        ...

    def on_select_directory_click(self, *, host, line_edit, settings_usecase) -> None:
        ...

    def on_auto_open_toggled(self, *, host, state: int) -> None:
        ...


class CollectSuppliesActionsPort(Protocol):
    def on_import_codes_click(self, *, host, text_edit) -> None:
        ...

    def on_reset_codes_click(self, *, host, text_edit) -> None:
        ...


class EventTipsActionsPort(Protocol):
    def bind(self, *, ui, logger, host) -> None:
        ...

    def refresh_tips(self) -> None:
        ...


TaskProfileProvider = Callable[[], PeriodicTaskProfilePort]
ShoppingSelectionFactory = Callable[[bool], ShoppingSelectionPort]
EnterGameActionsFactory = Callable[[IGameEnvironment], EnterGameActionsPort]
CollectSuppliesActionsFactory = Callable[[Any], CollectSuppliesActionsPort]
EventTipsActionsFactory = Callable[[Any, bool, Callable[[str, str], str]], EventTipsActionsPort]
