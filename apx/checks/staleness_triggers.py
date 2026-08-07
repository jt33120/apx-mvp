"""FR-58 / AD-23 — every enumerated staleness trigger has an observable, both ways (Story 4.13).

AD-23 states the trigger list as a **complete enumeration**: a new *ranking version*; a move of
**the line**; a *pin* added or removed; a *case theory* revision; a configuration change affecting
retrieval, ranking or the estimator; an *RBAC scope* change affecting the population; any ingestion
into the *matter*; and a re-extraction of any *pièce* (AD-40). FR-23 adds a ninth for the
*confidence bound* specifically: *"the population it was drawn from"*.

``_REQUIRED`` below holds AD-23's eight as the FLOOR — the list may grow when a requirement names a
further input, but none of the eight may leave.

An enumeration is only worth writing down if something checks it. This check reads the source of
:mod:`apx.core.domain.freshness` and asserts, **both ways**:

- every entry in ``TRIGGERS`` names a field that exists on ``FreshnessStamp`` — a trigger with no
  observable is a staleness nothing can detect, and the artefact would read **fresh** while its
  input had moved, which is exactly the failure AD-23 names;
- every field of ``FreshnessStamp`` is named by a trigger — an observable belonging to no trigger
  would be compared but never explainable, so the surface would say *"stale"* without being able to
  say *why*, which FR-58 forbids ("names which input changed");
- every trigger carries a non-blank French phrase and a non-blank source (the FR/AD it comes from),
  so the list stays auditable against the spine and the banner always has something to say;
- **no observable is a timestamp**. A clock as an input is how staleness would resolve itself by
  the passage of time. (:mod:`apx.checks.freshness_never_time_based` asserts the same property from
  the other direction, over the modules that compute the verdict.)

It then checks the per-kind narrowing (``INPUTS_BY_KIND``). Each artefact depends on a SUBSET of
the eight — a line move does not change the ranked order, and a banner claiming it does would be
false, which is its own way of destroying the signal. Narrowing is therefore allowed, but bounded:
no kind may name an input that is not a trigger; the union over all kinds must be the whole
enumeration (a trigger every kind excluded is a staleness deleted rather than argued); and the
*confidence bound* must depend on all eight, because FR-58 is written about the bound and fixes its
list literally.

Deliberately **not** written over the artefact-kind list as a coverage requirement. AD-23 also binds
the review-effort estimate and the exhaustive result set, neither of which exists as a stamped
artefact here (the first has no story; the second is computed at read time and never persisted). A
coverage check over kinds would have to exempt them, and an exemption is how a real gap gets a
permanent excuse. Over triggers there is nothing to exempt: the eight are all reachable today.

The check reads the module's SOURCE, not the imported objects, so a runtime monkey-patch cannot
make it pass. Fails closed: a missing module, a parse error, or a ``TRIGGERS``/``FreshnessStamp``
it cannot read statically all fail the build.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_FRESHNESS = _APX_ROOT / "core" / "domain" / "freshness.py"
_STAMP = "FreshnessStamp"
_TRIGGERS = "TRIGGERS"
_BY_KIND = "INPUTS_BY_KIND"
# The eight, verbatim from AD-23. Kept HERE as well as in the domain so the check is an independent
# statement of the requirement rather than a mirror of the code it checks: dropping a trigger from
# the domain fails against this list, not against itself.
_REQUIRED: frozenset[str] = frozenset({
    "ranking_version_no", "line_seq", "pin_ledger_seq", "case_theory_version_no",
    "config_digest", "scope_identity", "corpus_count", "extraction_digest",
})
# Annotations that would make an observable a clock.
_TIME_ANNOTATIONS = frozenset({"datetime", "date", "time", "timedelta", "float | None"})


def _stamp_fields(tree: ast.Module) -> dict[str, str] | None:
    """The ``FreshnessStamp`` dataclass fields as ``{name: annotation source}``, or None when the
    class is not statically readable."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == _STAMP:
            fields: dict[str, str] = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields[stmt.target.id] = ast.unparse(stmt.annotation)
            return fields or None
    return None


def _trigger_entries(tree: ast.Module) -> list[tuple[str, str, str]] | None:
    """The ``TRIGGERS`` tuple as ``(key, fr, source)`` triples, or None when it is not a literal
    tuple of ``Trigger(...)`` calls with constant string arguments (fails closed: a computed list
    is one this check cannot verify)."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == _TRIGGERS):
            continue
        value = node.value
        if not isinstance(value, ast.Tuple):
            return None
        out: list[tuple[str, str, str]] = []
        for element in value.elts:
            if not (isinstance(element, ast.Call) and isinstance(element.func, ast.Name)
                    and element.func.id == "Trigger" and len(element.args) == 3):
                return None
            parts = []
            for arg in element.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    return None
                parts.append(arg.value)
            out.append((parts[0], parts[1], parts[2]))
        return out
    return None


def _per_kind_problems(keys: set[str]) -> list[str]:
    """Each artefact kind's declared input set, checked against the enumeration.

    Narrowing is legitimate — a line move does not change the ranked order, and a banner that says
    it does is false — but three things must stay true, or the narrowing becomes the hiding place:

    - every kind's inputs are a SUBSET of the enumerated triggers (no invented input);
    - the UNION over all kinds is the WHOLE enumeration — a trigger every kind excluded is a
      trigger that does nothing, which is a staleness quietly deleted rather than argued;
    - the *confidence bound* AND the *sampling run* depend on ALL of them. FR-58 is written about
      the bound (*"a stale confidence bound cannot be exported as current"*), so that entry is
      fixed literally by the requirement; the run (Story 5.1) is fixed by FR-22, whose named list
      ("ingestion, re-ranking or a line move") is a floor rather than a ceiling — its population IS
      the derived discarded set, so a *pin* moves it too. Under-invalidating a run means an hour of
      verdicts silently answering the wrong question, so neither is a judgement call.

    Imported at call time rather than parsed, because the entries are set arithmetic
    (``_ALL - {...}``) that an AST reading would have to re-implement — and a re-implementation is
    a second source of truth. The keys it is checked against come from the SOURCE above, so a
    monkey-patched TRIGGERS still fails.
    """
    from apx.core.domain.freshness import (
        ARTEFACT_KINDS,
        INPUTS_BY_KIND,
        KIND_BOUND,
        KIND_SAMPLING_RUN,
    )

    problems: list[str] = []
    missing_kinds = sorted(set(ARTEFACT_KINDS) - set(INPUTS_BY_KIND))
    if missing_kinds:
        problems.append(
            f"{_BY_KIND} does not declare: {missing_kinds} — an undeclared kind falls back to all "
            "eight inputs, which is safe, but the omission must be deliberate, not silent")
    for kind, inputs in INPUTS_BY_KIND.items():
        invented = sorted(set(inputs) - keys)
        if invented:
            problems.append(f"kind {kind!r} names inputs that are not triggers: {invented}")
    covered: set[str] = set()
    for inputs in INPUTS_BY_KIND.values():
        covered |= set(inputs)
    orphaned = sorted(keys - covered)
    if orphaned:
        problems.append(
            f"triggers no artefact depends on: {orphaned} — a trigger every kind excluded is a "
            "staleness deleted rather than argued (AD-23's list is complete by requirement)")
    for kind, why in (
        (KIND_BOUND, "FR-58 is written about the bound and fixes its input list literally"),
        (KIND_SAMPLING_RUN,
         "a run's population IS the derived discarded set, so every input that moves the set "
         "invalidates the run in flight (FR-22)"),
    ):
        declared = set(INPUTS_BY_KIND.get(kind, ()))
        if declared != keys:
            problems.append(
                f"kind {kind!r} must depend on ALL of {sorted(keys)}, not {sorted(declared)} "
                f"— {why}")
    return problems


def every_staleness_trigger_has_an_observable() -> CheckResult:
    """The enumerated staleness triggers and the stamp's observables match both ways (FR-58/AD-23).
    A trigger with no observable would be a staleness nothing detects; an observable with no trigger
    would be a staleness the surface cannot explain. Both fail the build."""
    name, ad = "every staleness trigger has an observable", "AD-23"
    if not _FRESHNESS.is_file():
        return CheckResult(name, ad, False, f"{_FRESHNESS} is missing (failing closed)")
    tree = _parse(_FRESHNESS)
    if tree is None:
        return CheckResult(
            name, ad, False, f"cannot parse {_FRESHNESS.name} (failing closed, cannot verify)")
    fields = _stamp_fields(tree)
    if fields is None:
        return CheckResult(
            name, ad, False,
            f"cannot read {_STAMP}'s fields statically (failing closed, cannot verify)")
    entries = _trigger_entries(tree)
    if entries is None:
        return CheckResult(
            name, ad, False,
            f"cannot read {_TRIGGERS} statically — it must stay a literal tuple of Trigger(key, "
            "fr, source) calls with constant strings (failing closed, cannot verify)")

    problems: list[str] = []
    keys = [key for key, _, _ in entries]
    if len(set(keys)) != len(keys):
        problems.append(f"duplicate trigger keys: {sorted({k for k in keys if keys.count(k) > 1})}")
    missing_observable = sorted(set(keys) - set(fields))
    if missing_observable:
        problems.append(
            f"triggers with no observable on {_STAMP}: {missing_observable} — a staleness nothing "
            "can detect, so the artefact would read FRESH while its input moved (AD-23)")
    unexplained = sorted(set(fields) - set(keys))
    if unexplained:
        problems.append(
            f"observables named by no trigger: {unexplained} — the surface could say 'stale' "
            "without being able to say why (FR-58 requires naming the input that changed)")
    absent = sorted(_REQUIRED - set(keys))
    if absent:
        problems.append(
            f"AD-23 triggers not in the list: {absent} — the enumeration is complete by "
            "requirement, not by convenience")
    for key, fr, source in entries:
        if not fr.strip():
            problems.append(f"trigger {key!r} has no French phrase — the banner would say nothing")
        if not source.strip():
            problems.append(f"trigger {key!r} names no source requirement (FR/AD)")
    problems.extend(_per_kind_problems(set(keys)))
    clocks = sorted(f for f, ann in fields.items() if ann.strip() in _TIME_ANNOTATIONS)
    if clocks:
        problems.append(
            f"observables that are clocks: {clocks} — staleness is never resolved by the passage "
            "of time (FR-58)")

    if problems:
        return CheckResult(name, ad, False, "; ".join(problems))
    return CheckResult(
        name, ad, True,
        f"{len(entries)} enumerated staleness triggers, each with an observable on {_STAMP} and "
        "none of them a clock; the two sets match both ways, every artefact kind's inputs are a "
        "subset covering the whole list, and the confidence bound depends on all of them")


def run() -> list[CheckResult]:
    return [every_staleness_trigger_has_an_observable()]
