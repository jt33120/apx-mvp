"""Import-graph structural properties (AD-33), enforced by import-linter.

Two properties live here, both static import-graph checks — never runtime tests:

- **Layering (AD-4):** ``apx.core`` imports no ``apx.adapters``.
- **Egress deny-list (AD-45, AD-3):** no ``apx`` runtime module imports a
  hosted-provider SDK, and the core imports no hosted LLM SDK. This is where
  "only code travels" / "runs air-gapped" first becomes a build-failing property.

The contracts themselves are declared in ``pyproject.toml``'s
``[tool.importlinter]`` block. This module runs import-linter once and enforces a
**per-contract floor**: every contract in ``REQUIRED_CONTRACTS`` must be present
and KEPT, and none may be BROKEN. Deleting a required contract is therefore a
failure, not a silent pass — the lesson from the story 1.1 review, generalised
from one rule to the set.

**Known limitation (by design, not a gap to paper over).** This is a *static*
import-graph check: it catches ``import boto3`` and ``from google import cloud``
in source, but NOT a dynamic import (``importlib.import_module("boto3")``) whose
target is a runtime string. Static analysis cannot see a string. The egress guard
therefore prevents *code reaching for* a hosted SDK in source; the **network
isolation** (the offline boot here, and container ``--network none`` as the
pipeline grows) is what prevents *actual* egress at runtime. The two are
complementary — neither alone is complete, and neither is presented as if it were.
A determined insider can always exfiltrate; this guard raises the bar against the
casual or accidental hosted-SDK dependency, which is its real job.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Every contract that MUST exist and hold. A dropped one fails the build.
REQUIRED_CONTRACTS: frozenset[str] = frozenset(
    {
        "core imports no adapter (AD-4)",
        "apx imports no hosted SDK (AD-45)",
        "core imports no hosted LLM SDK (AD-27)",
    }
)

# import-linter prints one line per contract, e.g. "name (AD-4) KEPT" / "... BROKEN".
_RESULT = re.compile(r"^(?P<name>.+?)\s+(?P<verdict>KEPT|BROKEN)\s*$", re.MULTILINE)


def _project_root() -> Path | None:
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
    """Enforce the required import contracts (AD-4, AD-45, AD-27).

    ``ok`` is True only when every REQUIRED contract is present and KEPT and none
    is BROKEN. A missing tool, missing config, a missing required contract, or any
    broken contract yields ``ok=False``.
    """
    name = "import contracts (layering + egress)"
    exe = shutil.which("lint-imports")
    if exe is None:
        return CheckResult(
            name, "AD-4/45/27", False, "lint-imports not found; run `uv sync --group dev`."
        )
    root = _project_root()
    if root is None:
        return CheckResult(name, "AD-4/45/27", False, "no pyproject.toml with [tool.importlinter].")

    proc = subprocess.run([exe], cwd=root, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip()

    verdicts = {m.group("name").strip(): m.group("verdict") for m in _RESULT.finditer(output)}
    if not verdicts:
        return CheckResult(name, "AD-4/45/27", False, f"no contract was evaluated:\n{output}")

    missing = sorted(c for c in REQUIRED_CONTRACTS if c not in verdicts)
    broken = sorted(n for n, v in verdicts.items() if v == "BROKEN")
    problems = []
    if missing:
        problems.append(f"required contract(s) missing — guard dropped: {missing}")
    if broken:
        problems.append(f"broken contract(s): {broken}")

    ok = proc.returncode == 0 and not missing and not broken
    detail = output if ok else (" | ".join(problems) + "\n" + output)
    return CheckResult(name, "AD-4/45/27", ok, detail)
