"""Forward-looking structural properties (story 1.12; FR-9/10/14/34/35/42/23).

These guard code that arrives in a LATER epic. Each is a LIVE, registered check that scans the
surface its subject will occupy, passes **vacuously** today (there is nothing to catch yet), and
carries a failure-path fixture proving it FIRES on the violation it will one day meet — exactly as
the egress guard is green on the empty tree. Vacuous-green is honest ONLY with a firing fixture; a
vacuous check without one is the anti-pattern this harness exists to prevent.

- **embedder_has_one_implementation (FR-9/AD-11):** at most one concrete ``Embedder`` and no
  embedder constructed in an exception handler — the v1 silent hash fallback. (LIVE as of 2.8 —
  the one impl is ``embedder_bgem3``; this check now guards live code.)
- **destructive_index_ops_single_entry (FR-10/AD-7):** a bulk index drop/truncate is reachable
  from at most one function — the v1 self-wiping index. (The 2.8 vector write path is INSERT-only,
  so this stays vacuous — a runtime destructive op would make it non-vacuous.)
- **no_post_filter_in_retrieval (FR-14/AD-14):** no function takes a fetched result set AND a
  scope — scope is a query pre-filter, never a post-filter. (Retrieval = 3.x.)
- **no_natural_language_translation_key (FR-34):** a translation call's key is namespaced, never
  a natural-language string. (i18n = 6.3.)
- **no_hardcoded_locale (FR-35/AD-24):** no locale literal in a ``locale=`` / ``setlocale`` /
  ``Locale`` call. (i18n = 6.4.)
- **no_model_reported_confidence (FR-42/AD-19):** no ``confidence``/``certainty`` field read off a
  model response — confidence is derived, never self-reported. (Confidence = 4.x.)
- **no_banned_confidence_phrasing (FR-23):** no banned *confidence bound* phrasing in a string set
  or a source literal — a translator cannot reintroduce the §0.2 false claim. (Strings = 5.4/6.x.)

Each fails closed and accepts an injectable ``roots`` (a fixture) — the default is the runtime tree.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.isolation_harness import _trees, _where
from apx.checks.payload_schema import _enclosing_func, _fail_closed, _parent_map

# ── FR-9 / AD-11: no fallback / stub embedder ────────────────────────────────────────────────
# The methods a real embedder exposes — BGE-M3 (the AD-11 default) exposes `.encode`, not `.embed`.
_EMBED_METHODS = frozenset({"embed", "encode", "embed_documents", "embed_query"})


def _defines_dimensions(cls: ast.ClassDef) -> bool:
    """The class assigns a ``dimensions`` attribute (the Embedder port's fixed member) — as a class
    annotation/assignment or a ``self.dimensions = …`` in a method. This is the port SHAPE, so a
    disguised fallback (the v1 hash, named anything) is still counted if it is a usable embedder."""
    for sub in ast.walk(cls):
        if isinstance(sub, ast.AnnAssign):
            tgt = sub.target
            if (isinstance(tgt, ast.Name) and tgt.id == "dimensions") or (
                    isinstance(tgt, ast.Attribute) and tgt.attr == "dimensions"):
                return True
        if isinstance(sub, ast.Assign):
            for tgt in sub.targets:
                if (isinstance(tgt, ast.Name) and tgt.id == "dimensions") or (
                        isinstance(tgt, ast.Attribute) and tgt.attr == "dimensions"):
                    return True
    return False


def _is_concrete_embedder(node: ast.AST, path: Path) -> bool:
    """A concrete Embedder implementation: a ClassDef (not a Protocol/ABC) that exposes an embedding
    method (``embed``/``encode``/…) AND either looks like an embedder (name contains ``embed``, OR
    lives under an ``embed``-named dir, OR subclasses ``Embedder``) OR carries the port SHAPE (a
    ``dimensions`` member) — so a disguised fallback named anything (the v1 hash) is still counted,
    while a stray ``.encode`` (JSON/base64) with no ``dimensions`` and no embed-name is not. The
    ``Embedder(Protocol)`` port is excluded. A heuristic — a determined evader can still hide, but
    a *usable* second embedder (one the pipeline could inject) has the shape and is caught."""
    if not isinstance(node, ast.ClassDef):
        return False
    bases = {b.id for b in node.bases if isinstance(b, ast.Name)} | {
        b.attr for b in node.bases if isinstance(b, ast.Attribute)}
    if bases & {"Protocol", "ABC"}:
        return False
    has_method = any(
        isinstance(m, ast.FunctionDef | ast.AsyncFunctionDef) and m.name in _EMBED_METHODS
        for m in node.body)
    if not has_method:
        return False
    looks_like = (
        "embed" in node.name.lower() or "embed" in str(path).lower() or "Embedder" in bases)
    return looks_like or _defines_dimensions(node)


def _except_constructs_embedder(tree: ast.Module) -> ast.AST | None:
    """An ``except`` handler that constructs an embedder-named object — the v1 silent fallback path.
    A NAME heuristic (a ctor whose name mentions ``embed``), backstopped by the ≤1 count above,
    which (via the port-shape leg) catches a second *usable* embedder even under a disguised
    name."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                fn = sub.func
                nm = fn.id if isinstance(fn, ast.Name) else (
                    fn.attr if isinstance(fn, ast.Attribute) else "")
                if "embed" in nm.lower():
                    return sub
    return None


def embedder_has_one_implementation(roots: Iterable[Path] | None = None) -> CheckResult:
    """At most one concrete ``Embedder`` implementation, and none constructed in an exception
    handler (FR-9/AD-11). There is no fallback and no stub embedder: a second implementation, or an
    embedder built in an ``except`` block, is the v1 silent-degradation defect. An impl is detected
    by an embedding method (``embed``/``encode`` — BGE-M3 uses ``encode``) on an embedder-looking
    class. Vacuous until the embedder lands (story 2.8); the fixture proves it fires on a second
    implementation."""
    name, ad = "no fallback embedder", "AD-11"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    impls: list[str] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if _is_concrete_embedder(node, path):
                assert isinstance(node, ast.ClassDef)
                impls.append(f"{_where(path)}::{node.name}")
        caught = _except_constructs_embedder(tree)
        if caught is not None:
            return CheckResult(
                name, ad, False,
                f"{_where(path)}:{caught.lineno} an embedder is constructed in an except handler — "
                "the v1 silent fallback; the embedder fails loudly, never degrades (FR-9/AD-11)")
    if len(impls) > 1:
        return CheckResult(name, ad, False,
                           f"more than one Embedder implementation (a fallback): {sorted(impls)} "
                           "— there is exactly one non-test embedder (FR-9/AD-11)")
    shape = impls[0] if impls else "none — the one embedder implementation is missing (2.8)"
    return CheckResult(name, ad, True, f"at most one embedder implementation: {shape}")


# ── FR-10 / AD-7: destructive index operations reachable from one entry point only ────────────
# Vector-store / collection destruction by method name (Qdrant's real API is `recreate_collection`
# / `delete_collection`) AND by raw DDL/DML. Since story 2.8 the vector lives ON the chunk row, so a
# bulk `DELETE FROM chunk` (ORM `.delete()` or raw SQL) is a corpus wipe too — included (FR-10).
_DESTRUCTIVE_INDEX_CALLS = frozenset({
    "drop_index", "drop_collection", "delete_collection", "recreate_index", "recreate_collection",
    "reset_index", "truncate_index", "wipe_index", "rebuild_index", "delete_index", "delete_all",
})
_DESTRUCTIVE_SQL_RE = re.compile(
    r"\b(drop\s+index|drop\s+table|truncate|delete\s+from)\b", re.IGNORECASE)


def _destructive_call(node: ast.Call) -> bool:
    """A destructive index op: a call to a bulk-destroy method, or a raw ``execute``/``text`` whose
    SQL string is a ``DROP INDEX``/``DROP TABLE``/``TRUNCATE`` (the ORM/raw-DDL vectors the v1
    self-wipe used, beyond the named method calls)."""
    fn = node.func
    nm = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    if nm in _DESTRUCTIVE_INDEX_CALLS:
        return True
    # an ORM BULK delete — `query(...).delete()` / `session.query(X).delete()` — takes NO positional
    # object (unlike single-row `session.delete(obj)`), so a no-positional-arg `.delete()` is the
    # bulk-wipe form (FR-10; the chunk row IS the index since 2.8); single-row delete is not.
    if nm == "delete" and isinstance(fn, ast.Attribute) and not node.args:
        return True
    if nm in ("execute", "text"):
        return any(
            isinstance(a, ast.Constant) and isinstance(a.value, str)
            and _DESTRUCTIVE_SQL_RE.search(a.value)
            for a in node.args)
    return False


def destructive_index_ops_single_entry(roots: Iterable[Path] | None = None) -> CheckResult:
    """A destructive bulk index operation is reachable from at most ONE function (FR-10/AD-7).
    The v1 defect wiped the whole collection on any dimension mismatch — a transient error destroyed
    the corpus. Detected by vector-store destroy methods (incl. Qdrant ``recreate_collection``) and
    raw ``DROP``/``TRUNCATE`` DDL. Vacuous until an index exists (story 2.8); the fixture proves
    it fires on a second destructive call site."""
    name, ad = "destructive index ops reachable from one entry point", "AD-7"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    sites: list[str] = []
    for path, tree in trees:
        # Alembic migrations are deploy-time DDL, explicitly human-initiated and reviewed (AD-7's
        # sanctioned destructive path); a downgrade legitimately drops an index. FR-10 guards the
        # RUNTIME index-management path that must never wipe the corpus on error — not migrations.
        if "migrations" in path.parts:
            continue
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _destructive_call(node):
                func = _enclosing_func(node, parents)
                label = f"{_where(path)}::{func.name}" if func is not None else (
                    f"{_where(path)}::<module>")
                sites.append(label)
    distinct = sorted(set(sites))
    if len(distinct) > 1:
        return CheckResult(
            name, ad, False,
            f"destructive index operations reachable from {len(distinct)} call sites: {distinct} "
            "— they must live behind one named administrative entry point (FR-10/AD-7)")
    shape = distinct[0] if distinct else "none yet (vacuous until story 2.8)"
    return CheckResult(name, ad, True, f"destructive index ops behind one entry point: {shape}")


# ── FR-14 / AD-14: no post-filter in retrieval ───────────────────────────────────────────────
# A fetched result set + a scope in one signature = a post-filter. Names extended to the shapes real
# retrieval code will use; any param CONTAINING scope/rbac/acl/perm also counts as a scope.
_RESULT_PARAMS = frozenset({
    "results", "hits", "matches", "candidates", "rows", "result_set", "docs", "documents",
    "chunks", "pieces", "items", "records"})
_SCOPE_PARAMS = frozenset({
    "scope", "scopes", "rbac_scope", "rbac_scopes", "rbac", "acl", "permissions",
    "allowed_scopes", "allowed_matters"})
_SCOPE_SUBSTR = ("scope", "rbac", "acl", "perm")


def _scope_params(params: set[str]) -> set[str]:
    return {p for p in params if p in _SCOPE_PARAMS or any(s in p.lower() for s in _SCOPE_SUBSTR)}


def no_post_filter_in_retrieval(roots: Iterable[Path] | None = None) -> CheckResult:
    """No result-set post-processing function accepts a scope (FR-14/AD-14). A function that takes
    BOTH an already-fetched result set (``results``/``docs``/``chunks``/…) AND a scope (any param
    named or containing ``scope``/``rbac``/``acl``/``perm``) is a post-filter — the #1 silent leak
    vector, because the wrong rows were already fetched, counted or logged. Scope is a query
    PRE-filter; ``search(tenant, scopes, query)`` (scope constrains the query, no result-set
    parameter) is the correct shape, not flagged. Vacuous until retrieval lands (story 3.x)."""
    name, ad = "no post-filter in retrieval", "AD-14"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            params = {a.arg for a in (
                *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
            if (params & _RESULT_PARAMS) and _scope_params(params):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} {node.name}(...) takes a fetched result set + a "
                    "scope — a post-filter; scope is a query pre-filter, never after (FR-14/AD-14)")
    return CheckResult(name, ad, True,
                       f"no result-set post-filter accepts a scope ({len(trees)} file(s))")


# ── FR-34: no natural-language string used as a translation key ───────────────────────────────
# Bare (`t(...)`, `gettext(...)`) AND attribute-form (`i18n.t(...)`, `self._(...)`) translators.
# `translate` is omitted deliberately — `str.translate(table)` would false-positive.
_TRANSLATION_FUNCS = frozenset({"t", "gettext", "ngettext", "pgettext", "trans", "_"})


def no_natural_language_translation_key(roots: Iterable[Path] | None = None) -> CheckResult:
    """A translation call's key is a namespaced token, never a natural-language string (FR-34). A
    key containing a space is a sentence, and an f-string key is worse — both are the v1-style
    silent-fallback trap. Handles bare (``t("…")``) and attribute-form (``i18n.t("…")``,
    ``self._("…")``) translators. Vacuous until the i18n layer lands (story 6.3); the fixture proves
    it fires on a sentence key."""
    name, ad = "no natural-language string as a translation key", "FR-34"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            fn = node.func
            fn_name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else None)
            if fn_name not in _TRANSLATION_FUNCS:
                continue
            first = node.args[0]
            hit = None
            if isinstance(first, ast.Constant) and isinstance(first.value, str) and (
                    " " in first.value.strip()):
                hit = repr(first.value)
            elif isinstance(first, ast.JoinedStr):  # an f-string key is never a namespaced token
                hit = "an f-string"
            if hit is not None:
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} a natural-language string is used as a "
                    f"translation key ({hit}) — keys are namespaced tokens (FR-34)")
    return CheckResult(name, ad, True,
                       f"no natural-language translation key ({len(trees)} file(s))")


# ── FR-35 / AD-24: no hard-coded locale ──────────────────────────────────────────────────────
# fr_FR, en-US, and the setlocale forms fr_FR.UTF-8 / fr_FR@euro — a region-qualified locale
_LOCALE_RE = re.compile(r"\A[a-z]{2}([_-][A-Z]{2})(\.[\w-]+)?(@\w+)?\Z")
_LOCALE_FUNCS = frozenset({"setlocale", "Locale"})


def no_hardcoded_locale(roots: Iterable[Path] | None = None) -> CheckResult:
    """No date/number/currency format is hard-coded to a locale (FR-35/AD-24). Flags a
    region-qualified locale literal (``fr_FR``, ``en-US``) passed as a ``locale=`` keyword or to
    ``setlocale``/``Locale`` — the format context. A bare language code (``fr``) is NOT flagged: it
    is the ``interface_language`` config value, not a hard-coded format. Vacuous until locale-aware
    rendering lands (story 6.4); the fixture proves it fires on ``format_date(d, locale='fr_FR')``.
    """
    name, ad = "no hard-coded locale", "AD-24"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            fn_name = fn.id if isinstance(fn, ast.Name) else (
                fn.attr if isinstance(fn, ast.Attribute) else "")
            # a locale= keyword anywhere, OR a positional locale string to setlocale/Locale
            candidates = [kw.value for kw in node.keywords if kw.arg == "locale"]
            if fn_name in _LOCALE_FUNCS:
                candidates += list(node.args)
            for c in candidates:
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and _LOCALE_RE.match(
                        c.value):
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{node.lineno} a hard-coded locale ({c.value!r}) in a "
                        "format context — dates/numbers render in the user's locale (FR-35)")
    return CheckResult(name, ad, True, f"no hard-coded locale ({len(trees)} file(s))")


# ── FR-42 / AD-19: no model-reported confidence field consumed ───────────────────────────────
_CONFIDENCE_FIELDS = frozenset({"confidence", "certainty", "self_confidence", "confidence_score"})
# Subjects that name a MODEL response — a NAME heuristic. `output`/`prediction`/`result` are omitted
# (they name legitimate derived/domain values too — the false positive the review flagged). The
# ROBUST half of FR-42 — the derivation function has exactly one implementation — lands with the
# confidence path (4.x); this leg is extended to the real judge-result names then.
_MODEL_SUBJECTS = frozenset({
    "response", "resp", "completion", "llm_response", "model_response", "answer", "reply",
    "message", "choice", "verdict", "judgment", "judgement", "inference",
})


def _subject_name(node: ast.expr) -> str | None:
    """The base name a ``.field`` / ``[...]`` access reads from — ``response`` in
    ``response.confidence`` or ``response["confidence"]`` — or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _subject_name(node.value)
    return None


def no_model_reported_confidence(roots: Iterable[Path] | None = None) -> CheckResult:
    """No field named as a confidence is read off a model response (FR-42/AD-19). Per-pièce
    confidence is DERIVED from observable quantities — score margins, cascade agreement — never a
    number the model states about itself (a made-up number laundered through a statistical sentence
    is the §0.2 failure one layer down). Flags ``response.confidence`` / ``resp["certainty"]`` and
    the like off a model-response subject; the statistical ``confidence`` level on a domain result
    is NOT a model subject and is not flagged. Vacuous until the judge/confidence path lands."""
    name, ad = "no model-reported confidence field consumed", "AD-19"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
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
                    f"{_where(path)}:{node.lineno} a '{field}' field is read off a model response "
                    f"({subject}) — confidence is derived, never self-reported (FR-42/AD-19)")
    return CheckResult(name, ad, True,
                       f"no model-reported confidence consumed ({len(trees)} file(s))")


# ── FR-23: no banned confidence-bound phrasing in any locale's string set ─────────────────────
# The one literal the PRD names, plus the semantic shapes it bans (§0.2 / FR-23 / Glossary). The
# full multi-locale list grows as the string sets do (5.4/6.x); it lives here as DATA so a
# translator cannot reintroduce the false claim. Compared whitespace-collapsed, case-insensitive.
_BANNED_PHRASES = (
    "risk of having missed a relevant document",
    "probability that nothing was missed",
    "probability that nothing relevant was missed",
    "chance that nothing was missed",
    "chance that nothing relevant was missed",
)
# Locale/string-resource files (none exist yet); when they land, they are scanned as raw text too.
_RESOURCE_SUFFIXES = frozenset({".json", ".po", ".yaml", ".yml", ".ftl"})
_RESOURCE_DIRS = frozenset({"locales", "translations", "i18n"})


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _banned_hit(text: str) -> str | None:
    low = _collapse(text)
    for phrase in _BANNED_PHRASES:
        if phrase in low:
            return phrase
    return None


def no_banned_confidence_phrasing(roots: Iterable[Path] | None = None) -> CheckResult:
    """No banned *confidence bound* phrasing appears in a string set or a source string literal
    (FR-23). The bound states a prevalence; it never says "risk of having missed a relevant
    document" or any wording a reader could take as the probability that nothing was missed (the
    §0.2 false claim). Scans runtime source string literals (AST, so a comment is not a hit) and any
    locale-resource files as raw text. Vacuous until the confidence sentence / string sets land
    (5.4/6.x); the fixture proves it fires on a resource carrying the banned phrase."""
    name, ad = "no banned confidence-bound phrasing", "FR-23"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:                       # source string literals (never comments)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                hit = _banned_hit(node.value)
                if hit is not None:
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{node.lineno} a banned confidence-bound phrasing "
                        f"({hit!r}) — the bound states a prevalence, never 'nothing was missed' "
                        "(FR-23/§0.2)")
    for path in _resource_files(roots):            # locale resources, scanned as raw text
        try:
            hit = _banned_hit(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return CheckResult(name, ad, False,
                               f"cannot read {path.name} (failing closed, cannot verify)")
        if hit is not None:
            return CheckResult(name, ad, False,
                               f"{_where(path)} carries a banned confidence-bound phrasing "
                               f"({hit!r}) — the §0.2 false claim, in a resource (FR-23)")
    return CheckResult(name, ad, True, "no banned confidence-bound phrasing in source or resources")


def _resource_files(roots: Iterable[Path] | None) -> list[Path]:
    """Locale/string-resource files to scan as raw text — the injected roots' resource files for a
    fixture, else any resource file under a locales/translations/i18n directory in the runtime."""
    from apx.checks.isolation_harness import _APX_ROOT
    bases = list(roots) if roots is not None else [_APX_ROOT]
    out: list[Path] = []
    for base in bases:
        root = base if base.is_dir() else base.parent
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.suffix not in _RESOURCE_SUFFIXES:
                continue
            if roots is not None or (set(p.parts) & _RESOURCE_DIRS):
                out.append(p)
    return out


def run() -> list[CheckResult]:
    return [
        embedder_has_one_implementation(),
        destructive_index_ops_single_entry(),
        no_post_filter_in_retrieval(),
        no_natural_language_translation_key(),
        no_hardcoded_locale(),
        no_model_reported_confidence(),
        no_banned_confidence_phrasing(),
    ]
