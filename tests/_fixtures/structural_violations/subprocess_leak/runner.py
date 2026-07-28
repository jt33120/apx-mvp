"""Structural-violation fixture (Story 2.3, AD-28): a runtime-looking module OUTSIDE
adapters/extraction that reaches ``subprocess``. ``no_subprocess_call_outside_extraction`` must
fire on it — extraction engines run out-of-process only under adapters/extraction, so every exec
boundary is one audited place. AST-scanned, never imported."""

from __future__ import annotations

import subprocess


def run_something() -> int:
    return subprocess.run(["true"], capture_output=True, check=False).returncode
