"""The *audit record*'s continuity properties (Story 5.9, FR-53 / AD-35 / AD-22).

Stories 5.5 to 5.8 made the record impossible to alter. Nothing made it impossible to **shorten**,
and the three checks here guard the three ways the machinery that does goes quietly missing.

- **store-has-one-door (FR-53/AD-35):** every construction of the durable store passes through
  ``apx.adapters.store_postgres.opening.open_store``, which wires the head journal. AD-35's
  invariant is *the head is recorded outside the restorable store on every append*, and it was true
  of the API and false of the import worker and both provisioning commands — which between them
  write the bulk of the record. A head advanced with no outside witness is a stretch a later
  truncation removes undetectably, and "we remembered to pass the journal" is a habit, not a
  property.
- **continuity-claim-is-derived (FR-53):** nothing outside the document's own assembly may set
  ``recomputable_from_this_document``. The field asserts a property of the bytes a reader holds; it
  used to be handed over from the adapter, carrying a fact about whether a row in the DATABASE had
  an anchor — so it printed **True** on a court document from which literally nothing could be
  recomputed, and the test that guarded it asserted the boolean rather than attempting the
  recomputation. A claim about a document is derived from that document or it is not that claim.
- **audit-write-never-swallowed (FR-53/AD-22):** no runtime path catches an exception around an
  audit append without re-raising. FR-53's first consequence is that the act FAILS; a handler that
  logs and continues is the unaudited mode AD-22 forbids by name, and it is one ``except
  Exception:`` away at every call site.

Build-time tooling, so this module is outside the scanned runtime (``_RUNTIME_EXCLUDE``) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.audit_record import _APPEND_AUDIT
from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _fail_closed

#: The store class whose construction must be journalled, and the ONE module allowed to build it.
_STORE = "SqlStore"
#: The ONE module allowed to build it, by its path and not by its basename. A basename exemption
#: means any new file called ``opening.py`` anywhere in the runtime silently re-opens the property
#: — the check would go on passing while the door it guards had grown a second one (review,
#: confirmed).
_DOOR_MODULE = ("adapters", "store_postgres", "opening.py")

#: The document field that must be derived from the document, and the one function allowed to set
#: it. ``assemble`` is where the tier is applied and where every other document-wide truth is
#: decided, so it is also where a claim about the document belongs.
_CLAIM = "recomputable_from_this_document"
_ASSEMBLER = "assemble"
_CLAIM_MODULE = "matter_record.py"


def the_store_has_one_door(root: Path | None = None) -> CheckResult:
    """FR-53/AD-35 — the durable store is constructed in exactly one place, which wires the head
    journal.

    The failure this closes is not hypothetical and was not caught by review: the import worker
    built the store with no journal and wrote most of the record, and ``manage restore`` — the one
    blessed operation that can hard-delete the record — opened the journal ``required=False``, so
    with the variable unset it performed no continuity check and printed its ordinary success line.
    Two constructions, two different postures, and nothing anywhere that would notice a third.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("the store has one door", "FR-53/AD-35", unparseable)
    violations: list[str] = []
    for path, tree in trees:
        if path.parts[-len(_DOOR_MODULE):] == _DOOR_MODULE:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (node.func.id if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if name != _STORE:
                continue
            violations.append(
                f"{_where(path)}:{node.lineno} builds {_STORE}(...) directly — the store is opened "
                f"through open_store(), which wires the head journal; a construction that omits it "
                "advances the chain head with no record outside the restorable store (AD-35)")
    if violations:
        return CheckResult(
            "the store has one door", "FR-53/AD-35", False, "\n  - ".join(sorted(violations)))
    return CheckResult(
        "the store has one door", "FR-53/AD-35", True,
        f"no call to {_STORE}(...) outside {'/'.join(_DOOR_MODULE)} anywhere in the runtime, "
        "so every "
        "construction goes through open_store() and journals its chain head outside the "
        "restorable store (a store reached through an alias is not decidable here)")


def _sets_the_claim(node: ast.Call) -> bool:
    return any(kw.arg == _CLAIM for kw in node.keywords)


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Which function each line belongs to — so a violation can be excused by its OWNER rather than
    by its file, which is the distinction that keeps the exemption honest."""
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for inner in ast.walk(node):
                if hasattr(inner, "lineno"):
                    owner.setdefault(inner.lineno, node.name)
    return owner


def the_continuity_claim_is_derived_from_the_document(root: Path | None = None) -> CheckResult:
    """FR-53 — ``recomputable_from_this_document`` is set by the document's assembly and by nothing
    else.

    Two legs. **No caller sets it**: an adapter that passes the flag is asserting a property of the
    reader's bytes from a fact about its own storage, which is exactly how the field came to print
    True on a document carrying no entries at all. **The assembler still does**: a check that only
    banned callers would pass just as happily on a build where nobody set it anywhere and the
    default rode out onto every export.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("the continuity claim is derived", "FR-53/AD-33", unparseable)
    violations: list[str] = []
    derived_in_assembler = False
    for path, tree in trees:
        owners = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _sets_the_claim(node)):
                continue
            owner = owners.get(node.lineno, "")
            if path.name == _CLAIM_MODULE and owner == _ASSEMBLER:
                derived_in_assembler = True
                continue
            violations.append(
                f"{_where(path)}:{node.lineno} sets {_CLAIM} in {owner or '<module>'}() — the "
                "claim is derived from the document at assembly, never handed over by a caller "
                "that knows something the document does not carry (FR-53)")
    if not derived_in_assembler and root is None:
        violations.append(
            f"nothing derives {_CLAIM} in {_ASSEMBLER}() — the flag would ride out on every export "
            "at its default, which is a claim nobody computed")
    if violations:
        return CheckResult(
            "the continuity claim is derived", "FR-53/AD-33", False,
            "\n  - ".join(sorted(violations)))
    return CheckResult(
        "the continuity claim is derived", "FR-53/AD-33", True,
        f"{_CLAIM} is written in {_ASSEMBLER}() and nowhere else; WHAT it is computed from is "
        "asserted by test (tests/domain/test_continuity.py), not decidable here")


def _reraises(handler: ast.ExceptHandler) -> bool:
    """Whether a handler can only end in the act failing.

    Three things disqualify it, and the last two were added after review pointed out that the first
    alone accepts a handler which raises on one branch and carries on down another:

    * no ``raise`` anywhere — the log-and-continue shape, which is the realistic defect;
    * a ``return`` — returning from a handler around an audit append IS the act completing without
      its entry, dressed as control flow;
    * a bare ``pass`` — swallowing, written out in full.

    What it still cannot decide is a handler whose ``raise`` sits under a condition. ``_audited_tx``
    is exactly that (``if attempt == 3: raise``, otherwise retry), and retrying is legitimate — so
    the rule stops here on purpose rather than banning a shape the runtime needs. The pass message
    says what was inspected, not more."""
    if any(isinstance(n, ast.Return | ast.Pass) for n in ast.walk(handler)):
        return False
    return any(isinstance(n, ast.Raise) for n in ast.walk(handler))


def an_audit_write_failure_is_never_swallowed(root: Path | None = None) -> CheckResult:
    """FR-53/AD-22 — no ``try`` whose body appends an audit entry has a handler that continues.

    FR-53's first consequence is one sentence: *an action whose audit record entry cannot be written
    fails*. The whole apparatus — the chain, the sequence authority, the outside witness — rests on
    it, and it is defeated by a single ``except Exception:`` that logs and carries on, at any of the
    twenty-six call sites. That handler looks like defensive programming in review; what it produces
    is an act that happened and a record that says it did not.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("an audit write failure is never swallowed", "FR-53/AD-22", unparseable)
    violations: list[str] = []
    guarded = 0
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            appends = any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == _APPEND_AUDIT
                for stmt in node.body for c in ast.walk(stmt))
            if not appends:
                continue
            guarded += 1
            for handler in node.handlers:
                if not _reraises(handler):
                    named = (
                        ast.unparse(handler.type) if handler.type is not None else "everything")
                    violations.append(
                        f"{_where(path)}:{handler.lineno} catches {named} around an audit append "
                        "and continues — an act whose entry could not be written must fail, not "
                        "proceed unaudited (FR-53/AD-22)")
    if violations:
        return CheckResult(
            "an audit write failure is never swallowed", "FR-53/AD-22", False,
            "\n  - ".join(sorted(violations)))
    return CheckResult(
        "an audit write failure is never swallowed", "FR-53/AD-22", True,
        f"{guarded} try-block(s) contain an audit append; every handler raises and none returns "
        "or passes (a raise under a condition — the retry loop — is deliberately still allowed)")
