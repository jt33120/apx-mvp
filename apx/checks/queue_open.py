"""Nothing defers a job onto a queue it has not opened (Story 7.4, AD-6).

The defect this holds closed had no error message on any surface a developer sees, and it closed the
product's front door.

``PsycopgConnector.pool`` raises ``AppNotOpen`` until ``open_async`` has been called. ``open_async``
was called in exactly one place — ``manage worker``, a **different process** — so the API deferred
onto a pool that did not exist, and the upload route's ``except Exception`` turned that into
*« file d'import indisponible »*. Every submission on every real deployment answered 503, and the
suite could not notice: the connector is chosen from ``DATABASE_URL`` when the module is imported,
the suite runs on SQLite, and the in-memory connector it therefore gets is the one implementation
with no such guard. The failure existed only in the configuration no test uses.

The fix is that deferring opens the queue, and this check is what keeps the **next** enqueue helper
from being written the other way — because the next one will be added by somebody copying the
existing one, and the existing one is only correct now if the copy keeps the first line.

Stated over the sealed queue package alone: ``procrastinate`` may not be imported anywhere else
(AD-17), so this is the whole surface on which a ``defer`` can be written.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _APX_ROOT, _fail_closed, _load_trees

_QUEUE = ("store_postgres", "queue")
_DEFER = ("defer_async", "defer", "configure_task")
_OPENER = "ensure_open"


def _calls(node: ast.AST) -> set[str]:
    """Every attribute or bare name this function calls, by its final component."""
    names: set[str] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        if isinstance(inner.func, ast.Attribute):
            names.add(inner.func.attr)
        elif isinstance(inner.func, ast.Name):
            names.add(inner.func.id)
    return names


def every_defer_opens_the_queue(roots: Iterable[Path] | None = None) -> CheckResult:
    """A function that defers a job also opens the queue (AD-6)."""
    name, ad = "nothing defers onto a queue it has not opened", "AD-6"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    offenders: list[str] = []
    deferrers = 0
    opener_seen = False
    for path, tree in trees:
        if not any(path.parts[i:i + len(_QUEUE)] == _QUEUE for i in range(len(path.parts))):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name == _OPENER:
                opener_seen = True
                continue
            called = _calls(node)
            if not called & set(_DEFER):
                continue
            deferrers += 1
            if _OPENER not in called:
                offenders.append(f"{path.name}::{node.name}")

    if not opener_seen:
        return CheckResult(name, ad, False,
                           f"the queue package declares no {_OPENER}() — a check that cannot find "
                           "the door it guards is not passing (AD-6)")
    if offenders:
        return CheckResult(name, ad, False,
                           f"function(s) defer a job without opening the queue: {sorted(offenders)}"
                           f" — call {_OPENER}() first, or the deferral raises AppNotOpen against "
                           "a real PostgreSQL and reaches the caller as an availability error")
    return CheckResult(
        name, ad, True,
        f"{deferrers} enqueue helper(s) in the sealed queue package, each opening the queue before "
        "it defers, so a process that enqueues cannot depend on another process having opened it")
