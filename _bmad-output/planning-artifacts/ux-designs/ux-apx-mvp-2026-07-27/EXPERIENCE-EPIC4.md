---
name: APX — Experience Contract (Epic 4)
description: How the triage surface works — the ranked working set a lawyer keeps control of. The ranked table with a live change log, the line the tool draws and commits, the priced move, the pin, and the per-pièce justification derived from named evidence. Peer to EXPERIENCE.md (Epic 2) and EXPERIENCE-EPIC3.md (Epic 3); inherits the visual identity from DESIGN.md.
status: final
updated: 2026-08-05
sources:
  - ./DESIGN.md                                    # the visual identity (tokens referenced by {path.name})
  - ./EXPERIENCE.md                                # Epic-2 foundations (IA, voice, primitives, a11y floor)
  - ./EXPERIENCE-EPIC3.md                          # Epic-3 truth-status axis + the pièce viewer (reused here)
  - _bmad-output/planning-artifacts/epics.md       # Epic 4, Stories 4.1–4.12 (acceptance criteria)
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md  # FR-16..FR-21, FR-25, FR-40..FR-43
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/  # AD-7, AD-19, AD-23, AD-36, AD-37, AD-39
---

# APX — Experience Contract (Epic 4)

> **Scope.** This contract owns the **triage surface** — the north-star screen of the whole
> product. It is a peer to the Epic-2 contract ([EXPERIENCE.md](./EXPERIENCE.md)) and the Epic-3
> contract ([EXPERIENCE-EPIC3.md](./EXPERIENCE-EPIC3.md)); it **inherits** their foundations (IA,
> voice, interaction primitives, accessibility floor, the truth-status axis, the pièce viewer) and
> specifies only the Epic-4 delta. Visual identity lives in [DESIGN.md](./DESIGN.md) and is
> referenced by token name (`{components.the-line}`, `{colors.kept}`). **The spines win on conflict
> with any mock.**
>
> **The substrate is already built and this contract must honour it exactly** (Stories 4.1–4.5,
> 4.7 done). The UI *renders* the substrate's guarantees; it must never invent a control that
> contradicts them. The three that govern every pixel here:
> 1. **The corpus is complete.** Retenue + écartée + non-scorée = the whole matter. Nothing is
>    deleted; a discarded pièce is still returned by exhaustive search (FR-16, FR-13).
> 2. **The order is a judgement, not a proof.** A ranked working set can never read as a complete
>    or exhaustive answer — it is the tool's proposal, checkable and reversible (the Epic-3 truth
>    axis, carried in).
> 3. **Retained and discarded are derived views, never stored memberships** — a read of *(the
>    order, the line, the pins)*, recomputed, never a toggle a user flips (FR-16, AD-39).

---

## Foundation (delta)

- **Form factor.** Desktop-first web, the Epic-2 60rem reading shell. The triage **table** is the
  one place content runs **wider than 60rem** when the viewport allows — a dense working grid needs
  the width — but it lives in its own horizontally-scrolling container so the page body never
  scrolls sideways (DESIGN.md layout rule). The pièce viewer (Epic 3) remains the only surface
  whose *document canvas* leaves the shell.
- **UI system.** The ratified APX kit (DESIGN.md). No new framework. The table is built from the
  Epic-4 component tokens (`{components.triage-table}` and its cells).
- **Where this surface sits.** Reached from a **matter** (Epic-2 matters zone) once a ranking
  exists. It is the matter's working view; the pièce viewer opens *from* a row and returns to it.
- **Inherited truth axis.** The Epic-3 rule holds verbatim: a *suggestive* set may never read as
  complete. The ranked order **is** a judgement in that sense — so the surface never labels itself
  "all relevant pièces" or anything a court could read as an exhaustive claim. Its honesty banner
  (below) states what it is.

---

## Information Architecture

The triage surface is **one screen with four stacked zones** and two on-demand drawers. Reading
top to bottom is reading from *the whole* down to *the single pièce*:

1. **The header** — the matter name, the **ranking version** this view is bound to
   (`Classement v3 · 2026-08-05 · théorie du cas v2`), and the actions *Re-classer* (explicit,
   never automatic) and *Exporter le jeu retenu* (Epic 6). Naming the version is mandatory on every
   surface (AD-23) — an unqualified "the discarded set" is not sayable here.
2. **The denominator** — the permanent-denominator **equation** (`{components.equation}`), its
   terms now *retenue + écartée + non-scorée = le corpus*, under a **verdict** seal
   (`{components.verdict}`) stating *nothing has left the corpus*. This is the completeness proof,
   reused from Epic-2's accounting shape: the triage sets **partition** the matter.
3. **The honesty banner** — one sentence, always present: *"Ordre proposé par l'outil, révisable —
   ce n'est pas une preuve. Rien n'est supprimé : une pièce écartée reste retrouvable par la
   recherche exhaustive."* It carries the Epic-3 truth axis onto the triage surface without
   borrowing the search badges (this is not a search result).
4. **The table** — the ranked working set (`{components.triage-table}`), with **the line**
   (`{components.the-line}`) drawn between two rows and the **unscored zone** below the discarded
   set. This is the working surface; everything above is orientation.

Two drawers open from the table and never navigate away:
- **The audit / justification drawer** — opens from a confidence cell or a row's justification;
  shows the derivation and the named extracts (Story 4.6).
- **The change log** — a matter-level append-only panel; also surfaced inline beside an edited row.

**IA closure.** Every Epic-4 stated need has a home: the ranked table + change log (4.10) is zone
4 + the change-log drawer; the line (4.8) is the cut in zone 4; the priced move (4.9) is the
line-price panel raised while dragging; the pin (4.11) is a row action writing a side-badge pinned
variant; the justification (4.6) is the justification drawer. Nothing in Epic 4 lacks a surface,
and no surface here exists without a story that lands on it.

---

## The triage table (Stories 4.10, 4.7, 4.5, 4.4)

The table is the product. One row per pièce, **in rank order (rank 1..N)**. Its columns and their
behaviours *are* the acceptance criteria made visible.

| Column | Token | What it is | The honesty it carries |
|---|---|---|---|
| **Rang** | `{components.rank-cell}` | The ordinal, serif tabular-nums, right-aligned. | A pièce's place in **one** ranked order. A label edit or a pin **never** changes it (FR-40, FR-43). |
| **Pièce** | — | Name in the body face, a mono id beneath (like the register row). Opens the viewer. | Identity is stable and provenanced; the viewer (Epic 3) is one click away. |
| **Confiance** | `{components.confidence-cell}` | A **read-only derived** band (élevée/moyenne/faible) + a small `dérivée` marker. Expands to the justification. | **Derived from observables, never typed** (FR-42). It is shaped *unlike* an editable cell on purpose. |
| **Étiquette** | `{components.label-cell}` | An **editable** select: the tenant taxonomy or the explicit `unlabelled`. | Editing appends to the ledger + a change-log entry; **never** reorders the row or crosses the line (FR-40). Out-of-taxonomy can't be chosen. |
| **Côté** | `{components.side-badge}` | *Retenue / Écartée / Non-scorée* as a **derived view** chip. | A read of *(the line, the pins)* — **never a checkbox**. Its pinned variant shows a human override (FR-16, FR-43). |
| **(row actions)** | — | *Épingler* (the pin), *Justifier* (the drawer), *Historique* (this row's change log). | Every action is recorded and reversible. |

**The editable/derived contrast is load-bearing.** The confidence cell and the label cell sit side
by side precisely so the lawyer sees, without being told, that **scoring and classifying are
different acts**: one is the tool's derived reading she cannot type over, the other is her
editable classification the tool will not touch. This is FR-42 and FR-40 rendered as affordance.

**A cell edit changes that cell and nothing else** (FR-20, the invariant the whole architecture was
built around). Committing a label writes the ledger and shows a change-log entry beside the row
*immediately* — previous value → new value, author, timestamp. **No edit triggers regeneration,
re-ranking, or re-classification of any other row.** Re-ranking is a **separate, explicit,
user-initiated act** (*Re-classer* in the header) that produces a **new ranking version** and
**never overwrites edits** — human-set values survive it, marked as human-set.

**Rows never reorder on an edit.** The order changes only when the lawyer explicitly re-ranks (new
version). The table's stability under editing is a promise the surface keeps visibly: an edited row
stays exactly where it was, its change-log entry appearing in place.

---

## The line — the tool draws it and commits (Story 4.8, the north-star)

**The line is the defining gesture of the product.** A ranked list that refuses to decide pushes
the work back onto the lawyer; the line is the tool **taking a position**.

- **It is a cut *between* two rows**, drawn full-bleed across the table with a single gold hairline
  (`{components.the-line}`), retained above and discarded below. It is **never drawn on a row**, and
  **never a bare integer** ("position 180").
- **It speaks.** The interface states the commitment in words, verb-first, in the lawyer's voice:
  *"À mon sens, tout ce qui précède — jusqu'à la pièce n°142."* Not merely a divider. Below the
  sentence, an eyebrow states the **basis**: *"Fondé sur la théorie du cas v2"* where one exists,
  or *"Fondé sur les signaux intrinsèques nommés"* where none does (FR-17).
- **It is named by the last retained pièce.** The line's identity is *the identity of the last
  retained pièce* (`Pièce n°142 « Contrat de cession — 2019 »`), stored as an ordinal cut over a
  named ranking version, with author and timestamp — **never a bare score, never a bare integer**
  (FR-17). This is what the substrate stores (Story 4.7's `Line(last_retained_piece_id)`).
- **Why the identity, not the number** *(the failure path made visible)*: an import that adds
  pièces must **not silently move what the line designates**. Because the line is stored against
  *the last retained pièce*, not "position 180", a larger corpus leaves the line pointing at the
  same pièce — the surface states this when it happens: *"12 pièces importées depuis le tracé de la
  ligne ; la ligne reste sur la pièce n°142 (elle ne s'est pas déplacée)."*
- **Retained vs discarded are visually and verbally distinct** — the kept/discard semantic tier,
  kept distinct from gold. Above the line: a quiet `kept` wash on the côté badges and a *Retenue*
  zone label carrying its count (`142 pièces retenues`). Below: `discard`-toned, *Écartée* with its
  count.
- **Changing the line never reorders the underlying ranked order** (FR-17). Moving the line moves
  *the cut*, not the pièces.

**The unscored tail is its own zone.** Below the discarded set sits a separately-labelled zone —
*"Non scorées — la cascade n'a pas pu les départager (23 pièces)"* — never folded into the
discarded set (AD-19/AD-36). A pièce the cascade could not score is **not** silently discarded; it
is explicitly *pending a judgement*, and the surface says so. It sits below the line but is not
"below the line" in the retained/discarded sense — it is a third, honestly-named set.

---

## Moving the line is priced (Story 4.9 — the subtle, dangerous surface)

When the lawyer **repositions** the line (grabbing the cut and considering a new position), the
interface **prices the move before she commits** — the recall/precision trade-off as a dial with
its cost shown, never a silent drag.

- **What it states**, for a candidate position (`{components.line-price}`): the change in the
  **number of pièces to read**, and the change in the **estimated prevalence of relevant material
  in the resulting discarded set**. Copy, verbatim register:
  > *"400 pièces de plus à lire. La part estimée de pertinents dans l'écarté passe d'environ 3 % à
  > environ 0,4 %."*
- **It is labelled a projection, never a bound.** The panel carries an eyebrow *"PROJECTION DU
  CLASSEMENT — rien n'a été échantillonné"*, and its **visual register is deliberately different
  from the sampling bound / verdict seal** (Epic 5): an ink-toned, dashed-edge panel, **not** the
  `kept`/`review` verdict shape. A model estimate must never wear the costume of a proven bound
  (FR-19). A completed *sampling run*'s statement (Epic 5) is **never** shown in the same visual
  register as this projection.
- **It never says "risque d'avoir manqué".** That phrasing is barred product-wide (FR-23, §0.2):
  it is not what any estimator here produces. The projection speaks in *estimated prevalence*, not
  *risk of a miss*.
- **Failure path — no projection available.** Where the prevalence projection cannot be produced,
  the move **still shows the change in pièces to read**, and says the prevalence projection is
  **unavailable** — *"Projection de prévalence indisponible pour cette position"* — rather than
  inventing a number.
- **Committing the move** is an audited, reversible act writing a new line position (author,
  timestamp, the new last-retained pièce). The order does not change.

---

## The pin — moving a single pièce across the line (Story 4.11)

The lawyer knows one discarded document is decisive. She retains **that one pièce** without dragging
the line past the four hundred above it.

- **Exactly one pièce crosses.** Pinning a pièce into (or out of) the retained set changes the
  retained set **by exactly one pièce**; the **ranked order does not change**, **the line does not
  move**, and **no other pièce's membership changes** (FR-43). On the substrate this is a `Pin`
  applied *after* the line cut — `pins_in_force` counts only the ones that disagree with the line.
- **A pin carries a mandatory one-line reason** — it is recorded as an **override** (FR-25),
  because it contradicts a machine assertion. The reason field is required; the pin cannot be
  placed without it. Copy: *"Motif (obligatoire) — pourquoi cette pièce traverse la ligne"*.
- **The pinned pièce reads as an override, not as the line's placement.** Its côté badge takes the
  **pinned variant** (`{components.pin-marker}` — a gold épingle on the side badge). Hovering or
  expanding it shows *who* pinned it, *when*, and the reason. `Pins en vigueur : 3` is stated
  wherever the sets are counted, and the pinned pièces are **named**.
- **Pins are reversible and survive re-ranking.** A pin carries to new ranking versions **marked as
  human-set** until explicitly removed; removing a pin is **itself a recorded, reversible act**
  (a new change-log entry, never an erasure).

---

## Per-pièce justification, derived from named evidence (Story 4.6)

Each pièce shows **why it is where it is**, in one line, backed by extracts the lawyer can verify —
checkable, not a fluent sentence she must trust.

- **One line, in her language, without opening the pièce** (FR-18): *"Retenue — porte sur la
  période de la théorie du cas et nomme les parties."* The line is **generated from a stated input
  set**: the *case-theory version* or the named intrinsic signals, **and the specific retained
  extracts** the judgement used — each **named by chunk id** and **resolvable to a source
  position** (FR-41).
- **Every extract is verified by exact containment at the moment it is shown** (FR-41, FR-11). A
  justification whose extracts **do not resolve** against their source is shown as **unverified**
  (`{components.justification}` review-toned, *"Non vérifiée — un extrait cité ne se retrouve plus
  à sa source"*), **never as ordinary**. Verification is a show-time act, not a stored flag.
- **It expands into the audit drawer** showing the extracts behind it — each extract quoted, its
  chunk id in mono, a link that opens the pièce viewer *at that passage* (the Epic-3 passage
  highlight). Reversible in one action recorded in the audit record (FR-18).
- **It states the source pièce's language where it differs** from the interface language (FR-41,
  FR-36) — the quoted extract is marked as untranslated source, never silently machine-translated
  (the Epic-2 i18n foundation).

---

## Voice and Tone (delta)

The Epic-2/Epic-3 voice holds: verb-first, lawyer's language, no false-precise single number, no
engineer vocabulary, nothing rendered as destructive. Epic-4 specifics:

| Situation | Say | Never say |
|---|---|---|
| The line's commitment | *"À mon sens, tout ce qui précède — jusqu'à la pièce n°142."* | *"Ligne à la position 180."* (a bare integer) |
| The line's basis | *"Fondé sur la théorie du cas v2."* / *"…sur les signaux intrinsèques nommés."* | *"Score de coupe : 0,62."* (a bare score) |
| Priced move | *"400 pièces de plus à lire ; part estimée de pertinents dans l'écarté ≈ 3 % → ≈ 0,4 %."* | *"Risque de 3 % d'avoir manqué une pièce."* (barred, FR-23) |
| Projection label | *"Projection du classement — rien n'a été échantillonné."* | Presenting it in the sampling-bound / verdict register. |
| The discarded set | *"Écartée du jeu retenu de la version v3 — retrouvable par la recherche exhaustive."* | *"Supprimée."* / *"Exclue."* / *"the discarded set"* unqualified. |
| Unscored pièces | *"Non scorées — la cascade n'a pas pu les départager."* | Folding them into *écartées*. |
| Confidence | *"Confiance élevée (dérivée)."* | *"Le modèle est sûr à 87 %."* (self-report + false precision) |
| A pin | *"Épinglée dans le retenu — motif : …"* | *"Cochée."* (a stored toggle) |
| Unverified justification | *"Non vérifiée — un extrait cité ne se retrouve plus."* | Showing it as an ordinary justification. |

---

## Component Patterns (behavioural)

Visual specs live in DESIGN.md; here is how each behaves.

- **Triage table** (`{components.triage-table}`) — virtualised for large matters; the header row and
  the line's zone labels are sticky. A cell edit is optimistic-then-confirmed; on a write failure it
  reverts the cell and states the failure (never a silent loss). Sortable **only** by rank — the
  order is the ranking's, and the surface never offers a "sort by confidence" that would imply a
  second order.
- **The line** (`{components.the-line}`) — a keyboard-reachable handle (`role="separator"`,
  `aria-orientation="horizontal"`, arrow keys move the candidate cut). Grabbing it raises the
  **line-price** panel; releasing on a candidate opens a confirm with the priced summary. Committing
  writes the new cut; Escape abandons the move with no change.
- **Line price** (`{components.line-price}`) — recomputed per candidate position as the handle moves;
  debounced. Always shows the pièces-to-read delta even when the prevalence projection is
  unavailable.
- **Side badge** (`{components.side-badge}`) — never interactive as a *toggle*; the only way to
  change a side is to move the line (bulk) or pin a pièce (one). Clicking it explains that.
- **Pin** (`{components.pin-marker}`) — the row action opens a small form: side (retain/discard) +
  the mandatory reason. Placing writes an override; the badge takes the pinned variant. Removing is
  a second recorded act.
- **Change-log entry** (`{components.change-log-entry}`) — appears beside the row on commit and in
  the matter-level log; append-only, newest first in the panel, in-place beside the row. A reversal
  adds a new entry.
- **Justification** (`{components.justification}`) — verification runs when the drawer opens; the
  verified/unverified state is computed then, not cached from ranking time.

---

## State Patterns (Epic 4)

- **No ranking yet** — the matter shows the Epic-2 state ("ranking not run"); the triage surface is
  not reachable. The surface never renders an empty table as if it were a result.
- **Ranking stale** (case theory or config changed since the ranking) — a `review`-toned banner:
  *"Le classement date d'avant la dernière modification de la théorie du cas. Re-classer produira
  une nouvelle version ; vos valeurs saisies seront conservées."* Re-ranking is offered, never
  automatic. (Freshness/staleness is Story 4.13's own surface; this is the banner hook.)
- **Re-ranking in progress** — the current version stays fully readable and editable; the new
  version arrives as an explicit switch, and human-set values are carried marked as human-set. The
  surface never blanks the table mid-rerank.
- **The line not yet placed** — the table shows the ranked order with **no cut**; the retained and
  discarded zones are absent, and the tool *offers to draw the line* (Story 4.8's placement act).
  The unscored zone is still shown (it does not depend on the line).
- **A moving population** (an open import job on the matter) — consistent with Epic-3: the surface
  states the corpus is changing and that the line is held against a pièce identity, so it will not
  silently move; re-ranking waits for a stable corpus.
- **A write failure on an edit / pin / line move** — the action reverts and states the failure; no
  partial state, no silent loss (FR-20's promise extends to failure).

---

## Accessibility Floor (delta)

Inherits the Epic-2/Epic-3 floor. Epic-4 specifics:

- **The line is keyboard-operable** — a focusable separator handle, arrow keys to move the candidate
  cut, Enter to open the priced confirm, Escape to abandon. The priced summary is announced via
  `aria-live="polite"` as the candidate moves.
- **The editable/derived distinction is not colour-only** — the label cell is a real `<select>`
  (announced editable); the confidence cell is read-only text with a "dérivée" label (announced
  non-editable). A screen-reader user hears the difference the sighted user sees.
- **Change-log entries are announced** on commit via a polite live region beside the row.
- **The côté badge announces it is derived** — its accessible name includes "vue dérivée de la
  ligne" so an assistive-tech user is not told it is a toggle.
- **Counts are tabular and labelled** — retained/discarded/unscored counts read as "142 pièces
  retenues", never a bare number.

---

## Key Flows

Named-protagonist journeys, continuing **Claire Fontaine** from the Epic-2/Epic-3 contracts.

### Flow 8 — The tool draws the line and Claire accepts it (the north-star, Story 4.8)

1. Claire opens the ranked matter *Cession Lambert*. The header names the version
   (`Classement v3 · théorie du cas v2`); the denominator equation shows
   *retenue + écartée + non-scorée = 1 240 pièces*, the verdict seal green: *nothing has left the
   corpus*.
2. She reads the honesty banner — *ordre proposé, révisable, ce n'est pas une preuve; rien n'est
   supprimé* — and understands what she is looking at.
3. The line is already drawn between pièce n°142 and n°143. It **speaks**: *"À mon sens, tout ce
   qui précède — jusqu'à la pièce n°142. Fondé sur la théorie du cas v2."* Above it: *142 pièces
   retenues*. Below: *1 075 écartées*. Then, separately: *23 non scorées*.
4. **Climax.** The tool has *taken a position* — it did not hand her 1 240 rows and make her draw
   the line herself. She reads its basis, agrees, and the line stands, named by pièce n°142, stored
   against that identity so an import can't move it out from under her. She has spent her attention
   on *142 pièces*, not 1 240 — and she can defend exactly why.

### Flow 9 — Claire moves the line, priced (Story 4.9)

1. She suspects the cut is too tight. She grabs the line and drags it down.
2. As the candidate cut moves, the **projection panel** rises: *"400 pièces de plus à lire. Part
   estimée de pertinents dans l'écarté : ≈ 3 % → ≈ 0,4 %."* — under the eyebrow *PROJECTION DU
   CLASSEMENT — rien n'a été échantillonné*, in the ink-toned, dashed register.
3. **Climax.** She reads a *price*, not a *risk of a miss*, and she reads it as a **projection** —
   not a sampling bound she could put in front of a court. She knows the difference because the
   surface refuses to blur it. She commits at a position she chose deliberately; the move is
   recorded, the order unchanged.

### Flow 10 — Claire pins the one decisive discarded pièce (Story 4.11)

1. Exhaustive search surfaced pièce n°804 — deep in the discarded set — and Claire knows it is
   decisive.
2. She pins it into the retained set. The form requires a **motif**: *"Aveu implicite au §4 —
   décisif malgré le rang."* She types it; without it the pin will not place.
3. **Climax.** The retained set grows by **exactly one**. The line does not move; the four hundred
   pièces above n°804 are **not** dragged in with it. The badge shows the gold épingle — a *human
   override*, recorded, reversible — and *Pins en vigueur : 1* now reads in the counts. She kept the
   decisive piece without paying for four hundred she did not want.

### Flow 11 — Claire edits a label and nothing else moves (Story 4.10)

1. Row n°57 is mislabelled *Correspondance*; it is a *Contrat*. Claire opens the label select and
   changes it.
2. The change-log entry appears beside the row instantly: *Correspondance → Contrat · Claire
   Fontaine · 14:22*. The row **does not move**; its rank is unchanged; no other row re-ranks or
   re-classifies.
3. **Climax.** A minute later she corrects row n°58 — and her edit to n°57 is still there, untouched.
   *Correcting the machine never cost her the correction she made a minute ago.* When she later
   re-ranks explicitly, both edits survive, **marked as human-set**, rather than being replaced by
   fresh machine values.

---

## Inspiration & Anti-patterns (Epic-4 delta)

**Barred** (beyond the product-wide bars):
- A **checkbox** or stored toggle for retenue/écartée — it lies about the derived-view model.
- An **editable confidence** field, or a confidence that reads as the model's self-report.
- A **sort-by-confidence** that implies a second order competing with the ranking.
- The priced move in the **verdict/absence-seal register** — a projection wearing a bound's clothes.
- A **drag that silently re-ranks**, or any edit that regenerates another row.
- The word **supprimée / exclue** for a discarded pièce; folding **non-scorées** into écartées.
- A pin **without a mandatory reason**; a change-log that can be **edited or erased**.

**Salvaged / carried in:** the permanent-denominator equation + verdict seal (Epic-2), the
truth-status honesty (Epic-3), the pièce viewer + passage highlight (Epic-3), the audit-one-click
principle, the lawyer's-language voice.

---

## Handback — Story 4.8 first

This contract unblocks Stories **4.6, 4.8, 4.9, 4.10, 4.11**. Implementation begins with **Story
4.8 (the line)** because it consumes the Story-4.7 substrate directly (`Line(last_retained_piece_id)`,
`derive_triage_sets`) and is the north-star gesture the rest of the surface hangs from. The line's
UI/behavioural contract is the section **"The line — the tool draws it and commits"** above; its
visual tokens are `{components.the-line}`, `{components.side-badge}`, `{components.triage-table}`,
and the reused `{components.equation}` / `{components.verdict}`.
