"""The search snippet: centred on the match, whitespace collapsed, elided at cuts."""

from __future__ import annotations

from apx.core.domain.search import snippet


def test_snippet_centres_on_the_first_match() -> None:
    text = "avant " * 20 + "le mot CLEF ici" + " apres" * 20
    s = snippet(text, "clef", width=20)
    assert "clef" in s.lower()
    assert s.startswith("…") and s.endswith("…")  # elided on both sides


def test_snippet_collapses_whitespace() -> None:
    s = snippet("contrat\n\n  de   bail", "de", width=30)
    assert "  " not in s and "\n" not in s


def test_snippet_no_match_returns_the_head() -> None:
    assert snippet("un texte quelconque sans le terme", "absent", width=10).startswith("un texte")


def test_snippet_empty_term_returns_the_head() -> None:
    assert snippet("bonjour le monde", "   ", width=5).startswith("bonjour")
