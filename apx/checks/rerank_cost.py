"""No caller enqueues a ranking without first reading what it will destroy (Story 7.6, FR-22).

A new *ranking version* moves ``ranking_version_no``, and ``INPUTS_BY_KIND[KIND_SAMPLING_RUN]`` is
**every** observable — so every open *sampling run* in the *matter* is invalidated by a re-rank. The
product enforced that with ``_guard_open_run``, which is a **write** guard with two callers, both
writes: it fires after the cascade has been paid for and can only refuse to commit. What the lawyer
actually met was a 409 on her *next verdict*, after which ``abandon_sampling_run`` audited
``verdicts_kept=`` the count of the hour she had just lost.

AD-6 gives the HTTP layer the validate-authorise-enqueue job, so the warning lives at the enqueue.
This check is what keeps it there. The property is not *"the route as written today reads the
cost"* — that is what a test asserts — but *"there is no path to the enqueue that skips it"*, which
is a claim about every future caller, including the one written by somebody copying this one.

Stated over ``apx/api`` because that is where AD-6 puts the gesture: the worker calls the act, never
the enqueue, and the operator command deliberately runs the cascade synchronously (``manage rank``),
which is a different act with a different audience. A second enqueue site appearing anywhere in the
API is exactly the drift this exists to catch.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _APX_ROOT, _fail_closed, _load_trees
from apx.checks.queue_open import _calls

_API = ("apx", "api")
_ENQUEUE = "enqueue_ranking"
#: Either reads the cost directly, or goes through the helper that does and refuses on ``None``.
_COST_READERS = ("rerank_cost", "_rerank_cost_or_404")


def every_rerank_enqueue_states_its_cost(roots: Iterable[Path] | None = None) -> CheckResult:
    """A function that enqueues a ranking also reads the cost that ranking will impose (FR-22)."""
    name, ad = "no ranking is enqueued without stating its cost", "FR-22"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    offenders: list[str] = []
    enqueuers = 0
    reader_seen = False
    for path, tree in trees:
        if not any(path.parts[i:i + len(_API)] == _API for i in range(len(path.parts))):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            called = _calls(node)
            if called & set(_COST_READERS):
                reader_seen = True
            if _ENQUEUE not in called:
                continue
            enqueuers += 1
            if not called & set(_COST_READERS):
                offenders.append(f"{path.name}::{node.name}")

    if not reader_seen:
        return CheckResult(
            name, ad, False,
            f"the API reads no ranking cost at all — none of {list(_COST_READERS)} is called "
            "anywhere under apx/api, so this check cannot be passing (FR-22)")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"function(s) enqueue a ranking without reading its cost: {sorted(offenders)} — a "
            "re-rank invalidates every open sampling run in the matter, and a lawyer who was not "
            "told discovers it on her next verdict, after the verdicts are already lost")
    return CheckResult(
        name, ad, True,
        f"{enqueuers} enqueue site(s) under apx/api, each reading what the re-rank will invalidate "
        "before it is paid for, so the consequence is stated while it can still be refused")
