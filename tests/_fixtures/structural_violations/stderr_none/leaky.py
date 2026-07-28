"""Structural-violation fixture (Story 2.3, AD-28): an extraction-adapter-looking module that
sets ``stderr=None`` on a subprocess call, inheriting the parent's stderr — exactly where a
parser's document fragments would leak into a log or the terminal. ``no_stderr_none_in_extraction``
must fire on it. AST-scanned, never imported."""

from __future__ import annotations

import subprocess


def leaky_call() -> None:
    subprocess.run(["cat", "doc.msg"], stdout=subprocess.PIPE, stderr=None, check=False)
