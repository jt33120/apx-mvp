"""The *ranking version*'s identity has ONE source, and it is the judge that ran (Story 7.3, AD-23).

A *ranking version* is an immutable fingerprint over how an order was produced, printed on the
header a lawyer reads and hashed into the value that decides whether two orders are "the same
ranking". Every value in it is therefore a permanent factual claim.

Two ways to make it a false one, and this check closes both.

**A second composer.** Until Story 7.3 there was no production caller at all, so every construction
site of :class:`RankingIdentityInputs` was a fixture full of plausible literals — a model name, an
endpoint, ``temperature=0.0``, ``sampling={"top_p": 1.0}``. That last one was pure invention: the
live judge sends no sampling parameter of any kind. A second composer growing anywhere is a second
set of literals, so there is one door — ``core/app/rank.identity_inputs`` — and nothing else in the
runtime may build the inputs.

**A second reading of the model.** ``model_provider`` / ``model_endpoint`` / ``model_name`` are
configuration-as-data (AD-24), and configuration records a *preference*. This deployment composes
the deterministic ``criteria`` judge whenever no LLM credential is present, and substitutes the
environment's endpoint and model whenever the tenant's value equals the schema default — so a
composer that read those keys beside the judge would stamp *mistral-small-latest @ api.mistral.ai*
onto an order decided entirely by a comma-splitting keyword matcher. The keys may be read where the
judge is BUILT (``apx/wiring.py``), because there they configure the thing that then answers for
itself; read anywhere else in the runtime they are a claim about a run, made by something that did
not watch it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _APX_ROOT, _fail_closed, _load_trees

#: the one door — the only runtime module that may construct the inputs
_COMPOSER = ("core", "app", "rank.py")
#: the one door onto the judge — the only runtime module that may READ the model keys
_JUDGE_DOOR = ("apx", "wiring.py")
#: where the keys are DECLARED (their schema and defaults). Declaring a key is not reading one.
_DECLARATION = ("core", "domain", "config.py")
#: the checks themselves are not the runtime — this module has to name the keys to guard them.
_CHECKS = ("apx", "checks")

_INPUTS = "RankingIdentityInputs"
_MODEL_KEYS = ("model_provider", "model_endpoint", "model_name")


def _under(path: Path, parts: tuple[str, ...]) -> bool:
    return path.parts[-len(parts):] == parts


def _config_reads(tree: ast.AST) -> set[tuple[str, int]]:
    """Every CALL that passes a model-identity config key as an argument — ``get_config(t, "…")``,
    ``get("…")``, ``default_of("…")``. Matching the call, never the bare literal: the identity's own
    dataclass has fields of those names and the config schema declares them, and a check that
    flagged either would be a check on a SHAPE that the next reviewer weakens."""
    found: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for arg in (*node.args, *(kw.value for kw in node.keywords)):
            if isinstance(arg, ast.Constant) and arg.value in _MODEL_KEYS:
                found.add((str(arg.value), node.lineno))
    return found


def the_ranking_identity_has_one_source(roots: Iterable[Path] | None = None) -> CheckResult:
    """One composer for the identity inputs, and the model half comes from the judge (AD-23)."""
    name, ad = "the ranking identity has one source", "AD-23"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    composers: list[str] = []
    readers: list[str] = []
    door_seen = False
    for path, tree in trees:
        is_composer = _under(path, _COMPOSER)
        door_seen = door_seen or is_composer
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == _INPUTS and not is_composer:
                composers.append(f"{path.name}:{node.lineno}")
        exempt = (_under(path, _JUDGE_DOOR) or _under(path, _DECLARATION)
                  or _CHECKS[-1] in path.parts)
        if not exempt:
            for key, line in sorted(_config_reads(tree)):
                readers.append(f"{path.name}:{line}::{key}")

    if not door_seen:
        return CheckResult(name, ad, False,
                           f"the composer {'/'.join(_COMPOSER)} is not in the tree — a check that "
                           "cannot find its own door is not passing (AD-23)")
    if composers:
        return CheckResult(name, ad, False,
                           f"{_INPUTS} is constructed outside {'/'.join(_COMPOSER)}: "
                           f"{sorted(composers)} — a second composer is a second set of literals "
                           "in an immutable fingerprint")
    if readers:
        return CheckResult(name, ad, False,
                           f"the model-identity config key(s) are read outside "
                           f"{'/'.join(_JUDGE_DOOR)}: {sorted(readers)} — configuration records a "
                           "preference, and this deployment silently composes a different judge")
    return CheckResult(
        name, ad, True,
        f"{_INPUTS} is built only in {'/'.join(_COMPOSER)}, and {list(_MODEL_KEYS)} are read only "
        f"where the judge is composed ({'/'.join(_JUDGE_DOOR)}), so the recorded model is the one "
        "that ran")
