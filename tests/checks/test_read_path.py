"""The single-read-path structural gates (Story 3.3, AD-14/AD-13):

- ``tenant_reads_have_one_entry_point`` — a tenant-content query is CONSTRUCTED only in the
  sanctioned read path (``core/app/read/`` + the store adapter's read modules); a surface
  hand-rolling a ``select(Piece)`` fails the build.
- ``scoped_read_puts_scope_in_the_query`` — a function taking ``scopes`` may not ``select()`` a
  scoped content table filtered by ``tenant`` alone (the ``register_all`` fetch-then-post-filter
  shape); a read naming ``matter`` / ``MatterScope`` / an id-equality is exempt.

Both pass the real tree, fire on a planted violation, and fail closed on an unparseable file."""

from __future__ import annotations

from pathlib import Path

from apx.checks.read_path import (
    corpus_read_takes_no_admin_bypass,
    scoped_read_puts_scope_in_the_query,
    tenant_reads_have_one_entry_point,
)


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


# ── tenant_reads_have_one_entry_point ────────────────────────────────────────────────────────
def test_one_entry_point_fires_on_a_surface_content_query(tmp_path: Path) -> None:
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Piece\n"
        "def route(tenant):\n"
        "    return session.scalars(select(Piece).where(Piece.tenant == tenant)).all()\n"
    )
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "surface", src)])
    assert not r.ok and "outside the read path" in r.detail


def test_one_entry_point_fires_on_select_from_and_join_forms(tmp_path: Path) -> None:
    for i, src in enumerate([
        "from sqlalchemy import select, func\n"
        "from apx.adapters.store_postgres.models import Failure\n"
        "def c(t):\n"
        "    return select(func.count()).select_from(Failure).where(Failure.tenant == t)\n",
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Chunk, MatterScope\n"
        "def j(t):\n"
        "    return select(Chunk).join(MatterScope, MatterScope.matter == Chunk.matter)\n",
    ]):
        r = tenant_reads_have_one_entry_point([_mod(tmp_path, f"form{i}", src)])
        assert not r.ok, f"should fire on form {i}"


def test_one_entry_point_fires_on_session_get_of_a_content_model(tmp_path: Path) -> None:
    # an identifier-only read (AD-14: no method takes an id without a tenant+scope)
    src = (
        "from apx.adapters.store_postgres.models import Piece\n"
        "def route(session, pid):\n"
        "    return session.get(Piece, pid)\n"
    )
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "getleak", src)])
    assert not r.ok


def test_one_entry_point_fires_on_raw_sql_over_a_content_table(tmp_path: Path) -> None:
    # AD-14 forbids SQL TEXT too — a surface hand-rolling raw SQL over a content table
    src = (
        "from sqlalchemy import text\n"
        "def route(session, tenant):\n"
        "    return session.execute(text('SELECT id FROM piece WHERE tenant=:t'))\n"
    )
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "rawsql", src)])
    assert not r.ok and "raw SQL" in r.detail


def test_one_entry_point_ignores_a_docstring_that_says_from_failure(tmp_path: Path) -> None:
    # the raw-SQL leg scans text()/execute() args, not prose — a docstring is not a hit
    src = (
        "def helper():\n"
        "    \"\"\"Recovered from failure; joins chunk positions in memory.\"\"\"\n"
        "    return 1\n"
    )
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "prose", src)])
    assert r.ok


def test_one_entry_point_passes_a_non_content_query(tmp_path: Path) -> None:
    # a User/config read is not a matter-scoped corpus read — out of this check's scope
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import User\n"
        "def whoami(uid):\n"
        "    return session.scalar(select(User).where(User.id == uid))\n"
    )
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "auth", src)])
    assert r.ok


def test_one_entry_point_passes_the_real_tree() -> None:
    r = tenant_reads_have_one_entry_point()
    assert r.ok, r.detail


def test_one_entry_point_fails_closed_on_unparseable(tmp_path: Path) -> None:
    r = tenant_reads_have_one_entry_point([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "failing closed" in r.detail


# ── scoped_read_puts_scope_in_the_query ──────────────────────────────────────────────────────
def test_scope_in_query_fires_on_a_tenant_only_scoped_read(tmp_path: Path) -> None:
    # the register_all shape: takes scopes, SELECTs Failure filtered by tenant alone, then a Python
    # post-filter would drop out-of-scope rows — the leak vector AD-14 forbids.
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Failure, MatterScope\n"
        "def register_all(tenant, scopes, *, is_admin):\n"
        "    held = set(session.scalars(select(MatterScope.matter).where(\n"
        "        MatterScope.tenant == tenant, MatterScope.scope.in_(scopes))))\n"
        "    rows = session.scalars(select(Failure).where(Failure.tenant == tenant)).all()\n"
        "    return [f for f in rows if f.matter in held]\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "bad", src)])
    assert not r.ok and "fetch-then-post-filter" in r.detail


def test_scope_in_query_exempts_a_matter_scoped_read(tmp_path: Path) -> None:
    # the scope IS in the query (Failure.matter in a matter_scope sub-query) — the fixed shape
    src = (
        "from sqlalchemy import select, or_\n"
        "from apx.adapters.store_postgres.models import Failure, MatterScope\n"
        "def register_all(tenant, scopes, *, is_admin):\n"
        "    held = select(MatterScope.matter).where(\n"
        "        MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes)))\n"
        "    return session.scalars(select(Failure).where(\n"
        "        Failure.tenant == tenant, Failure.matter.in_(held))).all()\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "ok", src)])
    assert r.ok, r.detail


def test_scope_in_query_fires_when_the_scope_column_is_only_SELECTED_not_filtered(
        tmp_path: Path) -> None:
    # a tenant-wide enumeration that SELECTs Piece.id / Piece.matter but filters tenant alone is a
    # leak — the exemption must key on the .where() predicate, not the selected columns.
    for i, col in enumerate(["Piece.id", "Piece.matter"]):
        src = (
            "from sqlalchemy import select\n"
            "from apx.adapters.store_postgres.models import Piece\n"
            "def enumerate_all(tenant, scopes):\n"
            f"    return session.scalars(select({col}).where(Piece.tenant == tenant)).all()\n"
        )
        r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, f"enum{i}", src)])
        assert not r.ok, f"should fire when only selecting {col}"


def test_scope_in_query_exempts_a_matter_scope_join_with_conds_in_a_variable(
        tmp_path: Path) -> None:
    # the `search` shape: scope applied via .join(MatterScope, ...) with predicates in a conds list
    src = (
        "from sqlalchemy import select, func\n"
        "from apx.adapters.store_postgres.models import Piece, MatterScope\n"
        "def search(tenant, scopes, query):\n"
        "    on = (MatterScope.matter == Piece.matter) & (MatterScope.tenant == Piece.tenant)\n"
        "    conds = [Piece.tenant == tenant, MatterScope.scope.in_(scopes)]\n"
        "    return session.execute(\n"
        "        select(Piece.matter).join(MatterScope, on).where(*conds)).all()\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "searchshape", src)])
    assert r.ok, r.detail


def test_scope_in_query_fires_on_a_matter_scope_join_without_a_scope_filter(tmp_path: Path) -> None:
    # M3: joining matter_scope is NOT a scope filter on its own — this returns every matter's pieces
    # (the inner join on matter matches all, no MatterScope.scope predicate anywhere).
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Piece, MatterScope\n"
        "def leak(tenant, scopes):\n"
        "    return session.scalars(select(Piece).join(\n"
        "        MatterScope, MatterScope.matter == Piece.matter).where(Piece.tenant == tenant)"
        ").all()\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "joinnoscope", src)])
    assert not r.ok


def test_scope_in_query_fires_on_a_select_from_count_filtered_tenant_only(tmp_path: Path) -> None:
    # a scoped count leaks metadata too: count over Failure via select_from, filtered tenant-only
    src = (
        "from sqlalchemy import select, func\n"
        "from apx.adapters.store_postgres.models import Failure\n"
        "def count_all(tenant, scopes):\n"
        "    return session.scalar(\n"
        "        select(func.count()).select_from(Failure).where(Failure.tenant == tenant))\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "countleak", src)])
    assert not r.ok


def test_scope_in_query_exempts_an_id_guard_then_read(tmp_path: Path) -> None:
    # a single-row read by id (resolve_chunk's guard-then-read) is not a tenant-wide fetch
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Chunk\n"
        "def resolve_chunk(chunk_id, tenant, scopes):\n"
        "    return session.scalar(select(Chunk).where(\n"
        "        Chunk.chunk_id == chunk_id, Chunk.tenant == tenant))\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "byid", src)])
    assert r.ok, r.detail


def test_scope_in_query_ignores_a_read_that_takes_no_scopes(tmp_path: Path) -> None:
    # a content-free aggregate under the maintenance principal (no scopes) is out of scope
    src = (
        "from sqlalchemy import select, func\n"
        "from apx.adapters.store_postgres.models import Piece\n"
        "def projection_snapshot(tenant):\n"
        "    return session.scalar(select(func.count()).select_from(Piece).where(\n"
        "        Piece.tenant == tenant))\n"
    )
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "agg", src)])
    assert r.ok, r.detail


def test_scope_in_query_passes_the_real_tree() -> None:
    r = scoped_read_puts_scope_in_the_query()
    assert r.ok, r.detail


def test_scope_in_query_fails_closed_on_unparseable(tmp_path: Path) -> None:
    r = scoped_read_puts_scope_in_the_query([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "failing closed" in r.detail


# ── corpus_read_takes_no_admin_bypass (AD-12) ────────────────────────────────────────────────
def test_no_admin_bypass_fires_on_a_corpus_read_taking_is_admin(tmp_path: Path) -> None:
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Piece\n"
        "def read_corpus(tenant, scopes, *, is_admin=False) -> list:\n"
        "    return session.scalars(select(Piece).where(Piece.tenant == tenant)).all()\n"
    )
    r = corpus_read_takes_no_admin_bypass([_mod(tmp_path, "sudo", src)])
    assert not r.ok and "super-user" in r.detail


def test_no_admin_bypass_allows_is_admin_on_a_register_read(tmp_path: Path) -> None:
    # the failure register's is_admin is a narrow FR-49 carve-out over Failure, NOT a corpus read
    src = (
        "from sqlalchemy import select\n"
        "from apx.adapters.store_postgres.models import Failure\n"
        "def register_all(tenant, scopes, *, is_admin):\n"
        "    return session.scalars(select(Failure).where(Failure.tenant == tenant)).all()\n"
    )
    r = corpus_read_takes_no_admin_bypass([_mod(tmp_path, "reg", src)])
    assert r.ok


def test_no_admin_bypass_passes_the_real_tree() -> None:
    r = corpus_read_takes_no_admin_bypass()
    assert r.ok, r.detail


def test_no_admin_bypass_fails_closed_on_unparseable(tmp_path: Path) -> None:
    r = corpus_read_takes_no_admin_bypass([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "failing closed" in r.detail
