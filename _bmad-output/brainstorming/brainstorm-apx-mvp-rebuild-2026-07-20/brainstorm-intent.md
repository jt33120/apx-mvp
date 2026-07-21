# APX MVP Rebuild — Intent Brief

Input for `bmad-product-brief` → `bmad-prd`. Source: brainstorming session 2026-07-20 (`.memlog.md`).
Decisions and open questions are labelled. Do not treat an OPEN item as settled.

---

## 1. Intent

APX is rebuilding its legal-AI platform for law firms in France and Luxembourg (first clients: RMT, Philippe & Partners). v1 was never a failed product — it was a category error: a POC that had to be demoed without real firm data, so it mixed real and fake data until the demo layer became load-bearing. The through-line of this rebuild: **v1 built what can be SHOWN; v2 must build what can be PROVEN.** Every claim the product makes to a lawyer — this citation is real, this quote is exact, nothing relevant was discarded, this document was validated by a human, no data left the firm — must be backed by a mechanism that is deterministic, testable and auditable, not by an intention stated in a document. The rebuild targets a first increment installable at a real firm, not another demo.

---

## 2. Product framing

### Offers vs promises (user reframe, decided)

| The three OFFERS (features) | The three PROMISES (the actual product) |
|---|---|
| RAG / search over firm data | Security & confidentiality |
| Syllogisme (drafting) | Ease of use for non-technical collaborators |
| Veille | Volume — decades of activity |

A firm does not buy RAG; it buys the right to put its matters in without risking liability. **v1 built all three offers and skipped all three promises** — each promise maps onto an empty directory: security → empty `rbac/`; simplicity → no settings surface, 3 unreconciled colour systems, broken i18n; volume → 8 empty `workers/` files and a second upload that overwrites the first.

### Information architecture (decided)

The three offers dissolve into **three verbs in one workspace** — *consult/search*, *add*, *draft* — with **Veille as the one separate module**. Documentation/triage stops being a product and becomes "add documents" + a review queue. This replaces v1's three-tool navigation.

- **Home screen = the human-in-the-loop queue.** It opens on "what needs you?", not "what can I do?": what bugged, what errored, what needs re-reading or sorting, plus ongoing matters and tasks. Human-in-the-loop stops being a policy and becomes a worklist.
- **Design rule (decided):** the top zone is a WORKLIST, not a log. Every line must be an action in her language ("14 pièces illisibles — les traiter"), never a technical state. Not actionable = not at the top.
- **Cold-start ingestion = a folder.** USB key → select the folder holding 4 years → APX does the rest. No connector, no API, no IT project. Import runs non-blocking bottom-right (Google-Drive style); on completion it yields the human tasks plus a KPI summary. This UX specifies the backend: it *requires* the queue/worker layer and resumable ingestion.
- **Syllogisme screen:** chat left, document right. Two phases — (1) initialise with questions and context, (2) drafting. *Open: how to structure the drafting phase.*
- Minimalist, for non-technical non-expert users. Nothing superfluous.

### Scoping decision

**ONE FEATURE ONLY = Syllogisme** (decided, arbitration 1). Rationale: it is the deepest vertical slice — shipping it forces ingestion, index, RBAC, citation, generation and export to exist. Documentation is that spine plus a classification layer; Veille is an ETL into the same index.

**Accepted risk, stated honestly:** the commercial analysis points the other way. The strongest revenue story is *winning work the firm could not bid on before* — a 1 700-document *ordonnance 145 CPC* review is exactly the matter a firm declines or under-prices. That makes **triage the commercial wedge while Syllogisme is the technical wedge**. The user chose Syllogisme as the sales argument APX wants, with the divergence acknowledged and accepted.

### Deployment posture (decided)

Do not build "a SaaS". Build a **deployment-agnostic core with tenant isolation as a day-one invariant**; SaaS vs on-prem becomes a packaging decision per client. Retrofitting multi-tenancy is the classic rewrite trigger. Corollary: **customisation must be DATA, never code** — veille sources, .docx style templates, triage taxonomy, RBAC scopes, LLM provider are all config rows. One codebase, N clients. Forking per client is survivable at 3 clients and fatal at 8.

**Hard boundary (decided): only CODE travels.** APX never accesses, sees or extracts client data. Follow-up happens by call and human communication; updates are generated and shipped blind. Price of that boundary: no telemetry. Mitigation is *not* telemetry but a self-diagnosing product plus a **client-initiated, content-free diagnostic export** (counts, error types, versions, redacted stack traces). They push; APX never pulls. Cockpit visibility is itself per-tenant config: SaaS tenants can be live-monitored, on-prem tenants stay dark.

**Genuinely hard unsolved piece:** on-prem update delivery — signed, versioned, offline-installable artifacts with reversible migrations that run against a 100 000-document index *without re-indexing*. This is what "goes beyond generating HTML" actually means.

---

## 3. Non-negotiable mechanisms

Mechanisms, not intentions. Guarantee → the thing that makes it mechanical and measurable.

| # | Guarantee | Mechanism |
|---|---|---|
| 1 | Finding and proving are never confused | **Two engines with different truth status.** One that FINDS (semantic, top-k, suggestive) and one that PROVES (deterministic exact search, exhaustive, verifiable, returns the complete match set). Semantic top-k can never prove absence; only exhaustive search can say "exact search over the whole indexed corpus: zero occurrences". The UI must never blur them. This condemns v1's off-corpus gate — a score threshold, disabled by default: a guess that looks like a proof, worse than nothing. |
| 2 | No fabricated citation can ship | **Layer 1 CHECKER — deterministic, non-negotiable:** every citation resolves to a real indexed chunk by id; every quoted passage matches its source by exact string containment; every case reference resolves against Legifrance/Judilibre/EUR-Lex. A lookup, not a judgement — it cannot hallucinate. "Jurisprudence parfaite" becomes mechanically achievable: a fabricated citation becomes impossible to ship rather than unlikely. **Layer 2 CRITIC — LLM adversarial, optional (SHOULD):** re-reads for unsupported non-citation claims; it never gets to bless a citation (an LLM checking an LLM shares its blind spots and will confirm a hallucination). |
| 3 | The product refuses to emit an unresolved claim | **Blocking, not warning.** Anything the checker could not confirm — citation resolved but support uncertain, possibly-superseded ruling — blocks export until the lawyer rules on it. Warnings are ignored; blocks are not. |
| 4 | Absence can be asserted honestly | **The inventory guarantee.** A register of what FAILED to ingest (skewed scans, corrupt .msg, password-protected PDFs): "100 000 submitted / 97 200 indexed / 2 800 unreadable, listed one by one." The decisive piece hides statistically in those 2 800. Never demoed, always needed. |
| 5 | AI never destroys the lawyer's work | **The document is the source of truth; the chat may only PROPOSE.** Every AI action is a per-block diff she accepts or rejects. Never a full regeneration. |
| 6 | She has necessarily read what she signs | **Per-section validation on the skeleton.** The right pane shows EN FAIT / EN DROIT / PAR CES MOTIFS, each section in a state (empty / drafted / cited / validated by her); the chat is scoped to the current section. The skeleton IS the progress bar. Safeguard moves from the end to the path, so the final button is a formality. Plus **targeted friction, not uniform friction**: explicit per-item confirmation on paragraphs carrying a citation, a number, a date or a legal claim; boilerplate passes. Uniform friction is ignored friction. |
| 7 | The validation gesture leaves a defensible record | **Audit record:** who validated, when, which version, which sections were modified vs accepted as-is, and which warnings were overridden **with a required one-line reason**. Forcing a reason on an override is the cheapest single mechanism that both builds the trail and makes people think. |
| 8 | No cross-matter leak inside a firm | **RBAC as a query PRE-filter, never a post-filter.** A post-filter leak is silent and is a professional-conduct violation. This is the #1 realistic leak vector, ahead of the LLM provider and of logs. |
| 9 | The one irreversible decision is made once | **Frozen payload schema** — RBAC + provenance + matter + dates on every chunk. Everything else (LLM provider, hosting) stays reversible behind adapters; the payload schema is the only true lock-in. |
| 10 | "Only code travels" is verifiable, not declarative | **Content-free projection as a single reusable primitive**, built once and used three times: (a) the on-premises style extractor emitting a content-free profile, (b) the client-pushed diagnostic export, (c) the cockpit that sees THAT 2 800 failed but not WHICH. Its content-freedom must be enforced by a TEST, never promised in a doc. |
| 11 | Triage commits without destroying | **One ranked list underneath** — nothing deleted, nothing categorised, so reversibility is structural. **On top, the tool DRAWS A LINE and commits**: "in my view, everything above this". The pile is a VIEW over an order, not a destructive classification. The lawyer can drag the line; its position is an auditable parameter. |
| 12 | "Recall over precision" is a number, not a slogan | **Random sampling with a confidence bound.** Sample 200 of 1 400 discarded: "200 checked, 0 relevant, risk of having missed a relevant document < 1.5%." Moving the line is priced: "move it here and you read 400 more pieces, your risk falls from 3% to 0.4%." |
| 13 | The output does not read as LLM prose | **Prevention over filtering.** Constrain generation to the firm's own phrasebook (connectors and formulae extracted from their past documents) so the LLM register never surfaces. Keep a banned-patterns blacklist (em-dashes, rambling sentences) as config, not as the primary defence. |
| 14 | Ingestion survives volume and repetition | Resumable, **idempotent** ingestion with queue + workers, and the failure register (#4). v1's ingest reused point ids from 1, so a second upload overwrote the first. |

**Residual gap, acknowledged:** the deterministic checker proves a citation exists and a quote is exact; it cannot prove the passage *supports the proposition* the paragraph draws from it. That gap is where human validation is irreducible and where the LLM critic earns its place. Two further failure modes it does not cover: **stale law** (a perfect citation of overruled law is worse than none — the bridge to Veille) and **omission** (nothing fabricated, the decisive contrary authority simply never surfaced — invisible, and exactly why "recall over precision" exists). The indistinguishability criterion amplifies all three: the moment she most needs to read critically is the moment the draft is most convincing.

---

## 4. Scope — MoSCoW

First increment = installable at a real firm.

### MUST
- Frozen payload schema (RBAC + provenance + matter + dates) — the only irreversible decision
- RBAC as a query pre-filter
- Resumable, idempotent ingestion with queue + workers, plus the failure register
- A real semantic embedder that **fails loudly**
- The gold eval set running in CI
- Exhaustive deterministic search
- The citation checker, **blocking** (not warning) on unresolved claims
- Document-as-source-of-truth with per-block diffs and per-section validation
- Audit trail with reasoned overrides
- `.docx` export on the firm's real template
- Style profile v1 (skeleton + phrasebook)
- Tenant isolation + config-as-data
- Folder / USB ingestion

### SHOULD
- Statistical style fingerprint asserted in CI
- LLM critic (layer 2)
- Reranking
- Client-pushed content-free diagnostic export
- Veille as stale-law check
- Proper i18n — **becomes MUST if Philippe & Partners is the first client** (Luxembourg; v1 i18n is fatal there)

### COULD
- Full APX admin cockpit (operator console: tickets, follow-ups, per-client config)
- Triage module
- Auto-update channel
- Fully local model

### WON'T (this increment)
- Shared SaaS hosting
- Three-tool navigation
- Fine-tuning
- Live connectors
- **The fixture layer — deleted, not disabled**

Arbitrations recorded: (1) Syllogisme confirmed as the sales argument despite triage being the easier sell; (2) cockpit stays in COULD — coach caveat that "easy to write" is the cousin of "just tokens", but config-as-data remains MUST so the cockpit's foundation gets built anyway; (3) Cloud Act / AI Act inform technical choices but anything easily changed later is not a blocker — a provider-agnostic LLM adapter makes the Cloud Act decision reversible as a config line.

---

## 5. North-star acceptance criteria

1. **The blind two-document test (user, non-negotiable).** Syllogisme drafts the finished document directly: right format, firm letterhead and logo, exactly the lawyer's own style. Put two documents side by side — one human-written, one tool-written — and nobody can tell which is which.
2. **Automated statistical proxy for it.** Compute the firm's statistical fingerprint over its past documents (sentence-length distribution, em-dash frequency, connector frequency, section lengths) and assert generated output falls inside it. Deterministic, cheap, runs in CI — makes the north-star operational instead of ceremonial.
3. **Zero tolerance for anything false.** Enforced by the deterministic checker + blocking gate, not by review.
4. **Sampling confidence bound** on discarded material, expressed as a sentence a lawyer can say to a client or a judge (§3 #12). Measure the *human* baseline too, by sampling the lawyer's own past triage — the honest comparison is not against perfect human review but against what happens today: skimming and skipping under deadline. *Caveat: telling a client you measured their error rate is a delicate sales choice.*
5. **Retrieval measured against the existing gold eval set**, in CI. v1 never ran anything against it.

**Style-profile sourcing (sized):** per document type — 1 empty `.docx` template (highest leverage, zero confidentiality); 5 same-type documents for the skeleton; 20–30 for phrasebook + fingerprint; **+10 held out for the blind test**. ≈30 per type. Ask BY TYPE ("20 conclusions en droit des assurances, 3 dernières années"), never in bulk — that is likely why nothing ever arrived. Anonymisation leaves the critical path: ship the extractor to the firm, documents never move, only the content-free profile comes out.

---

## 6. Open decisions the brief / PRD must resolve

| Open question | The tension, in one line |
|---|---|
| SaaS vs forfait | SaaS contradicts the locked ADR `modele-facturation` (forfait per use case, no licences, no subscription) and the on-premise / sur-mesure positioning — yet the P&P quote is already a de facto subscription (~750–1 400 EUR/month recurring) **with no development forfait at all**. |
| Commercial narrative | "Fewer associates needed" (sells to the partner who signs, but users sabotage a tool that automates their job away, and associates *are* the production capacity and the future-partner pipeline) vs "same associates, more matters" (incentives align). The product cannot tell both stories. |
| Cloud Act acceptability | US-headquartered providers can be compelled to produce data regardless of storage location, so "EU region" is not sufficient. The stack flipped to Claude Sonnet on AWS Bedrock eu-west-1 — EU-located, US-operated — which contradicts the sovereignty pitch if a client's counsel looks closely. Local-first narrows exposure to the prompt only; a fully local model is the premium tier for firms that refuse it. |
| AI Act qualification | Genuinely unclear: Annex III covers administration of justice, but a firm's drafting tool is arguably not judicial-authority use. Needs a lawyer's determination, not a guess. **Move: ask RMT or P&P to qualify APX under the AI Act** — free expert legal work, de-risks APX, makes the client co-owner of the compliance story. |
| Does the first client's demand exceed capacity? | "More clients" only produces revenue if demand exceeds capacity; if the firm is not turning work away, saved time becomes idle time, not income. Sharpest qualifying question: *"Refusez-vous des dossiers aujourd'hui ?"* Aggravated by the structural paradox: on the billable hour, saving three hours **shrinks** the invoice — APX destroys revenue unless the firm moves to fixed fees or takes more volume. APX Advisory already sells forfait, not TJM; the client firms still bill by the hour. |
| Scale beyond the design target | Is 100 000 → 1 000 000 documents just more compute? Unanswered. |
| Drafting-phase structure | How phase 2 of the Syllogisme screen is structured beyond "skeleton + per-section chat". |

---

## 7. Constraints inherited, not up for debate

- EU-only
- Zero-retention (note: a contract clause, not a technical property — every RAG request carries client text)
- No fine-tuning on client data
- Human-in-the-loop everywhere (no auto-delete, auto-send, auto-sign)
- Never hard-delete — triage is reversible labelling
- Recall over precision in triage
- Design target: **100 000 documents** (decided; P&P M1 commitment is 60 000)
- Only code travels — APX never accesses, sees or extracts client data
- Full audit trail; RBAC by matter (Chinese walls)

---

## 8. Assets to salvage from v1

Ranked, paths as recorded in the memlog.

| Rank | Asset | Why |
|---|---|---|
| 1 | `data/mock/raw` + gold-standard `manifest.json` | A ready-made **eval set** — the thing needed to make retrieval measurable. |
| 2 | Bloc-03/04 syllogisme builder + scorer (~250 LOC, pure functions) | Tested both sides of the 0.70 gate. |
| 3 | The 13 executable PLAN-§5 guardrail tests | Already runnable. |
| 4 | The hard-won prompts | Syllogisme "RÈGLE ABSOLUE" + off-corpus escape hatch; the 9-label taxonomy; EN FAIT / EN DROIT / PAR CES MOTIFS. |
| 5 | `maquette_anfr_v2.html` — editable cell-by-cell triage table with live before→after change log ("aucun écrasement destructif") | Answers Éléonore's requirement directly; also the fully designed Audit Drawer (confidence, retained extracts, numbered "Trace d'audit proposée", 4 reversible actions). |
| 6 | Shipped `/syllogisme` tri-directional citation ↔ source ↔ graph cross-highlight + `OffCorpusPanel` | The one shipped interaction worth keeping. |

**Public-corpus move (adopted):** use real public legal corpora as the demo corpus — Legifrance/Judilibre via PISTE, EUR-Lex, HUDOC, Legilux. Real, free, legally clean, voluminous. Kills the fake-data problem outright for Syllogisme and Veille; only Documentation/triage still needs firm documents.

---

## 9. Known traps — v1 defects that must not recur

| Defect | Consequence |
|---|---|
| **Self-deleting index** — `qdrant.py:37` wipes the whole collection on any vector-size mismatch | One transient 429 destroys the corpus. |
| **Silent embedder fallback** — `embeddings/factory.py:40` falls back 1024-dim → 256-dim SHA-256 hash on ANY exception, unlogged | Retrieval silently becomes noise. The default embedder was a 256-bucket bag-of-words. |
| **`withDemo()` overriding a healthy backend** — `api.ts:282` swaps a healthy backend response for hand-authored fixtures whenever `provider=='stub'` | The demo layer literally overrides the real product. `/dossiers` and `/cartographie` never call the backend at all. |
| **Ingest id collision** — point ids reused from 1 | A second upload overwrites the first. |
| **Empty `rbac/`, `workers/` (all 8 files), `infra/db/`, `infra/queue/`** | No tenancy, no DB, no queue. RBAC is a PLAN-§5 legal obligation sitting at zero lines. |
| **0-byte modules** — `domain/audit/{service,events,models}.py`, `reranking.py`, `citations.py`; PR #33 (audit trail) closed unmerged | The sold differentiator — "auditabilité non-négociable" in BOTH client proposals — has nothing behind it. |
| **~80% untested; `make test` errors outright**; HEAD 3 commits ahead of main, stranding the audit trail off the deployed branch | Nothing is verifiable. |
| **Docs contradicting code** — `PISTE_API_KEY` and `COHERE_API_KEY` appear in ZERO source files; `retriever.py` (Bloc 02) does not exist; the ×1.4 "cabinet boost" is applied uniformly so it is a no-op on ordering; `.env.example` names the embedder var wrong | Documentation lies in load-bearing places. |
| **Off-corpus gate disabled by default** (`SYLLOGISME_MIN_SCORE=0`) | A guess presented as a proof. |
| **Destructive triage** — the only destructive control (`Supprimer`) is a raw `confirm()` with no undo and no audit entry; no triage bucket, no per-document confidence, no explicit "Valider" act | Directly violates "triage never destroys". |
| **3 unreconciled colour systems, ~20 hard-coded hexes, no settings surface** | Per-firm `.docx` templates and per-client veille profiles are unbuildable. Mockups and shipped app share almost no visual DNA. |
| **i18n untenable** — French source strings ARE the translation keys with silent fallback; `/dossiers/[id]` 100% untranslated; dates hard-coded `fr-FR`; no `lang` reaches the LLM | Fatal for a Luxembourg client. |
| **Superseded-but-unmarked ADRs** — default LLM Mistral Large → Claude Sonnet on AWS Bedrock eu-west-1; hosting Scaleway → OVHcloud Gravelines | Decisions drift without a record. |
| **No client has ever supplied a test document** (RMT `.msg` / *ordonnance 145* / gold standard; P&P 20 templates, pending since 2026-06-02) — yet the P&P proposal contractually commits to indexing 60 000 documents in M1 | The zero-data day-one loop: no demo without data, no data without trust, no trust without a demo. **Inverting it means the client-data onboarding flow is the FIRST feature built, not the last.** |
| **RMT price halved 40k → 22k EUR HT with no recorded decision** | Commercial decisions unrecorded. |

**The single most dangerous belief carried over:** "it's just Claude Code tokens". Writing code is nearly free; OWNING it is not. Every feature must be tested, migrated blind against a 100 000-document index at every client site, defended in front of a judge, and supported over the phone with zero telemetry. At 3 on-prem firms, one more feature = 3 blind deployments maintained forever. This belief, unchecked, reproduces v1 verbatim.

**And the corollary the session ended on:** "without APX you cannot be a law firm" demands infrastructure status; infrastructure status forbids breaking; casually-produced code breaks.
