from __future__ import annotations

from app.framework.ui.auto_page.base import AutoPageBase


class PeriodicAutoPage(AutoPageBase):
    """Auto-generated module page for periodic host.

    Periodic scheduling and log surfaces are provided by the host page,
    so this page only renders module settings and tips.
    """

    def _should_show_start_button(self) -> bool:
        return False

    def _should_show_log_panel(self) -> bool:
        return False

    def _should_show_actions(self) -> bool:
        return True

    def _tips_position(self) -> str:
        return "bottom"

    def _allow_half_layout(self) -> bool:
        return True

    def _non_ui_field_names(self) -> set[str]:
        return {"update_data", "task_name", "used_codes"}

    def __init__(self, parent=None, *, module_meta=None, host_context=None):
        super().__init__(parent, module_meta=module_meta, host_context=host_context)
        self.main_layout.setSpacing(0)
        self.settings_layout.setContentsMargins(0, 0, 0, 0)
