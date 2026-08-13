"""The *audit record*'s structural properties (Story 5.5, FR-24 / FR-53 / AD-43 / AD-22).

Three checks over the record the whole trust architecture rests on:

- **audit-catalogue-complete (FR-24):** every verb the runtime writes is catalogued, no verb is
  ever a hand-written string at a call site, and every FR-24 act class either has a real writer or
  is declared pending with the story that owns it. FR-24's enumeration stops being a list somebody
  read and starts being a list the build checks.
- **audit-sequence-not-generated (AD-43):** the sequence number is allocated from a locked head
  row inside the acting transaction. ``nextval``, ``Sequence`` and autoincrement on an evidential
  table fail the build — a burned number after an ordinary worker crash is a permanent gap that
  reports as tampering forever and that AD-22 forbids anyone to repair.
- **audit-record-append-only (FR-24/FR-21):** no runtime path updates or deletes an audit entry. A
  correction is a new entry.

Build-time tooling, so this module is outside the scanned runtime (``_RUNTIME_EXCLUDE``) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.forward_looking import _docstrings
from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _fail_closed
from apx.core.domain import audit

#: The tables whose rows are evidence: the record itself, and the append-only ledgers that carry
#: legal weight. Their identities are deterministic or application-computed; these checks make that
#: irreversible. ``audit_chain_head`` is deliberately NOT here — it is the allocator, not the
#: record, and it is the one row that must be updated in place.
EVIDENTIAL_TABLES: tuple[str, ...] = (
    "audit_record",
    "case_theory_version",
    "line_placement",
    "pin_entry",
    "taxonomy_label_entry",
    "sampling_run",
    "sampling_verdict",
)

#: The model classes those tables map to (checked by ORM class name, since a delete()/update() is
#: written against the class rather than the table name). NONE of them may be removed or bulk-
#: updated by a statement.
EVIDENTIAL_MODELS: tuple[str, ...] = (
    "AuditRecord",
    "CaseTheoryVersion",
    "LinePlacement",
    "PinEntry",
    "TaxonomyLabelEntry",
    "SamplingRun",
    "SamplingVerdict",
)

#: The subset that is APPEND-ONLY row by row: a loaded instance is never edited in place either.
#:
#: ``SamplingRun`` is deliberately absent, and the distinction is the point. A run is an entity
#: with a lifecycle — open, then completed or abandoned (Stories 5.1/5.2) — so ``status``,
#: ``closed_by`` and ``completed_at`` are transitions, not rewrites, and each transition writes its
#: own audit entry (``sampling-run-start`` / ``-complete`` / ``-abandon``). Forbidding those
#: assignments would forbid closing a run at all. What the record must never permit is editing what
#: an entry SAID; the run's history lives on the chain, which is append-only in the strict sense.
APPEND_ONLY_MODELS: tuple[str, ...] = (
    "AuditRecord",
    "CaseTheoryVersion",
    "LinePlacement",
    "PinEntry",
    "TaxonomyLabelEntry",
    "SamplingVerdict",
)

_APPEND_AUDIT = "_append_audit"
#: The position of the ``action`` argument in ``_append_audit(session, tenant, matter, actor,
#: action, detail, ts)``.
_ACTION_ARG = 4

#: The function that allocates a sequence number. Named here so the check follows it across a
#: rename of the module it lives in.
_ALLOCATOR = "_lock_chain_head"


def _catalogue_constants() -> frozenset[str]:
    """Every ``ACT_*`` name the catalogue module exports."""
    return frozenset(n for n in dir(audit) if n.startswith("ACT_"))


def _docstring_text(tree: ast.Module) -> list[str]:
    """The text of every docstring in the tree — prose, which allocates nothing."""
    ids = _docstrings(tree)
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) in ids
    ]


def _verb_of(node: ast.expr) -> str | None:
    """The catalogue constant a call site names for its verb, or None when it is not one."""
    if isinstance(node, ast.Attribute) and node.attr.startswith("ACT_"):
        return node.attr
    if isinstance(node, ast.Name) and node.id.startswith("ACT_"):
        return node.id
    return None


def audit_catalogue_is_complete(root: Path | None = None) -> CheckResult:
    """FR-24. Three legs, and each closes a different way of ending up with an act class nobody
    can count.

    **Leg 1 — no hand-written verb.** A string literal in the ``action`` position fails. A typo
    (``piece_labeled``) would otherwise mint an act class that no filter, count or export ever
    surfaces, and that nothing distinguishes from an act that never happened.

    **Leg 2 — every named verb exists.** A call site naming ``ACT_SOMETHING`` that the catalogue
    does not define fails at build rather than at the first act of a working day.

    **Leg 3 — every FR-24 class is covered or owned.** A class with no writer must be declared
    PENDING with the story that owns it, and a class with a writer must not be declared pending.
    The fitness driver's rule, applied to the record: asserted with something behind it, or
    pending with a name on it, and never faked in between.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("every recorded act is a catalogued act", "FR-24/AD-43", unparseable)
    violations: list[str] = []
    constants = _catalogue_constants()

    for path, tree in trees:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == _APPEND_AUDIT):
                continue
            arg = node.args[_ACTION_ARG] if len(node.args) > _ACTION_ARG else None
            for kw in node.keywords:
                if kw.arg == "action":
                    arg = kw.value
            if arg is None:
                violations.append(f"{_where(path)}:{node.lineno} names no act at all")
                continue
            if isinstance(arg, ast.Constant):
                violations.append(
                    f"{_where(path)}:{node.lineno} writes the literal {arg.value!r} — an audit "
                    "verb is catalogue data, never a string at the call site")
                continue
            named = _verb_of(arg)
            if named is None:
                # A variable carrying a catalogued constant is fine as long as every value it can
                # hold is one; the store's runtime guard refuses anything else at the write.
                continue
            if named not in constants:
                violations.append(
                    f"{_where(path)}:{node.lineno} names {named}, which the catalogue does not "
                    "define")

    covered = audit.covered_classes()
    for act_class in audit.FR24_CLASSES:
        if act_class in covered and act_class in audit.PENDING_CLASSES:
            violations.append(
                f"FR-24 class {act_class!r} is written by {audit.verbs_for(act_class)} and cannot "
                "also be declared pending")
        if act_class not in covered:
            owner = audit.PENDING_CLASSES.get(act_class)
            if not owner:
                violations.append(
                    f"FR-24 class {act_class!r} has no writer and no story that owns it — a hole "
                    "in the record that nothing names")

    for verb, entry in audit.ACTS.items():
        if entry.act_class in audit.PENDING_CLASSES:
            violations.append(
                f"{verb!r} writes {entry.act_class!r}, which is declared pending")

    if violations:
        return CheckResult(
            "every recorded act is a catalogued act", "FR-24/AD-43", False,
            "the record's act catalogue is not the record's acts:\n  - "
            + "\n  - ".join(sorted(violations)))
    return CheckResult(
        "every recorded act is a catalogued act", "FR-24/AD-43", True,
        f"{len(audit.ACTS)} catalogued acts, every FR-24 class covered or owned, no literal verbs")


def audit_sequence_is_not_generated(root: Path | None = None) -> CheckResult:
    """AD-43, in as many words: *"``nextval`` and any ``Sequence``-backed column on an evidential
    table fail the build (structural property)."*

    The reason is not tidiness. ``nextval`` is non-transactional: a worker that takes number 41 209
    and then crashes burns it forever, the chain carries a permanent gap, the continuity check
    reports it on every future export, and AD-22 forbids repair. An ordinary worker crash would
    manufacture an unrepairable tamper alarm on a record of asserted legal weight, on a machine APX
    reaches only by telephone.

    Two legs: no sequence generator anywhere near the evidential tables, and the allocation is in
    fact taken under a row lock (``with_for_update``) — a check that only banned the generator
    would pass happily on the unlocked read-modify-write that preceded this story.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("the audit sequence is never generated", "FR-53/AD-43", unparseable)
    violations: list[str] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            # `Sequence(...)` / `sa.Sequence(...)` / `func.nextval(...)` / `autoincrement=True`
            if isinstance(node, ast.Call):
                name = (node.func.attr if isinstance(node.func, ast.Attribute)
                        else node.func.id if isinstance(node.func, ast.Name) else "")
                if name in ("Sequence", "nextval"):
                    violations.append(
                        f"{_where(path)}:{node.lineno} builds a {name}() — the audit sequence is "
                        "allocated from a locked head row inside the entry's transaction (AD-43)")
            if isinstance(node, ast.keyword) and node.arg == "autoincrement":
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    violations.append(
                        f"{_where(path)}:{node.lineno} sets autoincrement=True")
        # A generator can also arrive as raw SQL, where no Call node names it. Docstrings are
        # exempt — AD-43's own rule has to be quotable by the module that obeys it, and a docstring
        # allocates nothing. The exemption is subtractive, so a `text("… nextval('x') …")` beside a
        # docstring that explains why nextval is banned still fails.
        text = path.read_text(encoding="utf-8")
        in_prose = sum(d.count("nextval") for d in _docstring_text(tree))
        if text.count("nextval") > in_prose:
            violations.append(
                f"{_where(path)} names nextval in executable text — a sequence generator is not "
                "the audit sequence's authority (AD-43)")

    # The allocator, wherever it lives: found by NAME, not by file, so moving it between modules
    # never quietly turns this leg off.
    allocators = [
        (path, node) for path, tree in trees for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == _ALLOCATOR
    ]
    for path, node in allocators:
        if not any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                   and c.func.attr == "with_for_update" for c in ast.walk(node)):
            violations.append(
                f"{_where(path)}:{node.lineno} allocates without a row lock: with no SELECT … FOR "
                "UPDATE two concurrent acts compute the same number and the loser is refused "
                "(AD-43/AD-22)")
    if not allocators and root is None:
        violations.append(
            f"no {_ALLOCATOR}() in the runtime — nothing allocates the audit sequence")

    if violations:
        return CheckResult(
            "the audit sequence is never generated", "FR-53/AD-43", False,
            "\n  - ".join(violations))
    return CheckResult(
        "the audit sequence is never generated", "FR-53/AD-43", True,
        "no sequence generator; the number comes from a head row locked in the acting transaction")


def _loaded_evidential_names(fn: ast.FunctionDef) -> set[str]:
    """Local names in ``fn`` bound to a LOADED append-only row — an assignment whose right side
    READS one of those models. A direct construction (``AuditRecord(...)``) builds a NEW row, which
    is an append, and is deliberately excluded."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        rhs = node.value
        if isinstance(rhs, ast.Call):
            called = (rhs.func.id if isinstance(rhs.func, ast.Name)
                      else rhs.func.attr if isinstance(rhs.func, ast.Attribute) else "")
            if called in APPEND_ONLY_MODELS:
                continue  # a construction is an append
        if any(isinstance(n, ast.Name) and n.id in APPEND_ONLY_MODELS for n in ast.walk(rhs)):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _in_place_edits(path: Path, fn: ast.FunctionDef) -> list[str]:
    """``row.<col> = …`` or ``session.delete(row)`` where ``row`` is a loaded evidential row — the
    in-store way to edit or remove the record without ever building a statement.

    This leg exists because the docstring above promised it and the first implementation did not
    deliver it: the check said *"no attribute of a loaded evidential row is assigned to"* while
    inspecting only ``delete()``/``update()`` builders. Five sibling checks
    (``line_placement_ownership``, ``pin_ledger_ownership``, ``taxonomy_label_ownership``,
    ``case_theory_ownership``, ``artefact_stamp_ownership``) already implement exactly this, so the
    idiom was known to be decidable; the record's own check was the one without it."""
    loaded = _loaded_evidential_names(fn)
    if not loaded:
        return []
    out: list[str] = []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "delete" and len(node.args) == 1
                and isinstance(node.args[0], ast.Name) and node.args[0].id in loaded):
            out.append(
                f"{_where(path)}:{node.lineno} removes a loaded evidential row in {fn.name}() — "
                "a correction is a new row (FR-24)")
        if isinstance(node, ast.Assign | ast.AugAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) \
                        and t.value.id in loaded:
                    out.append(
                        f"{_where(path)}:{node.lineno} assigns {t.value.id}.{t.attr} on a loaded "
                        f"evidential row in {fn.name}() — the record is append-only (FR-24)")
    return out


def audit_record_is_append_only(root: Path | None = None) -> CheckResult:
    """FR-24: *"No user-facing action edits or removes an entry; a correction is a new entry."*

    The record is the one place where a tidy-up is indistinguishable from a cover-up, so the
    prohibition is structural rather than a convention: no ``delete()`` or ``update()`` statement
    is built against an evidential model, **and no attribute of a loaded evidential row is assigned
    to, and no loaded evidential row is passed to ``session.delete``**. The head row is exempt and
    named as such — it is the allocator, not the record.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed(
            "an evidential row is never edited or removed", "FR-24/AD-22", unparseable)
    violations: list[str] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fname = (node.func.attr if isinstance(node.func, ast.Attribute)
                         else node.func.id if isinstance(node.func, ast.Name) else "")
                if fname in ("delete", "update") and node.args:
                    target = node.args[0]
                    named = (target.id if isinstance(target, ast.Name)
                             else target.attr if isinstance(target, ast.Attribute) else "")
                    if named in EVIDENTIAL_MODELS:
                        violations.append(
                            f"{_where(path)}:{node.lineno} builds {fname}({named}) — an evidential "
                            "row is never edited or removed; a correction is a new row")
            if isinstance(node, ast.FunctionDef):
                violations.extend(_in_place_edits(path, node))
    if violations:
        return CheckResult(
            "an evidential row is never edited or removed", "FR-24/AD-22", False,
            "\n  - ".join(sorted(violations)))
    return CheckResult(
        "an evidential row is never edited or removed", "FR-24/AD-22", True,
        f"no statement removes or bulk-updates any of the {len(EVIDENTIAL_MODELS)} evidential "
        f"models, and no loaded row of the {len(APPEND_ONLY_MODELS)} append-only ones is edited "
        "in place")
