from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ModuleHost(str, Enum):
    PERIODIC = "periodic"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True, slots=True)
class Field:
    """Decorator-time field metadata for stable i18n field IDs and layout hints."""

    id: str | None = None
    label: str | None = None
    help: str | None = None
    group: str | None = None
    layout: Literal["full", "half", "row"] = "full"
    icon: str | None = None
    description_md: str | None = None


@dataclass(slots=True)
class SchemaField:
    param_name: str
    field_id: str
    type_hint: Any
    default: Any
    required: bool
    label_key: str
    help_key: str
    label_default: str
    help_default: str | None = None
    group: str | None = None
    layout: Literal["full", "half", "row"] = "full"
    icon: str | None = None
    description_md: str | None = None


@dataclass(slots=True)
class ModuleMeta:
    id: str
    name: str
    host: ModuleHost
    runner: Callable[..., Any]

    page_cls: type | None = None
    ui_factory: Callable[[object, ModuleHost], object] | None = None
    module_class: type | None = None
    ui_bindings: Any = None

    order: int = 100
    description: str = ""
    enabled: bool = True
    passive: bool = False

    en_name: str = ""

    periodic_enabled_by_default: bool = False
    periodic_mandatory: bool = False
    periodic_force_first: bool = False
    periodic_default_hour: int = 4
    periodic_default_minute: int = 0
    periodic_max_runs: int = 1
    periodic_requires_home_sync: bool = True
    periodic_ui_page_index: int | None = None
    periodic_option_key: str | None = None
    periodic_default_activation_config: list[dict[str, Any]] = field(default_factory=list)

    config_schema: list[SchemaField] = field(default_factory=list)
    source_lang: str = "en"
    i18n_owner_dir: str | None = None
    generated_module_class: type | None = None

    def display_name(self, is_non_chinese_ui: bool) -> str:
        if is_non_chinese_ui and self.en_name:
            return self.en_name
        return self.name
