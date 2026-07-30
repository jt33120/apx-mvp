---
name: APX — Experience (Epic 3)
description: The user-facing surface of APX retrieval — the search entry, the two engines shown visibly and verbally distinct and never combined, the truth-status declaration carried by the data, the AD-42 absence statement, and how the distinction survives into an export a court reads without the system and into the audit record. Peer to EXPERIENCE.md (Epic 2), which owns the home, onboarding, import, completion summary and register; both inherit DESIGN.md.
status: final
updated: 2026-07-30
scope: Epic 3 (retrieval). The truth-status/search surface — Story 3.4 (every result set declares its truth status) is the story this contract unblocks; it also carries the AD-42 absence-statement wording deferred from Story 3.2 and the search-results layer 3.1/3.2 built as data. The pièce viewer (Story 3.5) now carries its full contract here (added 2026-07-30, Update mode) — the full-fidelity build: originals retained at rest and rendered per format inside the tenant boundary.
sources:
  - _bmad-output/planning-artifacts/epics.md            # Epic 3, stories 3.1–3.5
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md  # FR-12..FR-15, FR-23, FR-44, FR-57
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/  # AD-20, AD-38, AD-42, AD-21, AD-13/14
  - ./EXPERIENCE.md                                      # the Epic-2 foundations this extends (voice, denominator, a11y, RBAC)
design: ./DESIGN.md
---

# APX — Experience Contract (Epic 3)

> **What this contract unblocks.** Epic 3's two user-facing stories carry *"UX pass required
> before implementation. No UX design contract exists yet."* — **3.4** (every result set
> declares its *truth status*) and **3.5** (the *pièce* viewer). This document is the contract
> for **3.4** and for the **search-results surface** the two engines (3.1 semantic, 3.2
> deterministic) already produce as data; it also carries the **AD-42 absence-statement
> wording** deferred from Story 3.2. **Story 3.5 (the *pièce* viewer) now has its full contract
> here** (the *"The pièce viewer"* section below, added in Update mode 2026-07-30).
>
> **This extends [EXPERIENCE.md](./EXPERIENCE.md), it does not restate it.** Foundation, voice,
> the permanent denominator, the provenance drawer, the RBAC-in-UI rules, the a11y floor and
> the i18n foundation are inherited. Token names in `{braces}` reference
> [`DESIGN.md`](./DESIGN.md). **Both spines win over any mock on conflict.**
>
> **Key-screens mock:** [`mockups/epic-3-truth-status.html`](./mockups/epic-3-truth-status.html)
> — suggestive results, the exhaustive absence statement with its four qualifications, an
> exhaustive presence, the moving-population refusal, and the two export headers, all against the
> real `tokens.css`. The mock illustrates; this contract and DESIGN.md decide.

---

## Foundation (delta)

Everything in the Epic-2 Foundation holds: desktop-first single-column at `{spacing.shell-max}`,
the offline constraint (no web-font, no CDN, no beacon), the bespoke `tokens.css` kit, and **the
three-place model**. Epic 3 adds one governing idea that sits *beside* the three-place model, not
inside it:

**The two-truths model.** Every result a lawyer sees is one of exactly two kinds, and the
interface says which, always, in the same way: a **suggestion** (the semantic engine *finds* —
it never claims to be complete) or a **proof** (the deterministic engine *proves* — it returns
the whole match set within scope and carries its *denominator*). *Truth status* is a **different
axis** from the triage tier (kept / à-revoir / écartée); the UI never lets the two blur, and it
never merges a suggestion and a proof into one undifferentiated list (FR-15).

---

## Information Architecture

Search is not a new top-level destination; it lives **inside the scope a lawyer already stands
in** — the matter, or a scoped corpus view — so a result can never out-run its RBAC wall
(AD-13/AD-14, the 3.3 pre-filter).

```
Matter detail  (from EXPERIENCE.md — denominator · register · audit · [Epic 3+ embryos])
│
└── RECHERCHE  (Story 3.1/3.2/3.4)                one field, an EXPLICIT mode
      ├── mode: Suggestions (par sujet)  ─→  Suggestive result set  (≈ SUGGESTIF)
      │        └── row ─open→ the pièce viewer at the passage (Story 3.5)
      ├── mode: Preuve (terme exact)     ─→  Exhaustive result set  (= EXHAUSTIF)
      │        ├── the scoped denominator + the absence-statement seal (AD-42)
      │        ├── the COMPLETE match list
      │        └── Register name-matches  (separate block, AD-21)
      └── Exporter…  ─→  a court-readable document carrying the truth status (+ denominator)

Provenance / audit drawer   (inherited)   one click from any hit, as from any piece
Query   ─is an audited act→   the audit record (actor · term · engine · scope · denominator)
```

**Closure check.** Epic 3's two stated needs land: *find pièces about a topic* → the suggestive
set; *prove a term appears (or appears nowhere) and defend it* → the exhaustive set + its
absence statement + the export. Every hit reaches the viewer (3.5) and the provenance drawer
(inherited). Nothing here introduces a second shell width, a fourth colour, or a merged list.

---

## The two truth statuses (the spine of this contract)

As the *permanent denominator* is the spine of Epic 2, the **truth-status declaration** is the
spine of Epic 3. **Not decoration — a load-bearing, data-carried honesty device.**

**It is carried by the data, not chosen by a screen.** Each result set carries `truth_status`
(set at exactly one construction site per engine — already a build gate, Story 3.1). Every place
a result set appears — the results surface, an export, the audit entry — reads that field and
renders the **same** badge (`{components.truth-status-badge}`). A surface can neither invent nor
suppress it.

**Suggestive** (`{components.suggestive-result}`) — the semantic engine.
- Header: the **suggestive badge** (`≈ SUGGESTIF · classé par proximité`) on an **open** frame —
  a 2px *dashed* `{colors.line}` left rule. The dashed edge is the message: *this set is not
  closed.*
- The count is phrased as an **ordering, never a total**: *"les 20 pièces les plus proches sur
  ce périmètre"* — **never** *"20 résultats"* or any count a reader could take as completeness
  (FR-12). The stated `k` and the `similarity_threshold` (config-as-data, recorded with the set)
  are shown as *"les plus proches, seuil de proximité {value}"*, not as a guarantee.
- Each row: pièce name, a `scope` chip for its matter, a snippet with the query term marked, and
  the **proximity indicator** (`{components.proximity-indicator}`, a relative four-pip meter +
  rank — never a false-precise `%`). Row opens the **viewer at the passage** (3.5).

**Exhaustive** (`{components.exhaustive-result}`) — the deterministic engine.
- Header: the **exhaustive badge** (`= EXHAUSTIF · ensemble complet`) on a **solid**
  `{colors.line}` frame (a closed set).
- Directly beneath the header, the **scoped denominator** — the *same* `{components.equation}`
  the home screen uses (AD-38) — and the **absence-statement seal** (below).
- Presence: *"3 occurrences de « cession » dans 2 pièces — ensemble complet sur ce périmètre."*
  Then the **complete** match list (never a top-N; the engine takes no limit, AD-20).
- **Register name-matches are a separate block**, beneath the results, headed *"Correspondances
  dans le registre (pièces non indexées)"* — a register hit is a distinct thing, never counted
  inside the exhaustive set (AD-21).

**The absence statement** (`{components.absence-statement}`, AD-42) — *the product's most
dangerous output.* When the complete set is empty (or always, as the proof's honesty line), a
verdict-seal-shaped panel states the claim **with its four qualifications, in words**:

> **Aucune occurrence de « cession ».** Recherché dans tout l'indexé de ce périmètre.
> Le registre liste **2 800 pièces illisibles** et **1 archive au contenu inconnu** ;
> **12 %** du corpus recherché provient d'un OCR, **3 %** sous le seuil de qualité.

The four qualifications are exactly: the **scoped denominator** (AD-38, the equation), the **open
failure-register** count, the **unknown-cardinality** containers stated in words, and the **OCR
share + below-quality share** of the searched set. The seal is `kept`-toned when the scope is
fully indexed and stable, `review`-toned when qualified. It is **never** a bare *"introuvable"*,
and it **never** carries the FR-23 banned phrasing (*"risque d'avoir manqué un document
pertinent"* and its kin) — the bound states a prevalence, never a probability that nothing was
missed.

---

## Voice and Tone (delta)

All Epic-2 voice rules hold (lawyer's language, name-the-thing-not-the-mechanism, count
honestly, never a raw error, French terms of art stay French). Epic 3 adds the **truth-status
register**, binding:

| Situation | Say | Never |
|---|---|---|
| A suggestive set | "≈ Les 20 pièces les plus proches sur ce périmètre" | "20 résultats trouvés" (reads as a total) |
| Suggestive, none over the floor | "Aucune suggestion au-dessus du seuil de proximité. Ce n'est pas une preuve d'absence — utilisez la recherche exhaustive." | "0 résultat" / "introuvable" |
| An exhaustive presence | "3 occurrences de « cession » dans 2 pièces — ensemble complet sur ce périmètre" | "environ 3 résultats" |
| An exhaustive absence | "Aucune occurrence de « cession ». Recherché dans tout l'indexé de ce périmètre." + the four qualifications | "Introuvable." (a bare not-found) |
| The OCR qualification | "12 % du corpus recherché provient d'un OCR ; 3 % sous le seuil de qualité" | omitting it (v1's guess in the costume of a proof) |
| A moving population | "Import en cours sur ce dossier — la recherche exhaustive attend un corpus stable" | a partial exhaustive set with no warning |
| Any confidence bound (Epic 4) | "au plus X à Y %" | "risque d'avoir manqué un document pertinent" (FR-23, barred) |

**The one sentence this epic exists to make defensible:** *"Recherché dans tout l'indexé de ce
périmètre ; le registre liste 2 800 illisibles et 1 archive au contenu inconnu."* — a claim a
lawyer can stand behind before a court, not a guess.

---

## Component Patterns (behavioural)

Visual specs live in DESIGN.md; behaviour here.

**Search bar + mode** — one text field, and an **explicit** mode segmented control:
*Suggestions (par sujet)* / *Preuve (terme exact)*. The mode is **never chosen silently** — the
lawyer always knows which truth she asked for. A `scope` chip beside the field shows the wall the
search runs under; results and denominator are scoped to it. Submitting runs one engine and
renders one self-declaring result set; the two are **never** interleaved. (If a later surface
shows both, they are two separately-framed panels stacked, each with its own badge.)

**Suggestive result set** — `{components.suggestive-result}`. Ranked, dashed-open frame, the
suggestive badge, the "les N plus proches" count, per-row proximity + snippet + open-at-passage.
Empty state is a **suggestion-specific** message that explicitly disclaims proof (see the voice
table) — it never says "0 results" in a way that could read as "nothing exists".

**Exhaustive result set** — `{components.exhaustive-result}`. Solid frame, the exhaustive badge,
the scoped denominator, the absence-statement seal, the complete list, the separate register
block. It **refuses** over a moving population (below) rather than showing a partial set.

**Absence statement** — `{components.absence-statement}`. Always present on an exhaustive set
(as the honesty line on a presence, as the whole answer on an absence). Carries the four
qualifications in words; its tone follows whether the scope is clean or qualified. The
denominator figures inside it are the **scoped** ones (a caller never sees a count that betrays
out-of-scope material — the 3.3 guarantee, surfaced).

**Export** — an *Exporter…* action on either result set opens a small dialog offering a
**court-readable document** (PDF) and a data export (CSV). The exported artefact **carries the
truth status, visually and verbally, at its head**, and it survives a format read *without the
system*:
- A **suggestive** export header: *"SUGGESTIONS — liste non exhaustive, classée par proximité.
  Ne constitue pas une preuve d'absence."*
- An **exhaustive** export header: *"RECHERCHE EXHAUSTIVE"* + the **scoped denominator** + the
  four qualifications + the presence/absence claim — the defensible document.
The two exports are visually distinct on their face; a court could not mistake one for the other.

**Query as an audited act** — running a search writes an **audit record** entry (inherited
drawer surfaces it): actor, the term, the **engine (truth status)**, the **scope** it ran under,
and — for an exhaustive query — the **denominator at that moment**. The distinction survives into
the record, so "what was searched, how, and under which wall" is answerable later (FR-15).

---

## State Patterns (Epic 3)

Extends the Epic-2 catalogue.

| State | Rule |
|---|---|
| **Moving population** | An open *import job* on the matter makes the **exhaustive** engine refuse (Story 3.2): the surface states *"Import en cours sur ce dossier — la recherche exhaustive attend un corpus stable"* and offers the worklist line — **never** a partial exhaustive set. The suggestive engine may still run, clearly badged as such. |
| **Empty / no scope** | Fail-closed (Story 3.3): an empty scope yields an empty set with a **0/0 scoped denominator** and *"Aucun périmètre — rien n'a été recherché."* — never the whole corpus. |
| **Suggestive, nothing over the floor** | A suggestion-specific empty message that **explicitly disclaims proof** and points to the exhaustive engine (see voice table). Never "0 results" read as completeness. |
| **Below-quality / OCR** | The share is **stated** in the absence statement (12 % OCR, 3 % below quality), because a term absent from a poor OCR layer is *in the corpus but its text may not be* (Story 3.2 failure path). |
| **Loading** | Non-blocking; a skeleton result frame keeps its badge visible so the truth status is declared before the rows arrive. No full-screen spinner (inherited). |
| **Degraded hit** | A result whose provenance no longer resolves (piece gone, text changed) is shown **as degraded** and marks a containing export degraded (inherited, Story 2.9) — never displayed as though it still resolves. |

---

## The RBAC boundary, in the UI (inherited; Epic-3 specifics)

Scope is a query pre-filter (AD-13/AD-14, Story 3.3), and Epic 3 surfaces it:
- The `scope` chip beside the search field names the wall the search runs under; results, the
  **denominator**, and every qualification figure are computed **within that scope** — the numbers
  cannot betray the existence of material the lawyer may not see.
- A `pièce` outside scope is **not a hit, not a count, not a snippet, not a filename** in either
  engine — asserted adversarially (Story 3.3). The UI never offers a "search all matters" that a
  wall-holder could use to peer across a wall.

---

## The pièce viewer (Story 3.5)

*Stories 3.5; FR-44, FR-14, FR-45; AD-13/AD-14, AD-31. Key-screens mock:
[`mockups/epic-3-piece-viewer.html`](./mockups/epic-3-piece-viewer.html) — the eight screens
below against the real tokens.*

Reading the *pièce* is the job. The viewer is where a lawyer **reads the actual document** —
where *"lu"* becomes true — so reading never requires leaving the tool or sending a byte outside
the firm. It **renders** (not merely extracts) per format, inside the *tenant* boundary, applying
the scope pre-filter, and **opening it is an audited act**.

**The one deliberate exception to the shell.** Everywhere else in APX there is exactly one content
max-width (`{spacing.shell-max}`, 60rem — a DESIGN.md non-negotiable). **The reading canvas is the
single surface that leaves it**: a faithful render of a document — a PDF page, a scan, a
spreadsheet grid — is a *reading plane*, not shell content, and cramming it into 60rem would
betray the very fidelity this story exists to give. The viewer's chrome (the bar, the structure
rail, every control) stays strictly in the system's tokens and language; only the *document
itself* is allowed the room a document needs. This is the viewer's one assumed decision, and it is
deliberate.

### Information Architecture

The viewer is a **focused route**, reached by *opening a pièce* from anywhere a pièce is named —
a suggestive hit (Flow 6), an exhaustive match, a *retained extract* (Epic 4), or a *register*
entry. It is not a tab in the matter; it is the act of opening a document.

```
Open a pièce  ─(scope pre-filter runs FIRST, AD-13/14)→  the viewer route
│
├── BAR   ‹ retour · pièce name · format badge (+ OCR honesty) · scope chip
│          … ouvert·consigné HH:MM (audit) · ⤓ original · ×
├── STRUCTURE RAIL   (adapts per format — pages · thread+attachments · sheet tabs · outline)
├── CANVAS   the rendered document, opened AT the highlighted passage
└── FOOT   "rendu dans le périmètre du cabinet — aucun contenu n'a quitté l'infrastructure"
```

### The render, per format (the fidelity matrix)

Rendered, **not** a flat text dump. Each format keeps its nature; each resolves the passage its
own way; the structure rail carries what that format is *made of*.

| Format | Renders as | The passage is | Structure rail |
|---|---|---|---|
| **Born-digital PDF** | the pages | a text span, scrolled-to + washed | page thumbnails |
| **Scanned PDF** | the **page image** with the **OCR text layer over it** | a **box on the image** | page thumbnails + OCR confidence |
| **`.docx`** | the rendered document (the document-sheet renderer — screen-1 pattern) | a text span | outline / pages |
| **`.xlsx`** | the **sheet grid**, sheet tabs | the **cell** | sheet tabs |
| **`.msg`** | headers · body · **reply chain**, each **attachment its own pièce** | a text span in the body | thread turns + attachments |
| **Images** | the image (the screen-2 renderer without the OCR overlay) | a region box **if** the position resolves | image meta |
| **Un-renderable** | **the honest fallback**: states the limit + **offers the original** | — | — |

A format APX cannot render faithfully **never** yields an empty pane (FR-44): it names the limit
and serves the **original**, which never left the firm. *(Images and `.docx` reuse the screen-1
and screen-2 render patterns; they get no separate screen because they add no new visual pattern.)*

### The passage — "the tool sent you here"

Carried from a *chunk* / *retained-extract* source position, the viewer **opens at it** — scrolls
to it and highlights it — and this is **asserted per format with a planted passage** (the AC). The
highlight is the **`{components.passage-highlight}`** wash: a purposeful gold tint that is the
deliberate echo of the app's own `::selection`, so the mark reads as *the instrument's own
pointer*, not decoration. It is keyboard-reachable (the passage is the first focus stop).

### OCR honesty — the truth axis, extended to a single page

Epic 3's spine is *say which truth you are showing*. The viewer extends it from the result set to
the **page**: a scanned pièce's text came from **OCR**, so the viewer **says so** — the `OCR`
honesty variant on the format badge, and a confidence note in the rail — because *a term absent
from a poor OCR layer is in the corpus but its text may not be* (the same qualification the
exhaustive absence statement carries, AD-42). The instrument never lets recognised text pass for
the page itself.

### The RBAC boundary — the denial that discloses nothing

The scope pre-filter (AD-13/AD-14, the Story 3.3 pre-filter) runs **before any render**. An
out-of-scope pièce is **not renderable, not downloadable, and its existence is not disclosed**
(FR-14/FR-44): the denial is **indistinguishable from a genuine "does not exist"** — no name, no
size, no scope, no format, nothing that would confirm a pièce sits behind a wall. There is no
"open in another matter" affordance a wall-holder could use to peer across a wall.

### Opening is an audited act (ties FR-45)

Opening a pièce writes an **audit record** entry — and this is *the fact that distinguishes a
*validation act* performed **after reading** from one performed from the list*. The bar shows
*"ouvert · consigné HH:MM"* so the lawyer sees the act is recorded. Opening an attachment (its own
pièce) is its **own** audited open.

### The tenant boundary

Rendering happens **inside the tenant** — no pièce content (bytes, page images, OCR text) is sent
to any third-party rendering or conversion service, **in any deployment**. The foot line states
it; it is a load-bearing product promise, not a reassurance.

### State Patterns (the four states — frontend-quality discipline)

| State | Rule |
|---|---|
| **Empty / un-renderable** | Never an empty pane. States the limit and **offers the original** (FR-44). The "no pièce selected" resting state likewise invites, never blanks. |
| **Loading** | **Progressive** (FR-44 failure path): the structure rail is navigable and the first page renders while the rest streams; the interface stays live — **never a full-screen block, never a client exhausted**. |
| **Error / out-of-scope** | The **non-disclosing denial** (above). A pièce whose provenance no longer resolves (bytes gone, text changed) is shown **as degraded**, never as though it still resolves (inherited, Story 2.9). |
| **Real density** | A 340-page PDF (page-by-page), a deep `.msg` chain, a dense `.xlsx`, a poor scan — each renders without exhausting the client. **Over the configured render bound** → the viewer *refuses to render* and offers the **original** or a page-by-page read; the bound protects the reader's machine and hides nothing. |

### Accessibility Floor (delta)

Inherits the Epic-2/Epic-3 floor. Viewer specifics:
- **Keyboard-first**: the passage is the first focus stop; the structure rail, the attachments,
  the *original* action, and *close* are all keyboard-operable. Reading at the passage is not
  mouse-only.
- **The render region is a labelled region** naming the pièce and its format, so a screen reader
  announces *"bail commercial, PDF, ouvert au passage"* before the content.
- **OCR is spoken**, not only coloured: the `OCR` badge and the confidence are read verbatim — a
  screen-reader user learns the text is recognised, not native.
- **The denial is announced** as an ordinary "introuvable", carrying no side-channel a sighted
  user would not also get.

### Key Flow 7 — Claire reads a pièce at the passage

*Stories 3.5; FR-44/FR-14/FR-45.*

1. From a suggestive hit (Flow 6) — or, later, a *retained extract* behind a ranking (Epic 4) —
   Claire clicks **ouvrir au passage**. The scope pre-filter passes: it is her wall.
2. The viewer opens on *« Bail commercial — 12 rue de la Paix.pdf »*, the document **rendered**,
   scrolled to **Article 4**, the *dépôt de garantie* clause washed in gold. **★ Climax beat:**
   she is reading the **actual document, at the exact clause**, without leaving the tool and
   **without a byte leaving the cabinet** — and the bar shows the open is *consigné*, so a
   validation act she performs now is provably *after reading*, not from the list.
3. The source was a *`.msg`*: she opens its **`annexe-3.xlsx`** attachment — **its own pièce, its
   own audited open** — and reads the *clause de non-concurrence* cell (0 €), confirming the email's
   claim in the figures.
4. Had the pièce been outside her scope, step 2 would have been the **non-disclosing denial** —
   she would learn *nothing* about a pièce behind a wall.
5. Had it been a 512 Mo scan, it would have opened **progressively** — page 1 first, the rail
   already navigable — never blocking her screen; and a `1,2 Go` archive over the render bound
   would have **offered the original** rather than trying to load it.

---

## Accessibility Floor (delta)

Inherits the Epic-2 floor. Epic-3 specifics:
- **Truth status is word + glyph + framing, never colour or glyph alone.** `≈ SUGGESTIF` /
  `= EXHAUSTIF` are read verbatim by a screen reader; the dashed vs solid frame is reinforced by
  the word. Colour is never the sole carrier of "suggestion vs proof" (the palette barely uses
  colour for it by design).
- **The result frame is a labelled region** (`aria-label` naming its truth status), so a screen
  reader announces *"suggestions, non exhaustives"* or *"recherche exhaustive, ensemble complet"*
  before the rows.
- **The denominator inside an exhaustive set** keeps its `aria-live="polite"` and `tabular-nums`
  from Epic 2.
- **Keyboard-first**: the mode toggle, submit, each result row's open-at-passage, and the export
  dialog are all keyboard-operable; the flagship "prove an absence" path is not mouse-only.

---

## Key Flows

Named protagonist (from EXPERIENCE.md): **Maître Claire Fontaine**, litigation associate; her
supervisor **Maître Sophie Roux** holds the wider scope.

### Flow 5 — Prove the term appears nowhere (the defining Epic-3 flow)

*Stories 3.2, 3.4; AD-20/AD-38/AD-42/AD-21.*

1. Claire must tell a court that a term — *« clause de non-concurrence »* — appears **nowhere** in
   a four-year matter. In the matter's **Recherche**, she picks the **Preuve (terme exact)** mode,
   types the term, and runs it. The `scope` chip shows she is searching her own wall.
2. The engine runs over **one snapshot** of the scoped corpus. **★ Climax beat:** the answer is an
   **exhaustive** result set, badged `= EXHAUSTIF`, whose absence-statement seal reads — in her
   language, on its face — *"Aucune occurrence de « clause de non-concurrence ». Recherché dans
   tout l'indexé de ce périmètre. Le registre liste 2 800 pièces illisibles et 1 archive au
   contenu inconnu ; 12 % du corpus recherché provient d'un OCR, 3 % sous le seuil de qualité."*
   It is not *"introuvable"*; it is a claim **with its edges shown**.
3. A **register name-match** appears in the separate block beneath: one unreadable scanned file
   whose *filename* contains the term. It is not inside the exhaustive set — it is flagged as *a
   pièce the search could not read*, exactly the qualification that keeps the claim honest.
4. She clicks **Exporter…** → **PDF**. The exported document carries *"RECHERCHE EXHAUSTIVE"*, the
   scoped denominator, and the four qualifications at its head — a document she can put in front of
   a court **without the system**. The query is in the audit record with its truth status, scope,
   and denominator.
5. Had an import been running on the matter, step 2 would instead have **refused** — *"Import en
   cours — la recherche exhaustive attend un corpus stable"* — never a partial proof. The wall she
   cannot see never enters her denominator (3.3).

### Flow 6 — Find pièces about a topic (the suggestion, never mistaken for a proof)

*Story 3.1; FR-12.*

1. Claire wants pièces *about* indemnity, not an exact term. She picks **Suggestions (par sujet)**
   and searches *« indemnisation du préjudice »*.
2. The answer is a **suggestive** set, badged `≈ SUGGESTIF` on a **dashed-open** frame, headed
   *"Les 20 pièces les plus proches sur ce périmètre"* — each row a snippet, a proximity meter, and
   *ouvrir au passage*. **★ Climax beat:** nothing on the surface reads as *"these are all of
   them"* — the dashed edge, the word *suggestif*, and the *"les plus proches"* count make it
   impossible to mistake a suggestion for a proof. If she needs completeness, the **Preuve** mode
   is one click away, and the two answers never share a list.
3. She opens the nearest hit at the highlighted passage (the viewer, 3.5), reads it, and — later,
   in Epic 4 — acts on it. The suggestion did its job: it *found*, and it never pretended to
   *prove*.

---

## Inspiration & Anti-patterns (Epic-3 delta)

**Salvage / extend.**
- **The denominator, reused as a proof's spine.** The exhaustive set does not invent a new number
  object; it reuses the permanent-denominator equation, so "how much did you search?" has one
  answer everywhere.
- **Honest unknowns, extended to the searched set.** Epic 2 states unknown cardinality in words;
  Epic 3 extends the same honesty to the OCR / below-quality shares of what was searched.

**Anti-patterns (do not repeat).**
- **A merged result list.** Interleaving a suggestion and a proof, or a single "Search" that hides
  which engine ran, is the exact confusion FR-15 exists to prevent.
- **A bare "not found".** An absence with no denominator and no qualifications is v1's *"guess in
  the costume of a proof"* — barred.
- **A false-precise similarity %.** *"87 % de similarité"* is an invented number; proximity is an
  ordering, shown as such.
- **A count phrased as a total on a suggestion.** *"20 résultats"* on a suggestive set reads as
  completeness — say *"les 20 plus proches"*.
- **The FR-23 banned phrasing** anywhere near a bound — *"risque d'avoir manqué…"* stays barred in
  every locale.
