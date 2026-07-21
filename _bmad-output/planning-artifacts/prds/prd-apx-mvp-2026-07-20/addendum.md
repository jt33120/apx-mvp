---
title: "Addendum: APX MVP PRD — First Increment: Mass-Document Triage"
status: draft
created: 2026-07-21
updated: 2026-07-21
---

# Addendum — APX MVP PRD, First Increment

Everything the PRD deliberately excludes because it names a technology, a vendor or a sequencing consequence rather than a capability. The PRD body states **what the product must do and how you would test it**; this document states **what it may be built on, what it may not be built on, where the corpus comes from, in what order the work must happen, and what was considered and rejected.**

Downstream consumers: `bmad-architecture`, `bmad-create-epics-and-stories`.

Companion: `prd.md` in this folder. Upstream: `../briefs/brief-apx-mvp-2026-07-20/brief.md` and its `addendum.md`, and `../../brainstorming/brainstorm-apx-mvp-rebuild-2026-07-20/brainstorm-intent.md`.

**Revised 21 July 2026** alongside the PRD, to carry the mechanism detail behind the 22 requirements that revision added (PRD FR-37…FR-58). New here: §1.5 (what forbidding the managed identity layer actually costs), §7 (the relevance cascade), §8 (the estimator — what is settled and what is not), §9 (security mechanisms), §10 (the structural properties, as CI checks), §11 (viewer and export mechanisms). §3.3's sequencing and §4's rejected alternatives are extended. **The PRD body states capabilities; everything in this document is mechanism, technology or a rejected alternative, and none of it is a capability commitment.**

---

## 1. The infrastructure contradiction, and the rule that resolves it

### 1.1 The contradiction, stated plainly

- **Stated posture:** EU-only, only-code-travels, on-premise, local packaging.
- **Chosen build stack:** Supabase, Vercel, Railway — all US-operated, none installable at a law firm.

The two do not reconcile as a *deployment* story. They reconcile as a *development* story, and only under one condition:

> Supabase, Vercel and Railway are acceptable for development and for a future hosted tier.
> **The core must carry no hard dependency on any of them.**

### 1.2 The acceptable / not-acceptable boundary

| Acceptable | Not acceptable |
|---|---|
| Plain PostgreSQL (Supabase is just Postgres underneath) | Supabase Auth as the identity layer |
| Object storage behind an interface | Supabase Row-Level Security as the RBAC implementation |
| Next.js deployed on Vercel | Vercel-specific runtime primitives in application code |
| A worker process on Railway | Railway-specific queueing or scheduling semantics |

The right-hand column is not a style preference. Supabase Auth as the identity layer and Supabase RLS as the RBAC implementation each make on-premise installation impossible later — and PRD FR-14 (RBAC as a query pre-filter) and FR-29 (tenant isolation) both state that identity and authorisation are properties of the application, not of the hosting environment. That FR wording exists because of this table.

### 1.3 The fitness function

Write it down as an architecture fitness function and run it as a check, not as a review question:

> **Can this run, unmodified, on a single machine inside a law firm with no internet connection?**

Anything that fails it is a dependency to be pushed behind an adapter. This is the same shape as the provider-agnostic LLM adapter that makes the Cloud Act question reversible, and the general pattern is:

> **Anything that could be compelled, priced or discontinued by a third party lives behind an interface.**

Applied without exception to: the model provider, the embedder, OCR, object storage, the queue, and the vector index.

### 1.4 The two v1 index defects this table also has to survive

The index sits behind an interface for the reasons above, and also because the two most destructive v1 defects were both in the index adapter:

- The collection was wiped on any vector-size mismatch (`qdrant.py:37`). One transient error destroyed the corpus. → PRD FR-10.
- The embedder factory fell back from a 1024-dimension semantic model to a 256-dimension SHA-256 hash on **any** exception, unlogged (`embeddings/factory.py:40`). The default embedder was a 256-bucket bag-of-words, so retrieval silently became noise. → PRD FR-9.

Neither is a technology problem. Both are error-handling policy encoded in an adapter, and both must be asserted by test in the new adapter before any corpus is loaded into it.

### 1.5 What the right-hand column costs, stated once

The two forbidden items in §1.2 are the two that would otherwise have been free:

- **Supabase Auth as the identity layer** would have supplied password hashing, session lifetime, MFA, lockout, credential rotation and account recovery. Forbidding it does not remove those requirements — it removes the implementation. They are now PRD FR-48 and FR-51, written from scratch.
- **Postgres row-level security as the RBAC implementation** would have enforced the Chinese wall *at the storage layer, regardless of application bugs*. Forbidding it makes every authorisation decision hand-rolled application code (PRD FR-14, FR-49), written by AI agents, reviewed by one non-hands-on person, where a mistake is silent and is a criminal-law exposure.

**Both forbiddings are correct**: each would make on-premise installation impossible later, and on-premise is the product. The point of this section is that the cost is real, it lands entirely on the test suite, and it is now on the PRD's risk register as R-15 rather than implied by a table.

**Mitigation that costs little and is worth doing anyway:** even without RLS as *the* mechanism, a defence-in-depth scope predicate can be expressed once, in one query-construction layer, with a single enforced entry point (PRD FR-56) — so that the hand-rolled control has exactly one place to be wrong rather than one per call site. That is an architecture decision, and it is the single highest-leverage one in this programme after the payload schema.

### 1.6 The offline fitness function is now a CI job, not a review question

§1.3 instructed: *"run it as a check, not as a review question."* It was never run as anything. **PRD FR-55** makes it a CI job from the first week: boot in a network-isolated container with no hosted-provider service reachable, ingest, index, retrieve, rank, place the line, audit, export. Compare with the *content-free projection*, where an equivalently important guarantee is bound to a seeded-token test and the PRD says outright *"this test is the guarantee; a statement in a document is not."* The same sentence applies here and had not been applied.

The job also enumerates what does **not** survive the model provider's absence — the ranking, the justifications, the priced statement — and asserts the one thing that must: the *confidence bound* sentence renders offline from the *audit record*, by template, never by a model call. A statistical claim that depends on a network call is not the self-sufficient artefact SM-1 promises.

---

## 2. Corpus sources — specifics

The strategy is in PRD §8. This section holds the parts that name things.

| Need | Source | Specifics and cautions |
|---|---|---|
| **Real mess at volume** | **Enron / EDRM corpus** — ~500 000 genuine business emails with attachments, threads and duplicates, public since the FERC release; the canonical dataset of the e-discovery field | Real human correspondence: real threading, real duplicates, real dead ends, real attachments. **English** — this limits *language* realism, not *pipeline* realism. **Verify the licence terms of the specific distribution used** before ingesting; distributions differ. Several cleaned variants exist and the cleaned ones are the wrong choice here — the mess is the point. |
| **A measurable recall target** | **TREC Legal Track** collections — built for e-discovery evaluation, with human relevance judgments | This is the *gold set* of PRD SM-2. It is what gives the *confidence bound* something real to be scored against. v1 had a gold set (`data/mock/raw` plus a gold-standard `manifest.json`, ranked #1 on the salvage list) and never once executed it. |
| **French-language realism** | Real French public legal and administrative text — Légifrance and Judilibre via PISTE, EUR-Lex, HUDOC, Legilux — **mechanically degraded** | The degradation pipeline: render to skewed scans; wrap in `.msg` with plausible headers and reply chains; duplicate with variations; deliberately corrupt a fraction; password-protect a fraction. **The content is real; only the degradation is manufactured — and degradation is the thing under test.** This is categorically different from fabricating documents, which is what v1 did. |
| **A small genuinely-owned dump** | APX Advisory's own mail, proposals and project files | Tiny, unquestionably real, unquestionably owned. A smoke test for the pipeline, not an evaluation set. |

**Two rules that override everything in this table.**

1. **Every corpus enters through the same code path as client data.** No fixture layer, no demo branch, no `withDemo()`. A corpus is a *data source*, swappable by configuration — never a fallback that can silently override a working system. (PRD FR-33.)
2. **The degradation configuration is part of the test surface.** Each mechanical degradation is applied in order to produce a known expected outcome in the *failure register*: a corrupted `.msg` must produce error class `corrupt-file`, a password-protected PDF must produce `password-protected`, and so on. The degradation and the expected classification are asserted together, or the *failure register* is untested.

**What none of this buys.** Classification quality is measured against public benchmarks rather than against a practitioner's judgement of their own matter. The benchmarks make the product measurable; they do not make it wanted. The single highest-value acquisition remains one real anonymised litigation matter, from any friendly practitioner, on any terms — asked for **by shape and volume** ("one closed matter, 200+ pièces, mostly email, anonymised however you like"), never in the abstract. Asking in the abstract is the most likely reason nothing ever arrived before.

---

## 3. Capacity, and what it does to sequencing

**The team is one non-hands-on CTO plus AI agents.** That is the real headcount. Four consequences the build must absorb rather than discover:

### 3.1 Tests are the substitute for the engineers who are not on the team

They are not overhead here; they are the only mechanism that makes an AI-driven build safe. v1 ran approximately 80% untested with `make test` erroring outright, and its head of development sat three commits ahead of `main`, stranding the audit trail off the deployed branch. An AI-driven build with no test suite is v1 again, faster.

This is why every functional requirement in the PRD states its consequences in testable form, and why several FRs are written as assertions about what the code must **not** contain (no fallback embedder, no post-filter, no fixture path, no natural-language translation key, no hard-coded locale). Those are grep-able, CI-enforceable properties. They are cheap, and they are the ones that decayed silently in v1.

### 3.2 Front-load the irreversible

The **payload schema is the only true lock-in.** Everything else — model provider, hosting, embedder, UI, index — is replaceable behind an adapter. Getting the schema right on day one is worth more than any three features, because getting it wrong means a blind migration against a live 100 000-document index at a site APX cannot see, which is the one unsolved problem in the whole programme (PRD §16).

Corollary, recorded in PRD §15: design the schema now to accommodate an external-authority reference on a chunk, even though nothing in this increment writes one. The citation checker arrives next increment; the schema must not have to change to receive it.

### 3.3 Sequence against the spine, never breadth-first

The MUST list is large for this capacity. It is not padded — each item traces to a promise made to a lawyer — but attacked breadth-first it produces a half-built everything.

**Order:**

0. **Security foundations and provisioning** (FR-47…FR-51) — encryption, identity, sessions, grant-time authorisation, key management, and the provisioning surface. **Moved to step 0 by the 21 July revision**, because every later step writes *tenant* data and because a fail-closed system with no provisioning surface cannot be installed at all. It is not a cross-cutting concern to be added later; steps 1 and 2 write the data it protects.
1. **Payload schema** (FR-8) — irreversible, therefore first, and frozen before anything writes to it. Now including *custodian*, extractor version, stored full text and the accommodations for `supersedes` and an external-authority reference.
2. **Ingestion** (FR-1…FR-7, FR-57) — folder selection, resumable non-blocking import, container expansion and the *pièce*-denominated inventory guarantee, idempotent identifiers, multi-format extraction, failure register, completion summary. This is where the design target first bites and where v1 had eight empty files. **FR-3 is the largest single engineering surface in the increment** and should be planned in months.
3. **Index** (FR-9…FR-11) — real embedder that fails loudly, an index that never self-deletes, chunking with provenance.
4. **Corpus and evaluation** (FR-54, FR-55, FR-56, SM-2) — **promoted from a clause inside step 4 to a step of its own**, because the reviews were unanimous that as a clause it would be dropped, and because the merge gate it carries must exist before step 6 begins. The offline fitness function and the structural-property checks belong here for the same reason: they are cheap in week one and a rewrite in month six.
5. **Retrieval, measured** (FR-12…FR-15) — two engines with declared truth status, exhaustive search over stored full text with specified French normalisation, RBAC as a pre-filter with a scope-mutating adversarial suite. The gold set runs from the first day retrieval exists. Not after.
6. **Relevance and ranking** (FR-37…FR-43) — case theory, the cascade, the ranked order and its version, labelling, justification, derived confidence, pins. **Gated on §6.3 of the PRD**: not begun until one real anonymised matter is in hand or its absence is re-accepted in writing with a date.
7. **Triage** (FR-16…FR-21) — the line, the priced move, the cell-by-cell table with its change log.
8. **Reading and delivery** (FR-44…FR-46) — the viewer, the validation act, the retained-set export. It sits here because it consumes the ranking, and it must not sit later than this: it is the user's actual job, and a triage tool she cannot read in is a triage tool she will not use.
9. **Audit and sampling** (FR-22…FR-26, FR-53, FR-58) — the confidence bound, the record behind it, its continuity, and the freshness rules that keep it from going quietly false. Last of the product surfaces, because it consumes all of them.

**Cross-cutting, built into each step rather than after it:** tenant isolation and configuration-as-data (FR-29, FR-30) from step 0; i18n (FR-34…FR-36) from the first user-visible string, because retrofitting it is exactly what made v1's i18n untenable; the worklist (FR-27, FR-28) grows a line type per step rather than being built as a screen at the end; backup and restore (FR-52) exercised from the first step that has data to lose.

**On the honest size of this.** Nine steps, 58 requirements, one non-hands-on CTO and AI agents. PRD §6.3 names the minimum-viable subset and the cut order; this sequence is what to build if capacity permits, not a prediction that it will.

**Deliberately sequenced, not inherited as a side effect.** The original plan chose Syllogisme first precisely because shipping it forced ingestion, index, RBAC, citation and export to exist. Triage does not force the citation checker or the drafting surface into existence. That depth-forcing property is genuinely lost by the reversal and must be replaced by discipline: the schema accommodation in §3.2, and an explicit decision point before the next increment.

### 3.4 "It's just Claude Code tokens" is the identified failure belief

Generating is free; owning is not. Every shipped feature is a permanent tax: tested, migrated blind against a 100 000-document index at every client site, defensible in front of a judge, supportable by telephone with zero telemetry. At three on-premise firms, one more feature is three blind deployments maintained forever.

This belief, unchecked, reproduces v1 verbatim — and this capacity is precisely the one that makes it tempting. The corollary the brainstorming session ended on is worth keeping in front of whoever is making scope decisions: *"without APX you cannot be a law firm" demands infrastructure status; infrastructure status forbids breaking; casually-produced code breaks.*

---

## 4. Rejected alternatives, and why

| Considered | Rejected because | Where it shows in the PRD |
|---|---|---|
| **Syllogisme drafting as the first increment** (the original decision) | Two independent signals reversed it: the commercial analysis during the brainstorming session, then the competitive research. Drafting over a firm's own corpus is the most contested space in the market — an incumbent reaches 7 500 French firms with essentially this product through practice-management software they already pay for, and the cheapest competitor sells corpus-indexing legal AI at €19/month on SecNumCloud-qualified infrastructure. Triage for European firms under 50 lawyers is empty. Triage also unlocks the stronger revenue story: matters a firm currently declines or under-prices because the review cost is prohibitive. **The reversal is cheaper than it looks** — the spine is common to both. | PRD §5 (non-goal), §6.2 with a `[NOTE FOR PM]`, §1 |
| **A fixture / demo layer, disabled rather than deleted** | In v1 a demo helper (`api.ts:282`) swapped a healthy backend response for hand-authored fixtures whenever a provider flag was set — the demo layer literally overrode the real product, and two whole routes never called the backend at all. A disabled fallback is one configuration mistake away from being an enabled one, and the failure is silent because the fixtures look right. **Deleted, not disabled.** | FR-33 |
| **RBAC applied as a post-filter** | A post-filter leak is silent and is a professional-conduct violation, not a bug. It is the #1 realistic leak vector, ahead of the model provider and ahead of logs. It also leaks through counts and metadata even when documents are correctly hidden — which is why the PRD extends the zero target to counts, snippets, filenames and the denominator itself. | FR-14, SM-6 |
| **A similarity-score threshold as an off-corpus / absence gate** | v1 implemented exactly this and shipped it disabled by default (`SYLLOGISME_MIN_SCORE=0`). A threshold is a guess wearing the costume of a proof, which is worse than no gate at all, because the user stops checking. **Only deterministic exhaustive search can prove absence.** | FR-12, FR-13, FR-15 |
| **A fallback embedder for resilience** | The intention is reasonable and the outcome is catastrophic: v1's fallback turned semantic retrieval into a 256-bucket bag-of-words silently, and the system kept returning confident results. A halted import that says so is strictly better than a working import that is wrong. | FR-9, and the "fail loudly" rule in PRD §9 |
| **Automatic index recreation on schema or dimension mismatch** | v1 wiped the whole collection on any vector-size mismatch. One transient error destroyed the corpus. The recovery convenience is not worth the failure mode; halt and surface it. | FR-10 |
| **Destructive triage controls (delete, archive, file-into-folder)** | v1's only destructive control was a raw `confirm()` with no undo and no audit entry, directly violating "triage never destroys". More fundamentally: if the piles are containers, reversibility is a promise someone has to keep. If they are views over one ranked order, reversibility is a property that cannot be violated. | FR-16, FR-21 |
| **A ranked list with no committed line** | A ranking that refuses to decide pushes the judgement back onto the lawyer, which is precisely what she is paying to avoid. The tool commits and she moves the line — and the move is priced so she is choosing between options rather than guessing. | FR-17, FR-19 |
| **Regenerating the triage table after an edit** | Cell-by-cell editing with no destructive regeneration came from a practising associate and turned out to be the architectural invariant of the system, not a UI preference. Her requirement is negative — *do not lose my edits* — and it is only satisfiable if no edit can cost another. | FR-20 |
| **Per-client code forks to absorb bespoke requests** | Survivable at three clients, fatal at eight — and a consultancy says yes to bespoke requests, so the pressure is constant. Customisation must be **data**: taxonomy, RBAC scopes, model provider, sources, thresholds, labels. This also builds the admin cockpit's foundation while the cockpit itself stays deferred. | FR-30 |
| **Telemetry, of any kind** | Contradicts "only code travels" outright. The mitigation is not a smaller telemetry payload — it is a self-diagnosing product plus a **client-pushed, content-free diagnostic export**: they push, APX never pulls. Content-freedom is enforced by a seeded-token test, never promised in a document. | FR-31, FR-32, SM-7 |
| **French source strings as translation keys** | v1 did this with silent fallback; one route was 100% untranslated, dates were hard-coded to `fr-FR`, and no language ever reached the LLM. Fatal for a Luxembourg client and fatal again for an Italian one. Namespaced keys with build-time failure on a missing translation is the only version of this that survives contact with a second language. | FR-34, FR-35, FR-36 |
| **Retrofitting multi-tenancy later** | The classic rewrite trigger. Tenant isolation is a day-one invariant; SaaS versus on-premise then becomes a packaging decision per client rather than a product decision. | FR-29, and §1 above |
| **Building the admin cockpit now** | Nothing is installed, so there is nothing to operate. The coach caveat is recorded: "easy to write" is the cousin of "it's just tokens". Its foundation — configuration-as-data — is in scope, so only the interface waits. | PRD §5 |
| **A fully local model in this increment** | The premium sovereign tier. Only worth building once a firm refuses the hosted model provider **in writing**. Until then it is cost with no counterparty. Note the honest consequence: without it, zero-retention remains a contract clause rather than a technical property. | PRD §5, §10 |
| **Leading with EU AI Act compliance** | Legal AI sold to law firms is very likely outside Annex III high-risk — that provision covers use by or on behalf of judicial authorities — and the high-risk regime was deferred to 2 December 2027 by the Digital Omnibus. Art. 50 transparency applies from 2 August 2026. Leading with it signals APX has not read the Omnibus, and a sophisticated general counsel or bâtonnier will know. Replaced by the CNB March 2026 guide and *secret professionnel* (Art. 226-13 CP France / Art. 458 CP Luxembourg). | PRD §12 |
| **Publishing an accuracy or hallucination rate** | A competitor's unaudited "under 1%" is exactly the kind of claim that gets dismantled the first time a client tests it. Claim tier (a) citation verification — *the authority exists* — be explicit about tier (b) *still good law* and tier (c) *the authority supports the proposition*, and publish no number that has not been audited. | PRD §5 |
| **Competing on corpus depth, or positioning as a research tool** | Unwinnable. A publisher holds two centuries of doctrine and millions of decisions; consolidation in French legal data is essentially complete and foreign-owned. APX competes on the firm's own corpus plus free public sources, which is the right choice — and it means never pretending to be a research tool. | PRD §2.2, §5 |
| **A generic, corpus-intrinsic ranking with no user-stated criterion** | It was the only reading consistent with FR-1's original "exactly three inputs", and it is astrology with a confidence score attached: it cannot be validated against any matter-specific standard, its per-pièce justification is *necessarily* empty because there is nothing for it to be a justification relative to, and SM-2 would measure the ranker against TREC's notion of relevance rather than this lawyer's. **Replaced by the optional case theory**: mandatory nothing, offered everywhere, and where it is absent the product says so in every artefact and names the intrinsic signals it used instead. | PRD FR-1, FR-37, FR-38 |
| **A mandatory case-theory / configuration screen before ingestion** | The opposite failure. UJ-1's whole premise is one gesture on a Friday evening — plug in the key, name the matter, walk away — and a firm's associate who is asked to write a legal brief before her documents will import stops importing. Optional, rewritable at any time, triggering an explicit re-rank, is the only version that satisfies both. | PRD FR-1, FR-37 |
| **An LLM call per pièce at the design target** | 100 000 model calls per matter is the largest inference cost and the largest data-egress event in the system, and nobody had written down what it costs. **Replaced by the cascade** (§7 below): deterministic filters and near-duplicate grouping, then cheap semantic scoring, then LLM judgement only on the uncertain band plus a calibration sample — and justifications only near the line with on-demand backfill. Cuts cost, latency and egress by roughly an order of magnitude and costs nothing a user notices. | PRD FR-18, FR-38, §9, §11, SM-18 |
| **A model-reported confidence** | Asking a language model how confident it is produces a number that correlates with fluency, not with correctness, and it would have fed a statistical sentence a lawyer says in court. Confidence is derived from score margin or cross-stage agreement, calibrated against the gold set, and the absence of a consumed model-reported field is a structural check. | PRD FR-42, SM-17 |
| **The binomial rule of three for the confidence bound** | Two defects, one fatal. Fatal: it was applied to the wrong **estimand** — it bounds prevalence and the sentence claimed the probability that nothing was missed (PRD §0.2). Secondary: even correctly worded, at 200 drawn from 1 400 the finite-population correction is a material tightening, so the rule of three gives away accuracy the sample actually bought. **Hypergeometric, with the confidence level stated.** | PRD §0.2, FR-23, SM-1 |
| **Quietly fixing the false sentence** | The tempting move, and the wrong one. This document's entire thesis is that unaudited claims are how v1 failed; an unaudited number travelled from a brainstorming session through a brief into a glossary, three FRs and a north-star metric, and no reviewer caught it until the third review. **A permanent dated note in PRD §0.2**, plus a structural check on the banned phrasings across every locale, so a translator cannot reintroduce it in French or Italian. | PRD §0.2, FR-23, FR-56 |
| **Forbidding bulk acceptance outright** | A 1 700-row grid grows a select-all because every grid does, and a prohibition produces a workaround rather than compliance. **Permitted and never undetectable**: one audit entry per pièce, each marked `bulk` with the batch size and identifier, each recording whether the pièce was opened in the viewer, and counted separately in the export. A reader can always tell 180 judgements from one gesture over 1 400. | PRD FR-45 |
| **Removing a failure-register entry on successful retry** | The original wording said "removes it from the register" while FR-21 forbade deleting a register entry and §9 declared it append-only — three requirements that could not all hold, which two different agents would have implemented two different ways. **Resolution by state change**, with the inventory guarantee counting open entries only. | PRD FR-5, FR-6, FR-21 |
| **Making path part of the pièce identity** | FR-4 required the identifier to be a function of "content and provenance" *and* required two copies at different paths to collapse into one pièce. Both cannot hold, and the choice silently decides whether a 100 000-file dump with the customary duplication rate presents as 100 000 pièces or 65 000. **Identity is (content, matter); path is an attribute; every custodian survives the collapse.** | PRD FR-4, FR-8 |
| **Registering an unopened archive as one failure** | A `.zip` of 500 documents would read as "· 1 not indexed" behind a denominator the product promises never to round — defeating the exact purpose the glossary gives the failure register. **Containers are expanded with bounded recursion; an unopened one carries cardinality `unknown` and every absence claim states the unknown.** | PRD FR-57, FR-13 |
| **Leaving "the line" as the only instrument** | Retaining the one document that decides the case would have required dragging the line past the 400 above it, and the audit record would show a global 400-document decision where the actual decision was about one. **The pin** moves a single pièce, requires a reason, is recorded as an override and survives re-ranking. | PRD FR-43 |
| **Keeping "asserted by test" on universal negatives** | "No code path exists" is not decidable by a runtime test, and this document convicts v1 of documentation that lies in load-bearing places. With the test suite standing in for the engineers who are not on the team, an inflated claim about what it proves is the most dangerous inaccuracy available. **Three verbs: asserted by test, enforced as a structural property, asserted by review** — and the third is never counted as a passing test. | PRD FR-56, §5 of the rubric review |
| **Selling on total cost of ownership** | On-premise break-even against cloud requires roughly 80% sustained GPU utilisation over three years, and a 30-lawyer firm reaches nothing like it; on-premise also implies 0.5–1 FTE of operations. If a prospect's finance director models it, on-premise loses on cost. The only winning frame is **risk elimination for a named confidentiality-critical workflow** — *ordonnance 145 CPC* review, criminal defence, sensitive M&A, Luxembourg private wealth. The buyer can also read the CCBE's own March 2026 guide, which prices the hardware at €2 000–20 000. | PRD §10 (Cost), §18 R-8 |

---

## 5. Salvage from v1 — what is reusable in this increment

Ranked as recorded, filtered to what this increment can actually consume.

| Asset | Use here |
|---|---|
| `data/mock/raw` + gold-standard `manifest.json` | The eval set. Ranked #1 for a reason: it is the thing that makes retrieval measurable, and it was never executed. Feeds PRD SM-2 alongside TREC. |
| `maquette_anfr_v2.html` — the editable cell-by-cell triage table with its live before→after change log ("aucun écrasement destructif"), and the fully designed audit drawer (confidence, retained extracts, numbered *Trace d'audit proposée*, four reversible actions) | Directly the design source for PRD FR-20 and FR-26. The most directly reusable artefact in the whole salvage list for this increment. |
| The 13 executable PLAN-§5 guardrail tests | Already runnable. First entries in the CI suite. |
| The 9-label triage taxonomy (from the hard-won prompts) | A starting taxonomy, loaded as configuration-as-data (FR-30) rather than as code. Unvalidated for *ordonnance 145 CPC* review — PRD OQ-16. |

**Not salvageable into this increment** (they belong to the drafting increment): the Bloc-03/04 syllogisme builder and scorer, the syllogisme prompts and the EN FAIT / EN DROIT / PAR CES MOTIFS skeleton, and the shipped `/syllogisme` tri-directional citation ↔ source ↔ graph cross-highlight with its `OffCorpusPanel`.

---

## 6. Items this addendum deliberately does not decide

These belong to `bmad-architecture`, not to the PRD or its addendum:

- Which vector index, which relational store, which object store, which queue.
- Which embedding model, and which OCR engine — subject only to §1.3 (must run inside the tenant boundary offline) and PRD FR-9 (must fail loudly).
- Which model provider, and the shape of the provider-agnostic adapter — subject to PRD OQ-12.
- Chunking strategy and parameters — subject to PRD FR-11 (deterministic, provenance-carrying, configuration-as-data).
- The near-duplicate similarity measure and its threshold — subject to §7 below and to PRD OQ-4 and OQ-21, which are *not* architecture decisions.
- The rendering technology for the *pièce* viewer, subject to §11 and to the rule that no *pièce* content leaves the *tenant* boundary for rendering.
- The static-analysis tooling behind the structural properties of §10 — grep, lint, import-graph or architecture-rule engine. The *properties* are PRD FR-56; the tools are not.
- The statistical estimator behind the priced statement and the confidence bound. This is **not** an architecture decision either: it is PRD OQ-4, and it needs a statistician's answer before FR-19 and FR-23 can be built. **The *estimand* is now settled** (a hypergeometric prevalence bound with its confidence level stated — PRD §0.2); what remains is the estimator and the five inputs §8 lists. It is the most load-bearing unresolved item in the increment.
