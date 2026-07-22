"""The layering check — the one structural property story 1.1 ships.

Property enforced: **the core imports no adapter** (``apx.core`` must not import
``apx.adapters``). Verb: *enforced as a structural property* (AD-33) — a static
import-graph check decides it, never a runtime test. The finer contracts of the
paradigm (domain imports nothing outside itself; app imports only Domain+Ports;
no adapter imports another adapter — AD-4) are tightened in story 1.12; 1.1 ships
only the core→adapter rule, green on the empty tree.

Implementation: import-linter (`lint-imports`), configured by the
``[tool.importlinter]`` block in ``pyproject.toml``. This module runs it as a
subprocess and reports failure on any violation.

Two integrity properties, both learned from the 1.1 code review:

- **cwd-independent.** import-linter reads its config from the current directory.
  The harness locates the project root (the ``pyproject.toml`` carrying the
  ``[tool.importlinter]`` block) and runs there, so ``python -m apx.checks`` gives
  the same verdict from any directory rather than crying wolf off-root.
- **A dropped contract is a failure, not a pass.** import-linter exits 0 on
  "0 kept, 0 broken", so a plain exit-code check would go green if the contract
  were ever deleted — defeating "a cut cannot drop this" (AD-3/AD-45). This check
  parses the contract tally and fails unless at least one contract actually ran.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# The tally line import-linter prints, e.g. "Contracts: 1 kept, 0 broken."
_TALLY = re.compile(r"Contracts:\s*(\d+)\s+kept,\s*(\d+)\s+broken", re.IGNORECASE)


def _project_root() -> Path | None:
    """The nearest ancestor holding a pyproject.toml with an importlinter block."""
    for parent in Path(__file__).resolve().parents:
        pp = parent / "pyproject.toml"
        if pp.is_file() and "tool.importlinter" in pp.read_text(encoding="utf-8"):
            return parent
    return None


@dataclass(frozen=True)
class CheckResult:
    name: str
    ad: str
    ok: bool
    detail: str


def run() -> CheckResult:
    """Run the core→adapter layering contract via import-linter (AD-4).

    ``ok`` is True only when import-linter exits 0 **and** at least one contract
    was actually evaluated. A missing tool, a config-read error, a non-zero exit,
    or a zero-contract run all yield ``ok=False``.
    """
    name = "core imports no adapter"
    exe = shutil.which("lint-imports")
    if exe is None:
        return CheckResult(
            name, "AD-4", False, "lint-imports not found; run `uv sync --group dev`."
        )

    root = _project_root()
    if root is None:
        return CheckResult(name, "AD-4", False, "no pyproject.toml with [tool.importlinter] found.")

    proc = subprocess.run([exe], cwd=root, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()

    tally = _TALLY.search(output)
    if tally is None:
        # No tally line means import-linter did not evaluate contracts (e.g. a
        # config-read error). That is a failure, not a pass — the guard did not run.
        return CheckResult(name, "AD-4", False, f"no contract was evaluated:\n{output}")

    kept, broken = int(tally.group(1)), int(tally.group(2))
    if kept + broken == 0:
        # A dropped contract must not pass green (AD-3/AD-45).
        return CheckResult(
            name, "AD-4", False, f"zero contracts collected — guard dropped:\n{output}"
        )

    ok = proc.returncode == 0 and broken == 0
    return CheckResult(name, "AD-4", ok, output)
