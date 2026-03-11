from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UIDefinition:
    id: str
    content: str | dict[str, str] | None = None
    kind: str = "text"
    text: dict[str, str] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    image: str | None = None
    position: dict[str, Any] | None = None
    roi: tuple[float, float, float, float] | None = None
    threshold: float | None = None
    include: bool | None = None
    need_ocr: bool | None = None
    find_type: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    module_name: str | None = None
    group: str = "mixed"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UIReference:
    id: str | None = None
    source_file: str | None = None
    source_line: int | None = None
    module_name: str | None = None
    text: str | list[str] | None = None
    image: str | None = None
    roi: tuple[float, float, float, float] | None = None
    threshold: float | None = None
    include: bool | None = None
    need_ocr: bool | None = None
    find_type: str | None = None
    source_hint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResolvedUIObject:
    id: str | None
    target: str | list[str]
    find_type: str
    roi: tuple[float, float, float, float]
    threshold: float
    include: bool
    need_ocr: bool
    text: str | list[str] | None = None
    image_path: str | None = None
    module_name: str | None = None
    locale: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    resolution_trace: list[str] = field(default_factory=list)
    explain_trace: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    source_file: str | None = None
    source_group: str | None = None

    def to_click_kwargs(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "find_type": self.find_type,
            "threshold": self.threshold,
            "crop": self.roi,
            "include": self.include,
            "need_ocr": self.need_ocr,
        }
