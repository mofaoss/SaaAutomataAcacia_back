from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


RecordKind = Literal["static", "dynamic_template"]


@dataclass(slots=True)
class BaseI18nRecord:
    kind: RecordKind
    msgid: str
    owner_scope: str
    owner_module: str | None
    source_language: str
    source_text: str


@dataclass(slots=True)
class StaticRecord(BaseI18nRecord):
    kind: Literal["static"] = "static"


@dataclass(slots=True)
class DynamicTemplateRecord(BaseI18nRecord):
    kind: Literal["dynamic_template"] = "dynamic_template"
    template_id: str = ""
    source_template: str = ""
    fields: list[str] = field(default_factory=list)
    field_details: dict[str, dict[str, str]] = field(default_factory=dict)
    template_hash: str = ""
    callsite_key: str = ""
    file_path: str = ""
    line: int = 0
    col: int = 0
    function_name: str = ""
    class_name: str | None = None
    context: str = "ui"
    is_runtime_visible: bool = True
