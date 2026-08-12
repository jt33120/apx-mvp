"""The sentence's structural properties (Story 5.4, FR-23 / FR-55 / FR-56).

Three checks over the one text this product says out loud:

- **statement-one-composer (FR-23):** the *confidence bound* sentence is composed in exactly one
  module. Its telltale wording appears nowhere else in the runtime and nowhere in the client.
- **statement-composed-offline (FR-55/FR-36):** the composer's transitive import closure stays
  inside the Domain and touches nothing that could reach a network — *a statistical claim must
  never depend on a network call*.
- **unfitness-offers-no-line-move (FR-23):** where the ranking is declared unfit, the remedy on
  offer is a re-rank, never a line move; and the finding actually reaches a surface.

Build-time tooling, so this module is outside the scanned runtime (``_RUNTIME_EXCLUDE``) and may
name the things it forbids.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from apx.checks.forward_looking import _docstrings
from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _APX_ROOT, _trees, _where
from apx.checks.payload_schema import _fail_closed, _parse


def _function(tree: ast.Module, fn: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn:
            return node
    return None

# The ONE module allowed to compose the sentence, and the ONE function that does it.
_COMPOSER_MODULE = _APX_ROOT / "core" / "domain" / "statement.py"
_COMPOSER_FUNCTION = "statement_fr"

_WEB_ROOT = _APX_ROOT / "web" / "src"
_WEB_SUFFIXES = (".ts", ".tsx")


def _normalise(text: str) -> str:
    """Whitespace-collapsed, lower-cased, with typographic apostrophes folded onto the ASCII one.

    The client writes ``n’est`` and Python writes ``n'est``; a fragment list that did not fold them
    would police one file and wave the other through — the same one-sided comparison this story
    found in the banned-phrasing list."""
    return re.sub(r"\s+", " ", text).strip().lower().replace("’", "'").replace("‘", "'")


# The wording that only the composer may hold. Each fragment is a phrase that belongs to exactly one
# register's claim, so a copy anywhere else IS a second composer — not a coincidence of vocabulary.
_SENTENCE_FRAGMENTS = (
    "ont été tirées au hasard",          # the draw clause, shared by bound + counts-only
    "avec une confiance de",             # the bound register's inference
    "prévalence ≤",                      # the bound register's parenthetical
    "recensement : les",                 # the census register
    "aucune borne n'est énoncée",        # the counts-only register's refusal
    "pièces au pire",                    # the pièce worst case
)


def the_sentence_has_one_composer(
    roots: list[Path] | None = None, web_root: Path | None = None
) -> CheckResult:
    """The *confidence bound* sentence is composed in **one** module (FR-23, Story 5.4).

    Before this story its four registers' words lived in three places across two layers, and the
    client hand-assembled two of them from numeric fields. Every extra composer is another place the
    disjoint registers can be re-branched — the Story 5.2 review found that duplicated branching
    wrong in three separate readers — and, worse, a client-composed claim can silently omit the
    *RBAC scope* and the staleness that FR-23 and FR-58 require to travel **inside** the string.

    Two legs. The Python runtime, by AST string literal (a comment is not a hit). And the client, as
    raw text, because a claim assembled in TypeScript is still a claim assembled somewhere other
    than here — and it is the copy a lawyer actually pastes.

    **Docstrings are exempt**, and the exemption is a scoping decision rather than a weakening: a
    docstring is the first statement of a module, class or function and cannot be returned as a
    value, so it composes nothing. Documentation has to be able to quote the sentence it is
    explaining — ``confidence.prevalence_fr``'s own docstring does, describing the parenthetical it
    renders — and a check that forbade that would be forbidding the explanation of itself.
    """
    name, ad = "the sentence has one composer", "FR-23"
    if not _COMPOSER_MODULE.is_file() and roots is None:
        return CheckResult(name, ad, False,
                           "the sentence composer module is missing — the check cannot verify a "
                           "property whose subject does not exist (FR-56)")
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    scanned = 0
    for path, tree in trees:
        if roots is None and path == _COMPOSER_MODULE:
            continue                                    # the one place the words belong
        scanned += 1
        docstrings = _docstrings(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue                                # documentation, never a composer
            low = _normalise(node.value)
            for fragment in _SENTENCE_FRAGMENTS:
                if fragment in low:
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{node.lineno} composes the confidence-bound sentence "
                        f"({fragment!r}) outside apx/core/domain/statement.py — one sentence, one "
                        "composer (FR-23)")
    web = _WEB_ROOT if web_root is None else web_root
    for path in _web_files(web):
        try:
            low = _normalise(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False,
                               f"cannot read {path.name} (failing closed, cannot verify)")
        for fragment in _SENTENCE_FRAGMENTS:
            if fragment in low:
                return CheckResult(
                    name, ad, False,
                    f"web/src/{path.name} composes the confidence-bound sentence ({fragment!r}) "
                    "in the client — a client-composed claim can omit the scope and the staleness "
                    "the server puts inside the string (FR-23/FR-58)")
    return CheckResult(
        name, ad, True,
        f"the sentence is composed only in apx/core/domain/statement.py ({scanned} runtime "
        f"module(s) + the client checked)")


# Anything that could reach a network, by import name. A statistical claim that depended on one
# would make FR-55's *"regenerable from the audit record WITHOUT a model call"* false.
_EGRESS_IMPORTS = frozenset({
    "http", "httpx", "requests", "socket", "ssl", "urllib", "urllib3", "aiohttp", "websockets",
    "smtplib", "ftplib", "telnetlib", "openai", "anthropic", "mistralai", "boto3", "grpc",
    "subprocess", "asyncio",
})


def the_sentence_is_composed_offline(module: Path | None = None) -> CheckResult:
    """The sentence's composer reaches no network, transitively (FR-55/FR-36, Story 5.4).

    FR-55: *"the confidence bound sentence is regenerable from the audit record **without** a model
    call — a statistical statement must never depend on a network call."* FR-36 makes
    machine-generated user-facing text model-produced; FR-55's own assumption note resolves the
    contradiction in favour of *templated, translated, locally rendered* text, and this is that
    resolution made structural.

    **This is a check on an absence, and it is deliberately the belt rather than the braces.** An
    absence-check passes on an empty file and on a module that composes nothing; the positive proof
    is the round-trip test that regenerates the sentence from the recorded artefact and compares it
    character for character. So this check first requires the composer to **exist and export its
    function** — a property whose subject is missing is not satisfied, it is unverifiable (FR-56) —
    and only then walks the closure.

    The closure is followed through ``apx.*`` imports only, and must stay inside
    ``apx.core.domain``: a Domain module importing a port or an adapter is already an AD-4 breach,
    but stating it here means the sentence's own guarantee does not rest on another check's scope.
    """
    name, ad = "the sentence is composed offline", "FR-55"
    start = _COMPOSER_MODULE if module is None else module
    if not start.is_file():
        return CheckResult(name, ad, False,
                           f"the sentence composer {start.name} is missing — a property whose "
                           "subject does not exist is unverifiable, never satisfied (FR-56)")
    seen: set[Path] = set()
    pending = [start]
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = _parse(path)
        if tree is None:
            return _fail_closed(name, ad, [path.name])
        package = _dotted_of(path)
        for node in ast.walk(tree):
            for dotted in _imported_modules(node, package):
                if dotted == "<dynamic>":
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)} imports a module named at RUNTIME — the closure cannot be "
                        "verified, and an unverifiable offline guarantee is not one (FR-55/FR-56)")
                top = dotted.split(".")[0]
                if top in _EGRESS_IMPORTS:
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)} imports {dotted!r} — the confidence-bound sentence must "
                        "render with the network absent (FR-55)")
                if not dotted.startswith("apx"):
                    continue
                if not dotted.startswith("apx.core.domain"):
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)} imports {dotted!r} — the sentence's closure leaves the "
                        "Domain, so its offline guarantee would rest on a port's behaviour "
                        "(FR-55/AD-4)")
                nxt = _module_path(dotted)
                if nxt is not None:
                    pending.append(nxt)
    if module is None and not _exports(start, _COMPOSER_FUNCTION):
        return CheckResult(name, ad, False,
                           f"{_where(start)} does not define {_COMPOSER_FUNCTION}() — an offline "
                           "guarantee over a module that composes nothing is vacuous (FR-56)")
    return CheckResult(
        name, ad, True,
        f"the sentence's import closure is {len(seen)} Domain module(s), none of them networked")


def _imported_modules(node: ast.AST, package: str) -> list[str]:
    """Every dotted module name one import statement names — relative and dynamic ones included.

    CONFIRMED [HIGH] by the review, reproduced by editing the composer and running the real
    harness: the first version returned ``[]`` for any ``ImportFrom`` with ``level != 0`` and had
    no dynamic leg, so ::

        def _polish(text):
            import importlib
            return importlib.import_module("httpx").post(URL, json={"t": text}).text

    left all 89 checks green while the *confidence bound* sentence was being POSTed to a third
    party — FR-55's *"a statistical statement must never depend on a network call"* silently false,
    with a passing build saying otherwise. A relative import was invisible the same way, so any
    egress one relative hop away was equally unseen.

    ``from x import y`` yields ``x`` and ``x.y``, because ``y`` may itself be a module; following
    only ``x`` would walk past a submodule import and call the closure clean.
    """
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        base = node.module or ""
        if node.level:
            # a relative import resolves against the importing module's own package
            parts = package.split(".")
            # ``from . import x`` inside apx.core.domain.statement means apx.core.domain.x, so
            # one level strips the MODULE, not the package: keep = len(parts) - level.
            keep = len(parts) - node.level
            root = ".".join(parts[:keep]) if keep > 0 else ""
            base = f"{root}.{base}" if base else root
        if not base:
            return []
        return [base] + [f"{base}.{alias.name}" for alias in node.names]
    if isinstance(node, ast.Call):
        target = _dynamic_import_target(node)
        return [target] if target else []
    return []


# The two ways a module is imported by NAME at runtime rather than by statement.
_DYNAMIC_IMPORTERS = frozenset({"import_module", "__import__"})


def _dynamic_import_target(call: ast.Call) -> str | None:
    """The module a dynamic import names, when it is a plain string literal.

    A non-literal argument (a variable, an f-string) is deliberately NOT resolved and is instead
    reported by the caller as unverifiable: a closure walk that shrugged at
    ``importlib.import_module(name)`` would be answering "no network" when the honest answer is
    "cannot tell" — which is how a check on an absence fails open."""
    fn = call.func
    name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
    if name not in _DYNAMIC_IMPORTERS:
        return None
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(
            call.args[0].value, str):
        return call.args[0].value
    return "<dynamic>"                       # named at runtime — unverifiable, never assumed clean


def _module_path(dotted: str) -> Path | None:
    """The file a dotted ``apx.*`` name resolves to — the module, or the package's ``__init__``.

    Resolving the package form matters: without it the walk stops at the first sub-package and
    every module beneath it is outside the closure while the check reports success."""
    base = _APX_ROOT.parent / dotted.replace(".", "/")
    module = base.with_suffix(".py")
    if module.is_file():
        return module
    package = base / "__init__.py"
    return package if package.is_file() else None


def _dotted_of(path: Path) -> str:
    """The dotted name of a file inside the repo, for resolving its relative imports."""
    try:
        rel = path.relative_to(_APX_ROOT.parent)
    except ValueError:
        return path.stem
    return ".".join(rel.with_suffix("").parts)


def _exports(path: Path, function: str) -> bool:
    tree = _parse(path)
    return tree is not None and any(
        isinstance(n, ast.FunctionDef) and n.name == function for n in ast.walk(tree))


# The worklist offer an unfitness finding may NEVER carry. FR-23: the system "does not offer a line
# move as the remedy" — the order is not ordering, and re-cutting an order that carries no signal
# cannot help.
_FORBIDDEN_REMEDY = "re-line"
_LINE_MOVE_MARKERS = ("re-line", "offer_replace_line", "replaceline", "movetheline", "moveline")


def unfitness_offers_no_line_move(
    module: Path | None = None, api: Path | None = None, web_root: Path | None = None
) -> CheckResult:
    """Where the *ranking version* is declared unfit, the remedy is a re-rank — never a line move
    (FR-23, Story 5.4).

    Three legs, two of them live now:

    1. **the rule** — the Domain module that owns the finding never names the line-move offer. A
       finding that could carry it would put the forbidden remedy one assignment away;
    2. **the surface** — the API's bound payload ships the declaration. A finding computed and never
       shipped is a property with no surface, which FR-56 says is not a property at all;
    3. **the client** — a client that can move the line must know about the finding. **Vacuous
       until Story 4.9's line-move surface lands** (there is no such control today); stated now so
       the guard exists before the control does, rather than after.
    """
    name, ad = "an unfit ranking offers no line move", "FR-23"
    owner = _COMPOSER_MODULE if module is None else module
    if not owner.is_file():
        return CheckResult(name, ad, False,
                           f"{owner.name} is missing — the unfitness rule has no home (FR-56)")
    tree = _parse(owner)
    if tree is None:
        return _fail_closed(name, ad, [owner.name])
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _FORBIDDEN_REMEDY in _normalise(node.value):
                return CheckResult(
                    name, ad, False,
                    f"{_where(owner)}:{node.lineno} names the line-move offer — an unfit ranking "
                    "offers a re-rank with a revised case theory, never a re-cut (FR-23)")
    # FR-23's THIRD clause: the finding must produce a worklist line offering a re-rank with a
    # revised case theory. CONFIRMED by three lenses that it had no code anywhere — a requirement
    # two-thirds implemented reads, from the outside, exactly like one that is finished. The offer
    # is checked here so it can never become the line move by a one-word edit.
    worklist = _APX_ROOT / "core" / "domain" / "worklist.py"
    if worklist.is_file():
        wtree = _parse(worklist)
        if wtree is None:
            return _fail_closed(name, ad, [worklist.name])
        names = {n.name for n in ast.walk(wtree) if isinstance(n, ast.FunctionDef)}
        if "unfitness_line" not in names:
            return CheckResult(
                name, ad, False,
                "core/domain/worklist.py builds no unfitness line — FR-23 requires the finding to "
                "produce a worklist line offering a re-rank with a revised case theory (FR-37)")
        line = _function(wtree, "unfitness_line")
        for node in ast.walk(line) if line is not None else []:
            named = (node.id if isinstance(node, ast.Name)
                     else node.value if isinstance(node, ast.Constant) else "")
            if isinstance(named, str) and (
                    "OFFER_REPLACE_LINE" in named or _FORBIDDEN_REMEDY in _normalise(named)):
                return CheckResult(
                    name, ad, False,
                    "the unfitness worklist line offers the line move — the remedy is a re-rank "
                    "with a revised case theory, never a re-cut (FR-23)")
    # Leg 1b: the READ SEAM must strip the line-move offer where the ranking is unfit. Raised by
    # the review, which was right about the scope even though its consequence was refuted: the
    # offer is not in statement.py at all, it is ``worklist.OFFER_REPLACE_LINE``, and a stale line
    # already emits it. A check that never opened the module holding the forbidden thing was
    # inspecting the wrong tree — the recurring defect, in the guard against it.
    seam = _APX_ROOT / "core" / "app" / "read" / "freshness.py"
    if seam.is_file():
        try:
            seam_text = _normalise(seam.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False, f"cannot read {seam.name} (failing closed)")
        if "unfitness_line" in seam_text and "offer_replace_line" not in seam_text:
            return CheckResult(
                name, ad, False,
                "core/app/read/freshness.py adds the unfitness line without removing the "
                "line-move offer — FR-23 says the system does not OFFER a line move as the "
                "remedy, and a stale line emits one")
    api_path = (_APX_ROOT / "api" / "app.py") if api is None else api
    if api_path.is_file():
        try:
            api_text = _normalise(api_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False, f"cannot read {api_path.name} (failing closed)")
        if "unfit_fr" not in api_text:
            return CheckResult(
                name, ad, False,
                "the API ships no unfitness declaration — a finding the surface never receives is "
                "a property with no surface (FR-23/FR-56)")
    web = _WEB_ROOT if web_root is None else web_root
    movers = [p for p in _web_files(web) if _has_line_move(p)]
    blind = [p.name for p in movers if "unfit_fr" not in _read_lower(p)]
    if blind:
        return CheckResult(
            name, ad, False,
            f"web/src {sorted(blind)} can move the line without reading the unfitness declaration "
            "— the affordance must be REMOVED where the ranking is unfit, not merely greyed "
            "(FR-23)")
    if not movers:
        return CheckResult(
            name, ad, True,
            "the rule names no line-move remedy and the API ships the declaration; the client leg "
            "is vacuous — Story 4.9's line-move surface does not exist yet")
    return CheckResult(
        name, ad, True,
        f"the rule names no line-move remedy, the API ships the declaration, and {len(movers)} "
        "client file(s) that can move the line read it")


def _has_line_move(path: Path) -> bool:
    text = _read_lower(path)
    return any(marker in text for marker in _LINE_MOVE_MARKERS)


def _read_lower(path: Path) -> str:
    try:
        return _normalise(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):  # pragma: no cover - unreadable source is caught above
        return ""


def _web_files(root: Path) -> list[Path]:
    """The client's TypeScript sources, sorted. Empty when the client is absent — a backend-only
    checkout is not a violation."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.suffix in _WEB_SUFFIXES and p.is_file())
