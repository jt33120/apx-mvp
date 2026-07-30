"""Filesystem-backed retained-original store (Story 3.5a). Implements the ``OriginalStore`` port
over the tenant data volume: content-addressed, tenant-partitioned, application-encrypted at rest."""

from apx.adapters.originals_fs.store import FilesystemOriginalStore

__all__ = ["FilesystemOriginalStore"]
