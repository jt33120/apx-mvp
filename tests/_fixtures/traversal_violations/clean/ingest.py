"""A correct wiring: the submitted tree is enumerated through the one confined walk."""
from pathlib import Path

from apx.core.domain.traversal import walk_confined


def units(folder: Path) -> list[str]:
    return sorted(f.relative for f in walk_confined(folder).files)
