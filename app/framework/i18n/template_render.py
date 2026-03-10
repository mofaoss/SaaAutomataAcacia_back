from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TemplateFieldMismatch(Exception):
    expected_fields: list[str]
    actual_fields: list[str]

    def __str__(self) -> str:
        return (
            "Template fields mismatch: "
            f"expected={self.expected_fields}, actual={self.actual_fields}"
        )


@dataclass(slots=True)
class TemplateFieldSpecMismatch(Exception):
    expected_field_details: dict[str, dict[str, str]]
    actual_field_details: dict[str, dict[str, str]]

    def __str__(self) -> str:
        return (
            "Template field format mismatch: "
            f"expected={self.expected_field_details}, actual={self.actual_field_details}"
        )


class _SafeFormatProxy:
    def __init__(self, value: Any):
        self._value = value

    def _to_string(self) -> str:
        if isinstance(self._value, str):
            return self._value
        try:
            return str(self._value)
        except Exception:
            try:
                return repr(self._value)
            except Exception:
                return "<unprintable>"

    def __str__(self) -> str:
        return self._to_string()

    def __repr__(self) -> str:
        try:
            return repr(self._value)
        except Exception:
            return self._to_string()

    def __format__(self, spec: str) -> str:
        try:
            return format(self._value, spec)
        except Exception:
            text_value = self._to_string()
            try:
                return format(text_value, spec)
            except Exception:
                return text_value


def extract_template_fields(template: str) -> list[str]:
    formatter = string.Formatter()
    names: list[str] = []
    seen: set[str] = set()
    for _, field_name, _, _ in formatter.parse(template):
        if not field_name:
            continue
        base = field_name.split("[", 1)[0].split(".", 1)[0]
        if base and base not in seen:
            seen.add(base)
            names.append(base)
    return names


def extract_template_field_details(template: str) -> dict[str, dict[str, str]]:
    formatter = string.Formatter()
    details: dict[str, dict[str, str]] = {}
    for _, field_name, format_spec, conversion in formatter.parse(template):
        if not field_name:
            continue
        base = field_name.split("[", 1)[0].split(".", 1)[0]
        if not base or base in details:
            continue
        details[base] = {
            "format_spec": str(format_spec or ""),
            "conversion": str(conversion or ""),
        }
    return details


def render_localized_template(
    template: str,
    payload: dict[str, Any],
    *,
    expected_fields: list[str] | None = None,
    expected_field_details: dict[str, dict[str, str]] | None = None,
    strict_fields: bool = True,
) -> str:
    payload = payload or {}
    actual_fields = extract_template_fields(template)
    actual_field_details = extract_template_field_details(template)
    if expected_fields is not None and strict_fields:
        if sorted(expected_fields) != sorted(actual_fields):
            raise TemplateFieldMismatch(
                expected_fields=list(expected_fields),
                actual_fields=list(actual_fields),
            )
    if expected_field_details is not None and strict_fields:
        if expected_field_details != actual_field_details:
            raise TemplateFieldSpecMismatch(
                expected_field_details=dict(expected_field_details),
                actual_field_details=dict(actual_field_details),
            )
    safe_payload = {k: _SafeFormatProxy(v) for k, v in payload.items()}
    return template.format(**safe_payload)
