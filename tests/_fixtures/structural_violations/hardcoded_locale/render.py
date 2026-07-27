"""A hard-coded locale in a format context (FR-35/AD-24 violation). AST-scanned."""

from __future__ import annotations

from babel.dates import format_date


def render(when: object) -> str:
    return format_date(when, locale="fr_FR")  # a fixed locale — dates render in the user's locale
