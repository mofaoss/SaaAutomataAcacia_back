from __future__ import annotations

from app.framework.ui.auto_page.on_demand import OnDemandAutoPage
from app.framework.ui.auto_page.periodic import PeriodicAutoPage


def _is_periodic_host(host_context) -> bool:
    host = getattr(host_context, "value", host_context)
    return str(host or "").strip().lower() == "periodic"


def build_auto_page(parent=None, *, module_meta=None, host_context=None):
    page_cls = PeriodicAutoPage if _is_periodic_host(host_context) else OnDemandAutoPage
    return page_cls(parent, module_meta=module_meta, host_context=host_context)


__all__ = ["OnDemandAutoPage", "PeriodicAutoPage", "build_auto_page"]
