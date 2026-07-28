"""AD-37 — one owning module per state transition, as a static shadow (story 2.6).

AD-37 (*"the largest silence in the original spine"*) requires every stateful entity's state column
to be written by exactly one owning use case, each transition a conditional commit. Most of AD-37 is
a runtime property (a conditional commit, an isolation level) no static check can see. The tractable
static shadow: the *failure register*'s ``resolution_state`` — the `open → resolved` transition and
the `open` creation — is written **only inside the store adapter** (``adapters/store_postgres``).
A write anywhere else (an API handler, a core use case) would be a second owner AD-37 forbids, and
it fails the build here.

A "write" is either constructing the ``Failure`` ORM model with a ``resolution_state=`` keyword, or
assigning ``<x>.resolution_state = …``. A read DTO that merely *carries* the value
(``RegisterEntry(resolution_state=…)``, ``FailureOut(resolution_state=…)``) is NOT a write and is
not flagged. Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_STORE_DIR = _APX_ROOT / "adapters" / "store_postgres"


def _kw(node: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in node.keywords)


def _dict_has_key(node: ast.Call, key: str) -> bool:
    """A call whose first positional arg is a dict literal with ``key`` — e.g.
    ``query(Failure).update({"resolution_state": …})``."""
    return any(
        isinstance(a, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == key for k in a.keys)
        for a in node.args)


def _is_failure_state_write(node: ast.AST) -> bool:
    """A write to the ``Failure`` model's ``resolution_state`` — every idiom a second transition
    owner could use, mirroring ``one_chunk_writer``'s coverage of the Core path:
      (a) ``Failure(resolution_state=…)`` ORM construction;
      (b) ``<x>.resolution_state = …`` attribute assignment;
      (c) ``setattr(_, "resolution_state", _)``;
      (d) ``update(Failure).values(resolution_state=…)`` Core bulk update;
      (e) ``query(Failure).update({"resolution_state": …})`` ORM bulk update;
      (f) a raw-SQL ``UPDATE … resolution_state`` string passed to ``text()``/``execute()``.
    A ``resolution_state=`` keyword in a READ DTO (``RegisterEntry``/``FailureOut``) is not a write
    and is not flagged."""
    if isinstance(node, ast.Assign | ast.AugAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(
            isinstance(t, ast.Attribute) and t.attr == "resolution_state" for t in targets)
    if isinstance(node, ast.Call):
        if _is_call_to(node, "Failure") and _kw(node, "resolution_state"):
            return True  # (a)
        if _is_call_to(node, "setattr") and len(node.args) >= 2 and isinstance(
                node.args[1], ast.Constant) and node.args[1].value == "resolution_state":
            return True  # (c)
        if _is_call_to(node, "values") and _kw(node, "resolution_state"):
            return True  # (d) — .values(resolution_state=…) on a Core update
        if _is_call_to(node, "update") and _dict_has_key(node, "resolution_state"):
            return True  # (e) — .update({"resolution_state": …})
        if (_is_call_to(node, "text") or _is_call_to(node, "execute")):
            for a in node.args:  # (f) — raw SQL that UPDATEs the state column
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    up = a.value.upper()
                    if "UPDATE" in up and "RESOLUTION_STATE" in up:
                        return True
    return False


def register_state_written_once(roots: Iterable[Path] | None = None) -> CheckResult:
    """The failure register's ``resolution_state`` is written only inside the store adapter (AD-37).
    Any write elsewhere is a second transition owner — a build failure."""
    name, ad = "register resolution_state written only in the store adapter", "AD-37"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        writes = any(_is_failure_state_write(n) for n in ast.walk(tree))
        if writes and _STORE_DIR not in path.resolve().parents and path.resolve() != _STORE_DIR:
            offenders.append(str(path))
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"Failure.resolution_state written outside the store adapter: {offenders} — AD-37 "
            "requires one owning module per transition")
    return CheckResult(name, ad, True, "resolution_state is written only in the store adapter")


def run() -> list[CheckResult]:
    return [register_state_written_once()]
