from __future__ import annotations

from pathlib import Path
from typing import Any

from app.framework.infra.config.app_config import is_non_chinese_ui_language, is_traditional_ui_language
from app.framework.i18n.runtime import report_i18n_event
from app.framework.infra.ui_manifest.context import ModuleContext
from app.framework.infra.ui_manifest.manifest_engine import ManifestEngine
from app.framework.infra.ui_manifest.models import ResolvedUIObject, UIReference, UIDefinition
from app.framework.infra.ui_manifest.schema import parse_position, resolve_position_for_environment


class UIResolveError(RuntimeError):
    def __init__(self, code: str, message: str, trace: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.trace = trace or []


class AssetResolver:
    @staticmethod
    def resolve(module_ctx: ModuleContext, image_path: str | None) -> str | None:
        if not image_path:
            return None
        p = Path(image_path)
        if p.exists():
            return str(p)
        if module_ctx.assets_dir is not None:
            cand = module_ctx.assets_dir / image_path
            if cand.exists():
                return str(cand)
        return image_path


def _resolve_locale() -> str:
    if is_non_chinese_ui_language():
        return "en"
    if is_traditional_ui_language():
        return "zh_HK"
    return "zh_CN"


class UIResolver:
    def __init__(self, engine: ManifestEngine | None = None):
        self.engine = engine or ManifestEngine()

    def resolve(
        self,
        ref: UIReference | UIDefinition,
        module_ctx: ModuleContext,
        *,
        locale: str | None = None,
        environment: dict[str, Any] | None = None,
        current_resolution: tuple[int, int] | None = None,
    ) -> ResolvedUIObject:
        trace: list[str] = []
        explain_trace: list[str] = []
        resolution_trace: list[str] = []
        env = environment or {}
        resolved_locale = locale or _resolve_locale()
        reference = self._coerce_reference(ref)
        snapshot = self.engine.load(
            module_ctx.module_id or "framework",
            module_ctx.generated_manifest_path,
            module_ctx.ui_manifest_path,
        )
        trace.append(f"manifest={snapshot.path}")
        explain_trace.append("resolve/manifest_loaded")

        definition = self._select_definition(reference, snapshot.definitions, module_ctx, trace)
        target, text_target, image_target, find_type = self._resolve_target(reference, definition, module_ctx, resolved_locale, trace)
        pos_obj = parse_position(
            (definition.position if definition and isinstance(definition.position, dict) else None),
            fallback_roi=reference.roi or (definition.roi if definition else None),
        )
        roi = resolve_position_for_environment(pos_obj, current_resolution=current_resolution)
        if current_resolution is not None:
            resolution_trace.append(f"resolution={current_resolution}")
            resolution_trace.append(f"anchor={pos_obj.anchor if pos_obj else 'none'}")
        threshold = (
            float(reference.threshold)
            if reference.threshold is not None
            else float(definition.threshold if (definition and definition.threshold is not None) else 0.5)
        )
        include = bool(reference.include if reference.include is not None else (definition.include if definition else True))
        need_ocr = bool(reference.need_ocr if reference.need_ocr is not None else (definition.need_ocr if definition else True))
        explain_trace.append("resolve/overlay_applied")

        return ResolvedUIObject(
            id=reference.id,
            text=text_target,
            image_path=image_target,
            target=target,
            find_type=find_type,
            roi=roi,
            threshold=threshold,
            include=include,
            need_ocr=need_ocr,
            module_name=module_ctx.module_name or module_ctx.module_id,
            locale=resolved_locale,
            environment=env,
            resolution_trace=resolution_trace,
            explain_trace=explain_trace,
            trace=trace,
            source_file=module_ctx.callsite_file,
            source_group=definition.group if definition else None,
        )

    @staticmethod
    def _coerce_reference(ref: UIReference | UIDefinition) -> UIReference:
        if isinstance(ref, UIReference):
            return ref
        return UIReference(
            id=ref.id,
            source_file=ref.source_file,
            source_line=ref.source_line,
            module_name=ref.module_name,
            text=(ref.content if isinstance(ref.content, str) and ref.kind == "text" else None),
            image=ref.image,
            roi=ref.roi,
            threshold=ref.threshold,
            include=ref.include,
            need_ocr=ref.need_ocr,
            find_type=ref.find_type,
            extra=ref.extra,
        )

    def _select_definition(
        self,
        ref: UIReference,
        definitions: dict[str, UIDefinition],
        module_ctx: ModuleContext,
        trace: list[str],
    ) -> UIDefinition | None:
        if not ref.id:
            trace.append("no_id_ref")
            return None
        definition = definitions.get(ref.id)
        if definition is None:
            self.engine.register_discovered_definition(
                module_ctx.module_id or "framework",
                module_ctx.generated_manifest_path,
                module_ctx.ui_manifest_path,
                UIDefinition(
                    id=ref.id,
                    content=ref.text if isinstance(ref.text, str) else ref.id,
                    kind="text",
                    text={"zh_CN": ref.text if isinstance(ref.text, str) else ref.id},
                    module_name=module_ctx.module_name or module_ctx.module_id,
                    source_file=module_ctx.callsite_file,
                    source_line=module_ctx.callsite_line,
                    group="discovered",
                ),
            )
            report_i18n_event(
                "ui_resolve_unresolved_reference",
                f"{module_ctx.module_id}:{ref.id}:{module_ctx.callsite_file}:{module_ctx.callsite_line}",
            )
            raise UIResolveError(
                "resolve/id_not_registered",
                f"UI id '{ref.id}' not found for module '{module_ctx.module_id}'",
                trace=trace + [f"id={ref.id}:missing"],
            )
        trace.append(f"id={ref.id}:found")
        return definition

    def _resolve_target(
        self,
        ref: UIReference,
        definition: UIDefinition | None,
        module_ctx: ModuleContext,
        locale: str,
        trace: list[str],
    ) -> tuple[str | list[str], str | list[str] | None, str | None, str]:
        # Overlay precedence (highest -> lowest):
        # reference override > definition group config > group defaults.
        if ref.image:
            resolved = AssetResolver.resolve(module_ctx, ref.image)
            trace.append("target=image(ref)")
            image_value = resolved or ref.image
            return image_value, None, image_value, ref.find_type or "image"
        if ref.text:
            trace.append("target=text(ref)")
            return ref.text, ref.text, None, ref.find_type or "text"

        if definition is not None:
            if definition.image:
                resolved = AssetResolver.resolve(module_ctx, definition.image)
                trace.append("target=image(def)")
                image_value = resolved or definition.image
                return image_value, None, image_value, ref.find_type or definition.find_type or "image"
            text_value = definition.text.get(locale) or definition.text.get("zh_CN") or definition.text.get("en")
            if text_value:
                targets = [text_value] + [a for a in definition.aliases if a != text_value]
                trace.append(f"target=text(def):locale={locale}")
                text_target = targets[0] if len(targets) == 1 else targets
                return text_target, text_target, None, ref.find_type or definition.find_type or "text"

        if ref.id:
            # Fallback for author-friendly short path: auto.click("start")
            report_i18n_event("ui_resolve_fallback_text_id", f"{module_ctx.module_id}:{ref.id}")
            trace.append("target=fallback:id_as_text")
            return ref.id, ref.id, None, ref.find_type or "text"

        raise UIResolveError("resolve/empty_target", "Unable to resolve UI target", trace=trace + ["target=none"])
