"""The perf-ceiling gate (Story 2.13, AC4 / NFR-2): no latency / throughput / wall-clock CEILING is
declared in the product runtime while the timed 5 000-pièce run is unmeasured — so no performance
number is quoted before it is measured (NFR-2: *"none may be invented"*). The moment a real figure
is recorded (``apx/timedrun/measurements.json``), a ceiling resting on it is permitted; a ceiling
that DERIVES from the measurement record is permitted even while pending.

Unlike the gold gate — which anchors on an IMPORT of a stable interface — a perf ceiling has no
interface to anchor on: it is an arbitrary constant someone adds. So detection is **best-effort by
name** (a performance dimension token + a bound token), and this is stated plainly. The real
substrate is the honest ``pending`` record + the requirement that any real ceiling be derived from
it; this structural check is the secondary net that catches an *invented* constant slipping in
before the measurement exists.

**Known best-effort limitations** (documented, not hidden): detection sees only MODULE-LEVEL const
names (not class attributes, dict/config-string keys, or values), so a ceiling hidden in those slips
through; and the "derived" exemption is granted to any module that merely IMPORTS the measurement
record, which a determined author could abuse without truly deriving from it. Both are acceptable
because the load-bearing guarantee is the honest ``pending`` record, not this name heuristic. Fails
closed on an unparseable file and on an unreadable measurement state; injectable ``roots``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

from apx.checks.gold_gate import _imported_modules
from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse
from apx.timedrun.record import any_measured

_APX_ROOT = Path(__file__).resolve().parent.parent

# Build-time / measurement tooling is not the product runtime — scan the runtime only. `timedrun` is
# excluded because it legitimately defines the falsification thresholds (MAX_HNSW_P95_MS, …), which
# look exactly like the ceilings this gate forbids; it is measurement tooling, not a quoted target.
_RUNTIME_EXCLUDE = frozenset({"checks", "fitness", "timedrun", "__pycache__"})

# A perf ceiling names a performance DIMENSION and a BOUND sense (best-effort; no anchor to import).
# Matched on whole word TOKENS (so "sla" ⊄ "translation"), with a few multiword dimensions matched
# as phrases. `sla`/`deadline` are ceilings on their own (a latency bound); every other dimension
# needs a bound token too. This is a secondary net — the honest `pending` record is the substrate.
_DIMENSION = frozenset({"latency", "latence", "throughput", "p95", "p99", "qps", "rps"})
_DIMENSION_PHRASES = ("wall_clock", "wallclock", "docs_per_sec", "response_time", "responsetime")
_BOUND = frozenset({"max", "min", "ceiling", "limit", "budget", "target",
                    "ms", "s", "sec", "secs", "seconds"})
_CEILING_WORD = frozenset({"sla", "deadline"})
# A recorded figure, NOT an invented ceiling — NFR-2 permits recording a measured value.
_MEASUREMENT_WORD = frozenset({"measured", "observed", "actual", "sampled", "recorded", "baseline"})


def _name_tokens(name: str) -> set[str]:
    """Lower-case word tokens of a constant name, split on underscores and camelCase boundaries."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return {t for t in spaced.lower().split("_") if t}


def _is_ceiling_name(name: str) -> bool:
    """True when a name asserts a perf ceiling: a self-sufficient token (``sla``/``deadline``), or a
    perf dimension (token or phrase) paired with a bound sense. A bare ``TIMEOUT`` (no dimension), a
    ``TRANSLATION_KEYS`` (``sla`` is only a substring, not a token), or a ``MEASURED_LATENCY_MS`` (a
    recorded figure NFR-2 permits) does not match."""
    low = name.lower()
    tokens = _name_tokens(name)
    if tokens & _MEASUREMENT_WORD:
        return False
    if tokens & _CEILING_WORD:
        return True
    has_dimension = bool(tokens & _DIMENSION) or any(p in low for p in _DIMENSION_PHRASES)
    return has_dimension and bool(tokens & _BOUND)


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Tuple | ast.List):
        return [n for elt in target.elts for n in _target_names(elt)]
    return []


def _module_level_names(tree: ast.Module) -> list[str]:
    """Names bound by a MODULE-LEVEL assignment (a constant / config) — not locals inside a
    function, which are transient values, never a quoted target."""
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names.extend(_target_names(target))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def _references_measurement(tree: ast.Module) -> bool:
    """The module imports the measurement record — so any ceiling it declares is DERIVED from it,
    not invented (permitted, NFR-2)."""
    mods = _imported_modules(tree)
    return any(m == "apx.timedrun" or m.startswith("apx.timedrun.") for m in mods)


def _bare_ceiling(tree: ast.Module) -> str | None:
    """A module-level perf-ceiling constant not derived from the measurement record, else None."""
    if _references_measurement(tree):
        return None
    for name in _module_level_names(tree):
        if _is_ceiling_name(name):
            return name
    return None


def _runtime_trees() -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in sorted(_APX_ROOT.rglob("*.py")):
        if set(path.parts) & _RUNTIME_EXCLUDE:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def no_perf_ceiling_before_measurement(
    roots: Iterable[Path] | None = None, *, measured: bool | None = None
) -> CheckResult:
    """No latency / throughput / wall-clock ceiling is asserted in the runtime while the timed run
    is unmeasured (NFR-2). Vacuous until such a declaration exists; fires the moment an *invented*
    one appears with no recorded measurement; a ceiling derived from the record is permitted.
    ``measured`` defaults to the recorded state in ``measurements.json`` (``False`` today)."""
    name, ad = "no perf ceiling before the timed run is measured", "AD-32"
    trees, unparseable = _runtime_trees() if roots is None else _load_trees(list(roots))
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    if measured is None:
        try:
            has_measurement = any_measured()
        except (OSError, ValueError, KeyError) as exc:   # unreadable/corrupt measurements.json
            return CheckResult(
                name, ad, False,
                f"cannot read the measurement state (failing closed): {type(exc).__name__}")
    else:
        has_measurement = measured
    if has_measurement:
        return CheckResult(
            name, ad, True,
            "a timed-run measurement is recorded — a ceiling resting on it is permitted (NFR-2)")
    offenders = sorted(
        f"{path.name}:{nm}" for path, tree in trees if (nm := _bare_ceiling(tree)) is not None
    )
    if offenders:
        return CheckResult(
            name, ad, False,
            f"perf ceiling(s) declared with no timed-run measurement: {', '.join(offenders)} — "
            "NFR-2 forbids an invented target; derive it from the measurement record (pending)")
    return CheckResult(
        name, ad, True,
        f"vacuous: no perf ceiling declared while the timed run is pending ({len(trees)} file(s))")
