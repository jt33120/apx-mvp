---
name: APX — Experience Contract (Epic 5, the audit drawer and its export)
description: How the reasoning behind one pièce is read, and how the record for a whole matter leaves the building as a document a court can read without the system. The four-band drawer, the proposed audit entry, the two-tier export chosen before production, the cover that declares the document's own limits, and the sections that say they are not built yet. Peer to EXPERIENCE.md (Epic 2), EXPERIENCE-EPIC3.md (Epic 3), EXPERIENCE-EPIC4.md (Epic 4) and EXPERIENCE-EPIC5.md (the sentence); inherits the visual identity from DESIGN.md.
status: final
updated: 2026-08-13
sources:
  - ./DESIGN.md                                    # the visual identity (tokens referenced by {path.name})
  - ./EXPERIENCE.md                                # Epic-2 foundations (IA, voice, primitives, a11y floor)
  - ./EXPERIENCE-EPIC3.md                          # Epic-3 truth-status axis + the pièce viewer
  - ./EXPERIENCE-EPIC4.md                          # Epic-4 triage surface — the drawer opens from it
  - ./EXPERIENCE-EPIC5.md                          # the four-register sentence — quoted here, never re-assembled
  - ../../../../../maquettes/maquette_anfr_v2.html # the v1 drawer (salvage candidate named by the epics)
  - _bmad-output/planning-artifacts/epics.md       # Epic 5, Story 5.7 (acceptance criteria)
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md  # FR-11, FR-25, FR-26, FR-45, FR-53
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/  # AD-7, AD-22, AD-35, AD-43
---

# APX — Experience Contract (Epic 5, the audit drawer and its export)

> **Scope.** This contract owns the **audit drawer** and the **matter export** (Story 5.7). It is a
> peer to the Epic-2, Epic-3, Epic-4 and Epic-5-sentence contracts and specifies only the delta for
> these two surfaces. Visual identity lives in [DESIGN.md](./DESIGN.md), referenced by token name.
> **The spines win on conflict with any mock.**
>
> **The substrate is already built and this contract must honour it exactly** (Stories 4.1–4.13,
> 5.1–5.6 done). Four guarantees govern every pixel here:
>
> 1. **Confidence is derived, never declared** (4.4). The drawer shows a band, a *dérivée* marker
>    and the named derivation — never a bare bar with a number, which is what a self-report looks
>    like.
> 2. **Every extract is verified at show time** (4.6/FR-11). `verify_justification` re-checks exact
>    containment on every read. An extract that fails carries an enumerated cause; the surface
>    shows the cause and **not** the passage.
> 3. **The record is chained per (tenant, matter)** (5.5/AD-43), and only the matter's own chain is
>    recomputable by a reader holding the export alone. The document says which is which.
> 4. **An override is a property of an act carrying an FR-25 ground** (5.6), counted over the whole
>    trail. Both surfaces render the count they are given and never recompute it from what is on
>    screen.

---

## Foundation (delta)

- **Form factor.** Desktop-first web, the Epic-2 60rem reading shell. The drawer is an overlay
  **panel** at `{components.audit-drawer.width}` — not a route. Asking *why* must not cost the
  lawyer her place in the ranked order, and the answer is meaningless without the row it belongs
  to still being visible behind it.
- **Where it opens from.** Two places, one panel: the triage-table row (Epic 4) and the pièce
  viewer (Epic 3). The panel is identical from both; only the return is different.
- **What the export is.** A **document**, not a screen — the artefact a *bâtonnier* reads with no
  access to the system. Its layout is specified here because a document that cannot be read
  without the system is not evidence, and layout is where that promise is kept or broken.

---

## Information Architecture

```
Triage table (Epic 4) ──▶ row ──▶ [AUDIT DRAWER] ─────────────┐
Pièce viewer  (Epic 3) ──▶ passage ──▶ [AUDIT DRAWER] ────────┤
                                                              │
Matter surface ──▶ « Exporter le dossier » ──▶ [TIER FORK] ──▶ [EXPORT DOCUMENT]
                                                   │
                                                   └─▶ (full) ─▶ [SECOND CONFIRMATION]
```

**The drawer's four bands, in this order, and the order is the argument:**

| # | Band | Eyebrow (FR) | What it answers |
|---|---|---|---|
| 1 | The decision | `LA DÉCISION` | What the tool concluded, and how sure — derived, with its ranking version. |
| 2 | What it rests on | `CE SUR QUOI ELLE REPOSE` | The named evidence, each piece of it checked *now*. |
| 3 | What will be written | `CE QUI SERA INSCRIT` | The audit entry her next act appends, before it exists. |
| 4 | What you can do | `CE QUE VOUS POUVEZ FAIRE` | Reversible actions, each naming its own reversal. |

A lawyer who reads the bands top to bottom has been walked through *conclusion → evidence →
consequence → choice*. A lawyer who reads them bottom to top has been handed a set of buttons with
no argument behind them, which is every compliance feature that ever shipped and got dismissed.

---

## Band 1 — la décision (Stories 4.4, 4.7, 4.3)

- The **côté** as a `{components.side-badge}` — *retenue* / *écartée* / *non scorée* — carrying the
  `{components.pin-marker}` when a pin, not the line, put it there. It is a **derived view**
  (AD-39): the drawer states *how* it was derived in one line — « au-dessus de la ligne » or
  « épinglée en retenue par Claire Fontaine ».
- The **derived confidence** as `{components.confidence-cell}`: the band word, the derived meter,
  the `dérivée` marker, and beneath it the named derivation and the ranking version
  (AD-23 — no unqualified reference to a ranked figure anywhere in the product).
- The **justification sentence** (4.6), one line, in the source language with the Epic-4 note when
  it differs from the interface (FR-36).

**Barred here:** a bare confidence bar; a percentage with two decimals; any control that would let
the lawyer *type* a confidence. Scoring and classifying are different acts and the affordances must
keep saying so (FR-42).

---

## Band 2 — ce sur quoi elle repose (Story 4.6, FR-11)

Each retained extract renders as `{components.extract-quote}`:

- **Verified** — the passage in the serif reading face, under it the chunk identity and the exact
  source position in mono, and a kept-toned rule. One click opens the pièce viewer *at that
  passage* (Epic-3 contract, Flow 7).
- **Unresolved** — review-toned, dashed rule, **no quoted text**, and the enumerated cause said in
  the lawyer's language:

  | Cause (substrate) | What the drawer says |
  |---|---|
  | `text-changed` | « Le texte de la pièce a changé depuis cette citation. » |
  | `config-superseded` | « Le découpage du corpus a été refait depuis cette citation. » |
  | `position-out-of-range` | « La position citée n'existe plus dans cette pièce. » |
  | `piece-gone` | « La pièce citée n'est plus dans le corpus. » |

  Showing the stored quote anyway would be showing the reader the one string that could not be
  confirmed, wearing the clothes of a confirmed one.

- **Intrinsic-only** — a justification with named signals and **no** extracts is **not
  unverified**. It lists its named signals (FR-38) under an eyebrow saying so. Collapsing the two
  states would tell a lawyer that a sound intrinsic judgement is a broken citation, and she would
  stop believing the marker on the ones that are.

- **Rejected** — where the assessment has been set aside (4.6), the whole band carries a
  review-toned header saying so, with the restoring action in band 4. The extracts stay visible:
  setting aside is not erasing (AD-7).

---

## Band 3 — ce qui sera inscrit (FR-26, FR-24)

The `{components.proposed-entry}`: the audit-record row the lawyer's next act **will** append,
shown before it exists, as a field list and never as prose.

| Field | Value shown |
|---|---|
| `ACTE` | the catalogued verb, in the lawyer's language |
| `ACTEUR` | her display name — the entry is attributed to somebody, always (FR-24) |
| `HORODATAGE` | « à l'instant où vous validerez » — a promise, not a fake timestamp |
| `CHAÎNE` | the chain it lands on, named (« affaire « Vinci / Sogea » » or « chaîne du cabinet ») |
| `DÉROGATION` | present **only** for an override: its FR-25 ground + « motif obligatoire » |

When the pending act is an **override**, the reason field is in the panel and the confirming
control is disabled until it carries a sentence. The lawyer sees the cost before she commits, which
is the whole of FR-25 rendered.

**The timestamp is never pre-filled with a plausible value.** A shown timestamp that is not the one
that will be written is a small lie in the one place the product cannot afford one.

---

## Band 4 — ce que vous pouvez faire (FR-26, AD-7)

Every action here produces an audit entry and **names its own reversal** in the same sentence.

| Action (FR) | Substrate | Reversal, as stated |
|---|---|---|
| « Reclasser… » | `assign_taxonomy_label` (4.5) | « reclassez à nouveau — chaque valeur reste au journal » |
| « Écarter l'appréciation de l'outil » | `reject_justification` (4.6) | « rétablissez-la — le rejet reste lisible » |
| « Rétablir l'appréciation » | `restore_justification` (4.6) | « écartez-la de nouveau ; rien n'est effacé » |
| « Épingler de l'autre côté de la ligne… » | `pin_piece` (4.11) — an **override** | « retirez l'épingle — la pose et le retrait restent tous deux inscrits » |
| « Retirer l'épingle » | `remove_pin` (4.11) | « épinglez à nouveau » |
| « J'ai lu cette pièce… » | **Story 5.8** — not built | *disabled, with the sentence below* |

The validation act is rendered **disabled with its reason** — « Cette action arrive avec la story
5.8. » — rather than hidden. A hidden control cannot be asked about; a disabled one that says why
tells the truth about the build to the only person who could be misled by either.

---

## The matter export

### The tier fork, before anything is produced (FR-26 §11)

`{components.export-tier-fork}` — a **choice screen**, reached from « Exporter le dossier », showing
two cards. The download does not exist until a tier is chosen.

**« Chiffres seuls » (default).** Described by what it *cannot* carry:

> Comptes, versions, verdicts, positions et bornes. **Aucun extrait, aucun motif rédigé, aucun nom
> de fichier, aucun contenu client.** Suffit à refaire chaque chiffre de ce document.

**« Dossier complet ».** Described by what it *will* carry, itemised, review-toned:

> Tout ce qui précède, **plus** : les extraits retenus, les motifs de dérogation mot pour mot, les
> justifications, et les noms et chemins des fichiers du registre.

Choosing the full tier opens a **second confirmation** stating the fact plainly and
recipient-agnostically — this file will contain client content, and producing it is recorded. The
confirming verb is « Produire l'export complet », never « OK ».

**Why a fork and not a toggle.** A toggle beside a download button is a setting; this is the one act
in the product that moves client content out of the firm on purpose (§11's third named egress
path), and a setting is exactly what a person clicks past.

### The cover — the document declares its own limits first

`{components.export-cover}`, page one, before any content:

```
JOURNAL DU DOSSIER                                    « Vinci / Sogea »
────────────────────────────────────────────────────────────────────────
PÉRIMÈTRE      mur « contentieux-construction »   —  ce document ne contient
                                                     rien d'autre
NIVEAU         Chiffres seuls
PRODUIT PAR    Claire Fontaine · 13 août 2026, 14 h 22
────────────────────────────────────────────────────────────────────────
CONTINUITÉ     affaire « Vinci / Sogea » — 412 actes, la chaîne se recalcule
               sans rupture À PARTIR DE CE SEUL DOCUMENT
               chaîne du cabinet — 38 actes ici, vérifiée dans le système ;
               un lecteur qui ne détiendrait que ce document ne peut pas
               refaire ces maillons
────────────────────────────────────────────────────────────────────────
⚠ DÉGRADÉ      3 extraits retenus ne se résolvent plus (voir §4)
```

Four rules, each of which the substrate already makes true and the document must not undo:

1. **The scope is on the face** and phrased as a limit, not a boast.
2. **The continuity verdict is per chain** (AD-43). One boolean over both would claim a property of
   bytes the reader does not hold — the sentence names which chain *this document alone* proves.
3. **An unacknowledged truncation** (AD-35) prints its own banner above everything, and no override
   clears it from the page — only the audited override clears the state.
4. **Dégradé is a state of the document**, on the cover, with its count. It is computed at **read**
   time, so a document produced clean can be shown degraded later — the export must be able to say
   so rather than assert a freshness it cannot have.

### The body — the eight sections FR-26 enumerates

| § | Section | Numbers-only | Full |
|---|---|---|---|
| 1 | Le dénominateur du périmètre | the seven named counts + the words for unknown cardinality | same |
| 2 | La théorie du cas et ses révisions | version numbers, authors, timestamps | + the text of each version |
| 3 | L'histoire de la ligne | each placement: last retained pièce, ranking version, author, priced statement | same |
| 4 | Les épingles | pièce, side, author, timestamp | + the verbatim reason |
| 5 | Les tirages et leurs bornes | run identity, frozen population, verdicts, the **quoted** bound sentence | same |
| 6 | Les dérogations | count, act, ground, author, timestamp | + the verbatim reason |
| 7 | Les actes de validation | *pending — Story 5.8* | *pending — Story 5.8* |
| 8 | Modifié / accepté en l'état | the modified half; accepted *pending — 5.8* | same |

**§5 quotes the bound; it never re-assembles it.** The sentence was composed on the server in one
of four disjoint registers (EXPERIENCE-EPIC5.md), and a document that rebuilt it from numeric
fields could drop the wall or the staleness the server put inside the string.

**§6 states the count the server gave it**, over the whole record, and never the length of the list
printed beneath — the two agree on every matter that has no overrides, which is exactly how a
wrong count survives to production.

### Sections that are not built yet

`{components.pending-section}` — §7 and half of §8:

> **Les actes de validation.** Cette section est vide parce que l'acte n'existe pas encore : la
> validation par un humain est livrée avec la story 5.8. Ce document ne dit donc rien de ce qui a
> été relu — ni qu'il y en a eu, ni qu'il n'y en a pas eu.

Never an empty table, never a **0**. Zero is a finding about the firm; *not built* is a finding
about the build, and a *bâtonnier* reading a 0 in the validation section would draw the first
conclusion from the second.

---

## Voice and Tone (delta)

| Situation | Say | Never |
|---|---|---|
| Confidence | « confiance élevée — **dérivée** de : … » | « 94 % de confiance » |
| An unresolved extract | « Le texte de la pièce a changé depuis cette citation. » | showing the stored quote anyway |
| The proposed entry | « Sera inscrit au journal : … » | « Enregistré » (it is not, yet) |
| The full tier | « ce fichier contiendra du contenu client » | « inclure les détails » |
| A pending section | « l'acte n'existe pas encore (story 5.8) » | an empty table, or « 0 » |
| Continuity | « la chaîne se recalcule sans rupture à partir de ce seul document » | « vérifié ✓ » over both chains |
| Degraded | « 3 extraits retenus ne se résolvent plus » | « quelques références manquantes » |

**Banned, inherited and re-stated:** FR-23's « risque d'avoir manqué… » stays barred everywhere,
including in this document. So does any phrasing that lets a *suggestion* read as a proof, or a
*projection* as a bound.

---

## State Patterns (Epic 5, drawer + export)

| State | Drawer | Export |
|---|---|---|
| No justification for this pièce | band 2 says the tool recorded no justification for this pièce and names the ranking version — not an empty band | §-level: the pièce is listed with no justification, stated |
| Every extract unresolved | band 2 is entirely review-toned; band 1's confidence is unchanged (it was derived from observables, not from the extracts resolving *today*) | `degraded-banner` with the count |
| The assessment is rejected | review-toned header; the restoring action is the first in band 4 | the rejection and its restoration both appear in §8 |
| Out of scope | the drawer does not open, and the row was never there to open it from (Epic-4 pre-filter) | the export cannot be produced; the matter is not offered |
| An unacknowledged truncation | a banner above band 1, linking to the DR surface | the cover banner, above everything |
| Export refused | — | a refusal is **not** an export and writes no audit entry (the 5.4 precedent) |

---

## Accessibility Floor (delta)

- The drawer is a **modal-less panel**: focus moves to its heading on open, `Esc` closes it and
  returns focus to the row that opened it. The table behind stays readable and is not inert — the
  answer is meaningless without the question visible.
- Every band has a heading in the document outline; a screen-reader user gets the same four-step
  argument in the same order.
- The unresolved-extract state is **never colour-only**: the dashed rule, the eyebrow and the
  spoken cause all carry it.
- The tier fork is a radio group with the default pre-selected; the full tier's second confirmation
  is a real dialog with a named verb, reachable and dismissible by keyboard.
- The exported document carries a text layer and a linear reading order; the cover is the first
  thing a screen reader meets, as it is for a sighted reader.

---

## Key Flows

### Flow 14 — Claire is asked why a pièce was discarded (the defining drawer flow)

1. The partner points at rank 148 in the triage table: *why is that one below the line?*
2. Claire opens the drawer on the row. The table stays behind it — the pièce keeps its place in the
   order while they talk.
3. **La décision**: *écartée — sous la ligne*, confiance faible, **dérivée** de deux observables
   named, under ranking version `rk-2026-08-11-a`.
4. **Ce sur quoi elle repose**: one extract, verified, quoted; she clicks it and the viewer opens at
   the passage.
5. The partner disagrees. **Ce qui sera inscrit** shows him the row that will be appended if she
   pins it — his name will not be on it, hers will, and it will carry a *dérogation* with a
   mandatory reason.
6. **Climax.** She types the reason, pins the pièce, and the entry appears in the journal exactly as
   the panel promised. *The disagreement became a record instead of a conversation nobody can
   reconstruct.*

### Flow 15 — Claire sends the record to the bâtonnier

1. From the matter: « Exporter le dossier ».
2. **The fork.** She reads what *chiffres seuls* cannot carry, and takes it — it is the default and
   it is enough for what he asked.
3. The document is produced; the act is recorded with its tier, her name, the matter, the scope and
   the moment.
4. **Climax.** The *bâtonnier* opens page one and, before reading a single act, knows the wall it
   was produced under, that the matter's own chain recomputes from the document he is holding, that
   the cabinet's chain does not and why, and that three extracts no longer resolve. *He can tell
   what this document proves before he decides whether to trust it.*

---

## Inspiration & Anti-patterns (Epic-5 drawer delta)

**Salvaged from `maquette_anfr_v2.html`** — the panel shape, the band order, and the French
vocabulary: *Décision affichée*, *Extraits retenus*, *Trace d'audit proposée*, an *Actions* block.
The v1 drawer was the strongest surface in the abandoned product and it is the epics' named salvage
candidate.

**Deliberately not salvaged**, and each for a reason the substrate now makes non-negotiable:

- **The confidence bar.** A bar with a number is what a self-report looks like. Confidence is
  derived (4.4) and the surface must say so.
- **"Trace d'audit proposée" as the model's reasoning.** In v1 that label sat over three bullets of
  machine prose. In FR-26 it is the **proposed audit-record entry**. The v1 reading teaches a
  lawyer that the audit record is something a machine wrote about itself.
- **"Verser au syllogisme".** An action of the abandoned v1 product.
- **The metadata grid** (date / type / expéditeur / intervenants). Not dropped for being wrong —
  dropped for belonging to the **viewer**, which is where a lawyer reads the document (Epic-3
  contract). The drawer answers *why*, and a drawer that also tries to answer *what* becomes a
  worse viewer and a worse drawer.

---

## Handback — Story 5.7

This contract unblocks **Story 5.7** end to end. Build order, and it is not arbitrary:

1. **The drawer read** — bands 1 and 2 over the existing `read_justification` / `read_triage_table`
   substrate. Nothing new is written; FR-11's show-time verification already exists.
2. **Band 3 and band 4** — the proposed entry and the reversible actions, each already a shipped
   use case except the validation act, which renders disabled and says why.
3. **The export** — the tier fork, the cover, the eight sections, the two pending ones, and the
   audited egress act. The self-containment test (a process with no access to the stores recomputes
   every number in the document) is the story's hardest acceptance criterion and the reason the
   export's field list is specified here rather than left to implementation.

**Open, and owned elsewhere:** the validation act and the accepted-as-is breakdown (5.8); the
continuity check on the export's face is 5.9's to *verify*, this contract only specifies where it
is *printed*.
