"""The one filesystem walk, and the root it may not leave (Story 7.1, FR-1 / C1).

FR-1's traversal clause is one sentence with three obligations:

    *Traversal is confined to the selected subtree. Symbolic links and junctions are resolved only
    where the target is inside that subtree; a link pointing outside it is recorded in the failure
    register with class ``traversal-out-of-scope`` and is not ingested. Traversal cycles are
    detected and terminate the walk for that branch with an entry, not with a hang.*

None of the three was built. ``ErrorClass.TRAVERSAL_OUT_OF_SCOPE`` has sat in the taxonomy since
Story 2.x **with no producer anywhere**, which is this project's dominant defect shape: a decision
recorded and never implemented reads exactly like one that was.

Worse, the *outer* boundary was missing too. ``POST /api/ingest`` took the folder as a bare string
from the request body and validated it with ``if not folder.is_dir()`` — so any authenticated user
could name any directory the API process could read and have it ingested into their own *matter*
under their own *RBAC scope*. The predictable targets sit on the data volume itself:
``$APX_DATA_PATH/originals`` holds every *matter*'s retained source documents and
``$APX_DATA_PATH/spool/<job>`` holds another user's upload in flight.

**The one rule this module exists to hold:** a path is inside a root when the *resolved* path is
``is_relative_to`` the *resolved* root. Never a string prefix — ``/data/ingest-evil`` starts with
``/data/ingest`` and is not inside it, which is the recurring wrong-referent defect wearing a
filesystem costume.

Pure Domain: no store, no clock, no configuration. It reads directories, which is what a walk is,
and decides nothing else.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


class OutsideRoot(ValueError):
    """A path that does not lie within the configured root.

    **The message carries no path**, deliberately. The caller answers an out-of-root folder and an
    absent folder with the same words, so that a caller cannot map the server's filesystem one
    request at a time — the non-disclosure discipline every identifier-taking route already follows.
    """

    def __init__(self) -> None:
        super().__init__("outside the permitted ingestion root")


class RootNotConfigured(ValueError):
    """No ingestion root is configured, so no server-side folder ingestion is permitted.

    Fail closed, as the encryption key and the head journal do at start-up (AD-31, AD-35). The
    alternative — falling back to "anywhere" — is the defect this module was written to close.
    """


class RootOverlapsDataVolume(ValueError):
    """The configured root can reach the retained originals or the upload spool.

    A confinement that admits them grants exactly what it was built to deny — those two directories
    are where another *matter*'s source documents and another user's in-flight upload live.

    The rule is deliberately about **those two directories**, not about the data volume as a whole.
    A root that merely sits on the same volume beside them (``$APX_DATA_PATH/corpus`` next to
    ``$APX_DATA_PATH/originals``) is a perfectly ordinary on-premise layout and reaches nothing it
    should not; refusing it would push a deployment toward turning the confinement off.
    """


@dataclass(frozen=True)
class WalkedFile:
    """One file the walk will ingest. ``relative`` is its path within the submitted tree, which is
    what provenance records and what a *pièce* is named by."""

    path: Path
    relative: str


@dataclass(frozen=True)
class OutOfScopeLink:
    """A symbolic link whose target lies outside the submitted subtree.

    Recorded rather than followed (FR-1). ``target`` is kept for the register's detail — the firm's
    own administrator needs to know where the link pointed in order to fix it, and this value never
    crosses a *tenant* boundary because it is written into that *matter*'s own register entry.
    """

    path: Path
    relative: str
    target: str
    is_directory: bool


@dataclass(frozen=True)
class Walk:
    """What one confined walk found: the files to ingest, and the links that left the subtree."""

    files: tuple[WalkedFile, ...] = ()
    out_of_scope: tuple[OutOfScopeLink, ...] = ()

    def __len__(self) -> int:
        return len(self.files)


def resolve_within(root: Path | str, candidate: Path | str) -> Path:
    """The candidate, resolved, guaranteed to lie within ``root`` — or :class:`OutsideRoot`.

    Both sides are resolved before comparing. Resolving only the candidate leaves the comparison
    open in the flattering direction: a root given relatively, or a root that is itself a symlink,
    then fails to match a candidate that really is inside it, and a caller "fixes" it by relaxing
    the rule.

    The root itself is inside the root — ingesting the whole permitted tree is the ordinary case.
    """
    resolved_root = Path(root).resolve()
    resolved = Path(candidate).resolve()
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise OutsideRoot
    return resolved


def ingest_root(env: dict[str, str] | None = None) -> Path:
    """The one directory tree server-side folder ingestion may read, from ``APX_INGEST_ROOT``.

    Unset, blank, or absent from the filesystem → :class:`RootNotConfigured`. Overlapping the data
    volume in either direction → :class:`RootOverlapsDataVolume`.
    """
    source = dict(os.environ if env is None else env)
    raw = (source.get("APX_INGEST_ROOT", "") or "").strip()
    if not raw:
        raise RootNotConfigured(
            "APX_INGEST_ROOT is not set — server-side folder ingestion names the one directory "
            "tree it may read, and without it every folder is refused (there is no 'anywhere')")
    root = Path(raw).resolve()
    if not root.is_dir():
        raise RootNotConfigured(
            "APX_INGEST_ROOT does not name a directory that exists on this host")
    data = (source.get("APX_DATA_PATH", "") or "").strip()
    if data:
        volume = Path(data).resolve()
        for sensitive in (volume / "originals", volume / "spool"):
            # Either direction is a breach: a root ABOVE them can walk into them, and a root INSIDE
            # one of them is already standing in the material it must not read.
            if (root == sensitive or root.is_relative_to(sensitive)
                    or sensitive.is_relative_to(root)):
                raise RootOverlapsDataVolume(
                    f"APX_INGEST_ROOT can reach {sensitive.name} under APX_DATA_PATH — the "
                    "retained originals and the upload spool are exactly what the confinement "
                    "exists to keep out of an ingestion")
    return root


def _entries(folder: Path) -> Iterator[Path]:
    """Every path under ``folder``, files and directories alike.

    ``Path.rglob`` does not descend into symlinked directories (``recurse_symlinks=False`` is the
    default from Python 3.13), which is why a cycle terminates instead of hanging. That property is
    the standard library's and not ours, so it is pinned by a test that builds a real cycle — the
    day an upgrade or a rewrite to ``os.walk`` changes it, the build says so rather than the walk
    hanging in front of a lawyer.
    """
    return folder.rglob("*")


def walk_confined(folder: Path) -> Walk:
    """Walk ``folder``, yielding only what genuinely lies within it.

    A path is kept when its **resolved** location is inside the resolved folder. A symbolic link
    whose target leaves the subtree — to a file or to a directory — is recorded as out of scope and
    never read. FR-1's assumption says why this is a boundary question and not a filtering one: *a
    link into another matter's folder must not silently ingest that material under this matter's
    RBAC scope*, and no downstream filter can recover a provenance that was wrong at intake.
    """
    base = folder.resolve()
    files: list[WalkedFile] = []
    escaped: list[OutOfScopeLink] = []
    for path in sorted(_entries(folder)):
        try:
            relative = str(path.relative_to(folder))
        except ValueError:  # pragma: no cover — rglob yields only paths under folder
            continue
        try:
            target = path.resolve()
        except OSError:
            # A broken or unresolvable link is not out of scope, and it is not a file either; the
            # extraction path owns unreadable material and gives it its own register class.
            continue
        inside = target == base or target.is_relative_to(base)
        if not inside:
            escaped.append(OutOfScopeLink(
                path=path, relative=relative, target=str(target),
                is_directory=path.is_dir()))
            continue
        if path.is_file():
            files.append(WalkedFile(path=path, relative=relative))
    return Walk(files=tuple(files), out_of_scope=tuple(escaped))
