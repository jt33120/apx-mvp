"""Continuity, read from the document alone (Story 5.9, FR-53 / AD-35 / AD-43).

Everything Stories 5.5–5.8 built answers *was any of this changed?* Nothing answered *is this all of
it?* — and the second question cannot be answered from the entries at any length, because a
truncation to an earlier consistent point recomputes perfectly.

Pure core throughout: no store, no clock, no I/O. That is not a convenience, it is the property
under test — a *bâtonnier* holding an exported document and this module must reach the same verdict
the producing system printed on it, and be able to contradict it.
"""

from __future__ import annotations

from dataclasses import replace

from apx.core.domain import audit
from apx.core.domain.inventory import Inventory
from apx.core.domain.matter_record import (
    ChainEntryLine,
    ChainVerdictLine,
    Cover,
    Tier,
    WitnessLine,
    assemble,
    read_continuity,
)

TENANT, MATTER, WALL = "cabinet", "affaire-a", "mur-a"
_EMPTY = Inventory(
    submitted_pieces=0, in_corpus=0, open_register_entries=0, overridden_register_entries=0,
    excluded_as_noise=0, retired=0, unknown_cardinality_entries=0)


def _chain(scope: str, verbs: list[str], anchor: str = "") -> list[audit.VerifiableEntry]:
    """A real chain: each link computed by the shipped recipe over the previous value."""
    rows: list[audit.VerifiableEntry] = []
    prev = anchor
    for seq, verb in enumerate(verbs, start=1):
        row = audit.VerifiableEntry(
            tenant=TENANT, chain_scope=scope, seq=seq, matter=scope or MATTER,
            actor="Me Dupont", action=verb, detail=f"d{seq}",
            timestamp=f"2026-08-13T10:0{seq}:00.000000", chain="",
            content_version=audit.CONTENT_V2, app_version="0.1.0", schema_version="slice-a")
        prev = audit.chain_value(prev, audit.chained_content(
            version=row.content_version, seq=row.seq, tenant=row.tenant,
            chain_scope=row.chain_scope, matter=row.matter, actor=row.actor, action=row.action,
            detail=row.detail, timestamp=row.timestamp, app_version=row.app_version or "",
            schema_version=row.schema_version or ""))
        rows.append(replace(row, chain=prev))
    return rows


_VERBS = [audit.ACT_INGEST, audit.ACT_PIECE_LABELLED, audit.ACT_LINE_PLACED]


def _lines(entries: list[audit.VerifiableEntry]) -> tuple[ChainEntryLine, ...]:
    return tuple(
        ChainEntryLine(
            chain_scope=e.chain_scope, seq=e.seq, at=e.timestamp, actor=e.actor, action=e.action,
            detail=e.detail, chain=e.chain, content_version=e.content_version,
            app_version=e.app_version or "", schema_version=e.schema_version or "",
            matter=e.matter)
        for e in entries)


def _document(
    entries: list[audit.VerifiableEntry],
    *,
    witness: WitnessLine | None = None,
    anchor: str | None = "",
    tier: Tier = Tier.FULL,
    printed_verified: bool = True,
    extra: tuple[ChainVerdictLine, ...] = (),
    extra_entries: tuple[ChainEntryLine, ...] = (),
):  # noqa: ANN202
    line = ChainVerdictLine(
        chain_scope=MATTER, label_fr=audit.chain_label_fr(MATTER), entries=len(entries),
        verified=printed_verified, anchor=anchor, witness=witness,
        # Deliberately claimed by the CALLER, and deliberately wrong: ``assemble`` must derive it.
        recomputable_from_this_document=True)
    return assemble(
        cover=Cover(
            matter=MATTER, tenant=TENANT, scope=WALL, tier=tier, produced_by="Me Dupont",
            produced_at="2026-08-13T12:00:00.000000", chains=(line, *extra)),
        denominator=_EMPTY,
        trail=_lines(entries) + extra_entries)


# ── the verdict names WHICH failure (AC-3) ────────────────────────────────────────────────────

def _verdict(rows: list[audit.VerifiableEntry]) -> audit.ChainVerdict:
    (only,) = audit.verify_chains(rows, {MATTER: ""})
    return only


def test_a_clean_chain_names_no_cause() -> None:
    clean = _verdict(_chain(MATTER, _VERBS))
    assert clean.verified and clean.cause is None and clean.cause_fr is None


def test_a_missing_entry_is_a_gap_a_rewrite_is_a_link_an_unreadable_field_is_its_own() -> None:
    """Three findings, three letters to write. Collapsing them into one boolean and one integer —
    which is what the verdict did until this story — leaves a *bâtonnier* told *rupture au n° 2*
    unable to say whether an act was removed, whether one was rewritten, or whether the encryption
    key is simply wrong."""
    rows = _chain(MATTER, _VERBS)
    gapped = _verdict([rows[0], rows[2]])
    assert gapped.cause == audit.CAUSE_GAP and gapped.broken_at == 3
    rewritten = _verdict([rows[0], replace(rows[1], detail="corrigé après coup"), rows[2]])
    assert rewritten.cause == audit.CAUSE_LINK and rewritten.broken_at == 2
    unreadable = _verdict([rows[0], replace(rows[1], actor=None), rows[2]])
    assert unreadable.cause == audit.CAUSE_UNREADABLE and unreadable.broken_at == 2
    # each says something different, in the lawyer's language
    said = {v.cause_fr for v in (gapped, rewritten, unreadable)}
    assert len(said) == 3 and all(said)


# ── the witness: is this ALL of it? (AC-7, AC-8) ───────────────────────────────────────────────

def test_a_record_that_ends_where_the_witness_saw_it_end_is_current() -> None:
    rows = _chain(MATTER, _VERBS)
    head = audit.HeadWitness(chain_scope=MATTER, seq=3, chain=rows[2].chain)
    comparison = audit.compare_to_witness(rows, head)
    assert comparison.state == audit.WITNESS_CURRENT and comparison.complete
    assert comparison.missing == 0 and comparison.unwitnessed == 0


def test_a_tail_truncation_recomputes_perfectly_and_only_the_witness_sees_it() -> None:
    """The single fact this story exists for. The cut chain passes every check the record can run on
    itself — that is not a weakness of the verifier, it is the shape of the problem."""
    rows = _chain(MATTER, _VERBS)
    head = audit.HeadWitness(chain_scope=MATTER, seq=3, chain=rows[2].chain)
    cut = rows[:1]
    assert _verdict(cut).verified, "the cut chain must recompute — otherwise the point is moot"
    comparison = audit.compare_to_witness(cut, head)
    assert comparison.state == audit.WITNESS_TRUNCATED
    assert comparison.missing == 2 and not comparison.complete
    assert "2 actes manquants" in audit.witness_sentence_fr(comparison)


def test_a_record_ahead_of_its_witness_is_unwitnessed_never_clean() -> None:
    """The journal is written after the commit, so the last acts of a live system routinely have no
    outside witness. That is not a fault — and it is not *fine* either: those are exactly the acts a
    later truncation could remove without leaving a trace."""
    rows = _chain(MATTER, _VERBS)
    head = audit.HeadWitness(chain_scope=MATTER, seq=1, chain=rows[0].chain)
    comparison = audit.compare_to_witness(rows, head)
    assert comparison.state == audit.WITNESS_UNWITNESSED and comparison.unwitnessed == 2
    assert not comparison.complete, "an unwitnessed tail must never count as complete"


def test_a_rewritten_and_rechained_record_of_the_same_length_is_a_fork() -> None:
    """The forgery no length and no link can show: rewrite the entries, re-chain them from the true
    anchor, and every internal check passes — which two skeptics reproduced during Story 5.5. The
    journalled value is the only thing in the system that disagrees with it."""
    honest = _chain(MATTER, _VERBS)
    head = audit.HeadWitness(chain_scope=MATTER, seq=3, chain=honest[2].chain)
    forged = _chain(MATTER, [audit.ACT_INGEST, audit.ACT_JUDGE, audit.ACT_LINE_PLACED])
    assert _verdict(forged).verified, "the forgery must be internally perfect"
    assert len(forged) == len(honest), "and the same length, or the length would give it away"
    assert audit.compare_to_witness(forged, head).state == audit.WITNESS_FORKED


def test_no_witness_and_a_partial_chain_are_two_different_silences() -> None:
    """``absent`` is *nothing was recorded outside, so nothing can be concluded*; ``partial`` is
    *the witness may be perfectly good, but this reader does not hold the whole chain*. Neither is
    complete, and reporting a scoped export's tenant-chain slice as TRUNCATED would raise an alarm
    on every correctly-scoped document in the product."""
    rows = _chain(MATTER, _VERBS)
    absent = audit.compare_to_witness(rows, None)
    assert absent.state == audit.WITNESS_ABSENT and not absent.complete
    head = audit.HeadWitness(chain_scope=MATTER, seq=9, chain="x" * 64)
    partial = audit.compare_to_witness(rows, head, partial=True)
    assert partial.state == audit.WITNESS_PARTIAL and not partial.complete
    assert audit.witness_sentence_fr(absent) != audit.witness_sentence_fr(partial)


# ── the check runs on the DOCUMENT (AC-4, AC-5, AC-6) ─────────────────────────────────────────

def test_a_reader_holding_only_the_document_recomputes_it_and_finds_it_sound() -> None:
    rows = _chain(MATTER, _VERBS)
    document = _document(
        rows, witness=WitnessLine(seq=3, chain=rows[2].chain, recorded_at="2026-08-13T10:03:00"))
    (reading,) = read_continuity(document)
    assert reading.recomputable and reading.verdict is not None and reading.verdict.verified
    assert reading.comparison.state == audit.WITNESS_CURRENT
    assert reading.sound and "se vérifie de bout en bout" in reading.sentence_fr


def test_the_claim_is_derived_from_the_document_and_the_callers_value_is_discarded() -> None:
    """The defect this story found on a court document: the flag asserted a property of the reader's
    bytes and was computed from whether a row in the DATABASE carried an anchor — so it printed
    **true** on a numbers-only export that carried no entries at all. ``_document`` passes ``True``
    on purpose; ``assemble`` must ignore it."""
    rows = _chain(MATTER, _VERBS)
    numbers_only = _document(rows, tier=Tier.NUMBERS_ONLY)
    assert numbers_only.trail == (), "numbers-only carries no entry details (FR-26 §11)"
    (line,) = numbers_only.cover.chains
    assert line.recomputable_from_this_document is False
    (reading,) = read_continuity(numbers_only)
    assert not reading.recomputable and reading.verdict is None, (
        "a document with nothing to recompute must report NOT CHECKED, never verified=True")
    assert not reading.sound
    assert "affirmée par le producteur" in reading.sentence_fr


def test_the_readers_recomputation_can_contradict_the_printed_verdict() -> None:
    """The finding that has no counterpart anywhere else in the product: the document's own claim,
    checked against the document's own material. Printing both is what makes it possible."""
    rows = _chain(MATTER, _VERBS)
    document = _document(rows, printed_verified=False)
    (reading,) = read_continuity(document)
    assert reading.verdict is not None and reading.verdict.verified
    assert reading.printed_verified is False
    assert not reading.agrees_with_producer and not reading.sound
    assert "dit le contraire" in reading.sentence_fr


def test_a_truncated_document_recomputes_and_is_still_not_sound() -> None:
    rows = _chain(MATTER, _VERBS)
    document = _document(rows[:1], witness=WitnessLine(seq=3, chain=rows[2].chain))
    (reading,) = read_continuity(document)
    assert reading.verdict is not None and reading.verdict.verified, (
        "the truncated document must recompute — that is precisely why it needs a witness")
    assert reading.comparison.state == audit.WITNESS_TRUNCATED
    assert not reading.sound and "2 actes manquants" in reading.sentence_fr


def test_a_document_whose_entries_were_tampered_names_the_cause_to_the_reader() -> None:
    rows = _chain(MATTER, _VERBS)
    tampered = [rows[0], replace(rows[1], detail="corrigé après coup"), rows[2]]
    document = _document(tampered, witness=WitnessLine(seq=3, chain=rows[2].chain))
    (reading,) = read_continuity(document)
    assert reading.verdict is not None and not reading.verdict.verified
    assert reading.verdict.cause == audit.CAUSE_LINK
    assert "réécrite" in reading.sentence_fr and "n° 2" in reading.sentence_fr


def test_the_tenant_chain_is_reported_partial_never_truncated() -> None:
    """AD-43, on the page: a scoped export holds this *matter*'s share of the *tenant* chain and no
    more. Judging where that chain ends from a slice would raise a truncation alarm on every
    correctly-scoped document the product produces."""
    rows = _chain(MATTER, _VERBS)
    tenant_line = ChainVerdictLine(
        chain_scope=audit.TENANT_CHAIN, label_fr=audit.chain_label_fr(audit.TENANT_CHAIN),
        entries=1, verified=True, anchor="",
        witness=WitnessLine(seq=400, chain="z" * 64))
    slice_entries = _lines([replace(e, chain_scope=audit.TENANT_CHAIN) for e in rows[:1]])
    document = _document(
        rows, witness=WitnessLine(seq=3, chain=rows[2].chain),
        extra=(tenant_line,), extra_entries=slice_entries)
    readings = {r.chain_scope: r for r in read_continuity(document)}
    assert readings[MATTER].sound
    tenant = readings[audit.TENANT_CHAIN]
    assert not tenant.recomputable and tenant.comparison.state == audit.WITNESS_PARTIAL
    assert "qu'une part de cette chaîne" in tenant.sentence_fr


def test_an_unanchored_chain_is_taken_as_given_and_says_so() -> None:
    """A head row rebuilt at restore never carried the value its first entry chains onto. Every link
    after the first is still proved; the first is ADMITTED, and the document must not let that read
    as proved."""
    rows = _chain(MATTER, _VERBS)
    document = _document(rows, anchor=None, witness=WitnessLine(seq=3, chain=rows[2].chain))
    (reading,) = read_continuity(document)
    assert reading.verdict is not None and reading.verdict.verified
    assert not reading.verdict.anchored
    assert not reading.sound, "an admitted first link is not a proved one"
    assert "admise et non prouvée" in reading.sentence_fr


# ── found by the review ───────────────────────────────────────────────────────────────────────

def test_a_document_without_the_anchor_is_not_recomputable_but_is_still_checked() -> None:
    """AC-5 says *entries AND its anchor*, and the derivation dropped the second half — so a
    document whose first link can only be ADMITTED reported that the reader could recompute it.

    The two are kept apart rather than merged: the links this document CAN prove are still proved
    (and its end still compared against the witness), which a single flag would have thrown away."""
    rows = _chain(MATTER, _VERBS)
    document = _document(rows, anchor=None, witness=WitnessLine(seq=3, chain=rows[2].chain))
    (line,) = document.cover.chains
    assert line.carries_its_entries and not line.recomputable_from_this_document
    (reading,) = read_continuity(document)
    assert reading.verdict is not None and reading.verdict.verified
    assert not reading.verdict.anchored and not reading.recomputable and not reading.sound
    assert reading.comparison.state == audit.WITNESS_CURRENT, (
        "the end of the chain is still comparable — the missing anchor is about its beginning")


def test_a_chain_the_document_holds_nothing_of_is_a_truncation_not_a_silence() -> None:
    """The maximal truncation — every entry of the matter's own chain gone — used to leave a FULL
    document with no line, no comparison and nothing to read, and a silent document reads as a clean
    one. A full-tier export is BUILT to carry this chain, so holding none of it is a finding."""
    rows = _chain(MATTER, _VERBS)
    document = _document([], witness=WitnessLine(seq=3, chain=rows[2].chain))
    (reading,) = read_continuity(document)
    assert reading.verdict is None and not reading.sound
    assert reading.comparison.state == audit.WITNESS_TRUNCATED
    assert reading.comparison.missing == 3
    assert "3 actes manquants" in reading.sentence_fr


def test_agreement_is_not_reported_where_no_recomputation_happened() -> None:
    """*Agrees* is a comparison, and a comparison nobody performed is not agreement — the shape of
    every reassuring default this project has had to take back out."""
    numbers_only = _document(_chain(MATTER, _VERBS), tier=Tier.NUMBERS_ONLY)
    (reading,) = read_continuity(numbers_only)
    assert reading.verdict is None
    assert reading.agrees_with_producer is None and not reading.sound
