from __future__ import annotations

from app.framework.application.modules.contracts import ModuleSpec, ModuleUiBindings
from app.framework.core.module_system import ModuleHost, get_modules_by_host, make_module_class
from app.framework.core.module_system.naming import humanize_name
from app.framework.i18n.runtime import get_catalog


def _fallback_title_from_module_id(module_id: str) -> str:
    normalized = str(module_id or "").strip()
    if normalized.startswith("task_"):
        normalized = normalized[len("task_"):]
    readable = humanize_name(normalized)
    return readable or (module_id or "")


def _resolve_localized_titles(meta) -> tuple[str, str]:
    key = f"module.{meta.id}.title"
    legacy_key = "module.dummy.title"
    en_catalog = get_catalog("en")
    zh_cn_catalog = get_catalog("zh_CN")
    zh_hk_catalog = get_catalog("zh_HK")

    fallback_title = _fallback_title_from_module_id(meta.id)
    en_name = (
        en_catalog.get(key)
        or en_catalog.get(legacy_key)
        or meta.en_name
        or meta.name
        or fallback_title
    ).strip()
    zh_name = (
        zh_cn_catalog.get(key)
        or zh_hk_catalog.get(key)
        or zh_cn_catalog.get(legacy_key)
        or zh_hk_catalog.get(legacy_key)
        or en_name
    ).strip()

    return zh_name, en_name


def _meta_to_spec(meta, host: ModuleHost) -> ModuleSpec:
    if meta.ui_factory is None:
        if meta.page_cls is not None:
            meta.ui_factory = lambda parent, _host: meta.page_cls(parent)
        else:
            from app.framework.ui.auto_page.factory import build_auto_page

            meta.ui_factory = lambda parent, host_ctx, _meta=meta: build_auto_page(parent, module_meta=_meta, host_context=host_ctx)

    if meta.ui_bindings is None:
        meta.ui_bindings = ModuleUiBindings(
            page_attr=f"page_{meta.id}",
            start_button_attr="PushButton_start",
            card_widget_attr="SimpleCardWidget_option",
            log_widget_attr="textBrowser_log",
        )

    module_class = meta.module_class or make_module_class(meta)
    zh_name, en_name = _resolve_localized_titles(meta)
    return ModuleSpec(
        id=meta.id,
        zh_name=zh_name,
        en_name=en_name,
        order=meta.order,
        hosts=(host,),
        ui_factory=meta.ui_factory,
        module_class=module_class,
        ui_bindings=meta.ui_bindings,
        passive=meta.passive,
        on_demand_execution=getattr(meta, "on_demand_execution", "exclusive"),
    )


def get_periodic_module_specs() -> list[ModuleSpec]:
    metas = get_modules_by_host(ModuleHost.PERIODIC)
    return [_meta_to_spec(meta, ModuleHost.PERIODIC) for meta in metas]


def get_on_demand_module_specs(*, include_passive: bool = True) -> list[ModuleSpec]:
    metas = get_modules_by_host(ModuleHost.ON_DEMAND)
    if not include_passive:
        metas = [meta for meta in metas if not meta.passive]
    return [_meta_to_spec(meta, ModuleHost.ON_DEMAND) for meta in metas]

