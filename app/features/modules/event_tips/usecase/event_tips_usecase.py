from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt
from qfluentwidgets import BodyLabel, InfoBar, InfoBarPosition, ProgressBar

from app.features.utils.network import calculate_time_difference, get_date_from_api
from app.framework.i18n import _, qt, tr
from app.framework.i18n import runtime as i18n_runtime

_REMAINING_DAYS_RE = re.compile(r"^\s*(\d+)\s*(?:d\(s\)|d|day|days|ds)\s*left\s*$", re.IGNORECASE)
_REMAINING_DAYS_TEXT_RE = re.compile(r"^\s*remaining\s*(\d+)\s*(?:d\(s\)|d|day|days|ds)\s*$", re.IGNORECASE)
_REMAINING_HOURS_RE = re.compile(r"^\s*(\d+)\s*(?:h|hour|hours)\s*left\s*$", re.IGNORECASE)
_REMAINING_MINUTES_RE = re.compile(r"^\s*(\d+)\s*(?:m|min|minute|minutes)\s*left\s*$", re.IGNORECASE)
_STARTS_IN_DAYS_RE = re.compile(r"^\s*in\s+(\d+)\s*(?:d\(s\)|d|day|days)\s*$", re.IGNORECASE)

I18N_EVENT_STATUS_FINISHED = "module.event_tips.ui.event_status_finished"
I18N_EVENT_STATUS_REMAINING_DAYS = "module.event_tips.ui.event_status_remaining_days"
I18N_EVENT_STATUS_REMAINING_HOURS = "module.event_tips.ui.event_status_remaining_hours"
I18N_EVENT_STATUS_REMAINING_MINUTES = "module.event_tips.ui.event_status_remaining_minutes"
I18N_EVENT_STATUS_STARTS_IN_DAYS = "module.event_tips.ui.event_status_starts_in_days"
I18N_EVENT_STATUS_DISPLAY_WITH_TITLE = "module.event_tips.ui.event_status_display_with_title"


@dataclass(slots=True)
class EventStatus:
    kind: Literal["remaining_days", "remaining_hours", "remaining_minutes", "finished", "unknown", "starts_in_days"]
    value: int | None = None
    raw_text: str = ""


def parse_external_status_text(text: str) -> EventStatus:
    raw = "" if text is None else str(text).strip()
    i18n_runtime.report_i18n_event("event_status_raw", raw)
    i18n_runtime.report_i18n_event("event_status_parse_started", raw)
    if not raw:
        i18n_runtime.report_i18n_event("event_status_unparsed", raw)
        return EventStatus(kind="unknown", raw_text=raw)

    lowered = raw.lower()
    if lowered in {"finished", "done", "ended"}:
        status = EventStatus(kind="finished", raw_text=raw)
        i18n_runtime.report_i18n_event("event_status_parsed", str(status))
        return status

    day_match = _REMAINING_DAYS_RE.match(raw) or _REMAINING_DAYS_TEXT_RE.match(raw)
    if day_match:
        status = EventStatus(kind="remaining_days", value=int(day_match.group(1)), raw_text=raw)
        i18n_runtime.report_i18n_event("event_status_parsed", str(status))
        return status

    hours_match = _REMAINING_HOURS_RE.match(raw)
    if hours_match:
        status = EventStatus(kind="remaining_hours", value=int(hours_match.group(1)), raw_text=raw)
        i18n_runtime.report_i18n_event("event_status_parsed", str(status))
        return status

    minutes_match = _REMAINING_MINUTES_RE.match(raw)
    if minutes_match:
        status = EventStatus(kind="remaining_minutes", value=int(minutes_match.group(1)), raw_text=raw)
        i18n_runtime.report_i18n_event("event_status_parsed", str(status))
        return status

    starts_in_match = _STARTS_IN_DAYS_RE.match(raw)
    if starts_in_match:
        status = EventStatus(kind="starts_in_days", value=int(starts_in_match.group(1)), raw_text=raw)
        i18n_runtime.report_i18n_event("event_status_parsed", str(status))
        return status

    i18n_runtime.report_i18n_event("event_status_unparsed", raw)
    return EventStatus(kind="unknown", raw_text=raw)


def format_localized_status(status: EventStatus) -> str:
    kind = status.kind
    value = int(status.value or 0)

    if kind == "finished":
        localized = tr(I18N_EVENT_STATUS_FINISHED, fallback="Finished")
    elif kind == "remaining_days":
        localized = tr(I18N_EVENT_STATUS_REMAINING_DAYS, fallback="{days} days remaining", days=value)
    elif kind == "remaining_hours":
        localized = tr(I18N_EVENT_STATUS_REMAINING_HOURS, fallback="{hours} hours remaining", hours=value)
    elif kind == "remaining_minutes":
        localized = tr(I18N_EVENT_STATUS_REMAINING_MINUTES, fallback="{minutes} minutes remaining", minutes=value)
    elif kind == "starts_in_days":
        localized = tr(I18N_EVENT_STATUS_STARTS_IN_DAYS, fallback="Starts in {days} days", days=value)
    else:
        localized = status.raw_text

    i18n_runtime.report_i18n_event("event_status_localized", f"{status.kind}:{localized}")
    return localized


def compose_event_status_display(title: str, localized_status: str) -> str:
    display = tr(
        I18N_EVENT_STATUS_DISPLAY_WITH_TITLE,
        fallback="{title}: {status}",
        title=title,
        status=localized_status,
    )
    if display:
        i18n_runtime.report_i18n_event("event_status_composed", display)
        return display
    fallback = f"{title}：{localized_status}"
    i18n_runtime.report_i18n_event("event_status_composed", fallback)
    return fallback


def format_event_status_display(title: str, raw_status: str) -> str:
    status = parse_external_status_text(raw_status)
    if status.kind == "unknown":
        i18n_runtime.report_i18n_event("external_status_unparsed", raw_status)
        i18n_runtime.report_i18n_event("external_string_bypassed_i18n_static_enforcement", raw_status)
        return f"{title}：{status.raw_text}"

    localized_status = format_localized_status(status)
    i18n_runtime.report_i18n_event("external_status_parsed_localized", raw_status)
    return compose_event_status_display(title, localized_status)


class EventTipsUseCase:
    """Event tips business logic extracted from periodic host."""

    def __init__(self, settings_usecase):
        self.settings_usecase = settings_usecase

    def _load_tip_payload(self, logger, host, url=None):
        if url:
            tips_dic = get_date_from_api(url)
            if "error" in tips_dic.keys():
                logger.error(tips_dic["error"])
                return None
            self.settings_usecase.save_date_tip(tips_dic)
            return tips_dic

        tips_dic = self.settings_usecase.load_date_tip()
        if tips_dic:
            return tips_dic

        InfoBar.error(
            title=_("Failed to update event schedule", msgid="failed_to_update_event_schedule"),
            content=_("No local information stored and no URL fetched", msgid="no_local_information_stored_and_no_url_fetched"),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=host,
        )
        return None

    def refresh_tips_panel(self, ui, logger, host, url=None):
        tips_dic = self._load_tip_payload(logger, host, url=url)
        if not tips_dic:
            return

        if self.settings_usecase.is_log_enabled():
            logger.info(_("Successfully fetched event schedule", msgid="successfully_fetched_event_schedule"))
        normalized = {key: calculate_time_difference(value) for key, value in tips_dic.items()}
        max_total_days = max(
            (
                total_day
                for _event_key, (days, total_day, status) in normalized.items()
                if status == 0
            ),
            default=1,
        )

        items_list = []
        index = 0
        for key, value in normalized.items():
            body_label = ui.scrollAreaWidgetContents_tips.findChild(BodyLabel, name=f"BodyLabel_tip_{index + 1}")
            if body_label is None:
                body_label = BodyLabel(ui.scrollAreaWidgetContents_tips)
                body_label.setObjectName(f"BodyLabel_tip_{index + 1}")

            progress_bar = ui.scrollAreaWidgetContents_tips.findChild(ProgressBar, name=f"ProgressBar_tip{index + 1}")
            if progress_bar is None:
                progress_bar = ProgressBar(ui.scrollAreaWidgetContents_tips)
                progress_bar.setObjectName(f"ProgressBar_tip{index + 1}")

            days, total_day, status = value
            if status == -1:
                raw_status = "finished"
                body_label.setText(format_event_status_display(key, raw_status))
                sort_weight = 99999
                progress_bar.setValue(0)
            elif status == 1:
                raw_status = f"in {days}d(s)"
                body_label.setText(format_event_status_display(key, raw_status))
                sort_weight = 10000 + days
                progress_bar.setValue(0)
            else:
                raw_status = f"{days}d(s) left"
                body_label.setText(format_event_status_display(key, raw_status))
                sort_weight = days
                normalized_percent = int((days / max_total_days) * 100)
                progress_bar.setValue(normalized_percent)

            if self.settings_usecase.is_log_enabled():
                parsed_status = parse_external_status_text(raw_status)
                logger.debug(
                    f"event_status_trace raw_title={key} raw_status_text={raw_status} "
                    f"parsed={parsed_status} locale_used={i18n_runtime._resolve_lang()} final_display={body_label.text()}"
                )

            items_list.append([body_label, progress_bar, sort_weight])
            index += 1

        items_list.sort(key=lambda item: item[2])
        for row, (body_label, progress_bar, _sort_weight) in enumerate(items_list, start=1):
            ui.gridLayout_tips.addWidget(body_label, row, 0, 1, 1)
            ui.gridLayout_tips.addWidget(progress_bar, row, 1, 1, 1)


class EventTipsActions:
    """Host-facing adapter for tips refresh. Keeps host page free of business method bodies."""

    def __init__(self, usecase: EventTipsUseCase):
        self._usecase = usecase
        self._ui = None
        self._logger = None
        self._host = None

    def bind(self, *, ui, logger, host):
        self._ui = ui
        self._logger = logger
        self._host = host

    def refresh_tips(self, url=None):
        if self._ui is None or self._logger is None or self._host is None:
            return
        try:
            self._usecase.refresh_tips_panel(
                ui=self._ui,
                logger=self._logger,
                host=self._host,
                url=url,
            )
        except Exception as e:
            self._logger.error(_(f"Error occurred while updating controls: {e}", msgid="error_occurred_while_updating_controls_e"))
