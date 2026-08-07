"""FR-22 / AD-39 — the *sampling run* draws over the DERIVED discarded set (Story 5.1, decision A1).

There are two things this build could call "the discarded set", and they are not the same set:

1. ``label_record WHERE label = 'discard'`` — the Story-2.x relevance verdict. No *ranking version*,
   no **line**, no *pins*.
2. ``derive_triage_sets(order, line, pins).discarded`` — the Epic-4 **view** (AD-39). It is what the
   lawyer looks at, and it is what Epic 5 audits.

The Epic 4 retrospective named the comparison-against-a-nearly-right-referent as this build's single
recurring defect, and the planning review (``epic-5-planning-2026-08-07.md``) fixed the referent:
**#2**. FR-22 requires a run to record *"the ranking version, the position of the line"*, which is a
sentence that cannot even be stated over #1 — and a *pièce* the lawyer deliberately pinned back
across the line would still be handed to her to review.

A decision written in a document is not a property. This check makes it one, in three legs over the
store adapter's source:

- the **derivation** (``_derived_discarded``) calls ``derive_triage_sets`` and references
  ``LabelRecord`` nowhere — a re-point at the label pile fails the build;
- the **population** the draw takes (``_run_population``) and the **observable** the freshness stamp
  records (``_compute_stamp``) both go through that one derivation, so a run can never be drawn over
  one set and invalidated against another. This is the leg that matters most: two nearly-right sets
  is exactly how the falsely-fresh defect happens;
- no sampling-run function references ``LabelRecord`` at all.

The check reads the SOURCE, not the imported objects, so a runtime monkey-patch cannot make it pass.
Fails closed: a missing module, a parse error, or a function it cannot find all fail the build.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_STORE = _APX_ROOT / "adapters" / "store_postgres" / "store.py"

_DERIVATION = "_derived_discarded"          # the ONE derivation of the discarded set
_DERIVE_FN = "derive_triage_sets"           # the Domain function it must go through
_LABEL_PILE = "LabelRecord"                 # the Story-2.x model it must NOT read
_DISCARD_LITERAL = "discard"                # ...nor its label value, by any spelling
# Functions that must reach the discarded set only through _DERIVATION.
_MUST_DELEGATE = ("_run_population", "_compute_stamp")
# Every sampling-run function; none of them may touch the label pile.
_SAMPLING_FUNCTIONS = (
    _DERIVATION, "_run_population", "size_for_target_bound", "start_sampling_run",
    "record_sampling_verdict", "complete_sampling_run", "abandon_sampling_run",
    "read_sampling_run", "list_sampling_runs", "read_run_freshness", "_compute_stamp",
)


def _functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Every ``def`` in the module by name (methods included). A duplicate name is not resolved —
    the last wins, which is what Python does too."""
    return {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _names_in(node: ast.AST) -> set[str]:
    """Every ``Name`` and ``Attribute`` identifier appearing anywhere under ``node``."""
    out: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            out.add(child.id)
        elif isinstance(child, ast.Attribute):
            out.add(child.attr)
    return out


def _label_pile_aliases(tree: ast.Module) -> set[str]:
    """Every module-level name bound to the label-pile model, plus the model itself.

    A check that looked only for the literal ``LabelRecord`` would be one ``LR = LabelRecord`` away
    from passing while the draw read the wrong population — a gate defeated by a rename is a habit,
    not a property. Covers ``X = LabelRecord``, ``from ... import LabelRecord as X`` and the
    qualified ``models.LabelRecord``."""
    aliases = {_LABEL_PILE}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _LABEL_PILE and alias.asname:
                    aliases.add(alias.asname)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            hit = (isinstance(value, ast.Name) and value.id in aliases) or (
                isinstance(value, ast.Attribute) and value.attr == _LABEL_PILE)
            if hit and isinstance(target, ast.Name):
                aliases.add(target.id)
    return aliases


def _string_constants(node: ast.AST) -> set[str]:
    """Every string literal under ``node`` — how a raw SQL route would spell the wrong pile."""
    return {
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)}


def sampling_population_is_the_derived_view(store_path: Path | None = None) -> CheckResult:
    """The sampling run's population and the ``discard_population`` observable are BOTH the Epic-4
    derived discarded view, computed by one derivation — never the Story-2.x label pile.

    ``store_path`` overrides the module read, so a test can point the check at a scratch copy
    carrying a deliberate violation and prove the check is live."""
    name, ad = "the sampling population is the derived discarded set", "AD-39"
    store = store_path or _STORE
    if not store.is_file():
        return CheckResult(name, ad, False, f"{store} is missing (failing closed)")
    tree = _parse(store)
    if tree is None:
        return CheckResult(
            name, ad, False, f"cannot parse {store.name} (failing closed, cannot verify)")
    functions = _functions(tree)

    problems: list[str] = []
    missing = [fn for fn in _SAMPLING_FUNCTIONS if fn not in functions]
    if missing:
        return CheckResult(
            name, ad, False,
            f"cannot find the sampling-run functions {missing} in {store.name} (failing closed — "
            "a renamed or deleted seam is not a verified property)")

    derivation_names = _names_in(functions[_DERIVATION])
    if _DERIVE_FN not in derivation_names:
        problems.append(
            f"{_DERIVATION} does not call {_DERIVE_FN} — the discarded set must be the Epic-4 "
            "derived VIEW over (the order, the line, the pins), never a stored membership (AD-39)")
    for fn in _MUST_DELEGATE:
        if _DERIVATION not in _names_in(functions[fn]):
            problems.append(
                f"{fn} does not go through {_DERIVATION} — the population a run DRAWS from and the "
                "population its freshness stamp OBSERVES must be the same derivation, or a run is "
                "invalidated against a set it was never drawn over (FR-22/AD-23)")
    aliases = _label_pile_aliases(tree)
    for fn in _SAMPLING_FUNCTIONS:
        used = _names_in(functions[fn]) & aliases
        if used:
            problems.append(
                f"{fn} references {sorted(used)} — Epic 5's discarded set is the derived view, not "
                "the Story-2.x label pile (decision A1); the label pile has no ranking version and "
                "no line, so FR-22's freeze cannot be stated over it")
        literals = _string_constants(functions[fn])
        if _DISCARD_LITERAL in literals or "label_record" in literals:
            problems.append(
                f"{fn} names the label value {_DISCARD_LITERAL!r} or the table 'label_record' as a "
                "string — the ORM route is not the only way back to the wrong population, and a "
                "raw predicate would read the Story-2.x pile just as wrongly (decision A1)")

    if problems:
        return CheckResult(name, ad, False, "; ".join(problems))
    return CheckResult(
        name, ad, True,
        f"{_DERIVATION} derives the discarded set through {_DERIVE_FN}; the draw and the "
        f"discard_population observable both go through it; none of the {len(_SAMPLING_FUNCTIONS)} "
        f"sampling-run functions reads {_LABEL_PILE}")


def run() -> list[CheckResult]:
    return [sampling_population_is_the_derived_view()]
