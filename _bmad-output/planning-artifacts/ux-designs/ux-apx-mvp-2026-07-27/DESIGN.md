---
name: APX
description: The visual identity of a law-firm instrument for mass-document triage — navy ink, one restrained gold, warm paper. Ratified from apx/web/src/tokens.css (AD-29); this is the source of truth for how APX looks, product-wide.
status: final
updated: 2026-07-27
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
