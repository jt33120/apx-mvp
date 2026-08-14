"""The one door onto the durable store (Story 5.9, AD-35).

AD-35's invariant is *the head is recorded outside the restorable store on every append*. It was
true of the API and false of everything else: the import worker built ``SqlStore(...)`` with no
journal and wrote the bulk of the record — every ingest, every judgment — advancing the live head
with nothing recorded outside it; so did ``manage provision`` and ``manage create-user``. A
truncation back to the last head the *API* happened to record was therefore undetectable, and the
CLI restore — the one blessed operation that can hard-delete the record — opened the journal
``required=False`` and skipped the continuity check in silence when the variable was unset.

Every process that writes now builds the store here, and a structural check
(``the_store_has_one_door``) refuses a construction anywhere else in the runtime. One door is what
makes *every* append journalled a property rather than a habit.

``journal_required`` is True by default and False in exactly one place: the API, whose start-up
gate (``apx.api.startup``) already refuses to serve without the journal and produces a better
message than a store constructor can. Passing False anywhere the gate does not run would reopen the
hole this module closed.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import SqlStore
from apx.core.domain.head_journal import open_journal


def open_store(
    env: Mapping[str, str] | None = None, *, journal_required: bool = True
) -> SqlStore:
    """The store, wired to the head journal — the only construction the runtime performs."""
    source = dict(os.environ if env is None else env)
    return SqlStore(make_session_factory(), head_journal=open_journal(
        source, required=journal_required))
