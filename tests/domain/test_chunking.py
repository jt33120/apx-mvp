"""The deterministic, French-legal-aware chunker (Story 2.9, FR-11). Pure domain, no DB.

Provenance is BY RESOLUTION (AD-9 stores no offsets): the chunker is the deterministic function a
chunk's ``(position, chunking_config_version)`` resolves through, so its determinism and its exact
spans ARE the provenance guarantee. Every passage is an exact slice ``full_text[start:end]`` — the
containment check (FR-11) is then trivially true for a freshly-chunked passage, and only a changed
source can make it fail.
"""

from __future__ import annotations

from apx.core.domain.chunking import ChunkingConfig, Passage, chunk

_CFG = ChunkingConfig(target_chars=120)


def _tiles(text: str, passages: list[Passage]) -> None:
    """A chunking is a contiguous partition of ``[0, len(text))`` — every char accounted for, in
    order, no gaps and no overlap — and every passage's text is an EXACT slice (containment)."""
    assert passages[0].start == 0
    assert passages[-1].end == len(text)
    for a, b in zip(passages, passages[1:], strict=False):  # intentionally offset by one
        assert a.end == b.start
    for p in passages:
        assert p.text == text[p.start:p.end]  # provenance to the character


def test_chunking_is_deterministic_and_multi_passage() -> None:
    text = "Le contrat est nul. " * 30
    a = chunk(text, _CFG)
    b = chunk(text, _CFG)
    assert a == b  # byte-identical passages + spans (frozen-dataclass equality), across runs
    assert len(a) > 1  # a long text really splits into several passages (AC2)


def test_every_passage_is_an_exact_slice_and_they_tile_the_text() -> None:
    text = "Article premier du contrat. " * 20
    _tiles(text, chunk(text, _CFG))


def test_a_boundary_never_falls_inside_a_french_legal_citation() -> None:
    # the exact forms the v1 sentence splitter broke mid-token (AC8)
    citations = ["art. L. 1235-3", "n° 21-12.345", "Cass. soc.", "M. Dupont"]
    text = (
        "La cour statue aujourd'hui. Vu l'art. L. 1235-3 du code du travail applicable ici. "
        "L'arret n° 21-12.345 le confirme pleinement. Voir Cass. soc. sur ce point precis. "
        "M. Dupont a signe le document. Le litige est desormais clos."
    )
    passages = chunk(text, ChunkingConfig(target_chars=60))
    _tiles(text, passages)
    for c in citations:  # each citation lies wholly within ONE passage — never straddling a cut
        assert any(c in p.text for p in passages), f"{c!r} was split across a boundary"


def test_empty_text_is_no_passages() -> None:
    assert chunk("", _CFG) == []


def test_a_single_short_text_is_one_whole_passage() -> None:
    passages = chunk("Un seul paragraphe court.", _CFG)
    assert passages == [Passage(text="Un seul paragraphe court.", start=0, end=25)]


def test_the_config_version_is_derived_and_distinguishes_configs() -> None:
    assert ChunkingConfig(target_chars=1200).version == ChunkingConfig(target_chars=1200).version
    assert ChunkingConfig(target_chars=1200).version != ChunkingConfig(target_chars=800).version
    v = ChunkingConfig(target_chars=1200).version  # stable, short, and not a high-entropy secret
    assert isinstance(v, str) and 0 < len(v) < 24
