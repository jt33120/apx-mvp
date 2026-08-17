"""The confined walk and the ingestion root (Story 7.1, FR-1 / C1).

FR-1's traversal clause had three obligations and none was built; `ErrorClass.
TRAVERSAL_OUT_OF_SCOPE` sat in the taxonomy with no producer. These tests hold the boundary that
closes it, and they assert the FAILING half — a link out of the subtree is *not* ingested — because
the passing half (ordinary files are ingested) was already true of the defective code.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apx.core.domain.traversal import (
    OutsideRoot,
    RootNotConfigured,
    RootOverlapsDataVolume,
    ingest_root,
    resolve_within,
    walk_confined,
)


def _tree(base: Path) -> tuple[Path, Path]:
    """A submitted folder beside a directory it must never reach."""
    inside, outside = base / "submitted", base / "elsewhere"
    (inside / "sub").mkdir(parents=True)
    outside.mkdir()
    (inside / "ok.txt").write_text("dedans", encoding="utf-8")
    (inside / "sub" / "deep.txt").write_text("profond", encoding="utf-8")
    (outside / "secret.txt").write_text("le dossier d'un autre", encoding="utf-8")
    return inside, outside


# ── the walk ──────────────────────────────────────────────────────────────────────────────────

def test_a_file_link_pointing_out_of_the_subtree_is_not_ingested(tmp_path: Path) -> None:
    # The defect verified by hand before this story: rglob + is_file() FOLLOWS a file symlink, so
    # the target was walked, extracted and persisted under the importing matter's RBAC scope.
    inside, outside = _tree(tmp_path)
    os.symlink(outside / "secret.txt", inside / "piege.txt")

    walk = walk_confined(inside)

    assert sorted(f.relative for f in walk.files) == ["ok.txt", "sub/deep.txt"]
    assert [o.relative for o in walk.out_of_scope] == ["piege.txt"]
    assert walk.out_of_scope[0].is_directory is False
    assert "secret.txt" in walk.out_of_scope[0].target


def test_a_directory_link_pointing_out_of_the_subtree_is_recorded_not_merely_skipped(
    tmp_path: Path,
) -> None:
    # rglob already declines to descend into it, so nothing was ingested — but nothing was SAID
    # either, and FR-1 requires the link to be recorded. Silence is what this asserts against.
    inside, outside = _tree(tmp_path)
    os.symlink(outside, inside / "ailleurs")

    walk = walk_confined(inside)

    assert [o.relative for o in walk.out_of_scope] == ["ailleurs"]
    assert walk.out_of_scope[0].is_directory is True
    assert all("secret" not in f.relative for f in walk.files)


def test_a_link_pointing_inside_the_subtree_is_ordinary(tmp_path: Path) -> None:
    # The rule is about leaving the subtree, not about symlinks. A firm that keeps a link to its own
    # material inside the folder it submitted has done nothing wrong.
    inside, _ = _tree(tmp_path)
    os.symlink(inside / "ok.txt", inside / "alias.txt")

    walk = walk_confined(inside)

    assert walk.out_of_scope == ()
    assert "alias.txt" in {f.relative for f in walk.files}


def test_a_cycle_terminates_rather_than_hanging(tmp_path: Path) -> None:
    # Python 3.13's Path.rglob defaults to recurse_symlinks=False, so this holds today by the
    # STANDARD LIBRARY and not by our code — exactly the kind of property that changes silently
    # under an upgrade or a rewrite to os.walk. Pinned here so the build says so if it stops.
    inside, _ = _tree(tmp_path)
    os.symlink(inside, inside / "boucle")

    walk = walk_confined(inside)  # must return, not hang

    assert sorted(f.relative for f in walk.files) == ["ok.txt", "sub/deep.txt"]


def test_a_broken_link_pointing_out_of_the_subtree_is_still_recorded(tmp_path: Path) -> None:
    """A dangling link whose *declared* target is outside is reported, and that is deliberate.

    ``Path.resolve()`` does not raise on a broken link — it returns the non-existent target — so the
    comparison runs on where the link POINTS rather than on what it currently reaches. Keeping it is
    the conservative reading of FR-1: the clause is about a link pointing outside the subtree, and a
    link that is dangling today is one restored backup away from resolving. Special-casing it would
    also hand anyone a shape that points outside without being recorded.
    """
    inside, _ = _tree(tmp_path)
    os.symlink(tmp_path / "nexistepas.txt", inside / "casse.txt")

    walk = walk_confined(inside)

    assert [o.relative for o in walk.out_of_scope] == ["casse.txt"]
    assert "casse.txt" not in {f.relative for f in walk.files}


def test_a_broken_link_pointing_inside_the_subtree_is_not_a_boundary_finding(
    tmp_path: Path,
) -> None:
    # Unreadable material is the extraction path's business and has its own register classes.
    # Calling it a boundary breach would accuse the firm of the wrong thing.
    inside, _ = _tree(tmp_path)
    os.symlink(inside / "jamais-cree.txt", inside / "casse.txt")

    walk = walk_confined(inside)

    assert walk.out_of_scope == ()
    assert "casse.txt" not in {f.relative for f in walk.files}


# ── the root ──────────────────────────────────────────────────────────────────────────────────

def test_a_sibling_sharing_a_name_prefix_is_outside_the_root(tmp_path: Path) -> None:
    # The recurring wrong-referent defect in filesystem costume: str.startswith admits
    # /data/ingest-evil when the root is /data/ingest. Both sides are compared as PATHS.
    root, evil = tmp_path / "ingest", tmp_path / "ingest-evil"
    root.mkdir()
    evil.mkdir()

    with pytest.raises(OutsideRoot):
        resolve_within(root, evil)


def test_the_root_itself_and_its_descendants_are_inside(tmp_path: Path) -> None:
    root = tmp_path / "ingest"
    (root / "dossier").mkdir(parents=True)

    assert resolve_within(root, root) == root.resolve()
    assert resolve_within(root, root / "dossier") == (root / "dossier").resolve()


def test_a_relative_escape_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "ingest"
    root.mkdir()
    (tmp_path / "voisin").mkdir()

    with pytest.raises(OutsideRoot):
        resolve_within(root, root / ".." / "voisin")


def test_the_refusal_names_no_path(tmp_path: Path) -> None:
    # One message for "outside the root" and for "absent", so a caller cannot map the server's
    # filesystem one request at a time (FR-14's non-disclosure discipline).
    root = tmp_path / "ingest"
    root.mkdir()

    with pytest.raises(OutsideRoot) as raised:
        resolve_within(root, tmp_path / "secret-directory-name")

    assert "secret-directory-name" not in str(raised.value)


def test_an_unset_root_refuses_every_folder(tmp_path: Path) -> None:
    # Fail closed, as the encryption key and the head journal do at start-up. The alternative —
    # falling back to "anywhere" — IS the defect this story closes.
    with pytest.raises(RootNotConfigured):
        ingest_root({})
    with pytest.raises(RootNotConfigured):
        ingest_root({"APX_INGEST_ROOT": "   "})


def test_a_root_that_is_not_a_directory_refuses(tmp_path: Path) -> None:
    absent = tmp_path / "nexistepas"

    with pytest.raises(RootNotConfigured):
        ingest_root({"APX_INGEST_ROOT": str(absent)})


@pytest.mark.parametrize("relation", ["equal", "root-above", "root-inside"])
def test_a_root_that_can_reach_the_originals_refuses(tmp_path: Path, relation: str) -> None:
    volume = tmp_path / "data"
    originals = volume / "originals"
    originals.mkdir(parents=True)
    root = {"equal": originals, "root-above": volume,
            "root-inside": originals / "t"}[relation]
    root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(RootOverlapsDataVolume):
        ingest_root({"APX_INGEST_ROOT": str(root), "APX_DATA_PATH": str(volume)})


def test_a_root_that_can_reach_the_upload_spool_refuses(tmp_path: Path) -> None:
    volume = tmp_path / "data"
    (volume / "spool").mkdir(parents=True)

    with pytest.raises(RootOverlapsDataVolume):
        ingest_root({"APX_INGEST_ROOT": str(volume), "APX_DATA_PATH": str(volume)})


def test_a_corpus_beside_the_sensitive_directories_is_permitted(tmp_path: Path) -> None:
    # The rule is about the originals and the spool, not about the volume. Refusing an ordinary
    # on-premise layout would push a deployment toward turning the confinement off entirely.
    volume = tmp_path / "data"
    (volume / "originals").mkdir(parents=True)
    (volume / "spool").mkdir()
    corpus = volume / "corpus"
    corpus.mkdir()

    assert ingest_root({"APX_INGEST_ROOT": str(corpus),
                        "APX_DATA_PATH": str(volume)}) == corpus.resolve()
