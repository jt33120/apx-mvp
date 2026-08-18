"""What a *tenant* backup captures — derived from the mapped model, never listed by hand (AD-32).

The list this replaces was a hand-written tuple, and its history is the reason it is gone. Story 5.5
added ``audit_chain_head`` to it, Story 5.9 added ``journal_gap``, retro action B2 found
``register_override`` missing while fixing something else — and not one of those three asked whether
the list was *complete*. It was not: nine tenant-scoped tables and three child tables were
absent, so a restore returned a *matter* with no *ranking version*, no ranked order, no *sampling
run* and therefore no *confidence bound*, no *validation act* — while the *audit record* survived
intact and attested every one of them.

A list of what to back up cannot be reviewed. Reading it tells you what is in it and says nothing
about what is not, and the omission has no error message: the backup succeeds, the restore succeeds,
and the loss is discovered by the person who needed the document.

So the plan is **derived**, and it is **total or it is nothing**. Every table in
``Base.metadata`` is classified exactly once:

1. it carries a ``tenant`` column                      → ``WHERE tenant = :t``
2. it declares a foreign key to an already-captured table
                                                       → ``WHERE fk IN (SELECT pk FROM parent …)``
3. it is named in :data:`_WRITTEN` with a predicate    → that predicate, plus why it is by hand
4. it is named in :data:`_EXCLUDED` with a reason      → deliberately not in a backup

A table matching none of the four raises :class:`IncompleteBackupPlan`. That is the whole point: a
model nobody thought about stops the backup rather than being silently dropped from it, and the same
statement is made at build time by the ``backup-plan-is-total`` structural check (AD-33).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import MetaData, Table


class IncompleteBackupPlan(RuntimeError):
    """A mapped table the plan can neither capture nor name as excluded — fail closed (AD-32)."""


@dataclass(frozen=True)
class Capture:
    """One table and the predicate that selects a *tenant*'s rows of it."""

    table: str
    #: a SQL ``WHERE`` fragment binding exactly one parameter, ``:t`` (the tenant)
    predicate: str
    #: how the predicate was arrived at — read by the operator and by the check's message
    derivation: str


#: Tables whose *tenant* is reachable but **not** through a declared foreign key, each with the
#: predicate written out and the reason it had to be. Keep this list short: an entry here is a
#: place where the model does not say what it means, and the honest fix is usually the constraint.
_WRITTEN: dict[str, tuple[str, str]] = {
    "user_scope": (
        "user_id IN (SELECT id FROM user_account WHERE tenant = :t)",
        "keyed by a globally-unique user_id and declares no foreign key; tenant-bound through "
        "the user (the same reason apx.checks.tenant_isolation excludes it from OWNED_TABLES)",
    ),
}

#: Tables deliberately **outside** a tenant backup, each with the reason it is out. Empty today —
#: every mapped table is a tenant's. An entry here is a decision, and it is written down as one.
_EXCLUDED: dict[str, str] = {}


def _single_parent_link(table: Table, captured: set[str]) -> tuple[str, str, str] | None:
    """``(child_column, parent_table, parent_column)`` when ``table`` reaches exactly one captured
    parent through exactly one column pair — otherwise ``None``, so an ambiguous shape fails closed
    rather than being captured through a link somebody guessed at."""
    links: dict[str, set[tuple[str, str]]] = {}
    for fk in table.foreign_keys:
        parent = fk.column.table.name
        if parent == table.name or parent not in captured:
            continue
        links.setdefault(parent, set()).add((fk.parent.name, fk.column.name))
    if len(links) != 1:
        return None
    parent, pairs = next(iter(links.items()))
    if len(pairs) != 1:
        return None
    child_col, parent_col = next(iter(pairs))
    return child_col, parent, parent_col


def backup_plan(metadata: MetaData | None = None) -> tuple[Capture, ...]:
    """Every table this *tenant* backup captures, in an order safe to INSERT in.

    The order is the model's, not a typist's. Rules 1 and 2 run to a fixpoint over
    ``metadata.sorted_tables`` — topological over the declared foreign keys — so a parent is always
    captured before its children; the hand-written predicates of rule 3 are appended **after** that,
    because a link the model does not declare is a link ``sorted_tables`` cannot order, and rule 2
    then runs again for anything hanging off them. Reverse the result for deletes.

    Raises :class:`IncompleteBackupPlan` naming every unclassified table at once — an operator
    fixing this wants the whole list, not the first one.
    """
    if metadata is None:                       # the live model, imported lazily (no import cycle)
        from apx.adapters.store_postgres.models import Base

        metadata = Base.metadata
    captures: list[Capture] = []
    by_name: dict[str, Capture] = {}
    remaining = [t for t in metadata.sorted_tables if t.name not in _EXCLUDED]

    def _take(table: Table, capture: Capture) -> None:
        captures.append(capture)
        by_name[table.name] = capture
        remaining.remove(table)

    def _derive(table: Table) -> Capture | None:
        """Rule 1 then rule 2 — the two the model itself states."""
        if "tenant" in table.columns:
            return Capture(table.name, "tenant = :t", "carries a tenant column")
        link = _single_parent_link(table, set(by_name))
        if link is None:
            return None
        child_col, parent, parent_col = link
        return Capture(
            table.name,
            f"{child_col} IN (SELECT {parent_col} FROM {parent} "
            f"WHERE {by_name[parent].predicate})",
            f"child of {parent} through the declared foreign key {table.name}.{child_col}",
        )

    def _to_fixpoint() -> None:
        progress = True
        while progress:
            progress = False
            for table in list(remaining):
                capture = _derive(table)
                if capture is not None:
                    _take(table, capture)
                    progress = True

    _to_fixpoint()
    for table in list(remaining):                       # rule 3 — the written predicates
        if table.name in _WRITTEN:
            predicate, reason = _WRITTEN[table.name]
            _take(table, Capture(table.name, predicate, f"written by hand: {reason}"))
    _to_fixpoint()                                      # …and anything hanging off one

    if remaining:
        raise IncompleteBackupPlan(
            "no rule reaches these mapped table(s), so a backup would silently omit them: "
            f"{sorted(t.name for t in remaining)} — give each one a tenant column, a foreign key "
            "to a captured table, a written predicate in _WRITTEN, or a written reason in "
            "_EXCLUDED (AD-32)")
    return tuple(captures)


def excluded_tables() -> dict[str, str]:
    """The deliberate exclusions and their reasons — read by the structural check and by tests."""
    return dict(_EXCLUDED)
