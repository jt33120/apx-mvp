---
name: APX — the validation act
description: The experience contract for Story 5.8 (FR-45/FR-44) — "a human read this" as a real per-pièce gesture, its two provenances kept apart, and a bulk path that is permitted and never undetectable. Peer of DESIGN.md; extends EXPERIENCE-EPIC5-DRAWER.md, EXPERIENCE-EPIC4.md and EXPERIENCE-EPIC3.md.
status: final
updated: 2026-08-13
sources:
  - ./DESIGN.md                    # the visual identity — tokens referenced by name, never redefined
  - ./EXPERIENCE-EPIC5-DRAWER.md   # the drawer's four bands; band 4 holds the disabled control this story lights up
  - ./EXPERIENCE-EPIC4.md          # the triage table — the row this act attaches to
  - ./EXPERIENCE-EPIC3.md          # the viewer — « ouvert · consigné », the fact this act reads
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md   # FR-45, FR-44, §13 q.5, SM-C2
  - _bmad-output/planning-artifacts/briefs/brief-apx-mvp-2026-07-20/addendum.md  # §180 — why bulk is permitted
---

# The validation act — Story 5.8

> **Why this contract exists although the epic did not ask for one.** Story 5.8 carries no *"UX
> pass required"* note, unlike 5.7 and 6.1. Two of its three surfaces are already designed — the
> drawer reserved a disabled row for this act, the viewer already states *« ouvert · consigné »* and
> names FR-45 as the reason it matters. **The bulk path is designed nowhere**, and the triage table
> has no selection model at all. More to the point, this is the one story in the product where the
> **wording is the mechanism**: FR-45 does not ask for a button, it asks for a gesture whose meaning
> is stated in the lawyer's language and whose record cannot flatter her. That is an experience
> contract by nature, not decoration on one. Written before implementation, on the same footing as
> 5.4's and 5.7's.

**The failure this whole architecture must not end in.** Twelve stories built a record that cannot
be forged, cannot be silently truncated, and leaves the building in a form a court can read. All of
it is worth nothing if the last gesture — *a human read this* — can be produced by a click-through.
v1 sold that claim and never built it: it rested on a phrase, *validation act*, that no requirement
created. This story creates it, and the design problem is not how to make the gesture easy. **It is
how to make the record of it true when it was easy.**

**Key screens:** [`mockups/epic-5-validation-act.html`](./mockups/epic-5-validation-act.html) — the act
on one pièce (both provenances), the bulk confirmation, the badge states, and §7 of the exported
record. **The spines win over the mockup on any conflict.**

---

## Foundation (delta)

Inherits DESIGN.md wholly and the Epic-3/4/5 experience contracts. No new form factor, no new
surface of its own: the act attaches to three surfaces that exist. What is new is a **confirmation
step** (bulk) and a **state on a row** (validated, with its provenance).

**The act is available from exactly three places**, and FR-45 names them: the triage table, the
viewer, the audit drawer. The same act, the same sentence, the same record from all three. A fourth
entry point is not a convenience; it is a fourth chance for the wording to drift.

---

## Information Architecture

```
Triage table (Epic 4)                     Viewer (Epic 3)              Drawer (5.7)
├─ row                                    ├─ bar: « ouvert · consigné »  ├─ band 4
│  ├─ [ ] selection box  ── selects, ─┐   │                              │  └─ « J'ai lu cette
│  │      NEVER validates             │   └─ {validation-act}            │      pièce… »
│  ├─ {validation-badge}  (state)     │      (full sentence, inline)     │      {validation-act}
│  └─ « J'ai lu cette pièce… »        │                                  │      + proposed entry
│      {validation-act}               │                                  │
└─ selection bar (n selected)         │
   └─ « Valider les n pièces… »  ─────┘
      → {bulk-validation-confirm}   ← the count AND the split, before anything is written
```

**One thing the diagram is making a claim about.** The selection box and the validation control are
**different controls in different columns**. A checkbox that both selects and accepts is the
click-through, drawn.

---

## The act itself (FR-45)

### The sentence is the act, and it is never abbreviated

> **« J'ai lu cette pièce et j'accepte l'appréciation de l'outil. »**

`{components.validation-act}` renders that sentence **in full**, as the control's own text, on all
three surfaces. Not a tooltip, not a confirmation that appears after a button called *« Valider »*.

**Why the full sentence and not a verb.** The record will say a lawyer asserted this. A control
labelled *« Valider »* lets her assert it without reading it, and the entry it writes would then be
a claim she never made in the words that were recorded. The sentence costs one line of screen and
it is the only thing standing between this product and v1's unbuilt promise.

The act names the **ranking version** it accepts (AD-23 — no unqualified reference to a ranked
figure): *« …l'appréciation de l'outil, classement v3. »* What is accepted is a named version's
assessment, not a timeless verdict.

### The two provenances, stated *before* the act — never discovered after

FR-45's load-bearing field: **whether the pièce was opened in the viewer before the act**. The
surface states which one this will be, before she commits, in `{components.validation-provenance}`
directly beneath the sentence:

| She has opened it | The panel says | Tier |
|---|---|---|
| yes | « Vous avez ouvert cette pièce le 13 août à 14 h 32. Cette validation sera inscrite comme **lue**. » | kept |
| no | « Vous n'avez pas ouvert cette pièce. Cette validation sera inscrite comme **acceptée depuis la liste**, non comme lue. » | review |

**Neither one blocks.** Validating from the list is permitted — it is a legitimate act over a pièce
whose row already says enough. What is refused is doing it *without knowing that is what the record
will say*. This is the product's targeted-friction principle (§10) at its sharpest: the friction is
not a dialog, it is **one sentence naming the consequence**, and it costs nothing to the lawyer who
has actually read the document.

**« Vous »**, not « la pièce a été ouverte ». The fact recorded is about the actor performing the
act. Another lawyer's open is not this lawyer's reading, and a panel that said *« ouverte le 3 août »*
without saying by whom would let Claire's entry inherit Marc's diligence.

**The date, not a tick.** The provenance line prints *when* she opened it. « Ouverte » alone is true
of an open six months and three rankings ago; the reader of the export — and the lawyer herself —
needs the distance, and a boolean is a lossy projection of a timestamp.

---

## The bulk path — permitted, and never undetectable (FR-45)

**Why it exists at all.** A 1 700-row grid grows a select-all because every grid does. Forbidding it
produces a workaround, not compliance; leaving it unspecified produces 1 400 pièces marked *read by
a human* in four minutes, which is documented consent that was never given. It is **permitted and
made impossible to hide** — `addendum.md` §180.

### The confirmation names the count *and* the split

`{components.bulk-validation-confirm}` — a confirmation, reached from the selection bar, that
cannot be dismissed into the act. It states three numbers and one consequence:

> ### Valider 180 pièces
>
> Vous êtes sur le point de déclarer avoir lu **180 pièces** et d'accepter l'appréciation de l'outil
> pour chacune, sur le **classement v3**.
>
> Vous en avez ouvert **12**. Les **168** autres seront inscrites comme **acceptées depuis la
> liste**, jamais comme lues.
>
> Chaque pièce recevra sa propre entrée au journal, portant la taille du lot et son identifiant.
> Un lecteur du dossier exporté pourra toujours distinguer 12 lectures de 168 acceptations.

The confirming verb **names the count**: « Valider les 180 pièces ». Never « Confirmer », never
« OK ». A verb that names its object cannot be clicked past by muscle memory, and the count in the
verb is the last place the number is visible before it becomes 180 rows in a court document.

**The split is the whole point.** A confirmation naming only the total — *« Valider 180 pièces ? »* —
is the compliance theatre this product exists to avoid: it looks like friction, it obtains consent,
and it tells the lawyer nothing she did not already know. The 12/168 split tells her exactly what
the record will say about her.

### What the record carries, and what the export counts separately

Each pièce gets **its own entry**: marked `bulk`, carrying the size of the set and a **shared batch
identifier**, and carrying its own opened-or-not fact — *not* a blanket "not opened" over the batch.
A pièce in the batch that she *had* opened is recorded as opened, because it was.

The export counts the two registers **separately and never pools them** (§7, and §13's answer to
question 5). SM-C2 watches the ratio: a firm whose bulk share climbs is a firm whose audit surface
has become noise, and that is observable here without one byte of telemetry.

### The one thing the selection bar must not do

There is **no select-all-and-validate**. Selecting is one gesture; validating the selection is
another, and the confirmation sits between them. Nor does the selection bar offer validation as its
*primary* action — the primary action of a selection in the triage table is Epic-4's, and validation
sits beside it, weighted equally, never pre-focused.

---

## The state afterwards (`{components.validation-badge}`)

A validated pièce says so on its row, in the drawer, and in the export — with **four facts, never
one tick**:

> ✓ **Validée** · Me Durand · 13 août 14 h 36 · **lue** · classement v3

| Fact | Why it is on the badge and not in a detail panel |
|---|---|
| who | the assertion is personal; an unattributed « validée » is the v1 claim again |
| when | the reader judges distance; a badge without a date ages invisibly |
| **lue** / **depuis la liste** | the FR-45 distinction, carried to every surface that shows the state — a badge that dropped it would launder 168 acceptances into 168 readings at the last step |
| the ranking version | what was accepted was *a named version's* assessment |

**Bulk is visible after the fact, not only at the moment.** A pièce validated in a batch says
« depuis la liste · lot de 180 ». The marker does not fade with the session.

### Stale — the version moved under the acceptance

A validation accepted a *named version's* assessment. When the matter is re-ranked, the badge does
not silently keep its green check over values that no longer exist:

> ✓ Validée sur le **classement v3** — le classement actuel est **v4**. *(review tier)*

**This is not an invalidation.** The act happened, it is in the record, and nothing erases it. It is
a statement about what the acceptance refers to, and it is the same rule the whole product runs on:
no unqualified reference to a ranked figure (AD-23), and no comparison whose right-hand side is not
the same thing as its left.

### Reversal — a new entry, never an erasure

« **Retirer ma validation** » (FR-45). The reversal writes a new entry; both remain readable, and the
badge afterwards states that the pièce *was* validated and that the validation was withdrawn, with
both dates. The drawer's band-4 rule holds: the action names its own reversal in the same breath —
« retirez-la — la validation et son retrait restent tous deux inscrits ».

---

## Voice and Tone (delta)

| Situation | Say | Never |
|---|---|---|
| The control | « J'ai lu cette pièce et j'accepte l'appréciation de l'outil. » | « Valider » · « Marquer comme lu » |
| Provenance, opened | « Vous avez ouvert cette pièce le 13 août à 14 h 32 — inscrite comme **lue**. » | « ✓ lu » |
| Provenance, not opened | « …sera inscrite comme **acceptée depuis la liste**, non comme lue. » | « vous n'avez pas encore consulté ce document » (a scolding, not a fact) |
| The bulk confirmation | « Vous en avez ouvert 12. Les 168 autres seront inscrites comme acceptées depuis la liste. » | « Valider 180 pièces ? » |
| The confirming verb | « Valider les 180 pièces » | « Confirmer » · « OK » |
| A validated row | « Validée · Me Durand · 13 août · lue · classement v3 » | a bare ✓ |
| After a re-rank | « Validée sur le classement v3 — le classement actuel est v4. » | keeping the check silently |
| Reversal | « Retirer ma validation — la validation et son retrait restent tous deux inscrits » | « Annuler » · « Supprimer » |

**Banned outright, and this is the story where it would arrive:** any phrasing in which time,
scrolling, or presence produces acceptance — « lu automatiquement », « consulté », « vu ». **The
product has exactly one verb for this and it is performed by a person.**

---

## State Patterns

| State | Row / drawer | Export |
|---|---|---|
| Never validated | no badge — **not** « non validée » | listed among the not-validated, counted |
| Validated, read | kept-tier badge with the date | §7, individual register |
| Validated from the list | **review**-tier badge, « depuis la liste » | §7, bulk or individual — counted apart |
| Validated, then re-ranked | review-tier, both versions named | §7 carries the accepted version |
| Withdrawn | neutral badge, both dates, both entries readable | both entries in §7 |
| Out of scope | the row was never there (Epic-4 pre-filter) | not in the document |
| Nobody has validated anything | the export prints **0 actes de validation** — now a true zero about the firm | §7 is a real section as of this story; `pending-section` is retired from it |

**The last row is the story's quiet deliverable.** Until now §7 printed a sentence saying the act did
not exist. From this story it prints a number, and a **0 finally means what a reader would take it
to mean.** The pending sentence is not "replaced by a zero" — it is retired because the thing it was
protecting against no longer exists.

---

## Accessibility Floor (delta)

- The validation control is a **button carrying its full sentence as its accessible name** — a
  screen-reader user hears the assertion, not the word « valider ».
- The provenance line is `aria-describedby` on that button: the consequence is announced **with**
  the control, never as a separate region a keyboard user could pass by.
- The bulk confirmation is a **modal dialog** with focus trapped, its heading naming the count; the
  confirming button is **not** the initially-focused element — `Esc` and the cancel path are, so the
  keyboard's default gesture is *not* to accept 180 documents.
- The badge's provenance is **text, never colour alone**: « lue » / « depuis la liste » are read
  verbatim. The kept/review tiers carry the same distinction visually for everyone else.
- Every path — control, confirmation, reversal — is keyboard-reachable (FR-59).

---

## Key Flows

### Flow 16 — Claire reads 12 and accepts 168 (the defining flow)

*Stories 5.8, 3.5, 4.10; FR-45/FR-44.*

1. Claire has 180 pièces above **the line** on `classement v3`. Over the weekend she opens **12** of
   them in the viewer at the passage; each open writes its own audit entry and the viewer bar shows
   *« ouvert · consigné »*.
2. On each of those twelve she clicks **« J'ai lu cette pièce et j'accepte l'appréciation de
   l'outil. »** Beneath it: *« Vous avez ouvert cette pièce le 13 août à 14 h 32 — inscrite comme
   lue. »* Twelve entries, each marked read.
3. Monday morning, the remaining 168 are ones whose row and one-line justification she considers
   sufficient. She selects them and clicks **« Valider les 168 pièces… »**.
4. **★ Climax beat:** the confirmation does not ask *"are you sure?"*. It tells her what the record
   will say: *« Vous n'en avez ouvert aucune. Les 168 seront inscrites comme acceptées depuis la
   liste, jamais comme lues. »* She confirms with a verb that names the count. **She has done
   nothing wrong, and the record will not pretend she did more than she did.**
5. Six weeks later the *bâtonnier* holds the exported record. §7 reads: **12 lectures, 168
   acceptations depuis la liste, en un lot du 16 août.** He can tell the two apart, which is the
   entire point, and neither Claire nor the product had to be dishonest for the number to be
   flattering — it simply isn't.

### Flow 17 — Marc validates, then the matter is re-ranked

1. Marc validates a pièce on `v3` — read, badge in the kept tier.
2. A new *case theory* arrives; the matter is re-ranked to `v4`. The tool's assessment of that pièce
   has changed.
3. His badge now reads *« Validée sur le classement v3 — le classement actuel est v4 »*, in the
   review tier. **Nothing was erased and nothing was invalidated**; the badge says what the
   acceptance referred to, and a supervising partner reading the row learns that the acceptance and
   the current assessment are not the same object.

---

## Inspiration & Anti-patterns

**Taken from:** the read-receipt convention, inverted. A read receipt asserts a fact about a system
event; this asserts a fact about a person, so the person's own words carry it.

**Refused, and each was available:**

| Anti-pattern | Why it is refused |
|---|---|
| A « lu » checkbox column | a checkbox is state, not an assertion; and a column of them is a select-all away from the failure this story exists to prevent |
| Auto-validating on scroll, dwell time, or opening | FR-45 forbids it by name, and it is the single most tempting feature in this file |
| Forbidding bulk | produces a workaround, not compliance (`addendum.md` §180) |
| A bulk confirmation naming only the total | obtains consent while telling her nothing — friction without information |
| A green ✓ with no provenance | launders acceptances into readings at the last surface before the court |
| Hiding the bulk marker after the session | the export must be able to tell 12 from 168 six weeks later |
| « Tout valider » in the selection bar's primary slot | the primary gesture over a selection is not mass acceptance |

---

## Handback — Story 5.8

**Built here:** the act on three surfaces with its full sentence; the provenance stated before the
act and recorded per pièce; the bulk path with its count-and-split confirmation, per-pièce entries,
batch identifier and separate counting; the badge with its four facts and its stale state; the
reversal as a new entry.

**Retired here:** the drawer's disabled row (band 4) and the export's two `pending-section` blocks —
§7 and the accepted-as-is half of §8 become real sections carrying real numbers, including a
truthful zero.

**Open, and owned elsewhere:** atomicity of the act with its record under a read-only audit store
(Story 5.9, FR-53); the retained-set export's *whether validated and by whom* column (Story 6.1,
FR-46); SM-C2's inclusion in the content-free projection (Story 6.2, FR-32).
