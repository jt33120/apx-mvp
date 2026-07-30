---
name: APX
description: The visual identity of a law-firm instrument for mass-document triage — navy ink, one restrained gold, warm paper. Ratified from apx/web/src/tokens.css (AD-29); this is the source of truth for how APX looks, product-wide. Extended 2026-07-30 with the Epic-3 truth-status vocabulary (Story 3.4) and the pièce-viewer vocabulary (Story 3.5).
status: final
updated: 2026-07-30
sources:
  - apx/web/src/tokens.css            # the implemented design system — this file formalises it
  - docs/context/03-design-and-ux-inventory.md  # salvage verdicts; the three legacy systems reconciled here
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/  # AD-29 (one design system)

colors:
  # ink — the firm's writing colour, a deep navy. Text, headings, primary action.
  ink: '#0b1f3a'
  ink-2: '#33425a'
  ink-3: '#5b6678'
  # ground — warm paper and the surfaces that sit on it
  paper: '#f7f4ee'
  surface: '#ffffff'
  surface-2: '#fbf9f5'
  # structure — warm hairlines, biased toward the gold, never a cold grey
  line: '#e6e0d5'
  line-2: '#efeae0'
  # accent — the one gold. Used sparingly: focus, the X, a single hairline flourish.
  gold: '#9a7a34'
  gold-2: '#b8944a'
  muted: '#6b7280'
  # semantic — the triage verdict tier, kept deliberately DISTINCT from the accent
  kept: '#2f6f4f'
  kept-bg: '#e8f1eb'
  review: '#9a5a12'
  review-bg: '#f6ecdd'
  discard: '#6f6858'
  discard-bg: '#eeece5'
  danger: '#a3161c'
  danger-bg: '#fbeceb'

typography:
  serif:
    fontFamily: '"Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif'
    note: 'Wordmark, headings, and the big countable numerals. The instrument speaks in a book face.'
  sans:
    fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
    note: 'The whole interface. System sans — nothing to download, nothing that leaks a request offline.'
  mono:
    fontFamily: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace'
    note: 'Identifiers only — provenance paths, piece ids, hashes. Never body copy.'
  h1: { fontFamily: '{typography.serif.fontFamily}', fontSize: '1.5rem', fontWeight: '600', letterSpacing: '0.01em' }
  h2: { fontFamily: '{typography.serif.fontFamily}', fontSize: '1.2rem', fontWeight: '600' }
  h3: { fontFamily: '{typography.serif.fontFamily}', fontSize: '1rem', fontWeight: '600' }
  body: { fontFamily: '{typography.sans.fontFamily}', fontSize: '1rem', lineHeight: '1.55' }
  eyebrow: { fontFamily: '{typography.sans.fontFamily}', fontSize: '0.72rem', fontWeight: '600', letterSpacing: '0.08em', note: 'UPPERCASE. Field labels, section kickers. ink-3.' }
  hint: { fontFamily: '{typography.sans.fontFamily}', fontSize: '0.88rem', note: 'Secondary/meta text. muted.' }
  numeral-hero: { fontFamily: '{typography.serif.fontFamily}', fontSize: '3rem', lineHeight: '1', note: 'The denominator total. font-variant-numeric: tabular-nums.' }
  numeral-row: { fontFamily: '{typography.serif.fontFamily}', fontSize: '1.4rem', note: 'A denominator term. tabular-nums, right-aligned.' }

rounded:
  sm: '8px'      # inputs, buttons, small chips-with-corners
  DEFAULT: '12px' # cards, lists, the equation panel
  full: '9999px'  # chips, pills, badges

spacing:
  '1': '0.5rem'
  '2': '1rem'
  '3': '1.5rem'
  gutter: '1.25rem'   # shell horizontal padding
  shell-max: '60rem'  # the ONE content max-width. There is exactly one.

elevation:
  ring: '0 0 0 3px rgba(154, 122, 52, 0.28)'                                   # gold focus ring
  shadow-sm: '0 1px 2px rgba(11, 31, 58, 0.06)'
  shadow: '0 1px 2px rgba(11, 31, 58, 0.05), 0 12px 30px rgba(11, 31, 58, 0.08)'

components:
  button-primary:
    background: '{colors.ink}'
    color: '#ffffff'
    border: '1px solid {colors.ink}'
    radius: '{rounded.sm}'
    padding: '0.55rem 1rem'
    hover-background: '#12294a'
    focus: '{elevation.ring}'
  button-ghost:
    background: 'transparent'
    color: '{colors.ink}'
    border: '1px solid {colors.line}'
    hover-background: '#efeadf'
  card:
    background: '{colors.surface}'
    border: '1px solid {colors.line}'
    radius: '{rounded.DEFAULT}'
    shadow: '{elevation.shadow}'
  chip:
    radius: '{rounded.full}'
    padding: '0.07rem 0.55rem'
    fontSize: '0.76rem'
    variants:
      kept: { color: '{colors.kept}', background: '{colors.kept-bg}' }
      review: { color: '{colors.review}', background: '{colors.review-bg}' }
      discard: { color: '{colors.discard}', background: '{colors.discard-bg}' }
      scope: { color: '{colors.ink-2}', background: '{colors.line-2}' }
  equation:
    note: 'The denominator. A total on the left, its terms stacked on the right, one gold hairline between. The hero of every result and the home screen.'
    total-numeral: '{typography.numeral-hero}'
    term-numeral: '{typography.numeral-row}'
    divider: '1px solid {colors.line}'
  verdict:
    note: 'The consistency seal under the equation. kept-toned when submitted = corpus + failures + exclusions holds; review-toned when it does not.'
    radius: '{rounded.full}'
    ok: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    bad: { color: '{colors.review}', background: '{colors.review-bg}' }
  worklist-line:
    note: 'A single actionable task on the home worklist. A verb-first sentence in the lawyer language, a count, a caret. Left border in the tone of its urgency (review/danger). NEVER a technical state.'
    padding: '0.7rem 0.95rem'
    accent-border: '3px solid {colors.review}'  # danger tone for hard blocks
    label: '{typography.body}'
    counter: '{typography.numeral-row}'
  matter-row:
    note: 'A navigation line in the matters zone. Matter name, its scoped denominator as a compact inline equation, status ticks (running / ranking-stale / sampling-open), last-touched. Expandable.'
    padding: '0.7rem 0.95rem'
    divider: '1px solid {colors.line-2}'
  progress-indicator:
    note: 'The non-blocking import indicator. A persistent, collapsed bar of processed-against-submitted. Never a modal. Gold-to-gold fill on a line-2 track.'
    track: '{colors.line-2}'
    fill: 'linear-gradient(90deg, {colors.gold}, {colors.gold-2})'
    height: '3px'
  register-row:
    note: 'A failure-register entry. Filename (mono path beneath), error-class chip (review tone), cardinality, a retry affordance. Resolved rows fade to muted and keep their history.'
    padding: '0.7rem 0.95rem'
    class-chip: '{components.chip.variants.review}'
  truth-status-badge:
    note: 'Epic 3 (Story 3.4). The DATA-DRIVEN declaration of a result set truth status — a DIFFERENT axis from the triage tier, never blurred with it, never gold. Two variants, distinguished by glyph + word + framing, not by borrowing a verdict colour.'
    radius: '{rounded.full}'
    fontSize: '{typography.eyebrow.fontSize}'
    letterSpacing: '0.08em'
    variants:
      suggestive: { glyph: '≈', label: 'SUGGESTIF', color: '{colors.ink-3}', background: '{colors.line-2}', note: 'Tone-NEUTRAL. Pairs with an OPEN frame — a dashed left rule — signalling an open, non-complete set.' }
      exhaustive: { glyph: '=', label: 'EXHAUSTIF', color: '{colors.kept}', background: '{colors.kept-bg}', note: 'Authoritative. Pairs with the honesty SEAL (reuses {components.verdict}); a SOLID frame signalling a closed, complete set.' }
  suggestive-result:
    note: 'Epic 3. A semantic (suggestive) result set: the truth-status-badge (suggestive) header, an OPEN frame (2px dashed {colors.line} left rule), a ranked list. Each row carries a piece name, matter chip, a snippet with the term marked, and the proximity-indicator. Header count reads "les N plus proches", never "N résultats".'
    frame: '2px dashed {colors.line}'
    header-badge: '{components.truth-status-badge.variants.suggestive}'
  exhaustive-result:
    note: 'Epic 3. A deterministic (exhaustive) result set: the truth-status-badge (exhaustive) header on a SOLID {colors.line} frame, the scoped {components.equation} denominator, the {components.absence-statement} honesty seal, then the COMPLETE match list. Register name-matches are shown SEPARATELY (AD-21), never inside the list.'
    frame: '1px solid {colors.line}'
    header-badge: '{components.truth-status-badge.variants.exhaustive}'
  absence-statement:
    note: 'Epic 3 (AD-42). The honest absence/presence claim — the products most dangerous output. A verdict-seal-shaped panel carrying the FOUR qualifications in words: the scoped denominator, the open failure-register count, the unknown-cardinality containers, and the OCR + below-quality shares of the searched set. kept-toned when the scope is fully indexed and stable; review-toned when qualified (register/unknowns non-trivial, or a moving population). NEVER a bare "introuvable".'
    ok: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    qualified: { color: '{colors.review}', background: '{colors.review-bg}' }
    radius: '{rounded.DEFAULT}'
  proximity-indicator:
    note: 'Epic 3. A RELATIVE proximity read for a suggestive row — a small four-pip meter in {colors.ink-3} on {colors.line-2}, plus rank. NEVER a false-precise percentage (voice rule: no false-precise single number where a range is the truth).'
    pip-on: '{colors.ink-3}'
    pip-off: '{colors.line-2}'
  piece-viewer:
    note: 'Epic 3 (Story 3.5). The pièce reading surface — a focused route, not a widget. A BAR (back · pièce name in serif · format-badge · scope chip · audit marker · original · close), a BODY (structure-rail + document-canvas), and a FOOT stating the tenant boundary. Chrome stays strictly in tokens; only the document-canvas leaves the shell.'
    bar-background: '{colors.surface-2}'
    border: '1px solid {colors.line}'
    radius: '{rounded.DEFAULT}'
    audit-marker: { color: '{colors.kept}', background: '{colors.kept-bg}', note: 'ouvert · consigné HH:MM — opening is an audited act (FR-45), and the bar shows it.' }
  document-canvas:
    note: 'Epic 3 (Story 3.5). The rendered document itself — THE ONE SURFACE THAT LEAVES THE 60rem shell, because a faithful render (PDF page, scan, spreadsheet grid) is a reading plane, not shell content. A warm {colors.paper}-darker ground under a white document sheet; documents anchor to the top. This is the viewer''s single assumed exception, deliberate and documented.'
    ground: '#efe9df'
    sheet-background: '{colors.surface}'
    sheet-shadow: '{elevation.shadow}'
  structure-rail:
    note: 'Epic 3 (Story 3.5). The per-format "what this document is made of" rail: PDF/scan page thumbnails, .msg thread turns + attachments (each attachment its OWN pièce), .xlsx sheet tabs, .docx outline. On {colors.surface-2}; collapses to a horizontal strip below 52rem.'
    background: '{colors.surface-2}'
    divider: '1px solid {colors.line}'
  passage-highlight:
    note: 'Epic 3 (Story 3.5). The passage the tool sent you to, per format (text span, OCR box on a scan, spreadsheet cell). A purposeful gold wash that is the DELIBERATE ECHO of the app ::selection (rgba(154,122,52,0.18)) — the instrument''s own pointer, not decoration. The one sanctioned recurring use of gold as fill, justified because it IS a selection. scroll-margin so opening lands on it.'
    background: 'rgba(154, 122, 52, 0.17)'
    ring: '0 0 0 1px rgba(154, 122, 52, 0.22)'
  format-badge:
    note: 'Epic 3 (Story 3.5). A neutral chip naming the pièce format (PDF · Courriel · Tableur · image). The OCR variant is review-toned — the truth axis extended to a single page: recognised text is DECLARED as recognised, never passed for the page (AD-42 honesty, applied to the viewer).'
    radius: '{rounded.full}'
    neutral: { color: '{colors.ink-3}', background: '{colors.line-2}' }
    ocr: { color: '{colors.review}', background: '{colors.review-bg}' }
  render-fallback:
    note: 'Epic 3 (Story 3.5). The centred honest message for an un-renderable format, an out-of-scope denial, or a pièce over the render bound. NEVER an empty pane (FR-44): it states the limit and OFFERS THE ORIGINAL. The out-of-scope variant discloses NOTHING (byte-identical to "does not exist"); the over-bound variant is review-toned.'
    radius: '{rounded.DEFAULT}'
    ink: '{colors.ink-2}'
    over-bound-tone: '{colors.review}'
---

# APX — Design System

> This file **ratifies** the design system already implemented in
> [`apx/web/src/tokens.css`](../../../../apx/web/src/tokens.css) (AD-29). It does not
> re-open the visual direction: navy + one gold + warm paper is settled, and it is the
> best-reconciled descendant of the three incompatible legacy colour systems catalogued in
> the [design inventory §3e](../../../../docs/context/03-design-and-ux-inventory.md). The
> tokens above are lifted verbatim from that CSS; this document gives them their rationale,
> their rules, and the component vocabulary the Epic-2 surfaces extend.
>
> **DESIGN.md owns *how it looks*.** Its peer [`EXPERIENCE.md`](./EXPERIENCE.md) owns *how
> it works* and references these tokens by name. Both spines win over any mock or import on
> conflict.

## Brand & Style

APX is a **law-firm instrument**, not a SaaS dashboard. It should read like a well-set
legal document that happens to compute: warm paper under navy ink, a serif for anything a
partner's eye lands on, a single restrained gold used the way a good binding uses gilt —
once, on purpose. The feeling to protect is **quiet authority under scrutiny**. This is a
tool a lawyer may one day have to defend before a court ("what was and was not reviewed"),
so the surface earns trust by being legible, countable, and honest — never by looking
clever.

Three postures follow from that:

- **Countable over decorative.** The most important object on screen is usually a number
  with its terms shown — the *denominator*. Numerals get the serif and real size. Charts,
  gradients, and ornament stay out of the way.
- **One accent, spent once.** Gold marks focus, the wordmark's `X`, and at most one hairline
  flourish per surface. Everything else is ink, paper, and warm hairlines. A second accent
  would cheapen the first.
- **The verdict tier is not the brand.** Kept / à-revoir / écartée are semantic greens,
  ambers and taupes deliberately *offset* from the gold, so "this is the accent" and "this
  is a triage state" never blur.

## Colors

**Ink `{colors.ink}` — `#0b1f3a`.** The firm's writing colour. Body text, headings, the
primary button, `::selection`. Its two lighter steps (`{colors.ink-2}`, `{colors.ink-3}`)
carry secondary text and labels without dropping to a lifeless grey.

**Paper `{colors.paper}` — `#f7f4ee`.** The page. Warm, not white, so white cards
(`{colors.surface}`) lift off it without a shadow having to do all the work. `surface-2`
is the faint warm tint for nested/expanded regions.

**Line `{colors.line}` — `#e6e0d5`.** Every border and divider. A *warm* hairline biased
toward the gold, never a cold `#e5e7eb`. `line-2` is the even softer inner divider inside
lists and cards.

**Gold `{colors.gold}` — `#9a7a34`** (and the lighter `gold-2` for gradient ends and
hover sheen). **The one accent.** Permitted uses: the focus ring, the `X` in the wordmark,
links, the 3px flourish at the top of the login/onboarding card, and the progress fill.
Not permitted: filling buttons, tinting large areas, or standing in for a semantic state.

**Semantic tier — kept / review / discard / danger.** Each is a text colour paired with a
soft background for chips and seals:

| Token | Hex | Carries |
|---|---|---|
| `{colors.kept}` | `#2f6f4f` | *pertinente / dans le corpus*, consistency holds, integrity verified |
| `{colors.review}` | `#9a5a12` | *à revoir / à juger*, a failure-register class, "provisional" |
| `{colors.discard}` | `#6f6858` | *écartée / bruit système*, a declared exclusion |
| `{colors.danger}` | `#a3161c` | a hard, loud failure — a job that failed closed, an altered journal |

Rule: **danger is loud and rare.** A missing password is `review`, not `danger`. A job
that wrote nothing because the scope was null is `danger`. The register almost never uses
danger; the loud-failure paths do.

## Typography

Two families, one for identifiers.

- **Serif `{typography.serif}`** — a book face (Iowan Old Style → Palatino → Georgia). It
  carries the wordmark, `h1`–`h3`, and — importantly — **the big countable numerals**. When
  the denominator says `4 812`, that number is set in the serif at `{typography.numeral-hero}`
  (3rem). This is the single most APX typographic move: *the count is treated like a
  headline.*
- **Sans `{typography.sans}`** — the system UI stack. The entire interface, all controls,
  all body copy. It is deliberately the platform's own sans: nothing is fetched, so nothing
  can leak a network request on an air-gapped install (an EXPERIENCE.md/architecture
  non-negotiable, honoured here in the type layer).
- **Mono `{typography.mono}`** — identifiers *only*: provenance paths, piece ids, hashes.
  Never a paragraph.

The recurring signature is the **eyebrow** (`{typography.eyebrow}`): 0.72rem, uppercase,
`letter-spacing: 0.08em`, `ink-3`. It labels every field and section kicker. Numerals that
sit in columns or equations always take `font-variant-numeric: tabular-nums` so they line
up.

## Layout & Spacing

- **One content max-width.** `{spacing.shell-max}` = 60rem, centred, `{spacing.gutter}`
  horizontal padding. The legacy app shipped *five* different max-widths across routes and
  never felt like one product (design inventory §6.8). APX has exactly one shell width;
  everything lives in it.
- **Spacing scale** is a small, human set: `{spacing.1}` / `{spacing.2}` / `{spacing.3}`
  (0.5 / 1 / 1.5rem). Lay groups out with `gap`, not per-element margins.
- **Vertical rhythm.** Sections separate by ~1.9rem (`.apx-panel`). Lists are bordered
  blocks with `line-2` inner dividers, not free-floating rows.
- **Responsive.** The equation collapses from side-by-side to stacked below 34rem
  (total on top, terms beneath, the divider turning horizontal). The app is desktop-first
  (a lawyer at a workstation ingesting a USB key) but must not break on a tablet.

## Elevation & Depth

Depth is mostly **borders, not shadow.** Cards carry a 1px `line` border and a barely-there
two-part shadow (`{elevation.shadow}`) that reads as "lifted a millimetre off the paper",
never as a floating Material card. The only assertive light is the **gold focus ring**
(`{elevation.ring}`) — a 3px 28%-opacity gold halo on `:focus-visible`. There is **no
gradient anywhere** except the top-of-card hairline flourish and the progress fill, both
gold→gold-2.

## Shapes

Three radii, and only three: `{rounded.sm}` (8px) for inputs, buttons and cornered chips;
`{rounded.DEFAULT}` (12px) for cards, lists and the equation panel; `{rounded.full}` for
pills, badges and status chips. The legacy app had *five* radii in play (design inventory
§3c) — APX does not. If a thing has corners, it is 8px or 12px; if it's a pill, it's round.

## Components

The POC already implements a coherent kit; these are its visual specs, plus the four
Epic-2 additions. Behavioural specs live in EXPERIENCE.md — this section is appearance only.

**Button** — primary is ink-filled white-text (`{components.button-primary}`); ghost is
bordered-transparent for secondary/back actions (`{components.button-ghost}`). Both 8px,
both take the gold ring on focus.

**Card** — `{components.card}`: white surface, `line` border, 12px, the soft lift shadow.
The login and onboarding cards add a 3px gold→gold-2 hairline across the top edge.

**Chip** — `{components.chip}`: a round pill at 0.76rem. Four variants map to the semantic
tier (kept / review / discard) plus a neutral `scope` chip in `line-2`. Chips carry state,
never actions.

**Equation (the denominator)** — `{components.equation}`. The hero. A hero total in serif
3rem on the left, its terms stacked on the right (each a serif 1.4rem numeral + a
plain-language label, colour-coded to the tier), a single `line` divider between. Directly
beneath it, the **verdict** seal (`{components.verdict}`) states the identity in words —
kept-toned when `submitted = corpus + failures + exclusions` holds, review-toned when it
does not. *This component is already built* (`InventoryView` / `.apx-equation`) and is
promoted here to the permanent home-screen denominator.

**Worklist line** (new, Story 2.11/2.10) — `{components.worklist-line}`. A verb-first task
in the lawyer's language, a count set in the row numeral, a caret to its referent, and a
left border in the urgency tone. It must never render a technical state string.

**Matter row** (new, Story 2.11) — `{components.matter-row}`. A navigation line: matter
name, a compact inline denominator, small ticks for *job running* / *ranking stale* /
*sampling open*, and a last-touched timestamp. Expands to the matter's detail. Visually
quieter than a worklist line — it is orientation, not a task.

**Progress indicator** (new, Story 2.2) — `{components.progress-indicator}`. A persistent,
collapsed 3px gold-fill bar of processed-against-submitted, docked (app-bar or a slim
pinned strip), dismissible to an even smaller pill. **Never a modal, never blocks a
screen.**

**Register row** (new, Story 2.6) — `{components.register-row}`. Filename with a mono path
beneath, a `review`-tone error-class chip, cardinality, and a retry affordance. Resolved
entries fade to muted and keep their history rather than disappearing.

### Epic-3 additions — the truth-status vocabulary (Story 3.4)

Epic 3 introduces a **second axis** the interface must never blur with the triage tier:
*truth status* — whether a result set **finds** (suggestive) or **proves** (exhaustive). It is
carried by the data (one construction site per engine) and rendered identically everywhere it
appears. It is expressed by **glyph + word + framing**, deliberately **not** by borrowing a
verdict colour, so "this is a suggestion / a proof" and "this is a kept / à-revoir piece" never
read as the same thing.

**Truth-status badge** — `{components.truth-status-badge}`. Two variants: **suggestive**
(`≈ SUGGESTIF`, tone-neutral `ink-3` on `line-2`) and **exhaustive** (`= EXHAUSTIF`, `kept`-toned).
Uppercase eyebrow scale, `full` radius. Never gold; never a triage colour on the suggestive side.

**Suggestive result set** — `{components.suggestive-result}`. An **open** frame — a 2px *dashed*
`line` left rule — is the whole point: a dashed edge reads as *not closed*, so the eye is told
before it reads a word that this set makes no completeness claim. Its header count says
*"les 20 plus proches"*, never *"20 résultats"*.

**Exhaustive result set** — `{components.exhaustive-result}`. A **solid** `line` frame (a closed
set), the scoped **equation** denominator, then the **absence-statement** seal, then the complete
match list. Register name-matches sit in their own block beneath, visibly separate (AD-21).

**Absence statement** — `{components.absence-statement}`. The honesty seal, shaped like the
**verdict** seal it descends from: `kept`-toned when the searched scope is fully indexed and
stable, `review`-toned when qualified. It always states the four qualifications in words — the
scoped denominator, the open register count, unknown-cardinality containers, and the OCR /
below-quality shares — because *the absence claim is the one output a lawyer may have to defend*.

**Proximity indicator** — `{components.proximity-indicator}`. A small four-pip relative meter in
`ink-3`, plus rank. It is deliberately **not** a percentage: "au plus proche" is an ordering, not
a measurement, and a false-precise `87 %` would be exactly the kind of invented number the voice
bars.

### Epic-3 additions — the pièce-viewer vocabulary (Story 3.5)

The viewer is where a lawyer **reads the actual document**. Its vocabulary is grounded in the
key-screens mock ([`mockups/epic-3-piece-viewer.html`](./mockups/epic-3-piece-viewer.html)); the
tokens above decide, the mock illustrates.

**Piece viewer** — `{components.piece-viewer}`. A focused reading surface: a `surface-2` **bar**
(back · pièce name in serif · format-badge · scope chip · the `kept`-toned *ouvert · consigné*
audit marker · original · close), a **body** (structure-rail + document-canvas), and a **foot**
stating the tenant boundary. Every control is in-token; the surface reads as the same instrument.

**Document canvas** — `{components.document-canvas}`. **The one surface that leaves the 60rem
shell** — the single, deliberate, documented exception in the whole system, because a faithful
render is a *reading plane*, not shell content. A warm `#efe9df` ground carries a white document
sheet with the standard lift shadow; documents anchor to the top.

**Structure rail** — `{components.structure-rail}`. The per-format "what this document is made
of": page thumbnails (PDF/scan), thread turns + attachments (`.msg` — each attachment its **own**
pièce), sheet tabs (`.xlsx`), an outline (`.docx`). On `surface-2`; collapses to a horizontal
strip below 52rem.

**Passage highlight** — `{components.passage-highlight}`. The passage the tool sent you to, per
format. A purposeful gold wash that is the **deliberate echo of the app `::selection`** — the
*instrument's own pointer*. This is the **one sanctioned recurring use of gold as a fill**,
justified precisely because it *is* a selection, not ornament. (It does not spend the "one
flourish per surface" budget — it is functional, like focus.)

**Format badge** — `{components.format-badge}`. A neutral chip naming the format; its **OCR
variant is `review`-toned**, extending the Epic-3 truth axis to a single page: recognised text is
**declared** as recognised (with a confidence note), never passed for the page itself — the same
honesty the absence statement carries (AD-42), applied to the viewer.

**Render fallback** — `{components.render-fallback}`. The centred honest message for an
un-renderable format, an out-of-scope denial, or a pièce over the render bound. It is **never an
empty pane** (FR-44): it states the limit and **offers the original**. The **out-of-scope**
variant discloses **nothing** — byte-identical to "does not exist"; the **over-bound** variant is
`review`-toned and offers the original or a page-by-page read.

## Do's and Don'ts

**Do**
- Set every countable number in the serif, with `tabular-nums`. The count is the hero.
- Keep gold to focus, the wordmark, links, one hairline flourish, and the progress fill.
- Use the semantic tier for verdicts and classes; keep it visually distinct from gold.
- Warm every neutral — paper not white, `line` not cold grey.
- Give `:focus-visible` the gold ring, always. The flagship interactions must be keyboard-reachable.

**Don't**
- Don't introduce a fourth colour system, a second accent, or a chart palette off-token
  (the legacy app carried three unreconciled colour systems — never again; design inventory §6.11).
- Don't fill buttons or large areas with gold.
- Don't add a radius outside {8px, 12px, full}, or a second content max-width.
- Don't surface engineer vocabulary on a lawyer's screen — no "chunks", no raw stack traces,
  no "· 1 not indexed". Unknown cardinality is stated in words.
- Don't use a gradient anywhere but the two sanctioned hairline/fill flourishes.
- Don't render a decision as destructive. Nothing in this system deletes; it changes state.
