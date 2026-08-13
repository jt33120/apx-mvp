"""The *override*'s structural properties (Story 5.6, FR-25 / AD-37 / AD-22).

FR-25 costs one sentence, and the three ways that cost quietly stops being charged are the three
checks here.

- **override-reason-one-validator (FR-25):** "the reason is mandatory" is implemented ONCE, in
  ``core/domain/override.py``. Every module that writes an override verb calls it, and no module
  anywhere else defines a second blank-reason test. Before this story the rule existed twice — a
  typed error for *pins*, a bare ``ValueError`` for the truncation override — and a third copy was
  about to be written for the register. Two copies of one rule drift, and the copy that drifts is
  the one that stops refusing.
- **override-reason-in-the-record (FR-25/AD-22):** the reason reaches the *audit record* through
  the one renderer. FR-25 requires it stored **verbatim** there; the truncation override shipped
  in Story 5.5 putting its reason on a mutable marker row and **not** in the record at all, which
  is precisely the miss a hand-composed detail string makes easy.
- **override-ground-named (FR-25):** every *override* names which of FR-25's three grounds it rests
  on, the ``override`` act class has a real writer, and **nothing counts overrides by act class**.
  A *pin* is an override whose FR-24 class is ``pin``; a count over the class reports zero on a
  matter with forty pins and looks perfectly right on every matter that never pinned anything.

Build-time tooling, so this module is outside the scanned runtime (``_RUNTIME_EXCLUDE``) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.audit_record import _ACTION_ARG, _APPEND_AUDIT, _verb_of
from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _fail_closed
from apx.core.domain import audit, override

#: Where the rule lives. The one module allowed to say what a blank reason is.
_VALIDATOR_HOME = ("core", "domain", "override.py")

#: The names the rule is spelled with. A write path must call the first; the record must be
#: composed with the second.
_VALIDATOR = "validate_override_reason"
_RENDERER = "override_detail"

#: The catalogue constants naming an override verb — e.g. ``ACT_PIN_OVERRIDE``. Derived from the
#: catalogue rather than listed here, so a fourth override act is covered the moment it exists.
def _override_constants() -> frozenset[str]:
    verbs = set(audit.override_verbs())
    return frozenset(
        name for name in dir(audit)
        if name.startswith("ACT_") and getattr(audit, name) in verbs)


def _is_validator_home(path: Path) -> bool:
    return path.parts[-3:] == _VALIDATOR_HOME


def _calls(tree: ast.Module, func_name: str) -> bool:
    """Whether the module calls ``func_name`` anywhere (bare or attribute-qualified)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == func_name:
            return True
        if isinstance(fn, ast.Attribute) and fn.attr == func_name:
            return True
    return False


def _writes_an_override(tree: ast.Module, constants: frozenset[str]) -> bool:
    """Whether the module WRITES an override: it names an override act constant **and** appends to
    the record. Both halves are needed. The catalogue module names every constant and writes
    nothing; a module that appends without naming one writes something that is not an override."""
    named = any(
        (isinstance(node, ast.Attribute) and node.attr in constants)
        or (isinstance(node, ast.Name) and node.id in constants)
        for node in ast.walk(tree))
    return named and _calls(tree, _APPEND_AUDIT)


def _blank_reason_tests(tree: ast.Module) -> list[int]:
    """Line numbers of a second implementation of "the reason is mandatory".

    The shape: an ``if`` whose test calls ``.strip()`` on something called ``reason`` (or
    ``*_reason``). Narrow on purpose — it is exactly what the two pre-5.6 copies looked like, and
    it does not fire on the unrelated ``sentence``/``text`` emptiness rules elsewhere in the
    Domain, which are their own requirements and not this one."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for sub in ast.walk(node.test):
            if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "strip"):
                continue
            target = sub.func.value
            if isinstance(target, ast.Name) and (
                    target.id == "reason" or target.id.endswith("_reason")):
                hits.append(node.lineno)
    return hits


def override_reason_has_one_validator(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-25. Two legs.

    **Leg 1 — every override write path validates.** A module that both names an override act
    constant and appends to the record must call :func:`validate_override_reason`. A write path
    that forgot it accepts the empty sentence, and the entry it produces is indistinguishable from
    a reasoned one at every later read.

    **Leg 2 — nobody else defines "blank".** A second blank-reason test anywhere outside
    ``core/domain/override.py`` fails the build, whether or not it currently agrees with the
    first one."""
    name, fr = "the override reason has one validator", "FR-25"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    constants = _override_constants()
    violations: list[str] = []
    writers = 0

    for path, tree in trees:
        if _is_validator_home(path):
            continue
        for lineno in _blank_reason_tests(tree):
            violations.append(
                f"{_where(path)}:{lineno} tests a reason for blankness — FR-25's 'mandatory' is "
                f"defined once, in core/domain/override.py")
        if _writes_an_override(tree, constants):
            writers += 1
            if not _calls(tree, _VALIDATOR):
                violations.append(
                    f"{_where(path)} writes an override act without calling {_VALIDATOR}")

    if not constants:
        violations.append("the catalogue names no override act at all — FR-25 has no writer")
    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"{writers} module(s) write an override; all validate through {_VALIDATOR}, and no second "
        "definition of blank exists")


def override_reason_reaches_the_record(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-25/AD-22 — the reason is in the *audit record*, verbatim, through one renderer.

    **Leg 1 — the statically-known call sites.** Where an ``_append_audit`` call names an override
    verb outright, its ``detail`` must be an :func:`override_detail` call. An f-string there would
    compile and read fine and would be one edit away from dropping the reason — which is exactly
    what the truncation override shipped doing.

    **Leg 2 — the modules.** A module that writes an override must call the renderer. This covers
    the *pin*, whose verb arrives as a parameter (``audit_action``) and cannot be resolved
    statically at its call site. The residual gap is named rather than papered over: the renderer
    itself refuses a blank reason, so the runtime closes what the AST cannot see."""
    name, fr = "the override reason reaches the record", "FR-25"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    constants = _override_constants()
    violations: list[str] = []
    sites = 0

    for path, tree in trees:
        if _is_validator_home(path):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == _APPEND_AUDIT):
                continue
            action = node.args[_ACTION_ARG] if len(node.args) > _ACTION_ARG else None
            detail = node.args[_ACTION_ARG + 1] if len(node.args) > _ACTION_ARG + 1 else None
            for kw in node.keywords:
                if kw.arg == "action":
                    action = kw.value
                if kw.arg == "detail":
                    detail = kw.value
            if action is None or _verb_of(action) not in constants:
                continue
            sites += 1
            is_rendered = (
                isinstance(detail, ast.Call)
                and ((isinstance(detail.func, ast.Name) and detail.func.id == _RENDERER)
                     or (isinstance(detail.func, ast.Attribute) and detail.func.attr == _RENDERER)))
            if not is_rendered:
                violations.append(
                    f"{_where(path)}:{node.lineno} records an override with a detail that is not "
                    f"{_RENDERER}(...) — FR-25 requires the reason in the record, verbatim")
        if _writes_an_override(tree, constants) and not _calls(tree, _RENDERER):
            violations.append(f"{_where(path)} writes an override without calling {_RENDERER}")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"{sites} statically-named override write(s), each composed by {_RENDERER}")


def override_names_its_ground(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-25 — the classification is data, and it is never counted by act class.

    **Leg 1 — the catalogue.** Every act carrying the ``override`` FR-24 class is override-flagged;
    every override-flagged act names one of FR-25's three grounds; the class has a writer and is
    not also declared pending.

    **Leg 2 — the count.** No runtime module compares an act class against the override class. The
    correct count is over the flag (:func:`audit.is_override`), and the difference is not academic:
    a *pin* is an override whose class is ``pin``, so the class-based count returns zero on a
    matter with forty of them — and returns the right answer on every matter that has none, which
    is how it would reach production."""
    name, fr = "an override names its ground and is never counted by class", "FR-25"
    violations: list[str] = []

    for verb in audit.ACTS:
        act = audit.ACTS[verb]
        if act.act_class == audit.CLASS_OVERRIDE and act.override is None:
            violations.append(f"{verb!r} carries the override class but names no FR-25 ground")
        if act.override is not None and act.override not in override.GROUNDS:
            violations.append(f"{verb!r} names {act.override!r}, not one of FR-25's three grounds")
    if audit.CLASS_OVERRIDE not in audit.covered_classes():
        violations.append("the override act class has no writer")
    if audit.CLASS_OVERRIDE in audit.PENDING_CLASSES:
        violations.append("the override act class is written and cannot also be declared pending")

    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            for operand in operands:
                named = (
                    (isinstance(operand, ast.Attribute) and operand.attr == "CLASS_OVERRIDE")
                    or (isinstance(operand, ast.Name) and operand.id == "CLASS_OVERRIDE")
                    or (isinstance(operand, ast.Constant)
                        and operand.value == audit.CLASS_OVERRIDE))
                if named:
                    violations.append(
                        f"{_where(path)}:{node.lineno} compares against the override act CLASS — "
                        "an override is counted by its ground, never by its class (a pin's class "
                        "is 'pin')")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"{len(audit.override_verbs())} override act(s), each naming one of FR-25's three grounds; "
        "nothing counts them by class")


def run() -> list[CheckResult]:
    return [
        override_reason_has_one_validator(),
        override_reason_reaches_the_record(),
        override_names_its_ground(),
    ]
