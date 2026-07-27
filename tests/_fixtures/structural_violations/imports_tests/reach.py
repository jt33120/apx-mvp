"""A runtime module reaching into the TEST TREE (FR-33/AD-16 violation). AST-scanned."""

from __future__ import annotations

from tests import conftest

handler = conftest  # keep the import 'used' so the fixture stays lint-clean
