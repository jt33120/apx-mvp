"""OQ-4's five answers, made structural (Story 5.2, FR-22 / FR-23 / FR-38 / FR-56).

Story 5.2 answers the five difficulties a naive prevalence estimator gets wrong. An answer written
only in a story file is a paragraph nobody re-reads; FR-56 is explicit that *a property with no
check is not a property*. So each of the five carries exactly one check here, and reversing an
answer fails the build rather than passing review.

1. **The unit is the family, and the *pièce* figure is a worst case** —
   :func:`piece_figure_is_a_worst_case`.
2. **The census crossover: two registers, disjoint** — :func:`a_census_states_no_bound`.
3. **Repeated sampling: one run per bound, chosen by recency** —
   :func:`one_run_one_bound_chosen_by_recency`.
4. **Population freezing: the numbers come from the freeze** —
   :func:`the_bound_is_computed_from_the_freeze`.
5. **The projection at an unsampled position stays out of the bound** —
   :func:`the_bound_consumes_no_model_number`.

Every check reads SOURCE and fails closed on anything it cannot parse or cannot find: a guard
defeated by a rename is a habit, not a property (the Story 5.1 review's lesson).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

from apx.checks.forward_looking import _CONFIDENCE_FIELDS, _MODEL_SUBJECTS, _subject_name
from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_DOMAIN = _APX_ROOT / "core" / "domain"
_ESTIMATOR = _DOMAIN / "confidence.py"       # where prevalence_upper_bound is DEFINED
_SAMPLING = _DOMAIN / "sampling.py"          # the one module allowed to call it
_STORE = _APX_ROOT / "adapters" / "store_postgres" / "store.py"
# not product runtime: the harness scans itself, the fitness suite is build tooling.
_EXCLUDE_DIRS = frozenset({"checks", "fitness", "__pycache__"})


def _dotted(node: ast.expr) -> str:
    """``a.b.c`` for a Name/Attribute chain, ``""`` for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head else node.attr
    return ""


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _fail_closed(name: str, ad: str, why: str) -> CheckResult:
    return CheckResult(name, ad, False, f"{why} (failing closed, cannot verify)")


# ── input 1: the pièce figure is a WORST CASE, never a rescale ───────────────────────────────────

_PIECE_FIGURE = "count_upper_pieces"
_WORST_CASE_FN = "pieces_upper_bound"


def _allowed_piece_source(value: ast.expr) -> bool:
    """Where a ``count_upper_pieces=`` may come from: the one worst-case function, a pass-through
    (a name or an attribute), an explicit ``None`` (*not computable*), or a conditional over those.

    The conditional matters — ``estimate.count_upper_pieces if estimate else None`` is how a
    surface renders a run that has produced nothing yet, and it carries no arithmetic. Anything
    that COMPUTES a figure here is a second derivation; if it computes it by rescaling, the other
    leg names the rescale as well."""
    if _is_call_to(value, _WORST_CASE_FN) or isinstance(value, ast.Name | ast.Attribute):
        return True
    if isinstance(value, ast.Constant) and value.value is None:
        return True
    if isinstance(value, ast.IfExp):
        return _allowed_piece_source(value.body) and _allowed_piece_source(value.orelse)
    return False


def _is_a_rescale(node: ast.AST) -> str | None:
    """A prevalence used as a FACTOR — the forbidden conversion, named.

    The first draft of this required the other operand to be *pièce*-shaped, and the review found
    the evasion in one line: ``total = run.population_pieces`` then ``prevalence_upper * total``
    reads as neither operand naming a *pièce*, and the rescale ships with the gate green. Any
    denylist keyed on BOTH operands is defeated by renaming one of them.

    So the rule is one-sided and absolute: **a prevalence is a ratio you state, never a factor you
    multiply.** There is no legitimate multiplication of one anywhere in this product — the honest
    *pièce* figure comes from summing the D largest frozen family sizes, which is an addition — so
    the false-positive cost is zero and the evasion surface is one name instead of two."""
    if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult)):
        return None
    left, right = _dotted(node.left).lower(), _dotted(node.right).lower()
    for side in (left, right):
        if any(p in side for p in _FAVOURABILITY):
            return f"{left or '…'} * {right or '…'}"
    return None


# The web surface is TypeScript, so the Python AST cannot reach it — and it holds both operands and
# already renders the numbers a lawyer reads. A source-TEXT leg is weaker than an AST leg and is
# labelled as one; a leg that admits its own strength is worth more than a success message that
# claims a coverage it never had ("no prevalence is multiplied ANYWHERE" was false while apx/web was
# invisible — the review's finding, and the reason this exists).
_WEB_ROOT = _APX_ROOT / "web" / "src"
_WEB_SUFFIXES = (".ts", ".tsx")
_COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
_TS_PREVALENCE = re.compile(r"\w*(?:prevalence|count_upper)\w*", re.IGNORECASE)
# a `*` that is not `**`, not `*/`, and not immediately followed by a bare number
# One lookahead over `\s*\d`, NOT `\s*(?!\d)`: the latter backtracks the whitespace to zero and
# then happily matches the space, so `* 100` would be flagged as non-numeric. Found by watching
# this leg fire on the real client's percent rendering.
_TS_NON_NUMERIC_MULT = re.compile(r"(?<!\*)\*(?!\*)(?!\s*\d)")


def _web_rescales(root: Path) -> list[str]:
    """Lines in the client that multiply something named for a prevalence by something that is not
    a plain number.

    Two deliberate narrowings, both stated rather than accidental:

    - **comments are stripped first.** A JSDoc block is made of ``*`` and every one would be a
      false positive; a check that cries wolf is a check somebody deletes.
    - **``× <number>`` is exempt.** ``prevalence * 100`` is how a percentage is SPELLED in
      TypeScript, where Python writes ``:.1%`` — it is rendering, not rescaling. Multiplying a
      prevalence by anything with a *name*, however, is the forbidden conversion, and the
      parenthesised form ``(x ?? 0) * bound.piece_count`` is caught with it."""
    hits: list[str] = []
    if not root.is_dir():
        return hits
    for path in sorted(root.rglob("*")):
        if path.suffix not in _WEB_SUFFIXES or not path.is_file():
            continue
        try:
            source = _COMMENTS.sub(" ", path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            hits.append(f"{path.name}: unreadable (failing closed, cannot verify)")
            continue
        for number, line in enumerate(source.splitlines(), start=1):
            if _TS_PREVALENCE.search(line) and _TS_NON_NUMERIC_MULT.search(line):
                hits.append(f"web/{path.name}:{number} {line.strip()[:90]}")
    return hits


def piece_figure_is_a_worst_case(targets: Iterable[Path] | None = None) -> CheckResult:
    """The *pièce*-level figure is the sum of the largest frozen families, never a rescale of a
    family prevalence onto a *pièce* denominator (Story 5.2, OQ-4 input 1 / FR-38).

    The bound is computed over the unit that was drawn — near-duplicate families. The lawyer counts
    her pile in *pièces*, and the tempting conversion is ``prevalence_upper × population_pieces``.
    That product assumes the relevant families are of AVERAGE size, and where the few large thread
    families are the relevant ones it **understates** — in the flattering direction, the one
    direction a number said to a judge may never be biased in. The honest conversion is the worst
    case the same confidence already covers: if at most D families are relevant, at most the D
    LARGEST are.

    Three legs. Every ``count_upper_pieces=`` is produced by a call to ``pieces_upper_bound`` (or is
    a pass-through/absent); no Python expression in the product runtime uses a prevalence as a
    factor; and neither does the **TypeScript client**, which the AST cannot see and which holds
    both operands one line under the sentence."""
    name, ad = "the pièce figure is a worst case", "AD-19"
    roots = list(targets) if targets is not None else [_APX_ROOT]
    web_hits = _web_rescales(_WEB_ROOT) if targets is None else []
    offenders: list[str] = []
    unparseable: list[str] = []
    scanned = 0
    for path in _iter_py(roots):
        if set(path.parts) & _EXCLUDE_DIRS and targets is None:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        scanned += 1
        for node in ast.walk(tree):
            rescale = _is_a_rescale(node)
            if rescale is not None:
                offenders.append(
                    f"{path.name}:{node.lineno} uses a prevalence as a factor ({rescale}) — "
                    "rescaling a family prevalence onto a pièce denominator understates whenever "
                    "the largest families are the relevant ones, which is the flattering direction")
            if isinstance(node, ast.keyword) and node.arg == _PIECE_FIGURE:
                if not _allowed_piece_source(node.value):
                    offenders.append(
                        f"{path.name}:{node.lineno} sets {_PIECE_FIGURE} from something other than "
                        f"{_WORST_CASE_FN}(...) — the worst case has one derivation (AD-37)")
    if unparseable:
        return _fail_closed(name, ad, f"cannot parse {unparseable}")
    offenders.extend(
        f"{hit} — the client multiplies a prevalence (source-text leg: the AST cannot read "
        "TypeScript, and this is the surface the number is actually read from)"
        for hit in web_hits)
    if offenders:
        return CheckResult(name, ad, False, "; ".join(offenders))
    return CheckResult(
        name, ad, True,
        f"{scanned} python modules (AST) and the TypeScript client (source text) scanned; the "
        f"pièce figure is only ever {_WORST_CASE_FN}(...), and no prevalence is used as a factor")


# ── input 2: a census states an exact count, and no bound at all ─────────────────────────────────

_CENSUS_FN = "census_statement_fr"
_ESTIMATE_FN = "estimate_for_run"
_BOUND_FIELDS = ("prevalence_upper", "count_upper_families", "count_upper_pieces")
_CENSUS_FIELDS = ("relevant_pieces",)


def _without_docstring(fn: ast.FunctionDef) -> list[ast.stmt]:
    """The function's statements minus its docstring.

    The docstring is skipped — it is where the rule is explained, and the explanation necessarily
    quotes the forbidden sentence. A check that fired on its own rationale would be deleted within
    the week, which is how a structural property quietly stops running."""
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and (
            isinstance(body[0].value.value, str)):
        return body[1:]
    return list(body)


def _percent_reachable(tree: ast.Module, fn: ast.FunctionDef) -> tuple[int, str] | None:
    """``(line, where)`` of the first percent sign the sentence can reach, or ``None``.

    The first draft looked only inside ``census_statement_fr``'s own body, and the review found two
    ways past it in the same minute: move the percentage into a one-line helper, or hoist it into a
    module constant. Both leave the census sentence carrying a prevalence with the gate green —
    which is the failure this check exists for, not a variation on it.

    So the reachable set is: the function's own statements, the bodies of the module-level functions
    it CALLS (one hop — a two-hop helper chain to smuggle a percent sign into a court sentence is
    not a thing that happens by accident), and any module-level string constant it names."""
    local_functions = {
        n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    constants = {
        target.id: node.value
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant)}

    reachable: list[tuple[str, list[ast.stmt]]] = [(fn.name, _without_docstring(fn))]
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            called = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else "")
            helper = local_functions.get(called)
            if helper is not None and helper is not fn:
                reachable.append((f"{fn.name} -> {called}()", _without_docstring(helper)))
        if isinstance(node, ast.Name) and node.id in constants:
            const = constants[node.id]
            if isinstance(const.value, str) and "%" in const.value:
                return const.lineno, f"the module constant {node.id}"
    for where, body in reachable:
        line = _percent_in_statements(body)
        if line is not None:
            return line, where
    return None


def _percent_in_statements(body: list[ast.stmt]) -> int | None:
    """The line of the first percent sign in a string these statements build, or None."""
    for node in [n for stmt in body for n in ast.walk(stmt)]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "%" in node.value:
            return node.lineno
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            for spec in ast.walk(node.format_spec):
                if isinstance(spec, ast.Constant) and isinstance(spec.value, str) and (
                        "%" in spec.value):
                    return node.lineno
    return None


def a_census_states_no_bound(domain_path: Path | None = None) -> CheckResult:
    """A census and a sample speak in disjoint registers (Story 5.2, OQ-4 input 2 / FR-22).

    A census is not a tighter bound; it is a categorically different statement — nothing is
    estimated, everything was read. FR-22 names the failure in as many words: producing *"60 sampled
    from the 60 discarded; at most 4.8 % is relevant"* over a fully reviewed population is a false
    statement of residual risk, said out loud, to a judge.

    Two legs, both on ``core/domain/sampling.py``: ``census_statement_fr`` builds no percentage at
    all, and ``estimate_for_run``'s census branch constructs an ``Estimate`` carrying **none** of
    the bound fields while its bound branch carries none of the census fields. The crossover is
    ``n == N`` exactly and no third register exists near it."""
    name, ad = "a census states no bound", "AD-19"
    path = domain_path if domain_path is not None else _SAMPLING
    tree = _parse(path)
    if tree is None:
        return _fail_closed(name, ad, f"cannot parse {path.name}")
    census = _function(tree, _CENSUS_FN)
    estimate = _function(tree, _ESTIMATE_FN)
    if census is None or estimate is None:
        return _fail_closed(
            name, ad, f"{_CENSUS_FN} or {_ESTIMATE_FN} is not in {path.name} — renamed?")

    problems: list[str] = []
    percent = _percent_reachable(tree, census)
    if percent is not None:
        line, where = percent
        problems.append(
            f"{_CENSUS_FN} can reach a percentage at line {line} (via {where}) — a census "
            "estimates nothing, so it never states a prevalence (FR-22)")

    seen: set[str] = set()
    for node in ast.walk(estimate):
        if not _is_call_to(node, "Estimate"):
            continue
        assert isinstance(node, ast.Call)
        kind = _dotted(_keyword(node, "kind") or ast.Constant(None))
        keywords = {kw.arg for kw in node.keywords}
        if kind.endswith("KIND_CENSUS"):
            seen.add("census")
            leaked = sorted(keywords & set(_BOUND_FIELDS))
            if leaked:
                problems.append(
                    f"the census branch of {_ESTIMATE_FN} carries bound fields {leaked} — the two "
                    "registers are disjoint, or a census borrows a bound's shape")
        elif kind.endswith("KIND_BOUND"):
            seen.add("bound")
            leaked = sorted(keywords & set(_CENSUS_FIELDS))
            if leaked:
                problems.append(
                    f"the bound branch of {_ESTIMATE_FN} carries census fields {leaked} — a sample "
                    "never states an exact count over a population it did not read")
    if {"census", "bound"} - seen:
        return _fail_closed(
            name, ad, f"{_ESTIMATE_FN} no longer builds both registers ({sorted(seen)})")
    if problems:
        return CheckResult(name, ad, False, "; ".join(problems))
    return CheckResult(
        name, ad, True,
        "the census register carries an exact count and no percentage; the bound register carries "
        "no exact count — the crossover is n == N and there is nothing between them")


# ── input 3: one run per bound, and the current one chosen by recency ────────────────────────────

_BOUND_FN = "prevalence_upper_bound"
_CURRENT_BOUND_FN = "read_current_bound"
_ORDERING_CALLS = frozenset({
    "order_by", "sorted", "sort", "min", "max", "nlargest", "nsmallest"})


def _reaches(tree: ast.Module, symbol: str) -> bool:
    """Whether a module can reach ``symbol`` under ANY of the four spellings Python offers.

    The first draft matched ``ast.Name`` alone, and the review defeated it twice over: an
    ``import … as pub`` yields an ``ast.alias`` whose name is a plain string, and a qualified
    ``confidence.prevalence_upper_bound(…)`` yields an ``ast.Attribute`` whose attr is a plain
    string. Neither is an ``ast.Name``, so a second birthplace for a bound — the thing that makes
    pooling two runs possible — was one import style away with the gate green.

    A guard one rename from silence is a habit, not a property (the Story 5.1 lesson, and this is
    the second story it has had to be applied in)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            return True
        if isinstance(node, ast.Attribute) and node.attr == symbol:
            return True
        if isinstance(node, ast.Import | ast.ImportFrom) and any(
                alias.name == symbol or alias.name.endswith(f".{symbol}")
                for alias in node.names):
            return True
    return False
_FAVOURABILITY = ("prevalence", "count_upper")


def one_run_one_bound_chosen_by_recency(
    roots: Iterable[Path] | None = None, store_path: Path | None = None
) -> CheckResult:
    """A bound rests on exactly one run, and the run on show is the most RECENT one — never the one
    with the nicest number (Story 5.2, OQ-4 input 3 / FR-22).

    Two runs over one population is a multiple-comparisons problem that a record showing both does
    not repair, *because the sentence travels alone*. Pooling them is the textbook trap; showing the
    best of them is the feature request someone makes in good faith. Neither is possible here.

    Leg one: exactly one module in the product runtime calls the estimator — ``core/domain/
    sampling.py`` — so there is one place a bound can be born and no second path that could combine
    two draws. Leg two: ``read_current_bound`` never orders, minimises or maximises over anything
    named for how favourable it is."""
    name, ad = "one run, one bound, chosen by recency", "AD-37"
    scan = list(roots) if roots is not None else [_APX_ROOT]
    callers: list[str] = []
    unparseable: list[str] = []
    owner, definer = _SAMPLING.resolve(), _ESTIMATOR.resolve()
    for path in _iter_py(scan):
        if set(path.parts) & _EXCLUDE_DIRS and roots is None:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        if path.resolve() == definer:
            continue  # where it is DEFINED
        if _reaches(tree, _BOUND_FN):
            callers.append(str(path.resolve()))
    if unparseable:
        return _fail_closed(name, ad, f"cannot parse {unparseable}")
    extra = sorted(c for c in callers if c != str(owner))
    if extra:
        return CheckResult(
            name, ad, False,
            f"{_BOUND_FN} is reached from {[Path(p).name for p in extra]} as well as "
            f"{owner.name} — a second birthplace for a bound is a second chance to pool two runs "
            "over one population, and the sentence travels alone (FR-22)")

    path = store_path if store_path is not None else _STORE
    tree = _parse(path)
    if tree is None:
        return _fail_closed(name, ad, f"cannot parse {path.name}")
    reader = _function(tree, _CURRENT_BOUND_FN)
    if reader is None:
        return _fail_closed(name, ad, f"{_CURRENT_BOUND_FN} is not in {path.name} — renamed?")
    # A local assigned FROM a favourability column is a favourability column wearing a new name:
    # `col = SamplingRun.prevalence_upper` then `.order_by(col)` orders by how flattering the
    # number is while mentioning nothing flattering at the ordering site. Collect the aliases first
    # so the ordering scan sees through them.
    aliases: set[str] = set()
    for node in ast.walk(reader):
        if not isinstance(node, ast.Assign):
            continue
        source = " ".join(
            _dotted(inner).lower() for inner in ast.walk(node.value)
            if isinstance(inner, ast.Name | ast.Attribute))
        if any(f in source for f in _FAVOURABILITY):
            aliases.update(
                target.id.lower() for target in node.targets if isinstance(target, ast.Name))

    for node in ast.walk(reader):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else (
            func.id if isinstance(func, ast.Name) else "")
        if called not in _ORDERING_CALLS:
            continue
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            for inner in ast.walk(arg):
                dotted = _dotted(inner).lower() if isinstance(
                    inner, ast.Name | ast.Attribute) else ""
                if not dotted:
                    continue
                if any(f in dotted for f in _FAVOURABILITY) or dotted in aliases:
                    return CheckResult(
                        name, ad, False,
                        f"{_CURRENT_BOUND_FN} orders by '{dotted}' at line {node.lineno} — the "
                        "matter's current bound is the most RECENT run, never the most flattering "
                        "one; sampling until the number is nice is what this forbids (FR-22)")
    return CheckResult(
        name, ad, True,
        f"{_BOUND_FN} is reached from {owner.name} alone, and {_CURRENT_BOUND_FN} orders by "
        "recency — runs are never pooled and never ranked by how favourable they are")


# ── input 4: the numbers come from the FREEZE, not from the live set ─────────────────────────────

_COMPLETE_FN = "complete_sampling_run"
_RUN_BOUND_FN = "bound_for_run"
_LIVE_DERIVATIONS = ("_derived_discarded", "derive_triage_sets", "_run_population")


def the_bound_is_computed_from_the_freeze(store_path: Path | None = None) -> CheckResult:
    """A completed run's bound is computed from the population it FROZE, never from the discarded
    set as it stands at completion time (Story 5.2, OQ-4 input 4 / FR-22 / AD-23).

    Re-deriving the set here would compute a bound over whatever the *matter* looks like now and
    quote it with the authority of a draw made over what it looked like then — the same wrong
    referent as a stale artefact reading fresh, one layer deeper. For an invalidated run it would be
    a bound over a population that no longer exists at all.

    Two legs on ``complete_sampling_run``: the estimator's ``population`` and ``sample_size`` are
    read off the run row (an attribute access, not a call), and the function reaches none of the
    live derivations."""
    name, ad = "the bound is computed from the freeze", "AD-23"
    path = store_path if store_path is not None else _STORE
    tree = _parse(path)
    if tree is None:
        return _fail_closed(name, ad, f"cannot parse {path.name}")
    fn = _function(tree, _COMPLETE_FN)
    if fn is None:
        return _fail_closed(name, ad, f"{_COMPLETE_FN} is not in {path.name} — renamed?")

    for node in ast.walk(fn):
        for live in _LIVE_DERIVATIONS:
            if _is_call_to(node, live):
                return CheckResult(
                    name, ad, False,
                    f"{_COMPLETE_FN} calls {live}(...) at line {node.lineno} — the bound would be "
                    "computed over the discarded set as it is NOW and quoted with the authority of "
                    "the draw made over what it was THEN (FR-22)")
    calls = [n for n in ast.walk(fn) if _is_call_to(n, _RUN_BOUND_FN)]
    if len(calls) != 1:
        return _fail_closed(
            name, ad, f"{_COMPLETE_FN} calls {_RUN_BOUND_FN} {len(calls)} times, expected once")
    call = calls[0]
    assert isinstance(call, ast.Call)
    for field in ("population", "sample_size"):
        value = _keyword(call, field)
        if value is None:
            return _fail_closed(name, ad, f"{_RUN_BOUND_FN} has no '{field}=' — signature changed?")
        if not isinstance(value, ast.Attribute):
            return CheckResult(
                name, ad, False,
                f"{_RUN_BOUND_FN}'s '{field}=' is not read off the frozen run row (it is "
                f"{type(value).__name__}) — the estimator's inputs are the freeze (FR-22)")
    return CheckResult(
        name, ad, True,
        f"{_COMPLETE_FN} takes the estimator's population and sample from the frozen run row and "
        "reaches no live derivation of the discarded set")


# ── input 5: the bound consumes no model-reported number ─────────────────────────────────────────

_PROJECTION_MODULE = "line_projection"


def _projection_site(tree: ast.Module) -> tuple[int, str] | None:
    """``(line, how)`` of the first reach into the FR-19 projection module, or ``None``.

    All four spellings, because the review walked past the first draft using two of them:
    ``import apx.core.domain.line_projection as lp`` and ``from apx.core.domain import
    line_projection as lp`` both produce an ``ast.alias`` whose name is a plain string, invisible
    to a leg that matches only ``ImportFrom.module`` and a bare ``ast.Name``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
                node.module == _PROJECTION_MODULE
                or node.module.endswith(f".{_PROJECTION_MODULE}")):
            return node.lineno, f"from {node.module} import …"
        if isinstance(node, ast.Import | ast.ImportFrom):
            for alias in node.names:
                if alias.name == _PROJECTION_MODULE or alias.name.endswith(
                        f".{_PROJECTION_MODULE}"):
                    bound = alias.asname or alias.name
                    return node.lineno, f"imported as {bound}"
        if isinstance(node, ast.Name | ast.Attribute) and _PROJECTION_MODULE in _dotted(node):
            return node.lineno, f"references {_dotted(node)}"
    return None


def the_bound_consumes_no_model_number(targets: Iterable[Path] | None = None) -> CheckResult:
    """The *confidence bound* consumes no model-reported number and does not reach the FR-19
    projection (Story 5.2, OQ-4 input 5 / FR-42 / §0.2).

    OQ-4's fifth difficulty asks whether the projection at an unsampled position can be calibrated.
    Story 5.2 answers **no** — the only labelled corpus in the plan is TREC Legal Track, English
    e-discovery, a different task and a different relevance definition from *ordonnance 145 CPC*
    review — so no calibrated projection ships and the priced move states counts (Story 4.9).

    Story 4.9's ``line-projection-not-a-bound`` already forbids the projection from reaching the
    estimator. This is the other direction, and the direction §0.2 is actually about: *"a made-up
    number laundered through a statistical sentence"*. The estimator modules import nothing from
    ``line_projection`` and read no confidence field off a model response."""
    name, ad = "the bound consumes no model number", "AD-19"
    paths = list(targets) if targets is not None else [_ESTIMATOR, _SAMPLING]
    unparseable: list[str] = []
    for path in paths:
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        site = _projection_site(tree)
        if site is not None:
            line, how = site
            return CheckResult(
                name, ad, False,
                f"{path.name}:{line} reaches {_PROJECTION_MODULE} ({how}) — a sampling bound and a "
                "projection at an unsampled position are different kinds of statement and are "
                "never computed by the same code (§0.2)")
        for node in ast.walk(tree):
            subject = field = None
            if isinstance(node, ast.Attribute) and node.attr in _CONFIDENCE_FIELDS:
                subject, field = _subject_name(node.value), node.attr
            elif (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                  and node.slice.value in _CONFIDENCE_FIELDS):
                subject, field = _subject_name(node.value), node.slice.value
            if subject in _MODEL_SUBJECTS and field is not None:
                return CheckResult(
                    name, ad, False,
                    f"{path.name}:{node.lineno} reads '{field}' off a model response ({subject}) — "
                    "a made-up number laundered through a statistical sentence is the §0.2 failure "
                    "one layer down (FR-42)")
    if unparseable:
        return _fail_closed(name, ad, f"cannot parse {unparseable}")
    return CheckResult(
        name, ad, True,
        f"{len(paths)} estimator module(s) reach neither the FR-19 projection nor any "
        "model-reported number")


def run() -> list[CheckResult]:
    return [
        piece_figure_is_a_worst_case(),
        a_census_states_no_bound(),
        one_run_one_bound_chosen_by_recency(),
        the_bound_is_computed_from_the_freeze(),
        the_bound_consumes_no_model_number(),
    ]
