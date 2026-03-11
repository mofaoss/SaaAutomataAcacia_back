from __future__ import annotations

import inspect

from app.framework.infra.ui_manifest.context import ModuleContext
from app.framework.infra.ui_manifest.explain import UIExplainResult
from app.framework.infra.ui_manifest.manifest_engine import ManifestEngine
from app.framework.infra.ui_manifest.models import UIDefinition, UIReference, ResolvedUIObject
from app.framework.infra.ui_manifest.resolver import AssetResolver, UIResolveError, UIResolver


def U(
    text_or_id: str,
    *,
    id: str | None = None,
    roi: tuple[float, float, float, float] | None = None,
    image: str | None = None,
    threshold: float | None = None,
    include: bool | None = None,
    need_ocr: bool | None = None,
    find_type: str | None = None,
    **kwargs,
) -> UIReference | UIDefinition:
    # Keep author-facing API tiny and native:
    # U("开始", id="start", roi=(...))
    # U("start")
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    source_file = getattr(getattr(caller, "f_code", None), "co_filename", None)
    source_line = getattr(caller, "f_lineno", None)
    inferred_id = id or (text_or_id if "/" not in text_or_id and "\\" not in text_or_id else None)
    inferred_text = text_or_id if id else None
    is_definition = bool(id or image or roi is not None or threshold is not None or find_type)
    if is_definition:
        resolved_kind = "image" if image else "text"
        return UIDefinition(
            id=inferred_id or text_or_id,
            content=text_or_id,
            kind=resolved_kind,
            text={"zh_CN": text_or_id} if resolved_kind == "text" else {},
            image=image,
            roi=roi,
            threshold=threshold,
            include=include,
            need_ocr=need_ocr,
            find_type=find_type or resolved_kind,
            source_file=source_file,
            source_line=int(source_line) if isinstance(source_line, int) else None,
            extra=dict(kwargs),
        )
    return UIReference(
        id=inferred_id,
        source_file=source_file,
        source_line=int(source_line) if isinstance(source_line, int) else None,
        text=inferred_text,
        image=image,
        roi=roi,
        threshold=threshold,
        include=include,
        need_ocr=need_ocr,
        find_type=find_type,
        extra=dict(kwargs),
    )


__all__ = [
    "U",
    "UIDefinition",
    "UIReference",
    "ResolvedUIObject",
    "ManifestEngine",
    "ModuleContext",
    "AssetResolver",
    "UIResolver",
    "UIResolveError",
    "UIExplainResult",
]
