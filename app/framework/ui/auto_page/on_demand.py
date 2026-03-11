from __future__ import annotations

from app.framework.i18n import tr
from app.framework.ui.auto_page.base import AutoPageBase


class OnDemandAutoPage(AutoPageBase):
    """Auto-generated module page for on-demand host.

    Owns local run button + local log panel because on-demand tasks are
    independently started/stopped from this page.
    """

    def _should_show_start_button(self) -> bool:
        return True

    def _should_show_log_panel(self) -> bool:
        return True

    def _update_button_state(self, is_running: bool):
        button = getattr(self, "PushButton_start", None)
        if button is None:
            return

        stop_candidates: list[str] = []
        start_candidates: list[str] = []
        for module_id in self._module_i18n_ids():
            stop_candidates.extend([
                f"module.{module_id}.ui.stop_{module_id}",
                f"module.{module_id}.ui.stop",
            ])
            start_candidates.extend([
                f"module.{module_id}.ui.start_{module_id}",
                f"module.{module_id}.ui.start",
            ])

        if is_running:
            translated = self._first_translated(stop_candidates)
            button.setText(translated or tr("framework.ui.stop", fallback="Stop"))
            return

        translated = self._first_translated(start_candidates)
        button.setText(translated or tr("framework.ui.run", fallback="Run"))
