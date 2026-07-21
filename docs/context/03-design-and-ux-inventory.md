# 03 — Design & UX Inventory

> **What this is.** A factual inventory of every design artefact that exists today for the
> APX product line (Documentation/triage, Syllogisme, Veille IA): 5 distinct standalone HTML
> mockups shown to clients, plus the shipped Next.js front-end. Values in §3 are extracted
> from the files, not invented. Every claim carries a file path. Anything I could not
> confirm is marked **unverified**.
>
> **Read it for**: WDS phases (trigger mapping → scenarios → UX design), front-end stories,
> and any "do we keep this pattern?" decision.
>
> **Source of truth.** The mockups are copied verbatim into
> `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-mvp/docs/context/00-sources/mockups/`.
> The shipped app lives at
> `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-platform/apps/apx-demo/web/`.
> Both are **read-only reference** for this rebuild.

---

## 1. Asset inventory

| Artifact | Path | What it shows | Audience / client it was made for | Fidelity |
|---|---|---|---|---|
| **`philippe.html`** (6 May) | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/maquettes/philippe.html` | 5-view "LexCore IA console": Dashboard, Ingestion & Indexation, Bibliothèque annotée (editable table), Recherche sourcée (chat), Génération. Audit drawer over every piece. `<title>APX Advisory — Philippe & Partners · LexCore IA</title>` | **Philippe & Partners, Luxembourg.** Named reviewer in the UI: `{ initials: 'MG', name: 'Me M. Gouden', role: 'Partner · fonds / corporate Luxembourg' }` (l.244) | Hi-fi clickable (React 18 + Babel standalone + Tailwind CDN, all inline, single file) |
| **`maquette_enfr.html`** (13 May) | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/maquettes/maquette_enfr.html` | "Console v2" — the philippe.html console **plus** a boot Splash screen, a live Pipeline view and the **Syllogisme** page. 7 workflow views. `PROJECT.firm = 'Philippe & Partners'` (l.204). Despite the filename, **there is no FR/EN switch in this file** — no `DICT`, no `LangContext` | **Philippe & Partners** | Hi-fi clickable, single file |
| **`maquette_anfr_v2.html`** (13 May) | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/maquettes/maquette_anfr_v2.html` | Same 7 views as `maquette_enfr.html`, **rebranded to `PROJECT.firm = 'Cabinet Lexis'`** (l.461) and **fully bilingual**: adds `LangContext`, `DICT` (~250 keys, l.177+), `LangToggle`. This is the most complete mockup in the set | **Generic / anonymised prospect demo** ("Cabinet Lexis" is a placeholder firm; the sidebar footer reads *"Données fictives · aucun corpus client n'est mobilisé."*) | Hi-fi clickable, single file — **the reference mockup** |
| **`maquette-syllogisme-veille-demo.html`** (13 May) | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/maquettes/maquette-syllogisme-veille-demo.html` | "Lexoria" — a 4-tab **narrative/pitch** page (Dashboard, Research & syllogism, Regulatory watch, Assisted drafting), FR/EN, vanilla JS `data-i18n` swap. No console chrome; it is a *story about* the product, not the product | Pitch / prospect-facing demo. Content is **Luxembourg corporate/funds** (SPA carve-outs, ICT outsourcing, AIFM), not French employment law | Hi-fi static (no interaction beyond tab + language switch) |
| **`2026-05-13_Lexoria.html`** | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Resources/2026-05-13_Lexoria.html` | An **earlier, different Lexoria** with a much larger CSS-variable palette (navy/ochre/paper, three semantic tiers hi/mid/lo). Fonts: Inter + Source Serif 4 (the later demo switched to Inter + Lora) | Same pitch audience | Hi-fi static, superseded |
| **`2026-05-06_philippe.html`** | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Resources/2026-05-06_philippe.html` | **Not a mockup.** 193 KB, empty `<title></title>`, every line wrapped in `<p class="p1"><span class="s1">…` — this is a rich-text **export of the JSX source code** of `philippe.html`, not a renderable page. Useful only as a code archive | — | n/a (source listing) |
| **Shipped Next.js front-end** | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-platform/apps/apx-demo/web/` | 10 routes, 8 components, real design tokens in `tailwind.config.ts`, real i18n in `src/lib/translations.ts`, real Word/PDF export in `src/lib/export.ts`. Falls back to a bundled demo corpus (`src/lib/demo-data.json`, ~1 900 lines) when no backend | Public/private demo — Cabinet **Marchand & Lefèvre**, French employment law, ~6 months of corpus | **Shipped** (deployed to Vercel per `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-platform/CLAUDE.md`) |
| **Client review `.docx`** | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Resources/2026-06-06_Maquette Syllogisme - Review.docx` | Written review of the Syllogisme mockup by **Max** (lawyer) and **Lucia**, plus a copy-pasteable technical spec for the drafting layer and the Veille feature list. See §5 | Internal APX ← client-side reviewers | Text feedback (1 245 extracted paragraphs) |
| **Deck (unread here)** | `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Resources/2026-04-23_apx_advisory_syllogisme_ai_.pdf` | Referenced by the review as "le deck" and "la Couche 2 du deck" | — | **unverified** — not opened for this inventory |

**Nothing design-related was found in the recap folder.** A case-insensitive grep for
`maquette|design|UI|UX|interface|couleur|logo` across
`/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Agents/recaps/` returns only
commercial/status lines (e.g. `2026-05-11-cron-brief.md:15: P&P Luxembourg — LexCore IA +
Veille — status: deck_sent`) and the recurring architecture note *"RAG strict, fragments
seulement transmis aux LLM"*. **No design feedback lives in the recaps.**

---

## 2. Screen & flow inventory

### 2a. The console mockups (`philippe.html`, `maquette_enfr.html`, `maquette_anfr_v2.html`)

Shared shell: fixed 260 px left sidebar (`Sidebar`, `maquette_anfr_v2.html` l.810) → firm
badge → **Workflow** group of nav buttons → a greyed-out **"Extensions roadmap"** group
(`Veille réglementaire CSSF`, `Due Diligence Accelerator`, `KYC / AML Onboarding`, each
tagged `M2+` and `cursor-not-allowed`) → footer with a pulsing dot and the disclaimer
*"Données fictives · aucun corpus client n'est mobilisé."*. Right of it, a `HeaderBar`
(l.917) with breadcrumb eyebrow, serif page title, `LangToggle`, a ⌘K search field, a
"Trace démo / données illustratives" chip, and the reviewer avatar.

| # | Screen | Purpose | Key UI elements | Product |
|---|---|---|---|---|
| 1 | **Splash** (`Splash`, l.736) | Cinematic boot; sells the compliance story before the app loads | 5 sequenced boot lines: *Initialisation du noyau RAG… / Chargement des embeddings BGE-M3… / Connexion au vault d'audit (PostgreSQL)… / Vérification résidence des données — UE ✓ / Console prête.* Then "Entrer dans la console". Tagline: **"La mémoire vivante du cabinet."** | Cross-cutting |
| 2 | **Tableau de bord** (`Dashboard`, l.1043) | Orientation + proof | Gradient forest hero band; 3 CTAs (Démarrer l'ingestion / Lancer un syllogisme / Poser une question); `Donut` chart "Volumétrie par practice"; `Sparkline`s; **"Conformité by design"** card (*Données EU · zero retention LLM*, badge "Vérifié"); "Dernières pièces indexées" list, click → audit drawer | Documentation |
| 3 | **Pipeline live** (`PipelineLive`, l.1181) | Make the black box legible | 7 named stages — Ingestion → OCR/Parsing → Chunking → Embeddings → **Triage LLM** → Syllogisme → Indexation; per-stage counters (Ingérés / OCRisés / Embeddings / Classés / Syllogismes / **Rebut**); "7 fichiers en cours"; "Latence moyenne : 2.4 s/doc"; **"Sécurité réseau — aucun appel sortant non documenté"** | Documentation |
| 4 | **Ingestion / Import** (`ImportPage`, l.1346) | Get documents in | Drop zone, "Simuler 4 dépôts", per-file 7-step progress, then `CorpusList` with status filter chips **Tout / Pertinent / À revoir / Rebut** | Documentation |
| 5 | **Bibliothèque annotée** (`TablePage`, l.1530) | **The triage work surface** | 8-column table: Cote · Date · Pièce · Intervenants · Sommaire · Thématique · Confiance · Audit. `EditableCell` on Cote and Sommaire; `<select>` on Thématique; `ConfidenceBar`; "Voir" → audit drawer. Theme filter chips with live counts, search, exports **Excel / Word**, primary CTA **"Verser au syllogisme"**. Footer: *"N lignes affichées · edits persistés en mémoire de session · audit trail conservé"*. Below: **"Historique des modifications (session)"** — a monospace before→after diff log | Documentation |
| 6 | **Recherche sourcée** (`ChatPage`, l.1665) | Cited Q&A over the corpus | 2/3 chat + 1/3 **source preview** split. Streaming token-by-token render; markdown-lite parser handles `**bold**`, `*italic*` and `[1]` citation tokens → clickable chips; per-message "Sources" footer listing `[n] · cote · name`; suggestion chips; a rose guardrail banner at the top of the thread. Right pane shows the cited piece with `<mark class="cite">` highlighted extracts and "Voir la trace d'audit complète" | Documentation + Syllogisme |
| 7 | **Syllogisme juridique** (`SyllogismePage`, l.1890) — labelled *"THE WOW PAGE"* in the source comment | Staged legal reasoning | 4-phase state machine (idle → majeure → mineure → conclusion, 1 300 ms / 1 400 ms timers). Three `SyllogismeStep` cards numbered **I / II / III** with Latin subtitles *Praemissa major · Praemissa minor · Conclusio*, skeleton loaders while "running", inline `[n] cote` source chips per premise. Final **synthesis card**: numbered action list + risk badge + `Exporter mémo` / **`Verser à l'audit`** / `Valider et envoyer`. Right rail: source pieces with `ConfidenceBar`, plus a **"Garanties"** box — *"Les fragments envoyés au LLM ne dépassent jamais 2 000 tokens. Les embeddings restent locaux. Le raisonnement est journalisé dans l'audit trail immuable."* | Syllogisme |
| 8 | **Génération guidée** (`GeneratePage`, l.2063) | Draft in the firm's voice | Template picker + author (lawyer) picker → generate → document preview | Syllogisme |
| 9 | **Audit drawer** (`AuditDrawer`, l.951) — overlay, reachable from 2/4/5/6/7 | Justify one classification | Right-side max-w-xl slide-over with backdrop blur. Sections: *Décision affichée* + `ConfidenceBar` + theme + status pill · Date · Type · Expéditeur→destinataire · Intervenants (chips) · **Extraits retenus** (serif italic blockquotes, rose left border) · **"Trace d'audit proposée"** (numbered reasoning steps) · Actions: **Valider / Reclasser / Signaler / Verser au syllogisme** | Documentation |

`philippe.html` (6 May) is the same minus screens **1, 3 and 7** — i.e. no Splash, no
Pipeline, **no Syllogisme page**. The Syllogisme screen is the 13 May addition.

### 2b. The Lexoria pitch pages

`maquette-syllogisme-veille-demo.html` — 4 tabs driven by `data-tab` / `data-i18n`
(l.780–792, translations at l.1313+):

| Tab | Purpose | Key elements | Product |
|---|---|---|---|
| **Dashboard / Overview** | Positioning | "Visible principles": *Source-linked research · Structured reasoning · Lawyer validation* ("no final output without review") | Cross-cutting |
| **Recherche et syllogisme** | One worked example | Question → *Synthèse* → **Règle / Faits / Conclusion** (note the ordering and the plain-language labels — **not** Majeure/Mineure) | Syllogisme |
| **Veille réglementaire** | Prioritised alerts | 3 alert cards with priority + cadence tags: *Priorité haute · Externalisation ICT — "À revoir aujourd'hui"*; *Priorité moyenne · Gouvernance produit — "Cette semaine"*; *Surveillance · Minimisation des données — "Continu"* | Veille IA |
| **Rédaction assistée** | Drafting brief | Document type · Références utilisées ("1 mémo interne, 2 jeux de clauses antérieurs, 1 alerte réglementaire") · Style retenu ("Concis, partner-level, prudent et orienté business"). **Guardrails** block: *Source-linked drafting · Visible uncertainties ("open points are surfaced instead of hidden") · Final human sign-off* | Syllogisme |

### 2c. The shipped Next.js app

Shell (`src/app/layout.tsx`): 64 px top bar with the `APX • Legal` wordmark (serif, gold
dot separator), `HeaderMeta` (link *"Données EU · RAG strict · audit"* → `/confiance`,
`LangToggle`, a "Cabinet" pill) · 224 px (`w-56`) desktop sidebar, hidden below `md` and
replaced by `MobileNav` · content column capped at `max-w-6xl`.

Nav (`src/components/Nav.tsx`, `NAV_ITEMS`) uses **geometric glyphs, not icons**:
`◵ Tableau de bord · ◆ Assistant · ❋ Cartographie · ▤ Dossiers · ◧ Documents · ◳ Syllogisme · ◰ Veille IA`.

| Route | File | Purpose | Key UI elements | Product |
|---|---|---|---|---|
| `/` | `src/app/page.tsx` | Positioning + corpus health | 4 `StatCard`s (Documents / Indexés / Qualité moy. / Catégories); "Trois capacités qu'un chat n'a pas" — 3 differentiator cards (Raisonner / Cartographier / Veiller); 4 CTA buttons; demo-mode banner | All |
| `/assistant` | `src/app/assistant/page.tsx` | Single entry point that routes to a tool | Heuristic intent router (`VEILLE_RE`, `REASON_RE` regexes, l.36–41) → `ask` \| `syllogisme` \| `veille`; manual override chips (Auto/Recherche/Syllogisme/Veille); persisted thread; per-answer "Ouvrir dans le module →" | All |
| `/cartographie` | `src/app/cartographie/page.tsx` | Firm-as-graph | Full-bleed `CorpusGraph` at 640 px | Documentation |
| `/dossiers` | `src/app/dossiers/page.tsx` | Case list | Card grid: id (mono) · lawyer badge · parties (serif) · objet · statut · counts (pièces / e-mails / `syllogisme ✓`) | Documentation |
| `/dossiers/[id]` | `src/app/dossiers/[id]/page.tsx` | The one screen that reads like a case file | Meta grid (Client / Partie adverse / Juridiction / Ouverture / Statut) · Synthèse factuelle + Demandes · Questions de droit (ordered list) · **Chronologie** (date · kind badge Jalon/E-mail/Pièce · label, with a `⚠️ à vérifier` marker on `borderline` entries) · **Bordereau de pièces** table (N° · Pièce · Date · Catégorie) · **Contexte mobilisé** = Notes internes + Veille impactante with urgency badges · the dossier's Syllogisme | Documentation + Syllogisme |
| `/documents` | `src/app/documents/page.tsx` | Corpus health + inventory | 4 `HealthStat`s (Total / Indexés / OCR requis / Qualité moy.) · **`QualityBar`** stacked bar (Haute `#1E7F5C` / Moyenne `#B7791F` / Faible `#B3261E`) · embedded `CorpusGraph` (460 px) · documents table (Titre · Catégorie · Statut · Chunks · Actions → *Reclasser* / *Supprimer*) | Documentation |
| `/documents/upload` | `src/app/documents/upload/page.tsx` | Ingest | Dashed drop zone (keyboard-accessible: `role="button"`, Enter/Space), file list with size, result card (`document_count` / `chunk_count` / `skipped_files`) | Documentation |
| `/documents/search` | `src/app/documents/search/page.tsx` | Query the corpus | Segmented **Question / Recherche** toggle · shared `AskLine` prompt · answer card with model badge · `Sources` list with **relevance score `%`** and "Ouvrir la pièce dans le dossier →" | Documentation |
| `/syllogisme` | `src/app/syllogisme/page.tsx` (870 lines — the largest screen) | The reasoning product | Zero-state: frameless `AskLine` centred at `max-w:680`, eyebrow *"Module 2 · Syllogisme juridique"*, 4 real-dossier suggestion rows. Answered state: question echo + "Rattaché à {parties} · {dossier}" · **`RetrievalFigure`** (live graph that lights up node by node) · Majeure / Mineure / Conclusion `ReasonBlock`s with superscript citation chips · **`ConfidencePanel`** · "Note rédigée" card with Word/PDF/Copy · Sources list · **`ConclusionsAction`** ("Rédaction · couche 2") · follow-up composer. Off-corpus questions get an `OffCorpusPanel` instead | Syllogisme |
| `/veille` | `src/app/veille/page.tsx` | Regulatory watch | Theme query field + Actualiser · specialty chips (Tout / Droit social / Corporate / Fiscal / IP-RGPD) · dynamic source chips · **Brief exécutif IA** card with "Mis à jour le {date}", period `<select>` (Tout / 30 jours / 3 mois) and **Exporter .docx** · item cards with **PRIORITÉ** badge + red left border, source badge, date, "Consulter la source →" and `→ DOS-YYYY-NNN` impacted-case links | Veille IA |
| `/confiance` | `src/app/confiance/page.tsx` | Trust page | 6 commitment cards (Données EU · **RAG strict "cité ou hors corpus"** · Aucun entraînement · Chiffrement en transit · Transparence du modèle · **Réversibilité**) · demo-mode disclosure · **security roadmap** with 4 "À venir" items (per-firm isolation, roles & sharing, **Journaux d'audit**, SSO) · contact/DPA | Cross-cutting |

**Screens that exist in the mockups but not in the shipped app:** Splash, Pipeline live,
the triage-bucket filters (Pertinent / À revoir / Rebut), the editable Bibliothèque table,
the **Audit drawer**, and the Génération/template picker.
**Screens that exist only in the shipped app:** `/assistant` (intent router),
`/cartographie`, `/dossiers/[id]`, `/confiance`.

---

## 3. Design language, as actually implemented

### 3a. Shipped app — colour palette

From `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-platform/apps/apx-demo/web/tailwind.config.ts`:

| Token | Hex | Swatch | Role in the code |
|---|---|---|---|
| `paper` | `#FBFAF8` | ▩ warm off-white | Page background (`body`, also `--paper` in `globals.css`) |
| `surface` | `#FFFFFF` | ▩ white | Cards, top bar, sidebar (`bg-surface/60`) |
| `ink` | `#15191E` | ▩ near-black | Body text |
| `muted` | `#5B6470` | ▩ slate grey | Secondary text, inactive nav |
| `navy` (DEFAULT) | `#0B1F3A` | ▩ deep navy | Primary brand: active nav, primary button, headings, `::selection` |
| `navy.600` | `#143150` | ▩ | Primary button hover, small links |
| `navy.400` | `#3A5578` | ▩ | Focus border, tertiary text, upload arrow |
| `navy.50` | `#EEF2F7` | ▩ pale blue | Ghost-button hover, badge bg, progress track, glyph tiles |
| `gold` | `#B8924A` | ▩ antique gold | The single accent: eyebrows, citation chips, dot in the wordmark, hover state |
| `line` | `#E7E3DB` | ▩ warm beige | Every border and divider |
| `ok` | `#1E7F5C` | ▩ green | Indexed status, high confidence, "Haute" quality |
| `warn` | `#B7791F` | ▩ amber | needs_ocr, "Revue humaine", **Hors corpus**, "À consolider" |
| `danger` | `#B3261E` | ▩ red | empty status, Supprimer, Fragilités bullets, **Priorité** badge |

Non-token hexes hard-coded in components (a real inconsistency to fix in the rebuild —
these bypass the token layer):

- `globals.css` — scrollbar thumb `#d8d3c9`; `.apx-cta` gradient
  `linear-gradient(135deg, #1b3c63 0%, #0e2647 46%, #0a1a32 100%)`; gold sheen
  `rgba(216,185,120,.18)` / `#d8b978`; `.apx-ask` placeholder `#b7b1a6`.
- `src/app/syllogisme/page.tsx` — repeats `#B8924A`, `#E7E3DB`, `#EEF2F7`, `#143150`,
  `#0B1F3A`, `#15191E` as inline style strings (l.77–78, 108, 141, 170–171, 191–192).
- `src/components/AskLine.tsx` l.87 — `filled ? "#0B1F3A" : "#5B6470"`.
- `src/app/documents/page.tsx` `QualityBar` — `#1E7F5C` / `#B7791F` / `#B3261E`.

**Graph palettes** (`src/components/CorpusGraph.tsx` l.9–28) are a **third, unrelated
colour system** — none of these are Tailwind tokens:

| Node type | Hex | | Document category | Hex |
|---|---|---|---|---|
| dossier | `#1f2a44` | | Contrats | `#B7791F` |
| client | `#1E7F5C` | | Correspondance | `#1E7F5C` |
| adverse | `#B3261E` | | Jurisprudence | `#2563EB` |
| avocat | `#B7791F` | | Pièces de procédure | `#4F46E5` |
| juridiction | `#6D28D9` | | Pièces comptables | `#64748B` |
| note | `#0E7490` | | Réglementaire | `#92400E` |
| veille | `#C2410C` | | Note juridique | `#0E7490` |
| bruit | `#9AA1AC` | | Doctrine | `#9D4EDD` |
| | | | Autre | `#334155` |

`src/components/CategoryGraph.tsx` l.7–15 defines yet another 9-colour series
(`#0B1F3A`, `#B8924A`, `#1E7F5C`, `#3A5578`, `#8C5A3B`, `#5B6470`, `#7A3E5E`, `#2F6E8E`,
`#9A8330`) — this one *is* brand-derived.

### 3b. Shipped app — typography

`src/app/layout.tsx` l.11–22, via `next/font/google`:

| Role | Family | Weights / styles | CSS var | Tailwind |
|---|---|---|---|---|
| Display | **Spectral** (serif) | 400, 500, 600 + italic | `--font-display` | `font-serif` → `["var(--font-display)","Georgia","serif"]` |
| Body | **Instrument Sans** | default | `--font-body` | `font-sans` → `["var(--font-body)","system-ui","sans-serif"]` |

There is **no mono token** in `tailwind.config.ts`, yet `font-mono` is used for dossier
ids and dates (`page.tsx` l.740, `dossiers/page.tsx`, `dossiers/[id]/page.tsx`) — it falls
through to the Tailwind default stack. A gap.

Observed scale (Tailwind class or literal px):

| Use | Size | Where |
|---|---|---|
| Ask prompt (`.apx-ask`) | **30 px** / line-height 1.3 / letter-spacing −0.01em, serif 400, italic placeholder | `globals.css` l.149–167 |
| Question echo (syllogisme) | 24 px, serif, line-height 1.3 | `syllogisme/page.tsx` l.732 |
| H1 (`PageHeader`) | `text-3xl` serif navy, `tracking-tight`, `text-balance` | `components/ui.tsx` l.39 |
| Stat value | `text-4xl` serif navy, `leading-none` | `ui.tsx` l.72 |
| H2 (`Section`) | `text-xl` serif navy | `ui.tsx` l.183 |
| Reasoning body | **15.5 px / line-height 1.68** | `syllogisme/page.tsx` l.117 |
| Body default | `text-sm` (14 px) `leading-relaxed` | throughout |
| Eyebrow / label | `text-xs` (12 px), `font-semibold`, `uppercase`, **`tracking-[0.18em]`**, gold | `ui.tsx` l.35 |
| Micro (sidebar footer, badges) | `text-[11px]`, `text-[10px]` | `SidebarFooter.tsx`, veille priority badge |
| Hint / meta | inline `fontSize: 12.5` | `AskLine.tsx` l.74, `syllogisme/page.tsx` l.468 |

The eyebrow pattern — *12 px, uppercase, `tracking-[0.18em]`, gold* — is the single most
repeated typographic signature in the codebase.

### 3c. Shipped app — spacing, radii, elevation, motion

- **Radii**: `rounded-xl` is overridden to **14 px** (`tailwind.config.ts` l.32–34) and is
  the card radius. Buttons `rounded-lg` (8 px). Badges `rounded-md` (6 px). Chips/pills
  `rounded-full`. Citation superscripts `rounded-[5px]`. Source rows `rounded-[10px]`.
  The CTA is `12px`. **Five different radii in play.**
- **Shadows** (`tailwind.config.ts` l.28–31): `card` = `0 1px 2px rgba(16,24,40,.04), 0 1px
  3px rgba(16,24,40,.06)`; `pop` = `0 8px 28px rgba(11,31,58,.12)` (hover lift on
  clickable cards). Everything else is borders, not shadow.
- **Spacing**: 4 px base. Cards `p-5` / `p-6` / literal `p-[22px]`. Section rhythm `mb-8`.
  Content max widths differ per screen — `max-w-6xl` (shell), `max-w-3xl` (veille,
  confiance, search), `720` px (syllogisme thread), `760` px (assistant), `680` px
  (syllogisme zero state). **Inconsistent.**
- **Motion**: `@keyframes apxFade` (6 px rise + fade, 0.5 s) staggered by hard-coded delays
  — 0 / 140 / 280 ms for the three premises, then 360 (confidence) / 420 (note) / 540
  (sources) / 640 ms (conclusions CTA). Retrieval reveal timings in
  `syllogisme/page.tsx` l.654–665: anchor at 350 ms, then one node every **420 ms**.
  `@keyframes apxSheen` (3.6 s gold sweep on the CTA). `prefers-reduced-motion` is
  respected in three places (`globals.css` l.139, l.196; `syllogisme/page.tsx` l.645).
- **Deliberate rule-break, documented in the source**: `globals.css` l.42–47 —
  *"This is the one place the system breaks its no-gradient rule, on purpose."* The
  `.apx-cta` has a navy gradient, a guilloché pinstripe
  (`repeating-linear-gradient(115deg, …, rgba(216,185,120,.07) 7px, …)`) and a travelling
  gold sheen. **Note: `.apx-cta` is defined but no `.tsx` file references it** — dead CSS.

### 3d. Component patterns (`src/components/ui.tsx`, 191 lines)

`Card` (`bg-surface border border-line rounded-xl shadow-card`) · `PageHeader`
(eyebrow/title/description/action) · `StatCard` (with a loading spinner state) · `Badge`
(tone map: `indexed`→`bg-ok/10 text-ok`, `needs_ocr`→warn, `empty`→danger,
`default`→`bg-navy-50 text-navy-600`) · `Button` (`primary` navy / `ghost` bordered /
`danger` red-outline; `h-10 px-4 rounded-lg`; renders as `next/link` when `href` is given)
· `Spinner` · `EmptyState` · `Section`. That is the whole design system — **no Input, no
Select, no Table, no Modal, no Drawer, no Tabs, no Toast primitive.** Every form control,
table and toggle in the app is bespoke Tailwind written inline in the page.

### 3e. Mockup design languages (three incompatible systems)

| | `philippe.html` (6 May) | `maquette_enfr` / `maquette_anfr_v2` (13 May) | `maquette-syllogisme-veille-demo.html` (Lexoria) | Shipped app |
|---|---|---|---|---|
| Brand hue | Cool blue | **Forest green + rose** | Navy + gold on warm grey | **Navy + gold on warm off-white** |
| Ramp | `brand` 50 `#f5f7fa` · 100 `#e8eef5` · 200 `#cfdbe8` · 400 `#7a93b3` · 600 `#395876` · 700 `#27425c` · 800 `#1a2e44` · 900 `#0f1f33` | `forest` 50 `#F1F5F4` · 100 `#DCE7E4` · 200 `#B5CAC4` · 300 `#7FA39A` · 400 `#4F7A70` · 500 `#2F5A53` · 600 `#1B3B36` · 700 `#143029` · 800 `#0F2522` · 900 `#0A1A18`; `rose` 50 `#FBF1EE` · 100 `#F5DDD7` · 200 `#EFC6BC` · 300 `#E8B4AC` · 400 `#D29185` · 500 `#B26F62`; `cream` 50 `#FCFAF6` · 100 `#FAF7F2` · 200 `#F5F2EB` · 300 `#EFEADD` · 400 `#E5E0D5` | CSS vars: `--brand #1b3352` · `--brand-2 #254d74` · `--accent #b8924a` · `--bg #f1efe9` · `--panel #ffffff` · `--panel-warm #faf8f4` · `--line #e5e0d6` · `--text #1b2a38` · `--muted #8090a2` · `--sidebar-bg #18293c` · semantic trios `--green #0b7265` / `--amber #895018` / `--red #8b1f1f` (each with `-soft` and `-border`) | see §3a |
| Fonts | Inter + **Source Serif 4** | Inter + **Source Serif 4** + **JetBrains Mono** | **Inter + Lora** | **Instrument Sans + Spectral** |
| Radii | Tailwind defaults | Tailwind defaults, cards `rounded-2xl` | `--r-xs 6 / --r-sm 8 / --r 12 / --r-lg 16` | `xl` = 14 px |
| Shadows | Tailwind default `shadow-sm` | `soft` `0 1px 2px rgba(15,37,34,.04), 0 4px 12px rgba(15,37,34,.05)`; `lift` `0 8px 28px rgba(15,37,34,.10)…`; `glow` `0 0 0 4px rgba(232,180,172,.18)` | `--shadow-xs/sm/md` on `rgba(27,51,82,…)` | `card` / `pop` |
| Delivery | Tailwind CDN + Babel standalone, single file | idem | hand-written CSS, vanilla JS | Next.js build |

The **`#b8924a` gold is the only value that survives from the Lexoria mockup into the
shipped app** — it is the shipped `gold` token, exactly. Everything else was re-picked.

---

## 4. Interaction patterns worth keeping

Ordered by how much design thinking is already banked in them.

1. **Editable triage table with a visible edit log** — *mockup only*
   (`maquette_anfr_v2.html` l.1509 `EditableCell`, l.1530 `TablePage`). Click a cell → it
   becomes an input/textarea, autofocus + select; **Enter** commits (⌘/Ctrl+Enter for the
   multiline variant), **Escape** reverts to the original value, blur commits. On commit
   the cell flashes `ring-2 ring-forest-300` for 800 ms and the change is pushed onto a
   `history` array (`{ts, rowId, cote, key, prev, next}`, capped at 8) rendered as a
   monospace `prev → next` diff list. Thématique is a `<select>`, so re-classification is
   one click and never a free-text mistake. The strapline in the header says it outright:
   *"Édition cellule par cellule · audit trail systématique · aucun écrasement destructif."*
   **This is the single most valuable pattern in the whole asset set and it does not exist
   in the shipped app.**

2. **Audit drawer** — *mockup only* (`maquette_anfr_v2.html` l.951). A right slide-over
   that answers "why did the machine say that?" with: the decision + confidence bar, the
   metadata it used, the **verbatim extracts it retained** (serif italic blockquotes), a
   numbered **"Trace d'audit proposée"**, and four reversible actions (Valider / Reclasser
   / Signaler / Verser au syllogisme). Reachable from the dashboard list, the corpus list,
   the table, the chat source pane and the syllogisme source rail — i.e. **provenance is
   always one click away, from anywhere**.

3. **Citation → source → graph cross-highlight** — *shipped*
   (`syllogisme/page.tsx` l.51–89 `renderWithCites`, l.149 `SourceRow`). Every `[node_id]`
   token in the generated text is rewritten to a numbered gold superscript chip. Hovering
   a chip sets `activeSrc` + `focusId`, which simultaneously (a) fills the chip gold,
   (b) tints and outlines the matching source row, and (c) focuses the matching node in
   the live `CorpusGraph`. Hovering the source row or clicking a graph node does the same
   in reverse. Source rows resolve to a real route via `sourceHref()`
   (`src/lib/links.ts`), falling back to the turn's dossier. **Tri-directional linkage —
   text ↔ source ↔ map — is a genuinely distinctive asset.**

4. **Progressive retrieval reveal** — *shipped* (`syllogisme/page.tsx` l.436
   `RetrievalFigure`, l.644–665). Before any prose appears, the dossier anchor lights up at
   350 ms, then each cited passage lights in sequence every 420 ms, with a live counter
   `n / total passages`. On completion the header flips from a spinner + *"Lecture du
   corpus du cabinet…"* to `✓` + *"Récupération dans le corpus — N passages cités · M
   nœuds"*. `prefers-reduced-motion` short-circuits the whole animation to its end state.
   It makes retrieval *legible* rather than magical. The mockup's equivalent is the
   `SyllogismeStep` skeleton-loader staging (l.1840) and the token-streaming chat.

5. **Frameless "write on the line" prompt (`AskLine`)** — *shipped*
   (`src/components/AskLine.tsx` + `globals.css` l.149–183). A borderless 30 px serif
   textarea that auto-grows to content, under a 2 px rule that fills left-to-right with a
   `#b8924a → #d8b978` gradient the moment the field is non-empty. Enter submits,
   Shift+Enter newlines; the affordance is spelled out inline (*"pour raisonner"* + a
   `↵ Entrée` key cap). Shared verbatim by `/syllogisme`, `/documents/search` and
   `/assistant`. It is the app's signature moment.

6. **Confidence + human-review gate** — *shipped* (`syllogisme/page.tsx` l.276
   `ConfidencePanel`). A global percentage bucketed into three named levels —
   `≥0.85` **Confiance élevée** `#1E7F5C` · `≥0.70` **À consolider** `#B7791F` · else
   **Revue humaine requise** `#B3261E` — plus three sub-bars (Majeure / Mineure /
   Conclusion). When `requires_human_review` is true it renders a warn-toned box listing
   `questions_complementaires`; `fragilites` render as `risque — Parade : …`. The mockup
   equivalent is `ConfidenceBar` (`philippe.html` l.405, thresholds 0.85 / 0.60).

7. **Honest "hors corpus" panel** — *shipped* (`syllogisme/page.tsx` l.251
   `OffCorpusPanel`, and a compact twin in `assistant/page.tsx` l.283). When
   `res.off_corpus` is true the app renders **no syllogism at all** — just a warn card
   saying the question matches no dossier and naming three questions that *would* work.
   This is the direct UI answer to Max's review (§5).

8. **Chat / thread with tool routing** — *shipped* (`assistant/page.tsx`). Two regexes
   classify the question into `veille` / `syllogisme` / `ask`; the chosen tool is shown as
   a badge on the question echo and can be forced with chips. Threads persist across
   reloads via `usePersistedState` (`src/lib/use-persisted-state.ts`, localStorage keys
   `apx_assistant_thread`, `apx_syllo_turns`). The composer becomes
   `sticky bottom-0 … backdrop-blur` once the thread is non-empty. The mockup's chat
   instead streams tokens at 18 ms/2 chars with a typing cursor and a **persistent source
   preview pane** (`maquette_anfr_v2.html` l.1665) — the shipped app has no such pane.

9. **Veille prioritisation** — *shipped* (`veille/page.tsx` l.35 `priorityMap`). The AI
   brief is parsed line-by-line for `/priorit/i`; any `DOS-\d{4}-\d{3}` reference on that
   line becomes a clickable link on the matching item card, which also gains a
   `PRIORITÉ` badge and a 3 px danger left-border. Fragile (string matching on the first
   24 characters of a title) but the *idea* — the brief drives card prominence and links
   news to open cases — is right.

10. **Language switcher** — *shipped* (`src/components/LangToggle.tsx`). A 2-segment
    `FR|EN` pill in the top bar, `role="group"`, `aria-pressed` on the active segment;
    persists to `localStorage["apx_lang"]` and writes `document.documentElement.lang`.
    See §7 for what it actually translates.

11. **Mobile drawer** — *shipped* (`src/components/MobileNav.tsx`). Hamburger below `md`
    → `w-72 max-w-[82%]` left slide-in over a `bg-navy/40` scrim, `role="dialog"`
    `aria-modal="true"`, body-scroll lock while open, auto-close on route change, and the
    trust link + version repeated in its footer. The source comments the deliberate
    absence of a CSS transition ("stays robust in throttled / headless contexts").

12. **Graph filters and legend** — *shipped* (`CorpusGraph.tsx` l.435 `Picker`, l.451
    `Legend`). Force-directed canvas layout with a deterministic seeded initial placement,
    filters by année / dossier / catégorie / type de fichier, hover-neighbourhood
    highlight, gold halo (`#B8924A`) on highlighted nodes, node radius encoding quality
    (`3 + quality * 2.2`).

---

## 5. Client feedback on the designs

**Source**: `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Resources/2026-06-06_Maquette Syllogisme - Review.docx`.
Extraction succeeded (1 245 paragraphs; `xml.etree` fails on this machine — pyexpat is
broken — so the text was pulled with a regex over `word/document.xml`). Two named
reviewers: **Max** (evaluates the product as a lawyer) and **Lucia** (specifies what to
build next). Quotes are verbatim French; translations are mine.

### 5.1 Max — wording

> « Reformuler "chaque sortie restant ciblée ou hors corpus" par : **Chaque réponse est
> soit sourcée dans votre corpus, soit explicitement signalée comme externe au corpus.** »
>
> « NB. Max : je pense que les avocats ne vont pas comprendre de quoi il s'agit. »

*(Reword "each output remaining targeted or outside corpus" as "Every answer is either
sourced in your corpus, or explicitly flagged as external to the corpus." — NB: I think
lawyers won't understand what this is about.)*

**Status: adopted.** The shipped app uses almost exactly Max's sentence, in five places —
`src/app/page.tsx` l.70 (*"chaque réponse étant soit sourcée dans votre corpus, soit
signalée comme externe à celui-ci"*), `AskLine.tsx` default `hint`, `SidebarFooter.tsx`,
`MobileNav.tsx`, and `translations.ts` l.10/28/134.

### 5.2 Max — the off-corpus failure, the single most important design finding

> « Je me questionne sur l'élaboration du syllogisme dans la maquette : Ont-ils été
> générés directement par une IA ou ont-ils été générés à partir d'un corpus de documents
> […] ? »

He then pasted a full, unrelated employment-law hypothetical (M. Martin / Alpha Conseil —
bonus removal, coerced pay cut, sidelining, dismissal for *insuffisance professionnelle*)
and reported:

> « **Le module a répondu quelque chose d'hors sujet en se basant sur le dossier
> M. Julien Dupuis c/ TechnoSys SAS.** »
>
> « Je pense qu'il serait opportun de **ne pas répondre à ce genre de cas pratique** à
> partir du peu ou pas de data disponible […] dans les situations distinctes de celles
> traitées dans les dossiers car **le hors sujet risque de faire flipper les prospects**. »
>
> « Plusieurs solutions : soit la maquette ne permet pas de poser des cas pratiques sur
> des sujets de droit non traités dans les dossiers dispo dans la maquette ; soit la
> maquette le permet et répond tant bien que mal au cas pratique **comme le ferait une IA
> générative sans RAG**. »

*(The module answered something off-topic by falling back on the Dupuis case. It would be
better not to answer this kind of hypothetical at all when there is little or no relevant
data, because an off-topic answer risks freaking prospects out.)*

**Status: adopted** — this is the origin of `off_corpus` and `OffCorpusPanel`
(`src/app/syllogisme/page.tsx` l.251, l.626 *"RAG-strict guard: question outside the demo
corpus → no off-topic answer"*), and of the mirror panel in `/assistant`. The panel even
names Dupuis/Nader/Silva as questions that *will* work.

### 5.3 Max — surface the legal sources inside the prose

> « Dans ce cas, la réponse syllogistique n'est pas hors sujet. Il faudrait néanmoins
> **mieux mettre en avant les sources de droit**. Ex. : commencer un paragraphe par "en
> application de l'article L. 225-2 du code du travail, blablablabla". Idem pour les
> arrêts de la Cour de cassation : "la Chambre sociale a d'ailleurs consacré dans un arrêt
> du 2 avril 2013, les critères d'application de ce texte…". Bref, **ce genre de rigueur
> dans la rédaction devrait - de toutes façons - être assurée par les documents réels des
> avocats** avec lesquels on travaille. Ainsi, l'IA devrait être capable de répéter ce
> style, cette structure, les sources de droit, etc. »

*(The sources of law must be foregrounded in the prose itself — "pursuant to article
L. 225-2 of the Labour Code…" — and this rigour should come from the lawyers' real
documents; the AI should be able to reproduce that style, structure and sourcing.)*

**Status: partially open.** The shipped app carries the *machinery* for this — `MajeureStruct`
has `fondements_textuels` and `jurisprudence_appui` (`src/lib/api.ts` l.88–96) — but the
Syllogisme screen renders only the flat `res.majeure` / `res.mineure` / `res.conclusion`
strings with `[id]` chips. **`res.structured` is read for `fragilites` only**
(`syllogisme/page.tsx` l.775). The structured legal grounds are never displayed.

### 5.4 Lucia — drafting must be a separate layer, and it must reach Word

> « Nous mettons en avant la fonctionnalité de rédaction d'actes. Il serait donc optimal
> d'**avoir un module rattaché à Word**. »
>
> « **Syllogisme = moteur de raisonnement** : Il reste tel quel comme étape intermédiaire
> visible dans l'interface. L'avocat voit le raisonnement structuré, les sources
> identifiées, **peut valider ou corriger avant de passer à l'étape suivante**. »
>
> « **Rédaction = couche de présentation (à ajouter)** Un bouton "Rédiger la note" qui
> prend le syllogisme validé et génère un .docx en prose fluide au style cabinet — **sans
> les sources dépliées, sans la structure Majeure/Mineure visible**, juste la note "En
> droit / En l'espèce / Par conséquent" avec renvois en bas de page. »
>
> « Le .docx output doit être **paramétrable par cabinet**, ce qui implique de prévoir un
> système de templates ou d'exemples de référence par client. »

She then supplied a full implementation spec: a `syllogisme` JSON contract, a
`CABINET_STYLES` table keyed by `cabinet_id` (the worked example is `"lerins"` / "Lérins
Avocats") with a per-firm `system_prompt` mandating *"POUR : [client] / CONTRE :
[adversaire]"*, *"EN FAIT, / EN DROIT, / PAR CES MOTIFS,"*, footnoted citations `¹ ² ³`,
**"Jamais de mention d'outil ou système IA"**, and *"Ne reproduis pas la structure
Majeure/Mineure/Conclusion — rédige en prose fluide"*. She closes with:

> « **Point critique** : la qualité du rendu final dépend directement des exemples de
> conclusions réelles fournis dans `CABINET_STYLES[cabinet_id]["examples"]`. Sans exemples,
> le style sera générique mais correct. Avec 2-3 vraies conclusions du cabinet, **il
> devient indiscernable d'un acte rédigé par un collaborateur senior**. »

She is transparent about provenance: *« A ta de vérifier que ce que j'ai mis ici est
correcte, car je le fais avec Claude 🥲 »*.

**Status: adopted in shape, not in configurability.** `ConclusionsAction`
(`syllogisme/page.tsx` l.371) renders exactly the requested affordance — eyebrow
*"Rédaction · couche 2"*, copy promising *"EN FAIT / EN DROIT / PAR CES MOTIFS […] en
prose continue — sans la structure Majeure/Mineure — avec renvois numérotés"*, and a
button *"Rédiger les conclusions (.docx)"* wired to `redactConclusions()` +
`downloadConclusionsDocx()`. **There is no per-firm style UI, no template picker and no
`cabinet_id` anywhere in the front-end** — the "paramétrable par cabinet" requirement is
unbuilt. There is no Word add-in either.

### 5.5 Lucia — Veille: five concrete UI asks

Verbatim: *« Je te mets ici les peites fonctionnalités à ajouter »* — (1) specialty +
source filter bar between the search field and the brief, with the exact list
`Tout / Droit social / Corporate / Fiscal / IP / RGPD / Immobilier`; (2) **replace the
`pré-calculé (sans clé API)` badge with a real timestamp** — *"Mis à jour le
{dd/mm/yyyy hh:mm}"*; (3) a clickable link to the official source on every card, plus an
explicit *"Consulter la source →"* at the card foot; (4) a **PRIORITÉ** badge with a
`3px solid #c0392b` left border, driven by whether the item appears under `[PRIORITÉ]` in
the AI brief, plus `→ {dossier}` links to impacted cases; (5) an **Export brief** button
and a period selector (`7 derniers jours / 30 derniers jours / 3 derniers mois`).

**Status: 4½ of 5 adopted**, in `src/app/veille/page.tsx`. Deltas: the **Immobilier**
specialty was dropped (only `all`, `droit_social`, `corporate`, `fiscal`, `ip_rgpd` exist,
l.13–20); the period selector offers `Tout / 30 jours / 3 mois` rather than
`7 / 30 / 90` days (l.23–27); the timestamp shows date only, no time (l.108–113); and the
priority border is `border-l-[3px] !border-l-danger` (`#B3261E`) rather than her
`#c0392b`.

The rest of the document (≈1 000 of the 1 245 paragraphs) is **back-end** specification —
Légifrance/Judilibre via PISTE, EUR-Lex REST + SPARQL, CURIA, HUDOC, and regulator RSS
(EDPB, ESMA, EBA, EIOPA) — closing with: *« En pratique, l'essentiel pour couvrir 90% des
besoins est **EUR-Lex + CJUE + HUDOC**. Les régulateurs sectoriels s'ajoutent en fonction
de la spécialité du cabinet — tu peux les **activer par profil client dans les paramètres
de la veille** »*. That last clause is a **UX requirement with no screen**: there is no
settings surface anywhere in the app.

---

## 6. UX gaps and weaknesses

Measured against the product's own guardrails
(`00-sources/legacy-PLAN-2026-05-31.md` §5) and against `00-README.md`'s non-negotiables.

### Guardrail compliance scorecard (shipped app)

| Guardrail | Verdict | Evidence |
|---|---|---|
| Strict RAG — cite, or say "not in corpus" | ✅ **Honoured, and well** | `OffCorpusPanel` (`syllogisme/page.tsx` l.251), `off_corpus` guard l.626, twin in `assistant/page.tsx` l.283, promise restated in the shell footer and on `/confiance` |
| Every claim cited to a source | ⚠️ **Partial** | Syllogisme and Search cite properly. **`/assistant`'s `AskBlock` shows the answer prose then a bare line "N source(s) citée(s) — title · title · title"** (l.278–287) — no chips, no links, no way to open the source. `VeilleBlock` truncates to 4 items |
| Confidence surfaced | ⚠️ **Syllogisme only** | `ConfidencePanel` exists. **No per-document confidence anywhere in `/documents`** — only an aggregate `QualityBar`, and `quality` is buried as a node radius in the graph |
| Triage never destroys; "rebut" is a label | ❌ **Violated** | There is **no triage UI at all** in the shipped app. The one destructive control that exists — `onDelete` in `documents/page.tsx` l.46 — calls `deleteDocument(id)` behind a raw `confirm("Supprimer ce document du corpus ?")`, with **no undo, no soft-delete, no audit entry**. The mockups' `Pertinent / À revoir / Rebut` buckets, editable cells and change history did not ship |
| Recall over precision; default to "à revoir" | ❌ **No surface** | No bucket exists to default into |
| Auditability is the trust mechanism | ❌ **Not built** | The word "audit" appears in the shipped app exactly **4 times**: a header link label, a `/confiance` roadmap card titled *"Journaux d'audit"* explicitly marked **"À venir"**, and two `translations.ts` entries. The mockup's `AuditDrawer` and the syllogisme mockup's *"Verser à l'audit"* action are both absent. **The named client requirement (Emmanuel: random-sampling audit, every classification traceable) has no UI** |
| Human-in-the-loop; no auto-anything | ⚠️ **Passive** | Nothing auto-sends, but there is no **explicit validation act** either: no "Valider" button, no reviewer identity, no state transition from *proposed* to *accepted*. The mockups had `Valider / Reclasser / Signaler` in the drawer and `Valider et envoyer` on the syllogisme synthesis |
| Reversibility | ⚠️ **Claimed, thin** | `/confiance` promises *"export des notes (Word, PDF) et suppression du corpus à votre main"* — exports do work (`src/lib/export.ts`). But reversibility of a *decision* (undo a reclassification, restore a deleted doc) does not exist |
| RBAC by matter/team | ❌ **Absent** | No auth, no roles, no user. The header shows a static "Cabinet" pill. `/confiance` lists roles as roadmap |
| Stale-precedent flagging | ❌ **Absent** | Not in the UI. The nearest thing is the dossier page's "Veille impactante" list |

### Screen-level weaknesses

1. **No settings surface anywhere.** No firm profile, no practice-area subscription, no
   style/template configuration — all three are explicit client asks (§5.4, §5.5). The
   veille specialties are a hard-coded array of keyword lists
   (`veille/page.tsx` l.13–20).
2. **`/documents` is a dev tool, not a lawyer's tool.** Its columns are Titre · Catégorie ·
   Statut · **Chunks** · Actions. "Chunks" is an implementation detail on the main
   inventory screen; the actions are *Reclasser* (fire-and-forget, no preview of what
   changes) and *Supprimer* (destructive).
3. **`/dossiers/[id]` is the only screen not translated.** It contains zero `useI18n`
   calls — every string is hard-coded French (`Dossier introuvable`, `Synthèse factuelle`,
   `Bordereau de pièces`, `Contexte mobilisé`, …). Switching to EN leaves it fully French.
4. **`/cartographie` is a graph with no task.** 23 lines: a header and a 640 px canvas.
   No selection panel, no "what do I do with this", no path from a node to an action.
5. **The intent router is invisible and unexplained.** `/assistant` picks a tool from two
   regexes (`assistant/page.tsx` l.36–41) and shows only a result badge — the user is
   never told *why* a question went to Veille, and there is no "that was wrong, re-run as
   X" affordance on an existing answer (only a mode chip for the *next* question).
6. **Errors are strings.** `setError(e instanceof Error ? e.message : "Erreur")` in four
   screens; rendered as red text with no retry, no guidance, no error taxonomy.
7. **Loading is inconsistent.** `StatCard` has a skeleton-ish spinner state; tables and
   lists have none; the syllogisme has a bespoke pending block; `/veille` has three
   different loading treatments in one file (l.157, l.164, l.204).
8. **Five different content max-widths** (§3c) and five different radii mean the shell
   never feels like one product across routes.
9. **Accessibility is inconsistent.** Good: `MobileNav` (`role="dialog"`, `aria-modal`,
   scroll lock), `LangToggle` (`aria-pressed`), the upload drop zone (`role="button"` +
   Enter/Space), `prefers-reduced-motion` in three places. Missing: citation superscripts
   are `<sup>` with `onMouseEnter` only — **not keyboard-reachable and not focusable**, so
   the app's flagship interaction is mouse-only; no focus-visible styling is defined; nav
   glyphs are decorative Unicode with no `aria-hidden`; the confidence bars have no
   `role="progressbar"` or accessible value.
10. **Dead and duplicated code in the design layer.** `.apx-cta` (the deliberately
    special gradient CTA, ~90 lines of CSS) is referenced by no component.
    `src/lib/word-export.ts` exports `downloadSyllogismeWord` while `src/lib/export.ts`
    exports `downloadSyllogismeDocx` — two Word paths.
11. **Three unreconciled colour systems** inside one shipped app (tokens · CorpusGraph ·
    CategoryGraph), plus ~20 hard-coded hexes bypassing the tokens (§3a).
12. **The mockups and the shipped app disagree on almost everything visual** — forest+rose
    vs navy+gold, Source Serif 4 vs Spectral, Inter vs Instrument Sans, icons vs Unicode
    glyphs, 7 workflow steps vs 7 unrelated nav items. Anyone who saw a demo in May and
    the app in June saw two different products. **Also note the domain drift**: the
    mockups are Luxembourg corporate/funds (SPA, AIFM, CSSF, UBO); the shipped demo is
    French employment law (Marchand & Lefèvre, barème Macron, prud'hommes).
13. **Terminology is not settled.** *Majeure/Mineure/Conclusion* (shipped, and mockup with
    Latin) vs *Règle/Faits/Conclusion* (Lexoria) vs Lucia's *En droit / En l'espèce / Par
    conséquent* for the drafted output. Same for `Bibliothèque annotée` vs `Corpus
    documentaire`, `Recherche sourcée` vs `Interroger le corpus`, `Pièce` vs `Document`.
14. **No empty/first-run story for a real firm.** Every screen assumes a populated demo
    corpus. `EmptyState` exists but is used twice. There is no onboarding, no "connect your
    server", no ingestion progress after the upload result card.

---

## 7. i18n reality

### How it works today

`src/lib/i18n.tsx` — a React context holding `lang: "fr" | "en"`, `setLang`, and
`t(fr: string) => string`. The **translation key *is* the French source string**:

```ts
const t = useCallback((fr: string) => (lang === "en" ? EN[fr] ?? fr : fr), [lang]);
```

`src/lib/translations.ts` is a single flat `Record<string, string>` — **295 lines, ~250
entries**, grouped by comment blocks (Shell, Dashboard, Assistant, Syllogisme, Search,
Veille, Confiance, Documents, Upload, Dossiers, Cartographie, CorpusGraph). The file's own
header states the policy:

> "English translations keyed by the French source string. A missing key falls back to
> French, so partial coverage never breaks the UI. **The French legal corpus (dossiers,
> syllogismes, veille items) stays French — it is data, not UI.**"

Persistence: `localStorage["apx_lang"]`, hydrated in an effect after mount so the first
render always matches the SSR output (`"fr"`). `document.documentElement.lang` is updated
on change, but `layout.tsx` hard-codes `<html lang="fr">` server-side.

### What this actually means

| Property | Reality |
|---|---|
| Source language | **French.** English is a derived overlay |
| Coverage | Partial *by design*. `/dossiers/[id]` (298 lines) has **no `useI18n` at all** — 100 % French in EN mode. `/documents` has an untranslated `confirm("Supprimer ce document du corpus ?")` (l.46) and untranslated `QualityBar` labels `Haute / Moyenne / Faible` |
| Content | Never translated — dossiers, syllogisms, veille items, AI output stay French regardless of `lang` |
| Formatting | `toLocaleDateString("fr-FR")` is hard-coded in `veille/page.tsx` (l.106, l.240) and `maquette_anfr_v2.html` — **dates stay French even in EN** |
| Language of AI output | **Not controlled by the toggle.** No `lang` is passed to `draftSyllogism`, `askDocuments` or `getVeille` (`src/lib/api.ts`) |
| SEO / SSR | One `<html lang="fr">`, one URL per page. No `/fr` `/en` routes, no `hreflang`, no server-rendered EN |
| Mockups | `maquette_anfr_v2.html` uses the *opposite* model — a proper `DICT` of ~250 **semantic keys** (`'sidebar.tableau': { fr, en }`), `LangContext` + `useT()`. `maquette-syllogisme-veille-demo.html` uses `data-i18n` attributes swapped by vanilla JS. `philippe.html` and `maquette_enfr.html` are French-only |

### Implications for the rebuild

- **French-as-key does not survive.** Any copy edit to a French string silently breaks its
  English translation (silent fallback to French — no build error, no lint). With Max
  already having rewritten one core sentence (§5.1), copy *will* churn.
- The mockup's `'namespace.key': { fr, en }` shape is the better ancestor and it already
  exists — **~250 keys of FR/EN copy are sitting in `maquette_anfr_v2.html` l.177–423**,
  covering sidebar, header, splash, audit drawer, dashboard, pipeline, import, table,
  chat, syllogisme and generate. That is a free head start on a real message catalogue.
- **Luxembourg makes this load-bearing, not cosmetic.** Philippe & Partners is a
  Luxembourg firm; the Lexoria pitch is written EN-first. A rebuild should treat FR and EN
  as **peers** (per-locale routes, locale-aware dates/numbers, and a `lang` parameter
  threaded into every LLM call so the *answer* is in the reader's language), not as a
  French app with an English coat.
- Decide explicitly, and make it visible in the UI, what **stays French**: French legal
  terms of art (*conclusions*, *ordonnance 145 CPC*, *veille*, *bordereau de pièces*,
  *Majeure/Mineure*) and quoted corpus text must not be machine-translated — a
  mistranslated legal term is a liability. The current file already assumes this; the
  rebuild should state it as a rule and show the reader when they're looking at
  untranslated source material.

---

### Appendix — one-line salvage verdicts

| Asset | Verdict |
|---|---|
| `maquette_anfr_v2.html` — editable table + audit drawer + FR/EN dict | **Salvage the interaction design and the copy.** Highest-value artefact in the set |
| Shipped `/syllogisme` — citation ↔ source ↔ graph, confidence, off-corpus, AskLine | **Salvage the patterns**, rebuild the implementation (870 lines, inline hexes, mouse-only citations) |
| Shipped `/veille` | **Salvage** — it is the closest thing to a client-validated screen |
| Shipped `src/components/ui.tsx` | Keep the *shape* (Card/Badge/Button/Section), rebuild on a real primitive set |
| `tailwind.config.ts` tokens | **Keep the palette** (navy `#0B1F3A` + gold `#B8924A` + warm paper `#FBFAF8`); reconcile the three graph palettes into it |
| `philippe.html`, `maquette_enfr.html` | Superseded by `maquette_anfr_v2.html`; keep as provenance only |
| `2026-05-06_philippe.html` | Archive — it is a source-code printout, not a mockup |
| Shipped `/documents`, `/cartographie` | **Redesign from scratch** — both are engineer-facing, not lawyer-facing |
| Shipped `/dossiers/[id]` | Keep the information architecture (chronologie + bordereau + contexte mobilisé); it is the best-structured screen. Translate it |
