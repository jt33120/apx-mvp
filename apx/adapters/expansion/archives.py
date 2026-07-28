"""Archive expanders — `.zip` (stdlib) and `.7z` (py7zr), bounded by configuration (AD-17).

A zip bomb is refused by its **declared uncompressed sizes**, checked BEFORE any member is
decompressed, so the bomb is never read whole into memory — it becomes a ``ContainerUnopenable``
signal the ingestion use case records as one `container-unopenable` register entry of cardinality
`unknown` (AD-38), never an outage. A corrupt or password-protected archive is likewise a container
we could not open — `container-unopenable`, its contents unknown — not a leaf `extraction-error`.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from apx.core.domain.config import ExpansionBounds
from apx.core.ports.expansion import ContainerUnopenable


def _guard_archive(
    path: Path, n_members: int, declared_bytes: int, bounds: ExpansionBounds) -> None:
    """Refuse a bomb by its DECLARED figures, before decompressing (AD-17). A too-large member
    count or a declared expansion ratio over the configured ceiling raises ``ContainerUnopenable``.
    The reason names only numbers — never a filename or a fragment (no document content leaks)."""
    if n_members > bounds.max_members:
        raise ContainerUnopenable(
            f"{n_members} members exceed the configured limit of {bounds.max_members}")
    container_bytes = path.stat().st_size
    if container_bytes > 0:
        ratio = declared_bytes // container_bytes
        if ratio > bounds.max_expansion_ratio:
            raise ContainerUnopenable(
                f"declared expansion ratio {ratio}:1 exceeds the configured limit of "
                f"{bounds.max_expansion_ratio}:1")


class ZipExpander:
    """Implements the Expander port for .zip archives, bounded (AD-17)."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def recognises(self, path: Path) -> bool:
        return path.suffix.lower() == ".zip"     # a pure container (no own leaf body)

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".zip":
            return None
        try:
            with zipfile.ZipFile(path) as archive:
                files = [i for i in archive.infolist() if not i.is_dir()]
                _guard_archive(path, len(files), sum(i.file_size for i in files), self._bounds)
                return [(info.filename, archive.read(info)) for info in files]
        except ContainerUnopenable:
            raise
        except Exception as exc:  # noqa: BLE001 — a corrupt/encrypted zip is a container we could
            # not open; its contents are unknown → container-unopenable (never a leaf). The reason
            # names only the exception type, never a document fragment.
            raise ContainerUnopenable(
                f"could not open the archive ({type(exc).__name__})") from exc


class SevenZipExpander:
    """Implements the Expander port for .7z archives via py7zr (LGPL-2.1, in-process, lazy import),
    bounded exactly like ZipExpander — declared uncompressed sizes checked before extraction."""

    def __init__(self, bounds: ExpansionBounds | None = None) -> None:
        self._bounds = bounds or ExpansionBounds.defaults()

    def recognises(self, path: Path) -> bool:
        return path.suffix.lower() == ".7z"      # a pure container (no own leaf body)

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".7z":
            return None
        try:
            import py7zr

            with py7zr.SevenZipFile(path, "r") as probe:
                infos = [i for i in probe.list() if not i.is_directory]
                _guard_archive(
                    path, len(infos), sum(i.uncompressed for i in infos), self._bounds)
            # py7zr reads via extraction: extract to a temp dir (already bounded above) and read the
            # members back — a fresh handle, since list() consumed the first.
            with tempfile.TemporaryDirectory(prefix="apx-7z-") as td, \
                    py7zr.SevenZipFile(path, "r") as archive:
                archive.extractall(path=td)
                root = Path(td).resolve()
                members: list[tuple[str, bytes]] = []
                for info in infos:
                    member = (root / info.filename).resolve()
                    # Defence-in-depth against a Zip-Slip arcname: read only what stayed inside the
                    # temp dir (py7zr already sanitises on extract; this re-validates on read).
                    if member.is_relative_to(root) and member.is_file():
                        members.append((info.filename, member.read_bytes()))
                return members
        except ContainerUnopenable:
            raise
        except Exception as exc:  # noqa: BLE001 — corrupt / encrypted / unsupported codec: a
            # container we could not open, contents unknown → container-unopenable.
            raise ContainerUnopenable(
                f"could not open the archive ({type(exc).__name__})") from exc
