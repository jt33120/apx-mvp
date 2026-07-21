# 01 — Client & Commercial Context (APX MVP)

> **Purpose.** Ground-truth context pack for BMAD product planning on the APX MVP. Everything below is sourced from the APX-Advisory knowledge base. Citations are paths **relative to `/Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/`**.
> **Language note.** Written in English; French legal terms of art (*ordonnance 145 CPC*, *conclusions*, *cote*, *rebut*, *veille*, *syllogisme*, *devis*) are kept verbatim and glossed on first use.
> **Source window.** Oldest dated source: 2026-04-20. Newest dated source: **2026-06-20** (`Agents/mvp-updates/2026-06-20T10-20+0200-suggestions.md`).

> ⚠️ **Conflict/staleness — read this first:** `Agents/state.json` declares itself the "single source of truth" but its `_meta.last_updated` is **2026-04-28T14:00:00+02:00** (`Agents/state.json`). Every daily cron brief from 2026-05-01 to 2026-05-24 re-reports that same stale timestamp verbatim (e.g. `Agents/recaps/2026-05-24-cron-brief.md`), and the 2026-05-04 standup explicitly notes "State.json : dernière mise à jour 2026-04-28 — à mettre à jour après le call Lucia mardi" (`Agents/recaps/2026-05-04-monday-standup.md`). **Roughly two months of commercial and technical evolution (May–June 2026) is NOT reflected in `state.json`.** Where state.json disagrees with a May/June source, the later source is flagged below.

---

## 1. Who APX Advisory is

### 1.1 Positioning

| Item | Content | Source |
|---|---|---|
| What | "Conseil & ingénierie IA pour cabinets d'avocats" (AI consulting & engineering for law firms) | `Agents/state.json` |
| Deployment posture | On-premise / EU. Sur-mesure (bespoke), RGPD + AI Act compliant | `Agents/state.json` |
| Internal tagline | "Agence IA radicale" | `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| Explicit refusal | No SaaS subscription model | `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| Differentiator narrative | "moteur d'IA français, hébergement français, équipe française" — sovereignty as commercial argument | `Agents/decisions/2026-04-28-stack-llm-hebergement.md` |
| Differentiators (client-facing) | Deployment on client infra (secret professionnel guaranteed); full traceability for audit (RGPD/AI Act); the firm's own drafting style, not standardisation; "pas de formation requise (interface minimale)" | `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` |

### 1.2 People

| Name | Role | Contact | Notes | Source |
|---|---|---|---|---|
| **Maxime Durupt** | Cofondateur · technique/projet | maxime@apx-advisory.com · 07 57 94 72 90 | Julian's main interlocutor. Writes client workshop syntheses. Signs the P&P proposal ("Préparé par APX Advisory — Maxime Durupt"). | `Agents/state.json`; `Resources/04-structured/specs-candidates/APX_CONTEXT.md`; `Resources/LexCore_Devis_PhilippePartners.docx` |
| **Lucia Nakamoto** | Cofondatrice · commercial | nakamoto@apx-advisory.com | Owns sales, client RDVs, decks. Onboarded Julian. Produced the Syllogisme AI + UC02 Veille specs. | `Agents/state.json`; `Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md` |
| **Julian Talou** | Freelance AI architect & developer (APX-Advisory's execution capacity) | julian@apx-advisory.com | Onboarded 2026-04-17, confirmed 2026-04-20 after Lucia's pitch, committing to "un MVP+ en quatre semaines". ~50% of his bandwidth on APX. | `Resources/04-structured/specs-candidates/APX_CONTEXT.md`; `Agents/recaps/2026-04-28-cowork-session-1.md` |

> ⚠️ **Conflict/staleness:** `Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md` refers to a review meeting with "Lucia"; `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` is titled "Brief Réunion **Lucia**" but its body names participants "Toi + **Lucio** (possiblement Lucia/Maxime en async)". Sources do not establish whether "Lucio" is a third person or a typo for Lucia.

### 1.3 Commercial model (APX → client)

| Dimension | Rule | Source |
|---|---|---|
| Unit of sale | **Forfait par use case** (fixed price per use case) | `Agents/state.json` |
| Refused explicitly | `no_tjm: true`, `no_licenses: true`, `no_subscription: true` — no day rate, no licences, no subscription | `Agents/state.json` |
| Target price | **30–40 k€ per use case** | `Agents/decisions/2026-04-28-modele-facturation.md`; `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| Milestones | M1 Cadrage (S1-S2) · M2 Dev Core (S2-S3) · M3 Intégration & Tests (S3-S4) · M4 Livraison & Formation (S5-S6) | `Agents/state.json` |
| Payment rule | "Mn payé à validation de M(n-1)" — client pays milestone n only after validating n-1 | `Agents/state.json` |
| Milestone weights | M1 25% · M2 35% · M3 25% · M4 15% | `Agents/decisions/2026-04-28-modele-facturation.md`; `Resources/03-distilled/2026-05-04-P-and-P-devis-blocker.md` |
| Anti-scope-creep clause (client-facing) | "Aucun dépassement budgétaire silencieux : toute dérive déclenche un ajustement de périmètre discuté" | `Resources/LexCore_Devis_PhilippePartners.docx` |
| Post-delivery | 30 days support included from go-live; source code handed over at final delivery | `Resources/LexCore_Devis_PhilippePartners.docx` |

> ⚠️ **Conflict/staleness — milestone weights:** the 25/35/25/15 split above is contradicted by the two actual client-facing proposals, which both use **30 / 35 / 25 / 10**: `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` (§8.2) and `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` (§10.2, "M1 signé : 30% … M4 livré : 10%"). Additionally the RMT ODJ lists per-phase prices (M1 5 000 € / M2 20 000 € / M3 7 500 € / M4 7 500 € = 40 000 €) which are **internally inconsistent** with its own 30/35/25/10 schedule (12 000 / 14 000 / 10 000 / 4 000 €).

### 1.4 What APX refuses to sell / do

- No TJM, no licences, no subscription (`Agents/state.json`).
- **No fine-tuning on client data** — "RAG strict, jamais de fine-tuning" (`Agents/state.json`). In the P&P proposal fine-tuning is explicitly *out of scope*, offered only as a post-delivery evolution "après accumulation de 200+ syllogismes validés par type d'acte" (`Resources/LexCore_Devis_PhilippePartners.docx`).
- No SaaS white-label deployment for these clients: Vercel + Neon + Qdrant Cloud is listed and **rejected** — "Exclu par le barreau du Luxembourg" for P&P, "non conforme au secret professionnel" for RMT (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md`).
- No automated legal decision — "l'outil reste assistif : la décision juridique appartient toujours à l'avocat" (`Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx`).
- No cross-client reuse of client data / few-shot examples — "clause contractuelle interdisant à APX toute utilisation des données pour améliorer ses propres modèles" (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §8.1).
- OpenAI excluded as a provider — "pas de DPA EU satisfaisant"; Google Vertex AI evaluated and rejected on data residency (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §7.2).

### 1.5 Julian → APX contracting (freelance layer)

| Dimension | Position | Status | Source |
|---|---|---|---|
| Model | Forfait = **50% of the APX client invoice** per use case, paid on the same 4 milestones (25/35/25/15) | **Not signed.** "pré-décidé Julian · à négocier avec Maxime" | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Overrun backup | TJM cap **900 €/day** for scope explicitly validated by Julian by email | proposed | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Corrective maintenance | 30 days post-delivery included in the forfait | proposed | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Revenue envelope | 3 use cases × 50% → **45 k€ floor / 60 k€ ceiling over 8 weeks** (vs 31–36 k€ on a pure TJM basis) | estimate | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Zero retention on Julian's machine | No client data on his workstation except synthetic/anonymised samples; works remote on client infra via VPN/SSH | proposed clause | `Agents/decisions/2026-04-28-modele-facturation.md` |
| IP clause wanted | Code belongs to APX/clients; Julian may reuse generic architectural patterns (no content) | proposed | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Non-compete wanted | Limited to RMT and P&P only, not the whole legal sector | proposed | `Agents/decisions/2026-04-28-modele-facturation.md` |
| Open negotiation points | Does Maxime accept 50% (or 40%/60%)? Who notifies milestone validation → Julian payment? Should UC02 Veille drop to 25% because it is shorter? | open | `Agents/decisions/2026-04-28-modele-facturation.md` |

> ⚠️ **Conflict/staleness:** the 45–60 k€ figure in the ADR is restated as "45–72 k€ pour 2 mois (3 use cases)" in `Agents/recaps/2026-04-28-cowork-session-1.md` and `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md`. Sources do not reconcile the ceiling (60 k€ vs 72 k€).
> ⚠️ **Staleness risk:** the whole 50% calculation assumes 30–40 k€/use case. The signed-off RMT proposal is **22 000 € HT** (§2.5), which would mechanically halve the RMT slice.

---

## 2. Client 1 — Cabinet RMT (Paris)

### 2.1 Identity & domain

| Field | Value | Source |
|---|---|---|
| Project id / label | `rmt` — "Cabinet RMT — Triage de masse documentaire" | `Agents/state.json` |
| Domain | Contentieux commercial et pénal (commercial and criminal litigation) | `Agents/state.json` |
| Status | `discovery_done` (discovery workshop 2026-04-27) | `Agents/state.json` |
| Product name | "CPC-145 / Data Corpus Manager" — trademark filing in progress by APX | `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §12.4 |
| Proposal ref | APX-RMT-CPC145-MVP-2026-05, v1.0, dated **2026-05-06** | `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` |

### 2.2 Validated use case

"Triage automatisé de masses documentaires" — automated triage of document masses, across three recurring scenarios (`Agents/state.json`; `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §1):

1. **145 CPC** — *ordonnance 145 CPC* / *saisie in futurum* (ex parte court order authorising a surprise seizure of evidence at the opponent's premises); the seized mass must be triaged within a few days. Here *cotes* (exhibit reference numbers) reflect an internal thematic classification.
2. **Procédures pénales** (criminal instruction) — inbound flows on DVD from the *greffe* (court registry) or via the **Plex** network; pieces numbered by *cote* according to the investigating judge's *diligences*, not chronologically.
3. **Contentieux commercial classique** — typically **1 500 to 2 000 heterogeneous pieces**, mostly `.msg` emails, to characterise specific grievances.

**The pain being replaced:** trainees and juniors hand-build a *tableau de synthèse* piece by piece (cote / date du document / nature / intervenants / contenu sommaire / thématique). "Le risque est double — passer à côté d'une pièce déterminante, ou rejeter par erreur une pièce qui aurait dû être versée au dossier. Ce dernier risque est juridiquement le plus grave : une pièce mal rejetée ne sera jamais réintroduite." (`Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §1)

**Claimed ROI:** triage/classification of 200–500 docs in 4–6 h vs 3 days manually; KYC/AML 1–2 h vs 4–6 h (`Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md`).

### 2.3 Named stakeholders and the specific requirement each insists on

| Person | Role | Non-negotiable requirement they own | Source |
|---|---|---|---|
| **Emmanuel** | Avocat senior · lead of the discovery workshop · auditor | "Auditabilité non-négociable, échantillonnage aléatoire" — he must be able to draw N random pieces, see the full reasoning behind each AI classification, and correct it. He is the one who will validate the tool. | `Agents/state.json`; `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| **Éléonore** | Avocate (UX voice) | "Édition cellule par cellule, pas de régénération destructive du tableau" — surgical cell editing; a correction must never rewrite the whole table. | `Agents/state.json`; `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` |
| **Karine** | Pénaliste · *tableau de procédure* | (role only; no distinct requirement recorded) | `Agents/state.json` |
| **Noémie** | Contractuel · "forme + fond" (form and substance) | (role only; no distinct requirement recorded) | `Agents/state.json` |
| **Pierre** | Co-réflexion interne RMT | (role only) | `Agents/state.json` |
| **Maître Sorlin** | Direct contact — sorlin@rmt.fr | Named as the owner of the *audit aléatoire* requirement in the commercial proposal: "l'audit aléatoire exigé par Me Sorlin"; "Module d'audit aléatoire : Me Sorlin tire N pièces au hasard". | `Agents/state.json`; `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §1, §6bis.5 |

> ⚠️ **Conflict/staleness — Emmanuel vs Me Sorlin:** `Agents/state.json` lists **Emmanuel** and **Maître Sorlin** as two separate `key_contacts`, and attributes the random-audit requirement to Emmanuel. But `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` names the workshop participant "**Emmanuel Sorlin** (RMT)", `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` says "Emmanuel Sorlin (lead avocat senior)", and the 2026-05-06 proposal attributes the same requirement to "Me Sorlin". They are almost certainly **one person, Emmanuel Sorlin**, double-counted in state.json. Do not treat them as two stakeholders without confirming.

Workshop attendance 2026-04-27 ("RMT <> APX : Projet d'Agent IA"): Emmanuel, Éléonore, Pierre, Karine, Noémie (`Resources/04-structured/specs-candidates/APX_CONTEXT.md`). Maxime's synthesis notes reached Julian on the morning of 2026-04-28 (`Agents/recaps/2026-04-28-cowork-session-1.md`).

### 2.4 Expected deliverables

From `Agents/state.json` (`deliverables_attendus`):
1. Tableau de synthèse — columns **cote / date / nature / intervenants / contenu / thématique**
2. Q&A in natural language over the pieces
3. Tri **rebut / pertinent / à revoir** (discard / relevant / to review) with **reversible** justification
4. Random-audit tool for Emmanuel

Extended MVP scope from the 2026-05-06 proposal (`Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §1, 16 functions total):
- Native multi-format ingestion **preserving `.msg` without prior PDF conversion** — "point de friction explicite remonté par le cabinet"
- Ingestion adapter for **DVD / USB key / hard disk / Plex network**
- Tri pertinent/rebut with confidence score + short displayed justification
- Dynamic multi-thematic classification: free grid, **2 to 25 thématiques per dossier**, evolving mid-procedure
- Metadata extraction: **cote (explicitly dissociated from document date)**, nature, intervenants, dates, amounts, references
- Cell-by-cell editable tableau de synthèse, no global rewrite on correction (Éléonore)
- Q&A including relationships between people (graph relations)
- Random audit module (Me Sorlin)
- Excel / Word / PDF exports
- **Optional post-MVP upsell:** "analyse stratégique syllogistique (ce qu'une pièce dit pour ou contre le client)" — explicitly *not* in MVP scope. Originally spotted by Maxime in his 2026-04-28 email (`Resources/04-structured/specs-candidates/APX_CONTEXT.md` §7).

### 2.5 Commercials (RMT)

| Item | Value | Source |
|---|---|---|
| Budget MVP | **22 000 € HT** ("~30 % de réduction vs un projet from scratch grâce au socle LexCore") | `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §1 |
| Effort | 17,5 j-h brut → **~16 jours-homme** effective (vs ~28,5 j-h from scratch = ~44% reduction) | ibid. §2, §16.4 |
| Delay | **5 weeks firm, 8 calendar weeks** including UAT/stabilisation margin | ibid. §1, §8.1 |
| Milestones | M1 Cadrage & socle (S1) 30% · M2 Tri & classification (S2-S3) 35% · M3 Tableau, audit, Q&A (S4) 25% · M4 Chronologie & livraison (S5) 10% | ibid. §8.2 |
| Variable LLM cost | ~3 to 5 € per dossier of 200–500 pieces; 145 CPC standard (500) 8–12 €; pénal lourd (2 000) 32–48 €; commercial type (1 700 emails) 27–41 € | ibid. §14.2 |
| Recurring infra | 0 € OPEX on existing on-prem server, or 250–350 €/month in dedicated sovereign cloud; ~100–250 €/month API for 5 active dossiers | ibid. §14.2 |
| Data residency | 100% EU — deployment on RMT infrastructure (on-premise or dedicated sovereign cloud) | ibid. §1 |
| Reuse economics | ~6 000 € HT saved (5–6 j-h) via LexCore reuse; components split R (reused as-is, ~10,5 j-h saved) / A (adapted, ~2,0 j-h) / N (new for RMT, ~9,5 j-h) | ibid. §8.3, §16 |

> ⚠️ **Conflict/staleness — RMT price:** three figures coexist. (a) 30–40 k€/use case generic (`Agents/decisions/2026-04-28-modele-facturation.md`). (b) **40 000 € HT** with a detailed M1 5k / M2 20k / M3 7,5k / M4 7,5k breakdown over 6 weeks (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §10.2, dated 2026-05-05) — also echoed as "RMT : 40k€ HT aussi" in `Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md`. (c) **22 000 € HT** over 5–6 weeks in the actual client proposal one day later (`Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx`, 2026-05-06). The 2026-05-06 figure is the latest and is the one in the client-facing document, but no source records the decision to halve it.

Out-of-scope items quoted at TJM 900 €/day in the earlier ODJ: CSIP connector, veille réglementaire, multi-dossier simultaneity, GraphRAG for >10k docs (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §10.2). Also noted there: "TVA non applicable (prestataire APX = auto-entrepreneur sous régime de la franchise)".

### 2.6 Volumes & formats

| Aspect | Detail | Source |
|---|---|---|
| Typical volume | "1700+ docs/dossier (cas extrême), majoritairement .msg" | `Agents/state.json` |
| By dossier type | 145 CPC: 200–500 pieces · Pénal: 500–2 000 · Commercial: 1 500–2 500 | `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §14.1 |
| Average document | 2–4 pages ≈ 1 500–2 000 tokens | ibid. |
| Supported | `.msg` (native, never converted), native PDF, `.docx`, `.xlsx`, archives `.zip`/`.rar` (auto-extracted), DVD/USB/hard disk mounted read-only | `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §6.3 |
| Degraded | Scanned PDF (OCR needed), images jpg/png (OCR only), `.doc`/`.xls` legacy (LibreOffice conversion), `.eml` (script conversion) | ibid. |
| Not supported | `.p7s` signatures, password-encrypted files | ibid. |
| Physical inbound | DVD from the *greffe*, Plex network, USB keys, download links, photos | `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` |

### 2.7 Open blockers & awaited assets (RMT)

Still open as of the latest standup (`Agents/recaps/2026-05-25-monday-standup.md`) and re-confirmed as unresolved on 2026-06-02 (`Agents/mvp-updates/2026-06-02T07-42+0000-update.md`):

| Awaited asset | Owner | Status | Source |
|---|---|---|---|
| Anonymised sample of **50–100 `.msg`** | RMT (via Maître Sorlin / Maxime) | not received | `Agents/state.json`; `Agents/mvp-updates/2026-06-02T07-42+0000-update.md` |
| One anonymised **ordonnance 145** | RMT | not received | `Agents/state.json` |
| One **gold-standard** tableau from a past dossier (50 docs) | RMT | not received | `Agents/state.json`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §10.1 |
| 2–3 examples of thematic breakdown / validated *grille thématiques* | Emmanuel | not received | `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| **NDA mutuel + DPA** signed | RMT legal | not signed | `Resources/04-structured/specs-candidates/APX_CONTEXT.md`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §7.1 |
| Hosting decision (cabinet infra vs EU cloud) | RMT + APX | undecided | `Agents/state.json`; `Agents/recaps/2026-05-04-monday-standup.md` |

Escalation signal: "**Silence client RMT depuis 16 jours** — pas de retour sur les trois livrables attendus. À relancer." (`Agents/recaps/2026-05-14-cron-brief.md`, dated 2026-05-14). No source records the samples ever arriving; the last mention (2026-06-02) still says "client samples from RMT (50–100 .msg, ordonnance 145) … are still pending" (`Agents/mvp-updates/2026-06-02T07-42+0000-update.md`).

---

## 3. Client 2 — Philippe & Partners (Luxembourg)

### 3.1 Identity & domain

| Field | Value | Source |
|---|---|---|
| Project id / label | `pp` — "P&P Luxembourg — LexCore IA + Veille" | `Agents/state.json` |
| Domain | Droit des assurances, arbitrage (insurance law, arbitration) | `Agents/state.json` |
| Standing | "cabinet d'avocats de premier plan, reconnu **Legal 500 2026** en Assurances, Arbitrage et Dispute Resolution, avec **sept bureaux** couvrant la Belgique, le Luxembourg, la France, l'Allemagne et le Royaume-Uni" | `Resources/LexCore_Devis_PhilippePartners.docx` |
| Status | `deck_sent` (deck presented 2026-04-24) | `Agents/state.json` |
| Proposal ref | **APX-2026-PP-LEXCORE**, v1.0 Confidentiel, "Mai 2026", prepared by Maxime Durupt | `Resources/LexCore_Devis_PhilippePartners.docx` |

### 3.2 Named stakeholders

| Person | Role | Requirement / note | Source |
|---|---|---|---|
| **Maître Gouden** | Partner · **décideur** (decision-maker) | Attended the 2026-04-24 RDV; validated the two use cases. Drafting-style reference: "Maître Gouden = style direct". The *devis* must be addressed to him. | `Agents/state.json`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md`; `Resources/03-distilled/2026-05-04-P-and-P-devis-blocker.md` |
| **Jérôme** | Collaborateur IT interne, **néerlandophone** (Dutch-speaking) | Client-side technical referent. Owns the CSIP API documentation question and the deployment-option checklist (matières per avocat, dedicated mailbox, alert format/frequency, UC02 combined with UC01 or phase 2, deployment option A or B). | `Agents/state.json`; `Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md` |

### 3.3 Validated use cases

**UC01 — LexCore IA** (`Agents/state.json`): "RAG sur 15-20 ans CSIP + Outlook, recherche, génération d'actes au style maison" (RAG over 15–20 years of the CSIP case-management corpus plus Outlook, search, generation of *actes* in the firm's house style).

Scope detail (`Resources/LexCore_Devis_PhilippePartners.docx`; `Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md`):
- **Ingestion:** CSIP REST connector (`GET /api/cases`, `/api/documents?case_id=`, `/api/files/{id}`), formats PDF native + scanned, `.docx`, `.msg`, `.eml`, images, `.zip`. OCR automatic. Deduplication by fingerprint. CSIP tree structure preserved (Client → Dossier → Documents). **"Ne JAMAIS forcer conversion .msg → PDF" (pain point client).**
- **Outlook Microsoft Graph connector:** scoped **out of the MVP**, deferred to a later module (OAuth2 Azure AD, delta sync).
- **Intelligence:** triage pertinent/rebut with displayed justification; multi-label thematic classification over the firm's practices (Assurances, Arbitrage, Bancaire, Énergie, Corporate, Fiscal, Immobilier…); metadata extraction (parties, dates, cotes, montants, jurisprudence & doctrine references).
- **Moteur de syllogisme juridique** — structured three-part legal reasoning: **Majeure** (applicable rule) → **Mineure** (qualification of facts) → **Conclusion**, each assertion sourced to the exact internal corpus passage. Output constrained by a **forced JSON Schema** (Lucia's spec), e.g. `{syllogisme_id, type_acte, majeure{regle, source_interne, source_externe}, mineure{faits, qualification}, conclusion{argument, validé_par, confiance}}`.
- **Rédaction assistée:** *assignations*, *conclusions*, mémos, contracts, drafted from the firm's own validated *actes*. "Le système n'invente aucune règle de droit : il assemble uniquement à partir de vos actes validés et des sources citées."
- **Templates:** 20 representative Word templates, **double colonne FR/NL**, house styles, 95% conformity target; variables `[client] [contrepartie] [montant] [juridiction]`; style learning per lawyer from 3–4 of their own documents.
- **Interface:** cell-by-cell editable tableau de synthèse accessible from all offices; Word/Excel/PDF export; **tirage d'audit** (any partner can audit N pieces and see the full reasoning); complete immutable audit trail.

**UC02 — Veille réglementaire** (`Agents/state.json`): "Legilux, EUR-Lex, CSSF, CNPD, monitoring 24/7". Expanded in the proposal to **CSSF, EIOPA, EBA, EUR-Lex, CAA Luxembourg, ESMA, Legilux, gouvernement.lu** (`Resources/LexCore_Devis_PhilippePartners.docx`).
- Weekly structured briefing by email to the relevant partners, filtered per practice/per lawyer profile; immediate alerts for binding texts entering into force < 6 months; Q&A over the veille corpus **isolated from the internal corpus**.
- Claimed value: "~150 heures de lecture manuelle évitées par associé spécialisé et par an".
- Ingestion of paid-publisher newsletters (Legitech, Larcier…) via a **dedicated mailbox** (e.g. `veille-ia@philippelaw.eu`) — a deliberate workaround for publishers with no API.
- Technical stack specified by Lucia: Airflow DAGs per source (alt. n8n, Celery+Redis), Scrapy for structured official sites (Legilux, CAA, CSSF), Playwright for JS pages, `zeep` for the EUR-Lex SOAP API, `feedparser` for RSS, Unstructured.io + trafilatura for extraction. **Legilux = HTML scraping (no API); EUR-Lex = official free SOAP/REST API.** Qdrant collections split per source (`veille_eurlex`, `veille_legilux`, `veille_caa`, `veille_cssf`, `veille_newsletters`, `syllogisme_interne`). Alert template with 🔴 Critique / 🟡 À surveiller / 🟢 Pour info; immediate alert for critical + weekly digest Monday 08:00. (`Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md`)
- Source→practice mapping: EUR-Lex (Solvabilité II, IDD) & EIOPA → Droit des assurances; EUR-Lex arbitrage + UNCITRAL → Arbitrage; Legilux → all practices; CSSF → Corporate/bancaire. (ibid.)

> ⚠️ **Conflict/staleness — is UC02 in or out?** `Agents/state.json` lists Veille as a validated use case. `Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md` §Module 4 says "**HORS MVP** … Ne PAS inclure dans MVP (risque de délayage)", post-MVP M5–M6. The later client proposal reinstates it as **M5, weeks 9–10**, "indépendant du MVP principal" (`Resources/LexCore_Devis_PhilippePartners.docx`). Treat UC02 as a *separately sequenced* module, not as MVP scope.

### 3.4 Existing stack & firm-side specifics

| Item | Value | Source |
|---|---|---|
| Existing stack | **CSIP** (case management + DocuSign), Microsoft 365, minimal SharePoint, DeepL | `Agents/state.json` |
| Bilingual requirement | FR/NL in **double colonne** | `Agents/state.json` |
| Template conformity | "Templates 95% conformité" | `Agents/state.json` |
| Headcount / licences | "30 avocats, **pas de licences supplémentaires**" | `Agents/state.json` |
| Style learning | Per-lawyer writing style learned from their mailbox | `Agents/state.json` |
| Corpus size | **60 000 documents / 20 ans** (proposal); "15-20 ans CSIP + Outlook" (state.json) | `Resources/LexCore_Devis_PhilippePartners.docx`; `Agents/state.json` |
| Users | **25 avocats — 7 bureaux** (proposal) | `Resources/LexCore_Devis_PhilippePartners.docx` |

> ⚠️ **Conflict/staleness — firm size:** `Agents/state.json`, `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` and `Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md` all say **~30 avocats**. The May 2026 client proposal says **25 avocats, 7 bureaux** (`Resources/LexCore_Devis_PhilippePartners.docx`). The monthly cost model is built on **25 avocats × 5 dossiers/month**.
> ⚠️ **Conflict/staleness — corpus volume:** "Volume CSIP exact (Go ou nombre de dossiers)" is listed as an *open blocker* in `Agents/state.json`, yet the proposal already commits to indexing **60 000 documents** in M1. Sources do not record where the 60 000 figure came from or whether the client confirmed it.

### 3.5 Commercials (P&P)

| Item | Value | Source |
|---|---|---|
| Total duration | **10 semaines** (LexCore M1–M4 = 8 weeks + Veille M5 = 2 weeks); safety margin communicated as 10 calendar weeks for LexCore alone | `Resources/LexCore_Devis_PhilippePartners.docx` |
| Milestones | M1 Infra & base documentaire (S1–3, 60k docs indexed) · M2 Intelligence & rédaction (S3–5) · M3 Interface & UAT (S6–7) · M4 Mise en production (S8, support 30 j) · M5 Veille UC02 (S9–10) | ibid. |
| Development price | **Not stated in the *devis* document.** The doc only prices *recurring* monthly costs, explicitly "distincts du forfait de développement". | ibid. |
| Recurring monthly (post-M4) | Ingestion new dossiers 475–950 € · Q&A interactif 18–25 € · Veille 50–80 € · OVHcloud infra 200–350 € → **~750 € to ~1 400 €/month** (low = 200 pieces/dossier, high = 400) | ibid. |
| Client prerequisites | 50–100 annotated anonymised documents per practice for classifier calibration; a technical referent + a business referent; 4–6 h of UAT availability in weeks 6–7; dedicated veille mailbox + publisher newsletter list | ibid. |
| Explicit exclusions | Fine-tuning (post-delivery evolution only); integration with an existing case-management system (to be studied in cadrage); on-premise physical servers (available "en phase 2 sur demande") | ibid. |

Earlier internal figures, superseded but recorded: 37,5 days × 900 €/day = **33 750 € HT** + ~800 €/month infra, 6 weeks (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md`); and "**40k€ HT** + 800€/mois infra + 1k€/mois LLM" (`Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md`). A third internal version: 24 j-h brut → 16–20 j-h effective, 8 weeks firm / 10 with stabilisation margin, ~3–4 €/dossier of 200 pieces, OVHcloud (`Resources/04-structured/proposition_luxembourg_mvp.txt`, "Proposition technique MVP LexCore Luxembourg", 2026-05-05, v1.0).

> ⚠️ **Conflict/staleness — P&P price:** 33 750 € (ODJ 05-05) vs 40 000 € (message to James, 05-05) vs **absent** from the client-facing *devis*. There is no source that states the final P&P development forfait. This is a material gap for planning.

### 3.6 Open blockers & awaited assets (P&P)

| Blocker / asset | Owner | Status | Source |
|---|---|---|---|
| **Devis not sent to Maître Gouden** — severity `block`, priority `urgent` | Maxime + Lucia | open as of 2026-05-05; expected artifact `devis-p-and-p-001-signed.pdf` | `Resources/04-structured/p-and-p-devis-status.json`; `Resources/03-distilled/2026-05-04-P-and-P-devis-blocker.md` |
| **CSIP API documentation** — to be obtained via external IT provider | Jérôme / external IT provider | open | `Agents/state.json`; `Agents/recaps/2026-05-25-monday-standup.md` |
| Contact for the external IT provider | Lucia / Maxime | open | `Agents/state.json` |
| Exact CSIP volume (GB or number of dossiers) | P&P | open | `Agents/state.json` |
| **20 representative Word templates** (FR/NL double column) | Maître Gouden | open | `Agents/state.json`; `Agents/mvp-updates/2026-06-02T07-42+0000-update.md` |
| Microsoft Graph access (scopes `Mail.Read`, `Files.Read.All`) | Jérôme / Azure AD app registration | open | `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| List of retained public veille sources + practice/discipline per lawyer | Jérôme | open | `Agents/state.json` |
| **DPA not signed** — blocks access to real data | P&P legal | open | `Resources/04-structured/specs/validated/requirements.json` (`constraints`); `Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md` |
| No response from Maître Gouden or Jérôme since the deck | — | noted 2026-05-04 | `Agents/recaps/2026-05-04-monday-standup.md` |

`Resources/04-structured/ProjectMemory/task_queue.json` records the blocked set as `["csip-api-connection", "word-templates-integration", "dpa-production-data"]`, with the only actionable task being "Setup Docker minimal pour demo - contournement bloqueurs".

> ⚠️ **Terminology warning:** several agent-generated artefacts expand "P&P" as "**Procédures et Protocoles**" and call it a *module* (`Resources/04-structured/p-and-p-devis-status.json`; `Resources/03-distilled/2026-05-04-P-and-P-devis-blocker.md`). Everywhere else P&P means **Philippe & Partners**, the firm. Treat "module P&P (Procédures et Protocoles)" as an agent mislabel, not a real product line.

---

## 4. Other prospects / pipeline

Pipeline confirmed at **4 active prospects** on 2026-05-13: Philippe & Partners, RMT, Cabinet italien #1, Cabinet italien #2 (`Resources/04-structured/commercial-pipeline-status.json`; `Resources/03-distilled/2026-05-13-pipeline-demo-update.md`).

| Prospect | What is known | Status / date | Source |
|---|---|---|---|
| **Cabinet italien #1** | Part of the confirmed pipeline; RDV "lundi 11 mai". No scope, contact or constraint recorded anywhere. | RDV 2026-05-11 | `Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json` |
| **Cabinet italien #2** | Same stack as Luxembourg: **syllogisme IA + veille on Italian sources**. **15 years of documents (~60k) on a physical server in Italy** — no cloud. Data retrieval is the major constraint (remote export, VPN, or on-site intervention). Lucia presents; Julian on technical support. **Julian in Milan 21–27 June** = window for physical retrieval. No sample corpus provided for Italian-language ingestion testing. | RDV confirmed **2026-06-04 10:00**, owner Lucia | `Resources/04-structured/italian-cabinet-2-status.json`; `Resources/03-distilled/2026-05-11-italian-cabinet-rdv-summary.md`; `Resources/01-raw/2026-05-11T15:24:00+02:00--APX--whatsapp-italian-cabinet-rdv.json` |
| **Strelia — Maître Etienne De Crépy** (Luxembourg, M&A) | RDV held **2026-04-22**, Julian invited by Lucia. **No compte-rendu, no notes, no next step on record.** Standing action `doc-rdv-crepy-001` (medium priority, owner Maxime): document the outcome and decide whether to keep or archive the lead. | undocumented since 2026-04-22 | `Resources/04-structured/p-and-p-devis-status.json`; `Resources/03-distilled/inbox-summary-2026-05-05.md`; `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| **Marie, avocate (Bordeaux)** | New lead, introduced via "Sully". Classified **NOISE** for MVP purposes — "commercial follow-up only (RDV démo, pitch, remerciement). No product requirement/constraint/bug." | signal dated **2026-06-03** | `Agents/mvp-updates/2026-06-04T19-35+0000-update.md`; `Agents/mvp-updater-state.json` |
| **ANFR (frequency regulator)** context | Not a named prospect — a **mockup variant**: `maquette_anfr_v2.html` (149 KB, sent 2026-05-13 19:59), "mockup spécifique ANFR (régulateur fréquences)". Listed as an available commercial asset. | asset, not a deal | `Resources/04-structured/commercial-pipeline-status.json`; `Resources/01-raw/2026-05-13T13:52:00+02:00--APX--whatsapp-mockups-lexoria-anfr.json` |

**Commercial assets:**
- **Lexoria** (`Lexoria.html`, 86 KB, sent 2026-05-13 13:52) — generic, unbranded client-facing demo mockup for the *syllogisme IA + veille* pair, "vibecodé rapidement". **Approved by Lucia as the demo base**, to be refined per feedback. Lucia: "Pour un mock up à faire voir aux clients je pense que ça sera déjà sympa 😁. Ah affiner selon les besoins. Le mock up de Philippe etait aussi super bien." Julian's note: "Lexoria = nom de marque retenu pour la maquette démo générique. **À confirmer si c'est le nom produit définitif.**" (`Resources/01-raw/2026-05-13T13:52:00+02:00--APX--whatsapp-mockups-lexoria-anfr.json`; `Resources/04-structured/commercial-pipeline-status.json`)
- **Visual POC** delivered 2026-04-28 — `Code/index.html`, single-file React + Tailwind CDN, 2 014 LOC, 5 screens (Tableau de bord, Import & Triage, Tableau de synthèse, Recherche sourcée, Génération d'acte) + a global **Audit drawer**. Scenario "Affaire Tilburg / 145 CPC", 15 mocked pieces, 6 thématiques, 2 pre-written chat conversations. **Everything mocked, no LLM call, no real data.** Each screen maps to a named requirement: cell editing → Éléonore, sourced citations → Maître Gouden, audit drawer → Emmanuel. (`Agents/state.json` `deliverables_log`; `Agents/recaps/2026-04-28-cowork-session-1.md`)

---

## 5. Commercial state & blockers as of the latest dated source

**Latest commercially-meaningful source: 2026-05-14** (`Resources/04-structured/commercial-pipeline-status.json`, `updated_at: 2026-05-14T19:38:54+02:00`). **Latest source of any kind: 2026-06-20** (`Agents/mvp-updates/2026-06-20T10-20+0200-suggestions.md`), which is engineering-only and reports **0 actionable external signals**.

### 5.1 Quotes pending / decisions awaiting the client

| Item | State | Source |
|---|---|---|
| **P&P devis to Maître Gouden** | Drafted as `LexCore_Devis_PhilippePartners.docx` (May 2026, unsigned — signature blocks empty for both APX and P&P). Last recorded status: `devis_pending`, blocker `devis_not_sent`, severity `block`. No source confirms it was sent. | `Resources/LexCore_Devis_PhilippePartners.docx`; `Resources/04-structured/p-and-p-devis-status.json` |
| **RMT devis** | Technical proposal dated 2026-05-06 with 22 000 € HT. No source records sending, acceptance, or signature. | `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` |
| **Devis deadline** | "Deadline devis : **Vendredi 09/05/2026**" — no source confirms it was met. | `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` §7 |
| **Strelia lead** | Awaiting a decision to reactivate or archive. | `Resources/03-distilled/inbox-summary-2026-05-05.md` |
| **Julian → APX convention** | To be signed **before M1 starts**. Not signed. | `Agents/decisions/2026-04-28-modele-facturation.md` |
| **NDA + DPA** (both clients) | Not signed. Blocks access to real data on both sides. | `Resources/04-structured/specs/validated/requirements.json`; `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |

### 5.2 Cross-cutting blockers

1. **No test documents from any prospect.** "Pas de documents de test partagés par les prospects" is the single `open_blockers` entry in `Resources/04-structured/commercial-pipeline-status.json` (2026-05-14). "Lucia demandera au prochain RDV." Still true on 2026-06-02 (`Agents/mvp-updates/2026-06-02T07-42+0000-update.md`) — which is why synthetic mock corpora (`data/mock/documentation|syllogisme|veille`) were generated instead.
2. **Julian ↔ APX billing model unsettled** — "reste à arbitrer entre TJM pur … vs forfait pourcentage … Impacte la facturation prochaine" (`Agents/recaps/2026-05-14-cron-brief.md`).
3. **Strategic focus vs parallel execution — unresolved.** Julian's recommendation to James on 2026-05-05: "**Focus P&P** (client plus gros, specs claires) → mettre RMT en pause jusqu'à mi-août", with delivery mid-July before the summer break and RMT starting mid-August. No source records James's or Maxime's answer. (`Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md`; `Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md`)
4. **Milestone ambition flagged.** "Milestones Lucia validés par Julian le 11 mai **avec réserve sur l'ambition** (10 semaines fixes, Anthropic Sonnet obligatoire)" (`Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json`).
5. **Cadence never started.** Weekly Wednesday-morning 30 min live with Maxime + Lucia and a Friday/Saturday written synthesis were agreed but "Ce rythme n'a pas encore démarré" (`Resources/04-structured/specs-candidates/APX_CONTEXT.md`; `Agents/state.json` `cadence`).
6. **Product ≠ pitch.** As of 2026-06-20 the differentiating **audit trail is still absent from `main`** — `domain/audit/{service,events,models}.py` are 0-byte files; PRs #33 (audit trail) and #34 (Vercel deploy) were both **closed unmerged** on 2026-06-18. `domain/retrieval/` (the cited-answer guarantee) has **zero tests**. (`Agents/mvp-updates/2026-06-20T10-20+0200-suggestions.md`; `Agents/mvp-updates/2026-06-16T10-10+0200-suggestions.md`)
7. **Standing honesty guardrail.** Action item AI-005: "Ne pas présenter `legal-rag-core` comme MVP LexCore complet tant que triage, syllogisme, audit trail, exports et OCR réel ne sont pas implémentés et testés." (`Resources/04-structured/specs/validated/task.json`)

### 5.3 Dated calendar markers found in sources

| Date | Event | Source |
|---|---|---|
| 2026-04-22 | RDV Maître De Crépy (Strelia) — undocumented | `Resources/04-structured/specs-candidates/APX_CONTEXT.md` |
| 2026-04-24 | RDV Maître Gouden (P&P) — 2 use cases validated | `Agents/state.json` |
| 2026-04-27 | RMT discovery workshop | `Agents/state.json` |
| 2026-04-28 | Visual POC delivered; 4 ADRs written | `Agents/state.json` |
| 2026-05-05/06 | Meeting to define the joint devis; technical ODJs produced | `Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` |
| 2026-05-09 | Stated devis deadline | ibid. |
| 2026-05-11 | Cabinet italien #1 RDV; Lucia's milestones validated with reservation | `Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json` |
| 2026-06-04 10:00 | Cabinet italien #2 RDV (owner Lucia) | `Resources/04-structured/italian-cabinet-2-status.json` |
| 2026-06-15 | `deadline_target` for milestone "M1 (Infrastructure + Ingestion)" of `apx-luxembourg-lexcore-mvp` | `Resources/04-structured/ProjectMemory/current_goal.json` |
| 2026-06-21 → 27 | Julian in Milan — possible physical data retrieval for Cabinet italien #2 | `Resources/04-structured/italian-cabinet-2-status.json` |
| "mi-juillet" | Proposed P&P delivery date (before summer break) if focus strategy is adopted | `Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md` |

---

## 6. Architecture / stack / billing decisions already locked (one subsection per ADR)

Four ADRs exist, all dated **2026-04-28** (`Agents/decisions/`).

### 6.1 ADR — Noyau technique commun pour RMT et P&P
`decisions/2026-04-28-architecture-noyau-commun.md` · type: architecture · status: "décidé · à valider avec Maxime en hebdo"

**Decision.** Option **C — common core + per-client composition**. Three repos:
```
legal-rag-core/   ← library, semver, tested, no client logic
apx-rmt/          ← composes the core: connectors + vocab + RMT UI
apx-pp/           ← composes the core: connectors + vocab + P&P UI
```
Core owns: ingestion parsers (.msg/.pdf OCR/.docx/.xlsx/.pptx/images), adaptive semantic chunking, Qdrant indexing + BGE-M3 embeddings (option Mistral-embed), RAG pipeline with provenance + top-k re-ranking, LLM adapter layer, encrypted append-only audit log, `.docx`/`.pdf` generation respecting templates, RBAC schema with per-lawyer/team/firm scopes. Each client app owns: connectors, business schema (Pièce/Cote/Thématique for RMT, Document/Clause/Template for P&P), prompt vocabulary, bespoke UI (table-first vs chat-first), commercial configuration.

**Reasoning.** ~80% of the plumbing converges between the two clients; the diff is connectors, business vocabulary, UI emphasis and data model. Option A (two codebases) = massive duplication and double technical debt. Option B (one non-modular codebase) = "feature flag spaghetti" and dangerous commercial coupling (one client's bug affecting the other).

**Consequences.** Positive: every core improvement benefits both clients; the 3rd client becomes a 3rd app, not a 3rd codebase; test ROI concentrated on the core; "nous capitalisons sur N cabinets déjà déployés" becomes technically true. Negative: requires stable-API discipline on the core; mandatory semver with apps pinning a version; higher initial setup cost (S1 spent on the core, not directly on a client). Mitigations: start the core genuinely light and extract duplication *after* building both apps; integration tests on fixtures representative of both scenarios; CI tags on the core auto-open a version-bump PR in the apps.

> **Status vs later material:** partially superseded in form. The actual repo built by June 2026 is a **monorepo** `jt33120/apx-platform` containing `packages/legal-rag-core` plus `backend/` and `workers/`, not three separate repos (`Agents/mvp-updates/2026-06-01T20-10+0200-suggestions.md`; `Agents/mvp-updates/2026-06-16T10-10+0200-suggestions.md`). The *principle* (core library + client composition) survives; the three-repo layout does not. The RMT proposal monetises the reuse principle explicitly: R/A/N component split, ~44% effort reduction (`Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx` §16).

### 6.2 ADR — Choix LLM, embeddings, vector DB, hébergement
`decisions/2026-04-28-stack-llm-hebergement.md` · type: technique · status: "pré-décidé · à confirmer avec chaque client"

**Decisions.**
| Layer | Decision | Reasoning |
|---|---|---|
| Default LLM | **Mistral Large** via EU zero-retention API; fallback Claude Sonnet 4.6 on EU endpoints if Mistral underperforms | French company, native EU endpoints, "pas de gymnastique juridique de transfert"; ~3× cheaper than Claude Sonnet 4.6 on input |
| Air-gapped option | Mistral 7B Instruct or Llama 3 8B self-hosted on local GPU (Scaleway L4 or H100) | Absolute isolation; costlier (GPU CAPEX + monitoring OPEX), one notch below on performance |
| Embeddings | **BGE-M3** default; `mistral-embed` for all-Mistral consistency | Runs on CPU at these volumes; zero recurring cost (vs $0.10/M tokens); multilingual out of the box — essential for P&P FR/NL |
| Vector DB | **Qdrant** self-hosted on client infra | Apache 2.0, scales to millions of docs, complex filters, rich payload for RBAC. Weaviate rejected (heavier to deploy), Chroma rejected (less prod-mature). **GraphRAG** layer on top for very large corpora (10k+ docs, criminal instruction) |
| Hosting | 1. **Scaleway sovereign cloud** (FR, SecNumCloud-certified) — recommended default · 2. OVH · 3. Client infra (P&P potentially). Julian's dev box: Scaleway 30 €/month. Client prod: 8–16 vCPU + 32–64 GB RAM, or GPU L4 + 24 GB VRAM air-gapped | per-client decision |
| App stack | Backend **Python/FastAPI**; frontend **Next.js + Tailwind + TipTap** (editable tables, SSR + server auth coherent with RBAC — not a pure Vite SPA); doc templating **python-docx** + WeasyPrint/ReportLab; OCR **Tesseract** local, Mistral OCR or Azure Document Intelligence EU for high precision | ecosystem maturity for parsers; RBAC needs |

**Consequences.** 100% EU stack even in cloud mode; controlled LLM API cost; strong sovereignty sales argument. Trade-off acknowledged: "Mistral Large encore légèrement derrière Claude/GPT-5 sur certains benchmarks de raisonnement complexe — à mitiger via prompt engineering et possibilité de basculer en Claude EU pour tâches sensibles."

> ⚠️ **This ADR is largely SUPERSEDED by May 2026 material.**
> - **Default LLM flipped.** Every May document makes **Claude Sonnet 4.6 on AWS Bedrock `eu-west-1`** the primary and Mistral Large the fallback: `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §3.1, `Resources/03-distilled/mvp-briefs/2026-05-05_odj-luxembourg-syllogisme-mvp.md` §3, `Resources/LexCore_Devis_PhilippePartners.docx` ("Modèle IA principal : Claude Sonnet — AWS Bedrock EU (zero retention)"), `Resources/04-structured/specs/validated/requirements.json` NFR-03. The WhatsApp capture of 2026-05-11 records "**Anthropic Sonnet obligatoire**" as a constraint of Lucia's milestones (`Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json`).
> - **Hosting flipped.** Decision recorded 2026-05-05 by Julian: "Architecture MVP = **cloud OVH** (moins cher qu'AWS). Dockerisation on-premise possible en phase suivante pour déploiement sur serveurs clients." (`Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json`; `Resources/04-structured/commercial-pipeline-status.json`). Codified as NFR-01 "Infrastructure 100% UE (**OVHcloud GRA**)" (`Resources/04-structured/specs/validated/requirements.json`) and sold as "OVHcloud, datacenter Gravelines (France)" (`Resources/LexCore_Devis_PhilippePartners.docx`). Scaleway survives only as an alternative in option tables.
> - **BGE-M3 + Qdrant + FastAPI + Next.js survive unchanged** across all later documents.
> - **Unresolved third option.** `Resources/04-structured/specs/validated/requirements.json` review log flags that several earlier PDFs still cite **OpenRouter** as the MVP gateway, "ce qui reste en conflit avec les docs plus récents orientés zero-retention EU"; action item **AI-006** requires an explicit arbitration before any external promise. Julian's own operating-cost note also lists OpenRouter spend (`Resources/01-raw/briefs/Brief_Reunion_Lucio_2026-05-05.md` §5).

### 6.3 ADR — Modèle de facturation Julian → APX
`decisions/2026-04-28-modele-facturation.md` · type: commercial · status: "pré-décidé Julian · à négocier avec Maxime"

**Decision.** Option **C — hybrid**: forfait-dominant with a TJM backup. Full terms in §1.5 above.

**Reasoning.** Option A (pure TJM 900–1 100 €/day) requires hour tracking, permanent scope negotiation, and sends a bad commercial signal ("incite à tirer le projet en longueur"), misaligned with the fixed price APX sells. Option B (strict percentage) exposes Julian if APX under-quotes; scope creep eats the margin. Option C bounds both risks: defined scope = forfait, explicitly validated out-of-scope = TJM.

**Consequences.** Requires clear scope boundaries. Reference calculation on 3 use cases at 50%: 45 k€ floor / 60 k€ ceiling over 8 weeks vs 31–36 k€ on pure TJM — "le forfait est plus rémunérateur car il valorise la responsabilité technique (architecte + dev + recette) et pas seulement les heures."

> **Status:** **not superseded, but not closed either.** Still listed as an open question in `Agents/state.json` ("Forfait Julian → APX : 50% de l'invoice client, ou TJM 900€/jour avec cap ?") and still flagged as a live blocker on 2026-05-14 and 2026-05-17 (`Agents/recaps/2026-05-14-cron-brief.md`, `Agents/recaps/2026-05-17-cron-brief.md`). **Its 30–40 k€ base assumption is undermined by the 22 000 € HT RMT proposal** (see §2.5).

### 6.4 ADR — Architecture du pont multi-agent (Cowork ↔ APX agent ↔ Telegram)
`decisions/2026-04-28-bridge-multi-agent.md` · type: agentique · status: **implémenté**

**Decision.** Option 4 (combination), layered:
- **Current truth:** `state.json` — read/written by all agents.
- **Chronological memory:** `recaps/*.md` — append-only, one file per significant session.
- **Structural decisions:** `decisions/*.md` — append-only, ADR-light.
- **Async queue:** `inbox/inbox.md` — Telegram → Cowork.
- **Notion mirror** of recaps and decisions for web viewing and for sharing with Maxime/Lucia.

Flow: a Cowork session reads `state.json` + last 3 recaps + `inbox.md` at start and writes a recap + decisions + state at the end. A daily 18:00 cron re-reads the day (recaps, git commits, APX emails, Notion edits), produces a short brief, pushes it to Telegram, and a TTS audio version at 07:00. Implementation: Python scripts in `bridge/` (`daily_recap.py`, `telegram_send.py`, `telegram_inbox.py`, `morning_brief.py`, `github_webhook.py`), versioned in a private git repo.

**Reasoning.** Julian was acting as a manual relay between Cowork, APX agent Kimi-2, James, Luke Codex, Sofia DeepSeek — "pas tenable".

**Consequences.** Positive: no more human relay; auditable institutional memory; pattern reusable beyond APX (Groupama, MIP, xSOM). Negative: requires writing discipline ("Si je ne tiens pas le recap à la fin de session, le système se dégrade vite"); noise risk; `state.json` write conflicts if two agents write simultaneously — mitigated by git versioning and a `_meta` timestamp+name convention.

> ⚠️ **Superseded in practice / the predicted failure mode occurred.** (a) The documented risk — "si je ne tiens pas le recap … le système se dégrade vite" — materialised: `state.json` has not been updated since 2026-04-28 and `inbox/inbox.md` is still empty with the placeholder "*(vide — le bot n'a pas encore commencé à écrire)*" (`Agents/inbox/inbox.md`), described as "stale (Apr 28)" on 2026-06-16 (`Agents/mvp-updates/2026-06-16T10-10+0200-suggestions.md`). (b) The Telegram bridge never went live: "Inbox Telegram : vide (bot APX_JTA_bot pas encore configuré — TELEGRAM_BOT_TOKEN manquant)" (`Agents/recaps/2026-05-04-monday-standup.md`); `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are still listed as "à obtenir" in `Agents/state.json` `secrets_required`. (c) The daily cron did run 2026-05-01→2026-05-24 but produced near-identical templated briefs echoing stale state (`Agents/recaps/2026-05-*-cron-brief.md`). (d) The pipeline that actually carried May–June signal was **WhatsApp captures → `Resources/00-inbox`/`01-raw` → `02-processed` → `03-distilled` → `04-structured`**, plus an autonomous **MVP updater** writing to `Agents/mvp-updates/` against GitHub repo `jt33120/apx-platform`.

### 6.5 Decisions taken outside the ADR set (recorded, but never promoted to an ADR)

| Decision | Date | Maker | Source |
|---|---|---|---|
| MVP architecture = **cloud OVH**, on-prem dockerisation deferred to a later phase | 2026-05-05 | Julian | `Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json` |
| POC data collection = **local folder only**; email connector deferred to M3 (Graph OAuth2 too slow: Azure AD app registration 1–2 weeks, MFA/conditional access, rate limiting) | 2026-05-05 | Julian | `Resources/03-distilled/decision-notes/2026-05-05_poc-data-collection-decision.md` |
| POC UI = **Streamlit** (1–2 days) for the visual POC only; prod = Next.js + FastAPI. Gradio rejected (no native editable table), PyQt/Tkinter rejected (deployment + no remote access) | 2026-05-05 | Julian | ibid. |
| **RMT devis ≈ P&P devis**, "légèrement moins technique — pas de changement majeur de tjm" | 2026-05-06 | Julian | `Resources/01-raw/2026-05-13T00:12:00+02:00--APX--whatsapp-pipeline-status.json` |
| **Lexoria** retained as the brand name of the generic demo mockup — product-name status unconfirmed | 2026-05-13 | Julian | `Resources/01-raw/2026-05-13T13:52:00+02:00--APX--whatsapp-mockups-lexoria-anfr.json` |
| Chunking must cut at **legal section boundaries**, not fixed token counts; legal-specialised embedding models named (`legal-bert-fr`, `CamemBERT-legal`); syllogisme output under a **forced JSON Schema** | 2026-05-05 | Lucia's specs | `Resources/03-distilled/decision-notes/2026-05-05_mise-a-jour-proposition-lucia.md` |
| Embeddings **must run locally** — "Critique : … (secret professionnel)" | 2026-05-05 | Lucia's specs | ibid. |

> ⚠️ **Conflict/staleness — POC vs direct MVP, same day.** `Resources/03-distilled/decision-notes/2026-05-05_poc-data-collection-decision.md` recommends a **Streamlit POC** (3–4 days) with success criteria involving Emmanuel and Éléonore. `Resources/01-raw/briefs/2026-05-05_message-james-projet-luxembourg.md`, dated the same day, states "**Architecture validée : pas de POC, MVP direct (Next.js + FastAPI, pas Streamlit)**". The sources do not say which prevailed; the June repo is a Next.js/FastAPI monorepo, which suggests the second, but that is inference, not a recorded decision.

---

## 7. Non-negotiable constraints

### 7.1 Master list (cross-client)
From `Agents/state.json` `shared_architecture.non_negotiables` and `Resources/04-structured/specs-candidates/APX_CONTEXT.md` §6:

1. **RGPD (UE 2016/679) + AI Act (UE 2024/1689) + secret professionnel CNB.** The professional secret of French lawyers is criminally sanctioned — "sanctionné pénalement pour les avocats" (`Agents/recaps/2026-04-28-cowork-session-1.md`).
2. **EU only · zero retention.** No data leaves the EU; zero-retention on every third-party LLM (professional API, never consumer).
3. **RAG strict — never any fine-tuning on client data.**
4. **No complete document is ever sent to an LLM** — fragments only, "< 2 000 tokens", anonymised (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §2.3; `Resources/LexCore_Devis_PhilippePartners.docx`).
5. **Systematic human validation before any publication.** "aucune décision juridique n'est prise par le système."
6. **Total auditability** — "l'agent n'est pas une boîte noire". Direct answer to Emmanuel's requirement.
7. **Signed NDA + DPA before M1 starts.**

### 7.2 Regulatory / compliance detail

| Domain | Commitment | Source |
|---|---|---|
| **Secret professionnel (CNB)** | Dedicated instance per client, no cohabitation with other APX clients; AES-256 at rest (LUKS), TLS 1.3 in transit; one database per client, no pooling; M4 training module "Bonnes pratiques secret professionnel"; documentation supplied for the client's declaration to the Conseil National des Barreaux | `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §8.1 |
| **RGPD Art. 28** | APX = *sous-traitant* (processor), client = *responsable de traitement* (controller). Sub-processors listed with written guarantees (AWS Bedrock eu-west-1, Mistral AI EU). Client right to audit: logs, technical documentation, annual pentest | ibid. §8.2 |
| **RGPD Art. 32** | AES-256 at rest, TLS 1.3 in transit, pseudonymisation of names in logs (except business audit logs which keep identifiers), SHA-256 checksum per document verified before processing, daily encrypted backup | ibid. |
| **RGPD Art. 35** | Preliminary **DPIA** performed by APX, template supplied to the client. Risks identified: data leak (low, mitigated by isolation), wrongly rejecting a relevant piece (medium, mitigated by audit), discriminatory bias (low, mitigated by gold-standard tests). CNPD opinion assessed as not required | ibid. |
| **AI Act** | Classified **"système à risque limité"** (Annex III point 5, search/ranking systems) — **not high risk**, because no automated legal decision and human supervision is mandatory. Voluntary conformity: traceability, transparency, human supervision (override interface), accuracy (gold-standard tests). Annex IV technical documentation delivered at M4. Compliance register kept up to date and handed to the firm | ibid. §8.3; `Resources/LexCore_Devis_PhilippePartners.docx` |
| **Data retention** | Audit trail conservation 90 days (configurable), exportable to PDF for the client file. APX-side data destroyed 30 days post-final-delivery with a certified purge certificate | `Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §7.1, §8.5 |
| **Right to erasure** | Secure deletion procedure available on request | `Resources/LexCore_Devis_PhilippePartners.docx` |

### 7.3 Data-handling mechanics

- **Immutable audit event** structure: `{event_id, timestamp, user_id, action, document_id, document_hash, llm_prompt, llm_response, llm_model, final_decision, confidence, override}`. PostgreSQL `JSONB` with a trigger preventing UPDATE/DELETE — soft delete only, logged separately. (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §8.5)
- **Egress whitelist only**: `ufw default deny outgoing` + explicit allow to `api.mistral.ai:443` and `bedrock.eu-west-1.amazonaws.com:443`. A `network_audit.sh` script (24 h tcpdump capture) is supplied so the client can verify there are no undocumented network calls. (ibid. §8.6)
- **APX access to production** only under a written **break-glass** agreement, logged in a dedicated register, supervised by the client. Named individuals with potential access: Julian Talou, Maxime Durupt (break-glass only); client-side sysadmin has server but not application access. (ibid. §7.4; `Resources/LexCore_Devis_PhilippePartners.docx`)
- **Dev environment:** only anonymised documents (`{{NOM_AVOCAT}}`, `{{NOM_CLIENT}}`); preview data auto-deleted on PR merge; audit trail disabled in dev. (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §7.3)
- **Embeddings never leave the firm's infrastructure** — computed and stored strictly locally. (`Resources/LexCore_Devis_PhilippePartners.docx`; `Resources/04-structured/specs/validated/requirements.json` FR-02)
- **OpenClaw separation:** Maxime explicitly asked in his 2026-04-28 email whether "OpenClaw ne risque rien côté sécurité". Documented answer: OpenClaw is entirely separated from client data; no client data passes through that environment. The RMT proposal carries a section "10.4 Note sur OpenClaw (**à confirmer**)". (`Resources/04-structured/specs-candidates/APX_CONTEXT.md` §8; `Resources/APX_Proposition_Technique_MVP_Tri_Cabinet_RMT.docx`)

### 7.4 Anti-hallucination guardrails (contractually stated to P&P)

- **Absolute rule:** no legal argument may be produced without citing an internal source. If no source is available, the system displays **`[SOURCE MANQUANTE — À VÉRIFIER PAR L'AVOCAT]`**.
- **Post-generation fidelity check:** every draft is automatically checked by a second model that lists assertions unsupported by sources.
- **Confidence threshold:** if source relevance scores **< 0,75**, the system does not generate and requests human validation.
- **Stated limit:** user documentation and the UI permanently state that the system reduces hallucinations but does not eliminate them; the lawyer remains responsible for final validation.
(`Resources/LexCore_Devis_PhilippePartners.docx` §5)

### 7.5 Quality gates and supervision metrics (RMT)

- Triage accuracy > 95% on the 50-document gold standard for M2; thematic classification > 90%. Deployment **blocked in CI** if accuracy < 95% on the gold standard. Prometheus metric `apx_classification_accuracy` alerts below 0.90 over 1 h. (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §6.5, §10.1)
- Override rate > 15% of AI classifications corrected → alert to APX (few-shot retraining needed). Wrongly rejected relevant document > 2% → deep audit. (ibid. §8.4)
- Multi-label classification: softmax with threshold 0.6, **max 3 thématiques** per document, confidence displayed per label, manual override logged. (ibid. §6.2)
- SLA (during the active APX phase): Critical (system down, data leak) first contact 30 min / resolution 4 h · High (>10% misclassified) 2 h / 24 h · Medium 4 h / 72 h · Low 1 day / 2 weeks. Hours Mon–Fri 09:00–19:00 Paris; out of hours Critical only. (ibid. §9.2)

### 7.6 Intellectual property

- **Code licence: Apache 2.0** with a non-assertion clause; client receives the full source on a private GitHub repo, unlimited internal use/modification/redistribution. (`Resources/03-distilled/mvp-briefs/2026-05-05_odj-rmt-technique.md` §12.1)
- Client-specific connectors: property of the client; APX keeps a usage licence for other clients. Few-shot prompt examples: 100% client property, never reused for other clients (NDA), unless fully anonymised. **No fine-tuning ⇒ no derived model ⇒ no IP on weights.** (ibid. §12.1–12.3)
- Action item **AI-007** (open): document clearly the boundary between *reuse of APX code* (allowed) and *reuse of client data* (forbidden) — an older technical report conflated the two. (`Resources/04-structured/specs/validated/task.json`)

> ⚠️ **Conflict/staleness — messaging on external models.** The 2026-04-20 commercial deck asserts that **no external AI model accesses the data at all**, which is stricter than every later technical document (which allows zero-retention API calls on fragments). Action item **AI-008** requires a single reconciled message before any further distribution. (`Resources/04-structured/specs/validated/requirements.json` review log; `Resources/04-structured/specs/validated/task.json`)

---

## Open questions for Julian

These are genuinely unanswered by the sources, not merely undecided-in-one-place:

1. **What is the final P&P development price?** The client-facing `LexCore_Devis_PhilippePartners.docx` prices only recurring monthly costs. Internal figures range 33 750 € → 40 000 €. No source states the forfait actually quoted.
2. **Why did RMT drop from 40 000 € to 22 000 € HT between 2026-05-05 and 2026-05-06?** And does the Julian→APX 50% still apply on the lower base?
3. **Were the two devis actually sent, and to whom?** The last recorded status is `devis_not_sent` (2026-05-05) for P&P; nothing at all for RMT. The stated deadline was 2026-05-09.
4. **Are "Emmanuel" and "Maître Sorlin" the same person (Emmanuel Sorlin)?** state.json treats them as two contacts.
5. **P&P: 25 or 30 avocats, and where does the 60 000-document figure come from?** "Volume CSIP exact" is still listed as an open blocker while the proposal contractually commits to indexing 60 000 docs in M1.
6. **Focus or parallel?** Julian recommended pausing RMT until mid-August to focus on P&P (2026-05-05). No source records Maxime's, Lucia's or James's answer.
7. **Did any client sample ever arrive?** Last evidence (2026-06-02) says no. If still no, the MVP has never run on real data.
8. **What is the arbitration on the LLM gateway?** Bedrock/Claude vs Mistral EU vs OpenRouter — action item AI-006 is still `pending`.
9. **Is "Lexoria" the product name?** Flagged by Julian himself as unconfirmed. Also: what is the relationship between `Lexoria`, `LexCore`, `Syllogisme AI` and `CPC-145 / Data Corpus Manager` — four names for overlapping things.
10. **Cabinet italien #1** — who are they, what scope, what happened at the 2026-05-11 RDV? Nothing beyond a single line in a WhatsApp capture.
11. **Cabinet italien #2** — did the 2026-06-04 RDV happen, and was the Milan window (21–27 June) used for physical data retrieval?
12. **Strelia / Maître De Crépy** — active lead or archive? Undocumented since 2026-04-22.
13. **Marie (avocate, Bordeaux, intro Sully)** — is this a real pipeline entry? Only classified as commercial noise by an engineering agent.
14. **Who is "Lucio"?** A distinct person or a typo for Lucia in the 2026-05-05 meeting brief.
15. **Was the Julian↔APX convention ever signed?** It was meant to precede M1.
16. **Audit trail direction** — the 2026-06-20 updater explicitly asks whether to reopen a clean PR for the audit trail (default: it rebuilds automatically on 2026-06-23 absent objection) and who owns the Vercel setup. No answer is recorded.
17. **What happened between 2026-06-20 and now?** The knowledge base stops there.
