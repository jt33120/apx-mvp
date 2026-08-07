"""FR-58 / AD-23 — no clock reaches the freshness decision (Story 4.13).

FR-58's last consequence is the one a cache would quietly break: *"staleness is never resolved by
the passage of time, by a background recomputation or by being viewed. It is resolved by an explicit
user-initiated recomputation, which produces a new artefact rather than refreshing the old one."*

A TTL is the most natural thing in the world to add to a freshness module, and it would invert the
guarantee: an artefact whose input moved would become "fresh" again by waiting, and one whose inputs
never moved would become "stale" by sitting. So the modules that decide freshness are forbidden a
time source at all. This check reads their SOURCE and fails the build on:

- an ``import`` of ``time``/``datetime``/``calendar`` or a ``from datetime import …`` — including
  aliased forms, which are resolved to the module they come from;
- any call to a clock: ``now``, ``utcnow``, ``today``, ``time``, ``monotonic``, ``perf_counter``,
  ``timestamp``, ``mktime``, ``fromtimestamp`` — however it is reached;
- any use of ``timedelta``, the only arithmetic that could express an expiry window.

Covered modules: the freshness vocabulary, the worklist derived from it, and the read seam that
computes the verdicts. **Not** covered, and deliberately: the store adapter (which stamps rows with
an ``at`` timestamp — a record of *when*, never an input to the decision) and the API layer.

Reads the source, so a runtime patch cannot make it pass. Fails closed: a missing module or a parse
error fails the build.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent

# The modules that DECIDE freshness. Adding one here is how a future freshness module inherits the
# rule; a module missing from disk fails the check rather than being skipped.
_DECIDING_MODULES: tuple[Path, ...] = (
    _APX_ROOT / "core" / "domain" / "freshness.py",
    _APX_ROOT / "core" / "domain" / "worklist.py",
    _APX_ROOT / "core" / "app" / "read" / "freshness.py",
)

_TIME_MODULES = frozenset({"time", "datetime", "calendar", "zoneinfo"})
_CLOCK_CALLS = frozenset({
    "now", "utcnow", "today", "monotonic", "perf_counter", "process_time", "time_ns",
    "monotonic_ns", "mktime", "fromtimestamp", "timestamp",
})
_FORBIDDEN_NAMES = frozenset({"timedelta", "UTC", "timezone"})


def _offences(path: Path, tree: ast.Module) -> list[str]:
    found: list[str] = []
    aliases: set[str] = set()  # local names bound to a time module or one of its members
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _TIME_MODULES:
                    found.append(f"{path.name}: imports {alias.name} — a time source (FR-58)")
                    aliases.add(alias.asname or root)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _TIME_MODULES:
                imported = ", ".join(a.name for a in node.names)
                found.append(
                    f"{path.name}: imports {imported} from {node.module} — a time source (FR-58)")
                aliases.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            called = (
                func.attr if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else None)
            if called in _CLOCK_CALLS:
                found.append(f"{path.name}: calls {called}() — a clock (FR-58)")
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            found.append(
                f"{path.name}: names {node.id} — elapsed-time arithmetic has no place in a "
                "freshness decision (FR-58)")
    return found


def freshness_is_never_time_based() -> CheckResult:
    """No clock, no elapsed-time arithmetic and no time import reaches the modules that decide
    freshness (FR-58/AD-23) — so staleness cannot resolve itself by waiting, and freshness cannot
    expire by sitting."""
    name, ad = "the freshness decision names no clock", "AD-23"
    missing = [p.name for p in _DECIDING_MODULES if not p.is_file()]
    if missing:
        return CheckResult(
            name, ad, False,
            f"freshness modules missing: {missing} (failing closed — a module this check cannot "
            "read is a module nothing constrains)")
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in _DECIDING_MODULES:
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        offenders.extend(_offences(path, tree))
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"a time source reaches the freshness decision: {offenders} — FR-58 forbids staleness "
            "being resolved by the passage of time, by a background recomputation or by being "
            "viewed")
    return CheckResult(
        name, ad, True,
        f"no clock, no timedelta and no time import in {len(_DECIDING_MODULES)} deciding modules; "
        "staleness is resolved only by an explicit recomputation producing a new artefact")


def run() -> list[CheckResult]:
    return [freshness_is_never_time_based()]
