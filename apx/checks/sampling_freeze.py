"""FR-22 — a *sampling run* freezes its population by IDENTIFIER, not by a seed (Story 5.1).

FR-22 is explicit: the run *"records the ranking version, the position of **the line**, the *RBAC
scope* and the **explicit identifier list** of the drawn *pièces* — **a seed alone is
insufficient**"*.

The reason is not fastidiousness. A seed reproduces a draw only against the *same population in the
same order*: re-rank the *matter* and the same seed picks a different set, so a "frozen" run stored
as ``(seed, n)`` would silently re-describe itself every time the corpus moved — and the sentence a
firm says to a judge would be about a sample nobody ever reviewed.

This check makes the freeze a **shape**, over the data model's source:

- ``SamplingRun`` declares every freeze column, and every one of them is ``nullable=False``. A
  nullable freeze column is a freeze that can be absent, and an absent freeze is not a freeze;
- ``SamplingRunItem`` exists and carries ``proxy_piece_id`` and ``member_piece_ids`` — the explicit
  identifiers themselves. This is the leg that makes *"a seed alone is insufficient"* structural:
  deleting the item table to keep only the run's ``seed`` fails the build.

The check reads the SOURCE of ``models.py``, so it holds whether or not a migration has run, and a
runtime monkey-patch cannot make it pass. Fails closed on a missing or unparseable module.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_MODELS = _APX_ROOT / "adapters" / "store_postgres" / "models.py"

_RUN = "SamplingRun"
_ITEM = "SamplingRunItem"
# FR-22's freeze, column by column, with WHY each one is part of it.
_FREEZE: dict[str, str] = {
    "ranking_version_id": "the ranking version the discarded set was derived over",
    "ranking_version_no": "the version NUMBER the surface names (AD-23 — no unqualified reference)",
    "last_retained_piece_id": (
        "the position of THE LINE, by the identity of the last retained pièce — never a bare "
        "integer, so an import that adds pièces cannot silently move what the run recorded (FR-17)"
    ),
    "pin_ledger_seq": "the pin ledger's position: a pin moves one pièce across the line (FR-43)",
    "scope": "the RBAC scope the draw was taken within (AD-13)",
}
# The explicit identifier list — what makes a seed insufficient.
_IDENTIFIERS = ("proxy_piece_id", "member_piece_ids")


def _class_columns(tree: ast.Module, class_name: str) -> dict[str, ast.expr | None] | None:
    """``{column name: its mapped_column(...) value}`` for a model class, or None when absent."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            columns: dict[str, ast.expr | None] = {}
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    columns[stmt.target.id] = stmt.value
            return columns
    return None


def _is_not_nullable(value: ast.expr | None) -> bool:
    """True when the column declares ``nullable=False`` explicitly. An omitted ``nullable`` is NOT
    accepted: SQLAlchemy would infer it from the annotation, and inference is not a declaration —
    a freeze column's non-nullability has to be readable at the point of definition."""
    if not isinstance(value, ast.Call):
        return False
    for kw in value.keywords:
        if kw.arg == "nullable":
            return isinstance(kw.value, ast.Constant) and kw.value.value is False
    return False


def a_sampling_run_freezes_its_identifiers(models_path: Path | None = None) -> CheckResult:
    """The run's freeze is a shape: every FR-22 freeze column is present and NOT NULL, and the
    explicit identifier list exists as its own table — a seed alone is insufficient.

    ``models_path`` overrides the module read, so a test can point the check at a scratch copy
    carrying a deliberate violation and prove the check is live."""
    name, ad = "a sampling run freezes identifiers, not a seed", "AD-23"
    models = models_path or _MODELS
    if not models.is_file():
        return CheckResult(name, ad, False, f"{models} is missing (failing closed)")
    tree = _parse(models)
    if tree is None:
        return CheckResult(
            name, ad, False, f"cannot parse {models.name} (failing closed, cannot verify)")

    problems: list[str] = []
    run_columns = _class_columns(tree, _RUN)
    if run_columns is None:
        problems.append(f"{_RUN} is not declared in {models.name}")
    else:
        for column, why in _FREEZE.items():
            if column not in run_columns:
                problems.append(f"{_RUN}.{column} is missing — it freezes {why} (FR-22)")
            elif not _is_not_nullable(run_columns[column]):
                problems.append(
                    f"{_RUN}.{column} does not declare nullable=False — a freeze column that can "
                    f"be absent is not a freeze; it holds {why} (FR-22)")

    item_columns = _class_columns(tree, _ITEM)
    if item_columns is None:
        problems.append(
            f"{_ITEM} is not declared — without the explicit identifier list a run is frozen only "
            "by its seed, and FR-22 says in as many words that a seed alone is insufficient")
    else:
        for column in _IDENTIFIERS:
            if column not in item_columns:
                problems.append(
                    f"{_ITEM}.{column} is missing — the drawn population must be re-readable by "
                    "identifier, without re-deriving the discarded set (FR-22)")
            elif not _is_not_nullable(item_columns[column]):
                problems.append(
                    f"{_ITEM}.{column} does not declare nullable=False — a drawn family with no "
                    "identifiers is a row that says nothing about what was reviewed")

    if problems:
        return CheckResult(name, ad, False, "; ".join(problems))
    return CheckResult(
        name, ad, True,
        f"{_RUN} declares all {len(_FREEZE)} FR-22 freeze columns NOT NULL (the ranking version, "
        f"the line by pièce identity, the pin ledger and the scope), and {_ITEM} carries the "
        "explicit identifier list a seed cannot replace")


def run() -> list[CheckResult]:
    return [a_sampling_run_freezes_its_identifiers()]
