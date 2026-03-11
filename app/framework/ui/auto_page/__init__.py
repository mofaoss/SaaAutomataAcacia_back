from app.framework.ui.auto_page.base import AutoPageBase
from app.framework.ui.auto_page.on_demand import OnDemandAutoPage
from app.framework.ui.auto_page.periodic import PeriodicAutoPage
from app.framework.ui.auto_page.factory import build_auto_page

__all__ = [
    "AutoPageBase",
    "OnDemandAutoPage",
    "PeriodicAutoPage",
    "build_auto_page",
]
