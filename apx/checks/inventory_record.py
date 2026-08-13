"""AD-38 — the *denominator* is one record of seven disjoint counts, with no `int` representation
and the unknown cardinality never summed (Story 2.7; the seventh count is Story 5.6's). Two static
shadows of AD-38:

(A) ``inventory_record_fields_enumerated`` — the ``Inventory`` domain record declares EXACTLY the
    seven named fields; a dropped, added or renamed field fails the build (the same shape as
    ``payload_schema.chunk_columns_enumerated`` enforcing the chunk column set). This is the "one
    record with exactly these fields" half of AD-38.
(B) ``unknown_cardinality_never_summed`` — ``unknown_cardinality_entries``, ``excluded_as_noise``
    and ``retired`` (the counts AD-38 keeps OUTSIDE the two-term identity) are never an operand of
    ``+`` anywhere in ``apx/**``: they are named lines, never summed into a total. This is the
    decidable shadow of *"an unknown cardinality is never summed into any total"* and *"the
    denominator has no `int` representation anywhere in the source"*.

Both fail closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_INVENTORY = _APX_ROOT / "core" / "domain" / "inventory.py"

# AD-38's one record — exactly these seven disjoint named counts. ``overridden_register_entries``
# is Story 5.6's third identity term: FR-25 lets a person take a register entry out of `open`
# although the document never entered the corpus, and neither of the two other terms can hold it.
_SEVEN_FIELDS = frozenset({
    "submitted_pieces", "in_corpus", "open_register_entries", "overridden_register_entries",
    "excluded_as_noise", "retired", "unknown_cardinality_entries",
})
# The counts AD-38 keeps OUTSIDE the two-term identity — never summed into any total. (`in_corpus`
# and `open_register_entries` ARE the identity's two terms, so they are legitimately added.) Matched
# as an ATTRIBUTE (`inv.retired`) for all three; `retired` is a common word, so a BARE NAME
# `retired` is not flagged (only the two distinctive names are) — no unrelated-local false positive.
_NEVER_SUMMED = frozenset({"unknown_cardinality_entries", "excluded_as_noise", "retired"})
_NEVER_SUMMED_STRICT = frozenset({"unknown_cardinality_entries", "excluded_as_noise"})


def _inventory_fields(tree: ast.Module) -> set[str] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Inventory":
            return {
                s.target.id for s in node.body
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            }
    return None


def inventory_record_fields_enumerated(root: Path | None = None) -> CheckResult:
    """The ``Inventory`` record declares EXACTLY AD-38's seven disjoint fields (Story 2.7/5.6)."""
    name, ad = "the inventory record declares exactly AD-38's seven fields", "AD-38"
    path = root if root is not None else _INVENTORY
    tree = _parse(path)
    if tree is None:
        return CheckResult(name, ad, False, f"cannot parse {path.name} (failing closed)")
    fields = _inventory_fields(tree)
    if fields is None:
        return CheckResult(name, ad, False, "no `Inventory` record found (failing closed)")
    if fields != _SEVEN_FIELDS:
        missing, extra = sorted(_SEVEN_FIELDS - fields), sorted(fields - _SEVEN_FIELDS)
        return CheckResult(
            name, ad, False,
            f"Inventory fields != AD-38's six (missing={missing}, extra={extra})")
    return CheckResult(
        name, ad, True, "the seven disjoint denominator counts are all present")


def _is_forbidden_operand(node: ast.AST) -> bool:
    """An expression reading a count AD-38 keeps outside the identity: any of the three as an
    attribute (``inv.retired``), or the two distinctive names as a bare name (``retired`` alone is a
    common word, flagged only as an attribute — no unrelated-local false positive)."""
    if isinstance(node, ast.Attribute):
        return node.attr in _NEVER_SUMMED
    if isinstance(node, ast.Name):
        return node.id in _NEVER_SUMMED_STRICT
    return False


def _summed_call_elements(node: ast.Call) -> bool:
    """True if ``node`` is a ``sum(...)`` / ``math.fsum(...)`` whose literal iterable argument holds
    a forbidden count — the builtin-total idiom AD-38 forbids just as much as ``+``."""
    fn = node.func
    is_total = (isinstance(fn, ast.Name) and fn.id == "sum") or (
        isinstance(fn, ast.Attribute) and fn.attr in ("sum", "fsum"))
    if not is_total:
        return False
    for arg in node.args:
        if isinstance(arg, ast.List | ast.Tuple | ast.Set):
            if any(_is_forbidden_operand(e) for e in arg.elts):
                return True
    return False


def _sums_a_forbidden_count(node: ast.AST) -> bool:
    """True if ``node`` folds a count AD-38 keeps outside the identity into a total — via ``+`` /
    ``+=``, or as an element of a ``sum(...)`` / ``math.fsum(...)`` call (AD-38: never summed)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _is_forbidden_operand(node.left) or _is_forbidden_operand(node.right)
    if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
        return _is_forbidden_operand(node.target) or _is_forbidden_operand(node.value)
    if isinstance(node, ast.Call):
        return _summed_call_elements(node)
    return False


def unknown_cardinality_never_summed(roots: Iterable[Path] | None = None) -> CheckResult:
    """AD-38: ``unknown_cardinality_entries`` / ``excluded_as_noise`` / ``retired`` are never an
    operand of ``+`` — never summed into a total. A violation fails the build (Story 2.7)."""
    name, ad = "unknown-cardinality / noise / retired are never summed into a total", "AD-38"
    search = list(roots) if roots is not None else [_APX_ROOT]
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in _iter_py(search):
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        if any(_sums_a_forbidden_count(n) for n in ast.walk(tree)):
            offenders.append(str(path))
    if unparseable:
        return CheckResult(name, ad, False, f"cannot parse (failing closed): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"a count AD-38 keeps outside the identity is summed into a total in: {offenders} — "
            "an unknown cardinality is never summed (AD-38)")
    return CheckResult(name, ad, True, "no disjoint denominator count is ever summed into a total")


def run() -> list[CheckResult]:
    return [inventory_record_fields_enumerated(), unknown_cardinality_never_summed()]
