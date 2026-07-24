"""The scope-administration structural check is live (story 1.6, FR-49): it holds on the real
tree AND fires on a scope mutator that skips the audit, and fails closed on an unparseable file.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks import scope_admin


def test_check_passes_on_the_real_tree() -> None:
    result = scope_admin.scope_mutations_are_audited()
    assert result.ok, f"every scope mutator should audit:\n{result.detail}"


def test_fires_on_a_scope_mutator_that_skips_the_audit(tmp_path: Path) -> None:
    (tmp_path / "bad_store.py").write_text(
        "def grant_scope(self, tenant, actor, user_id, scope):\n"
        "    self.session.merge(UserScope(user_id=user_id, scope=scope))\n"  # no _append_audit
    )
    result = scope_admin.scope_mutations_are_audited([tmp_path])
    assert not result.ok and "grant_scope" in result.detail


def test_passes_when_the_mutator_audits(tmp_path: Path) -> None:
    (tmp_path / "ok_store.py").write_text(
        "def rescope_matter(self, tenant, actor, matter, new_scope):\n"
        "    self._append_audit(session, tenant, matter, actor, 'rescope_matter', 'd', now)\n"
    )
    assert scope_admin.scope_mutations_are_audited([tmp_path]).ok


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = scope_admin.scope_mutations_are_audited([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()
