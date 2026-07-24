"""The encryption structural checks are live, not decorative (story 1.7, AD-31/AD-33). Each
must hold on the real tree AND fire on a deliberately violating fixture — a plaintext sensitive
column (explicit OR inferred type), an encrypted text index, a warn-only gate, a gate missing a
layer — and fail closed on unparseable input. The gate check additionally runs the REAL gate.
A guard that cannot fail is worthless.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.checks import encryption

FIX = Path(__file__).resolve().parents[1] / "_fixtures" / "encryption_violations"


def test_both_encryption_checks_pass_on_the_real_tree() -> None:
    for result in encryption.run():
        assert result.ok, f"{result.name} should hold on the real tree:\n{result.detail}"


def test_fires_on_a_plaintext_sensitive_column() -> None:
    result = encryption.sensitive_columns_are_encrypted([FIX / "plaintext_sensitive"])
    assert not result.ok and "provenance_path" in result.detail


def test_fires_on_an_inferred_type_sensitive_column() -> None:
    # the bypass a denylist missed: a sensitive column with NO positional type still fails
    result = encryption.sensitive_columns_are_encrypted([FIX / "inferred_type"])
    assert not result.ok and "provenance_path" in result.detail


def test_fires_when_the_named_text_index_is_encrypted() -> None:
    # encrypting full_text would break exhaustive search (FR-13) — the check forbids it
    result = encryption.sensitive_columns_are_encrypted([FIX / "encrypted_index"])
    assert not result.ok and "full_text" in result.detail


def test_gate_check_fires_on_a_warn_only_gate() -> None:
    result = encryption.startup_gate_is_fail_closed([FIX / "warn_only"])
    assert not result.ok and "raise" in result.detail.lower()


def test_gate_check_fires_on_a_missing_volume_layer() -> None:
    result = encryption.startup_gate_is_fail_closed([FIX / "one_layer"])
    assert not result.ok and "volume" in result.detail.lower()


def test_gate_check_fires_when_no_gate_exists(tmp_path: Path) -> None:
    (tmp_path / "nothing.py").write_text("x = 1\n")
    result = encryption.startup_gate_is_fail_closed([tmp_path])
    assert not result.ok and "no startup_gate" in result.detail.lower()


def test_the_behavioural_leg_catches_a_gamed_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    # a warn-and-continue gate that never refuses is caught by executing it, even though it
    # would pass an AST "does it contain a raise" sniff — this is the ungameable leg.
    import apx.api.startup as startup_mod

    def _permissive(env: object = None) -> None:
        return None  # accepts everything — the exact downgrade the check must catch

    monkeypatch.setattr(startup_mod, "startup_gate", _permissive)
    problem = encryption._gate_behaves_fail_closed()
    assert problem is not None and "did NOT refuse" in problem


def test_checks_fail_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")  # a syntax error
    for check in (
        encryption.sensitive_columns_are_encrypted,
        encryption.startup_gate_is_fail_closed,
    ):
        result = check([tmp_path])
        assert not result.ok and "parse" in result.detail.lower()
