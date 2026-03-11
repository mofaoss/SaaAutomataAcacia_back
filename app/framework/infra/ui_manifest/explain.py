from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RESOLVE_FAILURES = {
    "id_not_registered",
    "manifest_conflict",
    "locale_override_missing",
    "asset_file_missing",
    "environment_override_missing",
}

MATCH_FAILURES = {
    "ocr_text_not_found",
    "image_match_below_threshold",
    "roi_out_of_bounds",
    "multiple_candidates_found",
}

EXECUTE_FAILURES = {
    "click_target_not_resolved",
    "window_state_invalid",
    "task_precondition_failed",
}


@dataclass(slots=True)
class UIExplainResult:
    ok: bool
    layer: str
    code: str
    detail: str
    resolved: dict[str, Any] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)

