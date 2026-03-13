from __future__ import annotations

import pytest

from app.framework.core.module_system import Field, Group, on_demand_module, periodic_module
from app.framework.core.module_system.naming import infer_module_id
from app.framework.core.module_system.registry import clear_registry, get_module


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_on_demand_module_id_infers_from_class_name_when_omitted():
    @on_demand_module("Demo")
    class CloseGameModule:
        def run(self, CheckBox_enabled: bool = True):
            return None

    meta = get_module("close_game")
    assert meta is not None
    assert meta.id == "close_game"


def test_periodic_module_id_infers_and_prefixes_task_when_omitted():
    @periodic_module("Demo Task")
    class CloseGameModule:
        def run(self, CheckBox_enabled: bool = True):
            return None

    meta = get_module("task_close_game")
    assert meta is not None
    assert meta.id == "task_close_game"


def test_field_id_defaults_to_field_key_when_omitted():
    @on_demand_module("Demo", fields={"ComboBox_plan_mode": Field(name="Plan Mode")})
    def plan_module(ComboBox_plan_mode: str = "fast"):
        return None

    meta = get_module("plan_module")
    assert meta is not None
    schema = {field.param_name: field for field in meta.config_schema}
    assert schema["ComboBox_plan_mode"].field_id == "ComboBox_plan_mode"


def test_explicit_module_id_must_be_python_identifier():
    with pytest.raises(ValueError, match="English identifier"):
        @on_demand_module("Demo", module_id="close-game")
        class CloseGameModule:
            def run(self):
                return None


def test_infer_module_id_normalizes_non_word_chars():
    dynamic_cls = type("Close Game-Module", (), {})
    assert infer_module_id(dynamic_cls) == "close_game"


def test_short_layout_api_scopes_are_registered():
    @periodic_module(
        "Demo Task",
        collapse=True,
        collapsed=False,
        layout="single_column",
        groups={"General": Group(layout="two_column", collapse=True, collapsed=True)},
    )
    class LayoutScopeModule:
        def run(self, CheckBox_enabled: bool = True):
            return None

    meta = get_module("task_layout_scope")
    assert meta is not None
    assert meta.collapse is True
    assert meta.collapsed is False
    assert meta.layout == "single_column"
    assert "General" in meta.groups
    assert meta.groups["General"].layout == "two_column"
    assert meta.groups["General"].collapse is True
    assert meta.groups["General"].collapsed is True


def test_invalid_layout_value_raises():
    with pytest.raises(ValueError, match="must be one of"):
        @periodic_module("Demo Task", layout="triple_column")
        class BadLayoutModule:
            def run(self):
                return None
