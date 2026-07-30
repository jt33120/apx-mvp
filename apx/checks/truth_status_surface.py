"""The truth-status SURFACE gate (Story 3.4; AD-20/FR-15). The two 3.1/3.2 checks gate how the
status is *constructed* (constant per engine, no truncation); this gates how it is *serialised*.

- **result_set_response_serialises_truth_status (FR-15):** a response/export model that carries an
  engine's result items — a field typed as ``SemanticResult``/``DeterministicResult`` (or their API
  DTOs ``…Out``), OR a bare ``results`` list/sequence (even ``list[dict]``/``list``) — must also
  carry a ``truth_status`` field, so the status is never dropped on the wire (*"every result set
  declares its truth status … in every export"*). A bounded PREVIEW (``hits: list[SearchHitOut]``)
  is deliberately not an engine result set and is not flagged.
- **no_response_merges_the_two_engines (FR-15):** no model carries BOTH a semantic result item AND a
  deterministic result item — the two engines are never combined into one undifferentiated list.

Both are **inheritance-aware** (a field carried on a base counts; a ``truth_status`` inherited from
a base satisfies the rule — so a DRY ``class _ResultSetOut(BaseModel): truth_status: str`` base is
not a false positive) and read **forward-ref string annotations** (mirroring ``no_truncation``).
Scope: the serialisation/wire layer (``apx/api/`` by default — where a result set becomes an
export). The internal reader-port bundle ``ExactSearch`` is mapped to a truth-status DTO before the
wire, so it is correctly out of scope. A result-set export added under ``worker/`` or a new module
must be added to the scanned roots. Both fail closed on an unparseable file; injectable ``roots``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _APX_ROOT / "api"
_REPO_ROOT = _APX_ROOT.parent
_EXCLUDE = frozenset({"__pycache__", "node_modules"})

# The engine result-item types (domain + their API DTOs). A model whose field is typed as one of
# these IS a serialised result set. `SearchHitOut` (the preview) is deliberately absent.
_SUGGESTIVE_ITEMS = frozenset({"SemanticResult", "SemanticResultOut"})
_EXHAUSTIVE_ITEMS = frozenset({"DeterministicResult", "DeterministicResultOut"})
_RESULT_ITEMS = _SUGGESTIVE_ITEMS | _EXHAUSTIVE_ITEMS
_SEQUENCE_TYPES = frozenset({"list", "tuple", "Sequence", "Iterable", "Collection"})


def _where(path: Path) -> Path | str:
    return path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path


def _api_trees(roots: Iterable[Path] | None) -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    if roots is not None:
        return _load_trees(list(roots))
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in sorted(_API_DIR.rglob("*.py")):
        if set(path.parts) & _EXCLUDE:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def _class_map(trees: list[tuple[Path, ast.Module]]) -> dict[str, ast.ClassDef]:
    out: dict[str, ast.ClassDef] = {}
    for _, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                out.setdefault(node.name, node)
    return out


def _ann_type_names(ann: ast.expr) -> set[str]:
    """The type names in an annotation — ``ast.Name`` ids AND any anchor name inside a forward-ref
    string, whole (``'list[SemanticResultOut]'``) or nested (``list['SemanticResultOut']``). Mirrors
    and extends ``no_truncation``'s string case."""
    names = {n.id for n in ast.walk(ann) if isinstance(n, ast.Name)}
    for n in ast.walk(ann):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            names |= {t for t in _RESULT_ITEMS if t in n.value}
    return names


def _is_sequence_ann(ann: ast.expr) -> bool:
    node = ann.value if isinstance(ann, ast.Subscript) else ann
    return isinstance(node, ast.Name) and node.id in _SEQUENCE_TYPES


def _own_type_names(cls: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            names |= _ann_type_names(node.annotation)
    return names


def _own_field_names(cls: ast.ClassDef) -> set[str]:
    return {node.target.id for node in cls.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}


def _own_has_results_sequence(cls: ast.ClassDef) -> bool:
    """A field NAMED ``results`` typed as a list/tuple/sequence — even untyped (``list[dict]`` /
    ``list``). The name convention catches an untyped result container the type anchor cannot."""
    for node in cls.body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == "results" and node.annotation is not None
                and _is_sequence_ann(node.annotation)):
            return True
    return False


def _resolved(cls: ast.ClassDef, cmap: dict[str, ast.ClassDef],
              accessor, seen: set[str] | None = None) -> set[str]:
    """``accessor`` unioned over ``cls`` and its in-scope base classes, transitively — so a field on
    a base is seen by the subclass (inheritance-aware)."""
    seen = seen if seen is not None else set()
    if cls.name in seen:
        return set()
    seen.add(cls.name)
    out = set(accessor(cls))
    for base in cls.bases:
        bn = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else None)
        if bn is not None and bn in cmap:
            out |= _resolved(cmap[bn], cmap, accessor, seen)
    return out


def _resolved_has_results_sequence(cls: ast.ClassDef, cmap: dict[str, ast.ClassDef],
                                   seen: set[str] | None = None) -> bool:
    seen = seen if seen is not None else set()
    if cls.name in seen:
        return False
    seen.add(cls.name)
    if _own_has_results_sequence(cls):
        return True
    for base in cls.bases:
        bn = base.id if isinstance(base, ast.Name) else (
            base.attr if isinstance(base, ast.Attribute) else None)
        if bn is not None and bn in cmap and _resolved_has_results_sequence(cmap[bn], cmap, seen):
            return True
    return False


def _carries_results(cls: ast.ClassDef, cmap: dict[str, ast.ClassDef]) -> bool:
    """The class serialises an engine result set — a result-item-typed field (own or inherited), or
    a bare ``results`` sequence (the untyped-container case)."""
    return bool(_resolved(cls, cmap, _own_type_names) & _RESULT_ITEMS) or \
        _resolved_has_results_sequence(cls, cmap)


def result_set_response_serialises_truth_status(
    roots: Iterable[Path] | None = None,
) -> CheckResult:
    """A response/export model carrying engine result items declares a ``truth_status`` field
    (FR-15) — inheritance-aware. Vacuous-safe; fires on a results-carrying model without
    ``truth_status``. Fails closed on an unparseable file."""
    name, ad = "a result-set response serialises its truth status", "AD-20"
    trees, unparseable = _api_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    cmap = _class_map(trees)
    seen = 0
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not _carries_results(node, cmap):
                continue
            seen += 1
            if "truth_status" not in _resolved(node, cmap, _own_field_names):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} {node.name} serialises engine results but "
                    "no truth_status (own or inherited) — every result set declares its truth "
                    "status, on the wire and in every export (FR-15)")
    return CheckResult(
        name, ad, True,
        f"every result-set response ({seen}) serialises its truth status ({len(trees)} files)")


def no_response_merges_the_two_engines(roots: Iterable[Path] | None = None) -> CheckResult:
    """No response/export model carries BOTH a semantic result item AND a deterministic one — the
    two engines are never combined into one list (FR-15). Inheritance-aware. Fails closed."""
    name, ad = "no response merges the two engines", "AD-20"
    trees, unparseable = _api_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    cmap = _class_map(trees)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            items = _resolved(node, cmap, _own_type_names)
            if (items & _SUGGESTIVE_ITEMS) and (items & _EXHAUSTIVE_ITEMS):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} {node.name} carries BOTH engines' result items "
                    "(own or inherited) — the suggestive and exhaustive sets are never combined "
                    "into one list (FR-15)")
    return CheckResult(
        name, ad, True, f"no response merges the two engines ({len(trees)} files)")


def run() -> list[CheckResult]:
    """The truth-status surface checks, for the harness to fan out over."""
    return [
        result_set_response_serialises_truth_status(),
        no_response_merges_the_two_engines(),
    ]
