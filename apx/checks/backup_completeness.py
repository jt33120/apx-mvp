"""A tenant backup's coverage is derived from the model, not maintained by hand (Story 7.2, AD-32).

The list this guards used to be a tuple in ``store.py``. It named 20 of the model's 35 tables, and
its history is the whole argument for a build-time check: Story 5.5 added ``audit_chain_head``,
Story 5.9 added ``journal_gap``, retro action B2 found ``register_override`` missing while fixing
something else — three separate stories each adding the one table they had in mind, and not one of
them asking whether the list was complete.

It cannot be reviewed by reading it. A list tells you what is in it and says nothing about what is
not, and the omission has no error message anywhere: the backup succeeds, the restore succeeds, and
the loss is found by the person who needed the *pièce*. So the property is stated the other way
round — every mapped table is accounted for, by a rule or by a written reason — and it is asserted
against the live metadata at build time, where an unclassified table is a red build rather than a
quiet subset.
"""

from __future__ import annotations

from sqlalchemy import MetaData

from apx.adapters.store_postgres.backup_plan import (
    IncompleteBackupPlan,
    backup_plan,
    excluded_tables,
)
from apx.checks.import_contracts import CheckResult


def _base_metadata() -> MetaData:
    from apx.adapters.store_postgres.models import Base

    return Base.metadata


def the_backup_plan_is_total(metadata: MetaData | None = None) -> CheckResult:
    """Every mapped table is captured by the plan or excluded by name with a written reason.

    Three legs, and the second and third exist because a written exclusion is the escape hatch:
    left unguarded it is how a table leaves a backup quietly, one blank string at a time.

    1. the plan builds — no table falls through all four rules (it raises rather than returning a
       subset, so this leg is the totality statement and not a count comparison, which would have
       been vacuous next to a function that fails closed);
    2. every exclusion carries a reason — an exclusion whose reason is empty is not an exclusion,
       it is an omission with a comment;
    3. no exclusion names a table the model no longer has — a stale entry is a decision about
       something that is not there, and it hides the day a table returns under that name.
    """
    name, ad = "a tenant backup's coverage is total over the model", "AD-32"
    tables = (metadata if metadata is not None else _base_metadata())
    excluded = excluded_tables()
    try:
        plan = backup_plan(tables)
    except IncompleteBackupPlan as exc:
        return CheckResult(name, ad, False, str(exc))

    mapped = set(tables.tables)
    captured = {cap.table for cap in plan}
    unreasoned = sorted(t for t, why in excluded.items() if not (why or "").strip())
    if unreasoned:
        return CheckResult(name, ad, False,
                           f"table(s) excluded from every backup with no reason given: "
                           f"{unreasoned} — an exclusion is a decision and is written as one")
    phantom = sorted(set(excluded) - mapped)
    if phantom:
        return CheckResult(name, ad, False,
                           f"exclusion(s) naming a table this model does not have: {phantom} — "
                           "a stale exclusion hides the day the name comes back")
    return CheckResult(
        name, ad, True,
        f"{len(captured)} of {len(mapped)} mapped tables captured, "
        f"{len(excluded)} excluded with a written reason")
