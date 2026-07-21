---
title: "Adversarial Review — APX MVP PRD, First Increment (Mass-Document Triage)"
status: draft
created: 2026-07-21
reviewer: adversarial (hostile)
target: prd.md + addendum.md (prd-apx-mvp-2026-07-20)
---

# Adversarial Review — PRD: APX MVP, First Increment

**Posture.** This review is hostile by design. It assumes the document is wrong until proven otherwise and reports only what is broken, missing, unprovable or self-contradicting. Nothing here is praise. A short section at the end (§8) lists things a naive reviewer would flag that are in fact correct, so the author does not waste time defending them.

**Overall verdict.** This is a disciplined, unusually self-aware PRD that has correctly diagnosed *why* v1 failed and has built a great deal of machinery to prevent the same failure. It nonetheless contains one mathematically false claim at the centre of its north-star metric, has no specified input for the ranking that is the entire product, and specifies no security requirements at all for a product sold on criminal-law confidentiality. It has also — in a document whose own top risk is "scope exceeds capacity" — accepted a scope that one non-hands-on CTO cannot deliver in this shape without silently dropping the parts nobody can see.

The document's characteristic failure mode is **over-claiming testability**. It repeatedly writes "Asserted by test" against properties that no test can decide. That is a milder version of the exact sin it convicts v1 of: documentation that lies in load-bearing places (§17). If the CI suite is the substitute for the engineers who are not on the team (§9), then the CI story must be literally true, and in several places it is not.

---

## 1. Findings, ranked by damage if left unfixed

### F1 — CRITICAL — The *confidence bound* sentence is not a true statement of the statistics. The north star is the liability.
**Where:** §3 Glossary (*Confidence bound*), §2.3 UJ-2 Climax, FR-23, SM-1, R-5.

The sentence written verbatim into the glossary, into UJ-2, into FR-23 and into the north-star metric is:

> *"200 pièces sampled at random from the 1 400 in the discarded set, 0 relevant; risk of having missed a relevant document below 1.5%."*

The 1.5% is evidently the rule of three (3/n = 3/200). The rule of three bounds **prevalence**: with 95% confidence, no more than ~1.5% of the discarded set is relevant. Applied to 1 400 documents, that is **up to 21 relevant documents still sitting in the discarded set**.

The sentence does not say that. It says *"risk of having missed a relevant document below 1.5%"* — which a lawyer, a client and a judge will all read as *P(at least one relevant document was missed) < 1.5%*. That statement is false, and not marginally. To be 95% confident that **zero** relevant documents remain in a discarded set of 1 400, having found zero, the hypergeometric requires (M−n)/M ≤ 0.05, i.e. **n ≥ 1 330 of 1 400**. The lawyer would have to read 95% of the pile the product exists to let her not read.

Consequences:

1. **The product's differentiating sentence cannot mean what it says.** The true sentence — *"with 95% confidence, no more than 21 relevant documents remain among the 1 400 set aside"* — is a materially less comforting thing to say to a client, and it is the thing that is actually supportable. Whether the product still sells on the true sentence is a commercial question the PRD has never asked, because it has been carrying the false one since the brief.
2. **R-5 understates the risk.** R-5 says the confidence bound "is wrong or misapplied" is a *Medium-high, under-specified* risk mitigated by OQ-4 needing a statistician. That framing implies the estimator is merely unchosen. It is worse: the **estimand** — what quantity the sentence asserts — is already chosen, already written into three FRs and a glossary entry, and is already wrong. A statistician cannot fix an estimator when the sentence it must produce is a category error.
3. **SM-1 is a reproducibility test, not a correctness test.** SM-1 targets "100% reproducibility, asserted by an automated test that recomputes from the export and compares." A test that recomputes a wrong number and gets the same wrong number passes. Nothing in the PRD validates that the bound is *sound*. That is precisely the v1 pattern in a new costume: a green test proving a mechanism ran, standing in for a proof that the mechanism is right.
4. **FR-19's priced statement inherits the same defect and adds a second one.** *"400 more pièces to read; risk falls from 3% to 0.4%"* is a projection at a candidate line position where **nothing has been sampled**. That figure is not a sampling bound at all — it is a calibrated probability derived from ranking scores. Calibration requires labelled data from a comparable corpus. The only labelled corpus in the plan is TREC Legal Track (English, e-discovery, a different task and a different relevance definition from *ordonnance 145 CPC* review). There is no requirement anywhere that the projected risk figure be **calibration-tested**, and no metric that would catch it being systematically optimistic. A systematically optimistic priced statement is the single most dangerous artefact this product can produce, because FR-19 requires it to be **recorded in the audit record at the moment of the move** — see F17.

**Required fixes (all cheap now, none cheap later):**
- Replace the sentence template in the glossary, UJ-2, FR-23 and SM-1 with one that states the estimand correctly, and state the confidence level explicitly (the current sentence states a bound with no confidence level attached, which is meaningless).
- Add an FR consequence: the sentence must name its confidence level and its estimand, and must never use the phrase "risk of having missed a relevant document" for a prevalence bound.
- Add a metric: the projected risk figure of FR-19 is validated against realised outcomes on the gold set (a calibration check), and a systematically optimistic projection fails the build.
- Escalate R-5 to High and move OQ-4 from "needs a statistician's answer" to a **blocking prerequisite** on FR-19 and FR-23. The addendum §6 already says this; the PRD's risk table does not agree with it.

---

### F2 — CRITICAL — The ranking has no specified input. Nothing in the document says what "relevant" means or where that judgement comes from.
**Where:** FR-1, FR-16, FR-17, FR-18, §4.4 as a whole, UJ-1.

This is the largest hole in the document, and it is invisible because everything around it is so carefully specified.

FR-1 states that starting an *import job* requires **exactly three user inputs** — the folder, the *matter*, the *RBAC scope* — and that "no further mandatory configuration screen exists on this path". UJ-1 reinforces it: "no connector, no API, no import wizard".

FR-17 then requires the system to draw **the line** — to commit to "in my view, everything above this". FR-18 requires every pièce to carry a confidence and a one-line justification. SM-2 measures **recall at the line**. SM-C1 counts relevant items below the line.

Relevant *to what*? The system has been told a folder path, a matter name and an access predicate. It has not been told what the case is about, what the legal question is, what period matters, who the parties are, what the *ordonnance 145* authorises seizure of, or what the associate is looking for. There is **no requirement anywhere in §4 that captures a relevance criterion**, and FR-1 affirmatively forbids asking for one on the ingestion path.

Only two things can be true:

- **(a) The ranking is generic.** It ranks by some corpus-intrinsic notion of importance — document type, recency, thread centrality, named-entity density, the v1 nine-label taxonomy (OQ-16). This is astrology with a confidence score attached. It cannot be validated against any matter-specific gold standard, its per-pièce "justification" (FR-18) will be a fluent restatement of the document rather than a reason, and SM-2's recall figure will measure the ranker against TREC's notion of relevance, which is not this user's. R-11 worries the justification may be "fluent-but-empty"; if there is no relevance criterion, the justification is *necessarily* empty, because there is nothing for it to be a justification relative to.
- **(b) The ranking secretly requires a matter description or a query**, in which case FR-1 is wrong, UJ-1 is wrong, the "one gesture" onboarding story is wrong, and a whole feature — capturing, versioning, translating and auditing the relevance criterion — is missing from §4, from §6.1, from the addendum §3.3 sequence and from every estimate.

Note what (b) implies downstream, all of it unspecified: the criterion is an input to the ranking, so it must be **versioned** (FR-16 versions rankings but not criteria), must appear in the **audit record** (FR-24 lists nine recorded items; the relevance criterion is not among them), must be **bound to the confidence bound** (FR-23 binds the bound to the matter, the ranking version and the line position — not to the criterion it was ranked against), and must be **exported** (FR-26, §13). A reader of the exported audit record cannot currently answer *"relevant to what question?"* — which is the first question anyone contesting the triage will ask.

**Required fix:** decide (a) or (b) explicitly and write it down. If (b), add an FR for the relevance criterion — its capture, its language, its versioning, its presence in the audit record and the export, and its binding to every ranking version, every line position and every confidence bound. If (a), say so plainly in §4.4 and accept that SM-2 measures a generic ranker, and rewrite §1's claim that the tool "draws the line" so it does not imply matter-specific judgement.

---

### F3 — CRITICAL — "Exhaustive" is not exhaustive. The v1 "guess in the costume of a proof" defect has been reintroduced one layer down.
**Where:** §3 Glossary (*Truth status*), FR-13, FR-6, FR-3, FR-11, §4.3 preamble.

§4.3 is written to kill one specific v1 defect: a score threshold dressed up as a proof of absence. It succeeds at that. It then builds a new proof-of-absence claim on three unexamined foundations, each of which makes the claim false.

**(a) OCR.** FR-3 requires scanned PDFs and images to be indexed via OCR, and requires that OCR output *below a configured quality signal* be **"indexed and flagged, not discarded"**. So the *corpus* — by the glossary's own definition, "all pièces successfully indexed" — contains transcriptions that are known to be unreliable. FR-13 then declares a deterministic search over that corpus **exhaustive**, "the only mechanism in the product that can support a claim of absence", and FR-6 requires exhaustive results to carry the *denominator*, i.e. the **failure register** count.

The failure register is the wrong qualifier. A pièce whose OCR produced garbage is a *success*: it is in the corpus, it is not in the failure register, and it therefore does not appear in the qualification attached to the absence claim. The product can print *"exact search over the entire indexed corpus, zero occurrences"* over a corpus in which some arbitrary fraction of pages are unreadable transcriptions, and the sentence carries no trace of that fact. This is exactly a guess wearing the costume of a proof — the thing §4.3 exists to prevent — merely relocated from the retrieval layer to the extraction layer, where nobody was looking.

**(b) Chunking.** FR-11 requires deterministic chunking with provenance. FR-13 requires a "complete match set". Nothing says which text an exhaustive query runs over. If it runs over *chunks*, a phrase or proximity match spanning a chunk boundary is **missed by construction**, and completeness is false. If it runs over full pièce text, then that text must be stored separately from the chunks and FR-8's payload schema does not mention it.

**(c) "A deterministic expression" is undefined.** FR-13 places the product's entire absence claim on a term that appears once and is never specified. Over French legal text and OCR output, every one of the following silently changes what "the complete match set" means, and none is decided: diacritics and their loss in OCR; case; elision (*l'article* / *article*); ligatures and hyphenation across line breaks in scanned PDFs; stemming and lemmatisation; whitespace normalisation; whether the expression supports boolean, proximity, wildcards or regex. Opposing counsel does not need a technical expert to break this — they need one document in which the word appears with an accent the OCR dropped.

**(d) The absence statement omits its RBAC scope.** FR-13's own body says the result is complete "over the whole indexed *corpus* within their *RBAC scope*" — correct. But its third testable consequence says a zero-result query yields "an explicit statement of absence, scoped to the indexed *corpus* and qualified by the *failure register* count". Scope is dropped. The glossary entry for *truth status* — the definition downstream workflows will build from — says "complete match set over the whole indexed *corpus* within *RBAC scope*" in one breath and calls it "the only thing that can prove an absence" in the next. The exported sentence a lawyer will actually rely on is therefore an absence claim over *the subset that one user was permitted to see*, presented in the vocabulary of an absence claim over everything. See also F10.

**Required fixes:**
- Every **exhaustive** result set and every absence statement must carry, alongside the failure register count: the count of pièces in the searched set whose text was derived by OCR, and the count flagged below the OCR quality signal. An absence claim that cannot state these is not exhaustive.
- Specify whether exhaustive search runs over chunk text or full pièce text, and if over chunks, state and test the boundary-spanning behaviour.
- Specify the normalisation semantics of a "deterministic expression" (accents, case, elision, hyphenation, whitespace) as testable consequences of FR-13. This is not an architecture decision; it is the definition of the guarantee.
- Every absence statement must disclose that it is scope-limited, and must say so in the exported wording, not only in the record.

---

### F4 — CRITICAL — There are no security requirements. None.
**Where:** §9, §10, §11, §12, §16, §17 — by absence.

The product is sold on *secret professionnel* — a **criminal** obligation in Luxembourg (Art. 458 CP), as §12 correctly notes. §12 cites GDPR Art. 32, "security of processing", by name. The PRD then specifies **not one security measure**.

Absent entirely, with no FR, no NFR, no open question and no assumption tag:

- **Encryption at rest.** Nothing. The product builds a single consolidated, fully-indexed, cross-matter searchable copy of a firm's most sensitive material on one machine, and never says it must be encrypted.
- **Authentication.** Every user journey begins "Authenticated" and no requirement says how. No password policy, no session lifetime, no MFA, no account lockout, no credential storage requirement. The addendum §1.2 explicitly forbids Supabase Auth as the identity layer — i.e. it removes the off-the-shelf option and replaces it with nothing. FR-29 says identity is "a property of the application"; that is a deployment constraint, not a security requirement.
- **Authorisation administration.** Who grants an RBAC scope? On what authority? Recorded where? FR-14 and FR-29 specify enforcement exhaustively and grant-time not at all. A Chinese wall that anyone can widen is not a wall.
- **Backup, restore, disaster recovery.** Nothing, anywhere. One machine, inside a firm, 100 000 documents, an append-only audit record with asserted legal weight, no telemetry, no ops staff, no SLA (§17), 0.5–1 FTE of operations acknowledged as needed in the addendum §4 and not staffed. A disk failure destroys the audit record the firm may need in front of a *bâtonnier*. This is the single most likely way this product ends a client relationship, and it does not appear in §16, §17, §18 or the open questions.
- **Key management** for the model-provider credentials, held on-premise, at a site APX cannot see, with no rotation mechanism and no telemetry to detect misuse.
- **Insider threat.** The product's entire premise is that matters are walled from each other. The obvious attack is a firm insider, and there is no threat model, no anomaly requirement, and no requirement that FR-24's retrieval log (which does record every query with its RBAC scope — good) is ever *reviewable* by anyone.
- **Risk concentration.** An *ordonnance 145 CPC* or a *perquisition* at the firm now finds one indexed, searchable, deduplicated appliance instead of scattered mailboxes. The product materially increases the firm's exposure in exactly the scenario it is sold for. No requirement, no risk row, no open question.

R-4 ("a cross-matter or cross-tenant leak") is rated **Low if the tests hold**. That rating is only defensible against the *application-logic* leak vector. Against a stolen laptop, an unencrypted volume, a shared password or a restored backup, the tests are irrelevant and the rating is fiction. The PRD explicitly asserts that RBAC is "the #1 realistic leak vector, ahead of the model provider and ahead of logs" (FR-14, §10) — an assertion made without a threat model, and one that a security reviewer would contest immediately, because an unencrypted appliance at rest is a simpler and more likely breach than a post-filter bug.

**Required fix:** a security section with FR-numbered, testable consequences, or an explicit, dated, argued deferral. Silence is the worst of the three options, and it is the one currently chosen. Given the buyer is a *bâtonnier* or a firm's insurer, this section will be asked for in the first serious conversation, and its absence is not survivable by saying it is an architecture concern.

---

### F5 — HIGH — "This document was read by a human" is the one v1 claim with no mechanism behind it.
**Where:** §1, FR-24, §13 item 4, FR-25, SM-C2.

§1 names the four claims v1 sold and never built: *nothing relevant was discarded*, *this document was read by a human*, *this matter cannot see that one*, *nothing left the firm*. Three of them have dedicated machinery in this PRD: FR-22/FR-23 (sampling), FR-14/FR-29 (pre-filter, isolation), FR-31/FR-32 (content-free projection). The second has **no FR**.

The only place it appears is a single clause inside FR-24's fifth bullet: *"A value the user never touched is recorded as accepted only if she performed an explicit validation act over it — not by default and not by the passage of time."* §13 item 4 then leans the entire audit story on it.

Nothing defines the validation act. Not its granularity (per pièce? per row? per screen? per matter?), not where it appears in the interface, not whether it requires the pièce to have been opened, not what it costs the user, not whether it can be performed in bulk. It is a promise stated as an intention in a document whose whole thesis is that promises must be mechanisms.

Worse: **nothing forbids or even mentions bulk acceptance.** A triage table of 1 700 rows with an editable cell grid (FR-20) will grow a select-all, because every table does. The moment it does, the audit record will contain 1 400 documents marked "accepted as-is" in four minutes, and §13 item 4 will be answering "did a human look at it?" with *yes*. That record is worse than no record: it is documented consent that was never given — precisely the failure R-6 describes, arriving through a door nobody guarded.

SM-C2 is supposed to catch this, and cannot: it has no threshold (A-16), and OQ-9 admits it is unobservable without telemetry, which §5 forbids forever.

**Required fix:** an FR for the validation act, with granularity, interface locus, cost and audit representation stated as testable consequences; an explicit position on bulk acceptance (forbid it, or specify it and record it as a distinct act with its own class in the audit record); and a way to distinguish "validated after opening the pièce" from "validated from the list".

---

### F6 — HIGH — FR-30 (configuration editable per tenant) and §5 (no admin cockpit) directly contradict each other, and nothing bridges them.
**Where:** FR-30 first bullet, §5, §6.2, §2.2, addendum §4.

FR-30's first testable consequence requires that the triage taxonomy and its labels, RBAC scopes **and their assignment**, the model provider and its endpoint, the configured sources, the chunking configuration, three families of threshold and the interface language be *"editable per tenant without a code change or a deployment of different code."*

§5 states: **"No admin cockpit. There is nothing installed to operate. Its foundation — configuration-as-data — is in scope; the operator interface is not."**

Editable by whom, through what? The three candidate answers are all unwritten and all bad:

1. **Direct database edits by APX at the firm's site.** Offline, no telemetry, no audit record entry (FR-30's last bullet requires config changes to be recorded in the audit record — a hand-written SQL UPDATE will not do that), no validation, no rollback. This is the "documentation lies in load-bearing places" failure of §17 waiting to happen, and it is a *manual per-site divergence* — the fork the whole section exists to prevent, arriving as data instead of code, which is not better.
2. **A config file shipped per installation.** Then it is a deployment of different artefacts per tenant, which FR-30 forbids in spirit and R-10's version drift eats alive.
3. **A surface exists after all**, in which case the admin cockpit is in scope and neither §6.1 nor the addendum §3.3 sequence has budgeted for it.

There is a second contradiction underneath: **RBAC scopes and their assignment** are in FR-30's list. Assignment of access rights is not decoration; it is the mechanism behind the Chinese wall and the criminal obligation of §12. Making it a configuration row with no specified administration surface, no grant-time authorisation and no audit trail (F4) is the most consequential instance of this gap.

**Required fix:** name the configuration surface, however minimal — a CLI, a signed config bundle, a single settings screen — give it an FR, and make FR-30's audit-record consequence achievable through it. "The foundation is in scope, the interface is not" is not a coherent position when the foundation's own acceptance criterion is *editability*.

---

### F7 — HIGH — The per-pièce LLM justification at 100 000 documents is uncosted, unlatencied, and is the largest data-egress event in the system.
**Where:** FR-18, FR-36, §10 (Cost), §11 (Egress), §14, R-9.

FR-18 requires **every** pièce in the ranking to carry a confidence value and a one-line justification "in the user's language". FR-36 requires that text to be produced by a language model with an explicit output language. The design target is 100 000 documents.

Three things follow that no requirement, metric, risk row or open question addresses:

1. **Cost.** 100 000 model calls per matter-scale corpus, each carrying enough source text to justify a placement. Nobody has written down what a single triage run costs. §10's cost section discusses the *feature-ownership* tax and the buyer's reference price (€7k–79k/year) and never touches marginal inference cost. If a single 100 000-document triage costs a four-figure sum in tokens, the pricing model in OQ-2 (forfait vs subscription) is being debated without the input that decides it.
2. **Latency.** OQ-6 defers all performance targets. Fine for import throughput; not fine here, because UJ-1's entire premise is that Éléonore starts the job on Friday evening and reads the retained set over the weekend. 100 000 sequential-ish model calls with rate limits is the binding constraint on that journey, and SM-C4 ("time to first useful screen") is explicitly flagged as depending on an answer nobody has. The PRD refuses to state targets on the correct principle that it must not invent numbers — but it could state a **ceiling beyond which the user journey is invalid**, which is not an invented target but a derived one. UJ-1 dies if first ranking takes longer than a weekend. Write that down.
3. **Egress.** §11 declares exactly two egress paths and describes the model-provider path as *"carrying query and retrieved context"*. FR-18 makes it carry **the substance of every document in the corpus**, one at a time, to a US-operated provider under a zero-retention *contract clause* that R-9 and §10 already admit is not a technical property. That is not a query path; it is a bulk export of the client's entire matter, performed automatically, as the normal operation of the product. For a product whose one differentiator is confidentiality, §11's characterisation of its own egress is materially misleading, and a *bâtonnier* applying the CNB criteria will see it immediately.

**Required fix:** state the per-matter inference cost model; derive a latency ceiling from UJ-1 rather than deferring it; and rewrite §11's egress description so it says what FR-18 actually does. Consider whether FR-18's justification must be generated for every pièce or only for pièces near and above the line — the latter cuts cost, latency and egress by an order of magnitude and costs nothing the user notices.

---

### F8 — HIGH — The corpus and evaluation pipeline is a product-sized project with no FR, no owner and no gate. It is the item most likely to be quietly dropped, and it is the exact v1 defect.
**Where:** §8, SM-2, addendum §2 and §3.3, salvage table.

The PRD says, twice and with feeling, that v1 had a gold set and **never once ran it**. It then places the entire remedy in §8 (a prose section explicitly labelled "invented section") and SM-2 (a metric). Everything else load-bearing in this document is an FR in §4 with numbered testable consequences. The corpus pipeline is not.

What §8 and addendum §2 actually require, in engineering terms:

- Acquiring and licence-clearing a specific Enron/EDRM distribution (~500k messages, "verify the licence terms" — an unowned action with no OQ number).
- Acquiring TREC Legal Track collections and their relevance judgments, and mapping their relevance definition onto this product's taxonomy and its notion of *the line*. That mapping is not mentioned anywhere and is not trivial.
- **Building a degradation pipeline**: render French public legal text to skewed scans, wrap in `.msg` with plausible headers and reply chains, duplicate with variations, corrupt a fraction, password-protect a fraction — and, per addendum §2 rule 2, assert each degradation against its expected failure-register error class.
- Running all of it through FR-33's single ingestion path, at 100 000 documents, in CI.

That is a substantial build with **zero user-visible output**, owned by nobody, sequenced only as a clause inside addendum §3.3 step 4, and defended by no acceptance gate. Under schedule pressure — for one non-hands-on CTO with no client — it is the first thing to go, and its absence is invisible, because the product still runs. This is the v1 failure repeating with a better justification attached.

Two further defects inside SM-2 itself:

- **The ratchet has no floor.** "A run whose recall is below the previously recorded figure fails the build", with no absolute target (correctly deferred to OQ-5). The consequence: whatever the *first* measured baseline happens to be — 0.35, say — becomes permanently acceptable, permanently defended by a green build, and permanently unarguable. A ratchet without a floor institutionalises the first number you happen to get.
- **The ratchet is applied to a stochastic measure with no significance test.** Recall over a gold set varies run to run with any nondeterminism in embedding, chunking or model output. A strict "below previous fails" rule on a noisy measure produces flaky builds, and flaky builds get disabled. That is how a gold set stops running for the second time.

**Required fix:** promote the corpus and evaluation pipeline to numbered FRs in §4 with testable consequences; add a hard sequencing gate ("no ranking code is merged before SM-2 executes against the gold set", which the addendum already believes and the PRD does not enforce); and give SM-2 a floor plus a significance rule.

---

### F9 — HIGH — The offline fitness function is the programme's most important invariant and it is prose in an addendum with no test.
**Where:** addendum §1.3, PRD §9, §14, §16.

> *"Can this run, unmodified, on a single machine inside a law firm with no internet connection?"*

Everything commercial about APX depends on the answer being yes. The addendum instructs: *"run it as a check, not as a review question."* No check exists. There is no FR, no SM, no CI job, no acceptance criterion. Compare with FR-31, where an equivalently important guarantee (content-freedom) is bound to a seeded-token test and the PRD says outright *"This test is the guarantee; a statement in a document is not."* The same sentence applies here and has not been applied.

Meanwhile the actual development stack is Supabase, Vercel and Railway. The gap between "we intend to keep it portable" and "it is portable" is measured in weeks of discovery, and it is discovered at the worst possible moment: at the first installation, in front of the first client, with SM-10 on the line. Every incremental piece of AI-generated code is an opportunity to take a hosted-primitive dependency, and there is nothing in CI that would notice.

**Required fix:** an FR whose testable consequence is that the application boots, ingests, indexes, retrieves and exports in a network-isolated container with no hosted-provider services present, executed in CI from the first week. That is a day of work now and a rewrite later.

---

### F10 — MEDIUM-HIGH — *Denominator* has two incompatible meanings, in a document that declares synonyms a discipline violation.
**Where:** §3 Glossary, FR-6, FR-14 third bullet, FR-28, FR-13.

§3 opens with: *"A synonym anywhere in this document is a discipline violation."* The document then gives one term two meanings.

- **Glossary + FR-6 + FR-28:** the *denominator* is the inventory guarantee **for a matter or a tenant** — `submitted = indexed + failure register`, exactly, always, never rounded, never suppressed.
- **FR-14 third bullet:** *"The denominator and any confidence bound shown to a user are computed within that user's RBAC scope, so the numbers themselves cannot leak the existence of material they may not see."*

These are different quantities. Two users on the same matter see different denominators; neither necessarily equals the matter's true submitted count; SM-3's invariant (`submitted = indexed + failure register`, zero violations ever) is stated over the matter/tenant quantity while the displayed quantity is the scoped one. An implementer — human or agent — will pick one and the other guarantee will silently not hold.

The consequence that matters is downstream in FR-13: an **exhaustive** result "carries the *denominator* it was computed against". If that is the scoped denominator, then the absence claim exported for a court is qualified by a number whose meaning is *"what this user was allowed to see"*, presented in wording that says *"the whole indexed corpus"*. See F3(d). If it is the unscoped denominator, FR-14's leak protection is violated.

**Required fix:** two glossary terms, two names, and an explicit statement of which one appears in which surface — particularly in the exhaustive-search export.

---

### F11 — MEDIUM-HIGH — The user's actual job is unspecified: there is no document viewer, and no export of the working set.
**Where:** FR-11 (one clause), §4.4, FR-26, §3 Glossary (*Pièce*).

UJ-1's resolution is *"She reads the 180 pièces above the line over the weekend."* Reading is the job. There is no FR for reading.

The only coverage is a single consequence in FR-11: *"From any chunk, the interface can open the source pièce and locate the passage the chunk was derived from."* That one clause conceals: in-browser rendering of `.msg` with reply chains and embedded attachments, born-digital PDF, scanned PDF with an OCR text layer positioned over the image, `.docx`, `.xlsx` and images; passage highlighting that resolves a chunk's stored source position onto the rendered surface for **each** of those formats; navigation between a message and its attachments; and doing it for files of arbitrary size. This is a substantial feature area with more implementation risk than several of the FRs that got their own numbered section, and it has no requirements, no consequences and no place in the addendum §3.3 sequence.

Second omission: **the product produces no deliverable.** FR-26 exports the *audit record*. The glossary defines *bordereau de pièces* as "the list of them" — and nothing produces one. The lawyer's actual work product is the bundle: the retained set, ordered, numbered, exportable, ideally in a form her *bordereau* can be built from. UJ-1 ends with her reading; it never ends with her producing anything. A triage tool that cannot emit its own working set makes the associate re-key 180 references by hand, and that is the friction that gets a tool routed around (§9: "a partner cannot make someone use a tool that adds friction").

**Required fix:** an FR for the pièce viewer with per-format testable consequences, and an FR for exporting the retained set in a form usable as the basis of a *bordereau*.

---

## 2. Is this buildable by one non-hands-on CTO plus AI agents?

**Short answer: not as scoped, and the PRD half-knows it.** R-1 rates "scope exceeds capacity" as **High and accepted**, with the remarkable mitigation note *"No mitigation makes the list smaller."* That is not a mitigation; it is a statement that the risk is unmanaged. A PRD is allowed to accept a risk. It is not allowed to accept its own top risk with an explicit declaration that nothing can be done, and then not cut anything.

### The three that will consume the most time

1. **FR-3 — multi-format extraction, and OCR at 100 000 documents.** Five bullets of prose concealing the largest engineering surface in the increment. `.msg` is a Microsoft compound-file/MAPI format: RTF-compressed bodies, TNEF (`winmail.dat`), nested `.msg` attachments, charset chaos, reply-chain reconstruction from quoted text. FR-3 requires headers, reply chains **and** embedded attachments, plus an N-attachment message yielding N+1 pièces with provenance — which means the attachment identity problem, the nested-container problem and the deduplication interaction with FR-4 all land at once. Then OCR: §15 requires it to run **inside the tenant boundary** for on-premise, which forbids every cloud OCR API and mandates a local engine, on a firm's single machine, over 100 000 documents, with a quality signal (FR-3, A-9) that nobody has defined and that gates the exhaustive claim (F3). This is months, not weeks, and it is entirely unglamorous.
2. **FR-19 + FR-23 — the estimator and the priced projection.** Not an implementation task at all. As F1 shows, the estimand is wrong, the projection requires calibration data that does not exist, and OQ-4 correctly names it "the most load-bearing unspecified item in the increment" — while the addendum §6 says it needs "a statistician's answer" and no statistician is on the team or budgeted. This is the item that can consume unbounded time because it cannot be brute-forced by an agent.
3. **FR-14 + FR-29 + SM-6 — isolation, and the adversarial suite that proves it.** Building the pre-filter is straightforward. Building the *proof* is not: SM-6 demands zero out-of-scope "results, counts, snippets or metadata across every retrieval, export and diagnostic surface", which means an adversarial suite that must be extended every time any surface is added, forever. And the addendum §1.2 forbids Postgres RLS — the one mechanism that would enforce this at the storage layer regardless of application bugs — so every authorisation decision is hand-rolled application code, written by AI agents, reviewed by one non-hands-on person, where a mistake is silent and criminal. The forbidding is *correct* for portability; its cost is that this becomes the highest-risk code in the product and it must be defended by tests alone.

Runner-up: **FR-2 + FR-4** (resumable, idempotent, concurrency-safe ingestion with induced kills at ≥3 points and induced write conflicts). Well-understood distributed-systems work — expensive but not dangerous.

### The three most likely to be quietly dropped

1. **The corpus and evaluation pipeline (§8, SM-2).** See F8. Invisible, unowned, no FR, no gate, no user-visible output, and identical in shape to the v1 defect it exists to prevent. This is the prediction I would stake the review on.
2. **FR-31 + FR-32 — the content-free projection and the client-pushed diagnostic export.** No client exists, nothing is installed, nobody has ever asked for a diagnostic. It is pure future tax, it is technically fiddly (the seeded-token test is the interesting part and the easiest to skip), and it will be stubbed to a JSON dump with the test written last or never. Its absence is undetectable until an installation exists — at which point it is the only support channel there is.
3. **The depth of FR-35 and FR-36 — locale collation, distinguishable pièce-date vs ingestion-date rendering, the source-language statement, and "language reaches the model" asserted with the locale switched.** FR-34's key-set parity is cheap and will survive because it fails the build. The rest is per-string diligence with no failing test behind most of it, and it decays exactly the way v1's did — which the PRD documents at length and then leaves protected by the same mechanism (care) that failed the first time.

Honourable mention for the drop list: **FR-26's "the export is self-contained: a reader with the export and no access to the system can reconstruct every number in it. Asserted by test."** This is a genuinely hard property and trivially fakeable with an export that merely *looks* complete.

### Scope that should be cut now

- **FR-11's exact-containment primitive (A-10).** Explicitly admitted as next-increment scope, included because "the mechanism is cheap now". In the document whose #1 risk is scope exceeding capacity and whose named failure belief is *"it's just tokens"* (§3.4 of the addendum), building a feature for a deferred increment because it is cheap is the failure belief operating in plain sight. Cut it, or name the consumer and the date.
- **FR-13's exhaustive search** deserves scrutiny as a whole: it exists to serve absence claims, which are consumed by UJ-2 (sampling, which does not use it) and by the drafting increment's citation checker (deferred). Ask honestly whether the *first* increment needs it, or whether the sampling story alone carries the sceptic.

---

## 3. Does this repeat v1's failure in a new costume?

The PRD's thesis is *"v1 built what can be shown; v2 builds what can be proven."* The costume has changed and the shape has not entirely.

**v1's failure was: build what can be demoed, skip what was sold.** This PRD's structural risk is: **build what can be tested, skip what cannot.** Tests are the new demo. Consider the scorecard: SM-1 through SM-9 are all CI-measurable and will all be green in a build that no lawyer has ever opened. SM-10 — *"installed and running at a real firm on their own documents"* — is the only metric that is not measurable in CI, is a binary, and carries A-15: **no date, because no engagement exists to attach one to.** A build that satisfies 90% of this PRD's success metrics is a build with no user. The document sees this (§8 "Accepted risk", R-2 "Nothing in this document fixes this") and names it honestly, but naming a drift is not a gate against it, and there is no requirement, no milestone and no sequencing rule anywhere that forces contact with a practitioner before the whole of §4 is built.

**Demo-shaped items:**

- **The line, and the ranking behind it (F2).** The single most demonstrable artefact in the product — a ranked table, confidences, a committed line, one-line justifications — sitting on top of a relevance judgement whose input is unspecified. It will look extraordinary in a screenshot and be unfalsifiable in the absence of a matter-specific gold standard. This is the definition of demo-shaped.
- **The confidence-bound sentence (F1).** Maximally quotable, minimally verified. SM-1 tests that it *reproduces*, never that it is *true*.
- **The priced line move (FR-19).** A number that changes as you drag. Beautiful. Derived by an unspecified estimator from an uncalibrated model.

**Promises stated as intention rather than testable mechanism:**

| Promise | Where | Why it is an intention |
|---|---|---|
| "This document was read by a human" | FR-24 bullet 5, §13 item 4 | The validation act is defined nowhere. See F5. |
| "Fail loudly, everywhere" | §9 | Generalised system rule with no test. FR-9 and FR-10 are testable instances; the rule is not. |
| "The product must be self-diagnosing" | §17 | No acceptance criterion, no test, no definition of adequate. |
| "The risk figures are derived by a documented method reproducible from the audit record" | FR-19 bullet 2 | The method does not exist (OQ-4). |
| "No technical vocabulary in any user-facing surface" | §9, FR-27 | Not decidable by any test. See F14. |
| "Can this run, unmodified, on a single machine with no internet?" | addendum §1.3 | Declared a check, implemented as prose. See F9. |
| "APX never accesses, sees or extracts client data" | §10 | True of APX's own channels, and materially incomplete given FR-18 ships every document's substance to a third-party model provider. See F7. |
| "Systematic verification of AI output" (CNB criterion 5) | §12 | Claimed as satisfied by FR-15/FR-24/FR-26. See F16. |

---

## 4. Where a hostile lawyer breaks the product

Read as opposing counsel, these are the claims the requirements do not make true.

- **"Your tool told you nothing relevant was missed."** → F1. The sentence overstates its own statistics by construction. Cross-examination: *"Your bound is a prevalence bound, is it not? So up to twenty-one relevant documents may remain in the 1 400 your client chose not to read?"*
- **"Your search covered everything."** → F3. It covered a corpus containing OCR transcriptions of unknown fidelity, none of which are disclosed in the absence statement; it covered chunk text of unspecified boundary behaviour; and the term "deterministic expression" is undefined, so accent loss in a scan defeats the search silently.
- **"Your search covered everything."** (second angle) → F3(d), F10. It covered what *one user's RBAC scope* permitted. The exported absence statement does not say so.
- **"A human reviewed these documents."** → F5. The record shows an "accepted as-is" flag whose triggering act is undefined and, absent a prohibition, plausibly performed 1 400 at a time.
- **"Nothing was ever deleted."** → OQ-8, A-13. Said to a client while the firm carries an Art. 17 erasure obligation and per-matter statutory retention limits. The PRD names the tension and leaves §10 stating "never hard-delete" as a hard constraint — so the build will implement the constraint and the contradiction will surface in production, at a client, with no mechanism to resolve it.
- **"We have an audit trail."** → F17. So does the other side, on discovery. See below.
- **"Your firm knew the risk was 3% and proceeded."** → FR-19 requires the priced statement shown at the moment of a line move to be **recorded in the audit record**, and FR-26 requires the audit record to be exportable. The firm has therefore manufactured, and retained forever (FR-21), a dated document in which it was told the probability of missing relevant material and accepted it. The PRD treats the audit record exclusively as a shield. It is also a sword, and nothing in §11, §12 or §13 considers its discoverability, its status under *secret professionnel*, whether it is protected work product, or whether a firm might rationally want a retention limit on it. That is a genuine missing analysis, and it is the kind that a client's own counsel raises before signing.
- **"Your dedup lost the custodian."** → FR-4: importing folder A then folder B, where B contains a copy of a file in A, produces **one pièce with two recorded provenance paths**. In an *ordonnance 145 CPC* or any e-discovery-adjacent context, *which custodian held this document* is frequently the fact in issue. Collapsing two custodians' copies into one pièce with a provenance list is defensible only if custodian is a first-class, queryable field — and *custodian* appears nowhere in the PRD, nowhere in FR-8's mandatory payload fields, and nowhere in the glossary. The e-discovery field this product borrows its corpus from treats custodian as mandatory metadata. This is a real omission with legal consequences.

---

## 5. Specified but unmeasurable / measurable but unspecified

### Specified but unmeasurable (stop writing "asserted by test")

- **FR-27** — "a phrasing in the user's language naming the thing and the action"; "No line exposes a technical state, a component name, an error code as its primary text". No test decides this. It is a taste requirement with a CI badge.
- **FR-30 bullet 2** — "A test asserts that no tenant-specific identifier, name or **behaviour** appears anywhere in source code." Identifiers and names are greppable. Behaviour is not.
- **FR-33 bullet 1** — "No code path substitutes stored, hand-authored or generated content for a live response from a working component, under any flag, environment variable or build configuration. Asserted by test." Undecidable in general. Approximable by an architecture/lint rule at best.
- **FR-9 bullet 3** — "no alternative embedding path reachable by exception handling or by configuration" — a reachability property, in practice a grep. Fine as a grep; say grep.
- **FR-18** — justification quality has no measure anywhere in the document, while R-11 rates "fluent-but-empty justification" as a Medium risk whose control is "the extracts are checkable". Nothing tests that the extracts actually *support* the justification.
- **§9** — "without unbounded memory growth" with no bound stated; "no technical vocabulary in any user-facing surface"; "nothing superfluous".
- **SM-8** — "100% of matters where the line was placed with a stated basis" — measurable only in CI over the evaluation corpus, since there are no matters and no telemetry.
- **SM-C2, SM-C3, SM-C4** — all three are behavioural trend metrics over real usage. §5 forbids telemetry forever. OQ-9 admits they are observable "only in evaluation sessions and in what a firm chooses to push". They are therefore **counter-metrics that cannot counter anything**, protecting the mechanisms (FR-25, FR-27, §4.5) that R-6 rates as the most likely to silently rot. The honest move is to say so in §7 rather than list them as metrics.

**Recommendation:** introduce a second verb. Reserve "asserted by test" for properties a CI job can actually decide, and use "asserted by review" or "asserted by lint rule" for the rest. Given §9 makes the test suite the substitute for absent engineers, an inflated claim about what the suite proves is the most dangerous inaccuracy in the document after F1.

### Measurable but unspecified

- **Every performance figure** (OQ-6, A-8, A-11, A-18): import wall-clock, exhaustive-search latency, time to first ranking, OCR throughput, model-call throughput. Refusing to invent absolute targets is right. Refusing to derive a **ceiling from UJ-1** is not: the Friday-evening journey has a hard deadline in it and the PRD never converts it into a number. See F7.
- **Cost per triage run** (F7). Not measured, not modelled, and it decides OQ-2.
- **Calibration of the FR-19 risk projection** (F1). Measurable against the gold set from day one; unspecified.
- **The OCR quality signal and its threshold** (A-9). Defensibly configuration — but it gates the exhaustive claim (F3), and no requirement says a corpus-wide OCR-quality figure must be computed at all, which it must be for F3's fix.
- **Recall floor** (SM-2, OQ-5). Deferring the target is right; the ratchet without a floor and without a significance rule is a defect. See F8.
- **Storage footprint** at 100 000 documents — originals, extracted text, chunks, embeddings, OCR images, audit record, append-only forever with no deletion ever (FR-21). A firm buying a single machine (CCBE's €2 000–20 000, §10) needs this number, and it is computable today.

---

## 6. Contradictions

| # | Contradiction | Where |
|---|---|---|
| C1 | Ingestion requires **exactly three inputs** and forbids further mandatory configuration, but the ranking, the line, the confidence and the justification all require a relevance criterion. | FR-1 vs FR-16/17/18. **See F2.** |
| C2 | The confidence bound must be *"reconstructible from the audit record alone, without access to the ranking model"*, while FR-19's priced risk figure is a projection **from** the ranking model at an unsampled position. Either the model's scores are in the record (in which case say so, and say what that means for export size and for F17) or the number is not reconstructible. | FR-23 bullet 3 vs FR-19. |
| C3 | *Denominator* means the matter/tenant inventory guarantee in the glossary, FR-6 and FR-28, and the **RBAC-scoped** count in FR-14 — in a document that declares synonyms a discipline violation. | **See F10.** |
| C4 | Configuration must be editable per tenant without a deployment; no operator interface is in scope. | FR-30 vs §5. **See F6.** |
| C5 | "Never hard-delete" as a hard safety constraint vs lawful erasure and per-matter statutory retention. Named as OQ-8/A-13 and left unresolved — but §10 states the constraint absolutely, so the build will implement it and the contradiction ships. | FR-21, §10, §11 vs OQ-8. |
| C6 | FR-5: retrying a failure-register entry *"on success removes it from the register"*. FR-21: no hard deletion of *"a failure register entry"*, and a full sweep of user actions must produce no reduction in stored counts. An agent implementing both literally will produce either a delete or a broken retry. Model it as a state transition and say so. | FR-5 vs FR-21. |
| C7 | "No automatic action without a human" (§10) vs FR-17, in which the machine automatically partitions 1 700 documents into read/don't-read. Not a substantive violation — nothing is destroyed — but the sentence as written will be read by a *bâtonnier* as covering exactly this, and the PRD should carve it out explicitly rather than leave it to be discovered. | §10 vs FR-17. |
| C8 | "No telemetry, ever" vs SM-8, SM-10, SM-C2, SM-C3, SM-C4, all of which require observing production behaviour. Acknowledged in OQ-9 and then not reflected in §7. | §5/FR-32 vs §7. |
| C9 | §12 claims FR-15, FR-24 and FR-26 answer the CNB's fifth criterion, *"systematic verification of AI output"*. Those FRs **record** verification; they do not make it systematic. The product's design is explicitly *non*-systematic — it samples, deliberately, and the whole value proposition is that the lawyer does **not** verify 1 400 outputs. | §12 vs §4.5. **See F16 below.** |
| C10 | The addendum's fitness function requires the core to run unmodified offline; §15 excludes identity providers and SSO entirely, while §14 assumes a browser-reachable web application inside a firm. A 30-lawyer firm with Active Directory will require SSO on day one, and "identity is a property of the application" (FR-29) means the product must own passwords — which F4 shows it does not specify. | addendum §1.2/§1.3, §14, §15, FR-29. |
| C11 | R-4 rates a cross-matter leak **"Low if the tests hold"**, while §10 and FR-14 call it the #1 realistic leak vector and a criminal-law exposure, and F4 shows the non-application-layer vectors are unaddressed. A Low rating on the risk the entire product exists to eliminate is not credible. | R-4 vs §10, §12. |

---

## 7. Missing entirely

Failure modes, user situations and operational realities with no requirement, no risk row and no open question.

1. **Security, in every dimension** — encryption at rest, authentication, session management, credential storage, key management, grant-time authorisation, insider threat, and the risk concentration the product itself creates. **See F4.** Highest-severity omission in the document.
2. **Backup, restore and disaster recovery.** One machine, no ops, no telemetry, an append-only legal record. **See F4.**
3. **The relevance criterion.** **See F2.**
4. **The pièce viewer, and any export of the retained set / bordereau.** **See F11.**
5. **Custodian as first-class metadata**, and the loss of it through FR-4's cross-folder dedup. **See §4.**
6. **Bulk operations.** No select-all, bulk-accept, bulk-reject, bulk-validate anywhere — not permitted, not forbidden, not mentioned. Every 1 700-row table grows one. **See F5.**
7. **Any feedback path from human corrections into the ranking.** FR-20 correctly forbids automatic regeneration on edit. Nothing provides the *user-initiated* alternative: Marc corrects fifty misclassifications and the remaining 1 650 keep the same wrong basis forever. The product cannot get better within a matter, and the PRD never says whether that is a deliberate choice.
8. **Model-provider failure during ranking.** FR-9 covers the *embedder* failing loudly. The model that produces FR-18's justifications and any classification has **no failure requirement at all**. What does the user see when the provider rate-limits for six hours in the middle of a 100 000-document run? §14 says absence of the provider must "degrade loudly", which is a sentence, not a mechanism.
9. **Sampling versus concurrent mutation.** FR-22 does not say which ranking version a draw runs over, what happens if a re-ranking completes mid-sample, what happens if another user moves the line mid-sample, or what happens if Marc edits a sampled pièce's classification while Emmanuel is reviewing it. UJ-2's edge case covers *abandonment* only. FR-23's staleness rule is retrospective and does not prevent an in-flight run from being invalidated silently.
10. **Multi-user concurrency beyond a single cell.** A-6 and FR-20 handle two users editing one cell. Nothing handles two simultaneous sampling runs, a re-rank during an import, or an import into a matter someone is triaging.
11. **First-run and tenant provisioning.** How does a tenant come to exist? Who creates the first user, the RBAC scopes, the taxonomy? **See F6.**
12. **Legal hold / freezing a matter** once litigation is live. The product is append-only, which helps, but there is no concept of sealing a matter against further ranking changes, and FR-16's re-ranking can silently produce a new version underneath a bound already quoted to a court.
13. *(Withdrawn — see §8. FR-35 already requires that "dates stored and dates in exports use an unambiguous, locale-independent representation". Timestamp semantics are covered.)*
14. **Import from a source that changes mid-job** — a USB key removed at 40%, a network share that disconnects. FR-2 covers *worker* death and *client* closure; it does not cover the *source* vanishing, which for a USB-key onboarding story is the more likely event.
15. **Storage growth and the never-delete constraint.** Nothing is ever deleted, every ranking version is retained, the audit record is append-only forever. There is no requirement to bound growth and no figure for what a firm must provision.

---

## 8. Findings a naive reviewer would raise that are actually correct — do not spend time defending these

These are right. They should not be changed in response to review pressure.

- **"No absolute recall target (SM-2 / OQ-5)."** Correct. Inventing a number before the gold set has ever run is exactly the unaudited-claim failure §5 forbids. The defect is the *ratchet's* missing floor and missing significance rule (F8), not the missing target.
- **"No latency or throughput targets anywhere (OQ-6)."** Largely correct for the same reason. My objection is narrow: derive a *ceiling* from UJ-1 rather than an absolute target. Do not let a reviewer push you into inventing "import completes in 4 hours".
- **"No named client, no named firm."** Deliberate, stated, and honest. It is the right call and the document is better for the discipline.
- **"Too many [ASSUMPTION] tags."** The assumptions index (§20) is the strongest structural feature of the document. Twenty-two inferences surfaced for confirmation is not weakness; it is the opposite of what v1 did.
- **"Zero-retention is only a contract clause."** Already admitted, in §10, in R-9 and in the addendum. There is nothing left to expose.
- **"The Enron corpus is English."** Already handled, twice, with the correct distinction between language realism and pipeline realism.
- **"No EU AI Act compliance claim."** Correct and well-argued, including the Digital Omnibus deferral. Do not let a compliance-minded reviewer reinstate it.
- **"The v1 defect annotations clutter §4."** They are load-bearing. They are the reason each negative requirement exists, and removing them turns a requirement into an arbitrary rule that a future agent will optimise away.
- **"Concurrent editing (A-6) is out of source scope."** The inclusion is right; a shared matter makes it near-certain.
- **"No mobile surface."** Fine.
- **"'Never hard-delete' vs GDPR is unresolved."** Correctly named as OQ-8. My objection (C5) is only that §10 states the constraint absolutely, so the build will ship the contradiction — not that the tension was missed.
- **"§8 is an invented section."** Inventing it was correct; it is the first real engineering problem. The defect is that it never became FRs (F8), not that it exists.
- **"Timestamps have no absolute storage requirement."** This review raised it and then withdrew it: FR-35 already requires that *"dates stored and dates in exports use an unambiguous, locale-independent representation"*, and FR-8 already separates the pièce's own date from the ingestion timestamp. Covered. Listed here so the point is not re-raised by the next reviewer.
- **"FR-20 forbids re-ranking after an edit, so the tool can never improve."** Half right, and the half that is right is finding 7 in §7 (there is no *user-initiated* re-rank that learns from corrections). But the prohibition itself is correct and came from a practising associate; do not let anyone soften FR-20 in response to the gap. The fix is an additional explicit action, never a relaxation of the invariant.

**Verification note.** Four of this review's load-bearing negative claims were checked against the source text rather than asserted from reading: *custodian* appears nowhere in prd.md or addendum.md; no encryption, backup, restore, authentication, session or at-rest requirement appears in either document; no relevance criterion, matter description or query input appears anywhere (only the undefined phrase "a stated basis", twice, at FR-17 and SM-8); and *bordereau de pièces* appears exactly once, inside the glossary definition of *pièce*, with no FR producing one.

---

## 9. Additional findings (medium and below)

- **F12 — SM-1 verifies reproduction, not correctness.** Covered under F1, restated here because SM-1 is the north star and a reader skimming §7 will believe it validates the bound. It does not.
- **F13 — FR-16's ranking versions multiply everything and nothing bounds them.** Each re-ranking creates a version; each version carries its own line position, its own confidence bounds, its own retained/discarded views, and interacts with human-set edit overlays (FR-20). Nothing says how many versions are retained, how the interface disambiguates "the discarded set" across versions, or which version FR-22's draw runs over. Combined with never-delete (FR-21), this is unbounded state with an ambiguous referent at the point where legal claims are made.
- **F14 — "Asserted by test" is over-claimed in at least six places.** See §5. Given the test suite is explicitly the substitute for absent engineers, inflating what it proves is a load-bearing documentation lie of exactly the kind §17 was written to prevent.
- **F15 — Counter-metrics that cannot be measured (SM-C2, SM-C3, SM-C4).** They guard the mechanisms most likely to rot (R-6), and OQ-9 admits they are unobservable. Either state a non-telemetry observation protocol (structured evaluation sessions with real users, on a schedule) or demote them from §7 to §19 so the metric set is honest.
- **F16 — §12 claims the CNB's "systematic verification of AI output" criterion is satisfied, and it is not.** FR-15 declares truth status, FR-24 records decisions, FR-26 exports them. None of them makes verification *systematic*; the product's entire proposition is that the lawyer verifies a *sample*. The defensible argument is that random-sample verification with a stated bound is a *superior* answer to the criterion — which may well be true and is a much better pitch — but that argument is not made, and the criterion is currently claimed as satisfied by mechanisms that do not satisfy it. Compounded by A-19: the criteria themselves are second-hand and load-bearing (OQ-11).
- **F17 — The audit record is treated only as a shield, never as a sword.** No analysis of discoverability, seizure, privilege, or the fact that FR-19 requires the firm to permanently record having been told a risk figure and having accepted it. No retention limit is even discussable, because FR-21 forbids deletion. This should be an OQ at minimum and a conversation with a practitioner before build.
- **F18 — FR-11's exact-containment primitive is next-increment scope, admitted (A-10), justified by cheapness.** In a document whose named failure belief is "it's just tokens", this is that belief in operation. Cut or justify with a consumer and a date.
- **F19 — R-1's mitigation is not a mitigation.** *"No mitigation makes the list smaller"* against the document's own top risk, rated High and accepted. Either cut scope (F18, FR-13, FR-18's per-pièce justification, FR-31/32) or state a sequencing gate with a decision point at which scope *will* be cut, and what gets cut first. An accepted risk with no response is an unmanaged risk with a paragraph attached.
- **F20 — Nothing forces contact with a practitioner before §4 is built.** OQ-17 asks whether one real anonymised matter can be obtained "before build starts", §8 calls it the highest-value acquisition, R-2 rates its absence High and says "nothing in this document fixes this". Correct — and a PRD *can* fix it, with a gate: no triage-layer work (addendum §3.3 step 5) begins until either one real matter is in hand or the absence is explicitly re-accepted with a date. That is one sentence and it is the only structural defence against the drift that produced v1.

---

## 10. Summary of required actions, in order

1. **Fix the confidence-bound sentence** (F1). It is false as written, it is the north star, and a lawyer is meant to say it in court.
2. **Decide and specify the relevance criterion** (F2), or state plainly that the ranking is generic and accept what that does to §1's claims.
3. **Qualify the exhaustive claim** with OCR provenance, chunk-boundary semantics, expression normalisation and RBAC scope (F3).
4. **Write a security section**, including backup and restore (F4).
5. **Give "read by a human" a mechanism**, and take a position on bulk acceptance (F5).
6. **Resolve FR-30 vs "no admin cockpit"** by naming the configuration surface (F6).
7. **Cost, time-bound and honestly describe the egress of the per-pièce justification** (F7); consider generating it only near the line.
8. **Promote the corpus/eval pipeline to FRs with a merge gate; give SM-2 a floor and a significance rule** (F8).
9. **Make the offline fitness function a CI job** (F9).
10. **Split *denominator* into two named terms** (F10).
11. **Add FRs for the pièce viewer and the retained-set export** (F11).
12. **Downgrade over-claimed "asserted by test" language** to what CI can actually decide (F14).
13. **Add a practitioner-contact gate before the triage layer begins** (F20).
