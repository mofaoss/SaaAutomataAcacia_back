from __future__ import annotations

from app.framework.ui.auto_page.base import AutoPageBase


class PeriodicAutoPage(AutoPageBase):
    """Auto-generated module page for periodic host.

    Periodic scheduling and log surfaces are provided by the host page,
    so this page only renders module settings/tips/actions.
    """

    def _should_show_start_button(self) -> bool:
        return False

    def _should_show_log_panel(self) -> bool:
        return False

    def __init__(self, parent=None, *, module_meta=None, host_context=None):
        super().__init__(parent, module_meta=module_meta, host_context=host_context)
        # Periodic host uses a denser middle column; keep content compact.
        self.main_layout.setSpacing(12)
        self.left_panel_layout.setSpacing(10)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
