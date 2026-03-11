from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Literal


class HostContext(str, Enum):
    PERIODIC = "periodic"
    ON_DEMAND = "on_demand"


@dataclass(frozen=True)
class ModuleUiBindings:
    page_attr: str
    start_button_attr: Optional[str] = None
    card_widget_attr: Optional[str] = None
    log_widget_attr: Optional[str] = None


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    zh_name: str
    en_name: str
    order: int
    hosts: tuple[HostContext, ...]
    ui_factory: Callable[[object, HostContext], object]
    module_class: Optional[type] = None
    ui_bindings: Optional[ModuleUiBindings] = None
    passive: bool = False
    on_demand_execution: Literal["exclusive", "background"] = "exclusive"

    def supports(self, host: HostContext) -> bool:
        return host in self.hosts

    def get_name(self, is_non_chinese_ui: bool) -> str:
        return self.en_name if is_non_chinese_ui else self.zh_name
