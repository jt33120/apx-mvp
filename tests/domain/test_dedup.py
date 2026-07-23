"""The deterministic dedup core: conservative normalisation + faithful clustering.

The load-bearing property is recall: a false merge would hide a piece behind
another's verdict, so near-but-different text must NOT share a key.
"""

from __future__ import annotations

from apx.core.domain.dedup import cluster, normalize_text, text_key


def test_normalisation_collapses_only_formatting() -> None:
    # whitespace runs -> one space, trimmed; case folded
    assert normalize_text("  Le  Contrat\n\tsigné ") == "le contrat signé"
    # Unicode form: composed é and decomposed e+◌́ are the same document
    assert normalize_text("café") == normalize_text("café")


def test_normalisation_preserves_meaning_bearing_characters() -> None:
    # punctuation and digits are NOT stripped — they carry meaning in law
    assert normalize_text("Article 145, al. 2.") == "article 145, al. 2."
    # so a comma vs a space is a real difference, not a formatting one
    assert text_key("partie a, partie b") != text_key("partie a partie b")


def test_same_text_modulo_formatting_shares_a_key() -> None:
    assert text_key("Le contrat est signé.") == text_key("  le   CONTRAT est signé.  ")


def test_near_but_different_text_does_not_share_a_key() -> None:
    # one word changed -> a different document -> different key (recall-first: never merge)
    assert text_key("Le contrat est signé.") != text_key("Le contrat est résilié.")


def test_cluster_collapses_copies_and_keeps_singletons_distinct() -> None:
    report = cluster([("p1", "k"), ("p2", "k"), ("p3", "x")])
    assert report.submitted == 3
    assert report.distinct == 2      # {k, x}
    assert report.duplicates == 1    # one copy of k collapsed
    assert len(report.clusters) == 1   # only the multi-member cluster is listed
    (g,) = report.clusters
    assert g.size == 2 and g.members == ("p1", "p2")


def test_representative_is_the_smallest_id_regardless_of_order() -> None:
    report = cluster([("p9", "k"), ("p2", "k"), ("p5", "k")])
    (g,) = report.clusters
    assert g.representative == "p2"   # min id, stable
    assert g.members == ("p2", "p5", "p9")


def test_clustering_is_deterministic_under_reordering() -> None:
    items = [("p1", "k"), ("p2", "k"), ("p3", "x"), ("p4", "y"), ("p5", "y")]
    assert cluster(items) == cluster(list(reversed(items)))


def test_invariant_holds_and_empty_is_consistent() -> None:
    report = cluster([("p1", "k"), ("p2", "k"), ("p3", "x")])
    assert report.distinct + report.duplicates == report.submitted
    empty = cluster([])
    assert empty.submitted == 0 and empty.distinct == 0 and empty.clusters == ()
