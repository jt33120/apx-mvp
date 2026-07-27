"""Structural-violation fixture (Story 2.2, AD-17): a runtime module OUTSIDE the queue submodule
that imports Procrastinate. ``no_queue_import_outside_submodule`` must fire on it — the queue is
sealed inside ``apx/adapters/store_postgres/queue`` so no read/progress path can consult the job
table and disagree with the application-owned ledger. AST-scanned, never imported."""

from __future__ import annotations

import procrastinate


def peek_at_the_queue() -> object:
    # A read path consulting the queue directly instead of the ledger — the leak the check catches.
    return procrastinate.App
