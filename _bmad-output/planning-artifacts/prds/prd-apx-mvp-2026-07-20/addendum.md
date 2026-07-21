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

> **The upstream above is current. The context pack is not.** `docs/context/`, its `00-README.md` entry point and the `state.json` snapshot beneath it — which the project's `CLAUDE.md` sends every agent to first — record the prospect relationships as live. **They are stale on that point:** no engagement has been won and no client corpus exists (brief `addendum.md` §1). Read them with that correction in hand.

**Revised 21 July 2026** alongside the PRD, to carry the mechanism detail behind the 22 requirements that revision added (PRD FR-37…FR-58). New then: §1.5 (what forbidding the managed identity layer actually costs). **Written by the reconciliation pass of the same date, having been promised by that revision and by PRD §0.1 and never written:** §7 (the relevance cascade), §8 (the estimator — what is settled and what is not), §9 (security mechanisms), §10 (the structural properties, as CI checks), §11 (viewer and export mechanisms). **Also new: §12** (the market judgements the PRD carries anonymised or not at all). That same pass added **PRD FR-59** (the usability gate — §10's last check, §3.3's cross-cutting note) and **PRD FR-60** (the *matters* zone), taking the PRD to 60 requirements. §3.3's sequencing and §4's rejected alternatives are extended. **The PRD body states capabilities; everything in this document is mechanism, technology, market judgement or a rejected alternative, and none of it is a capability commitment.**

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

The **payload schema is the only true lock-in.** Everything else — model provider, hosting, embedder, UI, index — is replaceable behind an adapter. Getting the schema right on day one is worth more than any three features, because getting it wrong means a blind migration against a live 100 000-*pièce* index at a site APX cannot see, which is the one unsolved problem in the whole programme (PRD §16).

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

**Cross-cutting, built into each step rather than after it:** tenant isolation and configuration-as-data (FR-29, FR-30) from step 0; i18n (FR-34…FR-36) from the first user-visible string, because retrofitting it is exactly what made v1's i18n untenable; the worklist (FR-27, FR-28) grows a line type per step rather than being built as a screen at the end, and the matters zone (FR-60) arrives with it; backup and restore (FR-52) exercised from the first step that has data to lose; and the usability gate (FR-59) run against whatever surfaces exist at each step rather than against all of them at the end, because a checklist first applied in month six is a checklist that finds work nobody will do.

**On the honest size of this.** Nine steps, 60 requirements, one non-hands-on CTO and AI agents — and, once installed, 0.5–1 FTE of operations per on-premise site on the same team (§12; PRD §17, R-1). PRD §6.3 names the minimum-viable subset and the cut order; this sequence is what to build if capacity permits, not a prediction that it will.

**Deliberately sequenced, not inherited as a side effect.** The original plan chose Syllogisme first precisely because shipping it forced ingestion, index, RBAC, citation and export to exist. Triage does not force the citation checker or the drafting surface into existence. That depth-forcing property is genuinely lost by the reversal and must be replaced by discipline: the schema accommodation in §3.2, and an explicit decision point before the next increment.

### 3.4 "It's just Claude Code tokens" is the identified failure belief

Generating is free; owning is not. Every shipped feature is a permanent tax: tested, migrated blind against a 100 000-*pièce* index at every client site, defensible in front of a judge, supportable by telephone with zero telemetry. At three on-premise firms, one more feature is three blind deployments maintained forever.

This belief, unchecked, reproduces v1 verbatim — and this capacity is precisely the one that makes it tempting. The corollary the brainstorming session ended on is worth keeping in front of whoever is making scope decisions: *"without APX you cannot be a law firm" demands infrastructure status; infrastructure status forbids breaking; casually-produced code breaks.*

---

## 4. Rejected alternatives, and why

| Considered | Rejected because | Where it shows in the PRD |
|---|---|---|
| **Syllogisme drafting as the first increment** (the original decision) | Two independent signals reversed it: the commercial analysis during the brainstorming session, then the competitive research. Drafting over a firm's own corpus is the most contested space in the market — an incumbent reaches 7 500 French firms with essentially this product through practice-management software they already pay for, and the cheapest competitor sells corpus-indexing legal AI at €19/month on SecNumCloud-qualified infrastructure. Triage for European firms under 50 lawyers is empty. Triage also unlocks the stronger revenue story: matters a firm currently declines or under-prices because the review cost is prohibitive. **The reversal is cheaper than it looks** — the spine is common to both. | PRD §5 (non-goal), §6.2 with a `[NOTE FOR PM]`, §1 |
| **A fixture / demo layer, disabled rather than deleted** | In v1 a demo helper (`api.ts:282`) swapped a healthy backend response for hand-authored fixtures whenever a provider flag was set — the demo layer literally overrode the real product, and two whole routes never called the backend at all. A disabled fallback is one configuration mistake away from being an enabled one, and the failure is silent because the fixtures look right. **Deleted, not disabled.** | FR-33 |
| **RBAC applied as a post-filter** | A post-filter leak is silent and is a professional-conduct violation, not a bug. It is the #1 realistic leak vector, ahead of the model provider and ahead of logs. It also leaks through counts and metadata even when *pièces* are correctly hidden — which is why the PRD extends the zero target to counts, snippets, filenames and the denominator itself. | FR-14, SM-6 |
| **A similarity-score threshold as an off-corpus / absence gate** | v1 implemented exactly this and shipped it disabled by default (`SYLLOGISME_MIN_SCORE=0`). A threshold is a guess wearing the costume of a proof, which is worse than no gate at all, because the user stops checking. **Only deterministic exhaustive search can prove absence.** | FR-12, FR-13, FR-15 |
| **A fallback embedder for resilience** | The intention is reasonable and the outcome is catastrophic: v1's fallback turned semantic retrieval into a 256-bucket bag-of-words silently, and the system kept returning confident results. A halted import that says so is strictly better than a working import that is wrong. | FR-9, and the "fail loudly" rule in PRD §9 |
| **Automatic index recreation on schema or dimension mismatch** | v1 wiped the whole collection on any vector-size mismatch. One transient error destroyed the corpus. The recovery convenience is not worth the failure mode; halt and surface it. | FR-10 |
| **Destructive triage controls (delete, archive, file-into-folder)** | v1's only destructive control was a raw `confirm()` with no undo and no audit entry, directly violating "triage never destroys". More fundamentally: if the piles are containers, reversibility is a promise someone has to keep. If they are views over one ranked order, reversibility is a property that cannot be violated. | FR-16, FR-21 |
| **A ranked list with no committed line** | A ranking that refuses to decide pushes the judgement back onto the lawyer, which is precisely what she is paying to avoid. The tool commits and she moves the line — and the move is priced so she is choosing between options rather than guessing. | FR-17, FR-19 |
| **Regenerating the triage table after an edit** | Cell-by-cell editing with no destructive regeneration came from a practising associate and turned out to be the architectural invariant of the system, not a UI preference. Her requirement is negative — *do not lose my edits* — and it is only satisfiable if no edit can cost another. | FR-20 |
| **Per-client code forks to absorb bespoke requests** | Survivable at three clients, fatal at eight — and a consultancy says yes to bespoke requests, so the pressure is constant. Customisation must be **data**: taxonomy, RBAC scopes, model provider, sources, thresholds, labels. This also builds the admin cockpit's foundation while the cockpit itself stays deferred. | FR-30 |
| **Telemetry, of any kind** | Contradicts "only code travels" outright. The mitigation is not a smaller telemetry payload — it is a self-diagnosing product plus a **client-pushed, content-free diagnostic export**: they push, APX never pulls. Content-freedom is enforced by a seeded-token test, never promised in a document. **Recorded reversal, which this row previously did not carry:** the session that decided the boundary also decided that *cockpit visibility is itself per-tenant config — SaaS tenants can be live-monitored, on-prem tenants stay dark*. The PRD reverses that to **no telemetry, ever**, and makes it a structural property: any outbound call site outside the enumerated adapters fails the build (FR-32). The reversal is deliberate — a per-tenant exception to a structural property is not a structural property — and its price is that the future hosted tier §1.1 keeps alive is permanently unmonitorable by the same check that protects the on-premise one. Stated as intended rather than left as a silent narrowing. | FR-31, FR-32, SM-7 |
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
| **Registering an unopened archive as one failure** | A `.zip` of 500 *pièces* would read as "· 1 not indexed" behind a denominator the product promises never to round — defeating the exact purpose the glossary gives the failure register. **Containers are expanded with bounded recursion; an unopened one carries cardinality `unknown` and every absence claim states the unknown.** | PRD FR-57, FR-13 |
| **Leaving "the line" as the only instrument** | Retaining the one document that decides the case would have required dragging the line past the 400 above it, and the audit record would show a global 400-pièce decision where the actual decision was about one. **The pin** moves a single pièce, requires a reason, is recorded as an override and survives re-ranking. | PRD FR-43 |
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

*The mechanism sections §7…§11 that follow state how the deferred requirements are meant to work. This section states where that stops: the decisions below are made by `bmad-architecture`, not by the PRD or by this document.*

- Which vector index, which relational store, which object store, which queue.
- Which embedding model, and which OCR engine — subject only to §1.3 (must run inside the tenant boundary offline) and PRD FR-9 (must fail loudly).
- Which model provider, and the shape of the provider-agnostic adapter — subject to PRD OQ-12.
- Chunking strategy and parameters — subject to PRD FR-11 (deterministic, provenance-carrying, configuration-as-data).
- The near-duplicate similarity measure and its threshold — subject to §7 below and to PRD OQ-4 and OQ-21, which are *not* architecture decisions.
- The rendering technology for the *pièce* viewer, subject to §11 and to the rule that no *pièce* content leaves the *tenant* boundary for rendering.
- The static-analysis tooling behind the structural properties of §10 — grep, lint, import-graph or architecture-rule engine. The *properties* are PRD FR-56; the tools are not.
- The storage layout and registration mechanism behind the projector registry of PRD FR-31 — subject to §10's check that no emission path exists outside it.
- The statistical estimator behind the priced statement and the confidence bound. This is **not** an architecture decision either: it is PRD OQ-4. **The estimand is settled** (a hypergeometric prevalence bound with its confidence level stated — PRD §0.2) **and the method is decided and no longer blocking** — standard finite-population statistics, validated by simulation in CI, with FR-19's counts-only fallback if validation cannot be made to pass. What remains open is the design of the inputs §8 lists, plus the stopping rule PRD OQ-26 adds to them. It is still the most load-bearing unresolved item in the increment.

---

## 7. The relevance cascade — mechanism behind PRD FR-38

The PRD states the capability: three stages, cheap first, an LLM judgement only on the uncertain band plus a calibration sample, stage boundaries as configuration-as-data. This section states the mechanism those consequences were written against, so that "cascade" is not re-invented per implementer. **None of it is a capability commitment.** Where it conflicts with an FR consequence, the FR wins.

**Stage 1 — deterministic, no model.** Type and extension; participant roles from `.msg` headers (custodian, sender, recipients, direction); dates against the case theory's period where one exists; exact-duplicate collapse, which FR-4's identity has already performed at ingestion; near-duplicate family grouping; and an obvious-noise pass over auto-replies, delivery receipts, signature-only bodies and boilerplate footers. Marginal cost per pièce: none beyond extraction, which has already happened.

**Near-duplicate grouping is the load-bearing part of stage 1**, and the part with two open questions against it (PRD OQ-21 for the product consequence, OQ-4 for the statistical one). The mechanism intended: shingled similarity over normalised extracted text; a message-id / in-reply-to family where headers survive; a normalised-subject family for chains where they do not. One representative carries the family into stages 2 and 3, and every member keeps its own identity, provenance and custodian (PRD FR-4). The similarity measure and its threshold are architecture's (§6). **The unit of the draw that follows from them is not** — it is PRD OQ-4, and choosing it wrongly narrows a bound stated to a judge.

**Stage 2 — cheap semantic scoring.** Cosine against the corpus embeddings FR-9 already wrote at ingestion: the case theory embedded once, or the intrinsic-signal profile where no case theory exists. No re-embedding of the corpus, no model call. This is the stage that produces the score dispersion FR-17's refusal condition is evaluated over.

**Stage 3 — the LLM judgement, on a band.** Applied to the pièces stages 1 and 2 could not separate — the band around the provisional line — **plus a mandatory random sample of the confident bands above and below it**, which is what makes the cascade's own calibration measurable rather than assumed (PRD SM-17). Without that sample the cascade can be confidently wrong at both ends and nothing detects it.

**The number nobody has.** The share of pièces reaching stage 3 decides the cost, the latency and the egress of a triage run (PRD SM-18, OQ-20). It is a configured band width, not an emergent property — which makes it the lever that gets pulled when a run turns out to be too expensive, trading a measured cost against an unmeasured quality. That trade is a recorded decision, not a configuration edit.

**Prompt and version discipline.** The prompt is part of the ranking version (PRD FR-39), not a file somebody edits between runs. A prompt change produces a new ranking version, which marks every derived artefact stale (FR-58). That is the mechanism standing between a silent prompt tweak and a confidence bound already quoted to a court.

---

## 8. The estimator — what is settled, and what is not

**Settled** (PRD §0.2, FR-23). The estimand is the **prevalence of relevant pièces in the discarded set**, bounded above at a stated confidence level. The estimator is **hypergeometric** — finite-population, without replacement. The binomial rule of three is rejected on two counts (§4). The sentence never states the probability that nothing was missed, and the banned phrasings are a structural check across every locale (§10).

**Not settled** — the five inputs of PRD OQ-4, plus one the reconciliation pass added:

1. **The unit of the draw.** Pièce, or near-duplicate family (§7). A population of 1 400 in which 300 pièces are 40 variants of eight threads is not 1 400 independent units; a textbook bound over it is narrower than the evidence supports, and it is stated out loud to a judge.
2. **Census versus sample.** Where the required size meets the population, the honest output is a census statement, not a residual-risk figure over a fully reviewed pile (PRD FR-22).
3. **Repeated runs.** Whether independent runs pool, how, and what a second run's sentence says about the first. The record showing both runs does not repair the multiple-comparisons problem, because the sentence travels alone.
4. **The freezing contract.** PRD FR-22 and FR-58 give the triggers; what is open is their sequencing — what invalidates a run in flight, and what a user is told at the moment it happens.
5. **Calibration of the projection at an unsampled position** (PRD FR-19). Not a sampling bound at all. The only labelled corpus in the plan is English e-discovery with a different relevance definition, and PRD SM-17 has to do something specific when the calibration is inadmissible.
6. **Added by the reconciliation pass — the stopping rule.** PRD OQ-26 asks what size of run a senior lawyer will actually complete, given that the user's own constraint is that lawyers do not sort. **Stratified draws** over the ranked order and **sequential or curtailed sampling** are the two mechanisms that buy a usable bound from fewer verdicts, and both change the estimator: a stopping rule applied to a fixed-size bound invalidates it. If the answer to OQ-26 is "sixty, not two hundred", the estimator is designed for sixty — that is a design input, not a later optimisation.

**How it ships.** Validated by simulation in CI, against populations of known relevant-item prevalence and known duplicate structure: a stated C% bound must hold in at least C% of runs, **including under whichever stopping rule is chosen**. A failing estimator emits the counts-only sentence and no bound (PRD FR-19's `[NOTE FOR PM]`). What simulation cannot validate is that a real discarded set resembles the simulated ones — that is the gold set's job, and it is where the honest residual uncertainty lives.

---

## 9. Security mechanisms — behind PRD FR-47…FR-53

The PRD states the capabilities; §1.5 states why none of them could be bought. What follows is deliberately conservative, because this is the code where invention is the enemy.

- **Password hashing (FR-48).** A current memory-hard function with a per-credential salt and its parameters recorded alongside the hash, so parameters can be raised later and existing credentials re-hashed on next successful authentication. No reversible storage anywhere — a structural property (§10).
- **Sessions (FR-48).** Server-side session records with opaque high-entropy identifiers; absolute and idle lifetimes as configuration-as-data; invalidation on password change, on scope revocation (FR-14) and on sign-out. **Revocation must reach open sessions within a bounded interval**, which is a requirement rather than a nicety and is the one most likely to be implemented as "at next login" by an agent that does not know why it matters.
- **Encryption at rest (FR-47).** In the storage adapters, never in a hosting provider's volume service, because §1.2 forbids the provider. The application therefore holds keys and the hierarchy is real: a data key per tenant, wrapped by a deployment key held outside the data stores (FR-51), rotatable without re-indexing.
- **The scope predicate (FR-14, and §1.5's mitigation).** One query-construction layer, one enforced entry point, scope a required argument with no default value anywhere. This is the highest-leverage architecture decision in the programme after the payload schema, because it is the difference between one place to be wrong and one per call site.
- **Backup and restore (FR-52).** Encrypted, inside the tenant boundary, scheduled and on demand; restore exercised in CI at reduced scale and by documented procedure at the design target; the FR-53 chain verified on restore. The storage-footprint figure is computed by the product because a firm buying one machine needs it before it buys.
- **Audit continuity (FR-53).** A monotonic sequence from a single authority, plus a chain value over the previous entry so that a gap or a truncation is detectable by a reader holding only the export. In a single-machine installation the authority is the application; in a multi-process one it must still be exactly one. An air-gapped site has no NTP, which is why ordering is by sequence and never by clock (PRD A-35).

**The honest note.** All of this is hand-rolled application code written by AI agents and reviewed by one non-hands-on person, in a domain where a mistake is silent and criminal (PRD R-15). The mitigation is the test suite and the structural properties of §10. There is no second mitigation.

---

## 10. The structural properties, as CI checks — PRD FR-56

The PRD names the properties. This names the shape of the check. The tooling is architecture's (§6); the property is not.

| Property (PRD) | Shape of the check |
|---|---|
| No fallback embedder (FR-9) | Import graph: exactly one non-test implementation of the embedder interface; no embedder constructed inside an exception handler in the embedding path; no provider selected by name outside the enumerated list |
| Destructive index operations from one entry point (FR-10) | Call graph: the destructive operations have exactly one caller, the named administrative entry point |
| No post-filter in retrieval (FR-14) | Retrieval has one entry point taking a required scope argument; no result-set post-processing function accepts a scope |
| One chunk write boundary (FR-8) | One writer; scope is a required parameter; no default value for that parameter exists in source |
| No tenant identifier in source (FR-30) | Pattern scan over source for tenant names and identifiers |
| No fixture path (FR-33) | No runtime module imports from the test tree; no runtime module reads a fixture directory; no environment-variable conditional selects a data source |
| No natural-language translation key (FR-34) | Key-shape lint over the string catalogue |
| No hard-coded locale (FR-35) | Pattern scan for locale literals and locale-bound formatting calls |
| No outbound call site outside the adapters (FR-32) | Call graph over the HTTP and socket primitives; the enumerated adapters are the only permitted callers |
| No reversible credential storage (FR-48) | The hashing function has one call site; no encryption or encoding is applied to a credential anywhere |
| No secret in source (FR-51) | Secret scan over source, committed configuration and example configuration |
| No model-reported confidence consumed (FR-42) | No field parsed from a model response is named as, or assigned to, a confidence; the derivation function has one implementation |
| No banned confidence-bound phrasing (FR-23) | Pattern scan over every locale's string set |
| The action registry is complete (FR-21) | Every user-reachable action is registered; an unregistered handler fails the build |
| No emission outside the projection registry (FR-31) | Every projector is registered; no emission path exists outside the registry; the seeded-token test runs per projector |
| No value outside the token set (FR-59) | Pattern scan for colour, spacing and type literals in the client surface |

**Two rules about this table.** A property with no check is not a property (PRD FR-56). And a claim a check cannot decide is replaced by the honest verb — *asserted by review* — never by a weaker check wearing the word "test", which PRD §9 rates the most dangerous inaccuracy available after §0.2.

---

## 11. Viewer, exports and the deliverable — behind PRD FR-44, FR-26, FR-46

- **Rendering runs inside the tenant boundary, always** (PRD FR-44). No hosted conversion or preview service, in any deployment. This constrains the technology more than anything else about the viewer, and it is why the choice is architecture's (§6) rather than the PRD's.
- **`.msg` is the hard case in the viewer exactly as it is in extraction.** Headers, body, reply chain, and navigation into each attachment as its own pièce with a route back to its parent. PRD FR-3 already calls extraction the largest single engineering surface in the increment; rendering the same formats is a second instance of that surface, and the plan should carry both rather than one.
- **Scanned PDF** renders the page image with the OCR text layer positioned over it — because highlighting a passage requires the positions, and because the OCR quality flag has to be visible where the lawyer is reading rather than only in a register.
- **Highlighting and verification are one primitive.** The passage a chunk came from is located by the provenance in the payload schema and verified by exact containment at the moment it is displayed (PRD FR-11). One mechanism serves the viewer, the justification and the audit drawer; a second implementation of it is a defect.
- **Two export tiers, numbers-only by default** (PRD FR-26). The full tier carries retained extracts, override reasons verbatim, justifications and failure-register filenames — an export handed to opposing counsel to substantiate a bound would otherwise disclose the extracts behind every sampled pièce. The tier is chosen before the export is produced, and producing either is recorded.
- **The retained-set export is the deliverable** (PRD FR-46): a numbered, ordered list a lawyer can paste, the basis from which a *bordereau de pièces* is built and not a bordereau. The salvaged mockup (§5) is the design source for the triage table and the audit drawer. It is **not** a design source for this, and nothing designs it yet.

---

## 12. Market judgement carried from the competitive landscape

The PRD carries competitive material **anonymised**, which is right for a build contract. The judgements below name things and therefore live here. Source: `docs/context/04-competitive-landscape.md` §7–§8.

**The value is the service wrapper, not the model.** The CCBE published the recipe and priced the hardware at €2 000–20 000; any technically-minded partner — or their nephew — can now price a DIY alternative. What cannot be assembled that way is *verification against Judilibre and Légifrance, deontological documentation, maintenance, and liability*. A consultancy competes on service depth and proximity or not at all. **In this increment: maintenance is in scope, verification is deferred, the deontological dossier is a document nobody owns, and liability is unaddressed** — carried into PRD §6.3 as a criterion on the cut order, and into PRD OQ-27.

**The SecNumCloud rebuttal — the answer to the hardest single fact against the thesis.** One legal-AI vendor (Haiku) runs on SecNumCloud-qualified infrastructure (S3NS) and sells at €19/month: the strongest sovereignty claim in the market, at a twentieth of any plausible APX price. **The qualification excludes AI services by construction**, so that vendor's inference is not itself qualified — and neither would APX's be, hosted. Nobody can claim end-to-end SecNumCloud without going fully on-premise, **which is precisely the argument on-premise wins**. The landscape document calls this its own highest-value open question and says: *verify it before using it.* PRD OQ-25, and PRD R-8 now carries the rebuttal alongside the threat.

**"If on-premise were viable, why is Relativity killing it?"** Relativity is retiring Server, raised Server pricing on 1 April 2026 to push migration, and requires all new matters on the cloud from 1 January 2028 — after more than 75% of its business had already moved. **The question will be asked, and the answer is *different buyer, different risk*:** Relativity sells to litigation-services providers optimising cost across thousands of matters at scale, for whom cloud is simply cheaper; this product sells to a partner optimising for *secret professionnel* — criminal in Luxembourg — for whom the machine staying inside the walls **is** the purchase rather than a deployment preference. PRD §2.2 names those providers as non-users, which is the answer's first half. Carried as PRD R-16, because the residual is real: one vendor's retreat will be cited as evidence against the whole posture.

**Luxembourg deserves disproportionate attention, and one fact in it is time-boxed.** Luxembourg is the sharpest version of the argument and is barely contested: Art. 458 CP makes breach of professional secrecy a **criminal** offence. **MeluXina-AI** (LuxProvide) — a national sovereign GPU facility with more than 2 100 accelerators — enters service in **H2 2026**, positioned explicitly so that organisations can work with specialised models **without exporting sensitive data**. That is a third option between "hosted US provider" and "buy a box in the firm", in the right jurisdiction, in the same half-year: PRD OQ-20, and PRD §15's requirement that the model-provider adapter admit a locally hosted model without a code change. It also bears on PRD OQ-3 — the Italy signal pulls the third language toward Italian while the jurisdiction the strategy points at is already covered by FR/EN.

**The size of the prize — [UNVERIFIED] in the source, and stated as such.** France has 77 190 lawyers, but 36% practise individually and only 32% are partners in a structure; the Décideurs business-law ranking covers 150 firms in total, around 55% of them with 6–50 lawyers. **No precise census of French firms in the 20–40-lawyer band exists in the source; the order of magnitude is low hundreds at most, many of them Paris business-law firms already being sold to by Harvey and Legora**, plus a smaller number in Luxembourg. This is the input PRD §6.3 argues without: 60 requirements, a permanent ownership tax per feature, three blind deployments per feature — against an addressable base of low hundreds, most of them already in somebody's pipeline. It does not change what to build. It is what makes the cut line arguable rather than merely reluctant.

**0.5–1 FTE of operations per on-premise site.** §4 files this figure as an argument about the buyer's total cost. It is also a statement about **APX's** capacity, and in that register it is the sharpest number in the whole input set: one non-hands-on CTO plus AI agents, and every installation carries half to one full-time person's operations that somebody performs. Carried into PRD §17 and PRD R-1, beside OQ-10's availability contradiction, which it quantifies.
