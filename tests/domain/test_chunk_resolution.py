"""Chunk resolution + the exact-string-containment check (Story 2.9, FR-11). Pure domain, no DB.

A chunk resolves to its exact source passage by re-chunking the stored full text and taking its
position; a resolution that fails at read time is surfaced as a typed ``FailedResolution`` and NEVER
as a passage — the court-facing guarantee that an extract in an export cannot silently point at
nothing. This covers every enumerated failure cause.
"""

from __future__ import annotations

import hashlib

from apx.core.domain.chunking import (
    CONFIG_SUPERSEDED,
    CONTAINMENT_FAILED,
    POSITION_OUT_OF_RANGE,
    TEXT_CHANGED,
    ChunkingConfig,
    FailedResolution,
    ResolvedPassage,
    chunk,
    resolve_passage,
)

_TEXT = (
    "Le contrat de bail est nul. La cour d'appel le confirme aujourd'hui meme. "
    "L'article premier du code civil s'applique ici pleinement au present litige."
)
_CFG = ChunkingConfig(target_chars=60)
_IDENTITY = hashlib.sha256(_TEXT.encode()).hexdigest()


def _resolve(position: int, **over: object) -> ResolvedPassage | FailedResolution:
    kw: dict = dict(
        full_text=_TEXT, piece_text_version="tv", piece_text_identity=_IDENTITY,
        chunk_full_text_version="tv", chunk_position=position,
        chunk_config_version=_CFG.version, config=_CFG)
    kw.update(over)
    return resolve_passage(**kw)  # type: ignore[arg-type]


def test_every_chunk_resolves_to_its_exact_source_span() -> None:
    passages = chunk(_TEXT, _CFG)
    assert len(passages) > 1
    for i, p in enumerate(passages):
        r = _resolve(i)
        assert isinstance(r, ResolvedPassage)
        assert (r.text, r.start, r.end) == (p.text, p.start, p.end)
        assert _TEXT[r.start:r.end] == r.text  # provenance to the character (containment holds)


def test_text_changed_under_re_extraction_is_a_failed_resolution() -> None:
    assert _resolve(0, chunk_full_text_version="an-older-version") == FailedResolution(TEXT_CHANGED)


def test_text_altered_in_place_fails_the_identity_check() -> None:
    # same version string, but the stored text no longer hashes to the recorded identity
    assert _resolve(0, piece_text_identity="deadbeef") == FailedResolution(TEXT_CHANGED)


def test_a_superseded_chunking_config_is_a_failed_resolution() -> None:
    assert _resolve(0, chunk_config_version="a-superseded-generation") == \
        FailedResolution(CONFIG_SUPERSEDED)


def test_a_position_past_the_end_is_a_failed_resolution() -> None:
    assert _resolve(9999) == FailedResolution(POSITION_OUT_OF_RANGE)


def test_a_stored_extract_no_longer_contained_fails_containment() -> None:
    assert _resolve(0, expected_text="ceci ne figure pas dans le texte source") == \
        FailedResolution(CONTAINMENT_FAILED)


def test_a_still_contained_stored_extract_resolves() -> None:
    assert isinstance(_resolve(0, expected_text="Le contrat de bail"), ResolvedPassage)


def test_containment_is_anchored_to_the_resolved_passage_not_the_whole_text() -> None:
    # FR-11 "at the moment it is shown": an extract that lives in a DIFFERENT passage must NOT pass
    # containment for this position (review MED-2 — checking the whole document under-detects).
    passages = chunk(_TEXT, _CFG)
    assert len(passages) > 1
    frag = passages[0].text.strip()[:12]  # a fragment of passage 0 …
    assert frag in passages[0].text and frag not in passages[-1].text  # … not in the last passage
    assert _resolve(len(passages) - 1, expected_text=frag) == FailedResolution(CONTAINMENT_FAILED)
    assert isinstance(_resolve(0, expected_text=frag), ResolvedPassage)  # but it resolves at pos 0
