---
title: "Addendum: APX MVP Product Brief"
status: draft
created: 2026-07-20
updated: 2026-07-20
---

# Addendum — APX MVP Product Brief

Depth that earned a place but does not belong in a 2-page brief. Downstream consumers: `bmad-prd`, `bmad-architecture`.
Mechanism-level detail, the MoSCoW, the salvage list and the v1 trap register live in
`_bmad-output/brainstorming/brainstorm-apx-mvp-rebuild-2026-07-20/brainstorm-intent.md` and are not repeated here.

## 1. No pilot client — the decision, and what it costs

**Superseding fact, established 20 July 2026: no engagement has been won.** The prospect whose *ordonnance 145 CPC* triage need drove the original discovery did not convert. Earlier project artefacts (`state.json`, the context pack) record that relationship as live and should be read as stale on this point. The product is therefore built for the **use case**, not for a named firm, and client names are deliberately absent from the brief.

Requirements collected during discovery are retained on their merits, not their provenance:
- **Random-sampling auditability**, from a senior lawyer acting as the firm's sceptic. This turned out to be the statistically correct way to bound what triage discarded — it is now the product's north-star criterion.
- **Cell-by-cell editing with no destructive regeneration**, from a practising associate. This turned out to be the architectural invariant of the whole system, not a UI preference.

**What is genuinely given up.** No pilot means no weekly reality check, and the product can drift toward what is buildable rather than what is wanted — a drift that restates precisely how v1 went wrong. Classification quality will be measured against public benchmarks rather than a practitioner's judgement of their own matter. Benchmarks make the product *measurable*; they do not make it *wanted*.

**Highest-value acquisition for this increment:** one real anonymised litigation matter, from any friendly practitioner, on any terms. No signed engagement is required. Ask by shape and volume, not in the abstract — "one closed matter, 200+ pieces, mostly email, anonymised however you like" is a request a practitioner can act on; "some documents" is not. That framing failure is the most likely reason nothing ever arrived before.

## 2. The corpus strategy — how triage gets built without a client

v1's mistake was conflating **real content** with **real mess**, and then fabricating both. Separating them resolves the problem: no single source has to supply everything, and none of them has to be invented.

| Need | Source | Notes for the PRD |
|---|---|---|
| **Real mess at volume** — genuine threading, duplicates, attachments, dead ends | **Enron / EDRM corpus**, ~500 000 real business emails, public since the FERC release; the canonical e-discovery dataset | Real human correspondence. English — limits *language* realism, not *pipeline* realism. Verify the licence terms of the specific distribution used. |
| **A measurable recall target** | **TREC Legal Track** collections, built for e-discovery evaluation with human relevance judgments | Gives the sampling confidence bound something real to be scored against. v1 had a gold set and never ran it. |
| **French-language realism** | Real French public legal and administrative text, **mechanically degraded**: rendered to skewed scans, wrapped in `.msg` with plausible headers and reply chains, duplicated with variations, a fraction deliberately corrupted | The content is real; only the degradation is manufactured — and degradation is the thing under test. Categorically different from fabricating documents. |
| **A small genuinely-owned dump** | APX Advisory's own mail, proposals and project files | Tiny, but unquestionably real and owned. Useful as a smoke test. |

**Rule carried forward from v1:** whatever corpus is used, it enters through the same code path as client data. No fixture layer, no demo branch, no `withDemo()`. The corpus is a *data source*, swappable by configuration — never a fallback that can silently override a working system.

## 3. The infrastructure contradiction, and the rule that resolves it

- **Stated posture:** EU-only, only-code-travels, on-premise, VS Code-style local packaging.
- **Chosen build stack:** Supabase, Vercel, Railway — all US-operated, none installable at a firm.

The two do not reconcile as a *deployment* story. They reconcile as a *development* story:

> Supabase, Vercel and Railway are acceptable for development and for a future hosted tier.
> **The core must carry no hard dependency on any of them.**

Concretely, for the PRD and the architecture:

| Acceptable | Not acceptable |
|---|---|
| Plain PostgreSQL (Supabase is just Postgres underneath) | Supabase Auth as the identity layer |
| Object storage behind an interface | Supabase Row-Level Security as the RBAC implementation |
| Next.js deployed on Vercel | Vercel-specific runtime primitives in application code |
| A worker process on Railway | Railway-specific queueing or scheduling semantics |

Write the test down as an architecture fitness function: *can this run, unmodified, on a single machine inside a law firm with no internet connection?* Anything that fails it is a dependency to be pushed behind an adapter.

Same shape as the provider-agnostic LLM adapter that makes the Cloud Act question reversible. The pattern: **anything that could be compelled, priced or discontinued by a third party lives behind an interface.**

## 4. Capacity, and what it does to sequencing

The team is Julian (CTO, self-described as not hands-on technically) plus AI agents. That is the real headcount, and the brief says so.

Implications the PRD should absorb rather than discover:

- **Tests are not optional overhead here; they are the substitute for the engineers who are not on the team.** An AI-driven build with no test suite is v1 again, faster. v1 ran ~80% untested with `make test` erroring outright.
- **Sequencing should front-load the irreversible.** The payload schema is the only true lock-in. Everything else — LLM provider, hosting, embedder, UI — is replaceable behind an adapter. Getting the schema right on day one is worth more than any three features.
- **The MUST list is large for this capacity.** It is not padded — each item traces to a promise made to a lawyer — but it should be sequenced against the spine (schema → ingestion → index → retrieval measured → checker → drafting → export) rather than attacked breadth-first.
- **"It's just tokens" is the identified failure belief.** Generating is free; owning is not. Each shipped feature is a permanent tax: tested, migrated blind at every client site, defensible in court, supportable by phone with no telemetry.

## 5. Market signal — Italy

**Several Italian firms are in discussion with the other APX partners.** This appears in no other project artefact — not in `state.json`, not in the context pack, not in the brainstorming session. It is new information as of 2026-07-20.

Consequences worth carrying:
- i18n scope moves from FR/EN toward **FR/EN/IT**. The brief holds FR/EN as MUST; Italian should be a PRD question, not an assumption.
- The context pack recorded one Italian prospect with ~15 years of documents on a physical server in Italy. That is an on-premise deployment, not a hosted one, and it reinforces the local-first packaging direction.
- The signal grounds the "clients in Italy, France and the USA" vision in something real rather than aspirational.

## 6. The three stakeholders

**The associate** — the daily user. Non-technical, works under deadline, opens the tool at inconvenient hours. Adoption is voluntary in practice: no partner can make someone use a tool that adds friction; they simply route around it. Her requirement is negative — *do not make me look stupid, do not lose my edits, do not make me check your work.*

**The partner** — signs, does not use. Buys capacity, margin and competitive standing. Vulnerable to the billable-hour paradox: efficiency shrinks the invoice unless the firm shifts to fixed fees or absorbs more volume.

**The sceptic** — the Emmanuel figure. A senior lawyer whose function is to distrust the machine on the firm's behalf. Not an obstacle: he is the mechanism by which the firm gets comfortable, and he is the source of the random-sampling requirement in §1. Design *for* him and the other two follow.

The unresolved narrative question — headcount reduction vs capacity expansion — determines whether the associate and the partner are on the same side. It belongs to the APX partners.

## 7. Deferred, with reasons

| Deferred | Why, and what it costs |
|---|---|
| **Triage module** | Sits in COULD despite being the stronger commercial story (it unlocks matters a firm currently declines). Cost of deferring: the easiest sale is not available in the first increment. Accepted knowingly. |
| **Admin cockpit** | Nothing to operate until clients are installed. Its foundation — configuration-as-data — is MUST, so only the interface waits. |
| **On-premise update delivery** | The genuinely unsolved problem. Deferring it is correct for a first increment, but not past the second client: version drift across blind installations compounds. |
| **Fully local model** | The premium sovereign tier. Only worth building once a firm refuses the hosted LLM in writing. |
