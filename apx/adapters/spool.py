"""Where decrypted pièce plaintext transits during rendering — the ENCRYPTED data volume, never the
system temp (a possibly-unencrypted mount), matching ``FilesystemOriginalStore``'s on-volume temp
(AD-31). Shared by the render adapters that must spool decrypted bytes to a path for a local tool:
the ``.msg`` worker (Story 3.5c-3) and the scanned-PDF rasteriser (Story 3.5c-4)."""

from __future__ import annotations

import os
import tempfile


def spool_dir() -> str:
    """The directory for a transient render spool: ``APX_DATA_PATH`` (the encrypted volume) when
    set, else the system temp (dev/test). Read per call, so a cached renderer honours the current
    environment (and a decrypted-plaintext spool never lands on an unencrypted mount in prod)."""
    return os.environ.get("APX_DATA_PATH", "").strip() or tempfile.gettempdir()
