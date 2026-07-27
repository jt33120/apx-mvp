"""A runtime module reading a fixture DIR by path literal (FR-33/AD-16 violation). AST-scanned."""

from __future__ import annotations

from pathlib import Path

SOURCE = Path("apx/core/_fixtures/demo")  # a runtime module must never read a fixture directory


def load() -> Path:
    return SOURCE
