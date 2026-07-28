"""Structural-violation fixture (Story 2.3, AD-28): a runtime-looking module that imports
extract_msg OUTSIDE the isolated worker. ``no_extract_msg_import_outside_worker`` must fire on it —
extract_msg (GPL-3.0) may be imported only in the out-of-process worker, so a single import
cannot contaminate the core. AST-scanned, never imported (extract_msg need not be installed)."""

from __future__ import annotations

import extract_msg


def parse(path: str) -> object:
    return extract_msg.openMsg(path)  # a product module importing the GPL parser — the leak
