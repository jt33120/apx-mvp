---
title: "APX MVP — First Increment: Mass-Document Triage"
status: draft
created: 2026-07-20
updated: 2026-07-21
---

# PRD: APX MVP — First Increment: Mass-Document Triage

*Working title — confirm.*

## 0. Document Purpose

This PRD is the build contract for the **first increment** of the APX rebuild: mass-document triage. Its readers are the CTO who owns the build, the AI agents that will execute it, and the downstream `bmad-architecture` and `bmad-create-epics-and-stories` workflows. It states **capabilities and their testable consequences**, never technology choices — every technology decision, every rejected alternative and every sequencing implication lives in the companion `addendum.md` in this folder.

Structure: vocabulary is anchored in §3 Glossary and used verbatim everywhere else in the document; features are grouped in §4 with functional requirements nested and numbered globally FR-1…FR-36 so they survive reorganisation; user journeys are numbered UJ-1…UJ-4 and referenced by ID from the FRs; success metrics are numbered SM-* and cross-reference the FRs they validate; every inference is tagged `[ASSUMPTION: …]` inline and indexed in §20.

Upstream inputs, not duplicated here:
- `../briefs/brief-apx-mvp-2026-07-20/brief.md` — the finalised Product Brief.
- `../briefs/brief-apx-mvp-2026-07-20/addendum.md` — corpus strategy, the infrastructure contradiction and the rule that resolves it, capacity, personas, deferrals.
- `../../brainstorming/brainstorm-apx-mvp-rebuild-2026-07-20/brainstorm-intent.md` — the 14 non-negotiable mechanisms, the MoSCoW, the v1 salvage list and the v1 trap register. **The trap register (§9 of that document) is requirement material and is carried into this PRD as consequences, not as prose.**
- `docs/context/04-competitive-landscape.md` §7–§8 — the gap analysis and its implications.

Two facts shape every requirement in this document and should be read before anything else. **No client engagement has been won.** The product is built for the use case, not for a named firm; no firm name appears anywhere in this document, and the persona names in §2.3 are illustrative composites drawn from the discovery record. **The team is one non-hands-on CTO plus AI agents.** Writing code is nearly free; owning it is not. Every requirement below is a permanent tax — tested, migrated blind against a corpus at the design target of 100 000 documents at every installation, defensible in front of a judge, and supportable by telephone with no telemetry.

---

## 1. Vision

A lawyer facing an undifferentiated dump — a *matter* of 1 700 *pièces*, mostly `.msg`, or four years of a practice — has three bad options today: read everything, skim and hope, or pay an associate to skim. She skims. The honest baseline for anything built here is not perfect human review; it is what actually happens on a Friday evening under deadline pressure.

APX's first increment turns that dump into a **ranked, reversible, auditable working set, with a measured statement of what was set aside.** Nothing is ever deleted. The tool does not hand back a ranked list and leave the judgement to her — a list that refuses to decide pushes the work back onto the person paying to avoid it. The tool **draws the line** and says "in my view, everything above this". She can move it, and the cost of moving it is priced for her before she does. And when she is asked what happened to the rest, she has a sentence she can say to a client or to a judge, backed by a random sample and a stated *confidence bound*, not by a promise.

The organising principle of the whole rebuild is one sentence: **v1 built what can be shown; v2 builds what can be proven.** Every claim this product makes to a lawyer — nothing relevant was discarded, this document was read by a human, this matter cannot see that one, nothing left the firm — must rest on a deterministic, testable mechanism rather than on an intention written in a specification. In v1 those claims were sold in two client proposals and implemented in zero lines of code. That is the specific failure this document exists to prevent, and it is why every functional requirement below carries testable consequences and why several of them are written as the negation of a v1 defect.

The competitive reason this increment comes first, rather than drafting: drafting over a firm's own corpus is the most contested space in the European market, sold at €19/month by vendors already inside the practice-management software 7 500 French firms pay for. Triage for European firms under 50 lawyers is empty — *ordonnance 145 CPC* review goes to forensics consultancies at consulting rates and no French-language sovereign tool addresses it (`04-competitive-landscape.md` §7.1 item 4, §8.5). This is a **wedge, not a market**: demand is episodic and unproven, and the honest read is that it opens a door rather than fills a pipeline.

---

## 2. Target User

### 2.1 Jobs To Be Done

**The associate — the daily user.**
- *When a matter arrives as a folder of thousands of files and I have a deadline*, I want the machine to have read all of it before I open the first one, **so that** my evening is spent on the twenty documents that decide the case rather than on the nine hundred that do not.
- *When the machine has sorted my documents*, I want to correct it cell by cell without anything else moving, **so that** I never lose an edit and never have to redo work the tool undid. (Functional. Also emotional: *do not make me look stupid, do not lose my edits, do not make me check your work.*)
- *When I am asked in front of a partner why a document was not in the bundle*, I want a record that shows what the tool proposed, what I changed and why, **so that** the answer is a document rather than a memory.
- *When I open the tool at 21:00 on a Friday*, I want it to tell me what needs me, **so that** I do not have to work out what to do next before I can start.

**The partner — signs, does not use.**
- *When I am offered a matter whose review cost I cannot bid*, I want to be able to price it, **so that** I stop declining work or under-pricing it.
- *When my insurer or my bâtonnier asks how AI is used in this firm*, I want a documented, mechanical answer, **so that** the conversation ends.

**The sceptic — a senior lawyer whose function is to distrust the machine on the firm's behalf.**
- *When the tool tells me it set aside 1 400 pièces*, I want to verify that claim myself by sampling, **so that** I am relying on a measurement rather than on a vendor's assurance.
- *When I have verified it*, I want a sentence with a number in it that I can repeat to a client or to a court, **so that** the firm's exposure is bounded and stated rather than unknown.

He is the gatekeeper, not the obstacle: "auditability is non-negotiable" is a direct quote from discovery, and *random-sampling auditability* is his requirement. Design for him and the other two follow.

### 2.2 Non-Users (first increment)

- **Firms shopping for a general productivity tool.** That market is served at €19–80 per user per month by vendors already inside the practice-management software. This product is for a firm with a **confidentiality problem it can name**: *ordonnance 145 CPC* review, criminal defence, sensitive M&A, Luxembourg private wealth.
- **Anyone looking for a legal research tool.** APX cannot compete on corpus depth and must never present itself as one. Retrieval in this increment is over the firm's own *corpus* only.
- **Large-scale litigation-services providers and their reviewers.** The e-discovery platforms serve them; this product does not.
- **The APX operator.** There is no admin cockpit in this increment; there is nothing installed to operate. Its foundation — configuration-as-data — is in scope; the interface is not.
- **A drafting user.** Syllogisme drafting is the next increment (§5).
- `[ASSUMPTION: Italian-speaking users are non-users of this increment. Several Italian firms are in discussion with the APX partners, which moves i18n scope toward FR/EN/IT; this PRD holds FR/EN and treats Italian as OQ-3 rather than as a requirement.]`

### 2.3 Key User Journeys

*Persona names are illustrative composites from the discovery record. No firm and no client is named.*

---

**UJ-1. Éléonore starts a four-year matter on a Friday evening and lets it run.** *(The user's own narration. Preserved.)*

**Persona + context.** Éléonore, associate, non-technical, works under deadline at inconvenient hours. It is Friday evening. The hearing is Monday. A *commissaire de justice* operation has left her a drive holding four years of a *matter* — roughly 1 700 *pièces*, mostly `.msg` with attachments, some scanned, some she already knows are corrupt.

**Entry state.** Authenticated, on the worklist home screen of her *tenant*, which currently shows two lines from another *matter*. She has not configured anything and has not spoken to anyone's IT department.

**Path.**
1. She plugs in the USB key and selects the folder holding the four years. One gesture. No connector, no API, no import wizard asking her to map fields. She names the *matter* and confirms the *RBAC scope* it belongs to.
2. The import job starts and collapses to a small non-blocking indicator, bottom-right, Google-Drive style. It shows a running count against a denominator. She does not wait for it.
3. She keeps working — she opens the other *matter*, reads two documents, answers an email. The indicator keeps counting. She closes her laptop lid; when she opens it again the import has resumed from where it stopped rather than starting over.
4. The indicator turns to a completed state. She clicks it.

**Climax.** She does not get a progress log. She gets two things. First, **the tasks that need a human**, in her language, as a worklist: *"14 pièces illisibles — les traiter"*, *"3 pièces protégées par mot de passe"*, *"1 dossier compressé n'a pas pu être ouvert"*. Second, **a completion summary** whose first line is the denominator: submitted, indexed, and in the *failure register*, listed one by one. Underneath, the *retained set* above **the line**, each *pièce* with a confidence and a one-line justification, and the *discarded set* below it with its count. Nothing has been deleted. Nothing has been filed into a folder she cannot undo.

**Resolution.** She reads the 180 *pièces* above **the line** over the weekend instead of 1 700. On Monday morning she can say what she did with the rest. The next thing she does is UJ-4 or she hands the *matter* to Emmanuel for UJ-2.

**Edge case.** She has already imported part of this folder last month, from a different drive, under a different top-level folder name. The second import does **not** overwrite the first and does **not** produce 1 700 duplicates: files already ingested for this *matter* are recognised as already ingested, counted as such in the completion summary under their own heading, and the *corpus* count is unchanged for them. `[ASSUMPTION: she is told how many were recognised as already present, rather than silently skipped — silence here reads as data loss to a user who has been told nothing is ever deleted.]`

---

**UJ-2. `[ASSUMPTION]` Emmanuel audits the discarded set before he lets the bundle out of the building.**

**Persona + context.** Emmanuel, senior lawyer, the firm's sceptic. His function is to distrust the machine on the firm's behalf. He does not care what the tool retained; he cares what it threw away.

**Entry state.** Authenticated, opens the *matter* Éléonore triaged, with an *RBAC scope* that includes it. The *discarded set* holds 1 400 *pièces*.

**Path.**
1. He opens the *discarded set* and asks for a random draw. He sets the sample size, or accepts the size the tool proposes for a stated target *confidence bound*.
2. The tool draws — verifiably at random, with the draw itself recorded — and presents the sampled *pièces* one at a time, each with the *truth status* of the evidence behind its position and the one-line justification the tool gave for discarding it.
3. He marks each one relevant or not relevant. He finds none relevant. On the two he hesitates over, he marks relevant and the tool tells him immediately what that does to the number.
4. He completes the sample.

**Climax.** The tool gives him a sentence: *"200 pièces sampled at random from the 1 400 in the discarded set, 0 relevant; risk of having missed a relevant document below 1.5%."* Not a dashboard, not a percentage in a coloured badge — a sentence, in his language, that he can put in a note to the client or say to a judge. Every number in it is reconstructible from the *audit record* alone.

**Resolution.** The sampling run is now part of the *matter*'s *audit record*: who sampled, when, which sample, which version of the ranking, what each verdict was. If he had found one relevant *pièce*, the sentence would have said so and the *confidence bound* would have widened accordingly — and the tool would have offered to move **the line** rather than quietly re-ranking behind him.

**Edge case.** He starts a sampling run and abandons it after 40 of 200. The tool does not present a partial sample as a result and does not produce a *confidence bound* from it. The incomplete run appears on the worklist as an actionable line — *"Audit échantillon: 40/200 — reprendre"* — and is retained in the *audit record* as incomplete.

---

**UJ-3. `[ASSUMPTION]` Marc corrects a misclassification and watches the change log record it.**

**Persona + context.** Marc, junior associate. He knows one *pièce* the tool put in the *discarded set* is the whole case, because he was on the call it summarises.

**Entry state.** Authenticated, on the triage table for the *matter*, which he can edit cell by cell.

**Path.**
1. He finds the *pièce*, opens the cell holding its classification, and changes it.
2. Nothing else on the screen changes. No regeneration runs. The other 1 699 rows keep exactly the values they had, including any correction he made ten minutes ago.
3. A **change log** entry appears immediately next to the row: the previous value, the new value, who, when.
4. He does the same to the confidence on a second row, and to the date on a third, extracted wrongly from a scan.

**Climax.** He makes twelve corrections in a row and none of them costs him another. The value he is getting is negative and he would only notice its absence: the tool did not undo his work. This is the architectural invariant of the system, expressed as a UI property — *cell-by-cell editing with no destructive regeneration* — and it came from a practising associate, not from a design preference.

**Resolution.** His corrections are in the *audit record* as modifications, distinguished from values accepted as-is. If his edit contradicts something the tool asserted with high confidence, he is asked for a one-line reason and the entry is marked as an override. If Emmanuel later runs UJ-2 over the *discarded set*, Marc's corrections are already reflected in it.

**Edge case.** Two people edit the same cell of the same *matter*. The second edit does not silently win: the *change log* shows both, attributed, in order, and the current value is unambiguous. `[ASSUMPTION: concurrent editing within one matter is in scope; the source documents do not address it, but a shared matter with a partner and two associates makes it near-certain.]`

---

**UJ-4. `[ASSUMPTION]` Éléonore moves the line and is shown the price before she pays it.**

**Persona + context.** Éléonore again, Sunday, having read the 180 *pièces* above **the line**. She is uneasy — the case turns on a period the retained material barely covers.

**Entry state.** On the triage view for the *matter*, **the line** where the tool put it.

**Path.**
1. She drags **the line** downward. Before she releases it, the tool prices the move: *"400 more pièces to read; estimated risk of having missed a relevant document falls from 3% to 0.4%."*
2. She sees the same figure for two other candidate positions as she drags past them, so she is choosing between priced options rather than guessing.
3. She releases. The *retained set* grows; the *discarded set* shrinks; **nothing is deleted and nothing is re-classified** — the piles are a view over one ranked order, and only the position of **the line** changed.
4. The new position is recorded as an auditable parameter of this *matter*, with who moved it and when.

**Climax.** She has converted a feeling ("I am not comfortable") into a decision with a number attached and a record behind it. That is the difference between a tool that commits and a tool that hedges.

**Resolution.** Any *confidence bound* already computed for this *matter* is marked as computed against the previous position of **the line** and is not silently reused. The worklist gains a line offering to re-sample.

**Edge case.** She drags **the line** to the very bottom, retaining everything. The tool does not object, does not warn, and does not treat this as an error — but the priced statement now reads that the *discarded set* is empty and no *confidence bound* is applicable, and it says so rather than reporting a risk of 0%.

---

## 3. Glossary

*Downstream workflows and readers use these terms exactly. FRs, UJs and SMs use them verbatim. A synonym anywhere in this document is a discipline violation.*

- **Tenant** — one installation's isolated world: one firm. All data, configuration and identities belong to exactly one tenant. Tenant isolation is a day-one invariant, not a later feature. One codebase, N tenants; a per-tenant code fork is a defect, not a delivery.
- **Matter** — a *dossier*: the unit of legal work, and the unit of confidentiality. Every *pièce* and every *chunk* belongs to exactly one matter. Matters are walled off from each other by professional-conduct rules (Chinese walls); a matter belongs to exactly one tenant.
- **RBAC scope** — the access predicate attached to a matter and to every *chunk* derived from it, and held against a user. Determines whether a user may see a *pièce* at all. Applied as a query **pre-filter**, never as a post-filter.
- **Pièce** — one source document as the lawyer understands it: an email, an attachment, a scan, a contract, a spreadsheet. The unit she reads, ranks, corrects and cites. One file usually yields one pièce; an email with three attachments yields four, each with its own identity and provenance to its parent. Kept in French: it is the term of art, and *bordereau de pièces* is the list of them.
- **Corpus** — all *pièces* successfully indexed for a given *tenant*, addressable by retrieval subject to *RBAC scope*. A pièce in the *failure register* is not in the corpus. "The whole indexed corpus" is a precise, countable set — that precision is what makes an absence claim honest.
- **Chunk** — the indexed unit derived from a *pièce*: a passage carrying its own *payload schema* record, including provenance back to its exact position in the source pièce. Retrieval returns chunks; the interface presents pièces.
- **Payload schema** — the record attached to every *chunk*: *tenant*, *RBAC scope*, *matter*, provenance (source pièce identity, source position, extraction method), and dates. **The only irreversible decision in the system.** Everything else sits behind an adapter and is replaceable; this is not.
- **Ingestion** — the single code path by which any *pièce* enters the system, from a folder selected by a user or from any other configured source. There is exactly one such path. There is no fixture layer, no demo path and no fallback path.
- **Import job** — one user-initiated run of *ingestion* over a selected folder. Resumable, idempotent, non-blocking, and the thing that produces the *failure register* entries and the completion summary.
- **Failure register** — the enumerated list of *pièces* submitted but not indexed, each with its filename, its path as submitted, an error class, the *matter* it was submitted for, and a retry action. It is the mechanism behind the **inventory guarantee**: *submitted = indexed + failure register*, exactly, always. The decisive pièce hides statistically in the failure register; a corpus claim made without it is dishonest.
- **Denominator** — the permanently visible statement of the inventory guarantee for a *matter* or a *tenant*: *"97 200 / 100 000 indexed · 2 800 unreadable"*. Never hidden behind a click, never rounded, never absent.
- **Triage** — reversible ranking and labelling of the *pièces* of a *matter*. Never deletion, never destructive classification.
- **The line** — the position in the single ranked order at which the tool commits: *"in my view, everything above this."* An auditable per-matter parameter with a value, an author and a timestamp. Movable by a user, and priced before it moves.
- **Retained set** — the *pièces* ranked above **the line**. A view over the ranked order, not a container.
- **Discarded set** — the *pièces* ranked below **the line**. A view, not a container: nothing in it is deleted, hidden from search, or excluded from the *corpus*. "Discarded" describes the tool's recommendation, not the data's fate.
- **Confidence bound** — the statistical statement about the *discarded set* produced by a completed random sampling run, expressed as a sentence a lawyer can say to a client or a judge: *"200 pièces sampled at random from the 1 400 in the discarded set, 0 relevant; risk of having missed a relevant document below 1.5%."* Bound to a specific position of **the line** and to a specific version of the ranking.
- **Truth status** — the declared epistemic standing of a result set. Exactly two values in this increment: **suggestive** (semantic, ranked, top-k — can support a finding, can never prove an absence) and **exhaustive** (deterministic, complete match set over the whole indexed *corpus* within *RBAC scope* — the only thing that can prove an absence). Declared on the result set itself, in the interface and in any export.
- **Audit record** — the per-*matter* append-only record of human and machine decisions: who validated, when, which version of what, which values were modified versus accepted as-is, which *overrides* were made and with what reason, where **the line** stood, and every sampling run with its verdicts. Exportable.
- **Override** — a user decision that contradicts a machine assertion or a system guard. Requires a mandatory one-line reason; recorded in the *audit record* as an override, distinct from an ordinary modification.
- **Change log** — the live, per-cell before→after trail shown in the triage table as edits are made. The user-facing surface of part of the *audit record*.
- **Audit drawer** — the per-*pièce* panel showing why the tool placed it where it did: its confidence, the retained extracts behind that confidence, the proposed audit trail entry, and reversible actions. Exportable.
- **Worklist** — the home screen. A queue of things that need a human, each line an action in the lawyer's language. **Not a log.** A line that is not actionable does not belong on it.
- **Configuration-as-data** — per-*tenant* behaviour expressed as data rows, never as a code branch: the triage taxonomy, *RBAC scopes*, the language model provider, the configured sources, the labels on **the line**. A bespoke request that becomes a code fork is a defect.
- **Content-free projection** — a single reusable primitive that emits information *about* a *tenant*'s data without emitting any of it: counts, error classes, versions, redacted diagnostics. Its content-freedom is enforced by a test, never promised in a document. Used by the client-pushed diagnostic export in this increment.
- **Gold set** — a corpus with human relevance judgments against which recall is measured, executed in CI. v1 had one and never once ran it.

---

## 4. Features

*Each subsection is a coherent feature: behaviour first, FRs nested, testable consequences under each FR. FRs are numbered globally. Where an FR exists to prevent a specific v1 defect, that defect is named — the v1 trap register is requirement material.*

### 4.1 Corpus intake

**Description.** Onboarding is a folder. The lawyer plugs in a USB key or points at a directory on the network, names the *matter*, confirms the *RBAC scope*, and the system does the rest — no connector, no API, no IT project, no meeting with anyone's systems people. The *import job* runs non-blocking so she keeps working, resumes rather than restarts, and finishes by handing back the things that need a human plus a summary of what happened. Realizes UJ-1.

This UX specifies the backend rather than decorating it: non-blocking, resumable, idempotent ingestion at the design target of 100 000 documents is what makes the gesture possible. In v1 this layer was eight empty files.

**Functional Requirements:**

#### FR-1: Folder selection as the whole onboarding gesture

An authenticated user can start an *import job* by selecting a filesystem folder (including a mounted removable drive), assigning it to a new or existing *matter* and confirming its *RBAC scope*. Realizes UJ-1.

**Consequences (testable):**
- Starting an *import job* requires exactly three user inputs: the folder, the *matter*, the *RBAC scope*. No further mandatory configuration screen exists on this path.
- Subfolders are traversed to arbitrary depth; the folder structure as submitted is preserved in each *pièce*'s provenance and is reconstructible from the *payload schema* record alone.
- An *import job* cannot be started without a *matter* and an *RBAC scope*. A *pièce* with a null or empty *RBAC scope* is never written to the *corpus*; the attempt fails the *import job* loudly rather than defaulting to permissive. *(v1: `rbac/` was empty — a legal obligation sitting at zero lines.)*
- Selecting a folder containing zero readable files produces a completed *import job* with a *denominator* of 0/0 and an explanatory *worklist* line, not an error dialog and not a silent no-op.

#### FR-2: Non-blocking, resumable *import job*

An *import job* runs in the background and survives interruption without losing or duplicating work. Realizes UJ-1.

**Consequences (testable):**
- After starting an *import job*, every other function of the application remains usable; no screen is blocked and no modal is shown.
- Progress is visible as a persistent, collapsed, non-blocking indicator showing processed count against the submitted count.
- Killing the worker process mid-job and restarting it resumes from the last committed unit of work. No *pièce* already indexed is re-indexed as a new *pièce*; no *pièce* not yet processed is skipped. Asserted by test with an induced kill at ≥3 different points of a run.
- Closing the client application does not stop the *import job*. Reopening it shows the job's true current state, not a stale snapshot.
- An *import job* over 100 000 documents completes without unbounded memory growth and without requiring the user to keep a window open. `[ASSUMPTION: no wall-clock target for a 100 000-document import is set in this PRD — the source documents state no target. See OQ-6.]`

#### FR-3: Multi-format extraction

*Ingestion* extracts text and structure from the formats a litigation *matter* actually contains. Realizes UJ-1.

**Consequences (testable):**
- The following are extracted: `.msg` (including headers, reply chains and embedded attachments), PDF (born-digital), PDF (scanned, via OCR), `.docx`, `.xlsx`, and standalone images (via OCR).
- An email with N attachments yields N+1 *pièces*: the message itself and each attachment, each with its own stable identifier, each carrying provenance to its parent message.
- Every extracted *pièce* records the extraction method used (e.g. native text, OCR) in its *payload schema* record, so a downstream reader can tell a transcription from a text layer.
- A format not on the supported list does not silently vanish: the *pièce* is entered in the *failure register* with error class `unsupported-format` and is counted in the *denominator*.
- OCR output below a configured quality signal is indexed **and** flagged, not discarded; the flag is visible on the *pièce* and generates a *worklist* line. `[ASSUMPTION: the quality signal and its threshold are configuration, not code — see FR-30. No threshold value is fixed here.]`

#### FR-4: Idempotent *ingestion* with stable identifiers

Re-submitting material that is already in the *corpus* neither duplicates it nor destroys it. *(v1 defect: ingest point ids were reused from 1, so a second upload overwrote the first.)*

**Consequences (testable):**
- Every *pièce* and every *chunk* receives an identifier that is a deterministic function of its content and its provenance, and is stable across runs, across processes and across installations. Identifiers are never allocated from a counter that restarts.
- Importing the same folder twice into the same *matter* leaves the *corpus* count unchanged, leaves every previously indexed *pièce* readable and unmodified, and reports the recognised-already-present count as its own line in the completion summary. Asserted by test.
- Importing folder A then folder B, where B contains a copy of a file in A, produces one *pièce* with two recorded provenance paths — not two *pièces*, and not one *pièce* whose original path has been overwritten.
- Importing the same file into two different *matters* produces two *pièces*, because *matter* is part of identity and confidentiality follows the *matter*. Cross-*matter* deduplication is explicitly not performed.
- Under an induced write conflict (the same *pièce* processed concurrently by two workers) the *corpus* contains exactly one copy and the *import job* does not fail.

#### FR-5: The *failure register*

Every *pièce* that fails to enter the *corpus* is enumerated, attributed and actionable. Realizes UJ-1.

**Consequences (testable):**
- A *pièce* that fails at any stage of *ingestion* appears in the *failure register* with: filename, submitted path, *matter*, error class, timestamp, and a retry action.
- Error classes are enumerated and stable, at minimum: `unreadable-scan`, `corrupt-file`, `password-protected`, `unsupported-format`, `extraction-error`, `archive-unopenable`. An unclassified failure is recorded with class `unknown` and its redacted diagnostic — it is never dropped.
- Retrying a *failure register* entry re-runs *ingestion* for that *pièce* only, and on success removes it from the register and increments the indexed count, with both counts remaining consistent with FR-6 throughout.
- The *failure register* is exportable as a list, one *pièce* per line, without leaving the application.
- No *pièce* can be removed from the *failure register* other than by successful *ingestion* or by an explicit user action recorded in the *audit record* with a reason (an *override* per FR-25).

#### FR-6: The inventory guarantee and the permanent *denominator*

The system can always state, exactly, what it was given and what it did with it. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- For every *matter* and for every *tenant*: `submitted = indexed + failure register entries`, at all times, with no third bucket. Asserted by an invariant test that runs after every *import job* and after every retry, at the design target of 100 000 documents.
- The *denominator* is displayed persistently — on the *worklist* home screen and on the *matter* — in the form *"97 200 / 100 000 indexed · 2 800 unreadable"*. It is never behind a click, never rounded, never suppressed when the failure count is zero.
- Any statement of *exhaustive* *truth status* (FR-13) carries the *denominator* it was computed against, in the interface and in any export. An exhaustive result cannot be displayed or exported without it.
- If the counts cannot be computed, the interface says so and no *exhaustive* claim is available for that *matter*. It never displays a partial denominator as if it were complete.

#### FR-7: Completion summary

When an *import job* finishes, the user gets human tasks and a summary — not a log. Realizes UJ-1.

**Consequences (testable):**
- Clicking the completed indicator opens a summary whose first element is the *denominator* and whose second is the set of *worklist* lines generated by this job.
- Every line in the human-tasks section is phrased as an action in the lawyer's language and is clickable through to the thing it refers to. A line that is not actionable is not shown here (see FR-27).
- The summary distinguishes, with counts: newly indexed, recognised as already present, entered in the *failure register* (broken down by error class).
- The summary is reachable again later from the *matter* and from the *audit record*; it is not a transient notification.

---

### 4.2 Index and *payload schema*

**Description.** The *payload schema* is the only irreversible decision in the system, and it is made once, first. Everything else — the language model provider, the hosting, the embedder, the interface — sits behind an adapter and is replaceable. Two v1 defects are negated here explicitly, because both silently converted a working system into a broken one that still returned results: an index that wiped its own collection on any vector-size mismatch, and an embedder that fell back to a 256-bucket hash on any exception, unlogged. Retrieval did not stop working in v1; it silently became noise, which is worse.

**Functional Requirements:**

#### FR-8: The frozen *payload schema*

Every *chunk* written to the *corpus* carries a complete *payload schema* record.

**Consequences (testable):**
- Mandatory fields on every *chunk*, none nullable: *tenant*; *matter*; *RBAC scope*; source *pièce* identifier; source position within the *pièce* (sufficient to locate the passage in the original); extraction method; schema version; ingestion timestamp; and the *pièce*'s own date where one could be determined, with an explicit "undetermined" value where it could not.
- A write of a *chunk* missing any mandatory field is rejected at the boundary, fails the *import job* unit loudly, and enters the *failure register*. It is never written with a default, and never written with an empty *RBAC scope*.
- The schema carries an explicit version. A *chunk* written under an older version remains readable; a migration that cannot preserve every mandatory field of an existing *chunk* is rejected rather than run.
- The distinction between the date a *pièce* bears and the date it was ingested is preserved separately. Neither is ever substituted for the other.
- A test asserts that no code path can produce a *chunk* whose *RBAC scope* was inherited from a global default rather than from its *matter*.

#### FR-9: The embedder fails loudly

Semantic embedding either works as configured or stops the work. It never degrades silently. *(v1 defect: silent 1024→256-dimension hash fallback on any exception, unlogged.)*

**Consequences (testable):**
- A real semantic embedder is used. There is no hash-based, bag-of-words or otherwise non-semantic embedder available at runtime under any configuration, including test and development configurations.
- Any failure of the embedder — unavailability, rate limiting, timeout, dimension mismatch, authentication failure — halts the affected unit of the *import job*, records it in the *failure register* with its error class, and generates a *worklist* line. It never produces a *chunk*.
- There is no fallback embedder. A test asserts that the code contains no alternative embedding path reachable by exception handling or by configuration.
- The embedder identity and its output dimension are recorded on every *chunk* via the *payload schema*, so a mixed-provenance *corpus* is detectable rather than merely suspected.
- Injecting a transient embedder failure into an *import job* of 1 000 documents results in: some documents indexed, the failed ones in the *failure register*, the *denominator* consistent, and a retry that completes them. Asserted by test.

#### FR-10: The index never deletes itself

No automatic process may destroy indexed material. *(v1 defect: the whole collection was wiped on any vector-size mismatch — one transient error destroyed the corpus.)*

**Consequences (testable):**
- No code path performs a bulk deletion, recreation or truncation of a *tenant*'s indexed material as a response to an error condition, a schema mismatch, a dimension mismatch or a version difference. Asserted by test.
- A dimension or schema mismatch between incoming *chunks* and the existing *corpus* halts ingestion for that unit, surfaces on the *worklist* as an actionable line naming the mismatch, and leaves the existing *corpus* intact and queryable.
- Destructive operations on a *corpus* exist only as explicit, human-initiated, per-*tenant* actions recorded in the *audit record* with a reason.
- Recovery from a halted state does not require re-indexing the whole *corpus*.

#### FR-11: Chunking with provenance to source position

Every *chunk* can be traced back to the exact place it came from.

**Consequences (testable):**
- From any *chunk*, the interface can open the source *pièce* and locate the passage the *chunk* was derived from.
- Chunk boundaries are deterministic: re-chunking the same *pièce* with the same configuration produces identical *chunks* with identical identifiers.
- A quoted passage surfaced anywhere in the product resolves to a *chunk* by identifier and matches its source by exact string containment. `[ASSUMPTION: exact-containment verification is built here as a shared primitive even though the citation checker that consumes it belongs to the next increment — the mechanism is cheap now and is the spine of the drafting increment. This is a deliberate scope inclusion, flagged for confirmation.]`
- Chunking configuration is *configuration-as-data* and is recorded on the *chunk*, so *chunks* produced under different configurations are distinguishable.

---

### 4.3 Retrieval — two engines with different *truth status*

**Description.** The product is two engines that must never be confused: one that **finds** and one that **proves**. Semantic retrieval is ranked, top-k and **suggestive** — it can support a finding and can never prove an absence. Deterministic exhaustive search returns the **complete** match set over the whole indexed *corpus* within *RBAC scope* and is the only thing that can support the sentence a lawyer needs: *exact search over the entire indexed corpus, zero occurrences.* The interface must never blur them, and a score threshold must never be dressed up as a proof. *(v1 defect: an off-corpus gate implemented as a score threshold, shipped disabled by default — a guess that looked like a proof, which is worse than nothing.)*

**Functional Requirements:**

#### FR-12: Semantic retrieval, marked *suggestive*

A user can retrieve *pièces* by meaning, ranked. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- Results are returned ranked, with a stated k, and the result set declares *truth status* = **suggestive**.
- Every result carries its *pièce* identity and the *chunk* provenance that produced it, and is openable at the source position.
- A semantic result set never displays or exports a count phrased as a total ("N documents match"); it displays "top N of the corpus by similarity" or equivalent wording that cannot be read as completeness.
- No score threshold, in any configuration, causes a semantic result set to be labelled or exported as **exhaustive**. Asserted by test.
- Where a similarity threshold is used for any purpose, its value is *configuration-as-data*, is recorded with the result, and has a defined default. A threshold defaulting to a value that disables the behaviour it governs is a defect. *(v1: `SYLLOGISME_MIN_SCORE=0`.)*

#### FR-13: Deterministic exhaustive search

A user can obtain the **complete** set of *pièces* matching a deterministic expression over the whole indexed *corpus* within their *RBAC scope*. This is the only mechanism in the product that can support a claim of absence. Realizes UJ-2.

**Consequences (testable):**
- The result set is complete, not truncated, not ranked by a model, and not sampled. If completeness cannot be guaranteed for a query, the query returns an error stating why, and never returns a partial set labelled **exhaustive**.
- The result set declares *truth status* = **exhaustive** and carries the *denominator* it was computed against (FR-6), including the *failure register* count.
- A zero-result exhaustive query yields an explicit statement of absence, scoped to the indexed *corpus* and qualified by the *failure register* count — never an empty screen and never "no results found" without the qualification.
- Correctness is asserted by test against a *corpus* with known plants: every planted match is returned, and no non-match is.
- Exhaustive search performance is stated against the design target of 100 000 documents. `[ASSUMPTION: no latency target is set in this PRD; the source documents state none. See OQ-6.]`

#### FR-14: *RBAC scope* as a query pre-filter

No user ever receives material outside their *RBAC scope*, and the filtering happens before retrieval, not after. This is the #1 realistic leak vector — ahead of the model provider and ahead of logs — and a post-filter leak is silent.

**Consequences (testable):**
- The *RBAC scope* predicate is applied as a constraint on the retrieval query itself. A test asserts that no retrieval code path filters results after they are returned.
- An adversarial test suite issues queries whose highest-similarity matches are deliberately outside the caller's *RBAC scope*, over both engines, and asserts zero out-of-scope results and zero out-of-scope metadata — including counts, snippets, identifiers, filenames and *denominator* figures.
- The *denominator* and any *confidence bound* shown to a user are computed within that user's *RBAC scope*, so the numbers themselves cannot leak the existence of material they may not see.
- A user with no *RBAC scope* receives an empty *corpus*, not the whole *corpus*. Fail-closed is asserted by test, including for administrative and system identities.
- Every retrieval is recorded in the *audit record* with the *RBAC scope* it was executed under.

#### FR-15: Every result set declares its *truth status*

The distinction between finding and proving is carried by the data, not by the user's memory.

**Consequences (testable):**
- *Truth status* is a property of every result set returned by any engine, present in the interface, in any export, and in the *audit record* entry for the query.
- The two statuses are visually and verbally distinct in the interface, and the distinction survives export to any format offered.
- No interface element combines results from both engines into one undifferentiated list.
- An export of a **suggestive** result set carries wording that cannot be read as a claim of completeness; an export of an **exhaustive** result set carries the *denominator*.

---

### 4.4 Triage

**Description.** Underneath there is **one ranked order** and nothing else. Nothing is deleted, nothing is moved into a folder, nothing is categorised into a container — so reversibility is a structural property rather than a promise anyone has to keep. On top of that order the tool **commits**: it draws **the line** and says "in my view, everything above this". The *retained set* and the *discarded set* are views over that order. The user moves **the line**, and the move is priced before she makes it. Each *pièce* carries a confidence and a one-line justification she can read in a second and reverse in one click. The table is editable cell by cell with a live *change log*, and no edit ever triggers a regeneration that costs her another edit. Realizes UJ-1, UJ-3, UJ-4.

*(v1 defect: the only destructive control was a raw confirmation dialog with no undo and no audit entry; there was no per-document confidence and no explicit validation act. That directly violated "triage never destroys".)*

**Functional Requirements:**

#### FR-16: One ranked order, nothing deleted, nothing categorised

Triage is a ranking, not a filing system.

**Consequences (testable):**
- The system holds exactly one ranked order per *matter* per ranking version. The *retained set* and the *discarded set* are derived from that order and the position of **the line**; they are not stored as memberships.
- No triage operation deletes a *pièce*, removes it from the *corpus*, or excludes it from retrieval. Asserted by test: a *pièce* in the *discarded set* is still returned by exhaustive search (FR-13).
- Re-running ranking produces a new ranking version; the previous version remains readable and every *confidence bound*, *audit record* entry and **the line** position remains bound to the version it was computed against.
- No user action in the triage surface is irreversible. There is no destructive control.

#### FR-17: The tool draws **the line**

The system commits to a recommendation rather than handing back an undifferentiated ranking. Realizes UJ-1, UJ-4.

**Consequences (testable):**
- After ranking, **the line** has a position, chosen by the system, with a stated basis. The interface states the commitment in words — "in my view, everything above this" — not merely by drawing a divider.
- **The line**'s position is stored as a per-*matter* parameter with a value, an author (system or named user), a timestamp and the ranking version it applies to.
- A ranking is never presented without **the line**. A ranking whose basis is insufficient to place **the line** says so explicitly and places no line, rather than placing one at an arbitrary position.
- Changing **the line** never reorders the underlying ranked order.

#### FR-18: Per-*pièce* confidence and a one-line reversible justification

Every *pièce* carries why it is where it is. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- Every *pièce* in the ranking carries a confidence value and a justification of one line, in the user's language, readable without opening the *pièce*.
- Every justification is expandable into the *audit drawer* (FR-26) showing the retained extracts behind it, each resolving to a *chunk* by identifier and to a position in the source *pièce*.
- Every justification is reversible: the user can reject the tool's assessment for that *pièce* in one action, and the rejection is recorded in the *audit record*.
- A *pièce* for which no confidence could be computed is shown as such, explicitly, and generates a *worklist* line. It is never shown with a default or an imputed confidence.

#### FR-19: Moving **the line** is priced

The user is shown the cost and the benefit of moving **the line** before she moves it. Realizes UJ-4.

**Consequences (testable):**
- While a user is repositioning **the line**, the interface states, for the candidate position: the change in the number of *pièces* to read, and the change in estimated risk of having missed a relevant *pièce* — in the form *"400 more pièces to read; risk falls from 3% to 0.4%"*.
- The stated risk figures are derived by a documented method that is reproducible from the *audit record*, and the method is named in the interface at least once (not buried).
- Moving **the line** to retain everything states that the *discarded set* is empty and no *confidence bound* applies — it never reports a risk of 0%.
- Every move of **the line** is recorded in the *audit record* with old position, new position, author, timestamp and the priced statement that was shown at the moment of the move.
- Any existing *confidence bound* for the *matter* is marked stale on a move and is not reused; a *worklist* line offers re-sampling. `[ASSUMPTION: the pricing model for the risk figure is a projection from the ranking and any completed sampling; the source documents state the sentence and the shape of the numbers but not the estimator. See OQ-4 — this is the single most statistically load-bearing unspecified item in the document.]`

#### FR-20: The editable cell-by-cell table with a live *change log*

The user corrects the tool without the tool undoing her. Realizes UJ-3.

**Consequences (testable):**
- Every editable value in the triage table is editable in place, cell by cell. Committing an edit changes that cell and nothing else. Asserted by test: after N edits across N rows, all N values hold.
- No user edit triggers regeneration, re-ranking or re-classification of any other row. Any re-ranking is a separate, explicit, user-initiated action that produces a new ranking version (FR-16) and never overwrites edits — edited values survive re-ranking and are marked as human-set.
- Each edit produces a *change log* entry shown next to the row immediately: previous value, new value, author, timestamp.
- Edits are reversible from the *change log* itself, and a reversal is itself a *change log* entry rather than an erasure.
- Concurrent edits to the same cell by two users are both recorded, in order, attributed; the current value is unambiguous and no edit is lost. `[ASSUMPTION: see UJ-3 edge case.]`

#### FR-21: Never hard-delete

No user-facing action destroys data.

**Consequences (testable):**
- No control in the product performs a hard deletion of a *pièce*, a *chunk*, an *audit record* entry, a *change log* entry or a *failure register* entry.
- Any action a user could reasonably read as deletion is implemented as a reversible state change, is labelled as such, and is recorded in the *audit record*.
- Removal of a *tenant*'s data as a whole exists only as an explicit administrative operation outside the user surface, recorded in the *audit record*. `[ASSUMPTION: a firm will eventually require erasure of a matter — for a GDPR request or at the end of a retention period. The source documents say "never hard-delete" and do not address lawful erasure. See OQ-8; this PRD does not resolve the contradiction, it names it.]`
- Asserted by test: a full sweep of user-reachable actions produces no reduction in the count of stored *pièces*, *audit record* entries or *change log* entries.

---

### 4.5 Audit and sampling

**Description.** This is the north star of the increment and the mechanism the sceptic actually buys. "Recall over precision" becomes a number rather than a slogan: draw at random from the *discarded set*, check, and state a *confidence bound* as a sentence a lawyer can say out loud. Around it sits the *audit record* — who validated, when, which version, what was modified versus accepted as-is, and which *overrides* were made with what reason. Forcing a one-line reason on an *override* is the cheapest single mechanism that both builds the trail and makes the person stop and think. Realizes UJ-2.

*(v1 defect: the audit modules were 0-byte files and the audit-trail pull request was closed unmerged — while "auditabilité non-négociable" was sold in both client proposals.)*

**Functional Requirements:**

#### FR-22: Random draw from the *discarded set*

A user can draw a verifiably random sample from the *discarded set* of a *matter*. Realizes UJ-2.

**Consequences (testable):**
- The user sets a sample size, or requests a target *confidence bound* and is given the sample size that achieves it.
- The draw is random over the whole *discarded set* within the user's *RBAC scope*, not over a recent, convenient or already-loaded subset. The draw is recorded — its seed or its resulting identifier list — such that it is reconstructible from the *audit record*.
- Each sampled *pièce* is presented with its one-line justification, its confidence and its *audit drawer*, and the user records a verdict of relevant or not relevant. A verdict cannot be skipped silently; an unanswered item leaves the run incomplete.
- Marking a sampled *pièce* relevant immediately updates the projected *confidence bound* shown to the user, before completion.
- An abandoned run produces no *confidence bound*, is stored as incomplete, and produces an actionable *worklist* line to resume it. Asserted by test.

#### FR-23: The *confidence bound* as a sentence

A completed sampling run produces the sentence, not a chart. Realizes UJ-2.

**Consequences (testable):**
- The output is a sentence of the form: *"N pièces sampled at random from the M in the discarded set, K relevant; risk of having missed a relevant document below X%."* It is copyable as text.
- The sentence names the *matter*, the ranking version and the position of **the line** it was computed against, or carries them in the accompanying record.
- Every number in the sentence is reconstructible from the *audit record* alone, without access to the ranking model. Asserted by test: recompute from the exported *audit record* and compare.
- The statistical method producing X is stated and is fixed for a given *tenant* by *configuration-as-data*; changing it produces a new *confidence bound* rather than silently restating the old one.
- Where the sample found K > 0 relevant *pièces*, the sentence says so and the bound widens accordingly; the product never suppresses or reframes an unfavourable result, and offers to move **the line** rather than silently re-ranking.
- A *confidence bound* computed against a superseded ranking version or a superseded position of **the line** is displayed as stale and cannot be exported as current.

#### FR-24: The *audit record*

Every decision that matters leaves a defensible trace. Realizes UJ-2, UJ-3, UJ-4.

**Consequences (testable):**
- The *audit record* is append-only. No user-facing action edits or removes an entry; a correction is a new entry.
- Recorded at minimum: who validated what and when; the version of the ranking, the *payload schema* and the application; which values were modified versus accepted as-is; every position of **the line** with author and priced statement; every sampling run with its draw, verdicts and resulting *confidence bound*; every *override* with its reason; every retrieval with its *truth status* and *RBAC scope*; every *import job* with its *denominator*.
- Every entry carries an actor, a timestamp and a *matter*. System-initiated entries name the system component as actor rather than attributing them to a user.
- The *audit record* is scoped by *tenant* and by *RBAC scope*: a user reading it sees only entries for *matters* within their scope.
- "Modified" and "accepted as-is" are distinguishable in the record. A value the user never touched is recorded as accepted only if she performed an explicit validation act over it — not by default and not by the passage of time.

#### FR-25: *Overrides* with a mandatory one-line reason

Contradicting the machine or a system guard costs one sentence.

**Consequences (testable):**
- Any action that contradicts a machine assertion made with stated confidence, removes an entry from the *failure register* without successful *ingestion*, or bypasses a system guard, is classified as an *override* and cannot be committed without a free-text reason.
- An empty or whitespace-only reason is rejected. `[ASSUMPTION: a minimum meaningful length is enforced and repeated identical reasons across a session are surfaced in the audit surface as a quality signal — see SM-C2. The source specifies "a required one-line reason" and no more.]`
- The reason is stored verbatim in the *audit record*, attributed and timestamped, and appears in the export.
- *Overrides* are countable and filterable in the *audit drawer* and in the export, separately from ordinary modifications.

#### FR-26: The *audit drawer* and its export

The reasoning behind any single *pièce*, and the record for a whole *matter*, are both readable and both leave the building as documents. Realizes UJ-2.

**Consequences (testable):**
- From any *pièce*, the *audit drawer* opens showing: its confidence, the retained extracts behind that confidence (each resolving to a *chunk* and a source position), the proposed *audit record* entry in readable form, and reversible actions.
- Every action offered in the *audit drawer* is reversible and each produces an *audit record* entry.
- The *audit record* for a *matter* is exportable as a document, within the user's *RBAC scope*, containing: the *denominator*, the position history of **the line**, all sampling runs and their *confidence bounds*, all *overrides* with reasons, and the modified-versus-accepted breakdown.
- The export is self-contained: a reader with the export and no access to the system can reconstruct every number in it. Asserted by test.
- The export never contains material outside the exporting user's *RBAC scope*.

---

### 4.6 The *worklist* home screen

**Description.** The home screen answers "what needs you?", not "what can I do?". It opens on a queue: what failed to import, what needs re-reading, which *matters* are moving. Human-in-the-loop stops being a policy statement in a proposal and becomes a queue with items in it. The design rule is absolute and is the thing most likely to erode: **every line is an action in the lawyer's language, never a technical state.** Not actionable means not on the *worklist*. Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-27: The *worklist*, actionable lines only

The home screen is a queue of human tasks.

**Consequences (testable):**
- Every *worklist* line has: a phrasing in the user's language naming the thing and the action (*"14 pièces illisibles — les traiter"*), a count where a count applies, and a single click-through to the surface where the action is performed.
- A line whose click-through leads nowhere actionable is a defect. Asserted by test: every generated line type resolves to a surface with an available action.
- No line exposes a technical state, a component name, an error code as its primary text, a stack trace, or a job identifier. Diagnostics live behind the line, not on it.
- Lines are generated by, at minimum: *failure register* entries, low-quality OCR flags, *pièces* with no computable confidence, incomplete sampling runs, stale *confidence bounds*, halted *import jobs*, and index-mismatch halts (FR-10).
- Completing the action removes the line; the line's history remains in the *audit record*.
- A line is never removed by the passage of time, by a background process, or by being viewed.

#### FR-28: The permanent *denominator* on the home screen

The user always knows what the system was given and what it did with it.

**Consequences (testable):**
- The *denominator* for the user's *RBAC scope* is displayed on the home screen at all times, in the stated form, alongside the *worklist*.
- Clicking the unreadable count opens the *failure register* filtered to it.
- The *denominator* is never displayed as a percentage alone and never as a health indicator; the absolute counts are always present.

---

### 4.7 Tenancy and configuration

**Description.** Tenant isolation is a day-one invariant because retrofitting multi-tenancy is the classic rewrite trigger. Customisation is **data, never code**: a consultancy says yes to bespoke requests, and every yes becomes a code fork unless configuration absorbs it — forking is survivable at three clients and fatal at eight. And "only code travels" has to be verifiable rather than declarative: the *content-free projection* is built once, tested for content-freedom, and used by the client-pushed diagnostic export. There is no telemetry, by design; the client pushes, APX never pulls.

**Functional Requirements:**

#### FR-29: Tenant isolation

Data, configuration and identities belong to exactly one *tenant* and never cross.

**Consequences (testable):**
- Every stored record carries its *tenant*, enforced at the write boundary. A record without a *tenant* cannot be written.
- Every read is constrained by *tenant* before *RBAC scope* is applied. An adversarial test asserts zero cross-*tenant* results, counts or metadata across every retrieval, export and diagnostic surface.
- Identity, authentication and authorisation are properties of the application, not of the hosting environment, so that isolation holds identically in a hosted deployment and in a single-machine installation inside a firm. *(Rationale and the acceptable/not-acceptable boundary: `addendum.md` §1.)*
- A *tenant*'s data is never used to compute anything shown to another *tenant*, including aggregate statistics and model behaviour.

#### FR-30: Configuration-as-data

Per-*tenant* behaviour is data rows, never a code branch.

**Consequences (testable):**
- At minimum the following are *configuration-as-data*, editable per *tenant* without a code change or a deployment of different code: the triage taxonomy and its labels; *RBAC scopes* and their assignment; the language model provider and its endpoint; the configured sources; the chunking configuration; thresholds referenced by FR-3, FR-12 and FR-23; and interface language.
- A test asserts that no *tenant*-specific identifier, name or behaviour appears anywhere in source code.
- Every configuration key referenced in any documentation exists in the configuration surface and is asserted to exist by a test. *(v1 defect: keys named in documentation appeared in zero source files; the embedder variable was named wrongly in the example configuration. Documentation lied in load-bearing places.)*
- Every configuration key has a defined default, and a test asserts that no default disables the guarantee its key governs. *(v1 defect: the off-corpus gate shipped disabled by default.)*
- Changing a configuration value that affects retrieval, ranking or the *confidence bound* is recorded in the *audit record* and marks derived artefacts stale.

#### FR-31: The *content-free projection* primitive

There is exactly one mechanism for emitting information about a *tenant*'s data without emitting the data, and its content-freedom is enforced by a test.

**Consequences (testable):**
- The primitive emits only: counts, enumerated error classes, version identifiers, timing figures, and diagnostics passed through a redaction step.
- A test asserts content-freedom by construction: given a *corpus* seeded with known unique tokens, no output of the primitive contains any of them. This test is the guarantee; a statement in a document is not.
- Filenames, paths, *matter* names, user names, *pièce* content, *chunk* content and query text never appear in the output. Where a name is needed for correlation, an opaque identifier is used.
- All emission of information about a *tenant*'s data goes through this primitive. A second, ad-hoc path is a defect.

#### FR-32: The client-pushed diagnostic export

The firm can send APX a diagnostic; APX can never fetch one.

**Consequences (testable):**
- The export is initiated by a user of the *tenant*, never by a remote request. There is no inbound channel by which APX can trigger it. Asserted by test.
- The export is produced by FR-31 and is inspectable by the user in full, in readable form, before it leaves — no opaque blob.
- The export contains at minimum: the *denominator*, *failure register* counts by error class, component and schema versions, and redacted diagnostics.
- Producing an export is recorded in the *audit record* with actor and timestamp.
- **There is no telemetry.** A test asserts that the application makes no outbound call carrying *tenant* information other than the user-initiated export and the configured language model provider.

#### FR-33: One *ingestion* path — no fixture layer, no demo override

Corpora are data sources, never fallbacks. *(v1 defect: a demo helper swapped a healthy backend response for hand-authored fixtures whenever a provider flag was set — the demo layer literally overrode the real product, and two whole screens never called the backend at all.)*

**Consequences (testable):**
- No code path substitutes stored, hand-authored or generated content for a live response from a working component, under any flag, environment variable or build configuration. Asserted by test.
- Every configured corpus — including any evaluation corpus — enters through *ingestion* (FR-1…FR-6) exactly as client material does. A corpus is selected by *configuration-as-data*.
- Every screen that displays data obtains it from the application's own components. A test asserts that no screen renders from an embedded literal dataset.
- Test fixtures exist only inside the test suite and are unreachable from any runtime code path.
- The v1 fixture layer is **deleted**, not disabled.

---

### 4.8 Internationalisation

**Description.** FR/EN, done properly, because v1's approach is fatal for a Luxembourg deployment and would be fatal again for an Italian one: French source strings were used as translation keys with silent fallback, one whole route was untranslated, dates were hard-coded to a French locale, and no language ever reached the language model — so a Luxembourg user got a French-shaped product with English chrome and French model output.

**Functional Requirements:**

#### FR-34: Namespaced translation keys, no silent fallback

**Consequences (testable):**
- Every user-visible string is referenced by a structured, namespaced key. A natural-language string is never used as a key. Asserted by test.
- A missing translation is detected at build time and fails the build; it never falls back silently to another language at runtime.
- A test asserts key-set parity across all supported languages: no key present in one and absent in another.
- Coverage is asserted across every route and every surface, including *worklist* lines, *failure register* error classes, justifications, the *confidence bound* sentence and every export. A route with zero translated strings fails the build.

#### FR-35: Locale-aware dates, numbers and sorting

**Consequences (testable):**
- No date, number or currency format is hard-coded to a locale anywhere in the code. Asserted by test.
- Dates rendered to a user use that user's locale; dates stored and dates in exports use an unambiguous, locale-independent representation.
- A *pièce*'s own date and its ingestion timestamp are rendered distinguishably and are never conflated (FR-8).
- Sorting of user-visible lists respects the active locale's collation.

#### FR-36: The language reaches the language model

**Consequences (testable):**
- Every request to a language model carries an explicit language for the expected output, derived from the user's active locale or from *tenant* configuration.
- Machine-generated user-facing text — the one-line justifications (FR-18), the priced statement (FR-19), the *confidence bound* sentence (FR-23) — is produced in that language. Asserted by test with the locale switched.
- Where the source *pièce* language differs from the interface language, the output states the source language rather than silently translating without saying so.
- Language selection is *configuration-as-data* per *tenant* and per user, not a build-time constant.

---

## 5. Non-Goals (Explicit)

- **Syllogisme drafting is not in this increment.** No drafting surface, no per-section skeleton (EN FAIT / EN DROIT / PAR CES MOTIFS), no per-block diff acceptance, no `.docx` export on a firm template, no style profile and no statistical style fingerprint. They move to the next increment on this same spine. The cost of deferring is named honestly in the brief: triage does not force the citation checker or the drafting surface into existence, so they must now be sequenced deliberately rather than arriving as a side effect.
- **The citation checker is not in this increment.** Tier (a) verification against Judilibre and Légifrance belongs with drafting. The exact-containment primitive (FR-11) is built now; the checker that consumes it is not.
- **This is not a legal research tool** and must never present itself as one. Retrieval is over the *tenant*'s own *corpus*. APX cannot compete on corpus depth against publishers with two centuries of doctrine, and pretending otherwise is a losing fight fought on the opponent's ground.
- **No *veille* module** in this increment.
- **No admin cockpit.** There is nothing installed to operate. Its foundation — *configuration-as-data* — is in scope; the operator interface is not.
- **No shared SaaS hosting** as a product offering.
- **No fine-tuning on client data**, ever. Inherited and not up for debate.
- **No live connectors** to practice-management systems, mail servers or document management systems. Onboarding is a folder.
- **No fully local model.** The premium sovereign tier is only worth building once a firm refuses the hosted model provider in writing.
- **No auto-update delivery mechanism.** Signed, offline-installable, reversible migrations against a live 100 000-document index is the genuinely unsolved problem; it is deferred, not solved (§16).
- **No telemetry, ever.** The client pushes a *content-free projection*; APX never pulls. This is a constraint, not a gap.
- **No automatic action without a human.** No auto-delete, no auto-send, no auto-sign. Human-in-the-loop is a queue with items in it, not a policy sentence.
- **No published hallucination rate, and no unaudited accuracy claim.** The competitive record shows exactly what happens to a vendor whose unaudited number is tested by a client (`04-competitive-landscape.md` §4.1, §8.4).
- **No AI Act compliance claim in product or pitch.** Legal AI sold to law firms is very likely outside Annex III high-risk, and the regime moved to 2 December 2027; leading with it signals APX has not read the Digital Omnibus (§12).
- **The fixture layer is deleted, not disabled** (FR-33). It is listed here because it was load-bearing in v1 and deleting it will feel like a loss during the first demo.

---

## 6. MVP Scope

### 6.1 In scope

**The shared spine** — unchanged by the pivot from drafting to triage, and the majority of the work:

- Frozen *payload schema* with *RBAC scope*, provenance, *matter* and dates on every *chunk* (FR-8).
- *RBAC scope* as a query pre-filter (FR-14).
- Resumable, idempotent *ingestion* with a queue and workers, plus the *failure register* and the inventory guarantee (FR-1…FR-7).
- A real semantic embedder that fails loudly, and an index that never deletes itself (FR-9, FR-10).
- Deterministic exhaustive search alongside semantic retrieval, with declared *truth status* (FR-12, FR-13, FR-15).
- The *audit record* with reasoned *overrides* (FR-24, FR-25).
- Tenant isolation and *configuration-as-data* (FR-29, FR-30).
- Folder and USB *ingestion* (FR-1).
- FR/EN internationalisation done properly (FR-34…FR-36).
- Retrieval measured against the *gold set* in CI (§8).
- The *content-free projection* primitive and the client-pushed diagnostic export (FR-31, FR-32).

**The triage layer:**

- One ranked order with nothing deleted and nothing categorised (FR-16).
- **The line**, drawn by the tool and movable by the user, priced before it moves (FR-17, FR-19).
- Per-*pièce* confidence and a one-line reversible justification (FR-18).
- The editable cell-by-cell table with a live *change log* and no destructive regeneration (FR-20).
- Random sampling over the *discarded set* with a *confidence bound* (FR-22, FR-23).
- The *audit drawer* and its export (FR-26).
- The *worklist* home screen with the permanent *denominator* (FR-27, FR-28).

**Design target: 100 000 documents.** Every scale-sensitive consequence above is asserted at that target, not at demo scale.

### 6.2 Out of scope for MVP

- **Syllogisme drafting, the style profile, the statistical fingerprint and `.docx` export** — next increment, same spine. `[NOTE FOR PM]` This is the deepest vertical slice and the thing the original plan was built around; the reversal was made on commercial and competitive evidence and the depth-forcing property is genuinely lost. Revisit sequencing if the first engagement is a drafting engagement.
- **The citation checker (all tiers)** — next increment.
- ***Veille*** — a separate module, later.
- **Admin cockpit** — nothing to operate yet.
- **Shared SaaS hosting** — packaging decision, not a first-increment feature.
- **Auto-update delivery / on-premise update mechanism** — deferred, not solved (§16). `[NOTE FOR PM]` Deferring this is correct for one installation and compounds badly from the second: version drift across blind installations is unrecoverable if it is allowed to start.
- **Fully local model** — premium tier, on demand.
- **Fine-tuning** — never.
- **Live connectors** — folder ingestion is the whole onboarding story.
- **Italian localisation** — see OQ-3. The i18n mechanism (FR-34…FR-36) is built so that adding a language is data, not a project.
- **The fixture layer** — deleted (FR-33).

---

## 7. Success Metrics

*Each metric cross-references the FRs it validates. Counter-metrics are as load-bearing as the primary metrics: they prevent the build from optimising the wrong thing.*

### Primary

- **SM-1 (north star) — the sayable sentence.** For every *matter* where triage has run and a sampling run has completed, the system produces the *confidence bound* as a sentence a lawyer can say to a client or a judge, and every number in it is reconstructible from the exported *audit record* alone. **Target: 100% reproducibility**, asserted by an automated test that recomputes from the export and compares. Validates FR-22, FR-23, FR-24, FR-26. *This converts "recall over precision" from an intention into a number, and it is the direct answer to the only named non-negotiable requirement APX has ever received from a client.*

- **SM-2 — recall against the *gold set*, executed in CI.** Recall at **the line** is measured against a *gold set* with human relevance judgments on every CI run, and the figure is recorded. A run whose recall is below the previously recorded figure fails the build. **No absolute target is set in this PRD** — the source documents state none, and inventing one here would be exactly the kind of unaudited number §5 forbids. See OQ-5. Validates FR-16, FR-17, FR-18, and §8. *v1 had a gold set and never once ran it; the metric that matters most is that it runs at all.*

- **SM-3 — the inventory guarantee holds.** `submitted = indexed + failure register`, exactly, for 100% of *import jobs*, asserted after every job and every retry, at the design target of 100 000 documents. **Target: zero violations, ever.** A single violation is a release blocker, not a bug. Validates FR-5, FR-6.

### Secondary

- **SM-4 — idempotency.** Re-importing an identical folder changes the *corpus* count by zero and modifies zero existing *pièces*. **Target: exact.** Validates FR-4.
- **SM-5 — loud failure.** Under injected faults (embedder unavailable, dimension mismatch, corrupt file, OCR failure), the number of silently degraded outcomes is **zero**: every fault produces either a *failure register* entry or a halt, plus a *worklist* line, and never a *chunk*. Validates FR-9, FR-10.
- **SM-6 — isolation.** The adversarial *RBAC scope* and *tenant* suite returns **zero** out-of-scope results, counts, snippets or metadata across every retrieval, export and diagnostic surface. **Target: zero. Any non-zero is a professional-conduct incident, not a defect.** Validates FR-14, FR-29, FR-31.
- **SM-7 — content-freedom.** The seeded-token test over the *content-free projection* finds **zero** *tenant* tokens in any emitted output. Validates FR-31, FR-32.
- **SM-8 — the tool commits.** Proportion of triaged *matters* where **the line** was placed by the system with a stated basis: **100%**, or an explicit refusal to place it. A ranking presented without **the line** and without a refusal is a defect. Validates FR-17.
- **SM-9 — edits survive.** In a scripted session of ≥20 cell edits interleaved with a re-ranking, **zero** edits are lost or overwritten. Validates FR-20.
- **SM-10 — installed, not demoed.** The increment is installed and running at a real firm on their own documents. This is a binary and it is the only success metric that is not measurable in CI. `[ASSUMPTION: no date is attached to this metric; no engagement exists to attach one to.]`

### Counter-metrics (do not optimise)

- **SM-C1 — relevant *pièces* below **the line**.** The count of *gold set* relevant items falling in the *discarded set*. **This number may never rise, even if the *retained set* shrinks and precision improves.** Counterbalances SM-2 and any temptation to make triage look better by retaining less. A change that reduces the *retained set* by 30% while moving one relevant item below **the line** is a regression, not an optimisation. The whole product exists because recall beats precision here; the metric must make that unarguable.
- **SM-C2 — *worklist* dismissal and *override* reason quality.** Two figures, tracked together: the proportion of *worklist* lines closed without the underlying action being performed, and the proportion of *override* reasons that are duplicates of an earlier reason in the same session or below a minimum meaningful length. **A rise in either means the audit surface has become noise the user has learned to dismiss** — which is the precise failure mode of every compliance feature ever shipped. Counterbalances FR-25, FR-27 and the whole of §4.5. `[ASSUMPTION: no thresholds are set; these are trend metrics whose direction is the signal, and with no telemetry they are observable only in evaluation sessions and in what a firm chooses to push. See OQ-9.]`
- **SM-C3 — abandoned sampling runs.** The proportion of sampling runs started and not completed. A high figure means the sampling ritual is too expensive to perform and the *confidence bound* is theatre. Counterbalances SM-1.
- **SM-C4 — time to first useful screen.** If **the line** is placed only after the entire *import job* completes, a 100 000-document import gives the lawyer nothing for the duration. Optimising SM-3 and FR-6 must not push the user's first useful moment to the end of the job. `[ASSUMPTION: partial triage over a partially-ingested corpus is desirable but is not specified as an FR — it interacts with the inventory guarantee in a way the sources do not address. See OQ-7.]`

---

## 8. Corpus and Evaluation Strategy

*Invented section. It exists because with no client and no client corpus, the corpus is the first real engineering problem of this increment rather than an afterthought — and because v1's central defect was manufacturing its own data. Source: brief `addendum.md` §2. Concrete sourcing detail is in this PRD's companion `addendum.md` §2.*

**The problem.** No engagement has been won, so there is no client *corpus*. The public-corpus move that solves the fake-data problem for drafting and *veille* — real published legal text — does **not** solve it for triage: published case law is clean, structured and uniformly relevant, which is the exact opposite of the undifferentiated dump triage exists to survive. And synthetic documents are precisely what produced v1.

**The resolution is to separate two things v1 conflated: real content and real mess.** No single source has to supply both, and none of them has to be invented.

| Need | Source | What it gives, and what it does not |
|---|---|---|
| **Real mess at volume** — genuine threading, duplicates, attachments, dead ends | **Enron / EDRM corpus**, ~500 000 genuine business emails, public since the FERC release; the canonical dataset of the e-discovery field | Actual human correspondence, messy for the right reasons. English — this limits *language* realism, not *pipeline* realism. Licence terms of the specific distribution used must be verified before use. |
| **A measurable recall target** | **TREC Legal Track** collections, built for e-discovery evaluation with human relevance judgments | This is the *gold set* that gives the *confidence bound* something real to be scored against. v1 had a gold set and never ran it; running it is SM-2. |
| **French-language realism** | Real French public legal and administrative text, **mechanically degraded**: rendered as skewed scans, wrapped in `.msg` with plausible headers and reply chains, duplicated with variations, a fraction deliberately corrupted | The *content* is real; only the *degradation* is manufactured — and degradation is the thing under test. This is categorically different from fabricating documents. |
| **A small genuinely-owned dump** | APX Advisory's own mail, proposals and project files | Tiny, but unquestionably real and owned. A smoke test, not an evaluation set. |

**Requirements this section imposes:**

- **Every corpus enters through *ingestion*** (FR-33). A corpus is a data source selected by *configuration-as-data*. It is never a fixture, never a demo branch, never a fallback that can override a working system.
- **SM-2 runs in CI against the *gold set***, every run, with the figure recorded and regression failing the build.
- **The degradation pipeline is itself part of the test surface**: the mechanical degradations applied to French public text are the inputs that must produce *failure register* entries of the expected error classes (FR-5), so the degradation configuration and the expected failure classification are asserted together.
- **The *denominator* is verified at 100 000 documents** using the assembled corpus, not extrapolated from a smaller run (SM-3).

**Accepted risk, stated plainly and not smoothed.** Without a firm looking at the output, classification quality is measured against public benchmarks rather than against a practitioner's judgement of their own *matter*. The benchmarks make the product **measurable**; they do not make it **wanted**. This is the same drift — toward what is buildable rather than what is wanted — that produced v1, and no mechanism in this PRD prevents it. The only thing that does is a real *matter*.

**Highest-value acquisition for this increment:** one real anonymised litigation *matter*, from any friendly practitioner, on any terms. No signed engagement is required. Ask by shape and volume, not in the abstract — *"one closed matter, 200+ pièces, mostly email, anonymised however you like"* is a request a practitioner can act on; "some documents" is not. That framing failure is the most likely reason nothing ever arrived before.

---

## 9. Cross-Cutting NFRs

- **Scale.** Every consequence in §4 that is scale-sensitive is asserted at the design target of **100 000 documents** per *tenant*. Demo-scale verification does not satisfy an FR. `[ASSUMPTION: no per-operation latency or throughput target is set — the sources state none. See OQ-6.]`
- **Testability as a first-class requirement.** With one non-hands-on CTO and AI agents as the whole team, **tests are the substitute for the engineers who are not on the team**. An AI-driven build with no test suite is v1 again, faster: v1 ran approximately 80% untested with its test command erroring outright. Every FR above states its consequences in testable form for this reason, and an FR shipped without its consequences asserted is not shipped.
- **Fail loudly, everywhere.** No component degrades silently under failure. Every failure produces one of: a *failure register* entry, a halt, or a *worklist* line — and never a plausible-looking wrong answer. This generalises FR-9 and FR-10 into a system-wide rule.
- **Fail closed on access.** Every ambiguity in *tenant* or *RBAC scope* resolves to less access, never more (FR-14, FR-29).
- **Determinism where determinism is claimed.** Anything labelled *exhaustive* *truth status*, and anything reconstructible from the *audit record*, must be reproducible: same inputs, same output, on a different machine and after a restart.
- **Append-only where evidence is claimed.** The *audit record*, the *change log* and the *failure register* are append-only (FR-21, FR-24).
- **No hard dependency on any hosting-provider primitive.** The fitness function: *can this run, unmodified, on a single machine inside a law firm with no internet connection?* Anything that fails it goes behind an adapter. The acceptable/not-acceptable boundary and the rationale are in `addendum.md` §1.
- **Reversibility of every third-party choice.** Anything that could be compelled, priced or discontinued by a third party — the model provider above all — lives behind an interface, so the decision is a configuration line rather than a rewrite.
- **Observability without telemetry.** The product must be diagnosable by its user, over the telephone, by someone who cannot see it. That means: state visible on the *worklist*, error classes enumerated and stable, versions readable in the interface, and the *content-free projection* as the only export path.
- **Accessibility and non-technical usability.** The daily user is non-technical and works at inconvenient hours. Adoption is voluntary in practice: a partner cannot make someone use a tool that adds friction — they route around it. Nothing superfluous; no technical vocabulary in any user-facing surface.
- **Visual consistency as a build requirement.** One token set, one colour system, no hard-coded values. *(v1 defect: three unreconciled colour systems, ~20 hard-coded values, no settings surface — which made per-*tenant* configuration unbuildable as a direct consequence.)*

---

## 10. Constraints and Guardrails

### Safety

- **Human-in-the-loop everywhere.** No auto-delete, no auto-send, no auto-sign. Inherited, not up for debate.
- **Never hard-delete.** *Triage* is reversible labelling (FR-21).
- **Recall over precision** in triage, made unarguable by SM-C1.
- **Targeted friction, not uniform friction.** Confirmation is demanded where a decision carries consequence — an *override* (FR-25), a move of **the line** (FR-19) — and nowhere else. Uniform friction is ignored friction, and ignored friction is worse than none because it produces a record that looks like consent.
- **The product must never present a guess as a proof.** This is the single design rule behind *truth status* (FR-15) and the reason a score threshold can never yield an *exhaustive* result set.

### Privacy and confidentiality

- **EU-only.** Inherited.
- **Zero-retention** with the model provider. Stated honestly: this is a **contract clause, not a technical property** — every retrieval-augmented request carries client text off the machine unless a fully local model is used, and a fully local model is out of scope (§5).
- **No fine-tuning on client data.** Ever.
- **Only code travels.** APX never accesses, sees or extracts client data. Follow-up is by telephone and human communication. The price of that boundary is no telemetry; the mitigation is a self-diagnosing product plus the client-pushed *content-free projection* (FR-31, FR-32).
- **RBAC by *matter* — Chinese walls** (FR-14). A cross-*matter* leak is a professional-conduct violation that happens silently, with no error message. It is the #1 realistic leak vector, ahead of the model provider and ahead of logs.

### Cost

- **Every shipped feature is a permanent tax**: tested, migrated blind against a 100 000-document index at every installation, defensible in front of a judge, supported by telephone with no telemetry. At three on-premise firms, one more feature is three blind deployments maintained forever.
- **"It's just tokens" is the identified failure belief** and the one this capacity makes most tempting. Writing code is nearly free; owning it is not. Unchecked, this belief reproduces v1 verbatim.
- **The buyer's reference price is low and public.** A 30-lawyer firm's realistic alternatives run €7k–79k per year, and the CCBE has publicly priced the hardware at €2 000–20 000. The product cannot be justified on cost of ownership; it is justified on removing a named confidentiality risk. This constrains scope: features that cost owning and do not serve that argument do not earn their place.

---

## 11. Data Governance

- **Residency.** All *tenant* data — *pièces*, *chunks*, *payload schema* records, *audit record*, *failure register*, configuration — resides within the *tenant*'s boundary: inside the firm for an on-premise installation, within the EU for a hosted one. Inherited, not up for debate.
- **Classification.** Every *chunk* carries its *tenant*, its *matter* and its *RBAC scope* in the *payload schema* (FR-8). Classification is a property of the data, not of the surface that displays it — which is why the pre-filter (FR-14) is possible at all.
- **Provenance.** Every *chunk* traces to a source *pièce* and a position within it, with the extraction method recorded (FR-8, FR-11). Nothing in the *corpus* is of unknown origin.
- **Retention.** Nothing is hard-deleted (FR-21). The *audit record*, *change log* and *failure register* are append-only. `[ASSUMPTION: no retention period is defined. A law firm has statutory retention obligations per matter and a client may make an erasure request; "never hard-delete" and lawful erasure are in tension and this PRD does not resolve it. See OQ-8.]`
- **Separation of derived data.** No *tenant*'s data contributes to anything shown to another *tenant*, including aggregates and model behaviour (FR-29). No client data is used for fine-tuning, ever.
- **Egress.** Exactly two egress paths exist: the configured model provider (carrying query and retrieved context, under a zero-retention clause) and the user-initiated *content-free projection* (FR-32). Any third path is a defect, and a test asserts their absence.

---

## 12. Compliance and Regulatory

*This section states what the product must satisfy and what it must not claim. It is a build constraint, not a sales narrative.*

- **Secret professionnel is the binding obligation.** In France, Art. 226-13 Code pénal; in Luxembourg, Art. 458 Code pénal plus the Bar's internal regulations — where it is a **criminal** obligation rather than a purely deontological one, which raises the bar above France's. This is the obligation FR-14 and FR-29 exist to satisfy mechanically.
- **The CNB guide (17 March 2026)** sets the criteria a *bâtonnier* will actually apply: data located in France or the EU; nationality of the server owner (European, excluding entities subject to extraterritorial laws); location of model hosting; nationality of the model provider; and **systematic verification of AI output**. `[ASSUMPTION: these criteria are reported second-hand from a practitioner reading; obtaining the source PDF is an open action — see OQ-11. They are currently doing load-bearing work.]` Running inside the firm's walls satisfies the first four by construction; FR-15, FR-24 and FR-26 are the product's answer to the fifth.
- **GDPR.** Art. 32 (security of processing) and Art. 44 et seq. (transfers) are the applicable provisions, together with the *tenant*'s own role as controller. Residency and egress are covered in §11.
- **The EU AI Act is not a compliance driver for this increment, and must not be used as one.** Legal AI sold to law firms is very likely outside Annex III high-risk (that provision covers use by or on behalf of judicial authorities), and the high-risk regime was deferred to 2 December 2027 by the Digital Omnibus. Art. 50 transparency applies from 2 August 2026. **Leading with "AI Act compliance" signals APX has not read the Omnibus** and a sophisticated general counsel will know it. Still worth a lawyer's confirmation, but it is not a blocking question.
- **Extraterritorial access is not resolved by an EU region.** The strongest available evidence on this point is Microsoft France's sworn testimony to the French Senate on 10 June 2025 that it could not guarantee French data would never be transmitted to US authorities. This is why the model provider sits behind an adapter (§9) — it makes the choice reversible as a configuration line rather than a rewrite. It is mitigated, not resolved. See OQ-12.
- **No compliance certification is claimed or pursued in this increment**, and no accuracy or hallucination figure is published (§5).

---

## 13. Audit Trail / Decision Provenance

*The formal requirement, consolidated. Mechanisms are in §4.5; this states what the record must be able to answer.*

Given only the exported *audit record* for a *matter*, a reader with no access to the system must be able to answer, for any *pièce*:

1. **Did it enter the *corpus*?** If not, why not, and is it in the *failure register* with which error class — and was it ever retried, by whom?
2. **Where did the tool place it, and on what basis?** Its confidence, its one-line justification, and the retained extracts behind it, each resolving to a *chunk* and a source position.
3. **Where was **the line** at the time?** Who put it there, when, and what priced statement were they shown when they moved it?
4. **Did a human look at it?** Was its value accepted as-is or modified — and "accepted" only where an explicit validation act occurred, never by default and never by elapsed time.
5. **Was any machine assertion overridden?** By whom, when, and with what stated reason.
6. **What can be said about what was set aside?** Which sampling runs were performed, over which draw, with which verdicts, producing which *confidence bound*, against which ranking version and which position of **the line**.
7. **What was the *denominator*** at the moment any of the above was asserted.

Properties: append-only; scoped by *tenant* and *RBAC scope*; every entry attributed and timestamped; system-initiated entries attributed to the system component rather than to a user; and self-contained on export, so that every number in it is recomputable from the export alone (SM-1).

The gap, stated rather than smoothed: this record proves a *human decision was made and recorded*. It does not prove the decision was *correct*. That is what the sampling *confidence bound* is for, and the *confidence bound* is itself a probabilistic statement — it bounds the risk, it does not eliminate it.

---

## 14. Platform

- **Web application**, usable on a standard workstation without an installation step for the daily user. `[ASSUMPTION: the sources state a "VS Code-style local packaging" direction for on-premise delivery but do not specify the client surface for this increment; a browser-reachable application served by the installed system is the reading that satisfies both the hosted-development tier and the single-machine installation.]`
- **Deployment-agnostic core.** The same code must run in a hosted deployment and on a single machine inside a firm with no internet connection. Hosted versus on-premise is a **packaging decision per *tenant***, never a fork. The acceptable/not-acceptable boundary is in `addendum.md` §1.
- **Local filesystem and removable-drive access** are required for FR-1 — this is the whole onboarding story and it constrains the client surface.
- **Languages: FR and EN** at parity (FR-34). Italian is OQ-3.
- **No mobile surface** in this increment.
- **Offline capability**: an on-premise installation must function without internet access except for the configured model provider, whose absence must degrade loudly (§9) rather than silently.

---

## 15. Integration and Dependencies

*In scope for this increment:*

- **The filesystem** — the only ingestion integration. Folders, subfolders, removable drives (FR-1).
- **A language model provider**, behind a provider-agnostic adapter so the choice is a configuration line. The only outbound path carrying *tenant* content, under a zero-retention contract clause (§11).
- **An OCR capability**, behind an interface, for scanned PDFs and images (FR-3). Must run inside the *tenant* boundary for an on-premise installation.
- **A semantic embedder**, behind an interface, that fails loudly (FR-9).
- **The evaluation corpora** — Enron/EDRM, TREC Legal Track, degraded French public text — as configured data sources entering through *ingestion* (§8, FR-33).

*Explicitly not integrated in this increment:*

- Practice-management systems, document management systems, mail servers — no live connectors (§5).
- **Judilibre and Légifrance** — the free public sources for tier-(a) citation verification. Named here because they are the dependency the next increment takes on, and because taking them on later must not require changing the *payload schema*. `[ASSUMPTION: the payload schema is designed now to accommodate an external-authority reference on a chunk, even though nothing in this increment writes one. Getting this wrong is the one mistake that cannot be undone cheaply.]`
- Identity providers, single sign-on — identity is a property of the application, not of the hosting environment (FR-29).
- Any telemetry or monitoring service (FR-32).

**Dependency policy.** Anything that could be compelled, priced or discontinued by a third party lives behind an interface. Applied without exception to the model provider, the embedder, OCR, storage and any queueing mechanism.

---

## 16. Deployment and Update Mechanism

**In scope for this increment:** a first installation, performed by APX, at one firm, on their documents. Installed — not demoed.

**Requirements that hold from the first installation:**

- The application version, the *payload schema* version and the ranking version are readable in the interface and present in the *audit record* and in the *content-free projection*. A user on the telephone must be able to read them out.
- Every *tenant*-specific behaviour is *configuration-as-data* (FR-30), so an installation differs from another by rows, never by code.
- A migration that cannot preserve every mandatory *payload schema* field of every existing *chunk* is rejected rather than run (FR-8). No migration re-indexes a *corpus* as a side effect, and no migration deletes one (FR-10).

**The genuinely unsolved problem, stated as unsolved.** Signed, offline-installable, reversible migrations that run against a live 100 000-document index without re-indexing, at a site APX cannot see, is the one technical problem in this programme that has no answer yet. It is **deferred out of this increment, not solved.** Deferring it is correct for one installation. It is not correct past the second: version drift across blind installations compounds and is unrecoverable once it starts. See OQ-13.

**No auto-update channel** in this increment (§5). Updates are generated and shipped blind, installed by agreement, and their outcome is reported back only by a user-initiated *content-free projection* (FR-32).

---

## 17. Operational Requirements

- **Support model: telephone and human communication, with no telemetry.** APX cannot see the installation. Every operational requirement below follows from that single constraint.
- **The product must be self-diagnosing.** The state a support call needs is on the *worklist* (FR-27) and in the *denominator* (FR-28): what failed, how many, of what class, and what the user can do about it — all in the lawyer's language, with the technical detail one click behind.
- **Error classes are enumerated, stable and translated** (FR-5, FR-34). A support conversation refers to a class the user can read on screen, not to a message that varies by machine.
- **Version readability** as stated in §16.
- **The diagnostic export is the only escalation path**, is user-initiated, is inspectable in full before it leaves, and is content-free by test (FR-31, FR-32).
- **No on-call, no SLA, and no uptime commitment is defined in this increment.** `[ASSUMPTION: with one non-hands-on CTO and no engineers, an availability commitment cannot be honoured and should not be written. This is stated as a gap because the brief is explicit that a firm which misses a filing deadline because APX was down does not send a support ticket — the ambition demands infrastructure-grade reliability that the current capacity cannot underwrite. See OQ-10.]`
- **Documentation must not lie in load-bearing places.** Every configuration key named in documentation exists and is asserted to exist by a test (FR-30). *(v1 defect: keys named in documentation appeared in zero source files; a module referenced throughout the documentation did not exist; a described ranking boost was applied uniformly and was therefore a no-op on ordering.)*
- **Decisions are recorded when superseded.** *(v1 defect: superseded architectural decisions were never marked, so the recorded default model and the recorded hosting provider both silently ceased to be true.)*
- **Nothing ships from a branch that is not the deployed one.** *(v1 defect: the head of development sat three commits ahead of the main branch, stranding the audit trail off the deployed branch — the sold differentiator was written and not deployed.)*

---

## 18. Risk and Mitigations

| # | Risk | Consequence if it lands | Mitigation in this PRD | Residual |
|---|---|---|---|---|
| R-1 | **Scope exceeds capacity.** The in-scope list is large for one non-hands-on CTO plus AI agents. | The increment is half-built and untested — v1 again, faster. | Sequencing against the spine (schema → ingestion → index → retrieval measured → triage → audit) rather than breadth-first; tests as the non-negotiable substitute for absent engineers (§9); `addendum.md` §3. | **High and accepted.** The brief says so plainly rather than discovering it later. No mitigation makes the list smaller. |
| R-2 | **No pilot client.** Drift toward what is buildable rather than what is wanted. | The exact mechanism by which v1 failed, repeated. | §8: measurement against public benchmarks; SM-10 as a binary; the standing acquisition ask for one real anonymised *matter*. | **High.** Benchmarks make it measurable, not wanted. Nothing in this document fixes this. |
| R-3 | **The *payload schema* is the only irreversible decision** and is made before anyone has seen a real *matter*. | A schema change after installation means a blind migration against a live 100 000-document index — the unsolved problem in §16. | FR-8 (explicit versioning, rejection rather than lossy migration); front-loaded sequencing; §15's note on accommodating an external-authority reference now. | **Medium.** Versioning limits the damage; it does not remove the lock-in. |
| R-4 | **A cross-*matter* or cross-*tenant* leak.** | A professional-conduct violation, silently, with no error message. The product's entire premise is void. | FR-14 pre-filter; FR-29; SM-6 with a zero target; fail-closed as a system rule (§9). | **Low if the tests hold. The tests are the control.** |
| R-5 | **The *confidence bound* is wrong or misapplied.** A lawyer says a number in court that does not hold. | Worse than having said nothing. The north-star metric becomes the north-star liability. | FR-23 (method stated, fixed by configuration, reconstructible from the record); OQ-4 flags the estimator as unspecified. | **Medium-high and under-specified.** OQ-4 is the most statistically load-bearing open question in this document. |
| R-6 | **The audit surface becomes noise** users learn to dismiss. | Every mechanism in §4.5 becomes ceremony, and the record documents consent that was never given. | Targeted friction not uniform friction (§10); FR-27 actionable-lines-only; SM-C2 as an explicit counter-metric. | **Medium.** This failure is gradual and invisible without observation, and there is no telemetry. |
| R-7 | **The market wedge does not convert.** Article 145 CPC demand is episodic; willingness to pay is unproven; the qualifying question — *"Refusez-vous des dossiers aujourd'hui ?"* — may be answered no. | The increment is well-built and unsold. | Nothing in this PRD. It is a commercial risk, named because engineering must not be surprised by it. | **High.** Belongs to the APX partners. |
| R-8 | **Distribution asymmetry.** An incumbent reaches 7 500 French firms with essentially this product through software they already pay for; the cheapest competitor has the strongest sovereignty claim at €19/month. | APX loses on price and on distribution simultaneously. | Positioning, not product: risk elimination for a named confidentiality-critical workflow, never TCO and never general productivity. | **High and structural.** |
| R-9 | **Zero-retention is a contract clause, not a technical property.** | The sovereignty claim is weaker than the pitch implies, and a client's counsel who looks closely will find it. | Stated honestly in §10; provider behind an adapter so the decision is reversible; the fully local model is the premium tier, out of scope. | **Medium, acknowledged rather than closed.** |
| R-10 | **Version drift across blind installations** once there is more than one. | Unrecoverable. Two firms on different code, neither observable. | §16 states it as unsolved and bounds it: correct to defer for one installation, not for two. | **Deferred, not mitigated.** OQ-13. |
| R-11 | **The one-line justification (FR-18) is model-generated and could be wrong or fluent-but-empty.** | The user trusts a sentence that explains nothing, and the *audit drawer* documents the trust. | FR-18 requires retained extracts resolving to *chunks* and source positions behind every justification — the extracts are checkable even when the sentence is not. | **Medium.** The extracts are the control; the sentence is not evidence. |

---

## 19. Open Questions

1. **Is the "same associates, more matters" narrative confirmed?** The brief assumes capacity expansion rather than headcount reduction, because the alternative gives the daily user a reason to sabotage the tool. The product cannot tell both stories. **Belongs to the APX partners, not the CTO.**
2. **Consulting forfait versus subscription.** The locked decision says forfait; the only quote ever issued priced monthly recurring cost with no development forfait at all; the market evidence points hard at forfait. Unresolved, and it changes what "configuration-as-data" has to absorb — a consultancy says yes to bespoke requests. **Belongs to the APX partners.**
3. **Is Italian in scope, and when?** Several Italian firms are in discussion with the APX partners; one recorded prospect holds ~15 years of documents on a physical server in Italy, which is an on-premise deployment. FR-34…FR-36 make adding a language data rather than a project, but the decision affects sequencing and the *gold set*.
4. **What is the estimator behind the priced statement (FR-19) and the *confidence bound* (FR-23)?** The sources give the sentence and the shape of the numbers — *"400 more pièces, risk falls from 3% to 0.4%"* — but not the statistical method, not whether sampling is simple random or stratified by rank, and not how a risk figure is projected for a candidate position of **the line** before any sample has been taken there. This is the most load-bearing unspecified item in the document. It needs a statistician's answer, not a guess.
5. **What recall target does SM-2 assert?** No target exists in the sources. Setting one before the *gold set* has ever been run would be inventing a number. Must be set from the first measured baseline, and then may only improve (SM-C1).
6. **What are the performance targets at 100 000 documents?** Import wall-clock, exhaustive-search latency, time to first ranking. None are stated in the sources; SM-C4 depends on the answer.
7. **Can triage run over a partially-ingested *corpus*?** Desirable (SM-C4) but it interacts with the inventory guarantee: a *denominator* that is still moving, and **the line** placed on incomplete evidence. Not specified as an FR because the sources do not address it.
8. **How does "never hard-delete" coexist with lawful erasure?** A firm has statutory retention obligations per *matter*, and a data subject may request erasure. FR-21 and §11 name the tension and do not resolve it.
9. **How are SM-C2 and SM-C3 observed with no telemetry?** They are the counter-metrics that protect the audit surface from becoming noise, and they are precisely the ones a firm would have to volunteer. Currently observable only in evaluation sessions and in what a *tenant* chooses to push.
10. **What availability is committed, if any?** §17 declines to write one. The brief is explicit that a firm missing a filing deadline because APX was down does not send a support ticket. The ambition and the capacity are in open contradiction here.
11. **Obtain the CNB March 2026 guide itself.** Its hosting and nationality criteria are currently second-hand from a practitioner reading and are doing a great deal of load-bearing work in §12.
12. **Cloud Act acceptability.** "EU region" is not sufficient against a US-operated provider. Mitigated but not resolved by the provider-agnostic adapter, which makes the choice reversible as a configuration line. **Belongs to the APX partners and, ideally, to a client's counsel.**
13. **On-premise update delivery.** Signed, offline-installable, reversible migrations against a live 100 000-document index, at a site APX cannot see. Genuinely unsolved (§16). Must be answered before the second installation, not the second increment.
14. **Scale beyond the design target.** Is 100 000 → 1 000 000 documents just more compute? Unanswered in every upstream document.
15. **Should the human baseline be measured?** The honest comparison for triage is not perfect human review but what happens today — skimming under deadline — and it can be measured by sampling a lawyer's own past triage. Telling a client you measured their error rate is a delicate sales choice, and it is a choice, not an engineering decision.
16. **Does the triage taxonomy carry over?** v1's nine-label taxonomy is on the salvage list. Whether it is the right taxonomy for *ordonnance 145 CPC* review is unvalidated — it is *configuration-as-data* (FR-30), so getting it wrong is cheap, but shipping it unexamined would be inheriting a v1 assumption unexamined.
17. **Can one real anonymised *matter* be obtained before build starts?** Named as the highest-value acquisition for this increment (§8). It has never arrived, and the most likely reason is that it was always asked for in the abstract.

---

## 20. Assumptions Index

*Every `[ASSUMPTION]` in this document, surfaced for confirmation. Correcting any of these is cheaper now than after §4 has been built.*

| # | Section | Assumption |
|---|---|---|
| A-1 | §2.2 | Italian-speaking users are non-users of this increment; Italian is treated as an open question rather than a requirement, despite Italian firms being in discussion with the APX partners. |
| A-2 | §2.3 | Persona names are illustrative composites drawn from the discovery record. No firm and no client is named anywhere in this document. |
| A-3 | §2.3 UJ-1 edge case | The user is told how many *pièces* were recognised as already present rather than having them silently skipped — silence reads as data loss to a user promised that nothing is ever deleted. |
| A-4 | §2.3 UJ-2 | The sceptical senior lawyer's random-sampling audit journey is an inference from the requirement, not a narrated scene from discovery. |
| A-5 | §2.3 UJ-3 | The associate's cell-by-cell correction journey is an inference from the requirement, not a narrated scene. |
| A-6 | §2.3 UJ-3 edge case, FR-20 | Concurrent editing within one *matter* is in scope. The sources do not address it; a shared *matter* with a partner and two associates makes it near-certain. |
| A-7 | §2.3 UJ-4 | The line-moving journey is an inference; the priced sentence itself is from source. |
| A-8 | FR-2 | No wall-clock target is set for a 100 000-document *import job*. The sources state none. |
| A-9 | FR-3 | The OCR quality signal and its threshold are *configuration-as-data*; no threshold value is fixed. |
| A-10 | FR-11 | Exact-containment verification is built in this increment as a shared primitive even though the citation checker that consumes it belongs to the next increment. A deliberate scope inclusion. |
| A-11 | FR-13 | No latency target is set for exhaustive search at the design target. |
| A-12 | FR-19 | The estimator behind the priced risk figure is a projection from the ranking and any completed sampling. The sources state the sentence, not the method. See OQ-4. |
| A-13 | FR-21, §11 | A firm will eventually require lawful erasure of a *matter*; "never hard-delete" and lawful erasure are in tension, named and not resolved. |
| A-14 | FR-25 | A minimum meaningful length is enforced on *override* reasons and repeated identical reasons are surfaced as a quality signal. The source specifies "a required one-line reason" and no more. |
| A-15 | SM-10 | No date is attached to "installed at a real firm"; no engagement exists to attach one to. |
| A-16 | SM-C2 | No thresholds are set for *worklist* dismissal or *override* reason quality; these are trend metrics whose direction is the signal. |
| A-17 | SM-C4 | Partial triage over a partially-ingested *corpus* is desirable but is not specified as an FR; it interacts with the inventory guarantee in a way the sources do not address. |
| A-18 | §9 | No per-operation latency or throughput target is set anywhere in this document. |
| A-19 | §12 | The CNB March 2026 criteria are reported second-hand from a practitioner reading; the source PDF has not been obtained. |
| A-20 | §14 | A browser-reachable application served by the installed system is the client surface. The sources state a local-packaging direction but do not specify the surface for this increment. |
| A-21 | §15 | The *payload schema* is designed now to accommodate an external-authority reference on a *chunk*, though nothing in this increment writes one — because this is the one mistake that cannot be undone cheaply. |
| A-22 | §17 | No availability commitment is written, because the current capacity cannot underwrite one. This contradicts the stated ambition and is recorded as a gap rather than smoothed. |
