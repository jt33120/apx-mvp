---
name: APX
description: The visual identity of a law-firm instrument for mass-document triage — navy ink, one restrained gold, warm paper. Ratified from apx/web/src/tokens.css (AD-29); this is the source of truth for how APX looks, product-wide. Extended 2026-07-30 with the Epic-3 truth-status vocabulary (Story 3.4) and the pièce-viewer vocabulary (Story 3.5); extended 2026-08-05 with the Epic-4 triage-surface vocabulary (Stories 4.6–4.11); extended 2026-08-13 with the Epic-5 audit-drawer and export vocabulary (Story 5.7) and the validation-act vocabulary (Story 5.8).
status: final
updated: 2026-08-13
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
  triage-table:
    note: 'Epic 4 (Story 4.10). The ranked working set as a table — one row per pièce in rank order, columns rang / pièce / confiance / étiquette / côté. The corpus is COMPLETE (its denominator sits above as {components.equation}); the ORDER is a judgement, not a proof. A cell edit changes that cell and nothing else — rows NEVER reorder on an edit. THE LINE is drawn BETWEEN two rows, never on one.'
    border: '1px solid {colors.line}'
    radius: '{rounded.DEFAULT}'
    row-divider: '1px solid {colors.line-2}'
    header-eyebrow: '{typography.eyebrow}'
  rank-cell:
    note: 'Epic 4. The rank ordinal — serif, tabular-nums, right-aligned (the count is the hero). Rank is the pièce''s position in ONE ranked order; it is never changed by a label edit or a pin.'
    numeral: '{typography.numeral-row}'
  confidence-cell:
    note: 'Epic 4 (Story 4.4/4.6). The DERIVED confidence read — a band word (élevée / moyenne / faible) with a small derived-meter and a DERIVED marker, so it can never read as an editable self-report. NOT a dropdown, NOT a text field: confidence is computed from observables, never typed. Expands to the {components.justification}. Deliberately shaped UNLIKE the editable {components.label-cell} — the affordance difference IS the FR-42 honesty.'
    band-high: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    band-mid: { color: '{colors.review}', background: '{colors.review-bg}' }
    band-low: { color: '{colors.ink-3}', background: '{colors.line-2}' }
    derived-marker: { color: '{colors.ink-3}', note: 'a small uppercase "dérivée" eyebrow — the derived-not-declared rule made visible' }
  label-cell:
    note: 'Epic 4 (Story 4.5). The taxonomy label as an EDITABLE cell — a select drawn from the tenant taxonomy or the explicit `unlabelled`, never null/blank/default. Editing appends to the append-only ledger and writes a {components.change-log-entry}; it NEVER reorders the row or moves the pièce across the line. Reads as editable (a select affordance) — the deliberate visual opposite of the read-only {components.confidence-cell}.'
    radius: '{rounded.sm}'
    border: '1px solid {colors.line}'
    unlabelled: { color: '{colors.ink-3}', background: '{colors.surface-2}', note: 'the explicit `unlabelled` — stated, never an empty cell' }
  side-badge:
    note: 'Epic 4 (Story 4.7). The retenue / écartée side as a DERIVED VIEW — a chip in the kept/discard tier, NEVER a checkbox that stores membership. It is a read of (the line, the pins) over one ranked order. The pinned variant carries the {components.pin-marker} — this side is a human override of the line, not the line''s own placement.'
    radius: '{rounded.full}'
    retained: { label: 'Retenue', color: '{colors.kept}', background: '{colors.kept-bg}' }
    discarded: { label: 'Écartée', color: '{colors.discard}', background: '{colors.discard-bg}' }
    unscored: { label: 'Non scorée', color: '{colors.ink-3}', background: '{colors.line-2}' }
  the-line:
    note: 'Epic 4 (Story 4.8) — THE north-star. An ordinal cut drawn BETWEEN two rows (retained above, discarded below), full-bleed across the table. It STATES the commitment in words ("À mon sens, tout ce qui précède") with its stated basis (the case-theory version, or the named intrinsic signals), and is LABELLED BY THE LAST RETAINED PIÈCE identity — never a bare integer, never merely a divider. Carries the ranking version it cuts. A single gold hairline (the sanctioned structural flourish) marks it.'
    rule: '2px solid {colors.gold}'
    label: '{typography.body}'
    basis-eyebrow: '{typography.eyebrow}'
  line-price:
    note: 'Epic 4 (Story 4.9). The PRICED move — considering a candidate line position states Δ pièces-to-read and Δ estimated prevalence of relevant material in the resulting discarded set. DELIBERATELY a DIFFERENT visual register from the sampling bound / verdict seal: an ink-toned PROJECTION panel with a dashed edge, explicitly labelled "projection du classement — rien n''a été échantillonné", so a model estimate is NEVER mistaken for a proven bound (FR-19). Never states a "risque d''avoir manqué".'
    radius: '{rounded.DEFAULT}'
    border: '1px dashed {colors.line}'
    ink: '{colors.ink-2}'
    projection-eyebrow: { color: '{colors.ink-3}', note: 'PROJECTION — not a bound; the safeguard is the label' }
  pin-marker:
    note: 'Epic 4 (Story 4.11). The épingle — a single pièce forced across the line, overriding it for that ONE pièce (the line does not move, the order does not change, no other membership changes). Carries the side it forces and expands to its MANDATORY one-line reason (recorded as an override, FR-25). Reversible; a removal is itself a recorded act. A small gold pin glyph on the {components.side-badge}.'
    color: '{colors.gold}'
    glyph: 'an inline gold épingle glyph'
  change-log-entry:
    note: 'Epic 4 (Story 4.10/4.5). An append-only per-row diff shown BESIDE the row and in the matter change-log: previous value → new value, author, timestamp. It never mutates or deletes a prior entry; a reversal is a NEW entry, not an erasure. Human-set values it records survive re-ranking marked as such.'
    divider: '1px solid {colors.line-2}'
    arrow: 'previous → new, in {colors.ink-3}'
    author: '{typography.hint}'
  justification:
    note: 'Epic 4 (Story 4.6). The one-line justification DERIVED FROM NAMED EVIDENCE — the named retained extracts (each by chunk id, resolvable to a source position), not a free-text opinion. Every extract passes exact-containment verification AT SHOW TIME; a justification whose extracts do not resolve is shown as UNVERIFIED (review-toned), never as ordinary. Expands into the audit drawer showing the extracts; reversible in one recorded act. States the source language where it differs from the interface.'
    verified: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    unverified: { color: '{colors.review}', background: '{colors.review-bg}' }
    extract-id: '{typography.mono}'
  audit-drawer:
    note: 'Epic 5 (Story 5.7). The trust surface the sceptic lives in — a right-hand panel over the triage table or the viewer, never a route of its own (the lawyer must not lose her place in the order to ask why). Four bands in a fixed order, and the order IS the argument: the decision, what it rests on, what will be written, what you can do. Salvaged in shape and vocabulary from the v1 mockup; its confidence bar and its "reasoning as audit trail" are deliberately NOT salvaged.'
    width: '30rem'
    background: '{colors.surface}'
    border-left: '1px solid {colors.line}'
    shadow: '{elevation.shadow}'
    band-divider: '1px solid {colors.line-2}'
    band-eyebrow: '{typography.eyebrow}'
  extract-quote:
    note: 'Epic 5 (Story 5.7). One retained extract as the drawer and the FULL export show it: the passage quoted in the serif reading face, under it the chunk identity and the exact source position in mono. Its show-time containment verdict is carried on the quote itself — a VERIFIED quote sits on paper; an UNRESOLVED one is review-toned, names its enumerated cause in the lawyer''s language, and shows NO quoted text, because the text it would show is precisely what could not be confirmed.'
    quote: { fontFamily: '{typography.serif.fontFamily}', color: '{colors.ink-2}' }
    rule: '2px solid {colors.line}'
    provenance: '{typography.mono}'
    verified-rule: '2px solid {colors.kept}'
    unresolved: { color: '{colors.review}', background: '{colors.review-bg}', rule: '2px dashed {colors.review}' }
  proposed-entry:
    note: 'Epic 5 (Story 5.7). The audit-record entry a reversible action WILL append, shown before it exists — rendered as the ROW it will become (act, actor, wall-clock, chain, and for an override its FR-25 ground and the verbatim reason it will carry), never as prose. It is styled like the entries in the journal, one shade quieter, with a "sera inscrit" eyebrow: the lawyer should recognise the thing she is about to create.'
    background: '{colors.surface-2}'
    border: '1px dashed {colors.line}'
    radius: '{rounded.sm}'
    field-label: '{typography.eyebrow}'
    value: '{typography.hint}'
  override-badge:
    note: 'Epic 5 (Stories 5.6/5.7). An entry that records an OVERRIDE — a decision taken against the tool or around a guard, which FR-25 makes countable apart from an ordinary edit. Review tier, deliberately: it is neither an error (danger) nor routine (muted). Carries its FR-25 ground on hover/inline and its verbatim reason where the tier permits it.'
    radius: '{rounded.full}'
    color: '{colors.review}'
    background: '{colors.review-bg}'
    eyebrow: '{typography.eyebrow}'
  export-tier-fork:
    note: 'Epic 5 (Story 5.7). The tier choice, as a FORK reached BEFORE anything is produced — two cards side by side, never a switch on a download button. NUMBERS-ONLY is the default and is described by what it CANNOT carry; FULL is described by what it WILL carry, itemised, and takes a second deliberate confirmation. This is the one act in the product that moves client content out of the firm on purpose, and the gesture must feel like it.'
    card: '{components.card}'
    default-card: { border: '1px solid {colors.ink}', note: 'the default carries the weight, not the accent' }
    full-card: { border: '1px solid {colors.review}', background: '{colors.review-bg}' }
    itemised: '{typography.hint}'
  export-cover:
    note: 'Epic 5 (Story 5.7). The exported document''s first page — a cover that declares the document''s own limits before any content: matter, RBAC scope, tier, author, timestamp; the continuity verdict PER CHAIN naming which chain a holder of this document alone can recompute; the AD-35 truncation banner when one is unacknowledged; and the degraded state with its count. A reader who stops at page one already knows what this document can and cannot prove.'
    background: '{colors.surface}'
    border: '1px solid {colors.line}'
    title: '{typography.h1}'
    field-label: '{typography.eyebrow}'
  degraded-banner:
    note: 'Epic 5 (Stories 5.7/FR-11). DÉGRADÉ as a state OF THE DOCUMENT, said on the cover with its count ("3 extraits ne se résolvent plus"), never as a footnote and never only as a per-row asterisk. Review tier — the document is honest, not broken. Self-containment is checked at READ time, so a document produced clean can be shown degraded later and must be able to say so.'
    color: '{colors.review}'
    background: '{colors.review-bg}'
    border: '1px solid {colors.review}'
    radius: '{rounded.sm}'
  validation-act:
    note: 'Epic 5 (Story 5.8, FR-45). The validation control on all three surfaces — table row, viewer, drawer band 4. Its own text IS the full assertion, « J''ai lu cette pièce et j''accepte l''appréciation de l''outil », followed by the ranking version it accepts (AD-23). NEVER a button labelled « Valider » with the sentence relegated to a tooltip or a follow-up dialog: the record will say a lawyer asserted this, and a control she can press without reading it writes a claim she never made in the words that were recorded. The accessible name is the whole sentence.'
    sentence: '{typography.body}'
    version-ref: '{typography.hint}'
    border: '1px solid {colors.ink}'
    radius: '{rounded.sm}'
  validation-provenance:
    note: 'Epic 5 (Story 5.8, FR-45/FR-44). The consequence line directly beneath the act, stating BEFORE the click what the entry will say: « Vous avez ouvert cette pièce le 13 août à 14 h 32 — inscrite comme lue » (kept) or « …sera inscrite comme acceptée depuis la liste, non comme lue » (review). Second person and a DATE, never « la pièce a été ouverte » and never a bare tick — the fact recorded is about the acting lawyer, and another lawyer''s open is not her reading. Neither state blocks the act; the friction is one sentence naming the consequence, which costs nothing to the lawyer who actually read the document. Rendered as aria-describedby on the control, never as a separate region.'
    read: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    from-list: { color: '{colors.review}', background: '{colors.review-bg}' }
    text: '{typography.hint}'
    radius: '{rounded.sm}'
  bulk-validation-confirm:
    note: 'Epic 5 (Story 5.8, FR-45). The modal confirming a bulk validation. States the COUNT AND THE SPLIT — « Vous en avez ouvert 12. Les 168 autres seront inscrites comme acceptées depuis la liste » — plus the per-pièce entry, the batch size and its identifier. A confirmation naming only the total is friction without information: it obtains consent while telling her nothing she did not know. The confirming verb NAMES THE COUNT (« Valider les 180 pièces »), never « Confirmer » or « OK », and is NOT the initially-focused element — the keyboard''s default gesture must not be to accept 180 documents.'
    surface: '{colors.surface}'
    border: '1px solid {colors.review}'
    radius: '{rounded.DEFAULT}'
    count: '{typography.numeral-row}'
    verb: '{components.button-primary}'
  validation-badge:
    note: 'Epic 5 (Story 5.8, FR-45). The state afterwards, carrying FOUR facts and never one tick: who, when, lue / depuis la liste, and the ranking version accepted. Dropping the third would launder acceptances into readings at the last surface before the court; dropping the fourth would keep a green check over values a re-rank replaced. Bulk stays visible after the fact (« depuis la liste · lot de 180 »). A never-validated pièce carries NO badge — never « non validée ». Stale (the version moved) and from-the-list both render review, read renders kept, withdrawn renders neutral with both dates.'
    read: { color: '{colors.kept}', background: '{colors.kept-bg}' }
    from-list: { color: '{colors.review}', background: '{colors.review-bg}' }
    withdrawn: { color: '{colors.ink-3}', background: '{colors.surface-2}' }
    text: '{typography.hint}'
    radius: '{rounded.full}'
  pending-section:
    note: 'Epic 5 (Story 5.7). A section of the export whose ACT does not exist yet — the validation acts and the accepted-as-is half of the breakdown, both Story 5.8''s. It prints its heading and one explicit sentence naming the act as not yet implemented. NEVER an empty table and NEVER a zero: a zero reads as "nobody validated anything", which is a finding about the firm rather than about the build. The project''s standing rule — asserted with something behind it, or pending with the story that owns it, never faked in between — rendered.'
    color: '{colors.ink-3}'
    background: '{colors.surface-2}'
    border: '1px dashed {colors.line}'
    eyebrow: '{typography.eyebrow}'
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

### Epic-4 additions — the triage-surface vocabulary (Stories 4.6–4.11)

Epic 4 is the product's **north-star surface**: a ranked working set the lawyer keeps control
of. Its whole visual argument is that **judgement and record are two acts** — the tool *proposes*
an order and *commits* to a line; the lawyer *corrects* without the tool undoing her, and every
correction is *recorded, reversible, never destructive*. The vocabulary encodes three honesties
the substrate already enforces (Stories 4.3–4.7): the corpus is **complete**, the order is a
**judgement not a proof**, and retained/discarded are **derived views, never stored memberships**.

**Triage table** — `{components.triage-table}`. One row per pièce in rank order. Above it sits the
permanent-denominator **equation** (`{components.equation}`) — but now the terms are
*retenue + écartée + non-scorée = le corpus*, and its **verdict** seal
(`{components.verdict}`) states *nothing left the corpus*: the same accounting shape as Epic-2,
proving the triage sets **partition** the whole matter and delete nothing. A cell edit changes one
cell; rows never reorder on an edit.

**Rank cell** — `{components.rank-cell}`. The ordinal in serif `tabular-nums`, right-aligned. Rank
is a pièce's place in **one** ranked order; a label edit or a pin never changes it.

**Confidence cell** — `{components.confidence-cell}`. A **read-only derived** band (élevée /
moyenne / faible) carrying a small `dérivée` marker. It is deliberately shaped **unlike** an
editable cell: confidence is *computed from observables, never typed* (FR-42), and the affordance
must say so at a glance. It expands to the **justification**.

**Label cell** — `{components.label-cell}`. The taxonomy label as an **editable** select — the
tenant taxonomy or the explicit `unlabelled`, never a blank. It reads as editable precisely where
the confidence cell reads as derived: the two cells are the visual statement that *classifying and
scoring are different acts*. Editing appends to the ledger and writes a change-log entry; it never
moves the row or crosses the line.

**Side badge** — `{components.side-badge}`. *Retenue / Écartée / Non-scorée* as a **derived view**
chip in the kept/discard tier — **never a checkbox**. It is a read of *(the line, the pins)* over
the order; making it look storable would be a lie about how triage works. Its pinned variant
carries the pin marker.

**The line** — `{components.the-line}`. The north-star. An ordinal cut drawn **between two rows**,
full-bleed, retained above and discarded below. It **speaks** — *"À mon sens, tout ce qui
précède"* with its stated basis — and is **named by the last retained pièce**, never a bare
integer. A single gold hairline (the sanctioned structural flourish) marks the cut; the kept→discard
tier shift carries the meaning. The **unscored** pièces are their **own zone** below the discarded
set — never folded into it (a pièce the cascade could not score is not silently discarded).

**Line price** — `{components.line-price}`. Moving the line is **priced before it commits**: Δ
pièces to read, Δ estimated prevalence of relevant material in the resulting discarded set. It is a
**projection**, and its visual register is deliberately **not** the verdict/absence seal — an
ink-toned, dashed-edge panel labelled *projection du classement — rien n'a été échantillonné*, so
a model estimate is never mistaken for a sampling bound (FR-19). It never says *risque d'avoir
manqué*.

**Pin marker** — `{components.pin-marker}`. The épingle. One pièce forced across the line, the line
unmoved and the order unchanged, with a **mandatory one-line reason** recorded as an override
(FR-25). Reversible; the removal is itself recorded.

**Change-log entry** — `{components.change-log-entry}`. An append-only *previous → new · author ·
time* line beside the row and in the matter log. A reversal is a **new** entry, never an erasure —
the log only grows. This is the surface the *"the document is the source of truth, the AI only
proposes"* principle lives on.

**Justification** — `{components.justification}`. One line, **derived from named evidence** — the
retained extracts by chunk id, each verified by exact containment *at show time*. An extract that
no longer resolves makes the justification **unverified** (review-toned), never ordinary. It
expands into the audit drawer and is reversible in one recorded act.

### Epic-5 additions — the audit drawer and its export (Story 5.7)

Seven components, and every one of them exists to keep a promise the product would otherwise be
making with prose. The drawer is where a sceptic asks *why*, and the export is where the answer
leaves the building and has to stand up without the system behind it.

| Component | What it is, and the rule it keeps |
|---|---|
| `audit-drawer` | The panel itself — four bands in a fixed order: **la décision · ce sur quoi elle repose · ce qui sera inscrit · ce que vous pouvez faire**. A panel, never a route: asking *why* must not cost the lawyer her place in the ranked order. |
| `extract-quote` | One retained extract, with its chunk identity and exact source position, carrying its **show-time** containment verdict. An unresolved extract shows **no quoted text** — the text is exactly what could not be confirmed — and names its cause instead. |
| `proposed-entry` | The audit entry an action **will** append, rendered as the row it will become. Never prose. The lawyer should recognise the thing she is about to create. |
| `override-badge` | An entry that records a **dérogation** (FR-25). Review tier: neither an error nor routine. |
| `export-tier-fork` | The tier choice as a **fork before production**, not a switch on a download button. Numbers-only is the default and is described by what it cannot carry. |
| `export-cover` | The document's first page, declaring the document's own limits before any content. |
| `degraded-banner` | **Dégradé** as a state of the document, on the cover, with its count. |
| `pending-section` | A section whose *act* does not exist yet: heading + one sentence naming the story that owns it. Never an empty table, never a zero. |

**Why the v1 confidence bar did not survive.** `maquette_anfr_v2.html` drew confidence as a bar
with a number beside it. Story 4.4 made confidence **derived from named observables**, and a bare
bar is indistinguishable from a self-reported score — the exact reading FR-42 exists to prevent.
The drawer reuses `{components.confidence-cell}`'s band + *dérivée* marker and names the derivation
and the ranking version underneath it.

**Why "trace d'audit proposée" changed meaning.** In v1 that label sat above the model's reasoning
in bullets. In FR-26 it is the **proposed audit-record entry**. Rendering reasoning under that
label teaches a lawyer that the audit record is prose a machine wrote, which is the opposite of
what it is and would poison the one artefact a *bâtonnier* is meant to be able to check.

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
- (Epic 4) Don't render *retenue / écartée* as a checkbox or a stored toggle — it is a **derived
  view** of the line and the pins. A storable-looking control would lie about how triage works.
- (Epic 4) Don't make the confidence cell look editable, or the label cell look derived — the
  affordance difference is the honesty that scoring and classifying are different acts.
- (Epic 4) Don't give the priced move the verdict/absence-seal shape. A **projection** is not a
  **bound**; keep them in different visual registers so a lawyer never confuses the two (FR-19).
- (Epic 4) Don't draw the line *on* a row or as a bare integer position. It is a cut **between**
  two rows, named by the last retained pièce, and it speaks its commitment in words.
- (Epic 5) Don't render the proposed audit entry as prose, a summary or a reasoning list. It is
  the **row that will be appended**; showing anything else teaches the lawyer to mistrust the one
  artefact a *bâtonnier* can check.
- (Epic 5) Don't show a quoted passage for an extract that failed containment at show time. The
  quote is precisely what could not be confirmed; show the cause instead (FR-11).
- (Epic 5) Don't put the export tier on a toggle beside a download button. It is a **fork** taken
  before anything is produced, because the full tier moves client content out of the firm.
- (Epic 5) Don't print a **0** for a section whose act does not exist yet. Zero is a finding about
  the firm; "not built yet" is a finding about the build, and they must never be confused.
- (Epic 5) Don't state one continuity verdict over a document spanning two chains. Say which chain
  a holder of **this document alone** can recompute (AD-43); one boolean would claim a property of
  bytes the reader does not hold.
- (Epic 5) Don't label the validation control « Valider » or « Marquer comme lu ». Its text **is**
  the assertion the record will attribute to her, in full. A verb she can press without reading it
  writes a claim she never made in the words that were recorded (FR-45).
- (Epic 5) Don't let a selection checkbox validate, and don't add a « lu » checkbox column. A
  checkbox is state; a validation act is an assertion by a person, and a column of them is one
  select-all away from the failure the whole trust architecture exists to prevent.
- (Epic 5) Don't render a validation badge as a bare ✓. Without **lue / depuis la liste** it
  launders acceptances into readings at the last surface before the court; without the ranking
  version it keeps a green check over values a re-rank has replaced (FR-45, AD-23).
- (Epic 5) Don't confirm a bulk validation with the total alone. The **split** — how many she
  opened, how many she did not — is the information; a count-only dialog is friction that obtains
  consent while telling her nothing.
- (Epic 5) Don't let time, scrolling, dwell or presence produce acceptance, in any wording
  (« lu automatiquement », « consulté », « vu »). FR-45 forbids it by name, and it is the single
  most tempting affordance in the Epic-5 surface.
