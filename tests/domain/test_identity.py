"""Deterministic piece identity (Story 2.5 AC1; FR-4, AD-8/AD-40/AD-12).

A pièce's identifier is a deterministic function of (content, matter) — never of its provenance
path, never a counter, stable across runs, processes and installations. The v1 defect was ids
restarted from 1 so a second upload overwrote the first; these tests pin the shape that makes that
unrepresentable.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from apx.core.domain.identity import content_hash, piece_id


def test_piece_id_is_a_pure_function_of_tenant_matter_content() -> None:
    a = piece_id("t", content_hash(b"les memes octets"), "m")
    b = piece_id("t", content_hash(b"les memes octets"), "m")
    assert a == b  # same inputs → same id, every time (never a counter, never random)


def test_provenance_path_is_not_part_of_identity() -> None:
    # the SAME bytes at two different paths are ONE pièce (path is an attribute, not identity).
    ch = content_hash(b"contrat de bail")
    assert piece_id("t", ch, "m") == piece_id("t", ch, "m")
    # nothing in the identity signature accepts a path — it is (tenant, content_hash, matter)
    assert "path" not in piece_id.__code__.co_varnames


def test_matter_is_inside_identity_so_two_matters_are_two_pieces() -> None:
    ch = content_hash(b"le meme fichier")
    assert piece_id("t", ch, "m-a") != piece_id("t", ch, "m-b")  # no cross-matter dedup (AD-8)


def test_tenant_is_inside_identity_so_two_tenants_never_collide() -> None:
    # a matter is tenant-local (AD-12): two firms naming a matter "dupont" with the same file are
    # two distinct pièces — one firm's ingest can never seize or overwrite the other's.
    ch = content_hash(b"piece")
    assert piece_id("tenant-a", ch, "dupont") != piece_id("tenant-b", ch, "dupont")


def test_content_change_yields_a_new_id() -> None:
    # changed content → a new content_hash → a NEW pièce (never overwriting the old in place).
    assert piece_id("t", content_hash(b"v1"), "m") != piece_id("t", content_hash(b"v2"), "m")


def test_identity_rejects_missing_components() -> None:
    ch = content_hash(b"x")
    for bad in (("", ch, "m"), ("t", "", "m"), ("t", ch, "")):
        with pytest.raises(ValueError):
            piece_id(*bad)


def test_identity_is_stable_across_a_fresh_process() -> None:
    # "stable across runs, processes and installations" — recompute the same id in a brand-new
    # Python process and assert it matches (no in-process state, no counter, no seed).
    here = piece_id("t", content_hash(b"cross-process"), "m")
    code = (
        "from apx.core.domain.identity import content_hash, piece_id;"
        "print(piece_id('t', content_hash(b'cross-process'), 'm'))"
    )
    other = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert other == here
