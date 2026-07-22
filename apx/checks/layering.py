"""The layering check — the one structural property story 1.1 ships.

Property enforced: **the core imports no adapter** (``apx.core`` must not import
``apx.adapters``). Verb: *enforced as a structural property* (AD-33) — a static
import-graph check decides it, never a runtime test. The finer contracts of the
paradigm (domain imports nothing outside itself; app imports only Domain+Ports;
no adapter imports another adapter — AD-4) are tightened in story 1.12; 1.1 ships
only the core→adapter rule, green on the empty tree.

Implementation: import-linter (`lint-imports`), configured by the
``[tool.importlinter]`` block in ``pyproject.toml``. This module runs it as a
subprocess and propagates its exit code so the harness (``python -m apx.checks``)
fails the build on any violation.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ad: str
    ok: bool
    detail: str


def run(config: str | Path | None = None) -> CheckResult:
    """Run the core→adapter layering contract via import-linter.

    Enforces AD-4. Returns a CheckResult; ``ok`` is False on any contract
    violation or on an import-linter error. ``config`` overrides the config file
    (the failure-path self-test in tests/ points it at a violating fixture).
    """
    name = "core imports no adapter"
    exe = shutil.which("lint-imports")
    if exe is None:
        return CheckResult(
            name=name,
            ad="AD-4",
            ok=False,
            detail="lint-imports not found on PATH — run `uv sync --group dev`.",
        )
    cmd = [exe]
    if config is not None:
        cmd += ["--config", str(config)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    ok = proc.returncode == 0
    detail = (proc.stdout + proc.stderr).strip()
    return CheckResult(name=name, ad="AD-4", ok=ok, detail=detail)
