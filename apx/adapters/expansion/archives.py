"""Expand a .zip archive into its member files (stdlib zipfile — no dependency)."""

from __future__ import annotations

import zipfile
from pathlib import Path

# Skip a member whose declared uncompressed size is absurd — a zip-bomb guard. The
# use case bounds total members and nesting depth; this bounds a single member.
_MAX_MEMBER_BYTES = 200 * 1024 * 1024


class ZipExpander:
    """Implements the Expander port for .zip archives."""

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        if path.suffix.lower() != ".zip":
            return None
        # A corrupt archive raises here; the ingestion use case records it as a failure.
        with zipfile.ZipFile(path) as archive:
            return [
                (info.filename, archive.read(info))
                for info in archive.infolist()
                if not info.is_dir() and info.file_size <= _MAX_MEMBER_BYTES
            ]
