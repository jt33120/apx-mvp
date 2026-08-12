"""The *confidence bound* as a sentence (Story 5.4, FR-23) — the one text this product says aloud.

A bound rendered on screen is qualified by everything around it: the panel, the freshness chip, the
version header, the tone. **A bound pasted into an email is qualified by nothing except the
characters inside it.** Every design decision in this module follows from that asymmetry: whatever
qualifies the number lives *in the string*, never beside it.

**One owner.** Before this story the four registers' words lived in three places — two functions in
``sampling.py``, one composed inline in the app-layer read seam, and ``no_population`` nowhere at
all. FR-23 makes the banned-phrasing list a **structural property** (FR-56), and a check over *the
words* is only as good as its knowledge of where the words are; a check aimed at the Domain would
have been green while the most-quoted sentence in the product was composed one layer up. It is also
the register split's weak point: every extra composer is another place the four registers can be
re-branched, and the Story 5.2 review found that duplicated branching wrong in three separate
readers. So: this module composes all four, the read seams delegate, and the client renders it
verbatim.

**What the sentence claims, and what it must never be read as.** A random sample bounds the
**prevalence** of relevant material in the *discarded set* — the share of it that is relevant. It
does **not** bound the probability that the pile is now free of relevant material, and the two
differ by orders of magnitude (PRD §0.2: to be 95 % confident that *none* remains among 1 400,
having found none in the sample, one must read roughly 1 330 of them). The phrasings that assert
the second quantity are banned across every locale by ``no-banned-confidence-phrasing``; this
docstring deliberately names the error rather than spelling it, because the check reads source
string literals and a docstring is one.

Pure: no clock, no I/O, no model call, Domain imports only (AD-4). That last one is not decoration —
FR-55 requires this sentence to render with the model provider absent, because *a statistical claim
must never depend on a network call*, and FR-23 requires every number in it to be reconstructible
from the *audit record* alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from apx.core.domain.confidence import prevalence_fr
from apx.core.domain.sampling import (
    KIND_BOUND,
    KIND_CENSUS,
    KIND_COUNTS_ONLY,
    KIND_NO_POPULATION,
    NO_POPULATION_FR,
)

# The four registers this module can speak in — the same disjoint set the estimate carries, named
# here so a renderer's arms and the composer's branches are checkable against ONE list.
REGISTERS: tuple[str, ...] = (KIND_BOUND, KIND_CENSUS, KIND_COUNTS_ONLY, KIND_NO_POPULATION)

# The *configuration-as-data* key naming FR-23's unfitness threshold. It lives beside the rule it
# parameterises rather than in either read seam, so the two seams cannot resolve "the threshold"
# from two different key names and quietly disagree about whether a ranking is unfit.
UNFIT_SHARE_KEY = "unfit_relevant_share"


@dataclass(frozen=True)
class StatementInputs:
    """Everything the sentence needs, and nothing else (Story 5.4, FR-23).

    Deliberately **not** a view over a store row or over
    :class:`~apx.core.domain.sampling.Estimate`. FR-23 requires that *"every number in the
    sentence is reconstructible from the audit record alone. Asserted by test: recompute from
    the exported audit record and compare."* A composer that reached into a live object could
    quietly consume a field the record does not carry, and the round-trip test would still pass
    because both sides would reach the same live object. A flat, explicit input is what makes
    the round trip a real comparison — the regeneration path builds one of these from the
    record and nothing else.

    ``unit_fr`` names **what was counted**. A *sampling run* draws near-duplicate FAMILIES
    (FR-38); calling a family count *"pièces"* makes the sentence false about its own
    denominator, which is the failure this epic exists to prevent. ``piece_count`` is stated
    **beside** the bound and never substituted into it.

    ``scope`` is the *RBAC scope* the number was computed under (FR-23) — see
    :func:`qualifications_fr` for why it is unconditional. ``freshness_fr`` is FR-58's staleness
    state, in words. Both travel inside the string.
    """

    kind: str
    unit_fr: str
    population_units: int
    sample_units: int
    relevant_units: int
    confidence: float
    piece_count: int | None = None
    # ── the bound register only ──────────────────────────────────────────────────────────────────
    count_upper_units: int | None = None
    prevalence_upper: float | None = None
    count_upper_pieces: int | None = None      # a WORST CASE; None = not computable, never 0
    # ── the census register only ─────────────────────────────────────────────────────────────────
    relevant_pieces: int | None = None         # EXACT; every unit was read
    # ── what travels inside the string, in every register that states a count ────────────────────
    scope: str | None = None
    run_ordinal: int = 1
    reviewed_on: date | None = None
    freshness_fr: str | None = None
    # ── the no_population register only: WHICH empty fact it is ──────────────────────────────────
    empty_reason_fr: str = NO_POPULATION_FR

    def __post_init__(self) -> None:
        if self.kind not in REGISTERS:
            raise ValueError(f"statement: unknown register {self.kind!r}")
        if self.run_ordinal < 1:
            raise ValueError(f"the first run over a population is ordinal 1: {self.run_ordinal}")


def statement_fr(inputs: StatementInputs) -> str:
    """**The** sentence — the claim, then everything that qualifies it, then a full stop.

    One function, four arms, no default arm: an unknown register raises in
    :meth:`StatementInputs.__post_init__` rather than falling through to the nearest-looking one.
    A renderer that silently degraded to a neighbouring register would produce a true-looking
    sentence about a different kind of claim, which is the one failure mode this whole epic is
    built around.
    """
    claim = _claim_fr(inputs)
    quals = qualifications_fr(inputs)
    # NOT str.capitalize(): it lowercases everything after the first character, which would mangle a
    # proper noun or a unit the sentence grows later. A claim opening on a digit is unchanged.
    claim = claim[:1].upper() + claim[1:]
    return f"{claim} — {quals}." if quals else f"{claim}."


def qualifications_fr(inputs: StatementInputs) -> str:
    """What travels **inside** the string, in reading order — or ``""`` when there is nothing to
    qualify.

    **The wall is named unconditionally.** FR-23 asks for it *"where the scope is narrower than the
    matter"*, and names the failure: a lawyer saying *"1 400"* to a court about a *matter* holding
    2 100. In this build a *matter* sits behind exactly one wall and a *pièce* carries no scope
    column at all (Story 1.3), so the population is never narrower than the *matter* and a check of
    "is the scope narrower?" would be a comparison whose right-hand side does not exist — this
    project's recurring defect, written deliberately. Naming the wall always satisfies a conditional
    requirement and cannot be wrong. It is not vacuous either: a *matter* can be re-scoped
    (Story 1.6), so a bound drawn under wall A and read after the move names A, and the surface can
    see that the two differ.

    ``no_population`` carries none of this: it states that **no claim applies**, so there is nothing
    to qualify, nothing to date, and nothing that could travel wrongly.
    """
    if inputs.kind == KIND_NO_POPULATION:
        return ""
    parts: list[str] = []
    # FR-22: a bound resting on a later draw over the same population states how many came first.
    # The sentence travels alone, so the multiplicity fact travels inside it or not at all — and
    # abandon-and-redraw is exactly what it is watching for.
    if inputs.run_ordinal > 1:
        parts.append(f"tirage n° {inputs.run_ordinal} sur cette population")
    # CONFIRMED by the review: Decision 3 says the wall is named "unconditionally" and the code
    # said ``if inputs.scope``. A legacy ``recall_review`` row recorded none (AD-19 — it is left
    # None, never back-filled), so its copied sentence dropped the clause entirely and a lawyer
    # pasted "1 400" with nothing saying under whose walls it was counted. An absence of evidence
    # is STATED here, exactly as an unstamped bound's freshness is — never rendered as silence.
    parts.append(
        f"périmètre « {inputs.scope} »" if inputs.scope
        else "périmètre non enregistré : cette borne n'a pas retenu son mur")
    if inputs.reviewed_on is not None:
        parts.append(f"revue du {inputs.reviewed_on.isoformat()}")
    if inputs.freshness_fr:
        parts.append(inputs.freshness_fr)
    return " — ".join(parts)


def _claim_fr(inputs: StatementInputs) -> str:
    if inputs.kind == KIND_NO_POPULATION:
        return inputs.empty_reason_fr
    if inputs.kind == KIND_CENSUS:
        return _census_claim_fr(inputs)
    if inputs.kind == KIND_COUNTS_ONLY:
        return _counts_only_claim_fr(inputs)
    return _bound_claim_fr(inputs)


def _bound_claim_fr(inputs: StatementInputs) -> str:
    """The draw, then the inference — §0.2's corrected form, with one declared deviation.

    The shipped sentence stated the bound and **not** the draw: it opened at *"Avec une confiance
    de 95 %…"*. §0.2's corrected form opens with what was drawn, and it opens there for a reason —
    the draw is the evidence and the bound is the inference, and a sentence that states an inference
    without its evidence is asking to be believed rather than checked.

    **Declared deviation from §0.2.** It reads *"— about Y pièces —"*; this says *« soit au plus Y
    pièces au pire »*. Story 5.2 established that the *pièce* figure is a **worst case** (the sum of
    the ``D`` largest frozen family sizes) precisely because ``prevalence × pièces`` understates
    whenever the large thread-families are the relevant ones. *« Environ »* on a worst case
    understates it again, in the flattering direction — the one direction §0.2 exists to forbid. The
    deviation makes the sentence more conservative than the PRD's wording, never less.
    """
    if inputs.count_upper_units is None or inputs.prevalence_upper is None:
        raise ValueError(
            "statement: the bound register has no bound to state — inventing one here would be a "
            "number with no provenance (AD-19)")
    # The worst case in *pièces*, stated so the reader does not do the rescale herself: 6 of 120
    # families is 5 %, and 5 % of 1 400 pièces is 70 — which is wrong, and wrong in the flattering
    # direction, because the relevant families may be the largest ones. Absent when the run never
    # froze its family sizes; never guessed (AD-19).
    #
    # And when it is NOT computable, the sentence SAYS so. Raised by the review: the expression was
    # a verbatim carry-over that emitted nothing, and the client arm this replaced did carry the
    # refusal ("Le pire cas en pièces n'est pas calculable pour ce tirage") — deleted with the arm,
    # leaving zero occurrences repo-wide. It is the module's own rule, applied two functions over
    # for the counts-only register: a number withheld without a reason reads as one the product
    # forgot rather than one it refused.
    worst = (f", soit au plus {inputs.count_upper_pieces} pièces au pire"
             if inputs.count_upper_pieces is not None
             else " ; le pire cas en pièces n'est pas calculable pour ce tirage")
    return (
        f"{_draw_clause_fr(inputs)} Avec une confiance de {inputs.confidence:.0%}, au plus "
        f"{inputs.count_upper_units} des {inputs.population_units} {inputs.unit_fr} étaient "
        f"pertinentes (prévalence ≤ {prevalence_fr(inputs.prevalence_upper)}){worst}")


def _census_claim_fr(inputs: StatementInputs) -> str:
    """What a census says — an exact count, **never a percentage** (Story 5.2, OQ-4 input 2).

    A census is not a tighter bound; it is a categorically different statement. Nothing is
    estimated, everything was read. A residual-prevalence figure over a fully reviewed population is
    a false claim of residual risk said out loud to a judge — §0.2's failure with better arithmetic.

    Both counts are **exact**: at a census the drawn units ARE the population, so the *pièces* held
    by the relevant ones are known by identity, not bounded. That is why this takes
    ``relevant_pieces`` and not a worst case: the two epistemic statuses are different and are never
    spelled the same way. ``relevant_pieces`` is ``None`` when it is not separately known — the unit
    already IS the *pièce*, or the run never froze its member lists — and the sentence then states
    one count instead of inventing a second.
    """
    pieces_total = inputs.piece_count if inputs.piece_count is not None else inputs.population_units
    head = f"recensement : les {pieces_total} pièces écartées ont toutes été examinées ; "
    if inputs.relevant_units == 0:
        return head + "aucune n'était pertinente"
    # CONFIRMED by the review: this said "1 famille … SE SONT RÉVÉLÉES pertinentes" — the exact
    # plural-verb-on-a-singular-count defect the Story 5.3 review confirmed and fixed in
    # ``_found_fr``, reintroduced eight lines away in the register that states an EXACT count. The
    # singular now comes from one place for both registers.
    one = inputs.relevant_units == 1
    units = (f"1 {singular_fr(inputs.unit_fr)}" if one
             else f"{inputs.relevant_units} {inputs.unit_fr}")
    verb = "s'est révélée pertinente" if one else "se sont révélées pertinentes"
    if inputs.relevant_pieces is None or inputs.unit_fr.startswith("pièces"):
        return f"{head}{units} {verb}"
    pieces = "1 pièce" if inputs.relevant_pieces == 1 else f"{inputs.relevant_pieces} pièces"
    return f"{head}{units} — {pieces} — {verb}"


def _counts_only_claim_fr(inputs: StatementInputs) -> str:
    """What the product says when the estimator has **not** been proven sound (Story 5.3, FR-23).

    Counts, and nothing derived from them: no percentage, no projection, no worst case — and it says
    why, because a number withheld without a reason reads as a number the product forgot rather than
    one it refused. FR-23: *"a failing estimator emits the counts-only sentence instead — it never
    emits a bound it cannot defend."*
    """
    return (
        f"{_draw_clause_fr(inputs)} Aucune borne n'est énoncée : l'estimateur n'a pas encore été "
        "prouvé par simulation, et le produit ne publie pas un chiffre qu'il ne peut pas défendre")


def _draw_clause_fr(inputs: StatementInputs) -> str:
    """*"N unités sur M (P pièces) ont été tirées au hasard ; K se sont révélées pertinentes."* —
    the evidence clause both sampling registers open with.

    Shared by the bound and the counts-only registers on purpose: they state the **same** observed
    facts and differ only in what they are then entitled to infer. Two copies of this clause would
    be two places for the draw to be described differently, and a reader comparing a bound sentence
    with a counts-only one would be comparing two accounts of one draw.
    """
    held = f" ({inputs.piece_count} pièces)" if inputs.piece_count is not None else ""
    return (
        f"{inputs.sample_units} {inputs.unit_fr} sur {inputs.population_units}{held} ont été "
        f"tirées au hasard ; {_found_fr(inputs.relevant_units, inputs.unit_fr)}.")


def _found_fr(relevant_units: int, unit_fr: str) -> str:
    """How many came back relevant, agreeing in number and carrying its unit.

    CONFIRMED by the Story 5.3 review: this once read *"1 se sont révélées pertinentes"* — a plural
    verb on a singular count, and no unit noun at all, in the one string a firm reads out loud. An
    unlabelled family count beside a labelled *pièce* count is the Story 5.1 denominator defect
    wearing grammar.

    FR-23: where the sample found K > 0 the sentence **says so** and the bound widens accordingly;
    the product never suppresses or reframes an unfavourable result.
    """
    if relevant_units == 0:
        return "aucune n'était pertinente"
    if relevant_units == 1:
        return f"1 {singular_fr(unit_fr)} s'est révélée pertinente"
    return f"{relevant_units} {unit_fr} se sont révélées pertinentes"


def singular_fr(unit_fr: str) -> str:
    """A crude French singular for the unit label, so *"1 familles"* never reaches a court. The
    labels are a closed, product-owned set (``pièces écartées``, ``familles de quasi-doublons
    écartées``); this is not a general pluraliser and does not pretend to be."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in unit_fr.split())


# ── FR-23: the unfitness declaration — when the remedy on offer would be the wrong one ───────────
#
# FR-23's seventh consequence: *"Where K approaches N — the reviewer disagrees with most or all of
# the sample — the finding is that the ranking carries no signal, not that the line is misplaced. At
# a configured threshold the system declares the ranking version unfit for this matter, says so in
# words, produces a worklist line offering a re-rank with a revised or newly written case theory
# (FR-37), and does not offer a line move as the remedy."*
#
# No other story claims it (``grep -rn "unfit"`` returned nothing across the epics, the architecture
# spine and the runtime); Story 5.4 adopts it, because it is what the sentence must say when the
# sample comes back mostly relevant.


@dataclass(frozen=True)
class Unfitness:
    """The finding that **this ranking version carries no signal on this matter**.

    Deliberately register-INDEPENDENT: it is a fact about the verdicts a human recorded, not about
    the estimator. A census reaches it (there K/N is the exact share of the discarded set that is
    relevant), a counts-only run reaches it (the counts were observed whether or not a bound may be
    stated), and a bound run reaches it. Gating it on the bound register would mean an unproven
    estimator could hide a ranking that is not ranking anything.

    ``remedy`` names the **one** act on offer. It is not a hint and not a preference: FR-23 says the
    product *does not offer a line move as the remedy*, and a greyed control still proposes the act.
    """

    relevant_units: int
    sample_units: int
    threshold: float
    remedy: str = "re-rank"

    @property
    def share(self) -> float:
        return self.relevant_units / self.sample_units


def unfitness(
    *, relevant_units: int, sample_units: int, threshold: float
) -> Unfitness | None:
    """The finding, or ``None`` when the ranking is not declared unfit.

    ``threshold`` is *configuration-as-data* (``unfit_relevant_share``); it is a required argument
    rather than a module default, because a default here would be a threshold every caller could
    silently inherit while believing it had consulted the tenant's.

    An empty sample yields ``None``: no verdicts were recorded, so there is no finding — never a
    share of zero, which would read as *"the ranking is fine"* about a draw nobody judged (AD-19).
    """
    if not 0 < threshold <= 1:
        raise ValueError(f"the unfitness threshold is a share in (0, 1]: {threshold}")
    if sample_units <= 0:
        return None
    if relevant_units < 0 or relevant_units > sample_units:
        raise ValueError(
            f"impossible counts: {relevant_units} relevant of {sample_units} judged")
    if relevant_units / sample_units < threshold:
        return None
    return Unfitness(
        relevant_units=relevant_units, sample_units=sample_units, threshold=threshold)


def unfitness_statement_fr(
    finding: Unfitness, *, version_no: int, unit_fr: str, kind: str = KIND_BOUND
) -> str:
    """The declaration, in words (FR-23) — the finding, the rule that fired, and the refusal.

    It **names the share it crossed** so the reader sees the rule rather than only its verdict, and
    it states in the same breath that moving the line would not help. Saying only *"the ranking is
    unfit"* leaves the obvious next gesture — drag the line down — looking reasonable, and FR-23 is
    explicit that it is not the remedy.

    ``kind`` makes only the **evidence clause** register-aware; the finding itself stays
    register-independent, which is the point of it. CONFIRMED by the review: this hard-coded the
    sampling register's *"tirées au hasard"* and was called for every register, so a census panel
    said *"les 5 pièces écartées ont toutes été examinées"* on one line and *"sur les 5 … tirées au
    hasard"* on the next — two incompatible accounts of how the same five units were judged, in the
    one module built to keep the registers disjoint.
    """
    drawn = "examinées" if kind == KIND_CENSUS else "tirées au hasard"
    one = finding.relevant_units == 1
    units = singular_fr(unit_fr) if finding.sample_units == 1 else unit_fr
    # The verb agrees with the count — the plural-verb-on-a-singular-count defect this module
    # already fixed twice, and reintroduced here on the third string it gained.
    verdict = "était pertinente" if one else "étaient pertinentes"
    # NOT "au-dessus du seuil": the rule is ``share >= threshold``, so the declaration fires AT the
    # boundary too, where "above" is false. CONFIRMED by the review — and both figures round to the
    # same displayed number there, which made the sentence read as a contradiction of itself.
    text = (
        f"sur les {finding.sample_units} {units} {drawn}, {finding.relevant_units} "
        f"{verdict} — soit {finding.share:.0%}, au niveau ou au-dessus du seuil de "
        f"{finding.threshold:.0%} configuré. Le classement v{version_no} ne trie pas ce dossier : "
        "déplacer la ligne ne corrigerait rien ; il faut reclasser avec une théorie du cas "
        "révisée.")
    # NOT str.capitalize() — it lowercases everything after the first character, which would turn
    # "Le classement v3" into "le classement v3" halfway through the declaration.
    return text[:1].upper() + text[1:]
