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
_STATEMENT = _DOMAIN / "statement.py"        # Story 5.4 — where the WORDS moved
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

# Story 5.4 — the sentence functions MOVED to core/domain/statement.py, and this check followed
# them rather than being relaxed. It failed closed the moment they left sampling.py — which is what
# a fail-closed check is for: the alternative is a green build over a rule nobody is applying.
_CENSUS_FN = "_census_claim_fr"
# Story 5.3 — the counts-only sentence is under the same ban: an unproven estimator that stated a
# percentage would be the §0.2 failure with an apology attached.
_COUNTS_ONLY_FN = "_counts_only_claim_fr"
_ESTIMATE_FN = "estimate_for_run"
_BOUND_FIELDS = ("prevalence_upper", "count_upper_families", "count_upper_pieces")
_CENSUS_FIELDS = ("relevant_pieces",)
# Every register `estimate_for_run` must still build. Losing one is a fail-closed condition, not a
# silent pass: a branch that quietly disappears takes its disjointness assertion with it.
_REGISTERS = frozenset({"census", "bound", "counts_only"})


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


def a_census_states_no_bound(
    domain_path: Path | None = None, statement_path: Path | None = None
) -> CheckResult:
    """A census and a sample speak in disjoint registers (Story 5.2, OQ-4 input 2 / FR-22).

    A census is not a tighter bound; it is a categorically different statement — nothing is
    estimated, everything was read. FR-22 names the failure in as many words: producing *"60 sampled
    from the 60 discarded; at most 4.8 % is relevant"* over a fully reviewed population is a false
    statement of residual risk, said out loud, to a judge.

    Two legs. The **words** (``core/domain/statement.py`` since Story 5.4): the census and
    counts-only claims build no percentage at all. The **shape** (``core/domain/sampling.py``):
    ``estimate_for_run``'s census branch constructs an ``Estimate`` carrying **none** of the bound
    fields while its bound branch carries none of the census fields. The crossover is ``n == N``
    exactly and no third register exists near it.

    ``statement_path`` defaults to ``domain_path`` when only that is given, so a single-module
    fixture still exercises both legs against one synthetic file."""
    name, ad = "a census states no bound", "AD-19"
    path = domain_path if domain_path is not None else _SAMPLING
    words_path = statement_path if statement_path is not None else (
        domain_path if domain_path is not None else _STATEMENT)
    tree = _parse(path)
    words = tree if words_path == path else _parse(words_path)
    if tree is None:
        return _fail_closed(name, ad, f"cannot parse {path.name}")
    if words is None:
        return _fail_closed(name, ad, f"cannot parse {words_path.name}")
    census = _function(words, _CENSUS_FN)
    estimate = _function(tree, _ESTIMATE_FN)
    if census is None:
        return _fail_closed(
            name, ad, f"{_CENSUS_FN} is not in {words_path.name} — renamed?")
    if estimate is None:
        return _fail_closed(
            name, ad, f"{_ESTIMATE_FN} is not in {path.name} — renamed?")

    problems: list[str] = []
    for sentence_fn in (census, _function(words, _COUNTS_ONLY_FN)):
        if sentence_fn is None:
            return _fail_closed(
                name, ad, f"{_COUNTS_ONLY_FN} is not in {words_path.name} — renamed?")
        percent = _percent_reachable(words, sentence_fn)
        if percent is not None:
            line, where = percent
            problems.append(
                f"{sentence_fn.name} can reach a percentage at line {line} (via {where}) — it "
                "estimates nothing, so it never states a prevalence (FR-22/FR-23)")

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
        elif kind.endswith("KIND_COUNTS_ONLY"):
            # Story 5.3 — the register that can say no. An unproven estimator states what it
            # counted and NOTHING derived from it: no bound, no exact projection, no worst case.
            seen.add("counts_only")
            leaked = sorted(keywords & (set(_BOUND_FIELDS) | set(_CENSUS_FIELDS)))
            if leaked:
                problems.append(
                    f"the counts-only branch of {_ESTIMATE_FN} carries {leaked} — an unproven "
                    "estimator emits the counts it observed and nothing derived from them (FR-23)")
    if _REGISTERS - seen:
        return _fail_closed(
            name, ad,
            f"{_ESTIMATE_FN} no longer builds every register ({sorted(seen)}, expected "
            f"{sorted(_REGISTERS)})")
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


# ── Story 5.3: the word "proven" is un-writable without the proof running ────────────────────────

_PROVEN_FLAG = "ESTIMATOR_PROVEN"
_PROVEN_FN = "estimator_is_proven"
_HARNESS = _APX_ROOT / "eval" / "estimator_simulation.py"
_GATE_TEST = _APX_ROOT.parent / "tests" / "eval" / "test_estimator_simulation.py"
# what the harness must NAME, or it is not a gate with a target
_HARNESS_SYMBOLS = ("COVERAGE_TARGET", "MIN_TRIALS", "SCENARIOS", "run_all", "unsound")
# the FLOOR (coverage) and the CEILING (tightness) — the test must assert both
_FLOOR_MARKERS = ("family_coverage", "piece_coverage")
_CEILING_MARKERS = ("tightness_ceiling", "worst_prevalence_upper")
_DISABLERS = ("skip", "skipif", "xfail")


def _module_flag(tree: ast.Module, flag: str) -> bool | None:
    """The module-level boolean bound to ``flag``, or ``None`` when that is not what it is.

    CONFIRMED [HIGH] by the review: the first version walked the whole tree and returned the FIRST
    literal it met, so a ``ESTIMATOR_PROVEN = False`` nested inside any function shadowed the real
    module-level ``True`` — and Python binds the LAST module-level assignment, not the first, so a
    module assigning it twice was read wrongly in the other direction too.

    Now: **module level only**, **last assignment wins** (Python's own rule), and any non-literal or
    multi-target form yields ``None``, which the caller treats as fail-closed."""
    found: bool | None = None
    for node in tree.body:                      # top level ONLY — not ast.walk
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if not (isinstance(target, ast.Name) and target.id == flag):
            continue
        value = node.value
        found = value.value if (
            isinstance(value, ast.Constant) and isinstance(value.value, bool)) else None
    return found


def _reads_the_flag(tree: ast.Module, function: str, flag: str) -> bool:
    """Whether ``function`` actually returns the module flag rather than a hard-coded answer.

    CONFIRMED [HIGH] by the review: the gate verified that ``estimator_is_proven()`` EXISTS and
    never that it consults ``ESTIMATOR_PROVEN``. ``def estimator_is_proven(): return True`` passed
    every leg — the one seam the whole mechanism hangs from, unchecked."""
    fn = _function(tree, function)
    if fn is None:
        return False
    return any(
        isinstance(node, ast.Name) and node.id == flag for node in ast.walk(fn))


def _disabled_tests(tree: ast.Module) -> list[str]:
    """Every way the gate's tests can be turned off while the file still looks like a gate.

    CONFIRMED [HIGH] by the review, which walked past the first version — decorators on ``def
    test*`` only — using six forms. Now covered:

    - a decorator on a test function (the original leg);
    - a module-level ``pytestmark = pytest.mark.skip(...)``, which disables the WHOLE file;
    - a bare ``pytest.skip(...)`` called anywhere, including at import time;
    - ``pytest.xfail(...)`` / ``pytest.importorskip(...)`` likewise;
    - a decorator on the enclosing class.

    A gate that is registered and skipped looks exactly like a gate that runs. That is the entire
    failure mode, so this leg is deliberately blunt: it reports anything skip-shaped anywhere in the
    module and lets a human argue."""
    disabled: list[str] = []

    def _marker(node: ast.expr) -> str:
        return _dotted(node.func if isinstance(node, ast.Call) else node)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            for decorator in node.decorator_list:
                if any(d in _marker(decorator).split(".") for d in _DISABLERS):
                    disabled.append(f"{node.name} (decorator)")
        # `pytestmark = pytest.mark.skip(...)` — or a list of markers — kills the whole module
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            spelled = ast.unparse(node.value)
            if any(d in spelled for d in _DISABLERS):
                disabled.append("pytestmark (the whole module)")
        # an imperative skip, wherever it sits — including at import time
        if isinstance(node, ast.Call):
            called = _marker(node)
            if any(called.endswith(f".{d}") or called == d
                   for d in (*_DISABLERS, "importorskip")):
                disabled.append(f"{called}() at line {node.lineno}")
    return disabled


def the_simulation_gate_is_wired(
    domain_path: Path | None = None, harness_path: Path | None = None,
    test_path: Path | None = None,
) -> CheckResult:
    """``ESTIMATOR_PROVEN`` cannot be true unless the proof actually runs (Story 5.3, FR-23/SM-1).

    FR-23: *"The estimator ships only if it is proven… A failing estimator emits the counts-only
    sentence instead — it never emits a bound it cannot defend."* A bare boolean satisfying that by
    assertion would be the §0.2 failure in one line of Python: a claim of soundness nobody checked,
    written into the product and defended by a green build.

    So, whenever the flag is true, all of this must hold — and the check FAILS CLOSED on anything it
    cannot read:

    - the simulation harness exists and names its target, its trial floor, its scenarios and its
      verdict functions;
    - a registered test module exercises it, asserting the coverage **floor** *and* the tightness
      **ceiling** — soundness alone is satisfiable by ``count_upper = N``, which covers the truth
      every time and says nothing;
    - **no test in that module is skipped or xfailed.** A gate that is registered and skipped looks
      identical to a gate that runs;
    - the Domain exposes ``estimator_is_proven()``, so the estimate seam has one name to consult
      rather than every caller reading a constant for itself.

    This is the shape of the gold-set merge gate (Story 2.12) — a static check cannot verify the
    mathematics, but it can make the word *"proven"* un-writable without the proof running. When the
    flag is **false** the check passes trivially and says so: shipping counts-only is an honest
    state, not a violation."""
    name, ad = "the simulation gate is wired", "AD-33"
    domain = domain_path if domain_path is not None else _ESTIMATOR
    tree = _parse(domain)
    if tree is None:
        return _fail_closed(name, ad, f"cannot parse {domain.name}")
    proven = _module_flag(tree, _PROVEN_FLAG)
    if proven is None:
        return _fail_closed(
            name, ad, f"{_PROVEN_FLAG} is not a module-level boolean in {domain.name}")
    if not any(
            isinstance(n, ast.FunctionDef) and n.name == _PROVEN_FN for n in ast.walk(tree)):
        return _fail_closed(name, ad, f"{_PROVEN_FN}() is not in {domain.name} — renamed?")
    if not _reads_the_flag(tree, _PROVEN_FN, _PROVEN_FLAG):
        return CheckResult(
            name, ad, False,
            f"{_PROVEN_FN}() does not read {_PROVEN_FLAG} — the one seam the whole mechanism hangs "
            "from would answer a hard-coded 'yes', and every other leg of this check would still "
            "pass (FR-23)")
    if not proven:
        return CheckResult(
            name, ad, True,
            f"{_PROVEN_FLAG} is False — the product emits counts only and states no bound. An "
            "unproven estimator that says so is not a violation; it is FR-23 working")

    harness = harness_path if harness_path is not None else _HARNESS
    gate_test = test_path if test_path is not None else _GATE_TEST
    for path, what in ((harness, "the simulation harness"), (gate_test, "the gate's test module")):
        if not path.is_file():
            return CheckResult(
                name, ad, False,
                f"{_PROVEN_FLAG} is True but {what} ({path.name}) does not exist — 'proven' is a "
                "claim about a proof that must therefore run (FR-23/SM-1)")
    harness_tree, test_tree = _parse(harness), _parse(gate_test)
    if harness_tree is None or test_tree is None:
        return _fail_closed(name, ad, f"cannot parse {harness.name} / {gate_test.name}")

    # Functions, classes, plain assignments AND annotated ones. `SCENARIOS: tuple[...] = (...)` is
    # an ast.AnnAssign, not an ast.Assign — this check reported the harness's own scenario set
    # missing until the annotated form was handled, which is the fail-closed behaviour working.
    defined = {
        n.name for n in ast.walk(harness_tree)
        if isinstance(n, ast.FunctionDef | ast.ClassDef)} | {
        t.id for n in ast.walk(harness_tree) if isinstance(n, ast.Assign)
        for t in n.targets if isinstance(t, ast.Name)} | {
        n.target.id for n in ast.walk(harness_tree)
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    missing = sorted(set(_HARNESS_SYMBOLS) - defined)
    if missing:
        return CheckResult(
            name, ad, False,
            f"{harness.name} does not name {missing} — a gate with no stated target, no trial "
            "floor or no scenarios is a gate whose strength nobody can read (FR-23)")

    # CONFIRMED [MEDIUM] by the review, on two counts at once.
    #
    # (a) The first version searched `ast.unparse(whole module)`. `unparse` drops comments but KEEPS
    #     docstrings and string literals, so a marker merely NAMED in prose satisfied the leg. Now
    #     only the text of real `assert` statements is searched.
    # (b) The floor markers were joined by `any()`, so mentioning `family_coverage` alone — the
    #     textbook hypergeometric — satisfied the leg that exists to guarantee the *pièce* claim,
    #     which is the one this build actually owns. Both are now required.
    asserted = "\n".join(
        ast.unparse(node) for node in ast.walk(test_tree) if isinstance(node, ast.Assert))
    for markers, leg, need_all in ((_FLOOR_MARKERS, "the coverage FLOOR", True),
                                   (_CEILING_MARKERS, "the tightness CEILING", False)):
        present = [marker for marker in markers if marker in asserted]
        if (len(present) < len(markers)) if need_all else (not present):
            missing = sorted(set(markers) - set(present))
            return CheckResult(
                name, ad, False,
                f"{gate_test.name} asserts nothing about {leg} ({missing} appear in no assert "
                "statement) — soundness alone is satisfiable by an estimator answering 'at most "
                "all of them', which covers the truth every time and says nothing (AC-2)")
    disabled = _disabled_tests(test_tree)
    # CONFIRMED [LOW] by the review: the only evidence the module is COLLECTED was `is_file()`, and
    # pytest collection is governed by conftest.py — one `collect_ignore` line turns the gate off
    # while every other leg stays green. The conftests on the path from the repo root down to the
    # module are read too.
    for parent in (gate_test.parent, gate_test.parent.parent):
        conftest = parent / "conftest.py"
        if not conftest.is_file():
            continue
        conftree = _parse(conftest)
        if conftree is None:
            return _fail_closed(name, ad, f"cannot parse {conftest}")
        spelled = ast.unparse(conftree)
        if "collect_ignore" in spelled and gate_test.stem in spelled:
            disabled.append(f"{conftest.name} de-collects it")
        disabled.extend(f"{conftest.name}: {d}" for d in _disabled_tests(conftree))
    if disabled:
        return CheckResult(
            name, ad, False,
            f"{gate_test.name} is skipped or de-collected ({disabled}) — a gate that is registered "
            "and skipped looks exactly like a gate that runs")
    return CheckResult(
        name, ad, True,
        f"{_PROVEN_FLAG} is True and the proof runs: {harness.name} names its target and its trial "
        f"floor, {gate_test.name} asserts both the coverage floor and the tightness ceiling, and "
        "nothing in it is skipped")


def run() -> list[CheckResult]:
    return [
        piece_figure_is_a_worst_case(),
        a_census_states_no_bound(),
        one_run_one_bound_chosen_by_recency(),
        the_bound_is_computed_from_the_freeze(),
        the_bound_consumes_no_model_number(),
        the_simulation_gate_is_wired(),
    ]
