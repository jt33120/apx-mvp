"""The *validation act*'s structural properties (Story 5.8, FR-45 / FR-44 / FR-24).

FR-45 turns *"this document was read by a human"* from a phrase into a mechanism. Three ways the
mechanism quietly stops being one, and a check for each. All three guard the same class of defect
and all three fail in the same direction — **the flattering one**, which is the direction nobody
reports.

- **validation-act-sole-acceptor (FR-45/FR-24 §614):** exactly one verb carries the
  ``value_accepted`` class, exactly one function in the runtime writes it, and that function writes
  the *validation act* in the same breath. FR-24 §614 is explicit — *a value the user never touched
  is recorded as accepted **only** where a validation act occurred over it* — so a second writer is
  not a duplicate, it is a **default**, and a default is the one thing FR-45 forbids by name.
- **validation-provenance-never-a-literal (FR-45(c)/FR-44):** no call site hands the opened-fact a
  constant. FR-45(c) legislates against exactly one shape: a bulk act that stamps *not opened* over
  a batch, when a *pièce* in that batch had in fact been opened. A literal at the call site **is**
  that shape, written down, and it looks perfectly reasonable in review.
- **acceptance-is-never-manufactured (FR-45):** nothing in the runtime by which dwell time, a
  scroll position or a screen visit could produce an acceptance, and **one home** for the sentence
  the record attributes to the lawyer. A second, differently-worded control is how she comes to
  assert something she never read.
- **validation-version-never-defaulted (FR-45/AD-23, retro B2/H7):** the *ranking version* an act
  accepts is never supplied by a default. Added after the fleet found the fourth way, on the
  assertion's OTHER load-bearing fact: ``validate_pieces`` defaulted ``version_no=None``, which
  resolves *the current version at commit time*, and no route or client sent one — so a re-rank
  landing between the reading and the click moved what a person was recorded as having accepted.
  Same shape as the provenance defect, same direction, one field over. A default here is a default
  on what a human is recorded as having accepted, which is the one thing FR-45 forbids by name.

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
from apx.core.domain import audit, validation

#: The catalogue constant naming the acceptance, and the one naming the gesture it must accompany.
_ACCEPTED = "ACT_VALUES_ACCEPTED"
_VALIDATE = "ACT_VALIDATE_PIECE"
_WITHDRAW = "ACT_VALIDATION_WITHDRAWN"

#: The keyword carrying FR-45's load-bearing fact into the ledger.
_PROVENANCE_ARG = "opened_at"

#: The OTHER load-bearing fact: which *ranking version*'s assessment the act accepts (AD-23). The
#: acts that take it, and the parameter's name at every layer.
_VERSION_ARG = "version_no"
_VERSION_TAKERS = ("validate_pieces", "batch_split")

#: Where the assertion lives. The one module allowed to spell the sentence the record attributes to
#: a lawyer.
_ASSERTION_HOME = ("core", "domain", "validation.py")

#: A fragment of the assertion, distinctive enough that a paraphrase elsewhere is caught and short
#: enough that it survives a re-wording of the tail.
_ASSERTION_MARK = "ai lu cette"

#: Names by which time, scrolling or presence could mint an acceptance. FR-45 forbids each of these
#: by name — *"no default, no elapsed time, no scroll position, no screen visit"* — and the
#: prohibition is worth a check precisely because auto-marking is the single most tempting
#: affordance on a 1 700-row reading surface.
_MANUFACTURED: tuple[str, ...] = (
    "auto_validate", "autovalidate", "auto_accept", "autoaccept",
    "mark_as_read", "mark_read", "on_scroll", "scroll_position",
    "dwell", "time_on_screen", "seconds_on_page", "elapsed_read",
)

#: The same prohibition in the lawyer's language: a French string that says the reading happened by
#: itself. A surface may not print one even if no function is named for it.
_MANUFACTURED_FR: tuple[str, ...] = (
    "lu automatiquement", "lue automatiquement", "consulté automatiquement",
    "validation automatique", "marqué comme lu", "marquée comme lue",
)


def _enclosing_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]


def _own_nodes(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Every node of ``fn``'s own body, **not** descending into a nested function.

    Without this a call inside a nested ``_work()`` — the store's transaction idiom — is reported
    once for the inner function and again for the outer one, which reads as two defects where
    there is one."""
    out: list[ast.AST] = []
    stack: list[ast.AST] = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        out.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return out


#: How a withdrawal names itself at a call site — the domain constant or the catalogue one.
_WITHDRAWAL_NAMES = frozenset({"ACTION_WITHDRAWN", _WITHDRAW})


def _is_withdrawal(call: ast.Call) -> bool:
    """Whether this call's ``action`` argument names a withdrawal."""
    for kw in call.keywords:
        if kw.arg != "action":
            continue
        target = kw.value
        if isinstance(target, ast.Name) and target.id in _WITHDRAWAL_NAMES:
            return True
        if isinstance(target, ast.Attribute) and target.attr in _WITHDRAWAL_NAMES:
            return True
    return False


def _appended_verbs(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """The catalogue constants this function appends to the record, by name."""
    verbs: set[str] = set()
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == _APPEND_AUDIT):
            continue
        arg = node.args[_ACTION_ARG] if len(node.args) > _ACTION_ARG else None
        for kw in node.keywords:
            if kw.arg == "action":
                arg = kw.value
        named = _verb_of(arg) if arg is not None else None
        if named is not None:
            verbs.add(named)
    return verbs


def only_the_validation_act_accepts(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-45/FR-24 §614 — an acceptance has exactly one origin, and it is a human gesture.

    Three legs.

    **Leg 1 — one verb.** Exactly one catalogued verb carries ``value_accepted``. Two would let a
    count over the class mean two different things, and the export prints that count.

    **Leg 2 — one writer.** Exactly one function in the runtime appends it. The rule *"accepted
    exists only where a validation act occurred"* is not enforceable if two places can write one.

    **Leg 3 — never alone.** That function also appends the *validation act* itself. An acceptance
    written without its gesture is precisely the default FR-45 forbids: countable, filterable, and
    indistinguishable at every later read from one a lawyer actually performed.
    """
    name, fr = "only the validation act produces an acceptance", "FR-45"
    violations: list[str] = []

    accepting = audit.verbs_for(audit.CLASS_VALUE_ACCEPTED)
    if list(accepting) != [audit.ACT_VALUES_ACCEPTED]:
        violations.append(
            f"the value_accepted class is carried by {sorted(accepting)} — FR-45 gives an "
            "acceptance exactly one origin, and a second verb is a second way to mint one")

    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)

    writers: list[str] = []
    for path, tree in trees:
        for fn in _enclosing_functions(tree):
            verbs = _appended_verbs(fn)
            if _ACCEPTED not in verbs:
                continue
            writers.append(f"{_where(path)}:{fn.lineno} {fn.name}()")
            if _VALIDATE not in verbs:
                violations.append(
                    f"{_where(path)}:{fn.lineno} {fn.name}() writes an acceptance without the "
                    "validation act that must accompany it — an acceptance with no gesture behind "
                    "it is the default FR-45 forbids")
    if len(writers) > 1:
        violations.append(
            f"{len(writers)} functions write an acceptance ({'; '.join(sorted(writers))}) — "
            "FR-45 allows one, and the second is how 'accepted as-is' acquires a default")
    if not writers:
        violations.append(
            "nothing writes an acceptance — the value_accepted class has a verb and no writer, so "
            "the export's accepted count can only ever be zero")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"one verb, one writer ({writers[0]}), and it never writes an acceptance alone")


def the_opened_fact_is_never_a_literal(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-45(c)/FR-44 — the provenance is **read**, never asserted.

    FR-45's fourth consequence exists because of one shape: a bulk act that records *not opened*
    for every *pièce* in a batch, including the ones the lawyer had opened. The requirement answers
    it in as many words — *"records for each pièce that it was not opened in the viewer, unless it
    was"* — and the code shape that breaks it is a **constant at the call site**.

    A literal is allowed only where the enclosing function names the withdrawal verb: a withdrawal
    accepts nothing and has no provenance to record, so ``opened_at=None`` there is the fact rather
    than an assumption about it."""
    name, fr = "the opened fact is never a literal", "FR-45"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    violations: list[str] = []
    seen = 0

    for path, tree in trees:
        for fn in _enclosing_functions(tree):
            for node in _own_nodes(fn):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg != _PROVENANCE_ARG:
                        continue
                    seen += 1
                    if not isinstance(kw.value, ast.Constant):
                        continue
                    # A withdrawal accepts nothing and has no provenance to record, so `None` in
                    # the SAME call as a withdrawal action is the fact rather than an assumption
                    # about it. Judged per call, never per function: a validate call sitting in the
                    # same function must still be read from the ledger.
                    if kw.value.value is None and _is_withdrawal(node):
                        continue
                    violations.append(
                        f"{_where(path)}:{node.lineno} in {fn.name}() hands the opened fact the "
                        f"literal {kw.value.value!r} — FR-45 requires it read per pièce for the "
                        "acting lawyer, and a constant is a blanket stamp over a batch")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True, f"{seen} call site(s) carry the opened fact; none asserts it")


def _version_param(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.arg | None:
    for arg in (*fn.args.args, *fn.args.kwonlyargs):
        if arg.arg == _VERSION_ARG:
            return arg
    return None


def _version_has_default(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if this function declares ``version_no`` WITH a default, positionally or keyword-only.

    Positional defaults align to the TAIL of ``args``; keyword-only defaults align one-for-one with
    ``kwonlyargs`` and carry ``None`` where there is none."""
    tail = fn.args.args[len(fn.args.args) - len(fn.args.defaults):]
    if any(a.arg == _VERSION_ARG for a in tail):
        return True
    return any(a.arg == _VERSION_ARG and d is not None
               for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True))


def the_accepted_version_is_never_defaulted(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-45/AD-23 — the *ranking version* an act accepts comes from the caller, never a default.

    Two legs, and the second is the one that catches a regression:

    (a) **No call to** ``validate_pieces`` / ``batch_split`` **omits** ``version_no``. A call that
        omits it is asking the store to pick, and the store's pick is *whatever is current when the
        request lands* — which is not what was on the screen.
    (b) **No layer ON THAT PATH declares** ``version_no`` **with a default** — the two acts
        themselves, and any function that calls one. This is where the defect actually lived: the
        store's signature said ``version_no: int | None = None``, the two routes repeated it, and
        every layer was individually defensible while the act as a whole had no referent. A default
        one layer up is the same defect with a longer stack trace.

    **Scoped to the ACT, deliberately.** A default is perfectly honest on a READ — *"the current
    version"* is what a table or a drawer should show when nobody named one, and thirty-seven
    functions in this tree rely on it. It stops being honest the moment the answer is written down
    as what a person accepted. So the check follows the act, not the parameter name: the two takers
    and their callers, and nothing else.
    """
    name, fr = "the accepted ranking version is never defaulted", "FR-45"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    violations: list[str] = []
    calls = 0

    for path, tree in trees:
        for fn in _enclosing_functions(tree):
            reaches_the_act = fn.name in _VERSION_TAKERS
            for node in _own_nodes(fn):
                if not isinstance(node, ast.Call):
                    continue
                target = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else "")
                if target not in _VERSION_TAKERS:
                    continue
                calls += 1
                reaches_the_act = True
                if not any(kw.arg == _VERSION_ARG for kw in node.keywords):
                    violations.append(
                        f"{_where(path)}:{node.lineno} in {fn.name}() calls {target}() without "
                        f"{_VERSION_ARG} — the act would accept whichever version is current when "
                        "it commits, not the one the lawyer was shown")
            if reaches_the_act and _version_param(fn) is not None and _version_has_default(fn):
                violations.append(
                    f"{_where(path)}:{fn.lineno} {fn.name}() performs or reaches a validation act "
                    f"and declares {_VERSION_ARG} with a default — a default here resolves "
                    "whatever version is current at the commit, on the record of what a person "
                    "accepted (AD-23)")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"{calls} call site(s) name the ranking version; no layer of the act defaults it")


def _is_assertion_home(path: Path) -> bool:
    return path.parts[-3:] == _ASSERTION_HOME


def acceptance_is_never_manufactured(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-45 — nothing produces an acceptance except a person, saying so in one set of words.

    **Leg 1 — no time, no scroll, no visit.** FR-45 forbids each by name: *"No default, no elapsed
    time, no scroll position, no screen visit produces it."* A symbol or a French string by which
    one could is refused at build time, because auto-marking is the single most tempting affordance
    on a reading surface with 1 700 rows and the requirement it breaks is the one the whole trust
    architecture rests on.

    **Leg 2 — one home for the assertion.** The sentence the record attributes to the lawyer is
    defined once, in ``core/domain/validation.py``. A second spelling anywhere else is a second
    control with different words, and the entry it writes would be a claim she never made in the
    terms that were recorded."""
    name, fr = "an acceptance is never manufactured", "FR-45"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    violations: list[str] = []

    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                lowered = node.name.lower()
                for banned in _MANUFACTURED:
                    if banned in lowered:
                        violations.append(
                            f"{_where(path)}:{node.lineno} defines {node.name!r} — FR-45 forbids "
                            "elapsed time, a scroll position or a screen visit from producing an "
                            "acceptance")
            if isinstance(node, ast.Name):
                lowered = node.id.lower()
                for banned in _MANUFACTURED:
                    if banned in lowered:
                        violations.append(
                            f"{_where(path)}:{node.lineno} names {node.id!r} — FR-45 forbids "
                            "presence or elapsed time from producing an acceptance")
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            lowered = node.value.lower()
            for phrase in _MANUFACTURED_FR:
                if phrase in lowered:
                    violations.append(
                        f"{_where(path)}:{node.lineno} says {phrase!r} — the product has exactly "
                        "one verb for reading and it is performed by a person")
            if _ASSERTION_MARK in node.value and not _is_assertion_home(path):
                violations.append(
                    f"{_where(path)}:{node.lineno} spells the assertion again — it is defined in "
                    "core/domain/validation.py, and a second spelling is a second control whose "
                    "words are not the ones the record will carry")

    if violations:
        return CheckResult(name, fr, False, "; ".join(sorted(set(violations))))
    return CheckResult(
        name, fr, True,
        f"nothing manufactures an acceptance; the assertion has one home "
        f"({len(validation.ASSERTION_FR)} chars, core/domain/validation.py)")


def run() -> list[CheckResult]:
    return [
        only_the_validation_act_accepts(),
        the_opened_fact_is_never_a_literal(),
        acceptance_is_never_manufactured(),
        the_accepted_version_is_never_defaulted(),
    ]
