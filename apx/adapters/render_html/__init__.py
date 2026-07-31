"""The server-side HTML render adapters — office (Story 3.5c-2) and ``.msg`` (Story 3.5c-3)."""

from __future__ import annotations

from apx.adapters.render_html.composite import CompositePieceRenderer
from apx.adapters.render_html.msg import MsgRenderer
from apx.adapters.render_html.renderer import HtmlPieceRenderer

__all__ = ["CompositePieceRenderer", "HtmlPieceRenderer", "MsgRenderer"]
