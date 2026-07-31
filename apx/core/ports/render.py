"""The pièce-render port — the viewer's server-side rendering boundary (AD-4, AD-14, Story 3.5c-2).

The viewer must **render** a document, not dump its extracted text, and the hybrid choice (Julian,
2026-07-31) renders **office** formats **server-side**, inside the tenant boundary. This port lets
the core depend on "render these bytes to sanitised inline HTML" without importing mammoth/openpyxl/
nh3 — the adapter (``adapters/render_html``) does. Every renderer's HTML is **already sanitised**
when it is returned (the adapter's one construction site guarantees it); the edge serves it in a
JSON envelope and the SPA embeds it sandboxed (Story 3.5d).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RenderedDocument:
    """One pièce rendered to SANITISED inline HTML (Story 3.5c-2). ``format`` is ``"html"``.
    ``html`` is the sanitised markup — script-free, no active content, no remote resource — and is
    the ONLY field safe to embed as HTML. ``title`` is **untrusted** text metadata (the pièce
    filename): it is NOT sanitised, so a consumer MUST render it as a text node, never via innerHTML
    — the same contract as a filename. ``truncated`` is True when a render bound was hit, so the
    viewer can say so honestly (a bounded render never silently drops content)."""

    format: str
    title: str
    html: str
    truncated: bool = False


class PieceRenderer(Protocol):
    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        """Render the pièce's ORIGINAL ``data`` to sanitised inline HTML, dispatching by the
        ``filename``'s format. Returns ``None`` for a format this renderer does not handle (the edge
        then offers the original — FR-44 never yields an empty pane) and for **malformed** input (a
        broken .docx/.xlsx is a ``None``, offer the original — never a raise, never a 500). The
        returned ``html`` is **already sanitised** to a strict, script-free allow-list; no
        unsanitised markup ever escapes the adapter (a structural property, Story 3.5c-2)."""
        ...
