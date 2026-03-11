from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Position:
    x: float
    y: float
    w: float
    h: float
    anchor: str = "top_left"
    base_resolution: tuple[int, int] = (1920, 1080)

    def to_roi(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)


def parse_position(node: Any, fallback_roi: tuple[float, float, float, float] | None = None) -> Position | None:
    if isinstance(node, dict):
        try:
            return Position(
                x=float(node.get("x", 0.0)),
                y=float(node.get("y", 0.0)),
                w=float(node.get("w", 1.0)),
                h=float(node.get("h", 1.0)),
                anchor=str(node.get("anchor", "top_left")),
                base_resolution=tuple(node.get("base_resolution", (1920, 1080))),  # type: ignore[arg-type]
            )
        except Exception:
            return None
    if fallback_roi is not None:
        return Position(x=fallback_roi[0], y=fallback_roi[1], w=fallback_roi[2], h=fallback_roi[3])
    return None


def resolve_position_for_environment(
    position: Position | None,
    *,
    current_resolution: tuple[int, int] | None = None,
) -> tuple[float, float, float, float]:
    if position is None:
        return (0.0, 0.0, 1.0, 1.0)
    if current_resolution is None:
        return position.to_roi()

    base_w, base_h = position.base_resolution
    cur_w, cur_h = current_resolution
    if base_w <= 0 or base_h <= 0 or cur_w <= 0 or cur_h <= 0:
        return position.to_roi()

    # Anchor-aware normalization: preserve anchor semantics before scale.
    x, y, w, h = position.x, position.y, position.w, position.h
    if position.anchor == "center":
        cx = x + w / 2
        cy = y + h / 2
        scale_x = cur_w / base_w
        scale_y = cur_h / base_h
        w2 = w * scale_x
        h2 = h * scale_y
        x2 = cx * scale_x - w2 / 2
        y2 = cy * scale_y - h2 / 2
        return (x2, y2, w2, h2)
    if position.anchor == "bottom_right":
        right = 1 - (x + w)
        bottom = 1 - (y + h)
        return (1 - right - w, 1 - bottom - h, w, h)
    return position.to_roi()

