"""The *matter* export's structural properties (Story 5.7, FR-26 §11).

Two ways the export's honesty stops being true without anybody noticing, and a check for each.

- **export-tier-never-defaulted (FR-26):** no boundary that produces the document gives ``tier`` a
  default. This is the one act in the product that can move client content out of the firm on
  purpose; a default is a decision taken on the caller's behalf about *that*, and the caller who
  forgets to pass it is exactly the caller who should be stopped. A default is also invisible in a
  code review of the call site, which is where it would be introduced.
- **pending-section-is-not-a-zero (FR-26):** a section whose act does not exist yet says so in
  words and names the story that owns it. Zero is a finding about the **firm** — nobody validated
  anything — and *not built* is a finding about the **build**; a *bâtonnier* handed the first would
  draw a conclusion the second does not support, and that is the most consequential misreading this
  document can produce.

Build-time tooling, so this module is outside the scanned runtime (``_RUNTIME_EXCLUDE``) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _fail_closed
from apx.core.domain import matter_record

#: The parameter that decides whether client content leaves the building.
_TIER = "tier"

#: Functions allowed to carry a defaulted ``tier`` — none. Kept as an explicit empty set rather
#: than an implicit rule, so granting an exception is a visible edit to this file.
_ALLOWED_DEFAULTS: frozenset[str] = frozenset()


def _defaulted_tier(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether ``fn`` gives a parameter named ``tier`` a default, positionally or keyword-only."""
    args = fn.args
    positional = args.posonlyargs + args.args
    for arg, default in zip(reversed(positional), reversed(args.defaults), strict=False):
        if arg.arg == _TIER and default is not None:
            return True
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
        if arg.arg == _TIER and default is not None:
            return True
    return False


def export_tier_is_never_defaulted(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-26 §11 — every boundary that produces the document demands its tier."""
    name, fr = "the export tier is never defaulted", "FR-26"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    violations: list[str] = []
    seen = 0
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            names = {a.arg for a in
                     node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
            if _TIER not in names:
                continue
            seen += 1
            if _defaulted_tier(node) and node.name not in _ALLOWED_DEFAULTS:
                violations.append(
                    f"{_where(path)}:{node.lineno} {node.name}() defaults its tier — the act that "
                    "can move client content out of the firm does not choose for the caller")
    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True, f"{seen} function(s) take a tier; none defaults it")


def a_pending_section_is_not_a_zero(roots: Iterable[Path] | None = None) -> CheckResult:
    """FR-26 — a section whose act does not exist yet says so, in words, naming its story.

    Three legs. Every declared pending section names a story; its sentence says the act does not
    exist and prints no digit that could read as a count; and the runtime never renders a pending
    section through a length or a count, which is how "empty table" would come back."""
    name, fr = "a pending section names its story and is never a zero", "FR-26"
    violations: list[str] = []

    if not matter_record.PENDING_SECTIONS:
        violations.append("no section is declared pending — Story 5.8's two are still not built")
    for section, story in matter_record.PENDING_SECTIONS.items():
        if not story or not story[0].isdigit():
            violations.append(f"{section!r} declares {story!r}, which is not a story number")
            continue
        sentence = matter_record.pending_sentence_fr(section)
        if "n'existe pas encore" not in sentence:
            violations.append(f"{section!r} does not say that the act does not exist yet")
        if story not in sentence:
            violations.append(f"{section!r} does not name the story that owns it")
        # a bare digit in the sentence would read as a count; the story number is the exception
        digits = {ch for ch in sentence.replace(story, "") if ch.isdigit()}
        if digits:
            violations.append(
                f"{section!r} prints {sorted(digits)} — a digit in a pending section reads as a "
                "count, and a count reads as a finding about the firm")

    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, fr, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            # `len(...)` / `count(...)` applied to the pending sections is the shape of "0 acts"
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in {"len", "sum"}):
                continue
            for arg in node.args:
                target = arg.attr if isinstance(arg, ast.Attribute) else (
                    arg.id if isinstance(arg, ast.Name) else "")
                if target in {"pending", "PENDING_SECTIONS"}:
                    violations.append(
                        f"{_where(path)}:{node.lineno} counts the pending sections — a pending "
                        "section is a sentence, never a number")

    if violations:
        return CheckResult(name, fr, False, "; ".join(violations))
    return CheckResult(
        name, fr, True,
        f"{len(matter_record.PENDING_SECTIONS)} pending section(s), each naming its story in words")


def run() -> list[CheckResult]:
    return [export_tier_is_never_defaulted(), a_pending_section_is_not_a_zero()]
