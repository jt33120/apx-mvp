"""A natural-language string used as a translation key (FR-34 violation). AST-scanned."""

from __future__ import annotations

from i18n import t


def greeting() -> str:
    return t("Please try again later")  # a sentence as a key — keys are namespaced tokens
