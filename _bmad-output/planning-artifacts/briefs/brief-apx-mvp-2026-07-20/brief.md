---
title: "Product Brief: APX MVP"
status: draft
created: 2026-07-20
updated: 2026-07-20
---

# Product Brief: APX MVP

*Purpose: internal build-scoping — sharpen what the product is and what gets coded. Not an investor or client document.*
*Depth lives in `addendum.md` and in `_bmad-output/brainstorming/.../brainstorm-intent.md`.*

## Executive Summary

APX sells AI to law firms in France, Luxembourg and — newly — Italy. A first implementation exists and works well enough to demo. It is being rebuilt from the foundations, because a demo and a deliverable turned out to be two different products, and only the first one got built.

The rebuild has one organising principle: **v1 built what can be shown; v2 builds what can be proven.** Every claim the product makes to a lawyer — this citation is real, this quote is exact, nothing relevant was discarded, a human validated this, no data left the firm — must be backed by a deterministic, testable mechanism rather than by an intention written in a specification. In v1 those claims were sold in two client proposals and implemented in zero lines of code.

The first increment is **triage**: turning an undifferentiated dump of a firm's matter — 1 700 pieces, mostly `.msg`, or four years of a practice — into a ranked, reversible, auditable working set, with a measured statement of what was set aside and how confident we are that nothing decisive was lost. Nothing is ever deleted; the tool commits to a line and the lawyer moves it.

This choice was revised against market evidence (`docs/context/04-competitive-landscape.md`, 20 July 2026). Drafting over a firm's corpus is the most contested space in the market — Septeo reaches 7 500 French firms with essentially this product, Haiku sells it at €19/month — while **triage for European firms under 50 lawyers is empty**: *ordonnance 145 CPC* review goes to FTI, EY and KLDiscovery at consulting rates, and no French-language sovereign tool addresses it. Triage also unlocks the strongest revenue story: matters a firm currently declines or under-prices because the review cost is prohibitive. Syllogisme moves to the next increment, on the same spine.

## The Problem

A lawyer with a deadline has three bad options: read everything (impossible at 1 700 pieces for one matter, let alone four years of a practice), skim and hope, or pay an associate to do the skimming. Today they skim. The honest baseline for any tool here is not perfect human review — it is what actually happens on a Friday evening under deadline pressure.

Generic AI does not solve this, for reasons specific to the profession:

- **A fabricated citation is a career event.** Courts have sanctioned lawyers for it. A tool that is usually right is not usable, because the failure is not "a bad answer" — it is a professional liability the lawyer personally carries.
- **Confidentiality is not a preference.** Matters are walled off from each other by professional-conduct rules. A tool that retrieves across those walls creates a violation silently, with no error message.
- **The firm's voice is part of the product they sell.** A document that does not read like the firm's work is not a draft — it is a rewrite waiting to happen, and the time saving evaporates.

So firms either stay out, or adopt a generic tool and quietly carry a risk nobody has priced.

## The Solution

One workspace, three verbs — **consult / add / draft** — with regulatory *veille* as a separate module. The three previously-separate tools dissolve into this; triage stops being a product and becomes "add documents" plus a review queue.

Two properties define the experience:

**The home screen answers "what needs you?", not "what can I do?"** It opens on a worklist: what failed to import, what needs re-reading, which matters are moving. Human-in-the-loop stops being a policy statement and becomes a queue with items in it. Every line is an action in the lawyer's language, never a technical state.

**Onboarding is a folder.** USB key, select the directory holding four years of the practice, done. No connector, no API, no IT project, no meeting with their systems people. The import runs in the background while the lawyer keeps working, and hands back a list of the things that need a human plus a summary of what happened.

Underneath, the product is split into two engines with deliberately different truth status: one that **finds** (semantic, ranked, suggestive) and one that **proves** (deterministic, exhaustive, verifiable). The interface must never let them be confused, because only the second can support the sentence a lawyer needs to be able to say: *exact search over the entire indexed corpus, zero occurrences.*

## What Makes This Different

*Benchmarked against `docs/context/04-competitive-landscape.md` (20 July 2026, 70 sourced links).*

**The feature is not the moat, and the market proves it.** Septeo Brain already does drafting and Q&A over a firm's own case files, claims 100%-France sovereign hosting, and restricts retrieval to internal documents for exactly the reason APX would — and it reaches **7 500 French firms** through the practice-management software they already pay for. Haiku sells corpus-indexing legal AI at **€19/month** on SecNumCloud-qualified infrastructure. On features and on price, this space is occupied.

What is genuinely empty is narrower and harder to copy:

**Nobody productises on-premise legal AI for 20–40-lawyer firms.** Mistral and Aleph Alpha sell enterprise contracts with no small-firm references; Noxtua is sovereign SaaS. The hole is real, and it exists for an economic reason — no small firm reaches the GPU utilisation where on-premise wins on cost. Which means the sale is never TCO. **The sale is risk elimination for a specific confidentiality-critical workflow**: *ordonnance 145 CPC* review, criminal defence, sensitive M&A, Luxembourg private wealth.

**Nobody meets the CNB's own March 2026 criteria.** EU location, non-US ownership of both infrastructure *and* model provider, systematic verification — GenIA-L runs on OpenAI, Legora's sub-processor list names OpenAI, Ordalie and Jimini decline to name theirs. Running inside the firm's walls satisfies all three by construction. This is a *deontological* argument, which is the argument French avocats actually respond to.

**Citation verification, scoped honestly.** Tier (a) — *the authority exists* — is deterministic, free via Judilibre and Légifrance, and differentiating only because competitors do not foreground it. Tier (b) — *still good law* — needs a citator APX does not own. Tier (c) — *the authority supports the proposition* — is unsolved by everyone per the 2026 benchmarks. **Claim (a). Be explicit about (b) and (c). Never publish an unaudited hallucination rate.**

**Luxembourg is the sharpest version of the whole argument** and is barely contested: professional secrecy is a *criminal* obligation there (Art. 458 CP, not merely deontological), there is one small local player, no published bar guidance, and MeluXina-AI — a national sovereign GPU facility — enters service in H2 2026.

The defensible position, in one sentence: *the only French provider that will install a legal AI inside your walls, where nothing leaves, verified against free public sources, documented so your bâtonnier and your insurer can both sign off.*

> **What this rules out.** APX cannot compete on corpus depth — Lefebvre Dalloz has 200 years of doctrine and RELX is acquiring Doctrine. It must never present itself as a research tool. And it cannot win on distribution against an incumbent already inside 7 500 firms.

## Who This Serves

**The user is not the buyer, and they want different things.** Ignoring that is the single most reliable way legal-tech products fail.

| | Wants | Risk if ignored |
|---|---|---|
| **The associate** (uses it daily, non-technical, evenings and deadlines) | To stop doing the tedious part; to not be embarrassed by output | Adoption is voluntary in practice — she routes around a tool that adds work |
| **The partner** (signs the cheque) | Capacity, margin, competitive standing | Without a revenue story, this is a cost line that gets cut |
| **The sceptic** — a senior lawyer whose function is to audit the machine | To verify rather than trust | The gatekeeper. "Auditability is non-negotiable" is a direct quote from discovery |

The product must serve all three, and the narrative must not promise the partner headcount reduction while promising the associate a better job. Those are two different products. **[ASSUMPTION]** The brief assumes the *"same associates, more matters"* narrative — capacity expansion, not headcount reduction — because the alternative gives the daily user a reason to sabotage it. Flag if APX intends otherwise; this belongs to the partners, not the CTO.

**Which firms, though.** Not firms shopping for a productivity tool — that market is served at €19–80/month by vendors already inside the practice-management software. The buyer is a firm with a **specific confidentiality problem it can name**: the four workflows listed under *What Makes This Different*. The addressable base is correspondingly small — the order of magnitude is low hundreds of French firms in the 20–40-lawyer band, many of them Paris business-law firms already being sold to by Harvey and Legora. Luxembourg is smaller still but far less contested.

## Success Criteria

1. **A defensible sentence about what was set aside.** *"200 pieces sampled at random from the 1 400 discarded, 0 relevant; risk of having missed a relevant document below 1.5%."* This is the north star: it converts "recall over precision" from an intention into a number a lawyer can say to a client or to a judge. It is also the direct answer to the only named non-negotiable requirement APX has ever received from a client.
2. **Nothing is ever destroyed, structurally.** One ranked list underneath; the visible piles are a *view* over that order. Reversibility is not a promise to keep but a property that cannot be violated.
3. **The tool commits.** It draws the line and says "in my view, everything above this" — a ranked list that refuses to decide pushes the judgement back onto the lawyer, which is precisely what she is paying to avoid. Moving the line is priced: *"read 400 more pieces and your risk falls from 3% to 0.4%."*
4. **Retrieval and classification measured against the gold eval set** that already exists in v1 and was never once executed.
5. **The inventory guarantee holds.** *"100 000 submitted / 97 200 indexed / 2 800 unreadable, listed one by one."* Without it, no claim of exhaustive search is honest.
6. **Installed and running at a real firm** on their own documents. Not demoed — installed.

*(The blind two-document test remains the north star for Syllogisme and moves with it to the next increment, along with the style profile and statistical fingerprint.)*

## Scope

**Shared spine — unchanged by the pivot, and the majority of the work.** Frozen payload schema with RBAC as a query pre-filter · resumable, idempotent ingestion with a queue and a **failure register** · a real semantic embedder that fails loudly · exhaustive deterministic search alongside semantic · the audit record with reasoned overrides · tenant isolation and configuration-as-data · folder ingestion · **FR/EN i18n done properly** · retrieval measured in CI.

**Triage layer — in.** Per-document confidence and a one-line reversible justification · the single ranked order with a committed, movable line · the editable cell-by-cell table with a live before→after change log (no destructive regeneration) · random-sampling audit with a confidence bound · the audit drawer.

**Out (deliberately):** Syllogisme drafting, `.docx` style export and the style profile *(next increment)* · shared SaaS hosting · the admin cockpit · auto-update delivery · a fully local model · fine-tuning · live connectors · **and the fixture layer, which is deleted rather than disabled.**

Design target: **100 000 documents**.

> **Scoping decision, revised 20 July 2026.** The first increment was originally Syllogisme, on the argument that it is the deepest vertical slice. Two independent signals reversed it — the commercial analysis during the brainstorming session, then the competitive research — and both point the same way: Syllogisme is the crowded field, triage is the empty one. **The reversal is cheaper than it looks**: the spine above is common to both, so most of the work is unchanged and Syllogisme follows on the same foundation. What is genuinely lost is the depth-forcing property of the original choice — triage does not require the citation checker or the drafting surface, so those must now be sequenced deliberately rather than arriving as a side effect.

## Constraints & Capacity

**The team is one non-hands-on CTO plus AI agents.** No other engineers. This is the binding constraint on everything above, and it deserves to be said plainly rather than discovered in October: the "in scope" list is large for that capacity, and the belief that made v1 fail — *"it's just tokens"* — is precisely the belief this capacity makes tempting. Writing code is nearly free. Owning it is not: every feature must be tested, migrated blind against a 100 000-document index at each client site, defended in front of a judge, and supported by phone with no telemetry.

**Infrastructure:** Supabase, Vercel, Railway — minimal cost, fast to move. These are US-operated and the opposite of on-premise, which contradicts the sovereignty posture. Resolution: they are acceptable as the *development and hosted-tier* platform, on one condition — **the core carries no hard dependency on them.** Plain Postgres, yes. Supabase-proprietary auth and RLS, no, or on-premise installation becomes impossible later.

**Inherited and not up for debate:** EU-only · zero-retention · no fine-tuning on client data · human-in-the-loop everywhere · never hard-delete · recall over precision · full audit trail · RBAC by matter · only code travels.

**No pilot client, and no client corpus.** No engagement has been won. The product is built for the *use case* — mass-document review in litigation — not for a named firm. Requirements gathered in discovery (random-sampling auditability; cell-by-cell editing with no destructive regeneration) are kept because they are correct, not because a particular firm asked for them.

**This makes the corpus the first real engineering problem, not an afterthought.** The public-corpus move — Légifrance and Judilibre via PISTE, EUR-Lex, HUDOC, Legilux — solved the fake-data problem for drafting and *veille*. It does **not** solve it for triage: public case law is clean, structured and uniformly relevant, the exact opposite of the undifferentiated dump that triage exists to survive. And synthetic documents are precisely what produced v1.

The resolution is to separate two things v1 conflated — **real content** and **real mess**:

| Need | Source | Why it is legitimate |
|---|---|---|
| Real mess, real threading, real duplicates, at volume | **Enron / EDRM corpus** — 500 000+ genuine business emails with attachments, threads and duplicates, public since the FERC release; the canonical dataset of the e-discovery field | Actual human correspondence, not generated. Messy for the right reasons. English, which limits language realism but not pipeline realism. |
| A gold standard for measuring recall | **TREC Legal Track collections** — built for e-discovery evaluation, with human relevance judgments | Gives the sampling confidence bound something real to be measured against, which v1 never had |
| French-language realism for demos and for the classifier | Real French public legal and administrative text, **mechanically degraded**: rendered as skewed scans, wrapped in `.msg` with realistic headers and reply chains, duplicated with variations, some deliberately corrupted | The *content* is real; only the *degradation* is manufactured — and degradation is exactly the thing under test. This is categorically different from fabricating documents. |

**Accepted risk, stated plainly:** without a firm looking at the output, classification quality is measured against public benchmarks rather than against a practitioner's judgement of their own matter. The benchmarks make the product measurable; they do not make it *wanted*. Getting one real anonymised matter — from any friendly practitioner, on any terms — remains the single highest-value acquisition for this increment.

## Open Decisions

Carried forward unresolved. The first two belong to the APX partners, not to the CTO.

| Decision | The tension |
|---|---|
| **Consulting forfait vs subscription** | The locked ADR says forfait, no licences, no subscription — yet the P&P quote prices only monthly recurring cost with no development forfait at all. **The market research now points hard at forfait**: this is a consultancy with a software artefact, not a SaaS, and it cannot win a per-seat price war against €19/month. But APX must be able to justify its number in one sentence against a buyer reference price of €7k–79k/yr — and against the CCBE publicly pricing the hardware at €2 000–20 000. *The consultancy posture also makes configuration-as-data more urgent, not less: a consultancy says yes to bespoke requests, and every yes becomes a code fork unless configuration absorbs it.* |
| **The commercial narrative** | Fewer associates, or the same associates handling more matters. Cannot be both. |
| **Cloud Act acceptability** | "EU region" is not sufficient against a US-operated provider. Mitigated but not resolved by the provider-agnostic adapter, which makes the choice reversible as a config line. The strongest available evidence for the pitch is Microsoft France's sworn Senate testimony that it cannot guarantee data stays out of US hands. |
| ~~**AI Act qualification**~~ — **downgraded, not open** | Research answer: legal AI sold to law firms is very likely **outside** Annex III high-risk (that provision covers judicial authorities), and the high-risk regime was deferred to 2 December 2027 by the Digital Omnibus. Art. 50 transparency applies from 2 August 2026. **Leading with "AI Act compliance" now signals APX has not read the Omnibus.** Replace it with the CNB March 2026 guide and *secret professionnel* (Art. 226-13 CP France / Art. 458 CP Luxembourg). Still worth a lawyer's confirmation — but it is no longer a blocking question. |
| **Does the demand exist?** | Time saved only becomes revenue if the firm is turning work away. Sharpest qualifying question for any prospect: *"Refusez-vous des dossiers aujourd'hui ?"* Aggravated by the billable hour, where saving three hours shrinks the invoice. |
| **On-premise update delivery** | The one genuinely unsolved technical problem: signed, offline-installable, reversible migrations against a live 100 000-document index. Deferred out of this increment, not solved. |

## Vision

If this works, APX is the firm's own reasoning made verifiable: documents go in, cited work comes out, nothing the machine asserts is unprovable, and nothing crosses the wall.

**But the shape of that success needs saying plainly, because the research contradicts the instinct.** This is a services business with a software artefact — a few dozen French firms and a smaller number in Luxembourg, sold as engagements to firms with a confidentiality problem they can name. It is not a platform every French lawyer subscribes to; that market is being taken by vendors with venture capital and existing distribution. A plan priced and staffed as a SaaS and a plan priced and staffed as a consultancy are two different companies, and APX should be honest with itself about which one it is building.

That is a smaller vision than "without APX you cannot be a law firm". It is also the one the evidence supports — and **Luxembourg deserves disproportionate attention within it**, for the reasons set out above.

The ambition still carries a price worth naming now, while it is cheap to name. Infrastructure is not allowed to break: a firm that misses a filing deadline because APX was down does not send a support ticket. The same discipline that makes the citation checker deterministic — mechanisms over intentions, tests over promises — is what earns the right to be installed behind a law firm's walls at all.

And the failure mode is precisely as concrete: leaked client data, or a decision overturned because a machine wrote a citation a human signed without reading. Both headlines are already written. The product is the argument against them.
