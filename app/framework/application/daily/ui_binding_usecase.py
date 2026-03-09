# coding:utf-8
from functools import partial
from typing import Any, Callable

from qfluentwidgets import CheckBox, ComboBox, LineEdit, SpinBox

from app.features.utils.ui import get_all_children


class DailyUiBindingUseCase:
    """Encapsulate UI signal wiring for daily config persistence."""

    @staticmethod
    def connect_config_bindings(
        *,
        root_widget: Any,
        person_selector: Any,
        weapon_selector: Any,
        on_widget_change: Callable[[Any], None],
        on_person_item_state_change: Callable[[int, int], None],
        on_weapon_item_state_change: Callable[[int, int], None],
    ) -> None:
        person_selector.itemStateChanged.connect(on_person_item_state_change)
        weapon_selector.itemStateChanged.connect(on_weapon_item_state_change)

        for child in get_all_children(root_widget):
            if isinstance(child, CheckBox):
                child.stateChanged.connect(partial(on_widget_change, child))
            elif isinstance(child, ComboBox):
                child.currentIndexChanged.connect(partial(on_widget_change, child))
            elif isinstance(child, LineEdit):
                child.editingFinished.connect(partial(on_widget_change, child))
            elif isinstance(child, SpinBox):
                child.valueChanged.connect(partial(on_widget_change, child))
