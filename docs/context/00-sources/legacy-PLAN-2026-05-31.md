# APX MVP Platform — Build Spec (PLAN.md)

> Status: build-ready draft · 2026-05-31 · owner Julian
> Scope: MVP of the three flagship tools — **Documentation**, **Syllogisme**, **Veille IA** — on the shared `legal-rag-core` foundation.
> Read alongside: `../../Agents/decisions/*` (ADRs), `../../Agents/state.json`, `../legal-rag-core/README.md`, `../maquettes/`.

## 0. Decisions locked (do not relitigate during build)

- **Architecture:** core library + per-client apps (`noyau-commun` ADR). For the MVP this is realized as a **monorepo** — `packages/legal-rag-core` (the lib) + `apps/apx-demo` (one app exercising all 3 modules). Diverges from the literal "3 separate repos" ADR for cost reasons; the *boundary* (core never knows the client) is preserved. Splitting into `apx-rmt` / `apx-pp` repos happens post-MVP.
- **MVP shape:** *real core behind a demo skin.* Same code path for demo and prod; only the **data source** and **UI chrome** differ. Demo never touches a real client connector.
- **Documentation tool** = mass-document **triage** (keep useful / discard junk, smartly, reversibly) + **NotebookLM-style chat/RAG** over the kept set.
- **Stack** (per ADR `stack-llm-hebergement`): Python/FastAPI backend, Next.js + Tailwind + TipTap frontend, BGE-M3 embeddings, Qdrant, Mistral Large EU default / Claude EU fallback, Tesseract+Mistral OCR, python-docx/WeasyPrint for export.
- **Non-negotiables:** EU-only · zero-retention · no fine-tuning on client data · strict RAG · human-in-the-loop · full auditability.

## 1. The three tools (corpus × task)

| Tool | Corpus | Core task | Client |
|---|---|---|---|
| **Documentation** | Ephemeral, per-matter dump (1700+ docs, mostly .msg) | Triage (pertinent / à revoir / rebut) → chat over kept set | RMT |
| **Syllogisme** | Persistent, firm-wide knowledge (memos, opinions, precedents) | Cross-matter Q&A with cited internal sources → firm-style drafting | P&P UC01 |
| **Veille IA** | Public sources (Légifrance, EUR-Lex, Cassation, CSSF/CNPD…) | Crawl → filter by practice area → digest | P&P UC02 |

Documentation + Syllogisme share ~90% of plumbing. Veille is an ETL/crawler + summarizer that reuses the embedding/LLM/digest layers but does no private RAG.

## 2. Repo layout (monorepo)

```
apx-platform/
├─ packages/
│  └─ legal-rag-core/        ← the library (semver). No client logic, ever.
│     ├─ ingestion/          ← extract-msg, pypdf/pdfplumber, python-docx, openpyxl, python-pptx, OCR
│     ├─ chunking/
│     ├─ embeddings/         ← BGE-M3 default; mistral-embed adapter
│     ├─ vectorstore/        ← Qdrant client + payload schema (provenance, RBAC scopes)
│     ├─ retrieval/          ← top-k + re-rank
│     ├─ llm/                ← provider-agnostic adapter (Mistral EU / Claude EU); STUB if no key
│     ├─ audit/              ← append-only immutable log
│     ├─ citation/           ← source → passage linking
│     ├─ generation/         ← python-docx / WeasyPrint
│     └─ rbac/               ← scopes by matter/team/lawyer
├─ apps/
│  └─ apx-demo/              ← FastAPI backend + Next.js frontend; turns on all 3 modules
│     ├─ modules/documentation/
│     ├─ modules/syllogisme/
│     ├─ modules/veille/
│     └─ web/                ← UI (reuse ../maquettes as reference)
├─ workers/                  ← async: ingestion, OCR, veille crawls (Celery/RQ or FastAPI bg tasks for MVP)
├─ data/mock/                ← synthetic/anonymized corpora (gitignored if sensitive)
└─ tests/
```

## 3. MVP scope per tool — IN vs deferred

### Documentation v1 (IN)
Upload a batch (zip) → parse + OCR → embed + index → triage into 3 buckets, each with a **confidence score** and a **one-line reversible justification** → **editable table** (cell-by-cell, never destructive regeneration) → **NotebookLM-style chat** over the *kept* set, citing source + passage, answering "not in the corpus" honestly → **audit drawer**.
Deferred: live connectors (Outlook Graph, CSIP, USB scan), dedup/thread reconstruction at scale, advanced re-rank, multi-user RBAC UI.

### Syllogisme v1 (IN)
Persistent mock firm corpus → **NL Q&A with cited internal sources** → generate **one** document type (memo or simple assignation) from a NL instruction → **docx export with source footnotes** → human edit.
Deferred: multi-template library, per-lawyer style profiles, conflict/Chinese-wall RBAC.

### Veille IA v1 (IN)
2–3 **real public** sources (Légifrance API + EUR-Lex + one Lux source) → scheduled crawl → filter by 1–2 practice areas → **digest** (summary + official link + urgency) → email/in-app.
Deferred: full source coverage, per-avocat tuning UI, GraphRAG entity linking.

## 4. Build sequence (maps to I1→I3)

- **S0** — monorepo init, CI, env, provider-agnostic config; generate `data/mock/` synthetic corpora (see §6 assumption A1).
- **S1** — core spine: ingestion + embeddings + Qdrant + audit. **Veille pipeline in parallel** (cheapest, public, fastest win).
- **S2** — Documentation module (triage + chat) on mock corpus.
- **S3** — Syllogisme module (Q&A + one drafting template).
- **S4** — demo UI (reuse `maquettes/`), private deploy, audit drawer, before/after metrics for sales.

## 5. Guardrails — what to be careful about (BLOCKING during build)

**Documentation — triage is the dangerous tool.**
- **Never hard-delete.** Triage = labeling + ranking, fully reversible. "Rebut" is a recommendation, never an action.
- **Optimize for recall over precision.** Tossing a relevant doc (false negative) ≫ keeping junk (false positive). Default to "à revoir" under uncertainty; always show confidence.
- **Auditability is the trust mechanism** (Emmanuel): random-sampling audit, every classification traceable.
- Chat must **refuse outside the corpus** — strict RAG, cite source + passage, say "not found" rather than hallucinate.

**Syllogisme — hallucination in drafting is catastrophic** (fabricated citations get lawyers sanctioned).
- Every claim cited to an internal source. Output is "best first draft, **not signable**"; human validation mandatory.
- **"Firm style" ≠ fine-tuning** (forbidden on client data). v1 = few-shot from retrieved exemplars + templates. Be honest match is approximate.
- Flag **stale precedents** (old firm position superseded by new law); ideally cross-check Veille.
- **RBAC by matter/team is a hard requirement** — no retrieval across walled-off matters (conflicts / Chinese walls).

**Veille — public, low-risk, but trust is fragile.**
- Use **official APIs/open data** (Légifrance API, EUR-Lex RSS/API, Legilux). Avoid brittle HTML scraping / ToS issues.
- Summary is a **pointer, not a substitute** — always link the official source. "Urgency" is a humble heuristic.
- Make filters tunable (false positives kill adoption, false negatives kill trust).

**Cross-cutting.**
- EU-only · zero-retention · no-training on every LLM call · per-client isolation.
- Human-in-the-loop everywhere: no auto-delete, auto-send, auto-sign.
- Cost discipline: Mistral default, cache embeddings, batch, reserve Claude EU for hard reasoning only.
- Scope: ONLY these 3 tools (KYC/AML and Suivi-dossier from the deck are out of MVP). Resist creep.
- Demo/real boundary: mock + public data only; the real client connector code path stays unused in the demo.

## 6. Assumptions to confirm (defaults chosen so build is not blocked)

- **A1 — Mock data:** assume we **synthesize** corpora for the demo (a fake litigation dump for triage; fake firm memos/precedents for Syllogisme). Swap for anonymized client samples (RMT 50–100 .msg + 145 ordonnance + gold-standard table; P&P 20 templates) when available.
- **A2 — Repo:** monorepo (see §2). Confirm GitHub org + **private** visibility.
- **A3 — Hosting:** frontend demo on private Vercel; backend on the Scaleway dev box (30€/mo). Confirm.
- **A4 — LLM keys:** if no Mistral/Claude EU key yet, ship the `llm/` adapter with a **stub/echo provider** so the pipeline runs end-to-end; wire real keys later.

## 7. Definition of done (MVP)

- All three modules run end-to-end on mock/public data through one `apx-demo` app.
- Documentation: upload → triage with confidence + justification → editable table → cited chat with honest "not found".
- Syllogisme: cited Q&A + one docx draft with source footnotes.
- Veille: live digest from ≥2 real public sources.
- Audit log present and viewable; no hard-delete anywhere; no auto-send/sign.
- Private deploy reachable; before/after metrics panel for sales.
