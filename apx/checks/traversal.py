"""The filesystem has one walk (Story 7.1, FR-1 / AD-33).

`walk_confined` is the boundary that keeps an ingestion inside the folder that was submitted, and
`resolve_within` is the one that keeps it inside the deployment's declared root. Both are worth
exactly as much as the guarantee that nobody walks the filesystem another way.

That guarantee was false when this story began, and its falseness is the whole finding: the ingest
route validated a caller-supplied absolute path with `folder.is_dir()` and then handed it to
`rglob`, and the capacity pre-flight ran a *second* `rglob` over the same tree — so the count that
decided whether the import would fit and the walk that actually ingested were two different
traversals of two possibly different sets.

"We remembered to call the confined walk" is a habit. This is the property.

Build-time tooling, so this module sits outside the scanned runtime (`_RUNTIME_EXCLUDE`) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _fail_closed

#: Directory enumerations reached as a method on a path object.
_PATH_METHODS = ("rglob", "glob", "iterdir")
#: Directory enumerations reached through the ``os`` module, matched ONLY in the ``os.``-qualified
#: form. Matching the bare attribute name was this check's own first defect: ``projection.py``
#: defines a local recursive ``walk(value)`` over an in-memory mapping, and the check reported it as
#: a filesystem traversal — a guard inspecting the SHAPE of a call rather than the property it
#: claims to hold, which is the exact family it was written to close.
_OS_FUNCTIONS = ("walk", "scandir", "listdir")

#: The ONE module allowed to make them, by its path and not by its basename — a basename exemption
#: means any new file called `traversal.py` anywhere in the runtime silently re-opens the property
#: (the Story 5.9 lesson, learned there on `opening.py`).
_DOOR_MODULE = ("core", "domain", "traversal.py")

#: Enumerations of a directory THIS PROCESS created, which are not traversals of submitted material
#: and cannot carry a subtree boundary because there is no submitted subtree. Each entry carries the
#: reason it is here; an unexplained entry is how an allowlist becomes a hole.
_PERMITTED: tuple[tuple[tuple[str, ...], str], ...] = (
    (("adapters", "extraction", "msg_worker.py"),
     "enumerates the tempfile.TemporaryDirectory this function just created, to find what "
     "extract-msg wrote into it — the directory is ours, its contents are ours, and no "
     "caller-supplied path reaches it"),
)


def _walk_call(node: ast.Call) -> str:
    """The enumeration this call performs, or ``""``.

    A method call is matched on its attribute (``folder.rglob(...)``); an ``os`` function only when
    it is genuinely reached through ``os`` (``os.walk(...)``), never on the bare name.
    """
    if not isinstance(node.func, ast.Attribute):
        return ""
    attr = node.func.attr
    if attr in _PATH_METHODS:
        return attr
    if attr in _OS_FUNCTIONS:
        value = node.func.value
        if isinstance(value, ast.Name) and value.id == "os":
            return f"os.{attr}"
    return ""


def the_filesystem_has_one_walk(root: Path | None = None) -> CheckResult:
    """FR-1 — every directory enumeration in the runtime goes through the confined walk.

    A second traversal is not a duplicate; it is a path on which the confinement does not exist. The
    two the runtime carried before this story both mattered: the worker's `enumerate_units` froze
    the unit set of an import job, and the API's capacity pre-flight counted the files. Neither
    consulted the subtree boundary, and one of them decided what a job would contain.
    """
    trees, unparseable = _trees(root)
    if unparseable:
        return _fail_closed("the filesystem has one walk", "FR-1/AD-33", unparseable)
    violations: list[str] = []
    permitted = 0
    for path, tree in trees:
        if path.parts[-len(_DOOR_MODULE):] == _DOOR_MODULE:
            continue
        exempt = next((r for parts, r in _PERMITTED if path.parts[-len(parts):] == parts), None)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _walk_call(node)
            if not name:
                continue
            if exempt is not None:
                permitted += 1
                continue
            violations.append(
                f"{_where(path)}:{node.lineno} calls {name}(...) — a directory is enumerated "
                "through walk_confined() in core/domain/traversal.py, which is where the submitted "
                "subtree's boundary is applied; a second traversal is a path on which that "
                "boundary does not exist (FR-1)")
    if violations:
        return CheckResult(
            "the filesystem has one walk", "FR-1/AD-33", False, "\n  - ".join(sorted(violations)))
    names = "/".join((*_PATH_METHODS, *(f"os.{f}" for f in _OS_FUNCTIONS)))
    return CheckResult(
        "the filesystem has one walk", "FR-1/AD-33", True,
        f"no call to {names}(...) outside {'/'.join(_DOOR_MODULE)} anywhere in the runtime "
        f"({permitted} permitted call(s) over a directory this process created itself, each with a "
        "written reason), so every enumeration of submitted material applies the subtree's "
        "boundary (a walk reached through an alias, or one written in a shell-out, is not "
        "decidable here)")
