from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser


def insert_startup_logo(text_browser: QTextBrowser | None) -> None:
    """Insert startup logo once per QTextBrowser instance."""
    if text_browser is None:
        return
    if bool(text_browser.property("startupLogoInserted")):
        return

    project_root = Path(__file__).resolve().parents[4]
    logo_path = project_root / "resources" / "logo" / "Aca.png"
    if not logo_path.exists():
        return

    try:
        logo_url = QUrl.fromLocalFile(str(logo_path)).toString()
        text_browser.insertHtml(
            f'<div style="margin: 6px 0 8px 0; text-align: center;"><img src="{logo_url}" style="max-width: 180px; height: auto; display: inline-block;" /></div><br/>'
        )
        text_browser.setProperty("startupLogoInserted", True)
        text_browser.ensureCursorVisible()
    except Exception:
        pass
