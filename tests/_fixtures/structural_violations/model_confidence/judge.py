"""A model-reported confidence field consumed (FR-42/AD-19 violation). AST-scanned."""

from __future__ import annotations


def score(response: dict) -> float:
    return response["confidence"]  # a number the model made up about itself — confidence is derived
