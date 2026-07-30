"""The single-read-path structural properties (Story 3.3; AD-14 / AD-13).

AD-14: *"exactly one code path reads tenant data — not only retrieval."* Its complement — *no read
filters after returning* — is already live as ``forward_looking.no_post_filter_in_retrieval`` (a
function taking a fetched result set **and** a scope). This module adds the two teeth that check
cannot see:

- **tenant_reads_have_one_entry_point (AD-14):** no query over a *tenant*-owned **content** table is
  *constructed* outside the sanctioned read path — ``core/app/read/`` (the application entry points)
  plus the store adapter's enumerated read-query modules it delegates to (``store.py``,
  ``semantic_query.py``, ``deterministic_query.py``). A ``select()`` / ``session.query()`` /
  ``select_from()`` / ``join()`` naming a corpus, register, label, audit or scope model **anywhere
  else** — a surface (``api/ web/ worker/ eval/``), ``core/`` outside ``read/``, or a non-read
  adapter module — fails the build, so a second query path cannot be written in good faith.

  *Reconciliation with AD-14's literal wording.* AD-14 says "no ORM query … outside
  ``core/app/read/``, grepped over ``adapters/`` …". Taken literally over ``adapters/`` that is
  impossible in this hexagonal build: the ORM models live in the store adapter, ``core/`` must not
  import them (dependency direction), and every read query is built against those models so CI can
  pin the PostgreSQL dialect (the 3.1–3.2 ``<=>`` / normalisation work). The faithful realisation is
  therefore *the sanctioned set above* — the read layer **plus** the adapter read modules it
  delegates to — and a build failure for a tenant-content query anywhere else.

- **scoped_read_puts_scope_in_the_query (AD-13/AD-14):** a function taking ``scopes`` may not
  ``select()`` a scoped content table filtered by ``tenant`` alone — the internal fetch-then-post-
  filter the signature-only check misses (the ``register_all`` shape: fetch every tenant row, then
  drop out-of-scope rows in Python). A read whose own statement names ``matter`` or ``MatterScope``
  (the scope join / sub-query) or an id-equality (a single-row *guard-then-read*) carries its scope
  in the query and is exempt; a bare tenant-only ``select()`` over a scoped table does not, and
  fails. ``AuditRecord`` is out of this set: the chain is per-*tenant* (AD-43), verified end to
  end and sliced to the authorised *matter* — not a corpus read.

Both fail closed on an unparseable file and take an injectable ``roots`` (a fixture); the default is
the product runtime tree (``apx/`` minus build-time tooling, vendored ``node_modules``, and
deploy-time ``migrations``).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parent_map, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _APX_ROOT.parent
# Build-time tooling + vendored/generated trees + deploy-time DDL are not the product read path.
_EXCLUDE_PARTS = frozenset(
    {"checks", "fitness", "timedrun", "__pycache__", "node_modules", "migrations"})

# Tenant-owned CONTENT models — the corpus, the register, labels, audit, scope. A query over one of
# these reads matter-scoped tenant data (the AD-14 leak surface). Auth/config/queue/DR tables (User,
# TenantSetting, ImportJob, BackupRecord …) are tenant-keyed infrastructure, not matter-scoped
# corpus, and are out of this check's scope.
_CONTENT_TABLES = frozenset({
    "Piece", "PieceProvenance", "PieceCustodian", "Chunk", "Failure", "NoiseExclusion",
    "MatterScope", "AuditRecord", "LabelRecord", "RecallReview",
})
# The subset a SCOPES-taking read must carry its scope over (check 2). MatterScope is excluded (it
# IS the authoritative scope table — reading it by tenant+scope is the pre-filter, not a leak);
# audit is excluded (per-tenant chain, AD-43).
_SCOPED_CONTENT_TABLES = frozenset({
    "Piece", "Chunk", "Failure", "LabelRecord", "RecallReview", "NoiseExclusion",
})
# ``get`` catches ``session.get(Piece, id)`` — an identifier-only read (AD-14: "no method that
# accepts an identifier without a tenant and a scope"); ``_names_a_table`` requires the model itself
# as the first arg, so an ordinary ``dict.get`` is not flagged.
_QUERY_BUILDERS = frozenset({"select", "query", "select_from", "join", "get"})
_READ_APP = ("core", "app", "read")
_STORE_DIR = ("adapters", "store_postgres")
# The methods whose args carry the scope PREDICATE — a ``.where()`` / ``.filter()`` clause. A
# ``.join(MatterScope, …)`` is handled separately: a join alone is not a scope filter (it must also
# filter ``MatterScope.scope``), and its ON-clause references ``.matter`` as a join key, which must
# not be mistaken for a matter filter.
_SCOPE_PREDICATE_METHODS = frozenset({"where", "filter", "filter_by", "having"})

# AD-14 says "no SQL TEXT and no ORM query": a surface hand-rolling raw SQL over a content table is
# a read too. The store adapter legitimately holds raw SQL (backfill, DR ``SELECT * FROM {tbl}``),
# so the raw-SQL leg is scanned everywhere EXCEPT ``adapters/store_postgres/``. Reads = FROM / JOIN.
_CONTENT_TABLE_NAMES = (
    "piece", "piece_provenance", "piece_custodian", "chunk", "failure", "noise_exclusion",
    "matter_scope", "audit_record", "label_record", "recall_review",
)
_RAW_SQL_READ_RE = re.compile(
    r"\b(?:from|join)\s+(?:" + "|".join(_CONTENT_TABLE_NAMES) + r")\b", re.IGNORECASE)


def _where(path: Path) -> Path | str:
    return path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path


def _scan_trees(
    roots: Iterable[Path] | None,
) -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    """The product runtime tree by default (``apx/`` minus tooling / vendored / migrations), or the
    injected ``roots`` for a fixture. An unparseable file fails closed, never skips silently."""
    if roots is not None:
        return _load_trees(list(roots))
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in sorted(_APX_ROOT.rglob("*.py")):
        if set(path.parts) & _EXCLUDE_PARTS:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def _contains(parts: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    return any(parts[i:i + len(needle)] == needle for i in range(len(parts) - len(needle) + 1))


def _under_store_adapter(path: Path) -> bool:
    """The persistence adapter legitimately holds raw SQL (the backfill, the DR ``SELECT * FROM
    {tbl}``). The raw-SQL leg does not scan it — a raw-SQL content read is a concern only OUTSIDE
    the store adapter (a surface hand-rolling one)."""
    return _contains(path.parts, _STORE_DIR)


def _is_query_builder(call: ast.Call) -> bool:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id in _QUERY_BUILDERS               # select(...)
    if isinstance(fn, ast.Attribute):
        return fn.attr in _QUERY_BUILDERS             # session.query(...) / .select_from() / .get()
    return False


def _raw_sql_reads_a_content_table(node: ast.AST) -> bool:
    """A ``text(...)`` / ``execute(...)`` call whose SQL string reads a content table (``FROM`` /
    ``JOIN``). Scanning only SQL-execution call args (not every string constant) keeps a docstring
    that merely says "from failure" out of it."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name | ast.Attribute):
        return False
    fname = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
    if fname not in ("text", "execute", "executemany", "exec_driver_sql"):
        return False
    return any(
        isinstance(a, ast.Constant) and isinstance(a.value, str)
        and _RAW_SQL_READ_RE.search(a.value)
        for a in node.args)


def _names_a_table(call: ast.Call, tables: frozenset[str]) -> bool:
    """A query-builder call whose args reference a table model — the whole entity
    (``select(Piece)``) or one of its columns (``select(Piece.id)`` / ``join(MatterScope, …)``)."""
    for arg in call.args:
        if isinstance(arg, ast.Name) and arg.id in tables:
            return True
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and (
                arg.value.id in tables):
            return True
    return False


def tenant_reads_have_one_entry_point(roots: Iterable[Path] | None = None) -> CheckResult:
    """No query over a tenant-content table is constructed outside the sanctioned read path (AD-14).
    Green on the real tree (all content queries live in the store adapter's read modules); fires on
    a planted ``select(Piece)`` in a surface. Fails closed on an unparseable file."""
    name, ad = "tenant reads have one entry point", "AD-14"
    trees, unparseable = _scan_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    injected = roots is not None
    scanned = 0
    for path, tree in trees:
        # The ORM leg trusts the one read path: core/app/read/ (the entry points) + the store
        # adapter (the persistence layer holds every content query — reads AND writes; a scoped read
        # there is policed by ``scoped_read_puts_scope_in_the_query``). The raw-SQL leg trusts only
        # the store adapter (surfaces must not hand-roll SQL).
        store_adapter = not injected and _under_store_adapter(path)
        orm_trusted = store_adapter or (not injected and _contains(path.parts, _READ_APP))
        if orm_trusted and store_adapter:
            continue
        scanned += 1
        for node in ast.walk(tree):
            # (a) an ORM query builder (select/query/select_from/join/get) over a content table
            if (not orm_trusted and isinstance(node, ast.Call) and _is_query_builder(node)
                    and _names_a_table(node, _CONTENT_TABLES)):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} constructs a query over a tenant-content table "
                    "outside the read path — every tenant read goes through core/app/read/ + the "
                    "store adapter's read modules, never a surface or a second query path (AD-14)")
            # (b) raw SQL (text()/execute()) reading a content table — outside the store adapter
            if not store_adapter and _raw_sql_reads_a_content_table(node):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} runs raw SQL over a tenant-content table "
                    "outside the store adapter — AD-14 forbids SQL text and ORM alike (read path)")
    return CheckResult(
        name, ad, True,
        f"no tenant-content query outside the sanctioned read path ({scanned} files)")


def _enclosing_stmt(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST | None:
    cur: ast.AST | None = node
    while cur is not None and not isinstance(cur, ast.stmt):
        cur = parents.get(id(cur))
    return cur


def _filter_predicates(stmt: ast.AST) -> list[ast.expr]:
    """The argument expressions of every ``.where()`` / ``.filter()`` call in the statement — the
    scope PREDICATE, as opposed to the SELECTed columns. Anchoring on the predicate is what stops
    ``select(Piece.id).where(Piece.tenant == t)`` — a tenant-wide enumeration — from being exempted
    merely because it selects an id/matter column."""
    preds: list[ast.expr] = []
    for n in ast.walk(stmt):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _SCOPE_PREDICATE_METHODS):
            preds.extend(n.args)
            preds.extend(kw.value for kw in n.keywords)
    return preds


def _stmt_joins_matter_scope(stmt: ast.AST) -> bool:
    """The statement ``.join(MatterScope, …)`` — the scope table is joined (its filter may then be
    applied via a predicate built in a variable, as in ``search``'s ``conds`` list)."""
    for n in ast.walk(stmt):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "join"
                and any(isinstance(a, ast.Name) and a.id == "MatterScope" for a in n.args)):
            return True
    return False


def _references_scope_column(node: ast.AST) -> bool:
    """``MatterScope.scope`` appears in ``node`` — the actual scope-column filter (not just the
    MatterScope name, and not the ``.matter`` join key)."""
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr == "scope"
                and isinstance(n.value, ast.Name) and n.value.id == "MatterScope"):
            return True
    return False


def _stmt_carries_scope(stmt: ast.AST, func: ast.AST) -> bool:
    """The read carries its scope IN the query — never a Python post-filter — iff its ``.where()`` /
    ``.filter()`` PREDICATE filters ``.matter`` or ``MatterScope.scope``, OR compares an id column
    for equality (a single-row guard-then-read), OR the statement joins ``MatterScope`` **and** the
    enclosing function filters ``MatterScope.scope`` (the ``search`` shape: the ``scope.in_`` lives
    in a ``conds`` variable). A bare ``.join(MatterScope)`` with no scope filter does NOT count."""
    for pred in _filter_predicates(stmt):
        for n in ast.walk(pred):
            if isinstance(n, ast.Attribute) and n.attr in ("matter", "scope"):
                return True
            if isinstance(n, ast.Compare) and any(isinstance(op, ast.Eq) for op in n.ops):
                for side in (n.left, *n.comparators):
                    if isinstance(side, ast.Attribute) and (
                            side.attr == "id" or side.attr.endswith("_id")):
                        return True
    return _stmt_joins_matter_scope(stmt) and _references_scope_column(func)


def scoped_read_puts_scope_in_the_query(roots: Iterable[Path] | None = None) -> CheckResult:
    """A function taking ``scopes`` may not ``select()`` a scoped content table filtered by
    ``tenant`` alone — the internal fetch-then-post-filter (the ``register_all`` shape). A read
    whose predicate filters ``.matter`` / ``MatterScope.scope`` / an id-equality — or that joins
    ``MatterScope`` and filters its scope via a variable — carries its scope in the query and is
    exempt. Fails closed on an unparseable file."""
    name, ad = "a scoped read puts its scope in the query", "AD-14"
    trees, unparseable = _scan_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            params = {a.arg for a in (
                *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
            if "scopes" not in params:
                continue
            for sub in ast.walk(node):
                # a read over a scoped content table — the entity/column in select(...) OR the table
                # in .select_from(...) (a `select(count).select_from(Failure)` count leaks too)
                if not isinstance(sub, ast.Call) or not isinstance(
                        sub.func, ast.Name | ast.Attribute):
                    continue
                fname = sub.func.id if isinstance(sub.func, ast.Name) else sub.func.attr
                if fname not in ("select", "select_from"):
                    continue
                if not _names_a_table(sub, _SCOPED_CONTENT_TABLES):
                    continue
                stmt = _enclosing_stmt(sub, parents)
                if stmt is not None and not _stmt_carries_scope(stmt, node):
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{sub.lineno} {node.name}(...) takes scopes but SELECTs a "
                        "scoped content table filtered by tenant alone — a fetch-then-post-filter; "
                        "the scope must be a join/pre-filter in the query, not a Python filter "
                        "over fetched rows (AD-13/AD-14)")
    return CheckResult(
        name, ad, True,
        f"every scopes-taking read carries its scope in the query ({len(trees)} files)")


# AD-12: "no identity bypasses the predicate." A corpus read (over ``Piece`` / ``Chunk``) must not
# take an admin/super-user flag — there is no whole-corpus super-user read. (The register's
# ``is_admin`` is a different, narrow FR-49 carve-out over ``Failure`` — matter-less entries — not a
# corpus read, so ``Failure`` is deliberately NOT in this set.)
_CORPUS_TABLES = frozenset({"Piece", "Chunk"})
_ADMIN_BYPASS_PARAMS = frozenset({
    "is_admin", "is_superuser", "superuser", "sudo", "bypass", "bypass_scope", "as_admin"})


def _reads_a_corpus_table(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """The function builds a read (select/query/select_from/join/get) over ``Piece`` / ``Chunk``."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and _is_query_builder(n) and _names_a_table(n, _CORPUS_TABLES):
            return True
    return False


def corpus_read_takes_no_admin_bypass(roots: Iterable[Path] | None = None) -> CheckResult:
    """No function that reads the *corpus* (``Piece`` / ``Chunk``) takes an admin/super-user bypass
    parameter (AD-12: no identity reads a whole *corpus* without a scope). The register's
    ``is_admin`` is a narrow FR-49 carve-out over ``Failure`` (not a corpus read), not flagged.
    Fails closed on an unparseable file."""
    name, ad = "a corpus read takes no admin bypass", "AD-12"
    trees, unparseable = _scan_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            params = {a.arg for a in (
                *node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
            bad = params & _ADMIN_BYPASS_PARAMS
            if bad and _reads_a_corpus_table(node):
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} {node.name}(...) reads the corpus (Piece/Chunk) "
                    f"and takes {sorted(bad)} — there is no super-user corpus read; scope is the "
                    "only authority (AD-12)")
    return CheckResult(
        name, ad, True, f"no corpus read takes an admin/super-user bypass ({len(trees)} files)")


def run() -> list[CheckResult]:
    """The single-read-path checks, for the harness to fan out over."""
    return [
        tenant_reads_have_one_entry_point(),
        scoped_read_puts_scope_in_the_query(),
        corpus_read_takes_no_admin_bypass(),
    ]
