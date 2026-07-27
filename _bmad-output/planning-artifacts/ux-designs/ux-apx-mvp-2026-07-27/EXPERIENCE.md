---
name: APX — Experience (Epic 2)
description: Information architecture, behaviour, states, and journeys for the Epic-2 user-facing surfaces of APX mass-document triage — the home (worklist + matters), folder-selection onboarding, the non-blocking import job, the completion summary, and the failure register. Peer to DESIGN.md, which owns visual identity.
status: final
updated: 2026-07-27
scope: Epic 2 (the ingestion epic). Foundations (IA, voice, primitives, a11y, i18n) are product-wide and extend to later epics via Update mode.
sources:
  - _bmad-output/planning-artifacts/epics.md            # Epic 2, stories 2.1–2.13
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md  # FR-1..FR-60
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/  # AD-13, AD-24, AD-40
  - apx/web/src/App.tsx                                  # the POC console — embryos of several surfaces
  - docs/context/03-design-and-ux-inventory.md          # salvaged patterns; anti-patterns to avoid
design: ./DESIGN.md
---

# APX — Experience Contract (Epic 2)

> **What this contract must unblock.** Four Epic-2 stories carry *"UX pass required before
> implementation. No UX design contract exists yet."* — **2.1** (folder-selection
> onboarding), **2.6** (the failure register), **2.10** (the completion summary), **2.11**
> (the home = worklist + matters). This document is that contract. A fifth story, **2.7**,
> defines the *permanent denominator* that threads through all of them; it gets its own
> section because it is the spine of the whole experience.
>
> **This contract wins over any mock on conflict.** Token names in `{braces}` reference
> [`DESIGN.md`](./DESIGN.md).

---

## Foundation

**Form factor.** Desktop-first web application, single content column at `{spacing.shell-max}`
(60rem). The archetypal user is a lawyer at a workstation pointing APX at a USB key or a
network share; the machine may be a single box in the firm with no internet (an
architecture non-negotiable). It must stay usable on a tablet but is not designed
mobile-first. No native app.

**UI system.** APX is its own small design system — the React SPA in `apx/web`
(Vite + React 19 + React Router, static build, **no Node runtime ships**, AD-29). There is
no shadcn/MUI dependency; components are the bespoke kit in `tokens.css`, specified visually
in DESIGN.md and behaviourally here. New surfaces compose that kit; they do not introduce a
component library.

**The offline constraint reaches the UI.** No web-font fetch, no CDN, no external asset, no
analytics beacon. Everything renders from system fonts and inlined assets. If a surface
would need a network call to look right, it is designed wrong.

**The three-place model is the mental model.** Everything a lawyer sees rests on one idea:
*every submitted piece is in exactly one of three named places — the corpus, the failure
register, or a declared exclusion.* The UI never contradicts this and never introduces a
fourth place or an unnamed remainder.

---

## Information Architecture

Four top-level surfaces for Epic 2, plus the cross-cutting denominator and the
provenance drawer.

```
Login  (owned auth, AD-15 — already built)
│
└── Home  ── the most-seen surface (Story 2.11)
    ├── [permanent denominator]     scoped to what the user can see (Story 2.7 / FR-28)
    ├── WORKLIST  (top zone)         actionable lines only — what needs a human
    │     └── line ─click→ its referent (a matter, the register, a completion summary)
    ├── MATTERS zone (below)         navigation; each matter's scoped denominator + ticks
    │     └── matter ─open→ Matter detail (denominator · register · triage* · audit)
    │                                   (*triage/judge/recall are Epic 3–5; present as POC embryos)
    └── "Import a folder" ─→ Onboarding

Onboarding  (Story 2.1)             one screen, 3 mandatory + 1 optional
    └── submit ─→ Import job starts, returns you to Home immediately

Import job  (Story 2.2)             NOT a screen — a persistent, collapsed indicator
    └── on finish ─→ Completion summary becomes available (and a worklist line appears)

Completion summary  (Story 2.10)    denominator first, then the tasks this job created
    └── reachable again later from the matter and the audit record

Failure register  (Story 2.6)       reachable from the denominator's "à revoir" term,
    └── from a worklist line, and from a matter. Resolved by state change, never removal.

Provenance / audit drawer  (salvaged pattern)  one click away from any piece, anywhere
```

**Closure check.** Every Epic-2 stated need maps to a surface, and every surface has a
journey that lands there (see Key Flows): *start an import* → Onboarding; *keep working
while it runs* → Import indicator; *see what needs me* → Home worklist; *see what this job
did* → Completion summary; *act on what failed* → Register; *find any piece regardless of
label* → Corpus search (POC embryo, Epic 3 proper); *know nothing was silently lost* → the
permanent denominator.

**Admin (the Cockpit)** — user & scope administration — already exists in the POC and is
Epic-1 territory (Stories 1.5/1.6). It stays a separate admin surface reachable only by
grant holders; Epic-2 does not change it beyond feeding it the custodian/scope vocabulary.

---

## The permanent denominator (Story 2.7 · FR-6 / FR-28 / FR-57)

The spine of the entire experience. **Not a result screen — a permanent, on-screen
accounting.**

**The identity, always true, shown as words and numbers:**

```
submitted  =  in corpus  +  open failure-register entries  +  declared exclusions
```

- Each of the three terms is **separately countable and displayed as its own line**.
  Nothing is in two terms; nothing is in none; there is **no fourth bucket and no unnamed
  remainder**.
- It renders in the **equation component** (`{components.equation}`) — already built as
  `InventoryView`/`.apx-equation` and promoted here to a permanent fixture. Total in serif
  3rem on the left; the three terms stacked on the right, each colour-coded to its tier
  (`{colors.kept}` corpus · `{colors.review}` register · `{colors.discard}` exclusions).
- Directly beneath it, the **verdict seal** (`{components.verdict}`) states the identity in
  a sentence and turns `review`-toned if it ever fails to balance — a failure that is a
  **release blocker** (SM-3), so in production the seal is effectively always green; when it
  is not, that is the loudest thing on the screen.

**Two honesty rules the UI must obey:**

1. **Provisional while enumerating.** While an import is still expanding containers and
   enumerating, `submitted` is **labelled provisional** — the total carries a small
   *"en cours d'inventaire"* qualifier and the equation does not claim to balance yet
   (FR-57). It freezes at completion of enumeration-and-expansion.
2. **Unknown cardinality stated in words.** A container that could not be opened is **one
   entry with cardinality `unknown`**, and the denominator says so explicitly —
   *"1 archive non ouverte, contenu inconnu"* — **never** a silent *"· 1 non indexé"*
   (Story 2.4). The count you can prove and the count you cannot are never blended.

**Scoping.** The home denominator is **scoped to what the viewer can see** (their RBAC
scope). Each matter row also carries its own *scoped denominator*. The number is never
firm-global for a user who cannot see the whole firm.

**Filesystem noise** is a declared, configured, countable **exclusion class**, reported as
its own line — *"1 240 exclus — bruit système"* — one click from the list of what was
excluded. It is neither silently dropped nor allowed to dominate the register.

---

## Voice and Tone

The governing rule, from the client review (Max, a practising lawyer, on the legacy
build: *"je pense que les avocats ne vont pas comprendre de quoi il s'agit"*): **wherever a
lawyer reads, speak the lawyer's language; a technical state is never surfaced as a task.**

**Principles**
- **Verb-first tasks.** A worklist line is an instruction the reader can act on:
  *"Fournir le mot de passe de 3 pièces protégées"*, not *"3 pieces: status=password-protected"*.
- **Name the thing in the world, not the mechanism.** *pièce*, *dossier*, *périmètre*,
  *bordereau* — never *chunk*, *embedding*, *vector*, *worker*, *job id*. "Chunks" on a
  lawyer's screen was a named legacy defect (design inventory §6.2).
- **Count honestly.** "au plus X à Y%" for a bound; "contenu inconnu" for what cannot be
  counted; never a false-precise single number where a range is the truth.
- **Never a raw error string.** `e.message` rendered as red text is barred (a named legacy
  weakness, §6.6). Every failure the user sees is a **classified, actionable line** drawn
  from the enumerated error set, with a redacted diagnostic available behind "détails".
- **French legal terms of art stay French** even in English UI — *ordonnance 145 CPC*,
  *conclusions*, *veille*, *bordereau de pièces*, *pièce* — and are marked as untranslated
  source, never machine-translated (a mistranslated legal term is a liability).

**Microcopy examples (binding)**

| Situation | Say | Never |
|---|---|---|
| A protected file | "3 pièces protégées — fournir le mot de passe" | "3 files: AES-encrypted, decrypt failed" |
| An unopened archive | "1 archive non ouverte — contenu inconnu" | "· 1 not indexed" |
| A zero-file folder | "Aucun fichier lisible dans ce dossier. Rien à indexer." | an error dialog / a silent no-op |
| A null-scope write refused | "Import interrompu : aucun périmètre défini. Rien n'a été écrit." | "NULL constraint violation on rbac_scope" |
| Import running | "Import en cours — 812 / 4 812 pièces" (collapsed, non-blocking) | a modal spinner blocking the screen |
| Consistency holds | "Inventaire cohérent : 4 812 = 4 590 + 180 + 42" | (nothing — always show it) |

---

## Component Patterns (behavioural)

Visual specs live in DESIGN.md; here is how each behaves.

**Worklist line** (`{components.worklist-line}`) — the atom of the home top zone and the
completion summary. Behaviour: (a) **aggregates** — "3 pièces protégées", not three lines;
(b) **caps** — beyond a configured count the zone shows the top-N by urgency with a
*"voir les N autres"* expander, so at the *design target* it cannot become the log it
forbids (FR-27); (c) **clicks through** to its referent and nothing else — a line is never
a dead status. A **non-actionable** line is never shown in the worklist.

**Matter row** (`{components.matter-row}`) — navigation, not a task. Shows the matter name,
its **scoped denominator** inline, and small ticks: *job en cours* / *classement obsolète* /
*échantillonnage ouvert* / *dernière activité {date}*. Expands in place to the matter
detail (denominator · register slice · the POC's triage/judge/recall embryos · audit
journal). **Law:** no line type appears in both the worklist and the matters zone
(asserted by test, FR-60) — a matter is orientation; a worklist line is a task.

**The equation** (`{components.equation}`) — see the denominator section. Updates live as a
job progresses; shows the provisional qualifier during enumeration; is `aria-live="polite"`.

**Progress indicator** (`{components.progress-indicator}`) — persistent, collapsed,
non-blocking (Story 2.2). Docks in the app bar as *"Import — 812 / 4 812"* with the 3px
gold fill; collapsible to a pill; **survives navigation and a page reload** (the job lives
server-side; the UI re-attaches). On resume after a worker kill it simply continues its
count — *no indexed piece re-counted as new, no piece skipped* — which the UI reflects
without drama. **Never a modal.**

**Register row** (`{components.register-row}`) — filename + mono path, error-class chip,
cardinality, resolution state, timestamp, and a **retry** action. Retry re-runs ingestion
for that piece only; success moves the row to `resolved` (faded, history kept), and the
denominator's "à revoir" term drops by one. A `password-protected` row offers a
**credential-supply** action, never an override. A **bulk retry** over a filtered set (by
class / matter / custodian) produces **one** audit entry naming the set, not one per piece.

**Provenance / audit drawer** (salvaged, highest-value legacy pattern) — a right slide-over
reachable from **any** piece anywhere (a register row, a matter, a search hit, later a
triage cell). It answers *"where did this come from and what happened to it?"*: submitted
path(s), custodian(s) as a queryable set, extraction method + extractor version, container
provenance, and the audit journal entries for that piece. Provenance is always **one click
away, from anywhere** — and it is read-only truth, not an editable field.

---

## State Patterns

Every Epic-2 surface must handle this catalogue. "Not designing the empty/error state" was
a named legacy weakness (§6.14, §6.6); here they are first-class.

| State | Rule |
|---|---|
| **First run / empty** | Home with no matters shows a single, calm call to action — *"Importer un dossier"* — and an explanation of the three-place model. Never a blank screen, never a fake demo corpus. |
| **Loading** | Non-blocking always. Skeleton rows for lists; the equation shows its last known value with the provisional qualifier. No full-screen spinner. |
| **Running (import)** | The denominator is live and provisional; the progress indicator is docked; the rest of the app is fully usable. |
| **Zero result** | A zero-readable-file folder is a **completed job with a 0/0 denominator** and one explanatory worklist line — not an error, not a no-op (Story 2.1 failure path). |
| **Unknown cardinality** | Stated in words in the denominator and on the register row ("contenu inconnu"); never blended into a count. |
| **Error (loud, fail-closed)** | A null/empty scope, a job that could not write — rendered `danger`-toned, plainly: what failed, that **nothing was written**, and the one action to take. |
| **Error (classified, actionable)** | Everything in the register — a `review`-tone line from the enumerated class set, with a retry and a "détails" disclosure carrying the redacted diagnostic. |
| **Resolved** | Faded to muted, history retained, removed from the open count. Never deleted. |
| **Degraded** | A provenance/extract that no longer resolves (piece gone, text changed) is shown **as degraded wherever it appears**, and marks any containing export as degraded — never displayed as though it still resolves (Story 2.9). |

---

## Interaction Primitives

- **Folder pick** — `<input type="file" webkitdirectory>` traverses subfolders to arbitrary
  depth; the submitted structure is reconstructible from the payload record alone
  (Story 2.1). The POC already does this.
- **Non-blocking submit** — starting an import returns the user to Home immediately with the
  indicator docked; it does **not** hold the screen on an "Analyse…" spinner (the POC's one
  behaviour to change).
- **Expand-in-place** — matter rows and register groups open beneath themselves; no route
  change, no modal, state preserved (the POC's `MatterRow` pattern, kept).
- **Click-through-to-referent** — every worklist and completion line resolves to exactly one
  destination.
- **Retry / bulk-retry** — single-row retry, and filtered multi-select → one bulk retry with
  one audit entry.
- **Credential supply** — a scoped, non-persisted prompt for a password-protected piece.
- **Keyboard-first** — every interactive affordance is reachable and operable by keyboard
  (see Accessibility Floor). The flagship interactions are not mouse-only.

---

## Accessibility Floor (behavioural)

Directly answering the legacy app's a11y inconsistencies (§6.9), where "the flagship
interaction was mouse-only".

- **Focus-visible everywhere.** Every interactive element takes the gold ring
  (`{elevation.ring}`) on `:focus-visible`. No exceptions, including chips-that-act and
  slide-over controls.
- **Keyboard-reachable flagship paths.** Folder pick, submit, worklist click-through,
  register retry, drawer open/close, bulk-select — all operable without a mouse. Any
  hover-reveal has a focus/click equivalent.
- **Live regions.** The denominator and the progress indicator are `aria-live="polite"` so a
  screen reader hears the count settle. The progress bar carries `role="progressbar"` with
  `aria-valuenow/max`.
- **Semantic structure.** One `h1` per surface; the worklist and matters zones are labelled
  landmarks; the drawer is `role="dialog"` `aria-modal` with scroll-lock and focus-trap
  (the legacy `MobileNav` did this well — reuse it).
- **Reduced motion.** `prefers-reduced-motion` short-circuits the progress-fill animation and
  any reveal to its end state.
- **Colour is never the only signal.** A verdict/tier is always word + colour (chip label,
  seal sentence), never colour alone.

---

## The RBAC boundary, in the UI (FR-1 / FR-49 / AD-13)

Scope is resolved at query time from the matter's scope (AD-13); the UI must make the wall
visible and un-crossable, in **both** directions:

- The **scope selector** at onboarding offers only scopes the user **holds or may grant** —
  she **cannot narrow** material out of her supervisor's sight, and **cannot broaden** it to
  a group she does not hold. Asserted by test in both directions.
- The home denominator and every matter list are **scoped to the viewer**; a matter outside
  scope is not merely hidden from actions — it is not in the count.
- Register entries whose **matter could not be determined** are visible **only** to the
  tenant-wide administrative grant holder — for everyone else they are not on the list.

---

## i18n foundation (product-wide; full surface is Epic 6)

Stated here so Epic-2 copy is authored correctly from line one, not retrofitted.

- **Namespaced semantic keys, FR/EN as peers** (`worklist.password_protected: {fr, en}`) —
  **never** French-as-key (the legacy model, where any copy edit silently broke the English
  overlay; §7). Max has already rewritten core sentences once; copy *will* churn.
- **Content stays in its language.** Corpus text, matter names, custodians, quoted extracts
  are data, never translated by the toggle.
- **Legal terms of art stay French** and are visibly marked as untranslated source.
- **Locale-aware dates/numbers** — no hard-coded `fr-FR`. (Deferred build: Epic 6 / FR-6.4.)

---

## Key Flows

Named protagonist: **Maître Claire Fontaine**, associée, litigation. She has four years of a
matter — mostly `.msg` with attachments and scanned PDFs — on a USB key. Her supervisor is
**Maître Sophie Roux**, who holds the wider scope.

### Flow 1 — The handover (Onboarding → non-blocking import → completion summary)

*Stories 2.1, 2.2, 2.10.*

1. Claire lands on **Home**. It is calm: her worklist (maybe empty), her matters below. She
   clicks **"Importer un dossier"**.
2. **Onboarding, one screen.** Three mandatory fields — **dossier** (she picks the USB
   folder; subfolders traverse to any depth), **affaire** (the matter), **périmètre** (the
   scope selector shows only scopes she holds or may grant). One mandatory **custodian**
   field (she types the client's name; if she genuinely doesn't know, she marks
   *custodian-undeclared* — never blank). One **optional** field — the **case theory** — which
   she can skip, and skipping blocks nothing. There is no second mandatory screen.
3. She submits. She is **returned to Home immediately**; a **collapsed progress indicator**
   docks in the app bar — *"Import — 0 / … en cours d'inventaire"*. Nothing is blocked. She
   goes back to drafting. The denominator on Home is live and **provisional** while
   containers expand.
4. Hours later — a worker was killed and resumed at hour six, invisibly to her — the
   indicator reads *"Import terminé — 4 812 pièces"* and a **worklist line** appears.
5. **Completion summary.** She opens it after dinner. **★ Climax beat:** the *first* thing
   she sees is the **denominator** — `4 812 = 4 590 dans le corpus + 180 à revoir + 42
   exclus` with a green *"inventaire cohérent"* seal — and the *second* is the **list of
   tasks this job created**, each a sentence she can act on ("Fournir le mot de passe de 6
   pièces", "1 archive non ouverte — contenu inconnu"). **Not** a wall of technical events.
   She sees *what needs her*, and she sees that nothing vanished in silence. The summary is
   still there tomorrow, from the matter and the audit record.

### Flow 2 — Opening APX in the morning (the home worklist)

*Story 2.11.*

1. Claire opens APX. The **top zone is the worklist** — actionable lines only, each an action
   in her language. Below it, her **matters**, each with its scoped denominator and a
   *dernière activité* stamp.
2. Her firm has three hundred matters. **★ Climax beat:** the worklist is **not** pushed off
   the screen — the matters zone is bounded and ordered by last activity, the rest one click
   away, and the worklist always sits on top. The queue of *what needs her* is never buried
   by the *list of what exists*.
3. She clicks a line — *"6 pièces protégées — fournir le mot de passe"* — and lands exactly on
   those six in the register.

### Flow 3 — The decisive document that would not open

*Stories 2.6, 2.3.*

1. From that worklist line, Claire is in the **failure register**, filtered to the six
   protected pieces. Each row: filename, its mono path, a `password-protected` chip, the
   matter, the custodian, a timestamp — and a **"fournir le mot de passe"** action (never an
   "exclude" as the only exit).
2. She supplies the password; ingestion re-runs for that piece only; the row moves to
   **resolved** (faded, history kept). The denominator's "à revoir" term ticks down by one.
3. One file is genuinely corrupt. It stays in the register as `corrupt-file`, **on a list she
   can act on** — **★ Climax beat:** the one document that would not open is *enumerated and
   attributed*, not silently gone. If she later needs to tell a court what was and was not
   reviewed, it is a line with a name, not a hole.

### Flow 4 — The wall holds (RBAC)

*FR-1 / FR-49.*

1. At onboarding, Claire's scope selector will not let her file the matter under a group she
   does not hold, nor narrow it out of Sophie's sight. **★ Climax beat:** she *cannot* make
   material invisible to her supervisor, and she *cannot* reach into a wall that is not hers —
   the UI offers neither option, and the server asserts it in both directions.
2. A handful of pieces arrived with no determinable matter. Claire never sees them; only the
   tenant-wide administrative grant holder does.

---

## Inspiration & Anti-patterns

**Salvage (patterns already validated — reuse, don't reinvent).**
- **The provenance/audit drawer** — provenance one click from anywhere. The single
  highest-value legacy pattern; central to the trust story.
- **The inventory equation** — already built (`InventoryView`), promoted to the permanent
  denominator. Keep it verbatim in spirit.
- **Honest "hors corpus" / honest unknowns** — the product says what it cannot claim. Extend
  the same honesty to unknown cardinality and provisional counts.
- **Lawyer-language microcopy** — Max's rewritten sentences and the POC's existing copy
  ("indexées — dans le corpus", "non traitées — à revoir") are the register to match.

**Anti-patterns (named legacy failures — do not repeat).**
- **Engineer-facing screens** — "Chunks" as a column, `/documents` as a dev tool (§6.2).
- **Destructive controls** — a raw `confirm("Supprimer ?")` with no undo, no audit (§6, the
  triage-never-destroys violation). Nothing in APX deletes; state changes.
- **Raw error strings** — `e.message` as red text (§6.6). Classify, or don't surface.
- **Mouse-only flagship interactions** — citations reachable only by hover (§6.9).
- **Inconsistent shell** — five max-widths, five radii, three colour systems (§3c, §6.8,
  §6.11). One shell width, three radii, one palette — enforced by DESIGN.md.
- **French-as-key i18n** — silent breakage on copy edits (§7).
