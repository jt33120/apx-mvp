---
name: APX — Experience Contract (Epic 5, the sentence)
description: How the confidence bound speaks — the one paragraph a lawyer says to a client or a court, its four disjoint registers, the copy gesture that cannot drop the staleness or the wall, and the unfitness declaration that refuses to offer the wrong remedy. Peer to EXPERIENCE.md (Epic 2), EXPERIENCE-EPIC3.md (Epic 3) and EXPERIENCE-EPIC4.md (Epic 4); inherits the visual identity from DESIGN.md.
status: final
updated: 2026-08-11
sources:
  - ./DESIGN.md                                    # the visual identity (tokens referenced by {path.name})
  - ./EXPERIENCE.md                                # Epic-2 foundations (IA, voice, primitives, a11y floor)
  - ./EXPERIENCE-EPIC3.md                          # Epic-3 truth-status axis
  - ./EXPERIENCE-EPIC4.md                          # Epic-4 triage surface — the priced move this must NOT resemble
  - _bmad-output/planning-artifacts/epics.md       # Epic 5, Story 5.4 (acceptance criteria)
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md  # §0.2, FR-19, FR-22, FR-23, FR-36, FR-55, FR-58
---

# APX — Experience Contract (Epic 5, the sentence)

> **Scope.** This contract owns **the confidence bound as a sentence** (Story 5.4) — the most
> consequential text the product emits, because it is the only text a lawyer repeats *outside* the
> product. It is a peer to the Epic-2, Epic-3 and Epic-4 contracts and specifies only the Epic-5
> delta for this surface. Visual identity lives in [DESIGN.md](./DESIGN.md), referenced by token
> name. **The spines win on conflict with any mock.**
>
> **The substrate is already built and this contract must honour it exactly** (Stories 5.1–5.3
> done). Three guarantees govern every pixel here:
> 1. **Four registers, disjoint in the type.** `bound` · `census` · `counts_only` ·
>    `no_population`. The server decides which; the surface renders the one it was given and has
>    **no arm that can render two**.
> 2. **The sentence is composed on the server.** The client never assembles a claim from numeric
>    fields — every path through the server's composition carries the wall and the staleness, and a
>    client that assembled its own could omit either (FR-58).
> 3. **The estimator is proven or it is silent.** Where the simulation gate has not passed the
>    product states counts and says why; it never emits a bound it cannot defend (FR-23).

---

## Foundation (delta)

- **Form factor.** Desktop-first web, the Epic-2 60rem reading shell. The sentence never leaves the
  shell and never runs wider than it: it is *read*, not scanned.
- **Where it sits.** Two homes, one text.
  - **The matter's triage surface** (Epic 4), directly beneath the denominator equation and above
    the honesty banner — the *constat* zone. It is the matter's current standing claim about what
    was discarded.
  - **The sampling-run screen**, at completion. Same paragraph, same treatment; the run screen adds
    the draw's own detail (which families, which verdicts) around it.
- **What it is not.** It is **not a chart, not a gauge, not a dial.** FR-23 opens with *"a completed
  sampling run produces the sentence, not a chart"*. A gauge invites a reader to interpolate; a
  sentence can only be read.

---

## The rule this surface exists to keep: two numbers that must never share a register

The product emits **two** quantitative statements about the discarded set, and they are different
kinds of claim:

| | **The priced projection** (FR-19, Story 4.9) | **The confidence bound** (FR-23, Story 5.4) |
|---|---|---|
| What it is | A model's estimate at a position where **nothing has been sampled** | A measurement of a **random sample a human actually read** |
| Comes from | The ranking's own scores | A frozen draw and its verdicts |
| Register | *projection* — hypothetical, priced, revisable | *constat* — recorded, dated, exportable |
| Where it appears | Raised **while the line is being moved** | The standing panel on the matter |

**They are never shown in the same visual register, and never in the same card.** This is FR-19's
own consequence (*"a completed sampling run produces a different kind of statement and the two are
never shown in the same visual register"*), and it is the single most important visual decision in
this contract.

How the two are told apart, by construction:

| | Priced projection | Confidence bound |
|---|---|---|
| Container | `{components.card}`, review-toned left border, **no** rule above | `{components.bound-constat}` — surface-2 ground, **gold hairline above**, ink left rule |
| Numerals | inline, body face | **serif tabular-nums**, the bound's percentage set as a numeral |
| Verb | conditional — *« passerait de … à … »* | indicative past — *« ont été tirées », « étaient pertinentes »* |
| Kicker (eyebrow) | `PROJECTION DU CLASSEMENT` | `CONSTAT — TIRAGE ALÉATOIRE` |
| Copy affordance | none — a hypothetical is not quotable | **Copier la phrase** |

The copy affordance is itself the boundary: **only a constat can be copied.** A projection has no
copy button anywhere in the product, because the act of copying is the act of taking a number
outside where its qualifications do not travel with it.

---

## The four registers

The server sends `kind`; the surface has exactly four arms and no default. **A fifth value renders
the honest-failure state, never the nearest-looking arm** — the Epic-3 rule carried in.

### 1. `bound` — the sentence

The whole point of the epic. One paragraph, rendered **verbatim from the server**, in the body face
with the numerals in serif tabular-nums.

> **CONSTAT — TIRAGE ALÉATOIRE**
> 200 familles de quasi-doublons écartées sur 1 400 (1 400 pièces) ont été tirées au hasard ;
> aucune n'était pertinente. Avec une confiance de 95 %, au plus 21 des 1 400 familles de
> quasi-doublons écartées étaient pertinentes (prévalence ≤ 1,5 %), soit au plus 34 pièces au pire
> — périmètre « contentieux-A » — revue du 2026-08-11 — à jour.

- **Ink-toned**, not gold. Gold is the accent, and an accent on the number would read as a
  highlight — a claim being sold. The bound is stated, not sold.
- **A stale bound is review-toned**, its staleness chip raised above the paragraph *and* present
  inside the paragraph. The chip is redundant on purpose: the chip is for the reader on screen, the
  in-sentence clause is for the reader of the paste.
- Beneath, in `{typography.hint}`: the accompanying record — the matter, the ranking version, the
  case-theory version, the position of the line, the method by name, and the draw ordinal.
  FR-23 allows these *"in the accompanying record"* rather than in the sentence; this is that
  record, and it is always on screen beside the sentence, never one click away.

### 2. `census` — an exact count, and never a percentage

A census is not a tighter bound; it is a **categorically stronger statement**. Nothing was
estimated; everything was read.

> **CONSTAT — RECENSEMENT**
> Recensement : les 1 400 pièces écartées ont toutes été examinées ; aucune n'était pertinente.
> — périmètre « contentieux-A » — revue du 2026-08-11 — à jour.

- **`{colors.kept}`-toned seal** (`{components.verdict}` ok variant) rather than the ink constat
  rule: this is the one statement in the product that is not an estimate.
- **No percentage appears anywhere in this arm** — not in the sentence, not in the record beneath,
  not in a tooltip. *« au plus 0,0 % est pertinent »* over a fully read population is a false claim
  of residual risk, and it is precisely §0.2's failure with better arithmetic.

### 3. `counts_only` — the counts, and the refusal, said out loud

> **CONSTAT — COMPTES SEULS**
> 200 familles de quasi-doublons écartées sur 1 400 (1 400 pièces) ont été tirées au hasard ;
> aucune n'était pertinente. Aucune borne n'est énoncée : l'estimateur n'a pas encore été prouvé
> par simulation, et le produit ne publie pas un chiffre qu'il ne peut pas défendre.
> — périmètre « contentieux-A » — revue du 2026-08-11 — à jour.

- **Review-toned**, with the refusal as a chip *and* inside the sentence.
- The refusal is stated, never implied by an absence: a missing figure reads as one the product
  forgot, not as one it refused.
- **The copy affordance stays.** A refusal is quotable and should be quoted — it is the honest
  answer, not an error state.

### 4. `no_population` — no claim applies

> **CONSTAT**
> Le jeu écarté est vide : aucune borne ne s'applique.

- Neutral (`{colors.muted}`), no seal, no copy button — there is no claim to carry anywhere.
- **Never rendered as 0 %.** Two different empty facts get two different sentences (the server
  supplies which): a matter with an empty discarded set, and a matter never ranked or never cut.

---

## The copy gesture — the one interaction on this surface

**`Copier la phrase` puts `copy_text` on the clipboard and nothing else.**

- The paragraph on screen **is** `copy_text`, rendered as a single text node. A user who selects the
  paragraph with the mouse and copies gets the identical string — there is no decoration inside the
  paragraph that a selection would pick up, and no qualification outside it that a selection would
  drop.
- The wall (*RBAC scope*) and the staleness are **inside** that string. Not beside it, not in a
  tooltip, not in the chip alone. A number that travels out of the product travels with what
  qualifies it or the product has helped a lawyer mislead a court.
- Confirmation is a quiet inline `· copiée` in `{typography.hint}`, not a toast. It fades on the
  next interaction; it never covers the sentence.
- **Failure is stated.** Where the clipboard is unavailable (no permission, no secure context) the
  button says so — *« Copie impossible — sélectionnez la phrase »* — and never silently no-ops.

---

## The unfitness declaration (FR-23) — when the remedy offered would be the wrong one

Where the sample comes back **mostly relevant** — K approaching N — the honest finding is *not*
that the line is misplaced. It is that **this ranking version carries no signal on this matter**.
A line move cannot fix an order that is not ordering anything, and offering one would be the
product suggesting an action that cannot help.

Its own state, replacing the remedies:

> **⚠ LE CLASSEMENT NE PORTE PAS DE SIGNAL**
> Sur les 20 familles tirées au hasard, 14 étaient pertinentes. Le classement v3 ne trie pas ce
> dossier : déplacer la ligne ne corrigerait rien.
> **[ Reclasser avec une théorie du cas révisée ]**

- **Review-toned block** (`{components.worklist-line}` urgency border), raised **above** the
  sentence — it qualifies the sentence rather than replacing it. The bound is still stated; it is
  simply not actionable by moving the line.
- **The line-move affordance is removed, not disabled-with-a-tooltip.** A greyed control still
  proposes the act. The remedy on offer is exactly one: re-rank with a revised or newly written
  case theory (FR-37).
- **The pin stays available.** A pin is a statement about one *pièce*, not a remedy for the order.
- The threshold is *configuration-as-data* per tenant. The declaration **names the share it
  crossed** so a reader can see the rule that fired, not merely its verdict.

---

## Voice and Tone (delta)

Inherits Epic-2's verb-first lawyer voice. Three additions specific to this text:

1. **Indicative past for what happened, present for what is bounded.** *« ont été tirées »*,
   *« étaient pertinentes »*, *« au plus X% … est pertinent »*. Never the conditional — a constat
   does not hedge.
2. **The unit is always named.** *familles de quasi-doublons écartées* is not *pièces*. Forty copies
   of one email are one draw (FR-38); calling a family count "pièces" makes the sentence false about
   its own denominator. The *pièce* figure is stated **beside** the bound, never substituted into it.
3. **The *pièce* figure is a worst case and says so.** *« soit au plus Y pièces au pire »* — never
   *« environ Y pièces »*. §0.2's English reads *"about Y pièces"*; in this product that figure is
   the sum of the D largest frozen families, and *« environ »* would understate it in the flattering
   direction. Declared deviation, recorded in the Story 5.4 file.

### Banned phrasings — the list, for anyone who writes or translates this text

**These may never appear in any locale's string set.** Enforced as a structural property (FR-56),
not by editorial care — the false sentence survived a brief, a glossary, three FRs and a north-star
metric on editorial care alone (§0.2).

- *risque d'avoir manqué* / *risk of having missed* — and every near variant
- *probabilité que rien n'ait été manqué* / *probability that nothing was missed*
- *aucune chance qu'il reste* / *chance that nothing relevant was missed*
- any wording attaching *risque* · *probabilité* · *chance* to *manqué* · *oublié* · *passé à côté*
  · *rien ne reste*

**What the sentence says instead:** a **prevalence** — the share of the discarded set that is
relevant — with its confidence level named. That is the quantity a sample bounds. The probability
that nothing was missed is a different quantity, orders of magnitude away, and no estimator here
produces it.

---

## State Patterns (Epic 5)

| State | What the surface does |
|---|---|
| **No bound yet** | *« Aucune borne n'a encore été établie pour ce dossier. »* Its own state — never a bound of zero, never an empty card. |
| **Not read** (out of scope / absent) | Nothing is rendered here; the matter-level banner already says what it can. A failed read is **not** a verified absence. |
| **Stale** | Review tone, chip above, staleness inside the sentence, export replaced by the reason it is refused and the offer to re-sample. |
| **Unverifiable freshness** | Treated exactly as stale, and worded as *« fraîcheur invérifiable »* — an absence of evidence is not evidence of freshness. |
| **Wall moved since the draw** | The sentence names the wall it was **computed under**; where that differs from the matter's current wall the surface says so plainly beside it. |
| **Repeated draw** | *« tirage n° 3 sur cette population »* inside the sentence. It travels in the paste, because the sentence travels alone. |
| **Unfit ranking** | The declaration above, line-move affordance removed. |

---

## Accessibility Floor (delta)

- The sentence is a single `<p>` inside a `<section>` with an accessible name (*Borne de
  confiance*). It is **not** `aria-live`: it is standing content, not a notification, and a live
  region would re-announce it on every unrelated re-render.
- The copy button is a real `<button>` with a visible label; the `· copiée` confirmation is in an
  `aria-live="polite"` span so the outcome is announced without the sentence being re-read.
- **Tone is never the only carrier.** Stale, counts-only and unfit each carry a *worded* chip, not a
  colour alone. The register is legible in a screen reader, in greyscale, and in the paste.
- Numerals use `font-variant-numeric: tabular-nums` so figures align and cannot be misread across a
  wrapped line.

---

## Key Flows

### Flow 12 — Claire quotes the bound to her client (the north-star of Epic 5)

1. Claire opens the matter. Under the denominator she reads the **constat**: 200 of 1 400 families
   drawn at random, none relevant, at most 1.5 % of the discarded set relevant, at most 34 pièces at
   worst — under the wall *contentieux-A*, reviewed today, current.
2. She presses **Copier la phrase**. The clipboard holds exactly what she read, wall and freshness
   inside it.
3. She pastes it into her note to the client. **Nothing was dropped in the paste** — not the
   confidence level, not the wall, not the date, not the freshness.
4. *Climax beat:* three weeks later 300 new pièces are ingested. She returns to the matter and the
   same panel is **review-toned**: the population moved, the bound is stale, the export is refused
   and a worklist line offers a new draw. **The number she quoted three weeks ago is still true
   about the population it was drawn from — and the product will not let her quote it again as if it
   were about this one.**

### Flow 13 — The sample comes back mostly relevant

1. Claire completes a 20-family draw and 14 come back relevant.
2. The panel does **not** offer to move the line. It states that ranking v3 carries no signal on
   this matter, names the share that crossed the threshold, and offers exactly one act: re-rank with
   a revised case theory.
3. The bound is still stated beneath — wide and unflattering — because the product never suppresses
   or reframes an unfavourable result.

---

## Inspiration & Anti-patterns (Epic-5 delta)

- **Anti-pattern: the confidence gauge.** A dial at 98 % invites a reader to feel a number rather
  than read a claim. FR-23 asks for a sentence for exactly this reason.
- **Anti-pattern: the tooltip qualification.** A qualification that lives in a hover does not survive
  a copy, a screenshot, or a print. Everything that qualifies the number is in the string.
- **Anti-pattern: the green tick.** A completed sampling run is not a pass. There is no ✓ on this
  surface; the census seal is the closest thing and it states a fact (*everything was read*), not an
  approval.
- **Anti-pattern: rounding for comfort.** *« environ 1 % »* where the bound is 1.5 %. The number is
  rendered at the precision the server sent and no other.

---

## Handback — Story 5.4

Buildable now. The surfaces this contract lands on already exist: `BoundPanel` in `triage.tsx` (the
matter constat) and the run panel in `App.tsx` (the run's completion). The delta is the register
treatment, the accompanying record beneath the sentence, the unfitness declaration, and the copy
failure path. The sentence itself is server-composed and the client renders it verbatim — the
client-side work is **presentation only**, and any client-side composition of a claim is a defect
this contract forbids.
