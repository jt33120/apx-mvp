---
title: "APX MVP — First Increment: Mass-Document Triage"
status: final
created: 2026-07-20
updated: 2026-07-21
---

# PRD: APX MVP — First Increment: Mass-Document Triage

*Working title — confirm.*

## 0. Document Purpose

This PRD is the build contract for the **first increment** of the APX rebuild: mass-document triage. Its readers are the CTO who owns the build, the AI agents that will execute it, and the downstream `bmad-architecture` and `bmad-create-epics-and-stories` workflows. It states **capabilities and their testable consequences**, never technology choices — every technology decision, every rejected alternative and every sequencing implication lives in the companion `addendum.md` in this folder.

Structure: vocabulary is anchored in §3 Glossary and used verbatim everywhere else in the document; features are grouped in §4 with functional requirements nested and numbered globally FR-1…FR-60 so they survive reorganisation; user journeys are numbered UJ-1…UJ-4 and referenced by ID from the FRs; success metrics are numbered SM-* and cross-reference the FRs they validate; open questions carry explicit `OQ-n` labels in §19; every inference is tagged `[ASSUMPTION: …]` inline and indexed in §20.

**FR numbers are allocation order, not reading order.** FR-37…FR-58 were added by the revision of 21 July 2026 (see *Revision log*, last section) and are grouped in §4.9…§4.13 rather than interleaved, so that every upstream reference to FR-1…FR-36 still resolves. FR-59 and FR-60 were added by the reconciliation pass of the same date; FR-59 opens the new §4.14 and FR-60 sits in §4.6, beside the requirement it completes. §4.4 Triage presupposes the ranking produced by §4.9; the two must be read together.

### 0.1 Build-readiness by section

Stated explicitly so downstream workflows do not have to guess which parts are a contract and which are still specification.

| Section | Readiness |
|---|---|
| §4.1 Corpus intake · §4.2 Index · §4.3 Retrieval · §4.7 Tenancy · §4.8 Internationalisation | **Contracted.** Buildable from this document. |
| §4.9 Relevance · §4.10 Reading and delivery · §4.11 Security and continuity · §4.12 Corpus and fitness functions · §4.13 Inventory arithmetic | **Contracted as capability; thin on mechanism.** New in this revision. Mechanism detail is in `addendum.md` §7…§11. |
| §4.4 Triage · §4.6 Home screen | **Contracted**, conditional on §4.9. |
| §4.14 Ease of use as a gate | **Contracted as capability; the artefact it gates against does not exist yet.** FR-59's phrasing checklist has to be written before the first release candidate. |
| **FR-19 and FR-23 specifically** | **Conditional on OQ-4, which is decided in approach and no longer blocking.** The sampling ritual, the draw and the *audit record* around them are buildable now. The *numbers* they emit ship only if the estimator passes its simulation; if it does not, the counts-only fallback at FR-19 is what ships. |

### 0.2 A dated correction, recorded rather than quietly fixed — 21 July 2026

Until this revision, the *confidence bound* was written throughout this document — in the Glossary, in UJ-2, in FR-23 and in the north-star metric SM-1 — as *"risk of having missed a relevant document below 1.5%"*. **That statement was false.** A random sample bounds the **prevalence** of relevant material in the *discarded set*. It does not bound the probability that nothing relevant was missed, and the two differ by orders of magnitude: to be 95% confident that *zero* relevant *pièces* remain among 1 400, having found none in the sample, one must review roughly 1 330 of them — 95% of the pile the product exists to let a lawyer not read.

The corrected sentence, used verbatim from this revision onward:

> *"200 pièces sampled at random from the 1 400 discarded; none relevant. With 95% confidence, at most 1.5% of the discarded set — about 21 pièces — is relevant."*

The estimator is **hypergeometric** (finite-population), never the binomial rule of three. At a sampling fraction of 200 in 1 400 the finite-population correction is a material gain, not a nicety.

This note is permanent. An unaudited number carried from a brainstorming session into a brief into a glossary into a north-star metric, without anyone checking the arithmetic, is precisely the failure mode this product exists to prevent — and it happened here, in this document, to its own north star. Removing the note would be the same mistake again.

### 0.3 Scope honesty

This revision absorbed three independent reviews in full rather than dropping findings to keep the increment tidy, and a second pass then reconciled the document against the four upstream inputs it was built from. The result is **60 functional requirements where there were 36**, for a team of one non-hands-on CTO plus AI agents.

**The increment as specified is larger than one person can comfortably build.** That is stated here, once, plainly, and repeated at each individually large requirement rather than left for the build to discover. No sequencing trick makes the list smaller; §6.3 proposes the cut line to use when capacity binds, and names what falls out first.

Upstream inputs, not duplicated here:
- `../briefs/brief-apx-mvp-2026-07-20/brief.md` — the finalised Product Brief.
- `../briefs/brief-apx-mvp-2026-07-20/addendum.md` — corpus strategy, the infrastructure contradiction and the rule that resolves it, capacity, personas, deferrals.
- `../../brainstorming/brainstorm-apx-mvp-rebuild-2026-07-20/brainstorm-intent.md` — the 14 non-negotiable mechanisms, the MoSCoW, the v1 salvage list and the v1 trap register. **The trap register (§9 of that document) is requirement material and is carried into this PRD as consequences, not as prose.**
- `docs/context/04-competitive-landscape.md` §7–§8 — the gap analysis and its implications.

**Those four inputs are current. Nothing else in the repository is.** The earlier project artefacts — the context pack under `docs/context/`, its `00-README.md` entry point and the `state.json` snapshot beneath it, which the project's own `CLAUDE.md` sends every agent to first — **record the prospect relationships as live, and are stale on exactly that point.** No engagement has been won and no client *corpus* exists (brief `addendum.md` §1). A downstream workflow that reads the context pack before this document starts from a fact that stopped being true on 20 July 2026, and it is the fact that changes the whole framing. This note is here rather than in an appendix because §17 forbids the *product* from letting documentation lie in load-bearing places, and this document's own upstream is a load-bearing place.

Two facts shape every requirement in this document and should be read before anything else. **No client engagement has been won.** The product is built for the use case, not for a named firm; no firm name appears anywhere in this document, and the persona names in §2.3 are illustrative composites drawn from the discovery record. **The team is one non-hands-on CTO plus AI agents.** Writing code is nearly free; owning it is not. Every requirement below is a permanent tax — tested, migrated blind against a corpus at the design target of 100 000 *pièces* at every installation, defensible in front of a judge, and supportable by telephone with no telemetry.

---

## 1. Vision

A lawyer facing an undifferentiated dump — a *matter* of 1 700 *pièces*, mostly `.msg`, or four years of a practice — has three bad options today: read everything, skim and hope, or pay an associate to skim. She skims. The honest baseline for anything built here is not perfect human review; it is what actually happens on a Friday evening under deadline pressure.

APX's first increment turns that dump into a **ranked, reversible, auditable working set, with a measured statement of what was set aside.** Nothing is ever deleted. The tool does not hand back a ranked list and leave the judgement to her — a list that refuses to decide pushes the work back onto the person paying to avoid it. The tool **draws the line** and says "in my view, everything above this". She can move it, and the cost of moving it is priced for her before she does. And when she is asked what happened to the rest, she has a sentence she can say to a client or to a judge, backed by a random sample and a stated *confidence bound*, not by a promise — a sentence that says exactly what the sample supports and not one word more (§0.2).

**A firm buys three promises, not three features.** This is the frame that ranks the work, and it is the reason the requirements below cluster where they do:

| The three offers (the features) | The three promises (what is actually bought) |
|---|---|
| Retrieval over the firm's own *corpus* | **Security and confidentiality** |
| Syllogisme drafting | **Ease of use for a non-technical collaborator** |
| *Veille* | **Volume — decades of activity, at once** |

A firm does not buy retrieval; it buys the right to put its *matters* into a machine without creating a liability. **v1 built all three offers and skipped all three promises** — and each skipped promise maps onto an empty directory: security onto an empty `rbac/`, ease of use onto no settings surface plus three unreconciled colour systems and broken i18n, volume onto eight empty `workers/` files. The promise, not the feature, is the thing that has to be gated. The one promise this document does *not* cover evenly is the second, and §7 says so in those words rather than leaving it to be noticed.

The organising principle of the whole rebuild is one sentence: **v1 built what can be shown; v2 builds what can be proven.** Every claim this product makes to a lawyer — nothing relevant was discarded, this document was read by a human, this matter cannot see that one, nothing left the firm — must rest on a deterministic, testable mechanism rather than on an intention written in a specification. In v1 those claims were sold in two client proposals and implemented in zero lines of code. That is the specific failure this document exists to prevent, and it is why every functional requirement below carries testable consequences and why several of them are written as the negation of a v1 defect.

The competitive reason this increment comes first, rather than drafting: drafting over a firm's own corpus is the most contested space in the European market, sold at €19/month by vendors already inside the practice-management software 7 500 French firms pay for. Triage for European firms under 50 lawyers is empty — *ordonnance 145 CPC* review goes to forensics consultancies at consulting rates and no French-language sovereign tool addresses it (`04-competitive-landscape.md` §7.1 item 4, §8.5). This is a **wedge, not a market**: demand is episodic and unproven, and the honest read is that it opens a door rather than fills a pipeline.

**Where this increment sits.** The product it belongs to is **one workspace with three verbs — *consult*, *add*, *draft* — with regulatory *veille* as a separate module.** That decision dissolved v1's three separate tools, and it is what stopped triage being a product: triage is not a fourth tool, it is the ***add*** **verb plus the review queue that verb produces.** This increment builds *add*, serves *consult* thinly through retrieval (§4.3) and the viewer (FR-44), and leaves *draft* for the next increment on the same spine. The navigational consequence is binding and is stated in §14. Building §4 as a standalone triage application is not a neutral simplification: it is the "three-tool navigation" the brainstorming session put in WON'T, arriving by default and discarded the moment drafting exists.

---

## 2. Target User

### 2.1 Jobs To Be Done

**The associate — the daily user.**
- *When a matter arrives as a folder of thousands of files and I have a deadline*, I want the machine to have read all of it before I open the first one, **so that** my evening is spent on the twenty documents that decide the case rather than on the nine hundred that do not.
- *When the machine has sorted my documents*, I want to correct it cell by cell without anything else moving, **so that** I never lose an edit and never have to redo work the tool undid. (Functional. Also emotional: *do not make me look stupid, do not lose my edits, do not make me check your work.*)
- *When I am asked in front of a partner why a document was not in the bundle*, I want a record that shows what the tool proposed, what I changed and why, **so that** the answer is a document rather than a memory.
- *When I open the tool at 21:00 on a Friday*, I want it to tell me what needs me, **so that** I do not have to work out what to do next before I can start.

**The partner — signs, does not use.**
- *When I am offered a matter whose review cost I cannot bid*, I want to be able to price it, **so that** I stop declining work or under-pricing it. Partially served in this increment: FR-39 emits a per-*matter* review-effort estimate **after** ingestion and ranking, which prices a matter already in the building. Bidding a matter **before** its documents arrive is an explicit non-goal (§5) — and since this is the revenue thesis (`addendum.md` §4; R-7), the honest reading is that the revenue story rests on the estimate being usable retrospectively until a later increment produces a pre-ingestion one.
- *When my insurer or my bâtonnier asks how AI is used in this firm*, I want a documented, mechanical answer, **so that** the conversation ends. **Not served in this increment, and named as a non-goal rather than left implied (§5).** FR-26 exports a per-*matter* audit record; that is evidence about one *matter*, not the firm-level deontological dossier this job asks for. The material such a dossier would be assembled from — versions, the three egress paths of §11, the structural properties of FR-56, §12's CNB analysis — exists inside the build. The dossier is a document APX writes rather than a feature the product ships, which is precisely why it goes missing, and nobody owns it: OQ-27.

**The billable-hour paradox sits underneath both of the partner's jobs.** On the hourly billing his firm uses, saving three hours *shrinks* the invoice: efficiency destroys revenue unless the firm moves to fixed fees or absorbs more volume. APX Advisory itself sells *forfait*; the firms it sells to bill by the hour. The consequence for this document is narrow and load-bearing — the only partner-facing value the product can honestly claim is **matters the firm could not previously bid**, never hours saved. That is why FR-39's per-*matter* review-effort estimate carries the revenue thesis rather than being a convenience, and why R-7 must be rated on that mechanism rather than on the symptom of unproven willingness to pay.

**The sceptic — a senior lawyer whose function is to distrust the machine on the firm's behalf.**
- *When the tool tells me it set aside 1 400 pièces*, I want to verify that claim myself by sampling, **so that** I am relying on a measurement rather than on a vendor's assurance.
- *When I have verified it*, I want a sentence with a number in it that I can repeat to a client or to a court, **so that** the firm's exposure is bounded and stated rather than unknown.

He is the gatekeeper, not the obstacle: "auditability is non-negotiable" is a direct quote from discovery, and *random-sampling auditability* is his requirement. Design for him and the other two follow.

**He verifies; he does not sort.** From the session record, in the user's own words: *"lawyers hate it, it is monotonous; the lawyer just keeps an eye on it — the whole point is to automate the tedious part."* Random sampling exists because it is how a lawyer keeps an eye on 1 400 *pièces* without reading them. **That constraint is in direct tension with FR-22**, which asks this man for one individual verdict per sampled *pièce* — 200 of them to bound a discarded set of 1 400 — which is monotonous reviewing reintroduced as the north-star ritual. Both things are true and the boundary between them is stated in §4.10: reading is the job **above** *the line*; below it, supervising is the job. The tension is not resolved here. It is sized at FR-22, measured after the fact by SM-C3, and carried as OQ-26 — rather than left for a senior lawyer to discover in his fourth hour.

### 2.2 Non-Users (first increment)

- **Firms shopping for a general productivity tool.** That market is served at €19–80 per user per month by vendors already inside the practice-management software. This product is for a firm with a **confidentiality problem it can name**: *ordonnance 145 CPC* review, criminal defence, sensitive M&A, Luxembourg private wealth.
- **Anyone looking for a legal research tool.** APX cannot compete on corpus depth and must never present itself as one. Retrieval in this increment is over the firm's own *corpus* only.
- **Large-scale litigation-services providers and their reviewers.** The e-discovery platforms serve them; this product does not.
- **The APX operator.** There is no admin **cockpit** in this increment; there is nothing installed to operate. The minimal per-*tenant* configuration and provisioning surface of FR-50 is in scope and is not the cockpit — §5 states the boundary once and authoritatively.
- **A drafting user.** Syllogisme drafting is the next increment (§5).
- `[ASSUMPTION: Italian-speaking users are non-users of this increment. Several Italian firms are in discussion with the APX partners, which moves i18n scope toward FR/EN/IT; this PRD holds FR/EN and treats Italian as OQ-3 rather than as a requirement.]`

### 2.3 Key User Journeys

`[ASSUMPTION: persona names are illustrative composites from the discovery record. No firm and no client is named anywhere in this document.]`

---

**UJ-1. Éléonore starts a four-year matter on a Friday evening and lets it run.** *(The user's own narration. Preserved.)*

**Persona + context.** Éléonore, associate, non-technical, works under deadline at inconvenient hours. It is Friday evening. The hearing is Monday. A *commissaire de justice* operation has left her a drive holding four years of a *matter* — roughly 1 700 *pièces*, mostly `.msg` with attachments, some scanned, some she already knows are corrupt.

**Entry state.** Authenticated, on the worklist home screen of her *tenant*, which currently shows two lines from another *matter*. She has not configured anything and has not spoken to anyone's IT department.

**Path.**
1. She plugs in the USB key and selects the folder holding the four years. One gesture. No connector, no API, no import wizard asking her to map fields. She names the *matter* and confirms the *RBAC scope* it belongs to. A fourth field is offered and she skips it: **the *case theory*** — two or three sentences saying what she is trying to establish, against whom, over what period. It is optional, she can write it later, and skipping it does not block anything (FR-1, FR-37).
2. The import job starts and collapses to a small non-blocking indicator, bottom-right, Google-Drive style. It shows a running count against a denominator. She does not wait for it.
3. She keeps working — she opens the other *matter*, reads two documents, answers an email. The indicator keeps counting. She closes her laptop lid; when she opens it again the import has resumed from where it stopped rather than starting over.
4. The indicator turns to a completed state. She clicks it.

**Climax.** She does not get a progress log. She gets two things. First, **the tasks that need a human**, in her language, as a worklist: *"14 pièces illisibles — les traiter"*, *"3 pièces protégées par mot de passe"*, *"1 dossier compressé n'a pas pu être ouvert"*. Second, **a completion summary** whose first line is the denominator: submitted, indexed, and in the *failure register*, listed one by one. Underneath, the *retained set* above **the line**, each *pièce* with a confidence and a one-line justification, and the *discarded set* below it with its count. Nothing has been deleted. Nothing has been filed into a folder she cannot undo.

**Resolution.** She opens the first *pièce* in the viewer (FR-44), reads the 180 above **the line** over the weekend instead of 1 700, marks them read as she goes (FR-45), and on Monday exports the retained set as the basis of her *bordereau* (FR-46). She can say what she did with the rest. The next thing she does is UJ-4, or she hands the *matter* to Emmanuel for UJ-2.

**Edge case.** She has already imported part of this folder last month, from a different drive, under a different top-level folder name. The second import does **not** overwrite the first and does **not** produce 1 700 duplicates: files already ingested for this *matter* are recognised as already ingested, counted as such in the completion summary under their own heading, and the *corpus* count is unchanged for them. `[ASSUMPTION: she is told how many were recognised as already present, rather than silently skipped — silence here reads as data loss to a user who has been told nothing is ever deleted.]`

**Second edge case — the dump arrived as four `.zip` files.** Which is the normal delivery shape for a *commissaire de justice* operation. The four archives are expanded and their members become *pièces* with provenance through the container (FR-57); the *denominator* counts *pièces*, not the four files she selected. An archive that cannot be opened produces **one** *failure register* entry marked as standing for an **unknown number** of *pièces*, and every absence claim over this *matter* is qualified by that unknown rather than by a count of one. `[ASSUMPTION: containers are expanded rather than registered as single failures. The sources describe a compressed folder only as a failure; a litigation dump delivered as archives makes expansion the difference between a denominator that is right and one that is wrong by two orders of magnitude.]`

---

**UJ-2. `[ASSUMPTION]` Emmanuel audits the discarded set before he lets the bundle out of the building.**

**Persona + context.** Emmanuel, senior lawyer, the firm's sceptic. His function is to distrust the machine on the firm's behalf. He does not care what the tool retained; he cares what it threw away.

**Entry state.** Authenticated, opens the *matter* Éléonore triaged, with an *RBAC scope* that includes it. The *discarded set* holds 1 400 *pièces*.

**Path.**
1. He opens the *discarded set* and asks for a random draw. He sets the sample size, or accepts the size the tool proposes for a stated target *confidence bound*.
2. The tool draws — verifiably at random, with the draw itself recorded — and presents the sampled *pièces* one at a time, each with the *truth status* of the evidence behind its position and the one-line justification the tool gave for discarding it.
3. He marks each one relevant or not relevant. He finds none relevant. On the two he hesitates over, he marks relevant and the tool tells him immediately what that does to the number.
4. He completes the sample.

**Climax.** The tool gives him a sentence: *"200 pièces sampled at random from the 1 400 discarded; none relevant. With 95% confidence, at most 1.5% of the discarded set — about 21 pièces — is relevant."* Not a dashboard, not a percentage in a coloured badge — a sentence, in his language, that he can put in a note to the client or say to a judge. It states a **prevalence** and it names its confidence level; it does not claim that nothing was missed, because a sample cannot support that claim (§0.2). Every number in it is reconstructible from the *audit record* alone, and the sentence carries the *RBAC scope* it was computed under, because his walls are not the *matter*'s walls.

He notices, and is meant to notice, that the honest sentence is less comforting than the one the product used to print. Whether the firm still buys the product on the true sentence is a commercial question `[ASSUMPTION: the true sentence is still worth buying — no client has ever been shown either version. See OQ-20.]`

**Resolution.** The sampling run is now part of the *matter*'s *audit record*: who sampled, when, which draw, which *ranking version*, which position of **the line**, which *case theory* the ranking was relative to, and what each verdict was. If he had found one relevant *pièce*, the sentence would have said so and the bound would have widened accordingly — and the tool would have offered to move **the line** or to pin that *pièce* above it (FR-43), rather than quietly re-ranking behind him.

**Edge case.** He starts a sampling run and abandons it after 40 of 200. The tool does not present a partial sample as a result and does not produce a *confidence bound* from it. The incomplete run appears on the worklist as an actionable line — *"Audit échantillon: 40/200 — reprendre"* — and is retained in the *audit record* as incomplete.

---

**UJ-3. `[ASSUMPTION]` Marc corrects a misclassification and watches the change log record it.**

**Persona + context.** Marc, junior associate. He knows one *pièce* the tool put in the *discarded set* is the whole case, because he was on the call it summarises.

**Entry state.** Authenticated, on the triage table for the *matter*, which he can edit cell by cell.

**Path.**
1. He finds the *pièce*, opens the cell holding its label, and changes it.
2. Nothing else on the screen changes. No regeneration runs. The other 1 699 rows keep exactly the values they had, including any correction he made ten minutes ago.
3. A **change log** entry appears immediately next to the row: the previous value, the new value, who, when.
4. He does the same to the confidence on a second row, and to the date on a third, extracted wrongly from a scan.
5. Changing the label did **not** move the *pièce* across **the line** — the label and the rank are different things. So he **pins** it above the line (FR-43): one *pièce* crosses, nothing else moves, the *retained set* grows by exactly one, and the pin is recorded as an *override* with his one-line reason ("j'étais à l'appel que cette pièce résume"). He does not have to drag **the line** past the 400 *pièces* above it to keep the one that decides the case.

**Climax.** He makes twelve corrections in a row and none of them costs him another. The value he is getting is negative and he would only notice its absence: the tool did not undo his work. This is the architectural invariant of the system, expressed as a UI property — *cell-by-cell editing with no destructive regeneration* — and it came from a practising associate, not from a design preference.

**Resolution.** His corrections are in the *audit record* as modifications, distinguished from values accepted as-is — and "accepted as-is" is reachable only through an explicit *validation act* (FR-45), never by default and never by the passage of time. If his edit contradicts something the tool asserted with high confidence, he is asked for a one-line reason and the entry is marked as an *override*. If Emmanuel later runs UJ-2 over the *discarded set*, Marc's corrections and his pin are already reflected in it, and any *confidence bound* computed before them is marked stale (FR-58).

**Edge case.** Two people edit the same cell of the same *matter*. The second edit does not silently win: the *change log* shows both, attributed, in order, and the current value is unambiguous. `[ASSUMPTION: concurrent editing within one matter is in scope; the source documents do not address it, but a shared matter with a partner and two associates makes it near-certain.]`

---

**UJ-4. `[ASSUMPTION]` Éléonore moves the line and is shown the price before she pays it.**

**Persona + context.** Éléonore again, Sunday, having read the 180 *pièces* above **the line**. She is uneasy — the case turns on a period the retained material barely covers.

**Entry state.** On the triage view for the *matter*, **the line** where the tool put it.

**Path.**
1. She drags **the line** downward. Before she releases it, the tool prices the move: *"400 more pièces to read; the estimated share of the discarded set that is relevant falls from about 3% to about 0.4%."* The figure is a **projection from the ranking**, not a sampling bound, and it is labelled as such on the screen — it is a model's estimate of prevalence, calibrated against the *gold set* (FR-19), and it can be wrong in a way a completed sample cannot.
2. She sees the same figure for two other candidate positions as she drags past them, so she is choosing between priced options rather than guessing.
3. She releases. The *retained set* grows; the *discarded set* shrinks; **nothing is deleted and nothing is re-classified** — the piles are a view over one ranked order, and only the position of **the line** changed.
4. The new position is recorded as an auditable parameter of this *matter*, with who moved it and when.

**Climax.** She has converted a feeling ("I am not comfortable") into a decision with a number attached and a record behind it. That is the difference between a tool that commits and a tool that hedges.

**Resolution.** Any *confidence bound* already computed for this *matter* is marked as computed against the previous position of **the line** and is not silently reused. The worklist gains a line offering to re-sample.

**Edge case.** She drags **the line** to the very bottom, retaining everything. The tool does not object, does not warn, and does not treat this as an error — but the priced statement now reads that the *discarded set* is empty and no *confidence bound* is applicable, and it says so rather than reporting a prevalence of 0%. Note that this position satisfies every quality metric in §7 while delivering no triage at all; SM-11 exists to make that visible rather than to forbid it.

**Second edge case — the top of the range.** The system places **the line** above the first *pièce*, so the *retained set* is empty. It may do this only where FR-17's refusal condition is not met but no *pièce* clears the retention threshold, it must say so in words ("in my view, nothing here needs reading — check this"), and it produces a *worklist* line rather than a silent empty table. `[ASSUMPTION: the empty-retained-set case is handled symmetrically with the empty-discarded-set case. The sources handle only the bottom of the range.]`

---

## 3. Glossary

*Downstream workflows and readers use these terms exactly. FRs, UJs and SMs use them verbatim. A synonym anywhere in this document is a discipline violation.*

**Three words are banned as substitutes for *pièce*:** *document*, *item*, *file*. *File* means a filesystem entry as submitted and nothing else; *document* and *item* appear in this document only inside quotations from external sources. The design target is stated in *pièces* (see *Design target*).

- **Tenant** — one installation's isolated world: one firm. All data, configuration and identities belong to exactly one tenant. Tenant isolation is a day-one invariant, not a later feature. One codebase, N tenants; a per-tenant code fork is a defect, not a delivery.
- **Matter** — a *dossier*: the unit of legal work, and the unit of confidentiality. Every *pièce* and every *chunk* belongs to exactly one matter. Matters are walled off from each other by professional-conduct rules (Chinese walls); a matter belongs to exactly one tenant.
- **RBAC scope** — the access predicate attached to a matter and to every *chunk* derived from it, and held against a user. Determines whether a user may see a *pièce* at all. Applied as a query **pre-filter**, never as a post-filter.
- **Pièce** — one source document as the lawyer understands it: an email, an attachment, a scan, a contract, a spreadsheet. The unit she reads, ranks, corrects and cites. One file usually yields one pièce; an email with three attachments yields four, each with its own identity and provenance to its parent. Kept in French: it is the term of art, and *bordereau de pièces* is the list of them.
- **Corpus** — all *pièces* successfully indexed for a given *tenant* **and yielding at least one retrievable *chunk***, addressable by retrieval subject to *RBAC scope*. A pièce in the *failure register* is not in the corpus, and a pièce whose extraction succeeded but produced no text is in the *failure register* under `extracted-empty`, not silently in the corpus. "The whole indexed corpus" is a precise, countable set — that precision is what makes an absence claim honest.
- **Index** — the storage and retrieval machinery over the *corpus*: the vector store, the deterministic text store and their identifiers. The *corpus* is the set of *pièces*; the index is the thing that holds and searches them. They are not synonyms and an index rebuild does not change the *corpus*.
- **Chunk** — the indexed unit derived from a *pièce*: a passage carrying its own *payload schema* record, including provenance back to its exact position in the source pièce. Retrieval returns chunks; the interface presents pièces.
- **Payload schema** — the record attached to every *chunk*: *tenant*, *RBAC scope*, *matter*, *custodian*, provenance (source pièce identity, source position, extraction method and extractor version), and dates. **The only irreversible decision in the system.** Everything else sits behind an adapter and is replaceable; this is not.
- **Custodian** — the person or mailbox from whose holdings a *pièce* was submitted, as declared at import or derived from provenance. In *ordonnance 145 CPC* and adjacent work, *who held this document* is frequently the fact in issue, so custodian is a mandatory, queryable *payload schema* field and survives deduplication (FR-4, FR-8).
- **Container** — a *pièce*-bearing file that holds other files: an archive, a PDF portfolio, a mailbox export, an email carrying attachments, a `.msg` nested inside another. Containers are expanded; the members become *pièces* with provenance through the container (FR-57).
- **Ingestion** — the single code path by which any *pièce* enters the system, from a folder selected by a user or from any other configured source. There is exactly one such path. There is no fixture layer, no demo path and no fallback path.
- **Import job** — one user-initiated run of *ingestion* over a selected folder. Resumable, idempotent, non-blocking, and the thing that produces the *failure register* entries and the completion summary.
- **Failure register** — the enumerated list of *pièces* submitted but not in the *corpus*, each with its filename, its path as submitted, an error class, the *matter* it was submitted for, its *custodian* where known, a **cardinality** (one, or *unknown* where the entry is an unopened *container*), a resolution state, and a retry action. Entries are **resolved by state change, never removed** — the *inventory guarantee* counts *open* entries, and a resolved entry stays in the register so that §13's question 1 remains answerable. It is the mechanism behind the guarantee: *submitted = in corpus + open failure register entries*, exactly, always, counted in *pièces* (FR-57). The decisive pièce hides statistically in the failure register; a corpus claim made without it is dishonest, and a corpus claim made with a register that understates itself is equally dishonest.
- **Denominator** — the statement of the inventory guarantee **for a *matter* or a *tenant***, counted in *pièces*: *"97 200 / 100 000 indexed · 2 800 not indexed"*. This is the quantity SM-3's invariant is asserted over. Never rounded, never absent from a surface that claims completeness.
- **Scoped denominator** — the same statement **computed within one user's *RBAC scope***. This is the quantity **displayed** to a user (FR-28) and carried by an *exhaustive* result set (FR-13), because an unscoped count leaks the existence of material the user may not see. Two users on one *matter* legitimately see different scoped denominators, and neither is the *matter*'s denominator. Any surface showing a scoped denominator says so. *(These are two quantities and therefore two terms; the previous single term carried both meanings and could not.)*
- **Design target** — **100 000 *pièces* indexed per *tenant***, and every scale-sensitive consequence in §4 is asserted at that figure. Stated in *pièces*, not in files: after container expansion (FR-57) the file count and the *pièce* count differ by a multiple, not by a rounding.
- **Triage** — reversible ranking (FR-39) **and** labelling (FR-40) of the *pièces* of a *matter*. Never deletion, never destructive classification.
- **Case theory** — the lawyer's optional statement, in free text in her own language, of what she is trying to establish: the question, the parties, the period, what would count as relevant. It is the input relevance is *relative to*. Optional at import, writable and rewritable at any time, versioned, carried in the *audit record*, and a re-rank is triggered when it changes (FR-37). Where no case theory exists, relevance is judged from intrinsic signals alone and every artefact derived from that ranking says so.
- **Relevance judgement** — the per-*pièce* assessment of relation to the *case theory* (or, absent one, to intrinsic signals), produced by the cascade of FR-38. It yields a score, a band and the evidence the justification is derived from. Relevance is a **relation to a question**, never a property of a document.
- **Ranking version** — the complete, immutable identity of the machinery that produced one ranked order: the *case theory* version, the model identity, the prompt version, the temperature and any other sampling parameter, the cascade configuration, the embedder identity, the chunking configuration, and the schema version. Re-running a fixed ranking version over a fixed *corpus* reproduces the same order, *pièce* for *pièce* (FR-39). Every *confidence bound*, every position of **the line** and every classification binds to one.
- **The line** — the position in the single ranked order at which the tool commits: *"in my view, everything above this."* Stored as an **ordinal cut over a named *ranking version*, together with the identity of the last retained *pièce*** — never as a bare score and never as a bare integer, so that its referent survives the population changing underneath it. An auditable per-*matter* parameter with a value, an author and a timestamp. Movable by a user, priced before it moves, and overridable for a single *pièce* by a *pin*.
- **Pin** — a per-*pièce*, per-*matter* override of **the line**: this *pièce* is retained (or discarded) regardless of its rank. Requires a reason, is recorded as an *override*, survives re-ranking, and is the only way to move one *pièce* across **the line** without moving the line itself (FR-43).
- **Retained set** — the *pièces* ranked above **the line**, plus those pinned in, minus those pinned out. A view over the ranked order, not a container.
- **Discarded set** — the *pièces* ranked below **the line**, adjusted by *pins*. A view, not a container: nothing in it is deleted, hidden from search, or excluded from the *corpus*. "Discarded" describes the tool's recommendation, not the data's fate.
- **Sampling run** — one attempt to bound the *discarded set*: a target, a draw over a frozen population, an ordered list of *pièces* presented for verdict, the verdicts recorded, and either a completed *confidence bound* or an incomplete state. Identified, versioned, bound to a *ranking version*, a position of **the line** and an *RBAC scope*, and recorded in the *audit record* whether it completes or not.
- **Confidence bound** — the statistical statement about the *discarded set* produced by a **completed** *sampling run*, expressed as a sentence a lawyer can say to a client or a judge: *"200 pièces sampled at random from the 1 400 discarded; none relevant. With 95% confidence, at most 1.5% of the discarded set — about 21 pièces — is relevant."* It bounds **prevalence** — the share of the discarded set that is relevant — using a **hypergeometric** (finite-population) estimator. **It never states, and must never be worded as, the probability that nothing relevant was missed**; that quantity is not estimable from a sample of this size (§0.2). It states its confidence level explicitly, names its *RBAC scope*, and is bound to one *ranking version*, one position of **the line** and one *case theory* version.
- **Validation act** — the explicit gesture by which a human asserts *"I read this pièce and I accept the tool's assessment of it"*. It is the only thing that produces an "accepted as-is" entry in the *audit record*; elapsed time, scrolling past, opening and closing, and default state never do. Per-*pièce*, recorded with actor, timestamp, *ranking version* and whether the *pièce* was opened in the viewer first (FR-45).
- **Retained extracts** — the specific *chunks*, named by identifier and resolvable to a position in the source *pièce*, that the *relevance judgement* used and that the one-line justification is derived from. They are the checkable part of a justification whose prose is not checkable (R-11), and they are what the *audit drawer* shows.
- **Deterministic expression** — the query language of exhaustive search: a literal, boolean or proximity expression over text, with **explicitly specified** normalisation semantics for French (FR-13). Not a similarity score, not a model output, and not a natural-language question.
- **Truth status** — the declared epistemic standing of a result set. Exactly two values in this increment: **suggestive** (semantic, ranked, top-k — can support a finding, can never prove an absence) and **exhaustive** (deterministic, complete match set over the whole indexed *corpus* within one *RBAC scope*, qualified by the *failure register* and by the OCR-derived share of the searched set — the only thing that can support an absence claim, and only a qualified one). Declared on the result set itself, in the interface and in any export.
- **Audit record** — the per-*matter* append-only record of human and machine decisions: who validated, when, which version of what, which values were modified versus accepted as-is, which *overrides* were made and with what reason, where **the line** stood, and every sampling run with its verdicts. Exportable.
- **Override** — a user decision that contradicts a machine assertion or a system guard. Requires a mandatory one-line reason; recorded in the *audit record* as an override, distinct from an ordinary modification.
- **Change log** — the live, per-cell before→after trail shown in the triage table as edits are made. The user-facing surface of part of the *audit record*.
- **Audit drawer** — the per-*pièce* panel showing why the tool placed it where it did: its confidence, the *retained extracts* behind that confidence, the proposed *audit record* entry, and reversible actions. Exportable.
- **Worklist** — the queue of things that need a human, occupying the **top zone** of the home screen; each line is an action in the lawyer's language. **Not a log.** A line that is not actionable does not belong on it: it belongs in the *matters* zone (FR-60) or nowhere. The worklist is the top zone, not the whole screen.
- **Configuration-as-data** — per-*tenant* behaviour expressed as data rows, never as a code branch: the triage taxonomy, *RBAC scopes*, the language model provider, the configured sources, the labels on **the line**. A bespoke request that becomes a code fork is a defect.
- **Content-free projection** — a single reusable primitive that emits information *about* a *tenant*'s data without emitting any of it. Its content-freedom is a **structural property**, enforced by test over every registered projector, never promised in a document. What it may emit is a **registry, not a closed list** (FR-31): the client-pushed diagnostic export is its consumer in this increment; the next increment's on-premises style extractor is the second, and the deferred admin *cockpit* would be the third.
- **Gold set** — a corpus with human relevance judgments against which recall is measured, executed in CI. v1 had one and never once ran it. Its acquisition, its mapping onto this product's notion of relevance, and its execution are a requirement (FR-54), not a strategy paragraph.
- **Structural property** — a property of the *source code or the build*, not of a run: "no module imports X", "no string literal matches this pattern", "this interface has exactly one implementation". Enforced by a static check in CI (grep, lint, import-graph or architecture rule), because a runtime test cannot decide a universal negative over program behaviour. Where this document previously wrote *"asserted by test"* against a universal negative, it now writes *"enforced as a structural property (FR-56)"*.

---

## 4. Features

*Each subsection is a coherent feature: behaviour first, FRs nested, testable consequences under each FR. FRs are numbered globally. Where an FR exists to prevent a specific v1 defect, that defect is named — the v1 trap register is requirement material.*

### 4.1 Corpus intake

**Description.** Onboarding is a folder. The lawyer plugs in a USB key or points at a directory on the network, names the *matter*, confirms the *RBAC scope*, and the system does the rest — no connector, no API, no IT project, no meeting with anyone's systems people. The *import job* runs non-blocking so she keeps working, resumes rather than restarts, and finishes by handing back the things that need a human plus a summary of what happened. Realizes UJ-1.

This UX specifies the backend rather than decorating it: non-blocking, resumable, idempotent ingestion at the *design target* is what makes the gesture possible. In v1 this layer was eight empty files.

**The best adoption idea in the product and its widest attack surface are the same event.** One hundred thousand confidential *pièces* entering in a single gesture, at 19:10, with no IT department in the room and a non-technical user holding the drive — whatever guards the folder-import path is what separates "clients in Italy, France and the USA" from "leak at a Paris firm". So FR-1's *RBAC scope* ceiling in both directions, its loud refusal of a null scope, and its traversal boundary are not fastidiousness at the margin of a convenience feature. They are the guard on the widest surface the product has, and they are exactly the kind of consequence that reads as an edge case to whoever is cutting scope. Security in this product does not begin downstream of intake (§4.11).

**Functional Requirements:**

#### FR-1: Folder selection as the whole onboarding gesture

An authenticated user can start an *import job* by selecting a filesystem folder (including a mounted removable drive), assigning it to a new or existing *matter* and confirming its *RBAC scope*. Realizes UJ-1.

**Consequences (testable):**
- Starting an *import job* requires exactly three **mandatory** user inputs: the folder, the *matter*, the *RBAC scope*. Exactly one **optional** input is offered on the same screen — the *case theory* (FR-37) — which can be skipped, and skipping it blocks nothing. **No further mandatory configuration screen exists on this path.** *(Previously this consequence admitted no fourth field at all, which foreclosed the only place a user could state what she wanted ranked toward, and left the ranking with no input. The optional case theory resolves that without reopening the one-gesture onboarding.)*
- Subfolders are traversed to arbitrary depth; the folder structure as submitted is preserved in each *pièce*'s provenance and is reconstructible from the *payload schema* record alone.
- Traversal is confined to the selected subtree. Symbolic links and junctions are resolved only where the target is inside that subtree; a link pointing outside it is recorded in the *failure register* with class `traversal-out-of-scope` and is not ingested. Traversal cycles are detected and terminate the walk for that branch with an entry, not with a hang. `[ASSUMPTION: a link into another matter's folder must not silently ingest that material under this matter's RBAC scope — the pre-filter cannot detect data that was mislabelled at the boundary, so the boundary is where it must be caught.]`
- An *import job* cannot be started without a *matter* and an *RBAC scope*. A *pièce* with a null or empty *RBAC scope* is never written to the *corpus*; the attempt fails the *import job* loudly rather than defaulting to permissive. *(v1: `rbac/` was empty — a legal obligation sitting at zero lines.)*
- The *RBAC scope* selectable at import is constrained to scopes the importing user holds or is authorised to grant (FR-49). A user cannot assign a *matter* to a scope she does not hold, in either direction — narrower (material becomes invisible to her supervisor) or broader (material becomes readable by a group she chose). Asserted by test over both directions.
- The *custodian* is captured at import — a single value for the selected folder, or per top-level subfolder — and is a mandatory field. Where it is genuinely unknown the value is the explicit `custodian-undeclared`, never blank.
- Selecting a folder containing zero readable files produces a completed *import job* with a *denominator* of 0/0 and an explanatory *worklist* line, not an error dialog and not a silent no-op.

#### FR-2: Non-blocking, resumable *import job*

An *import job* runs in the background and survives interruption without losing or duplicating work. Realizes UJ-1.

**Consequences (testable):**
- After starting an *import job*, every other function of the application remains usable; no screen is blocked and no modal is shown.
- Progress is visible as a persistent, collapsed, non-blocking indicator showing processed count against the submitted count.
- Killing the worker process mid-job and restarting it resumes from the last committed unit of work. No *pièce* already indexed is re-indexed as a new *pièce*; no *pièce* not yet processed is skipped. Asserted by test with an induced kill at ≥3 different points of a run.
- Closing the client application does not stop the *import job*. Reopening it shows the job's true current state, not a stale snapshot.
- An *import job* at the *design target* completes without unbounded memory growth and without requiring the user to keep a window open. Memory is bounded **per unit of work** as well as per job: no single *pièce*, however large, may be required to fit in memory whole, and a unit that exceeds the configured resource bound is entered in the *failure register* with class `resource-exhausted` rather than killing the worker.
- **A unit of work that kills the worker is quarantined, not retried forever.** After a configured number of failed attempts the unit enters the *failure register* with its error class and the job proceeds. Asserted by test with a deliberately poisonous unit: the job completes, the completion summary fires, and the poison *pièce* is one register entry. *(Without this, the resume rule of the previous bullet resumes onto the unit that killed it, and the job never completes — so UJ-1 never reaches its climax.)*
- The submitted set is **frozen at enumeration**, and the enumeration itself is recorded. A file that disappears, is modified, or becomes unreadable between enumeration and processing produces a *failure register* entry with class `source-unavailable` or `source-modified` — never `corrupt-file`, which would tell the lawyer a readable document was damaged. Files added to the folder after enumeration are not silently included; they require a second *import job*.
- No wall-clock target is set for an import at the *design target*, and none is invented here. **A ceiling is derived rather than invented:** UJ-1 requires that the *retained set* be readable over a weekend, so first *ranking version* available to the user must be reachable within that window or UJ-1 is invalid. `[ASSUMPTION: no wall-clock target for a 100 000-pièce import is set in this PRD — the source documents state none — but the weekend ceiling is derived from UJ-1 rather than invented, and a build that cannot meet it has invalidated a user journey, not missed a target. See OQ-6.]`

#### FR-3: Multi-format extraction

*Ingestion* extracts text and structure from the formats a litigation *matter* actually contains. Realizes UJ-1.

**Consequences (testable):**
- The following are extracted: `.msg` (including headers, reply chains and embedded attachments), PDF (born-digital), PDF (scanned, via OCR), `.docx`, `.xlsx`, and standalone images (via OCR). **This is the largest single engineering surface in the increment** — `.msg` alone means compound-file parsing, RTF-compressed bodies, TNEF, nested messages, charset recovery and reply-chain reconstruction, and OCR must run inside the *tenant* boundary (§15), which forbids every hosted OCR service. It is months of unglamorous work and it is stated as such here rather than discovered.
- Container expansion — archives, PDF portfolios, mailbox exports, nested `.msg` — is specified in FR-57, including recursion limits and the arithmetic of the *denominator*.
- An email with N attachments yields N+1 *pièces*: the message itself and each attachment, each with its own stable identifier, each carrying provenance to its parent message and inheriting the parent's *custodian*.
- Every extracted *pièce* records the extraction method **and the extractor version** (OCR engine and version, parser version) in its *payload schema* record, so a downstream reader can tell a transcription from a text layer and a re-extraction under a new engine is detectable rather than merely suspected.
- A format not on the supported list does not silently vanish: the *pièce* is entered in the *failure register* with error class `unsupported-format` and is counted in the *denominator*.
- An extraction that succeeds and yields no text — a blank scan, an empty `.docx`, an image with no recognisable characters — is entered in the *failure register* with class `extracted-empty`. It is **not** counted as in the *corpus*, because it would otherwise be a *pièce* that every exhaustive absence claim asserts was searched and that retrieval cannot reach. Asserted by test.
- OCR output below a configured quality signal is indexed **and** flagged, not discarded; the flag is visible on the *pièce* and generates a *worklist* line. A **corpus-wide OCR figure** is computed and maintained per *matter* and per *tenant* — how many *pièces* in the *corpus* were derived by OCR, and how many of those are below the quality signal — because FR-13's absence claims cannot be honest without it. `[ASSUMPTION: the quality signal and its threshold are configuration, not code — see FR-30. No threshold value is fixed here.]`

#### FR-4: Idempotent *ingestion* with stable identifiers

Re-submitting material that is already in the *corpus* neither duplicates it nor destroys it. *(v1 defect: ingest point ids were reused from 1, so a second upload overwrote the first.)*

**Consequences (testable):**
- Every *pièce* receives an identifier that is a deterministic function of **(content, *matter*)** — provenance path is **not** part of identity. Every *chunk*'s identifier is a deterministic function of its *pièce* identifier, its position and the chunking configuration. Identifiers are stable across runs, across processes and across installations, and are never allocated from a counter that restarts. *(The previous wording made the identifier a function of "content and provenance" while also requiring two copies at different paths to collapse into one pièce. Those cannot both hold; path is now explicitly excluded and provenance is recorded as an attribute, not as identity.)*
- Importing the same folder twice into the same *matter* leaves the *corpus* count unchanged, leaves every previously indexed *pièce* readable and unmodified, and reports the recognised-already-present count as its own line in the completion summary. Asserted by test.
- Importing folder A then folder B, where B contains a copy of a file in A, produces one *pièce* with two recorded provenance paths — not two *pièces*, and not one *pièce* whose original path has been overwritten. **Every *custodian* associated with either copy is retained on the *pièce* as a queryable set.** Deduplication may never collapse two custodians into one; in *ordonnance 145 CPC* work, who held a document is frequently the fact in issue. Asserted by test.
- The same content at the same path with **changed** content produces a new *pièce* carrying a `supersedes` relation to the previous one. Both remain in the *corpus*, both are readable, and the *bordereau* export (FR-46) marks the superseded one as such — so two versions of one document do not rank independently and are not counted as two independent draws by a *sampling run*. `[ASSUMPTION: a supersession relation between pièces is required. The sources address duplication and not versioning; without it, a re-imported edited file silently doubles.]`
- **Near-duplicates are not exact duplicates and are not handled by this FR.** Quoted reply chains, sender-and-recipient copies of one message, and a message forwarded as an attachment are never byte-identical, so content hashing does not collapse them. Their treatment is a *ranking* concern (FR-38) and a *sampling* concern (OQ-4), and it is named here so that no reader concludes deduplication has solved it.
- Importing the same file into two different *matters* produces two *pièces*, because *matter* is part of identity and confidentiality follows the *matter*. Cross-*matter* deduplication is explicitly not performed.
- Under an induced write conflict (the same *pièce* processed concurrently by two workers) the *corpus* contains exactly one copy and the *import job* does not fail.

#### FR-5: The *failure register*

Every *pièce* that fails to enter the *corpus* is enumerated, attributed and actionable. Realizes UJ-1.

**Consequences (testable):**
- A *pièce* that fails at any stage of *ingestion* appears in the *failure register* with: filename, submitted path, *matter*, *custodian*, error class, cardinality (one, or *unknown*), resolution state, timestamp, and a retry action.
- Error classes are enumerated and stable, at minimum: `unreadable-scan`, `corrupt-file`, `password-protected`, `unsupported-format`, `extraction-error`, `extracted-empty`, `container-unopenable`, `resource-exhausted`, `source-unavailable`, `source-modified`, `traversal-out-of-scope`. An unclassified failure is recorded with class `unknown` and its redacted diagnostic — it is never dropped.
- **Entries are resolved by state change, never by removal.** Retrying re-runs *ingestion* for that *pièce* only; on success the entry moves to state `resolved` and remains in the register with its history, and the *pièce* enters the *corpus*. The *inventory guarantee* (FR-6) counts **open** entries only. *(This states once what FR-5, FR-21 and §9 previously asserted in three mutually incompatible ways: "removes it from the register", "no hard deletion of a failure register entry", and "the failure register is append-only".)*
- Where an entry is required to be actionable, the action must exist. A `password-protected` entry offers a credential-supply action; supplying the password re-runs *ingestion* for that *pièce*. An entry whose only exit is an *override* is a defect of this FR, not of FR-27, because it forces a lawyer to record in a permanent audit record that she deliberately excluded a document she could in fact have opened.
- A **bulk retry** exists over a filtered set of entries — by error class, by *matter*, by *custodian* — and produces one *audit record* entry naming the set, not one per *pièce*. Without it, 2 800 entries are 2 800 clicks and the *worklist* becomes the log FR-27 forbids.
- The *failure register* is exportable as a list, one *pièce* per line, without leaving the application, **within the exporting user's *RBAC scope***, and producing the export is recorded in the *audit record*. Entries whose *matter* could not be determined — and which therefore have no scope — are visible only to a user holding the *tenant*-wide administrative grant of FR-49. *(Filenames and submitted paths are frequently the privileged fact; this register is the one surface that cannot inherit the FR-8 stamped scope, because a pièce that never entered the corpus never had a chunk written.)*
- No entry can leave the `open` state other than by successful *ingestion* or by an explicit user action recorded in the *audit record* with a reason (an *override* per FR-25).

#### FR-6: The inventory guarantee and the permanent *denominator*

The system can always state, exactly, what it was given and what it did with it. Realizes UJ-1, UJ-2.

**Consequences (testable):**
- For every *matter* and for every *tenant*, **counted in *pièces* after container expansion**: `submitted = in corpus + open failure register entries`, at all times, with no third bucket. The unit and the freezing point are defined in FR-57. Asserted by an invariant test that runs after every *import job* and after every retry, at the *design target*.
- The *denominator* is displayed persistently — on the *worklist* home screen and on the *matter* — in the form *"97 200 / 100 000 indexed · 2 800 not indexed"*. The label is **"not indexed"**, not "unreadable": the register also holds password-protected, unsupported-format and out-of-scope entries, none of which is unreadable, and a narrow label narrows the guarantee it exists to express. It is never behind a click, never rounded, never suppressed when the failure count is zero.
- What a **user** sees is the *scoped denominator* (FR-14, FR-28), and the surface says so. What SM-3's invariant is asserted over is the *matter*/*tenant* *denominator*. These are two quantities with two names; no surface presents one as the other.
- Any statement of *exhaustive* *truth status* (FR-13) carries the *scoped denominator* it was computed against, the count of open `container-unopenable` entries of unknown cardinality, and the corpus-wide OCR figures of FR-3 — in the interface and in any export. An exhaustive result cannot be displayed or exported without them.
- If the counts cannot be computed, the interface says so and no *exhaustive* claim is available for that *matter*. It never displays a partial denominator as if it were complete.
- **Filesystem noise is a declared class, not a third bucket.** A configured exclusion list (`.DS_Store`, `Thumbs.db`, lock files, `desktop.ini`, resource forks) is applied at enumeration, is *configuration-as-data*, and its excluded count is reported as its own named line in the *denominator* and in the completion summary — *"1 240 excluded as filesystem noise"* — visible, countable, and one click from the list of what was excluded. It is neither silently dropped nor allowed to dominate the register. `[ASSUMPTION: an exclusion list is required and must be surfaced as its own count. FR-6 previously forbade a third bucket outright, which forces either a corpus polluted with thousands of zero-value pièces or a failure register dominated by operating-system detritus. A declared, countable, inspectable exclusion is neither.]`

#### FR-7: Completion summary

When an *import job* finishes, the user gets human tasks and a summary — not a log. Realizes UJ-1.

**Consequences (testable):**
- Clicking the completed indicator opens a summary whose first element is the *denominator* and whose second is the set of *worklist* lines generated by this job.
- Every line in the human-tasks section is phrased as an action in the lawyer's language and is clickable through to the thing it refers to. A line that is not actionable is not shown here (see FR-27).
- The summary distinguishes, with counts: newly indexed, recognised as already present, excluded as filesystem noise, expanded from containers, entered in the *failure register* (broken down by error class).
- The summary is reachable again later from the *matter* and from the *audit record*; it is not a transient notification.
- **Only one *import job* may be open on a *matter* at a time.** A second start is refused with an explanatory *worklist* line offering to queue it. Without this, the *denominator* has no defined value while two jobs are open and FR-7's "newly indexed" versus "already present" counts become racy — the same two jobs run again would produce different numbers, which is exactly the silence UJ-1's edge case exists to prevent. `[ASSUMPTION: concurrent import jobs into one matter are serialised rather than specified. Allowing them requires a distributed count that no source document asks for.]`

---

### 4.2 Index and *payload schema*

**Description.** The *payload schema* is the only irreversible decision in the system, and it is made once, first. Everything else — the language model provider, the hosting, the embedder, the interface — sits behind an adapter and is replaceable. Two v1 defects are negated here explicitly, because both silently converted a working system into a broken one that still returned results: an index that wiped its own collection on any vector-size mismatch, and an embedder that fell back to a 256-bucket hash on any exception, unlogged. Retrieval did not stop working in v1; it silently became noise, which is worse.

**Functional Requirements:**

#### FR-8: The frozen *payload schema*

Every *chunk* written to the *corpus* carries a complete *payload schema* record.

**Consequences (testable):**
- Mandatory fields on every *chunk*, none nullable: *tenant*; *matter*; *RBAC scope*; *custodian*; source *pièce* identifier; source position within the *pièce* (sufficient to locate the passage in the original); extraction method **and extractor version**; schema version; ingestion timestamp; and the *pièce*'s own date where one could be determined, with an explicit "undetermined" value where it could not.
- The **full extracted text of a *pièce* is stored addressably**, separately from its *chunks*, because exhaustive search runs over it (FR-13) and chunk-boundary-spanning matches would otherwise be missed by construction. Its identity and version are recorded on the *pièce*.
- A write of a *chunk* missing any mandatory field is rejected at the boundary, fails the *import job* unit loudly, and enters the *failure register*. It is never written with a default, and never written with an empty *RBAC scope*.
- The schema carries an explicit version. A *chunk* written under an older version remains readable; a migration that cannot preserve every mandatory field of an existing *chunk* is rejected rather than run. **An *import job* that spans a version change completes under the schema and chunking versions it started with**, or is halted and restarted; a job may not silently produce two generations of *chunks* inside one *matter*.
- The distinction between the date a *pièce* bears and the date it was ingested is preserved separately. Neither is ever substituted for the other.
- Enforced as a **structural property** (FR-56): no code path can produce a *chunk* whose *RBAC scope* was inherited from a global default rather than from its *matter*. The check is a static one over the write boundary — there is exactly one writer, it takes the scope as a required argument, and no default value for that argument exists anywhere in the source.
- The schema accommodates, without writing them in this increment: an external-authority reference on a *chunk* (§15) and a `supersedes` relation between *pièces* (FR-4).

#### FR-9: The embedder fails loudly

Semantic embedding either works as configured or stops the work. It never degrades silently. *(v1 defect: silent 1024→256-dimension hash fallback on any exception, unlogged.)*

**Consequences (testable):**
- A real semantic embedder is used. There is no hash-based, bag-of-words or otherwise non-semantic embedder available at runtime under any configuration, including test and development configurations.
- Any failure of the embedder — unavailability, rate limiting, timeout, dimension mismatch, authentication failure — halts the affected unit of the *import job*, records it in the *failure register* with its error class, and generates a *worklist* line. It never produces a *chunk*.
- There is no fallback embedder. Enforced as a **structural property** (FR-56): the embedder interface has exactly one non-test implementation, no exception handler in the embedding path constructs an embedder, and no configuration key selects one by name outside the enumerated provider list.
- The embedder identity and its output dimension are recorded on every *chunk* via the *payload schema*, so a mixed-provenance *corpus* is detectable rather than merely suspected.
- Injecting a transient embedder failure into an *import job* of 1 000 *pièces* results in: some *pièces* indexed, the failed ones in the *failure register*, the *denominator* consistent, and a retry that completes them. Asserted by test.

#### FR-10: The index never deletes itself

No automatic process may destroy indexed material. *(v1 defect: the whole collection was wiped on any vector-size mismatch — one transient error destroyed the corpus.)*

**Consequences (testable):**
- No code path performs a bulk deletion, recreation or truncation of a *tenant*'s indexed material as a response to an error condition, a schema mismatch, a dimension mismatch or a version difference. Enforced as a **structural property** (FR-56): the destructive index operations are reachable from exactly one named administrative entry point, and a static check asserts no other call site exists.
- A dimension or schema mismatch between incoming *chunks* and the existing *corpus* halts ingestion for that unit, surfaces on the *worklist* as an actionable line naming the mismatch, and leaves the existing *corpus* intact and queryable.
- Destructive operations on a *corpus* exist only as explicit, human-initiated, per-*tenant* actions recorded in the *audit record* with a reason.
- Recovery from a halted state does not require re-indexing the whole *corpus*.

#### FR-11: Chunking with provenance to source position

Every *chunk* can be traced back to the exact place it came from.

**Consequences (testable):**
- From any *chunk*, the interface can open the source *pièce* and locate the passage the *chunk* was derived from.
- Chunk boundaries are deterministic: re-chunking the same *pièce* with the same configuration produces identical *chunks* with identical identifiers.
- A quoted passage surfaced anywhere in the product resolves to a *chunk* by identifier and matches its source by exact string containment. In this increment the consumer is FR-41's justification and FR-26's *audit drawer*: every *retained extract* shown to a user or written into an export is verified by exact containment at the moment it is shown. `[ASSUMPTION: exact-containment verification is built here, and it now has a consumer inside this increment rather than only in the next one. Previously it was justified by cheapness alone, which is the "it's just tokens" belief operating in plain sight; the named consumer is what earns it a place.]`
- A resolution that **fails** at read time — the *pièce* is gone, its text has changed under re-extraction, the containment check does not hold — is surfaced as such wherever the extract appears, and marks the containing *audit record* export as degraded. An extract that no longer resolves is never displayed as though it did. *(An export exists to be read later, without the system, by a bâtonnier or a court. Self-containment verified only at export time is self-containment that rots at exactly the moment it is used.)*
- Chunking configuration is *configuration-as-data* and is recorded on the *chunk*, so *chunks* produced under different configurations are distinguishable.

---

### 4.3 Retrieval — two engines with different *truth status*

**Description.** The product is two engines that must never be confused: one that **finds** and one that **proves**. Semantic retrieval is ranked, top-k and **suggestive** — it can support a finding and can never prove an absence. Deterministic exhaustive search returns the **complete** match set over the whole indexed *corpus* within *RBAC scope* and is the only thing that can support the sentence a lawyer needs: *exact search over the entire indexed corpus, zero occurrences.* The interface must never blur them, and a **similarity threshold** must never be dressed up as a proof. *(v1 defect: an off-corpus gate implemented as a similarity threshold, shipped disabled by default — a guess that looked like a proof, which is worse than nothing.)*

**Functional Requirements:**

#### FR-12: Semantic retrieval, marked *suggestive*

A user can retrieve *pièces* by meaning, ranked. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- Results are returned ranked, with a stated k, and the result set declares *truth status* = **suggestive**.
- Every result carries its *pièce* identity and the *chunk* provenance that produced it, and is openable at the source position.
- A semantic result set never displays or exports a count phrased as a total ("N documents match"); it displays "top N of the corpus by similarity" or equivalent wording that cannot be read as completeness.
- No similarity threshold, in any configuration, causes a semantic result set to be labelled or exported as **exhaustive**. Enforced as a **structural property** (FR-56): *truth status* is set at exactly one construction site per engine and is a constant there.
- Where a **similarity threshold** is used for any purpose — the term is used consistently; "score threshold" is not a second name for it — its value is *configuration-as-data*, is recorded with the result, and has a defined default. A threshold defaulting to a value that disables the behaviour it governs is a defect. *(The v1 instance and its variable name are recorded in `addendum.md` §4.)*

#### FR-13: Deterministic exhaustive search

A user can obtain the **complete** set of *pièces* matching a *deterministic expression* over the whole indexed *corpus* within their *RBAC scope*. This is the only mechanism in the product that can support a claim of absence — **and only a qualified one**. Realizes UJ-2.

**Consequences (testable):**
- The result set is complete, not truncated, not ranked by a model, and not sampled. If completeness cannot be guaranteed for a query, the query returns an error stating why, and never returns a partial set labelled **exhaustive**.
- **Exhaustive search runs over the stored full extracted text of each *pièce* (FR-8), never over *chunks***, so that a phrase or proximity match spanning a chunk boundary is found. Asserted by test with planted matches placed deliberately across chunk boundaries.
- **The normalisation semantics of a *deterministic expression* are specified, not left to an implementation.** For French text and OCR output, each of the following is decided, stated in the interface at least once, and asserted by test: diacritics (a query for *arrêté* matches *arrete* in degraded OCR, and the result declares that accent-insensitive matching was applied); case; elision (*l'article* / *article*); ligatures; hyphenation across a line break in a scanned PDF; whitespace normalisation; and whether the expression supports boolean, proximity, wildcards or none of them. **An unspecified normalisation is not a detail: opposing counsel needs one document in which the word appears with an accent the OCR dropped.** `[ASSUMPTION: accent-insensitive, case-insensitive, elision-aware, hyphenation-joining matching is the default, with the applied normalisation declared on the result. The sources specify none of this and the guarantee is undefined without it.]`
- The result set declares *truth status* = **exhaustive** and carries, in the interface and in every export: the *scoped denominator* (FR-6); the count of open *failure register* entries; the count of open `container-unopenable` entries **of unknown cardinality**; the count of *pièces* in the searched set whose text was derived by OCR; and how many of those are below the OCR quality signal (FR-3). **An absence claim that cannot state these is not exhaustive and is not offered.**
- **Every absence statement discloses that it is scope-limited, in its exported wording and not only in its record**: *"no occurrence in the 97 200 pièces indexed for this matter and visible under the scope 'Contentieux X'; 2 800 not indexed; 1 archive unopened, contents unknown; 31 400 pièces transcribed by OCR, 900 of them below the quality threshold."* Never *"exact search over the entire corpus, zero occurrences"* unqualified. *(§4.3 exists to prevent a guess wearing the costume of a proof. Without these qualifications the same defect returns one layer down, at the extraction boundary, where nobody was looking.)*
- **The name of a *pièce* is inside the searched set.** The user's own statement of what this engine is for was *"type the exact name of the pièce, like on a classic computer"* — a Ctrl+F escape hatch behind the semantic search — and neither engine searched names. The filename as submitted and the title where one is extractable are searched under the same normalisation as the text, and the result declares that names were searched. A *pièce* in the *failure register* is **not** in the searched set even where its name matches: the register is searched separately within scope (FR-5), and a name match there is returned as a register hit, visibly distinct from a *corpus* hit and never counted inside the **exhaustive** set. *(An exhaustive result declares completeness over "the searched set". A searched set that silently excludes the one field the user was told to type makes that declaration true and useless.)* `[ASSUMPTION: names and titles are inside the searched set, and the failure register is searchable by name separately. The sources record the user's request for an exact-name search; no requirement implemented it.]`
- Correctness is asserted by test against a *corpus* with known plants: every planted match is returned, and no non-match is; plants include accented, hyphenated, elided and OCR-degraded variants, **and planted names — a *pièce* found by its filename, and a *failure register* entry found by its filename and returned as a register hit.**
- Exhaustive search latency at the *design target* is measured and recorded from the first measured baseline and may then only improve, in the same manner as SM-2's recall ratchet. `[ASSUMPTION: no absolute latency target is set; the source documents state none. What is required is that the figure exists, is recorded, and regresses no further. See OQ-6.]`

#### FR-14: *RBAC scope* as a query pre-filter

No user ever receives material outside their *RBAC scope*, and the filtering happens before retrieval, not after. This is the #1 realistic leak vector — ahead of the model provider and ahead of logs — and a post-filter leak is silent.

**Consequences (testable):**
- The *RBAC scope* predicate is applied as a constraint on the retrieval query itself. Enforced as a **structural property** (FR-56): retrieval has exactly one entry point, it requires a scope argument, and no result-set post-processing function accepts a scope.
- An adversarial test suite issues queries whose highest-similarity matches are deliberately outside the caller's *RBAC scope*, over both engines, and asserts zero out-of-scope results and zero out-of-scope metadata — including counts, snippets, identifiers, filenames and *scoped denominator* figures.
- **The adversarial suite mutates scopes**; it does not only query against static ones: it re-scopes a *matter* mid-corpus, revokes a scope while a session is open, grants one mid-*sampling run*, and asserts the wall holds in its new position immediately and in its old position never (FR-49 for the re-stamp mechanism and for the grant). *(A wall widened by an ordinary administrative act is the failure R-4 rates "Low if the tests hold" — and the tests did not previously cover it.)*
- The *failure register* is inside this guarantee, not outside it (FR-5). It is the one surface that cannot inherit the stamped scope of FR-8, because a *pièce* that never entered the *corpus* never had a *chunk* written, and its filename is frequently the privileged fact.
- The *scoped denominator* and any *confidence bound* shown to a user are computed within that user's *RBAC scope*, so the numbers themselves cannot leak the existence of material they may not see — and the surface says which quantity it is showing (FR-6).
- A user with no *RBAC scope* receives an empty *corpus*, not the whole *corpus*. Fail-closed is asserted by test, including for administrative and system identities.
- Every retrieval is recorded in the *audit record* with the *RBAC scope* it was executed under, and that record is reviewable by a holder of the *tenant* administrative grant (FR-49) — a log nobody can read is not an insider-threat control.
- **Revocation reaches open sessions.** A scope change invalidates rendered state, in-flight exports and running *sampling runs* belonging to the affected user within a bounded interval, rather than at next login. An incomplete *sampling run* whose owner lost the scope is re-assigned to the *worklist* of a user who holds it, or is closed as abandoned with a recorded reason — never left invisible.

#### FR-15: Every result set declares its *truth status*

The distinction between finding and proving is carried by the data, not by the user's memory.

**Consequences (testable):**
- *Truth status* is a property of every result set returned by any engine, present in the interface, in any export, and in the *audit record* entry for the query.
- The two statuses are visually and verbally distinct in the interface, and the distinction survives export to any format offered.
- No interface element combines results from both engines into one undifferentiated list.
- An export of a **suggestive** result set carries wording that cannot be read as a claim of completeness; an export of an **exhaustive** result set carries the *denominator*.

---

### 4.4 Triage

**Description.** Underneath there is **one ranked order** and nothing else. Nothing is deleted, nothing is moved into a folder, nothing is categorised into a container — so reversibility is a structural property rather than a promise anyone has to keep. On top of that order the tool **commits**: it draws **the line** and says "in my view, everything above this". The *retained set* and the *discarded set* are views over that order. The user moves **the line**, and the move is priced before she makes it; or she moves **one *pièce*** across it with a *pin*, without dragging the line past everything above. Each *pièce* carries a label, a confidence and a one-line justification she can read in a second and reverse in one click. The table is editable cell by cell with a live *change log*, and no edit ever triggers a regeneration that costs her another edit. Realizes UJ-1, UJ-3, UJ-4.

**Where the order comes from.** This section governs what the product *does with* a ranked order. **The order itself, the labels, the confidences and the justifications are produced by §4.9 (FR-37…FR-43)**, which was added in the revision of 21 July 2026 after three reviews independently found that no requirement in the document produced the ranking the whole increment is named after. Read §4.9 first.

*(v1 defect: the only destructive control was a raw confirmation dialog with no undo and no audit entry; there was no per-document confidence and no explicit validation act. That directly violated "triage never destroys".)*

**Functional Requirements:**

#### FR-16: One ranked order, nothing deleted, nothing categorised

Triage is a ranking, not a filing system.

**Consequences (testable):**
- The system holds exactly one ranked order per *matter* per *ranking version*. The *retained set* and the *discarded set* are derived from that order, the position of **the line** and the *pins* (FR-43); they are not stored as memberships.
- No triage operation deletes a *pièce*, removes it from the *corpus*, or excludes it from retrieval. Asserted by test: a *pièce* in the *discarded set* is still returned by exhaustive search (FR-13).
- Re-running ranking produces a new *ranking version*; the previous version remains readable and every *confidence bound*, *audit record* entry, *pin* and **the line** position remains bound to the version it was computed against. Human-set values (FR-20) and *pins* carry across versions and are marked as human-set; machine values do not.
- **Every surface naming "the discarded set" or "the retained set" names the *ranking version* it means.** With multiple versions retained and nothing ever deleted, an unqualified reference has an ambiguous referent at precisely the point where legal claims are made.
- **The number of retained *ranking versions* is bounded by configuration**, with the versions referenced by a *confidence bound*, a *pin*, an export or an *audit record* entry exempt from the bound. Unbounded versioning against a never-delete rule is unbounded state; the exemption is what keeps the record intact. `[ASSUMPTION: a retention bound on ranking versions is required. The sources require never-delete and per-version binding, and do not address what accumulates.]`
- No user action in the triage surface is irreversible. There is no destructive control.

#### FR-17: The tool draws **the line**

The system commits to a recommendation rather than handing back an undifferentiated ranking. Realizes UJ-1, UJ-4.

**Consequences (testable):**
- After ranking, **the line** has a position, chosen by the system, with a stated basis — the basis being the *case theory* where one exists, or the named intrinsic signals where none does (FR-38). The interface states the commitment in words — "in my view, everything above this" — not merely by drawing a divider.
- **The line**'s position is stored as an **ordinal cut over a named *ranking version*, together with the identity of the last retained *pièce***, with an author (system or named user) and a timestamp. It is never stored as a bare score and never as a bare integer: under a bare ordinal, position 180 of 1 700 becomes position 180 of 2 000 after an import and silently designates a different set; under a bare score, the retained count moves on its own and FR-19's priced statement is computed against a number nobody changed.
- A ranking is never presented without **the line**. **The refusal condition is defined, not left as a word:** the system places no line, and says so, where the *matter* holds fewer *pièces* than a configured floor, or where the dispersion of relevance scores is below a configured threshold (the degenerate case in which the model has separated nothing), or where more than a configured share of *pièces* could not be scored at all (FR-38). Each of the three is *configuration-as-data*, each has a defined default, and each is asserted by test with a *matter* constructed to trigger it. `[ASSUMPTION: the three refusal conditions and their form are an inference. The sources require a refusal and define none, which makes SM-8 satisfiable by an implementation that never refuses and by one that always does.]`
- Changing **the line** never reorders the underlying ranked order.
- **The line** is a per-*matter*, *matter*-global parameter, while every view of the order is filtered by *RBAC scope*. A user whose scope covers part of a *matter* sees a filtered view, is told so, and **may not move the line** unless her scope covers the whole *matter*; she may pin (FR-43) within her scope. *(Otherwise she moves the line two positions in her view and thirty in the matter, over documents she has never seen, recorded as her decision.)*

#### FR-18: Per-*pièce* confidence and a one-line reversible justification

Every *pièce* carries why it is where it is. Realizes UJ-1, UJ-3. *(How the confidence is derived: FR-42. What the justification is derived from: FR-41.)*

**Consequences (testable):**
- Every *pièce* in the ranking carries a confidence value and a justification of one line, in the user's language, readable without opening the *pièce*.
- **The justification is generated only where it can be read.** One-line justifications are generated for the *pièces* above **the line** and for a configured band below it, and on demand for any other *pièce* in one click. Generating 100 000 of them is the largest data-egress event and the largest inference cost in the system (§9, §11), and generating them where nobody will read them buys nothing the user notices. `[ASSUMPTION: near-the-line generation with on-demand backfill, rather than universal generation. The sources require a justification on every pièce; this preserves that for every pièce a user actually encounters and cuts cost, latency and egress by roughly an order of magnitude.]`
- Every justification is expandable into the *audit drawer* (FR-26) showing the *retained extracts* behind it, each resolving to a *chunk* by identifier and to a position in the source *pièce*.
- Every justification is reversible: the user can reject the tool's assessment for that *pièce* in one action, and the rejection is recorded in the *audit record*.
- A *pièce* for which no confidence could be computed is shown as such, explicitly, and generates a *worklist* line. It is never shown with a default or an imputed confidence, and it is never sorted to the bottom as though it had scored zero (FR-38).

#### FR-19: Moving **the line** is priced

The user is shown the cost and the benefit of moving **the line** before she moves it. Realizes UJ-4.

`[NOTE FOR PM]` **Unblocked 21 July 2026.** This FR and FR-23 depend on the estimator behind the *confidence bound*, previously recorded as a blocking prerequisite awaiting a statistician. **Decision: build it and prove it by simulation** (OQ-4). The estimator is standard hypergeometric statistics; the five hard inputs are design decisions to be answered explicitly and recorded, and the result is validated against populations whose truth is known — a stated 95% bound must hold in at least 95% of simulated runs, asserted in CI. An estimator that fails that test does not ship.

**The fallback stands if the validation cannot be made to pass:** the draw, the verdicts, the *audit record* and the *worklist* mechanics of FR-22 and FR-24 in full, and a sentence reporting **counts only** — *"200 pièces sampled at random from the 1 400 discarded; none relevant"* — with no bound and no projected figure. Materially weaker, and still honest. Shipping a number nobody can defend is neither.

**Consequences (testable):**
- While a user is repositioning **the line**, the interface states, for the candidate position: the change in the number of *pièces* to read, and the change in the **estimated prevalence of relevant material in the resulting discarded set** — in the form *"400 more pièces to read; the estimated share of the discarded set that is relevant falls from about 3% to about 0.4%"*. It never states a "risk of having missed a relevant document"; that quantity is not what any estimator here produces (§0.2).
- **The priced figure is labelled, on screen, as a projection from the ranking rather than as a sampling bound.** It is a model's estimate at a position where nothing has been sampled; a completed *sampling run* produces a different kind of statement and the two are never shown in the same visual register.
- **The projection is calibration-tested against the *gold set*, and a systematically optimistic projection fails the build** (SM-17). Calibration is what makes a projected number defensible; without it the priced statement is the single most dangerous artefact the product can emit, because FR-19 also requires it to be recorded permanently as the basis of a decision.
- The method producing the figure is documented, is reproducible from the *audit record*, and is named in the interface at least once (not buried). Where the method requires model scores to be reproducible, those scores are part of the *ranking version* record (FR-39) — otherwise FR-23's "reconstructible from the audit record alone" and this consequence contradict each other.
- Moving **the line** to retain everything states that the *discarded set* is empty and no *confidence bound* applies — it never reports a prevalence of 0%.
- Every move of **the line** is recorded in the *audit record* with old position, new position, author, timestamp, *ranking version* and the priced statement that was shown at the moment of the move.
- **The line** is a single per-*matter* parameter and is not a cell: a move is serialised, a second user's move made against a superseded position is refused with the current position shown, and the priced statement recorded is always one that was true when it was shown. `[ASSUMPTION: the line needs a concurrency rule of its own. FR-20's cell rule does not reach it, and without one the audit record stores a priced statement that was never true, attributed to a user who was shown it in good faith.]`
- Any existing *confidence bound* for the *matter* is marked stale on a move and is not reused; a *worklist* line offers re-sampling (FR-58).

#### FR-20: The editable cell-by-cell table with a live *change log*

The user corrects the tool without the tool undoing her. Realizes UJ-3.

**Consequences (testable):**
- Every editable value in the triage table is editable in place, cell by cell. Committing an edit changes that cell and nothing else. Asserted by test: after N edits across N rows, all N values hold.
- No user edit triggers regeneration, re-ranking or re-classification of any other row. Any re-ranking is a separate, explicit, user-initiated action that produces a new ranking version (FR-16) and never overwrites edits — edited values survive re-ranking and are marked as human-set.
- Each edit produces a *change log* entry shown next to the row immediately: previous value, new value, author, timestamp.
- Edits are reversible from the *change log* itself, and a reversal is itself a *change log* entry rather than an erasure.
- Concurrent edits to the same cell by two users are both recorded, in order, attributed; the current value is unambiguous and no edit is lost. `[ASSUMPTION: see UJ-3 edge case.]`
- **"In order" means a server-assigned monotonic sequence, not a workstation clock.** Every *change log* and *audit record* entry carries both a wall-clock timestamp and a sequence number assigned by a single authority; ordering is decided by the sequence. An append-only record ordered by whichever workstation is fast is worse than one with no timestamps, because it answers §13's questions confidently and wrongly. `[ASSUMPTION: an authoritative monotonic sequence is required. The sources require timestamps and ordering and name no clock; an air-gapped installation has no NTP.]`
- **There is no undetectable bulk operation on this table.** A bulk edit, where one exists, produces one *audit record* entry per affected *pièce*, each carrying a marker that it was applied in bulk together with the size of the set — so that a reader of the export can tell 1 400 individual judgements from one gesture. A bulk *validation act* is governed separately and more strictly by FR-45.

#### FR-21: Never hard-delete

No user-facing action destroys data.

**Consequences (testable):**
- No control in the product performs a hard deletion of a *pièce*, a *chunk*, an *audit record* entry, a *change log* entry or a *failure register* entry. A resolved *failure register* entry is a **state change**, not a removal (FR-5).
- Any action a user could reasonably read as deletion is implemented as a reversible state change, is labelled as such, and is recorded in the *audit record*.
- Removal of a *tenant*'s data as a whole exists only as an explicit administrative operation outside the user surface, recorded in the *audit record*. `[ASSUMPTION: a firm will eventually require erasure of a matter — for a GDPR request or at the end of a retention period. The source documents say "never hard-delete" and do not address lawful erasure. See OQ-8; this PRD does not resolve the contradiction, it names it.]`
- Asserted by a **bounded runtime probe over an enumerated action set** — not by a claim about all possible program behaviour: every user-reachable action is enumerated in a registry, the registry's completeness is a *structural property* (FR-56), and the probe executes each action and asserts no reduction in the count of stored *pièces*, *audit record* entries, *change log* entries or *failure register* entries.

---

### 4.5 Audit and sampling

**Description.** This is the north star of the increment and the mechanism the sceptic actually buys. "Recall over precision" becomes a number rather than a slogan: draw at random from the *discarded set*, check, and state a *confidence bound* as a sentence a lawyer can say out loud. Around it sits the *audit record* — who validated, when, which version, what was modified versus accepted as-is, and which *overrides* were made with what reason. Forcing a one-line reason on an *override* is the cheapest single mechanism that both builds the trail and makes the person stop and think. Realizes UJ-2.

*(v1 defect: the audit modules were 0-byte files and the audit-trail pull request was closed unmerged — while "auditabilité non-négociable" was sold in both client proposals.)*

**Functional Requirements:**

#### FR-22: Random draw from the *discarded set*

A user can draw a verifiably random sample from the *discarded set* of a *matter*. Realizes UJ-2.

**Consequences (testable):**
- The user sets a sample size, or requests a target *confidence bound* and is given the sample size that achieves it under the hypergeometric estimator.
- **The requested size is bounded by the population, and the census case is a different statement.** Where the required or requested size equals the *discarded set*, the run is a **census**, is labelled as one, and produces *"every discarded pièce was reviewed; none was relevant"* — a stronger and categorically different statement than a bound. Where a requested target bound is unreachable at any size, the tool says so and offers the best achievable. Drawing is **without replacement**. *(Producing "60 sampled from the 60 discarded; at most 4.8% is relevant" over a fully reviewed population is a false statement of residual risk, said out loud, to a judge.)*
- The draw is random over the whole *discarded set* within the user's *RBAC scope*, not over a recent, convenient or already-loaded subset. **The population is frozen for the duration of the run**: the run records the *ranking version*, the position of **the line**, the *RBAC scope* and the **explicit identifier list** of the drawn *pièces* — a seed alone is not sufficient, because a seed indexes into an ordering that must then be stable, and FR-39's tie-break makes the ordering stable only within a *ranking version*. Ingestion, re-ranking or a line move during a run marks the run as invalidated-in-flight and tells the user immediately, rather than letting an hour of a senior lawyer's verdicts silently become worthless.
- Each sampled *pièce* is presented with its one-line justification, its confidence, its *audit drawer* and the ability to open it in the viewer (FR-44), and the user records a verdict of relevant or not relevant. A verdict cannot be skipped silently; an unanswered item leaves the run incomplete.
- Marking a sampled *pièce* relevant immediately updates the projected *confidence bound* shown to the user, before completion. **The interface must not make honest verdicts feel expensive**: the running figure is shown as provisional and the surface never implies that stopping now preserves a better number. *(This live update is an FR-created incentive to stop early, and SM-C3 measures the consequence.)*
- **Repeated sampling over the same population is recorded and declared, never quietly pooled.** A second run over the same *ranking version*, line position and scope is permitted, is presented alongside the first rather than replacing it, and any bound derived from more than one run states how many runs it rests on. Sampling until a favourable result is a multiple-comparisons problem that a record showing all runs does not repair, and the copied sentence travels alone. **Whether independent runs pool, and how, is an input to OQ-4.**
- **The ritual is sized before it is started, in the lawyer's own terms.** Before the first *pièce* is presented, the tool states what it is asking for: how many *pièces*, the estimated reading burden derived from their extent (the same quantity FR-39 emits for the *retained set*), and the bound that size buys. A senior lawyer about to spend an evening is told so before the first verdict, not after the fortieth. *(This is the requirement that runs hardest against the constraint the product was shaped by — §2.1: the lawyer keeps an eye on the pile, he does not sort it. Nothing here makes 200 verdicts pleasant. Stating the size is the minimum honesty; OQ-26 is where the size itself is questioned.)*
- **A run is completable in batches, across sessions.** Progress is preserved, the population stays frozen, and the resumption *worklist* line states the remaining count. An abandoned run is a failure of ergonomics, not of the lawyer, and SM-C3 reads it that way.
- **Early stopping is a property of the estimator, never of the interface.** Where a run may be declared complete before its full size — because the verdicts already observed support the target bound — the stopping rule is part of the estimator and is validated with it (OQ-4, OQ-26). Optional stopping applied to a fixed-size bound invalidates the number it reports. No prompt, no progress indicator and no affordance may end a run early by any route that is not inside the validated rule.
- An abandoned run produces no *confidence bound*, is stored as incomplete, and produces an actionable *worklist* line to resume it. Asserted by test.

#### FR-23: The *confidence bound* as a sentence

A completed sampling run produces the sentence, not a chart. Realizes UJ-2. **Depends on the estimator (OQ-4), which is decided in approach and no longer blocking** — see the `[NOTE FOR PM]` at FR-19 for the method and the fallback.

**The estimator ships only if it is proven.** Its soundness is asserted by simulation in CI: over populations whose relevant-item prevalence and duplicate structure are known by construction, a stated C% bound must hold in at least C% of runs. A failing estimator emits the counts-only sentence instead — it never emits a bound it cannot defend. This is the same discipline the rest of the document applies to every other guarantee, and it is the direct answer to the false claim recorded in §0.2.

**Consequences (testable):**
- The output is a sentence of the form: *"N pièces sampled at random from the M discarded; K relevant. With C% confidence, at most X% of the discarded set — about Y pièces — is relevant."* It is copyable as text.
- **The sentence states a prevalence and names its confidence level. It never uses the phrase "risk of having missed a relevant document", or any wording a reader could take as the probability that nothing was missed.** Enforced as a **structural property** (FR-56): the banned phrasings are a checked list across every locale's string set, so a translator cannot reintroduce the false claim in French or Italian. *(This is the correction of §0.2 made mechanical rather than editorial, because the false sentence survived a brief, a glossary, three FRs and a north-star metric on editorial care alone.)*
- **The estimator is hypergeometric (finite-population).** The binomial rule of three is not used: at the sampling fractions this product operates at — 200 of 1 400 — the finite-population correction is a material tightening, and using the wrong one gives away accuracy the sample actually bought.
- The sentence names the *matter*, the *ranking version*, the *case theory* version, the position of **the line** and the *RBAC scope* it was computed under, or carries them in the accompanying record. **The scope is stated in the sentence itself where the scope is narrower than the *matter***: M is otherwise presented as a fact about the *matter* when it is a fact about one user's walls, and the lawyer says "1 400" to a court about a *matter* holding 2 100.
- Every number in the sentence is reconstructible from the *audit record* alone. Asserted by test: recompute from the exported *audit record* and compare. Anything the recomputation needs — including model scores where the method requires them — is in the record, or the method is not admissible (FR-19).
- The statistical method producing X is stated and is fixed for a given *tenant* by *configuration-as-data*; changing it produces a new *confidence bound* rather than silently restating the old one.
- Where the sample found K > 0 relevant *pièces*, the sentence says so and the bound widens accordingly; the product never suppresses or reframes an unfavourable result, and offers to move **the line** or to pin (FR-43) rather than silently re-ranking.
- **Where K approaches N — the reviewer disagrees with most or all of the sample — the finding is that the ranking carries no signal, not that the line is misplaced.** At a configured threshold the system declares the *ranking version* unfit for this *matter*, says so in words, produces a *worklist* line offering a re-rank with a revised or newly written *case theory* (FR-37), and does not offer a line move as the remedy. `[ASSUMPTION: a post-hoc unfitness declaration is required. FR-17's refusal is evaluated before ranking and never again; without this the product emits "at most 100% is relevant" and offers an action that cannot help.]`
- A *confidence bound* is displayed as stale, and cannot be exported as current, when its *ranking version*, its position of **the line**, its *case theory* version, its *pins* **or the population it was drawn from** have changed — the last of which includes **any ingestion into the *matter*** (FR-58).

#### FR-24: The *audit record*

Every decision that matters leaves a defensible trace. Realizes UJ-2, UJ-3, UJ-4.

**Consequences (testable):**
- The *audit record* is append-only. No user-facing action edits or removes an entry; a correction is a new entry.
- Recorded at minimum: who validated what and when, via a *validation act* (FR-45); every *case theory* and every revision of one, with its author and timestamp; the *ranking version*, the *payload schema* version and the application version; which values were modified versus accepted as-is; every position of **the line** with author and priced statement; every *pin*; every *sampling run* with its draw, its frozen identifier list, its verdicts and its resulting *confidence bound*; every *override* with its reason; every retrieval with its *truth status* and *RBAC scope*; every *import job* with its *denominator*; every configuration change; every *RBAC scope* grant, revocation and re-scope, with the authority under which it was made.
- Every entry carries an actor, a wall-clock timestamp, a **monotonic sequence number from a single authority**, and a *matter*. System-initiated entries name the system component as actor rather than attributing them to a user.
- The *audit record* is scoped by *tenant* and by *RBAC scope*: a user reading it sees only entries for *matters* within their scope.
- "Modified" and "accepted as-is" are distinguishable in the record. **A value the user never touched is recorded as accepted only where a *validation act* (FR-45) occurred over it** — not by default, not by elapsed time, and not by having been on screen.
- Continuity, write-or-fail and tamper-evidence are specified in FR-53. An *audit record* whose incompleteness cannot be detected is not evidence.

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
- The *audit record* for a *matter* is exportable as a document, within the user's *RBAC scope*, containing: the *scoped denominator*, the *case theory* and its revisions, the position history of **the line**, all *pins*, all *sampling runs* and their *confidence bounds*, all *overrides* with reasons, the *validation acts*, and the modified-versus-accepted breakdown.
- **The export is offered in two tiers, and the tier is chosen before it is produced.** A **numbers-only** tier carries counts, versions, verdicts, positions and bounds — everything SM-1's reconstruction needs and no client content. A **full** tier additionally carries *retained extracts*, *override* reasons verbatim, justifications and *failure register* filenames and paths. The default is numbers-only. *(An export handed to opposing counsel to substantiate a confidence bound would otherwise disclose the retained extracts of every sampled pièce.)*
- **This export is a third egress path and is named as one** (§11). It is not content-free, it is deliberate, and producing it — tier, actor, *matter*, scope, timestamp — is recorded in the *audit record*. It is the one act in the product that moves client content out of the firm on purpose, and it previously had no recorded trace of having occurred.
- The export is self-contained: a reader with the export and no access to the system can reconstruct every number in it. Asserted by test that recomputes from the export in a process with no access to the application's stores. Where a *retained extract* no longer resolves (FR-11), the export marks itself degraded rather than presenting a broken reference as intact.
- The export never contains material outside the exporting user's *RBAC scope*, and states the scope it was produced under on its face.

---

### 4.6 The home screen — the *worklist*, and the *matters*

**Description.** The home screen answers "what needs you?", not "what can I do?". **It has two zones, and the distinction between them is the design.** The **top zone is the *worklist***: a queue of what failed to import, what needs re-reading, what needs sorting. Human-in-the-loop stops being a policy statement in a proposal and becomes a queue with items in it. The design rule there is absolute and is the thing most likely to erode: **every line is an action in the lawyer's language, never a technical state.** Not actionable means not on the *worklist*.

The **second zone is the user's *matters* and where each has got to** (FR-60) — the answer to "where are my matters?", which the *worklist* by construction cannot give. It is **navigation, not a queue**, and it sits deliberately outside FR-27's rule. *(This resolves a contradiction the document carried: the description here promised "which matters are moving" while FR-27 forbade any line that is not actionable. The upstream decision was that the worklist is the top **zone**, not the whole screen. Collapse the two and matter progress arrives as worklist lines — which is the log FR-27 exists to prevent.)* Realizes UJ-1, UJ-2.

**Functional Requirements:**

#### FR-27: The *worklist*, actionable lines only

The home screen is a queue of human tasks.

**Consequences (testable):**
- Every *worklist* line has: a phrasing in the user's language naming the thing and the action (*"14 pièces illisibles — les traiter"*), a count where a count applies, and a single click-through to the surface where the action is performed.
- A line whose click-through leads nowhere actionable is a defect. Asserted by test: every generated line type resolves to a surface with an available action.
- No line exposes a technical state, a component name, an error code as its primary text, a stack trace, or a job identifier. Diagnostics live behind the line, not on it. **This is asserted by review against a checklist, not by test** — no test decides whether a phrasing is in a lawyer's language — and §7's metric suite does not pretend otherwise.
- Lines are generated by, at minimum: *failure register* entries, low-quality OCR flags, *pièces* with no computable confidence, incomplete or invalidated *sampling runs*, stale *confidence bounds*, halted *import jobs*, index-mismatch halts (FR-10), unfit *ranking versions* (FR-23), *matters* whose *case theory* is absent where one would materially help (FR-37), and failed backup verifications (FR-52).
- **Lines aggregate; the *worklist* is never one line per *pièce*.** The aggregation key is (*matter*, line type, error class), the aggregate carries a count and resolves to a filtered list with a bulk action where one exists (FR-5), and a partially completed aggregate shows its remaining count rather than disappearing. **A hard cap on displayed lines is configured**, with the remainder reachable in one click as "and N more". At the *design target* — 2 800 register entries plus OCR flags plus unscored *pièces* — an unaggregated worklist is exactly the log this FR forbids, on day one, at the scale this PRD chose. `[ASSUMPTION: the aggregation key, the cap and the partial-completion semantics are an inference. The sources show aggregated lines in UJ-1 and specify no aggregation rule.]`
- Completing the action removes the line; the line's history remains in the *audit record*.
- A line is never removed by the passage of time, by a background process, or by being viewed.

#### FR-28: The permanent *denominator* on the home screen

The user always knows what the system was given and what it did with it.

**Consequences (testable):**
- The *scoped denominator* is displayed on the home screen at all times, in the stated form, alongside the *worklist*, and is labelled as scope-relative.
- Clicking the not-indexed count opens the *failure register* filtered to it, within scope (FR-5).
- The *scoped denominator* is never displayed as a percentage alone and never as a health indicator; the absolute counts are always present.
- A change to the user's *RBAC scope* invalidates and recomputes the displayed figure within a bounded interval, not at next login (FR-14).

#### FR-60: The *matters* zone — "where are my matters?"

The home screen's second zone answers the question the *worklist* is forbidden to answer. Realizes UJ-1.

**Consequences (testable):**
- Below the *worklist*, the home screen lists the *matters* within the user's *RBAC scope* with the state of each: its *scoped denominator*, whether an *import job* is running, whether a ranking exists and whether it is stale (FR-58), whether a *sampling run* is open, and when this user last touched it.
- **A *matters* line is navigation, not a task.** It is never generated from a *worklist* line, never merged with one and never counted with one; where a state needs a human the *worklist* carries it and the *matters* line does not duplicate it. Asserted by test: no line type appears in both zones.
- The zone is bounded and ordered by last activity, with the remainder one click away. **The *worklist* is always the top zone** — a *tenant* with three hundred *matters* may not push the queue off the screen.
- Nothing in this zone is actionable beyond opening the *matter*. A control that performs work belongs on the *worklist* or on the *matter*.
- `[ASSUMPTION: matter progress belongs on the home screen as a second, separate zone. The upstream decision made the worklist the top zone rather than the whole screen, and §4.6 promised "which matters are moving" while FR-27 prohibited it. A second zone is the reading that keeps both true; the alternative — no matter progress on the home screen at all — is cheaper, is coherent, and is what §6.3's cut produces.]`

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
- At minimum the following are *configuration-as-data*, editable per *tenant* without a code change or a deployment of different code: the triage taxonomy and its labels; *RBAC scopes* and their assignment; the language model provider and its endpoint; the configured sources; the chunking configuration; the exclusion list of FR-6; the cascade and refusal thresholds of FR-17 and FR-38; thresholds referenced by FR-3, FR-12 and FR-23; and interface language.
- **Editable through the surface named in FR-50**, which is the answer to "editable by whom, through what". Direct database editing at a firm's site is not the mechanism: it produces no *audit record* entry, no validation and no rollback, and it is a per-site divergence — the fork this section exists to prevent, arriving as data instead of as code, which is not better.
- Enforced as a **structural property** (FR-56): no *tenant*-specific identifier or name appears anywhere in source code. *Tenant*-specific **behaviour** is not a greppable property and is not claimed as one; it is covered by the single-codebase build rule — one artefact is built and every installation runs it.
- Every configuration key referenced in any documentation exists in the configuration surface and is asserted to exist by a test. *(v1 defect: keys named in documentation appeared in zero source files; the embedder variable was named wrongly in the example configuration. Documentation lied in load-bearing places.)*
- Every configuration key has a defined default, and a test asserts that no default disables the guarantee its key governs. *(v1 defect: the off-corpus gate shipped disabled by default.)*
- Changing a configuration value that affects retrieval, ranking or the *confidence bound* is recorded in the *audit record* and marks derived artefacts stale (FR-58). Changing an *RBAC scope* additionally re-stamps or invalidates the material it governs (FR-56, FR-49) — stale is not sufficient where a wall has moved.

#### FR-31: The *content-free projection* primitive

There is exactly one mechanism for emitting information about a *tenant*'s data without emitting the data, its content-freedom is enforced by a test, and **it is built to outlive its first consumer.**

**Consequences (testable):**
- **The primitive is a registry, not a fixed list of value kinds.** Every emission is produced by a named **projector** registered in one enumerated registry; each projector declares the shape of what it emits; all emission goes through the registry. The registry holds, today, what the client-pushed diagnostic export needs: counts, enumerated error classes, version identifiers, timing figures, and diagnostics passed through a redaction step. **It is open by construction**, because the same primitive must serve the next increment's on-premises **style extractor** — whose output is a distribution over sentence lengths, a connector frequency and a phrasebook of the firm's own formulae, and is none of those five things. *(A closed enumeration here forces the next increment either to amend this FR or to build a second content-free path — which the last consequence below calls a defect, and which SM-7 would not cover. The primitive was specified upstream as one mechanism with three consumers; it was being built for one and narrowed against another.)*
- **Content-freedom is the property, and it is enforced structurally rather than by that list.** Three checks together: **(i)** the seeded-token test runs against **every registered projector**, not against the export — given a *corpus* seeded with known unique tokens, no output of any projector contains any of them; **(ii)** an emission path outside the registry fails the build, as a *structural property* (FR-56), so a projector cannot be added by writing one; **(iii)** a projector deriving a value from *pièce* or *chunk* text may emit only values **attested across a configured minimum number of *pièces* and *matters***, never a value traceable to one. The third is what makes a phrasebook of a firm's own formulae content-free rather than a set of quotations from a client's *matter*. `[ASSUMPTION: an attestation floor is the structural form of content-freedom for text-derived projectors, and it is what lets the style extractor reuse this primitive rather than fork it. The sources specify one reusable primitive with three consumers and do not say how the third stays content-free.]`
- The seeded-token test is the guarantee; a statement in a document is not.
- Filenames, paths, *matter* names, user names, *pièce* content, *chunk* content and query text never appear in any output. Where a name is needed for correlation, an opaque identifier is used.
- All emission of information about a *tenant*'s data goes through this primitive. A second, ad-hoc path is a defect.

#### FR-32: The client-pushed diagnostic export

The firm can send APX a diagnostic; APX can never fetch one.

**Consequences (testable):**
- The export is initiated by a user of the *tenant*, never by a remote request. There is no inbound channel by which APX can trigger it. Asserted by test.
- The export is produced by FR-31 and is inspectable by the user in full, in readable form, before it leaves — no opaque blob.
- The export contains at minimum: the *denominator*, *failure register* counts by error class, component and schema versions, and redacted diagnostics.
- Producing an export is recorded in the *audit record* with actor and timestamp.
- **There is no telemetry.** Enforced as a **structural property** (FR-56): every outbound network call originates from an enumerated set of adapters — the configured language model provider, the configured embedder, the configured OCR service where one is used — and a static check asserts no other outbound call site exists. The three egress paths of §11 are the whole list.

#### FR-33: One *ingestion* path — no fixture layer, no demo override

Corpora are data sources, never fallbacks. *(v1 defect: a demo helper swapped a healthy backend response for hand-authored fixtures whenever a provider flag was set — the demo layer literally overrode the real product, and two whole screens never called the backend at all.)*

**Consequences (testable):**
- No code path substitutes stored, hand-authored or generated content for a live response from a working component, under any flag, environment variable or build configuration. Enforced as a **structural property** (FR-56): no runtime module imports from the test tree; no runtime module reads a fixture directory; and no conditional on an environment variable selects a data source outside the enumerated configured-source list.
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

### 4.9 Relevance — what the ranking is relative to

**Description.** This section was added on 21 July 2026. Until then the increment was named after a triage no requirement produced: §4.4 held the ranked order, **the line**, the confidences and the justifications, and nothing anywhere said that the system ranks, what it ranks toward, or where the judgement comes from. Three independent reviews found the same hole.

**The model is hybrid, with an LLM judgement at its centre.** An LLM assesses each *pièce*'s relevance, informed by a **case theory** the lawyer may optionally write — what she is trying to establish, against whom, over what period — and by intrinsic signals where no case theory exists. **Relevance is a relation to a question, not a property of a document.** A *pièce* is not "relevant"; it is relevant *to this case theory* or, failing that, *by these named intrinsic signals*, and every artefact derived from a ranking says which.

**This is the most expensive capability in the increment**, in build time, in inference cost and in data egress, and it is the one whose quality nobody can verify without a real *matter*. §9 and §11 state its cost and its egress honestly rather than describing it as "a query path".

**Functional Requirements:**

#### FR-37: The optional *case theory*

The lawyer can state what she is looking for, at any time, and the ranking is relative to it. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- A *case theory* is free text in the user's own language, offered as an optional fourth field at import (FR-1) and writable, rewritable and deletable at any later moment from the *matter*. It is never mandatory and its absence never blocks *ingestion*, ranking or any other function.
- Writing or rewriting a *case theory* produces a **new version** of it, retains the previous versions readably, is recorded in the *audit record* with actor and timestamp, and offers a re-rank. The re-rank is user-initiated and explicit; it is never automatic, because an automatic re-rank would overwrite the work FR-20 exists to protect.
- A re-rank under a new *case theory* version produces a new *ranking version* (FR-39). Human-set values, *validation acts* and *pins* survive it and remain marked as human-set.
- Every *ranking version*, every position of **the line**, every *confidence bound*, every justification and every *audit record* entry derived from a ranking names the *case theory* version it was computed against, **or names explicitly that none existed**. A reader of the export can therefore answer *"relevant to what question?"*, which is the first thing anyone contesting the triage will ask.
- The *case theory* is carried in the *audit drawer*, in the *audit record* export (full tier, and as a version identifier in the numbers-only tier) and in the retained-set export (FR-46). It is translated for display like any other user-visible text but is **never machine-translated before being sent to the model**; the model receives it as written, with its language declared (FR-36).
- Where no *case theory* exists and the *matter* exceeds a configured size, a *worklist* line offers to write one, stating in the lawyer's language what it would buy. It is an offer, never a block.

#### FR-38: The *relevance judgement* — a cascade, cheap filters first

Every *pièce* in a *matter* receives a relevance assessment, produced by a staged cascade rather than by an LLM call per *pièce*. Realizes UJ-1.

**Consequences (testable):**
- The cascade has three stages and its stage boundaries are *configuration-as-data*: **(1)** deterministic filters and near-duplicate grouping — document type, participant roles, dates against the *case theory*'s period, exact and near-duplicate families, obvious noise; **(2)** cheap semantic scoring over the *corpus* embeddings already produced by FR-9; **(3)** an **LLM judgement, applied only to the uncertain band** that stages 1 and 2 could not separate, plus a mandatory sample of the confident bands so the cascade's own calibration is measurable.
- **The share of *pièces* reaching stage 3 is measured and recorded per run** (SM-18). This is the number that decides the cost, the latency and the egress of a triage run, and it is the number a build regression would otherwise hide.
- Near-duplicate families — quoted reply chains, sender and recipient copies, a message forwarded as an attachment — are **grouped and judged as a family**, with one representative carrying the family and the members retaining their own identity, provenance and *custodian*. Without this, forty near-copies of one thread occupy forty positions around **the line**, crowd out distinct documents, and are counted by a *sampling run* as forty independent draws when they are one document. **The near-duplicate threshold is an input to OQ-4, not only to this FR.**
- Where a *case theory* exists, the judgement is relative to it and the *retained extracts* it used are recorded. Where none exists, the judgement is relative to an **enumerated, named set of intrinsic signals** — document type, participant roles, date distribution, duplication, obvious noise — and every artefact derived from that ranking states, in the user's language, that no case theory was given and what was used instead. It never presents an intrinsic-signal ranking in the vocabulary of a matter-specific judgement.
- **Model-provider failure during judgement halts loudly and never imputes.** Rate limiting, timeout, unavailability or a malformed response for a *pièce* leaves that *pièce* **unscored**, not scored zero; unscored *pièces* are excluded from the ranked order rather than sorted to the bottom, are shown as unscored, and generate a *worklist* line. A *matter* whose unscored share exceeds the FR-17 threshold gets no line. *(A null sorted to the bottom is a document no model ever read, sitting in the discarded set, inside the population a confidence bound reports on. That is "a plausible-looking wrong answer" at exactly the point the product's claim rests.)*
- A ranking may be produced over a partially ingested *corpus* only where the interface says so and no *confidence bound* is offered against it (OQ-7).

#### FR-39: The ranked order and the *ranking version*

The system produces one ranked order per *matter*, reproducibly. Realizes UJ-1, UJ-4.

**Consequences (testable):**
- Ranking is an explicit, user-initiated or import-completion-triggered act that produces exactly one ranked order over the *pièces* of a *matter*, together with a *ranking version* recording the full identity of what produced it: *case theory* version, model identity, prompt version, temperature and every other sampling parameter, cascade configuration, embedder identity, chunking configuration, schema version.
- **Re-running a fixed *ranking version* over a fixed *corpus* reproduces the same order, *pièce* for *pièce*.** Asserted by test. Where the model is non-deterministic at the configured temperature, the *ranking version* records the scores themselves so that the order is reconstructible even where the judgement is not repeatable — an order that cannot be reproduced cannot support FR-23's "reconstructible from the audit record alone".
- **The tie-break is deterministic and specified**: ties in relevance score are broken by a stable key recorded in the *ranking version*, never by the order a store happened to return. Ties are the normal case for near-duplicates and for boilerplate, and a tie spanning **the line** would otherwise reshuffle set membership on recomputation with no recorded event — which silently invalidates any *sampling run* drawn from it.
- The ranked order is a view input, not a stored membership: the *retained set* and *discarded set* are derived from it (FR-16).
- The ranking emits a **per-*matter* review-effort estimate** — the count of *pièces* above **the line** and an estimated reading burden derived from their extent — which is the figure the partner bids from (§2.1) and the quantity SM-11 tracks.
- A ranking that cannot be produced at all fails loudly with a *worklist* line and leaves the *matter* unranked; it never produces an arbitrary order.

#### FR-40: Per-*pièce* labelling against the *tenant*'s triage taxonomy

*Triage* is ranking **and** labelling, and this is the labelling. Realizes UJ-3.

**Consequences (testable):**
- Every *pièce* in a ranking carries **exactly one label** drawn from the *tenant*'s configured triage taxonomy (FR-30), or the explicit value `unlabelled` where none could be assigned. There is no null and no default label.
- A label is a *label*, not a rank: **changing a label never changes a *pièce*'s position** in the ranked order and never moves it across **the line**. Moving one *pièce* across **the line** is FR-43. *(The Glossary has defined Triage as ranking and labelling since the first draft, UJ-3's whole path is a lawyer changing a classification, FR-30 makes the taxonomy configurable and OQ-16 questions whether it is the right one — and until this revision no requirement applied a label to anything.)*
- A label change is an ordinary cell edit: it produces a *change log* entry (FR-20), it survives re-ranking marked as human-set, and it is reversible from the *change log*.
- The taxonomy is *configuration-as-data*; changing it does not invalidate existing labels, but labels no longer in the taxonomy are shown as such and generate a *worklist* line rather than being silently remapped.
- **The word *classification* is used in this document for triage labelling only.** §11's data-classification bullet uses "data classification" in full. Two concepts, two phrasings.

#### FR-41: The justification, derived from named evidence

The one-line justification is derived from something checkable, not composed freely.

**Consequences (testable):**
- Every justification is generated from a stated input set: the *case theory* version (or the named intrinsic signals), and the **specific *retained extracts*** the *relevance judgement* used — each named by *chunk* identifier and resolvable to a position in the source *pièce*.
- Every *retained extract* shown with a justification passes exact-containment verification against its source at the moment it is shown (FR-11). A justification whose extracts do not resolve is shown as unverified, never as ordinary.
- The justification is in the user's active language (FR-36) and states the source *pièce*'s language where it differs.
- **The extracts are the control; the sentence is not evidence.** This is stated in the interface, once, plainly: the justification is a model's summary of why the extracts were thought relevant, and the extracts are what a reader should check. R-11 is mitigated by making the checkable part visible, not by asserting the sentence is good.
- Justification quality has **no automated measure** in this increment, and none is claimed. It is assessed in structured evaluation sessions (§7, SM-C2) and the absence of a metric is recorded rather than papered over.

#### FR-42: Per-*pièce* confidence is derived, never self-reported

A number the model made up about its own certainty must never reach a *confidence bound*.

**Consequences (testable):**
- The confidence attached to a *pièce* is **derived from observable quantities** — the margin between competing scores, agreement across the cascade's stages, or agreement across repeated judgements — and never from a figure the language model states about itself. Enforced as a **structural property** (FR-56): no field parsed from a model response is named or used as a confidence, and the derivation function has one implementation.
- The derivation method is recorded in the *ranking version* and is reproducible from it.
- Confidence is **calibrated against the *gold set***: among *pièces* the system assigned a given confidence band, the observed share that are relevant is measured and recorded (SM-17). A systematically overconfident derivation fails the build.
- A *pièce* whose confidence could not be derived is shown as such (FR-18) and is never given an imputed value.
- No self-reported model number feeds FR-19's priced statement or FR-23's *confidence bound*, directly or through any intermediate. *(A made-up number laundered through a statistical sentence is the failure mode of §0.2, one layer further down.)*

#### FR-43: Moving a single *pièce* across **the line** — the *pin*

One *pièce* can cross **the line** without dragging the line past everything above it. Realizes UJ-3.

**Consequences (testable):**
- A user can **pin** a *pièce* into the *retained set*, or out of it, in one action from the triage table, the *audit drawer* or a *sampling run*. The *retained set* changes by exactly one *pièce*; the ranked order does not change; **the line** does not move; no other *pièce*'s membership changes.
- A pin requires a one-line reason and is recorded as an *override* (FR-25), because it contradicts a machine assertion.
- Pins survive re-ranking and carry to new *ranking versions*, marked as human-set, until explicitly removed. Removing a pin is itself a recorded, reversible act.
- The *retained set*, the *discarded set*, the review-effort estimate, the *sampling run* population and every *confidence bound* are computed **after** pins are applied, and the count of pins in force is stated wherever the sets are counted.
- A pin marks any existing *confidence bound* stale (FR-58), because it changed the population the draw was over.
- A user may pin only within her *RBAC scope*; a user who cannot move **the line** (FR-17) can still pin.

*(UJ-3's stated premise — Marc knows one pièce in the discarded set is the whole case — had no resolution in the requirements until this FR existed. Retaining that one document required dragging the line past the 400 above it, and recording, as a priced 400-*pièce* decision, what was actually a decision about one.)*

---

### 4.10 Reading, validating and handing back the work

**Description.** UJ-1 ends *"She reads the 180 pièces above the line over the weekend."* **Reading is the job**, and until this revision the entire coverage of it was one clause inside FR-11.

**Reading is the job above *the line*. Below it, supervising is the job.** The two halves of this product are not symmetric and the boundary between them is a design constraint rather than an accident. The *retained set* is read, *pièce* by *pièce*, with a *validation act* behind every acceptance (FR-45). The *discarded set* is **sampled** — because the product exists to automate the part the user told us lawyers hate (§2.1). Any requirement that asks for per-*pièce* verdicts *below* **the line** is spending the very thing the product is sold to save. FR-22 is the one requirement that does, deliberately and as the north star, which is why it is sized there and questioned at OQ-26. The product also produced no deliverable: it exported an *audit record* and never the working set, so the associate would re-key 180 references by hand to build her *bordereau* — which is the friction that gets a tool routed around. And "this document was read by a human" — one of the four claims v1 sold and never built — rested on a phrase, *validation act*, that no requirement created.

**This section is large.** A per-format viewer with passage highlighting is more implementation risk than several requirements that already have their own numbered section, and it is stated here rather than discovered in month four.

**Functional Requirements:**

#### FR-44: The *pièce* viewer

The lawyer can read a *pièce* inside the product. Realizes UJ-1, UJ-2, UJ-3.

**Consequences (testable):**
- Every format FR-3 extracts is **rendered**, not merely extracted: `.msg` with headers, body and reply chain, and navigation to and from each attachment as its own *pièce*; born-digital PDF; scanned PDF with its OCR text layer positioned over the page image; `.docx`; `.xlsx`; images. A format that cannot be rendered offers a download of the original and says so — it never shows an empty pane.
- From any *chunk* or *retained extract*, the viewer opens the source *pièce* **at the passage**, highlighted, for each of those formats. Asserted by test per format with a planted passage.
- A *pièce* larger than a configured rendering bound opens progressively or offers the original; it never blocks the interface and never exhausts the client.
- The viewer applies the *RBAC scope* pre-filter (FR-14): a *pièce* outside scope is not renderable, not downloadable, and its existence is not disclosed.
- Opening a *pièce* in the viewer is recorded in the *audit record*, and is the fact that distinguishes a *validation act* performed after reading from one performed from the list (FR-45).
- Rendering happens inside the *tenant* boundary. No *pièce* content is sent to any third-party rendering or conversion service, in any deployment.

#### FR-45: The *validation act*, and no undetectable bulk acceptance

"This document was read by a human" becomes a mechanism. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- A *validation act* is a **per-*pièce*** gesture available from the triage table, the viewer and the *audit drawer*, whose meaning is stated in the interface in the lawyer's language: *"I have read this pièce and I accept the tool's assessment of it."*
- It produces one *audit record* entry carrying: actor, timestamp, sequence number, *matter*, *pièce*, *ranking version*, the values accepted, and **whether the *pièce* was opened in the viewer before the act**. The last field is what distinguishes reading from clicking.
- **"Accepted as-is" exists only where a *validation act* occurred.** No default, no elapsed time, no scroll position, no screen visit produces it. Asserted by test: a *matter* left open for an arbitrary period and scrolled end to end yields zero accepted-as-is entries.
- **Bulk acceptance is permitted and is never undetectable.** A bulk *validation act* over a selected set: (a) requires an explicit confirmation naming the count; (b) produces one *audit record* entry **per *pièce***, each marked `bulk`, each carrying the size of the set and a shared batch identifier; (c) records for each *pièce* that it was **not** opened in the viewer, unless it was; and (d) is counted and reported separately in the *audit record* export and in §13's answer to question 5. A reader of the export can therefore always tell 180 individual judgements from one gesture over 1 400. *(A 1 700-row grid grows a select-all because every grid does. Forbidding it produces a workaround; leaving it unspecified produces 1 400 *pièces* marked "read by a human" in four minutes, which is documented consent that was never given.)*
- A *validation act* is reversible, and the reversal is a new entry rather than an erasure.

#### FR-46: Export of the *retained set*

The product hands back the working set. Realizes UJ-1.

**Consequences (testable):**
- The *retained set* of a *matter* is exportable, within the exporting user's *RBAC scope*, as an ordered, numbered list — one row per *pièce* — carrying at minimum: sequence number, *pièce* identity, title or filename, *pièce* date, *custodian*, label (FR-40), rank, confidence, the one-line justification, whether it was validated and by whom, and any *pin*. This is the basis from which a *bordereau de pièces* is built; the product does not claim to produce a court-ready *bordereau*, and says so.
- The order of the export is the order of the ranked set as adjusted by pins, and the export names the *ranking version*, the *case theory* version, the position of **the line** and the *RBAC scope* it was produced under.
- Superseded *pièces* (FR-4) are marked as superseded and the current version is named.
- The export is offered in a machine-readable form and in a form a lawyer can paste into a document. Producing it is recorded in the *audit record*, and it is the third egress path's second use (§11, FR-26).
- The export never contains material outside the exporting user's *RBAC scope*.

---

### 4.11 Security, continuity and recovery

**Description.** This section did not exist before 21 July 2026. The product is sold on *secret professionnel* — a **criminal** obligation in Luxembourg — §12 cites GDPR Art. 32 by name, and the document specified not one security measure: no encryption, no authentication requirement, no key management, no grant-time authorisation, no backup, no restore. That is not survivable in the first serious conversation with a *bâtonnier* or a firm's insurer.

**This is real work, not a procurement decision.** `addendum.md` §1.2 forbids the off-the-shelf options — Supabase Auth as the identity layer, Postgres row-level security as the RBAC implementation — because each makes on-premise installation impossible later. That forbidding is correct for portability, and its price is that identity, session handling and authorisation are hand-rolled application code, written by AI agents, reviewed by one non-hands-on person, where a mistake is silent and criminal. **This is the highest-risk code in the product and it is defended by tests alone.**

The product also **concentrates risk it did not previously carry**: an *ordonnance 145 CPC* or a *perquisition* at the firm now finds one indexed, searchable, deduplicated appliance instead of scattered mailboxes. That is stated in §18 R-14 rather than left unsaid.

**And security does not begin here.** This section was written as though it lived downstream of intake. It does not: the widest attack surface in the product is the *ingestion* gesture itself (§4.1), and everything below protects material FR-1 has already accepted, under a scope FR-1 has already stamped. A scope mislabelled at that boundary is enforced correctly and permanently against the wrong wall.

**Functional Requirements:**

#### FR-47: Encryption at rest and in transit

**Consequences (testable):**
- All *tenant* data at rest — original *pièces*, extracted text, *chunks*, embeddings, OCR images, the *audit record*, the *failure register*, configuration and exports staged for download — is encrypted, in a hosted deployment and in a single-machine installation alike.
- All network traffic carrying *tenant* data or credentials is encrypted in transit, including traffic between the application and its own stores in a multi-process installation.
- Encryption is a property of the application's storage adapters, not of a hosting provider's volume service, so that it holds identically on a firm's own machine (`addendum.md` §1).
- Asserted by test: an inspection of the raw stores for seeded unique tokens finds none in plaintext. This reuses the FR-31 seeded-token mechanism against a different target.
- A deployment started with encryption disabled or without a key fails to start. There is no permissive default and no warning-and-continue.

#### FR-48: Authentication and session handling

**Consequences (testable):**
- Identity, authentication and session handling are properties of the application (FR-29), and are not delegated to a hosting provider's identity service.
- Credentials are stored using a current password-hashing function with per-credential salt; no reversible storage exists. Enforced as a **structural property** (FR-56).
- Sessions have a configured absolute and idle lifetime, are invalidated on password change, on scope revocation (FR-14) and on explicit sign-out, and their identifiers are not guessable and not reusable.
- A configured lockout or rate limit applies to repeated authentication failure, and every failure and lockout is recorded in the *audit record*.
- Multi-factor authentication is supported and is *configuration-as-data* per *tenant*. `[ASSUMPTION: MFA is required to exist and its enforcement is a tenant policy decision. The sources specify no authentication requirement at all; a firm's insurer will.]`
- Single sign-on against a firm's own directory is **not** in scope for this increment (§5), and is named as a probable day-one requirement of a 30-lawyer firm rather than left as a surprise (OQ-22).

#### FR-49: Grant-time authorisation and *RBAC scope* administration

FR-14 specifies enforcement exhaustively and grant-time not at all. A Chinese wall anyone can widen is not a wall.

**Consequences (testable):**
- Creating an *RBAC scope*, granting one to a user, revoking one, and re-scoping a *matter* are **privileged acts**, each requiring an explicit administrative grant held by a named user of the *tenant*, each recorded in the *audit record* with actor, subject, scope, authority and timestamp, and each reversible.
- The administrative grant itself is granted by the same mechanism and its first holder is established at *tenant* provisioning (FR-50). There is no implicit superuser and no identity that bypasses FR-14; fail-closed applies to administrative and system identities alike.
- **A re-scope re-stamps.** Changing the *RBAC scope* of a *matter* propagates to every *chunk* of that *matter*, or invalidates the affected material until it is re-stamped, and the propagation is recorded as a single audited operation with its before and after counts. The material is never left with a stale stamp that the pre-filter then enforces correctly and permanently against the wrong wall. This is asserted by the mutating adversarial suite of FR-14, which the previous suite did not exercise.
- Every retrieval record (FR-14) is reviewable by a holder of the administrative grant, filtered by *matter* and by user, so that an insider-threat question has somewhere to be asked.

#### FR-50: The minimal configuration and provisioning surface

Resolves the contradiction between FR-30's editability and §5's absent admin cockpit.

**Consequences (testable):**
- A per-*tenant* surface exists through which every *configuration-as-data* value of FR-30 can be read and changed, and through which a *tenant*, its first administrative user, its *RBAC scopes* and its taxonomy are provisioned on first run. Without it, a correctly fail-closed installation is one in which nobody can see anything and nobody can grant access — at a site APX cannot see and reaches only by telephone.
- Every change made through it produces an *audit record* entry with actor, key, before value, after value and timestamp, and marks derived artefacts stale (FR-58).
- Every change is validated against the configuration's declared schema and defaults, and is reversible.
- It is **per-*tenant*, inside the *tenant*'s boundary, and never cross-*tenant***. It is not an operator console: no ticketing, no cross-*tenant* view, no APX-side access. That remains out of scope (§5).
- It is the **only** mechanism by which configuration changes: direct store editing is not a supported path, and a configuration value whose provenance is not an audited change through this surface is detectable as such.
- `[ASSUMPTION: the surface is the smallest thing that closes the contradiction — a settings screen and a provisioning step, not a cockpit. The sources declare configuration-as-data in scope and the operator interface out of scope, and never say who edits the data.]`

#### FR-51: Secret and key management

**Consequences (testable):**
- Model-provider credentials, embedder credentials, encryption keys and any other secret are held outside the application's own data stores, are never written to a log, a diagnostic, an export or an *audit record* entry, and are never displayed in the interface after entry.
- Every secret is rotatable without a redeployment and without re-indexing, and rotation is recorded in the *audit record*.
- Enforced as a **structural property** (FR-56): no secret value appears in source, in configuration committed to source, or in any example configuration. *(v1 named configuration keys in documentation that existed in zero source files; the inverse mistake — a secret in source — is the one that ends a client relationship.)*
- The *content-free projection* (FR-31) is asserted against seeded secret values as well as seeded content tokens.

#### FR-52: Backup, restore and disaster recovery

One machine, inside a firm, at the *design target*, with an append-only record of asserted legal weight, no telemetry, no ops staff and no SLA. A disk failure destroys the record the firm may need in front of a *bâtonnier*.

**Consequences (testable):**
- The product produces a **complete, restorable backup** of a *tenant* — original *pièces*, extracted text, index, *audit record*, *failure register*, configuration — on a configured schedule and on demand, encrypted, inside the *tenant* boundary.
- **Restore is exercised, not assumed**: a restore into an empty installation reproduces a *tenant* whose *denominator*, ranked orders, *audit record* sequence and *confidence bounds* are identical to the source. Asserted by test in CI at a reduced scale and by a documented procedure at the *design target*.
- Backup success or failure is a *worklist* line in the lawyer's language, and a *tenant* with no successful backup within a configured interval says so persistently on the home screen. A backup nobody knows failed is worse than none.
- The **storage footprint** of a *tenant* at the *design target* — originals, text, chunks, embeddings, OCR images, *ranking versions*, *audit record*, never deleted — is computed and stated by the product, so that a firm buying one machine can provision it. A pre-flight capacity check refuses an *import job* that cannot fit rather than discovering it at 70%.
- Recovery from a full disk is specified: writes to the append-only stores fail closed (FR-53), the *import job* halts with a *worklist* line, and no partial state is presented as complete.
- `[ASSUMPTION: this whole FR is an inference. Backup, restore and disaster recovery appear nowhere in any source document, and this is the single most likely way an installation ends a client relationship.]`

#### FR-53: *Audit record* continuity

An action whose record cannot be written must not succeed, and a record with a hole in it must say so.

**Consequences (testable):**
- **An action whose *audit record* entry cannot be written fails.** Moving **the line**, committing an *override*, completing a *sampling run*, performing a *validation act*, granting a scope and changing configuration are each atomic with their record: either both happen or neither does. Asserted by test with the audit store made read-only mid-action.
- Entries carry a **monotonic sequence number from a single authority and a chain value over the previous entry**, so that a gap, a reordering or a truncation is detectable by a reader holding only the export. A continuity check runs on export and its result appears on the export's face.
- The chain is verified on restore (FR-52) and a failed verification is surfaced, never silently repaired.
- Where the audit store cannot be written at all, the application refuses the affected actions rather than degrading to an unaudited mode. Read-only functions may continue.
- `[ASSUMPTION: sequencing and chaining are required. The sources require append-only and say nothing about detecting incompleteness; an action that succeeded while its record did not is, afterwards, indistinguishable from an action that never happened — and the gap is an absence, which §13's reader cannot see.]`

---

### 4.12 Corpus, evaluation and the fitness functions

**Description.** §8 describes a corpus and evaluation strategy with no requirement behind it, and the adversarial review named it **the item most likely to be quietly dropped** — invisible, unowned, no user-visible output, and identical in shape to the v1 defect it exists to prevent. v1 had a gold set and never once ran it. A strategy paragraph is exactly what v1 had.

The same argument applies to the offline fitness function: `addendum.md` §1.3 says *"run it as a check, not as a review question"*, and no check exists, while the development stack is Supabase, Vercel and Railway and every increment of AI-generated code is an opportunity to take a hosted-provider dependency that nothing would notice.

**Functional Requirements:**

#### FR-54: The corpus and *gold set* pipeline

**Consequences (testable):**
- The evaluation corpora of §8 are acquired, licence-cleared and assembled as **configured data sources entering through *ingestion*** (FR-33) — never as fixtures. Licence verification of the specific distribution used is an explicit, recorded step.
- The **degradation pipeline** is built and is itself part of the test surface: each mechanical degradation applied to real French public text is asserted against the *failure register* error class it must produce (a corrupted `.msg` → `corrupt-file`, a password-protected PDF → `password-protected`, an unopenable archive → `container-unopenable`, and so on). The degradation configuration and the expected classification are asserted together, or the *failure register* is untested.
- The *gold set*'s relevance judgments are **mapped onto this product's notion of relevance** — its *case theory*, its taxonomy and its notion of **the line** — and the mapping is written down, versioned and reviewable. It is not trivial and it is not assumed.
- **A merge gate:** no ranking or triage code is merged before SM-2 executes against the *gold set* in CI. The addendum's sequencing already believes this; this consequence enforces it.
- The pipeline runs at the *design target*, not extrapolated from a smaller run, and the *denominator* is verified against it (SM-3).
- **This is a product-sized build with no user-visible output.** It is stated as such, it has a numbered requirement so that dropping it is a visible decision rather than an omission, and R-2 remains High regardless.

#### FR-55: The offline fitness function, executed in CI

*"Can this run, unmodified, on a single machine inside a law firm with no internet connection?"*

**Consequences (testable):**
- A CI job boots the application in a **network-isolated container**, with no hosted-provider service reachable and no outbound network except a stubbed model-provider endpoint, and asserts that it: starts; ingests a folder; indexes it; retrieves over both engines; ranks; places **the line**; produces an *audit record*; and exports. A failure fails the build.
- The job runs from the first week of the build, not before the first installation. The gap between "we intend to keep it portable" and "it is portable" is measured in weeks of discovery, and it is otherwise discovered in front of the first client with SM-10 on the line.
- Which capabilities **do not** survive the model provider's absence is enumerated by this job rather than described: the ranking, the justifications, the priced statement. The *confidence bound* sentence is regenerable from the *audit record* **without** a model call — a statistical statement must never depend on a network call — and this is asserted here. *(§14's "degrade loudly" is otherwise satisfied by a product that does nothing.)*
- `[ASSUMPTION: the confidence bound sentence must be renderable offline from the record. FR-36 makes machine-generated user-facing text model-produced, which would make a statistical claim network-dependent; templated, translated, locally rendered text is the reading that keeps SM-1's self-sufficiency true.]`

#### FR-56: Structural properties, enforced in CI

Where this document asserts that no code path does something, that assertion is a static check over the source, not a runtime test.

**Consequences (testable):**
- A named set of **structural properties** is enforced by static checks in CI — grep, lint, import-graph or architecture rules — and a violation fails the build. The set includes at minimum: no fallback embedder (FR-9); destructive index operations reachable from one entry point only (FR-10); no post-filter in retrieval (FR-14); one write boundary for *chunks* with a required scope argument (FR-8); no *tenant*-specific identifier or name in source (FR-30); no runtime import from the test tree and no fixture path (FR-33); no natural-language string used as a translation key (FR-34); no hard-coded locale (FR-35); no outbound call site outside the enumerated adapters (FR-32); no reversible credential storage (FR-48); no secret in source (FR-51); no model-reported confidence field consumed (FR-42); and no banned *confidence bound* phrasing in any locale's string set (FR-23).
- Each property names the check that enforces it and the file or pattern it inspects. A property with no check is not a property.
- **Where a claim cannot be decided by a check or a test, this document says which verb applies**: *asserted by test* (a CI test decides it), *enforced as a structural property* (a static check decides it), or *asserted by review* (a human decides it against a checklist). The third is used for FR-27's phrasing rule, FR-41's justification quality and §9's usability rules, and none of them is counted as a passing test. *(With the test suite standing in for the engineers who are not on the team, an inflated claim about what the suite proves is the most dangerous inaccuracy this document can contain after §0.2.)*
- The registry of user-reachable actions that FR-21's probe sweeps is itself a structural property: an action not in the registry fails the build.

---

### 4.13 Inventory arithmetic and freshness

**Description.** Two properties the rest of the document depends on and neither of which was well-defined: what the *denominator* counts, and when a derived artefact stops being true.

**Functional Requirements:**

#### FR-57: Container expansion and the unit of the *denominator*

**Consequences (testable):**
- **Containers are expanded**: archives (`.zip`, `.7z` and the configured list), PDF portfolios, mailbox exports, and `.msg` nested inside `.msg`. Members become *pièces* carrying provenance through the container and inheriting its *custodian*. Asserted by test with a container three levels deep.
- Recursion depth and total expansion ratio are **bounded by configuration**. A container exceeding either is entered in the *failure register* with class `container-unopenable` and the reason, rather than exhausting the worker. A zip bomb is a register entry, not an outage.
- **A container that cannot be opened is one entry standing for an unknown number of *pièces***, and it carries cardinality `unknown`. Every *denominator* displaying such an entry, and every absence claim qualified by the register (FR-13), states the unknown explicitly — *"1 archive unopened, contents unknown"* — never "· 1 not indexed". *(Otherwise a `.zip` of 500 *pièces* reads as one missing file, and the register understates itself by 499, which defeats the exact purpose the Glossary gives it.)*
- **The unit of the inventory guarantee is the *pièce*, counted after expansion**, and the *submitted* count is frozen at the completion of enumeration-and-expansion rather than at folder selection. Where expansion is still in progress the *denominator* declares itself provisional. *(Previously *submitted* counted files while *indexed* counted *pièces*; an email with three attachments made indexed exceed submitted by three, and SM-3 — "a single violation is a release blocker" — would have failed on the first real `.msg` corpus or been rewritten against a unit somebody invented.)*
- The completion summary reports expansion explicitly: files selected, *pièces* after expansion, containers expanded, containers unopened with unknown contents.
- The *design target* is 100 000 ***pièces***, post-expansion (§3, *Design target*).

#### FR-58: Freshness and staleness of derived artefacts

**Consequences (testable):**
- A derived artefact — a ranked order, a position of **the line**, a review-effort estimate, a *confidence bound*, an *exhaustive* result set — is marked **stale** when any of its inputs changes. The complete trigger list: a new *ranking version*; a move of **the line**; a *pin* added or removed; a *case theory* revision; a configuration change affecting retrieval, ranking or the estimator; an *RBAC scope* change affecting the population; **and any ingestion into the *matter***.
- **Ingestion is a staleness trigger.** *Pièces* ingested into a *matter* that already has a ranking are in neither the *retained set* nor the *discarded set* — a third state FR-16 does not admit — so ingestion into a ranked *matter* marks the ranking stale, marks any *confidence bound* stale, generates a *worklist* line offering a re-rank, and states the count of unranked *pièces* wherever the sets are counted. *(Previously staleness was triggered only by a line move or a superseded ranking version. 300 *pièces* could arrive, the sentence on screen would still read "1 400 in the discarded set", it would not be marked stale, and it would remain exportable as current — the north-star artefact, false, asserted as fresh.)*
- **A stale *confidence bound* cannot be exported as current**, cannot be copied as text without its staleness in the copied string, and is visually distinct wherever it appears.
- Staleness is never resolved by the passage of time, by a background recomputation or by being viewed. It is resolved by an explicit user-initiated recomputation, which produces a new artefact rather than refreshing the old one.
- Asserted by test for each trigger in the list: perform the trigger, assert the artefact is stale, assert the export refuses it as current, assert the *worklist* line exists.

---

### 4.14 Ease of use, as a gate rather than an adjective

**Description.** Of the three promises in §1, this is the one v1 skipped most quietly and the one this document carries worst. It cannot be a feature: "ease of use for a non-technical collaborator" is a property of everything, which is how it becomes the property of nothing. What *can* be built is a **gate** — a small number of checkable rules, run before a release, over surfaces that already exist, with recorded verdicts. That is what this section is, and it is deliberately modest. **It does not make the product easy to use. It makes the claim falsifiable**, which is the whole difference between a promise and an adjective, and §7 states what it still does not measure.

Adoption is voluntary in practice. A partner cannot make an associate use a tool that adds friction — she routes around it, and nobody reports that she has.

**Functional Requirements:**

#### FR-59: The usability gate — a checklist, a keyboard and one token set

The three rules this document already asserts about the user-facing surface become one gate with a recorded result. Realizes UJ-1, UJ-3.

**Consequences (testable):**
- **The phrasing checklist is a versioned artefact, not a habit.** It states what FR-27 and §9 assert: no technical vocabulary, no component name, no error code as primary text, no job identifier, no untranslated string, an action and its object on every line, and a plain reading of what the surface is asking the user to decide. **Every user-facing surface** — every *worklist* line type, every *failure register* error class, the completion summary, the priced statement, the *confidence bound* sentence, the *audit drawer*, the viewer's controls, the *matters* zone and the face of every export — is reviewed against it before a release candidate ships, and **each item's verdict is recorded with its reviewer and date** (SM-20).
- **A failed item blocks the release candidate**, or is recorded as an accepted exception with a reason in the same register. An unrecorded verdict counts as a failure. *(This is* asserted by review *— the third verb of FR-56 — and it is never counted as a passing test. Its value is that the review happened, is dated and is arguable; not that it proves anything.)*
- **Every *worklist* action and every triage-table edit is reachable and completable by keyboard alone.** Asserted by test. No WCAG level is claimed (§9).
- **One token set.** No colour, spacing or type value appears outside it. Enforced as a *structural property* (FR-56). *(v1 shipped three unreconciled colour systems and around twenty hard-coded values, which is what made per-*tenant* configuration unbuildable — and the shipped v1 application and its mockups shared almost no visual DNA, while this increment's single most reusable asset is a mockup, `addendum.md` §5. Fidelity to it is asserted by review under this FR, because no check decides it.)*
- **The surfaces a non-technical user needs in order to be self-sufficient exist and are reachable**: FR-50's configuration and provisioning surface, FR-5's retry and credential-supply actions, FR-27's click-through to somewhere the action can actually be performed. A *worklist* line whose only resolution is a telephone call to APX is a defect of this FR as much as of FR-5.
- `[ASSUMPTION: a recorded review gate is the strongest available answer to "ease of use" in an increment with no user. The sources name ease of use for non-technical collaborators as one of the three promises and specify no mechanism; a checklist with dated verdicts is falsifiable and an adjective is not. Whether the product is in fact usable is decided by SM-10, which has no date.]`

---

## 5. Non-Goals (Explicit)

- **Syllogisme drafting is not in this increment.** No drafting surface, no per-section skeleton (EN FAIT / EN DROIT / PAR CES MOTIFS), no per-block diff acceptance, no `.docx` export on a firm template, no style profile and no statistical style fingerprint. They move to the next increment on this same spine — **and the *blind two-document test* moves with them.** That test — can a reader tell the tool's draft from the firm's own, shown both blind — remains the north star for Syllogisme and was the user's own non-negotiable acceptance criterion. It is recorded here because the two things this increment defers, the style profile and the statistical fingerprint, are the *measurement apparatus* for it: deferring the apparatus while losing the criterion is how a non-negotiable becomes an oversight, and the next increment's PRD will be written from this one. The *content-free projection* underneath the style extractor (FR-31) **is** built here, and is built open for that reason.
- **No deontological documentation pack, and no firm-level answer for the *bâtonnier* or the insurer.** FR-26 exports a per-*matter* audit record — evidence about one *matter*, not the product-level dossier the partner's second job asks for (§2.1). The material exists inside the build; the dossier is a document APX writes rather than a feature the product ships, which is exactly why it disappears. **Liability** — what APX warrants, and what it excludes, when a triage run misses the *pièce* that decides a case — is likewise addressed nowhere in this document or its inputs. Both are components of the service wrapper the competitive analysis calls the actual value (§6.3), and both are named here rather than left implied: OQ-27.
- **The citation checker is not in this increment.** Tier (a) verification against Judilibre and Légifrance belongs with drafting. The exact-containment primitive (FR-11) is built now; the checker that consumes it is not.
- **This is not a legal research tool** and must never present itself as one. Retrieval is over the *tenant*'s own *corpus*. APX cannot compete on corpus depth against publishers with two centuries of doctrine, and pretending otherwise is a losing fight fought on the opponent's ground.
- **No *veille* module** in this increment.
- **No admin cockpit.** No operator console, no ticketing, no cross-*tenant* view, no APX-side access. The minimal per-*tenant* configuration and provisioning surface of **FR-50 is in scope**, because a *tenant* that cannot be provisioned and a scope that cannot be granted make the first installation impossible; that surface is not the cockpit. *(This resolves a contradiction the document carried until 21 July 2026: FR-30 required configuration to be editable and §5 removed the surface that would edit it.)*
- **No single sign-on and no external identity provider.** Identity is a property of the application (FR-29, FR-48). This is very likely a day-one requirement of a 30-lawyer firm with a directory, and it is deferred rather than solved — OQ-22.
- **No bidding a *matter* before its documents arrive.** FR-39 emits a review-effort estimate after ingestion and ranking. A pre-ingestion estimate — the partner's stated job in §2.1 and the revenue thesis — is not in this increment.
- **No court-ready *bordereau de pièces*.** FR-46 exports the *retained set* as the ordered, numbered basis from which one is built. The document a court receives is the lawyer's.
- **No feedback path from human corrections back into the ranking.** FR-20 correctly forbids automatic regeneration on edit, and this increment provides no user-initiated learning either: Marc corrects fifty misclassifications and the remaining 1 650 keep the same basis. This is a deliberate choice, stated so it is not mistaken for an oversight — OQ-24.
- **No legal hold or sealing of a *matter*.** Nothing freezes a *matter* against further ranking once litigation is live, so FR-16 can produce a new *ranking version* underneath a bound already quoted to a court. Named, not solved — OQ-23.
- **No shared SaaS hosting** as a product offering.
- **No fine-tuning on client data**, ever. Inherited and not up for debate.
- **No live connectors** to practice-management systems, mail servers or document management systems. Onboarding is a folder.
- **No fully local model** *as a planned deliverable of this increment* — but see §9 and OQ-20: the per-*pièce* LLM judgement of FR-38 sends the substance of a *matter* to the model provider as the product's normal operation, and a *bâtonnier* applying the CNB criteria may treat that as disqualifying. A local model may therefore turn out to be **necessary rather than premium**, and that is now an open question rather than a settled tier.
- **No auto-update delivery mechanism.** Signed, offline-installable, reversible migrations against a live 100 000-*pièce* index is the genuinely unsolved problem; it is deferred, not solved (§16).
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

- The *case theory*, the *relevance judgement* cascade, the ranked order and the *ranking version* (FR-37…FR-39).
- Per-*pièce* labelling against the *tenant*'s taxonomy (FR-40).
- One ranked order with nothing deleted and nothing categorised (FR-16).
- **The line**, drawn by the tool and movable by the user, priced before it moves (FR-17, FR-19); and the *pin*, which moves one *pièce* across it (FR-43).
- Per-*pièce* confidence, derived rather than self-reported, and a one-line justification derived from named extracts (FR-18, FR-41, FR-42).
- The editable cell-by-cell table with a live *change log* and no destructive regeneration (FR-20).
- Random sampling over the *discarded set* with a *confidence bound* (FR-22, FR-23).
- The *audit drawer* and its export (FR-26).
- The home screen: the *worklist* with the permanent *denominator*, and the *matters* zone beneath it (FR-27, FR-28, FR-60).

**Reading and handing back the work:** the *pièce* viewer (FR-44), the *validation act* (FR-45), the retained-set export (FR-46).

**Security, continuity and recovery:** FR-47…FR-53. Entirely new, entirely unbudgeted before this revision, and not optional for a product sold on a criminal confidentiality obligation.

**Corpus, evaluation and fitness functions:** FR-54…FR-56, with the merge gate that stops ranking code shipping before the *gold set* runs.

**Inventory arithmetic and freshness:** FR-57, FR-58.

**Ease of use, gated rather than asserted:** FR-59 — the phrasing checklist with recorded verdicts, keyboard reachability, one token set.

**Design target: 100 000 *pièces* after container expansion.** Every scale-sensitive consequence above is asserted at that target, not at demo scale.

### 6.2 Out of scope for MVP

- **Syllogisme drafting, the style profile, the statistical fingerprint and `.docx` export** — next increment, same spine. `[NOTE FOR PM]` This is the deepest vertical slice and the thing the original plan was built around; the reversal was made on commercial and competitive evidence and the depth-forcing property is genuinely lost. Revisit sequencing if the first engagement is a drafting engagement.
- **The citation checker (all tiers)** — next increment.
- ***Veille*** — a separate module, later.
- **Admin cockpit** — nothing to operate yet. The minimal provisioning and configuration surface (FR-50) is **in** scope; the operator console is not.
- **Single sign-on / external identity providers** — FR-48 owns identity. OQ-22.
- **Pre-ingestion matter pricing, court-ready *bordereau*, correction feedback into the ranking, legal hold** — see §5; each is named, none is solved.
- **The deontological dossier for the *bâtonnier* and the insurer, and any stated liability position** — see §5 and OQ-27. Two of the four components of the service wrapper §6.3 calls the actual value, and neither is engineering.
- **Shared SaaS hosting** — packaging decision, not a first-increment feature.
- **Auto-update delivery / on-premise update mechanism** — deferred, not solved (§16). `[NOTE FOR PM]` Deferring this is correct for one installation and compounds badly from the second: version drift across blind installations is unrecoverable if it is allowed to start.
- **Fully local model** — **not** a premium tier any more: §5, §9 and OQ-20 escalate it to *possibly necessary*, because FR-38 sends the substance of a *matter* to a hosted provider as normal operation. Out of scope here either way; open as a question, not settled as a tier.
- **Fine-tuning** — never.
- **Live connectors** — folder ingestion is the whole onboarding story.
- **Italian localisation** — see OQ-3. The i18n mechanism (FR-34…FR-36) is built so that adding a language is data, not a project.
- **The fixture layer** — deleted (FR-33).

---

### 6.3 The cut line, if capacity binds

`[NOTE FOR PM]` **The in-scope list above is 60 functional requirements for one non-hands-on CTO plus AI agents, and it is larger than one person can comfortably build.** R-1 has said "High and accepted" since the first draft with the note *"no mitigation makes the list smaller"* — which is a statement that the risk is unmanaged, not a mitigation. This document tells lawyers that a ranking which refuses to decide pushes the work back onto the person paying to avoid it. It should not do the same to its own reader.

**The minimum that is still a product**, in the sequence of `addendum.md` §3.3: the *payload schema* (FR-8); *ingestion* with the *failure register*, the inventory guarantee and container expansion (FR-1…FR-7, FR-57); the index that fails loudly and never self-deletes (FR-9…FR-11); retrieval with *truth status* and the *RBAC* pre-filter (FR-12…FR-15); the relevance cascade and the ranked order (FR-37…FR-39); **the line** (FR-16, FR-17); the viewer and the retained-set export (FR-44, FR-46); the *audit record* with continuity (FR-24, FR-25, FR-53); the security baseline (FR-47…FR-52); tenancy, configuration and provisioning (FR-29, FR-30, FR-50); the *worklist* and *denominator* (FR-27, FR-28); the corpus pipeline and the fitness functions (FR-54…FR-56).

**The criterion this cut order was derived without.** The competitive judgement the whole programme rests on is that **the value is the service wrapper, not the model**: the CCBE published the recipe and priced the hardware publicly, so any technically-minded partner — or their nephew — can price a DIY alternative, and what a firm cannot assemble that way is *verification against public sources, deontological documentation, maintenance and liability*. A consultancy competes on service depth and proximity, or not at all. **This document is 60 requirements of product.** Of the four wrapper components: **maintenance is in scope** (FR-31, FR-32, §17); **verification against Judilibre and Légifrance is deferred** (§5); **the deontological dossier is a document nobody owns** (§5, OQ-27); **liability is unaddressed anywhere** (OQ-27).

The consequence for the order below is uncomfortable and is stated rather than smoothed: **cut #2 removes the only wrapper component that is in scope.** The order is derived purely from internal dependency — what breaks what — and by that criterion cut #2 is right. By the wrapper criterion it is the last thing that should go, because at the first installation the diagnostic export is the only support channel that exists and its absence is undetectable until then. Both readings are recorded. Whoever holds the capacity decides, knowing that the cheapest cut and the most damaging cut are the same item.

**What falls out first, in order, and what it costs:**

1. **FR-11's exact-containment primitive as a general facility** — keep only the narrow use FR-41 needs. *(Cost: the drafting increment rebuilds it. Was previously justified by cheapness alone, which is "it's just tokens" in plain sight.)*
2. **FR-31, FR-32 — the *content-free projection* and the diagnostic export.** *(Cost: when an installation exists, this is the only support channel there is. Its absence is undetectable until then, which is exactly why it will go.)*
3. **FR-13 — deterministic exhaustive search.** *(Cost: the product loses the only mechanism that can support an absence claim. Ask honestly whether the sceptic is carried by the sampling story alone in a first increment; the answer may be yes.)*
4. **FR-19 and FR-23's numbers** — ship the sampling ritual and report counts only. *(Cost: the north star becomes a weaker sentence. Already the fallback if OQ-4 goes unanswered.)*
5. **FR-34…FR-36 beyond key-set parity** — locale collation, source-language statements, locale-switched model assertions. *(Cost: exactly the decay v1 suffered, protected by the same mechanism — care — that failed the first time. Say so before dropping it.)*
6. **FR-60's *matters* zone** — the home screen falls back to the *worklist* alone. *(Cost: the user has no answer to "where are my matters?" and navigates by memory. Small, and the pressure it creates is to add matter progress as worklist lines, which is the log FR-27 exists to prevent — so cut the zone or keep the rule, never both.)*

**What must not be cut, whatever happens:** FR-54 (the corpus and *gold set* pipeline). It is invisible, it has no user-visible output, it is the item the adversarial review predicted would be dropped, and dropping it **is** the v1 defect — a gold set that exists and never runs.

**Sequencing gate:** no triage-layer work (`addendum.md` §3.3 step 5, i.e. §4.4 and §4.9 here) begins until either one real anonymised *matter* is in hand or its absence is explicitly re-accepted, in writing, with a date. That is one sentence, and it is the only structural defence in this document against the drift that produced v1 (R-2, OQ-17).

---

## 7. Success Metrics

*Each metric cross-references the FRs it validates. Counter-metrics are as load-bearing as the primary metrics: they prevent the build from optimising the wrong thing.*

### Primary

- **SM-1 (north star) — the sayable sentence, and its soundness.** For every *matter* where triage has run and a *sampling run* has completed, the system produces the *confidence bound* as a sentence a lawyer can say to a client or a judge. **Two targets, and the second is the one that was missing:**
  - **Reproducibility — 100%.** Every number is reconstructible from the exported *audit record* alone, asserted by an automated test that recomputes from the export in a process with no access to the application's stores.
  - **Soundness — asserted, not assumed.** The bound is a **prevalence** bound, computed by the hypergeometric estimator, stating its confidence level, its *RBAC scope*, its *ranking version* and its *case theory* version. A property-based test asserts the estimator against known populations: for a discarded set of known composition, the stated bound covers the true prevalence at the stated confidence level over repeated simulated draws, and the emitted wording contains none of the banned phrasings (FR-23, FR-56).

  *A test that recomputes a wrong number and gets the same wrong number passes. Reproducibility was the whole of SM-1 until 21 July 2026, and it is exactly the v1 pattern in a new costume: a green test proving a mechanism ran, standing in for a proof that the mechanism is right (§0.2).* Validates FR-22, FR-23, FR-24, FR-26.

- **SM-2 — recall against the *gold set*, executed in CI.** Recall at **the line** is measured against a *gold set* with human relevance judgments on every CI run, and the figure is recorded. **No absolute target is set in this PRD** — the source documents state none, and inventing one would be exactly the unaudited number §5 forbids. See OQ-5. Two fixes to the ratchet:
  - **The ratchet has a floor.** A recall floor is set from the **first measured baseline** and, once set, may only rise. Without a floor, whatever the first measured figure happens to be becomes permanently acceptable, permanently defended by a green build and permanently unarguable.
  - **The ratchet is significance-tested.** Recall over a *gold set* varies run to run with any nondeterminism in the cascade. A run fails the build when it is below the recorded figure **by more than the measured run-to-run variance**, not on any decrease. A strict rule on a noisy measure produces flaky builds, and flaky builds get disabled — which is how a gold set stops running for the second time.

  Validates FR-16, FR-17, FR-18, FR-37…FR-39, FR-54 and §8. *v1 had a gold set and never once ran it; the metric that matters most is that it runs at all.*

- **SM-3 — the inventory guarantee holds.** `submitted = in corpus + open failure register entries`, counted in *pièces* after container expansion (FR-57), exactly, for 100% of *import jobs*, asserted after every job and every retry, at the *design target*. **Target: zero violations, ever.** A single violation is a release blocker, not a bug. Validates FR-5, FR-6, FR-57.

### Secondary

- **SM-4 — idempotency.** Re-importing an identical folder changes the *corpus* count by zero and modifies zero existing *pièces*. **Target: exact.** Validates FR-4.
- **SM-5 — loud failure.** Under injected faults (embedder unavailable, dimension mismatch, corrupt file, OCR failure, **model provider rate-limiting or unavailable mid-ranking**, **audit store read-only**, **disk full**), the number of silently degraded outcomes is **zero**: every fault produces a *failure register* entry, a halt or a refused action, plus a *worklist* line — never a *chunk*, never an imputed score, and never a completed action whose record was not written. Validates FR-9, FR-10, FR-38, FR-53.
- **SM-6 — isolation.** The adversarial *RBAC scope* and *tenant* suite returns **zero** out-of-scope results, counts, snippets or metadata across every retrieval, export and diagnostic surface. **Target: zero. Any non-zero is a professional-conduct incident, not a defect.** Validates FR-14, FR-29, FR-31.
- **SM-7 — content-freedom.** The seeded-token test over the *content-free projection* finds **zero** *tenant* tokens in any emitted output. Validates FR-31, FR-32.
- **SM-8 — the tool commits, and refuses when it should.** Two figures over the evaluation corpus: the proportion of triaged *matters* where **the line** was placed by the system with a stated basis (**target 100%**, counting explicit refusals as satisfying it), **and** the proportion of deliberately constructed refusal cases — a *matter* below the size floor, one with no score dispersion, one with too many unscored *pièces* — where the system does refuse (**target 100%**). *(The first figure alone is satisfied by an implementation that never refuses and by one that always does; the second is what makes it mean anything.)* Validates FR-17, FR-39.
- **SM-9 — edits survive.** In a scripted session of ≥20 cell edits interleaved with a re-ranking, **zero** edits are lost or overwritten. Validates FR-20.
- **SM-10 — installed, not demoed.** The increment is installed and running at a real firm on their own documents. This is a binary and it is the only success metric that is not measurable in CI. **A build satisfying every other metric in this section is a build with no user**, which is the drift that produced v1; §6.3's sequencing gate is the only structural defence. `[ASSUMPTION: no date is attached to this metric; no engagement exists to attach one to.]`

- **SM-11 — the retained set is a selection, not a copy of the corpus.** The proportion of a *matter*'s *pièces* above the **system-placed** line, and the review-effort estimate derived from it (FR-39), recorded per *matter* on every evaluation run. **This is the metric that opposes recall and it did not exist before 21 July 2026.** Without it the metric suite has a degenerate optimum: place **the line** at the very bottom and SM-2 reaches 100% recall, SM-C1 reaches zero, SM-8 is satisfied, SM-3…SM-7 are unaffected, and the product has done no triage at all — a position UJ-4's edge case explicitly permits and instructs the tool not to object to. **The rule: SM-11 may be traded against SM-2 and may never be traded against SM-C1.** No absolute target; the figure is recorded from the first measured baseline and its movement is the signal. Validates FR-17, FR-39.

- **SM-12 — the *payload schema* holds at the write boundary.** Zero *chunks* written with a missing, defaulted or inherited mandatory field, over the whole evaluation corpus at the *design target*; every rejected write appears in the *failure register*; every migration that would lose a mandatory field is rejected rather than run. **Target: zero violations.** *(FR-8 is the only irreversible decision in the system and R-3 rates it the highest-consequence risk; until this revision no metric could fail on it.)* Validates FR-8.

- **SM-13 — proving and finding stay apart.** Three figures, all with a target of exact: planted-match recall for exhaustive search is 100% and planted non-matches returned is zero, including accented, hyphenated, elided and OCR-degraded plants; **zero** result sets are emitted or exported without a *truth status*; **zero** result sets carry *truth status* `exhaustive` without their full qualification set (scoped denominator, open register count, unknown-cardinality count, OCR figures). Validates FR-12, FR-13, FR-15.

- **SM-14 — internationalisation does not decay.** Key-set parity across all supported languages holds; zero natural-language strings used as keys; zero hard-coded locales; every route has translated strings; and machine-generated user-facing text is asserted to be produced in the active language with the locale switched. **Target: zero violations, build-failing.** *(v1's i18n is described in this document as fatal for a Luxembourg deployment, and had no metric.)* Validates FR-34, FR-35, FR-36.

- **SM-15 — the security baseline is present, not intended.** Zero seeded tokens or secrets found in plaintext in any store; zero reversible credential storage; a restore from backup reproduces a *tenant* identically; the *audit record* continuity chain verifies; and a deployment started without encryption or a key fails to start. **Target: zero violations. Any non-zero is a release blocker.** Validates FR-47…FR-53.

- **SM-16 — the ranking is reproducible.** Re-running a fixed *ranking version* over a fixed *corpus* reproduces the same order, *pièce* for *pièce*, including tie-break, on a different machine and after a restart. **Target: exact.** Validates FR-38, FR-39.

- **SM-17 — the numbers are calibrated, not merely produced.** Two figures against the *gold set*: the **projected prevalence** of FR-19 compared with the realised prevalence at the same line positions, and the **derived per-*pièce* confidence** of FR-42 compared with the observed relevant share within each confidence band. **A systematically optimistic projection, or a systematically overconfident confidence, fails the build.** *(An uncalibrated projected figure recorded permanently in the audit record as the basis of a decision is the single most dangerous artefact this product can emit.)* Validates FR-19, FR-42.

- **SM-18 — the cost of the judgement is visible.** Per evaluation run, recorded: the share of *pièces* reaching stage 3 of the FR-38 cascade, the number of model calls, the volume of *tenant* text egressed to the model provider, and the wall-clock time to first *ranking version*. **No target; the figures are the input to OQ-2 and OQ-20 and a build that stops recording them has hidden the increment's largest cost and its largest egress.** Validates FR-38, and §9's egress and cost bullets.

- **SM-19 — every *pièce* carries a label, and the unlabelled share is visible.** Three figures over every evaluation run: **zero** *pièces* in a ranking without exactly one label from the *tenant*'s taxonomy or the explicit `unlabelled` value; the `unlabelled` share, recorded per *matter* and per run; and **zero** labels silently remapped when the taxonomy changes. **Target: zero on the first and third. The second has no target and its movement is the signal.** *This measures that labelling happens and that it is honest about itself. It does not measure whether a label is right* — see "What has no metric" below, and OQ-16. Validates FR-40.

- **SM-20 — the ease-of-use gate is executed, and its verdicts are recorded.** Three figures per release candidate: every user-facing surface reviewed against FR-59's phrasing checklist with a recorded verdict per item (**target: 100% of surfaces, zero unrecorded verdicts**); every *worklist* action and every triage-table edit completable by keyboard alone (**target: exact, asserted by test**); and zero colour, spacing or type values outside the token set (**target: zero, enforced as a structural property**). *This metric measures that the gate ran and what it found. It does not measure whether the product is easy to use — nothing in this section does, and the closing paragraphs say so.* Validates FR-59, FR-27, and §9's usability and visual-consistency rules.

### Counter-metrics (do not optimise)

- **SM-C1 — relevant *pièces* below **the line**.** The count of *gold set* relevant *pièces* falling in the *discarded set*. **This number may never rise.** *Correction, 21 July 2026: this was previously described as counterbalancing SM-2, which it cannot — for a fixed gold set, "relevant pièces below the line may never rise" and "recall at the line may never fall" are the same assertion in two units. It is a restatement of SM-2 in the unit a lawyer thinks in, and it is kept for that reason and not as a counterweight.* **The metric that genuinely opposes recall is SM-11.** Restates SM-2; validates FR-16, FR-17.
- **SM-C2 — *worklist* dismissal and *override* reason quality.** Two figures, tracked together: the proportion of *worklist* lines closed without the underlying action being performed, and the proportion of *override* reasons that are duplicates of an earlier reason in the same session or below a minimum meaningful length. **A rise in either means the audit surface has become noise the user has learned to dismiss** — the precise failure mode of every compliance feature ever shipped. Counterbalances FR-25, FR-27 and the whole of §4.5. `[ASSUMPTION: no thresholds are set; these are trend metrics whose direction is the signal. See OQ-9 and the observation protocol below.]`
- **SM-C3 — abandoned and invalidated *sampling runs*.** The proportion of runs started and not completed, and the proportion invalidated in flight by ingestion, re-ranking or a line move (FR-22). A high first figure means the ritual is too expensive and the *confidence bound* is theatre; a high second means the product is wasting senior lawyers' hours. Counterbalances SM-1.
- **SM-C4 — time to first useful screen.** If **the line** is placed only after the entire *import job* completes, an import at the *design target* gives the lawyer nothing for the duration. Optimising SM-3 and FR-6 must not push the user's first useful moment to the end of the job. Its mechanism — ranking over a partially ingested *corpus* — is permitted but unspecified (FR-38, OQ-7), so this remains a design constraint rather than a build-failing metric, and is listed as such. `[ASSUMPTION: partial triage over a partially ingested corpus is desirable but is not specified as an FR; it interacts with the inventory guarantee in a way the sources do not address. See OQ-7.]`

**How SM-C2, SM-C3 and SM-C4 are observed, given there is no telemetry and never will be.** They are behavioural trend metrics over real usage, §5 forbids telemetry permanently, and OQ-9 concedes they are otherwise unobservable — so as listed they would be counter-metrics that cannot counter anything, guarding exactly the mechanisms R-6 rates most likely to rot. **The observation protocol, stated rather than assumed:** structured evaluation sessions on a defined schedule with real practitioners, plus whatever a *tenant* chooses to push through FR-32, plus — for SM-C2's *override*-reason figure and SM-C3 — computation **inside the installation** and inclusion in the *content-free projection* as counts, which is content-free by construction and requires no telemetry. Where a figure cannot be obtained by any of the three, it is recorded as unobserved rather than reported as good.

**What has no metric, said plainly.** Justification quality (FR-41) is assessed by review only; *worklist* phrasing (FR-27) is assessed by review only, now against a recorded checklist (FR-59, SM-20) which measures that the review happened and not whether the phrasing is good; "self-diagnosing" (§17) has no acceptance criterion. **And label accuracy (FR-40) has none.** SM-19 measures that a label was applied, that it came from the taxonomy and that nothing was silently remapped; no *gold set* available to this increment carries judgements in a French firm's triage taxonomy, so one half of what the Glossary defines *Triage* to be ships measured and the other half ships merely counted. The consequence lands on OQ-16: whether v1's nine-label taxonomy is right for *ordonnance 145 CPC* review cannot be answered empirically here, only by a practitioner's reading.

**And the asymmetry among the three promises, stated rather than left to be noticed.** §1 names what a firm actually buys: security, ease of use, volume. **Security has FR-47…FR-53, SM-6, SM-15 and three risk rows. Volume has FR-2, FR-57, SM-3 and the *design target* asserted at every scale-sensitive consequence in §4. Ease of use has FR-59, SM-20, one keyboard requirement and a checklist a human reads.** That is not an even distribution. It is the exact shape of the v1 failure this document exists to prevent — v1 skipped all three promises, and the one it skipped most quietly was the second, which is also the one no test can reach. The gap is not closed here and this revision does not pretend it is: establishing that a non-technical lawyer can use this product requires a non-technical lawyer using it, which is SM-10, which has no date because no engagement exists. What has changed is that the asymmetry is written down instead of being visible only to someone counting requirements.

---

## 8. Corpus and Evaluation Strategy

*Invented section. It exists because with no client and no client corpus, the corpus is the first real engineering problem of this increment rather than an afterthought — and because v1's central defect was manufacturing its own data. Source: brief `addendum.md` §2. **The named sources live in this PRD's companion `addendum.md` §2, which is the authoritative copy**; this section holds the strategy and the requirements it imposes, and the table below is a summary of the addendum's rather than a second maintained copy of it.*

**This strategy is now backed by a requirement: FR-54.** Until 21 July 2026 it was a prose section and a metric, which is precisely what v1 had — a gold set that existed and never ran. A strategy with no numbered requirement, no owner and no gate is the first thing to go under schedule pressure, and its absence is invisible because the product still runs.

**The problem.** No engagement has been won, so there is no client *corpus*. The public-corpus move that solves the fake-data problem for drafting and *veille* — real published legal text — does **not** solve it for triage: published case law is clean, structured and uniformly relevant, which is the exact opposite of the undifferentiated dump triage exists to survive. And synthetic documents are precisely what produced v1.

**The resolution is to separate two things v1 conflated: real content and real mess.** No single source has to supply both, and none of them has to be invented.

| Need | Source | What it gives, and what it does not |
|---|---|---|
| **Real mess at volume** — genuine threading, duplicates, attachments, dead ends | **Enron / EDRM corpus**, ~500 000 genuine business emails, public since the FERC release; the canonical dataset of the e-discovery field | Actual human correspondence, messy for the right reasons. English — this limits *language* realism, not *pipeline* realism. Licence terms of the specific distribution used must be verified before use. |
| **A measurable recall target** | **TREC Legal Track** collections, built for e-discovery evaluation with human relevance judgments | This is the *gold set* that gives the *confidence bound* something real to be scored against. v1 had a gold set and never ran it; running it is SM-2. |
| **French-language realism** | Real French public legal and administrative text, **mechanically degraded**: rendered as skewed scans, wrapped in `.msg` with plausible headers and reply chains, duplicated with variations, a fraction deliberately corrupted | The *content* is real; only the *degradation* is manufactured — and degradation is the thing under test. This is categorically different from fabricating documents. |
| **A small genuinely-owned dump** | APX Advisory's own mail, proposals and project files | Tiny, but unquestionably real and owned. A smoke test, not an evaluation set. |

**Requirements this section imposes — all of them now carried by FR-54:**

- **Every corpus enters through *ingestion*** (FR-33). A corpus is a data source selected by *configuration-as-data*. It is never a fixture, never a demo branch, never a fallback that can override a working system.
- **SM-2 runs in CI against the *gold set***, every run, with the figure recorded, a floor, a significance rule, and a **merge gate**: no ranking or triage code merges before it executes.
- **The degradation pipeline is itself part of the test surface**: the mechanical degradations applied to French public text are the inputs that must produce *failure register* entries of the expected error classes (FR-5), so the degradation configuration and the expected failure classification are asserted together.
- **The *gold set*'s relevance definition is mapped onto this product's**, in writing and versioned. TREC's notion of relevance is not *ordonnance 145 CPC* relevance, and a recall figure measured against an unmapped gold set measures the ranker against somebody else's question.
- **The *denominator* is verified at the *design target*** using the assembled corpus, not extrapolated from a smaller run (SM-3).

**Accepted risk, stated plainly and not smoothed.** Without a firm looking at the output, classification quality is measured against public benchmarks rather than against a practitioner's judgement of their own *matter*. The benchmarks make the product **measurable**; they do not make it **wanted**. This is the same drift — toward what is buildable rather than what is wanted — that produced v1, and no mechanism in this PRD prevents it. The only thing that does is a real *matter*.

**Highest-value acquisition for this increment:** one real anonymised litigation *matter*, from any friendly practitioner, on any terms. No signed engagement is required. Ask by shape and volume, not in the abstract — *"one closed matter, 200+ pièces, mostly email, anonymised however you like"* is a request a practitioner can act on; "some documents" is not. That framing failure is the most likely reason nothing ever arrived before.

---

## 9. Cross-Cutting NFRs

- **Scale.** Every consequence in §4 that is scale-sensitive is asserted at the *design target* of **100 000 *pièces* after container expansion** per *tenant*. Demo-scale verification does not satisfy an FR. `[ASSUMPTION: no per-operation latency or throughput target is set — the sources state none. Ceilings derived from UJ-1 are not the same thing as invented targets, and where one exists it is stated at the FR. See OQ-6.]`
- **Capacity boundaries, distinct from performance targets.** OQ-6 covers how *fast*; this covers how *much*, and the two fail differently — capacity turns into crashes, performance into slowness. Bounded by configuration, each with a defined default and each surfaced as a *failure register* class rather than an outage: the size of one *pièce*; container nesting depth and expansion ratio (FR-57); attachments on one message; *matters* per *tenant*; concurrent *import jobs* per *matter* (one, FR-7); retained *ranking versions* (FR-16); rows in one export. `[ASSUMPTION: capacity bounds are required and none is specified anywhere upstream. The specific defaults are architecture's to set; their existence is not.]`

- **The per-*pièce* LLM judgement is the largest inference cost and the largest data-egress event in the system, and it is uncosted.** FR-38 sends *tenant* text to the model provider for every *pièce* that reaches stage 3 of the cascade. At the *design target* this is not a query path; it is a substantial export of a client's *matter*, performed automatically, as the product's normal operation. Three consequences the build must carry rather than discover:
  - **Cost.** Nobody has written down what one triage run costs. §10's cost section discusses the ownership tax and the buyer's reference price and never touches marginal inference cost — while OQ-2 (forfait versus subscription) is being argued without the input that decides it. SM-18 makes the figure exist; OQ-20 asks what it means.
  - **The cascade is the mitigation, and it is a requirement, not an optimisation.** Deterministic filters, near-duplicate grouping and cheap semantic scoring run first; the LLM judgement is applied only to the uncertain band plus a calibration sample (FR-38); justifications are generated only near **the line** (FR-18). This is what stands between the product and 100 000 model calls per *matter*.
  - **A fully local model may be necessary rather than premium.** §5 lists it as a premium sovereign tier worth building once a firm refuses the hosted provider in writing. Given what FR-38 actually sends, a *bâtonnier* applying the CNB criteria may refuse first, and the zero-retention clause — a contract clause, not a technical property (§10, R-9) — is the only thing between the firm's *matter* and a US-operated provider. **This is now an open question about the product's viability, not a pricing tier.** See OQ-20 and R-13.
- **Testability as a first-class requirement.** With one non-hands-on CTO and AI agents as the whole team, **tests are the substitute for the engineers who are not on the team**. An AI-driven build with no test suite is v1 again, faster: v1 ran approximately 80% untested with its test command erroring outright. Every FR above states its consequences in testable form for this reason, and an FR shipped without its consequences asserted is not shipped.
- **Fail loudly, everywhere.** No component degrades silently under failure. Every failure produces one of: a *failure register* entry, a halt, or a *worklist* line — and never a plausible-looking wrong answer. This generalises FR-9 and FR-10 into a system-wide rule.
- **Fail closed on access.** Every ambiguity in *tenant* or *RBAC scope* resolves to less access, never more (FR-14, FR-29).
- **Determinism where determinism is claimed.** Anything labelled *exhaustive* *truth status*, anything reconstructible from the *audit record*, **and any ranked order under a fixed *ranking version*** must be reproducible: same inputs, same output, on a different machine and after a restart. This includes tie-breaks (FR-39).
- **Security is a requirement, not an architecture concern.** Encryption at rest and in transit, authentication and session handling, grant-time authorisation, key management, and backup and restore are FR-47…FR-53. The off-the-shelf options are forbidden by `addendum.md` §1.2 for portability reasons that are correct, which makes this hand-rolled code, written by agents, reviewed by one non-hands-on person, where a mistake is silent and criminal.
- **Append-only where evidence is claimed.** The *audit record*, the *change log* and the *failure register* are append-only (FR-21, FR-24).
- **No hard dependency on any hosting-provider primitive.** The fitness function: *can this run, unmodified, on a single machine inside a law firm with no internet connection?* Anything that fails it goes behind an adapter. The acceptable/not-acceptable boundary and the rationale are in `addendum.md` §1.
- **Reversibility of every third-party choice.** Anything that could be compelled, priced or discontinued by a third party — the model provider above all — lives behind an interface, so the decision is a configuration line rather than a rewrite.
- **Observability without telemetry.** The product must be diagnosable by its user, over the telephone, by someone who cannot see it. That means: state visible on the *worklist*, error classes enumerated and stable, versions readable in the interface, and the *content-free projection* as the only export path.
- **Non-technical usability, with one bounded accessibility requirement.** The daily user is non-technical and works at inconvenient hours. Adoption is voluntary in practice: a partner cannot make someone use a tool that adds friction — they route around it. Nothing superfluous; no technical vocabulary in any user-facing surface — **assessed by review against a checklist, not by test** (FR-56), because no test decides whether a phrasing is in a lawyer's language. **The checklist, the review and its recorded verdicts are FR-59**, which is what turns this bullet from an adjective into something that can fail. The one bounded, testable requirement: **every *worklist* action and every triage-table edit is reachable and completable by keyboard alone.** No WCAG level is claimed, because claiming one without auditing it is the unaudited-number failure §5 forbids. `[ASSUMPTION: keyboard reachability is the accessibility requirement worth committing to in this increment. The sources name no accessibility standard; the previous wording promised accessibility in its heading and delivered adjectives.]`
- **Visual consistency as a build requirement.** One token set, one colour system, no hard-coded values — **enforced as a *structural property*** (FR-56, FR-59): no colour, spacing or type value appears outside the token set. *(v1 defect: three unreconciled colour systems, ~20 hard-coded values, no settings surface — which made per-*tenant* configuration unbuildable as a direct consequence.)* **The second half of that v1 defect has no structural answer and is stated instead: the shipped v1 application and its mockups shared almost no visual DNA**, and this increment's single most directly reusable asset is a mockup (`addendum.md` §5). Fidelity to it is *asserted by review* under FR-59 — the honest verb, and the only one available.

---

## 10. Constraints and Guardrails

### Safety

- **Human-in-the-loop everywhere.** No auto-delete, no auto-send, no auto-sign. Inherited, not up for debate.
- **Never hard-delete.** *Triage* is reversible labelling (FR-21).
- **Recall over precision** in triage, made unarguable by SM-2 and restated in a lawyer's unit by SM-C1 — and bounded, so that "retain everything" is visible as the non-answer it is, by SM-11.
- **The machine partitions; it never acts.** "No automatic action without a human" is not violated by FR-17 drawing **the line**: nothing is deleted, nothing is hidden, nothing is sent, nothing is signed, and both sets remain fully searchable and fully reversible. This carve-out is stated explicitly because a *bâtonnier* reading "no automatic action" will otherwise read it as covering exactly the act the product is named after, and the answer should not have to be improvised in the meeting.
- **Targeted friction, not uniform friction.** Confirmation is demanded where a decision carries consequence — an *override* (FR-25), a move of **the line** (FR-19) — and nowhere else. Uniform friction is ignored friction, and ignored friction is worse than none because it produces a record that looks like consent.
- **Blocking, not warning.** Warnings are ignored; blocks are not. Where a guarantee cannot be met the product refuses rather than qualifying — a query that cannot guarantee completeness errors instead of returning a labelled partial set (FR-13); a stale bound cannot be exported as current (FR-23, FR-58); an action whose record cannot be written fails (FR-53); a *pièce* that could not be scored is excluded from the order rather than sorted to the bottom (FR-38). Those consequences are already written. The rule is stated here so that the next requirement written against it inherits it rather than re-deriving it.
- **Prevention over filtering.** Where an output must not contain something, constrain what can be produced rather than screening what was produced. The *confidence bound* sentence is templated and rendered locally (A-42) rather than generated and vetted; confidence is derived from observable quantities rather than filtered out of a model's self-report (FR-42). **FR-23's banned-phrasing check across locales is a backstop, not the primary defence** — a blacklist doing primary-defence work is exactly what this rule distrusts, and it is kept because a translator is a second author, not because it is what makes the sentence safe.
- **The product must never present a guess as a proof.** This is the single design rule behind *truth status* (FR-15) and the reason a *similarity threshold* can never yield an *exhaustive* result set.

### Privacy and confidentiality

- **EU-only.** Inherited.
- **Zero-retention** with the model provider. Stated honestly: this is a **contract clause, not a technical property** — every retrieval-augmented request carries client text off the machine unless a fully local model is used, and a fully local model is out of scope (§5).
- **No fine-tuning on client data.** Ever.
- **Only code travels — meaning *APX's* channels, and nothing more.** APX never accesses, sees or extracts client data; follow-up is by telephone; the price is no telemetry and the mitigation is a self-diagnosing product plus the client-pushed *content-free projection* (FR-31, FR-32). **This says nothing about the model provider**, and FR-38 sends the substance of a *matter* there as the product's normal operation (§9, §11). Stating "only code travels" without that qualification would be materially misleading to the person it is said to.
- **RBAC by *matter* — Chinese walls** (FR-14). A cross-*matter* leak is a professional-conduct violation that happens silently, with no error message. It is the #1 realistic leak vector, ahead of the model provider and ahead of logs.

### Cost

- **Every shipped feature is a permanent tax**: tested, migrated blind against a 100 000-*pièce* index at every installation, defensible in front of a judge, supported by telephone with no telemetry. At three on-premise firms, one more feature is three blind deployments maintained forever.
- **"It's just tokens" is the identified failure belief** and the one this capacity makes most tempting. Writing code is nearly free; owning it is not. Unchecked, this belief reproduces v1 verbatim.
- **The buyer's reference price is low and public.** A 30-lawyer firm's realistic alternatives run €7k–79k per year, and the CCBE has publicly priced the hardware at €2 000–20 000. The product cannot be justified on cost of ownership; it is justified on removing a named confidentiality risk. This constrains scope: features that cost owning and do not serve that argument do not earn their place.

---

## 11. Data Governance

- **Residency.** All *tenant* data — *pièces*, *chunks*, *payload schema* records, *audit record*, *failure register*, configuration — resides within the *tenant*'s boundary: inside the firm for an on-premise installation, within the EU for a hosted one. Inherited, not up for debate.
- **Classification.** Every *chunk* carries its *tenant*, its *matter* and its *RBAC scope* in the *payload schema* (FR-8). Classification is a property of the data, not of the surface that displays it — which is why the pre-filter (FR-14) is possible at all.
- **Provenance.** Every *chunk* traces to a source *pièce* and a position within it, with the extraction method recorded (FR-8, FR-11). Nothing in the *corpus* is of unknown origin.
- **Retention.** Nothing is hard-deleted (FR-21). The *audit record*, *change log* and *failure register* are append-only; a resolved register entry is a state change, not a removal (FR-5). `[ASSUMPTION: no retention period is defined. A law firm has statutory retention obligations per matter and a client may make an erasure request; "never hard-delete" and lawful erasure are in tension and this PRD does not resolve it. See OQ-8.]`
- **Storage growth.** Nothing is deleted, every *ranking version* within the FR-16 bound is retained, and the *audit record* grows forever. FR-52 requires the product to compute and state a *tenant*'s storage footprint at the *design target*, because a firm buying one machine (§10: the CCBE prices the hardware at €2 000–20 000) needs that number before it buys, and it is computable today.
- **The *audit record* is a sword as well as a shield.** FR-19 requires the priced statement shown at the moment of a line move to be recorded, and FR-21 forbids deleting it — so the firm manufactures and retains permanently a dated document in which it was told the estimated prevalence of relevant material below **the line** and proceeded. This document has treated the record exclusively as a defence. Its discoverability, its standing under *secret professionnel*, whether it is protected work product, and whether a firm might rationally want a retention limit on it are **unanalysed**, and the analysis belongs to a practitioner rather than to this document. See OQ-19.
- **Separation of derived data.** No *tenant*'s data contributes to anything shown to another *tenant*, including aggregates and model behaviour (FR-29). No client data is used for fine-tuning, ever.
- **Egress. Exactly three paths exist, and the first is far larger than this section previously claimed.**
  1. **The configured model provider.** Previously described as "carrying query and retrieved context". That description is not true of this increment. FR-38 sends the substance of every *pièce* that reaches stage 3 of the relevance cascade, and FR-41 sends the *retained extracts* and the *case theory* for every justification generated. At the *design target* this is the largest movement of client data in the system, it is automatic, and it is the product's normal operation rather than an exceptional one. It travels under a **zero-retention contract clause, which is not a technical property** (§10, R-9). A *bâtonnier* applying the CNB criteria will see this immediately, and the honest description is the one that survives that conversation. The cascade (FR-38) is what bounds the volume; SM-18 is what measures it; OQ-20 is where the question of whether it is acceptable at all is recorded.
  2. **The user-initiated *content-free projection*** (FR-32), content-free by test.
  3. **The user-initiated *audit record* and retained-set exports** (FR-26, FR-46). Deliberate, *RBAC*-scoped, recorded in the *audit record*, and offered numbers-only by default because the full tier carries retained extracts, override reasons and filenames. It is the one act that moves client content out of the firm on purpose, and it was previously not counted as an egress path at all — which would have made §11's own assertion false the first time anyone exercised it.

  Any fourth path is a defect, and the absence of one is enforced as a *structural property* (FR-56), not by a runtime test.

---

## 12. Compliance and Regulatory

*This section states what the product must satisfy and what it must not claim. It is a build constraint, not a sales narrative.*

- **Secret professionnel is the binding obligation.** In France, Art. 226-13 Code pénal; in Luxembourg, Art. 458 Code pénal plus the Bar's internal regulations — where it is a **criminal** obligation rather than a purely deontological one, which raises the bar above France's. This is the obligation FR-14 and FR-29 exist to satisfy mechanically.
- **The CNB guide (17 March 2026)** sets the criteria a *bâtonnier* will actually apply: data located in France or the EU; nationality of the server owner (European, excluding entities subject to extraterritorial laws); location of model hosting; nationality of the model provider; and **systematic verification of AI output**. `[ASSUMPTION: these criteria are reported second-hand from a practitioner reading; obtaining the source PDF is an open action — see OQ-11. They are currently doing load-bearing work.]` Where this product stands against each:
  - **Criteria 1 and 2 — data location, and the nationality of the server's owner.** Satisfied by construction: the installation runs inside the firm's walls.
  - **Criteria 3 and 4 — where the model is hosted, and whose it is.** **Not satisfied by construction, and not satisfied at all in this increment**, because FR-38 sends *tenant* text to a hosted provider as normal operation (§11). That is the honest position, and OQ-20 is where it is resolved.
  - **Criterion 5 — systematic verification of AI output.** **This document previously claimed satisfaction it did not have.** FR-15 declares *truth status*, FR-24 records decisions and FR-26 exports them; none of that makes verification systematic, and the product's entire proposition is that the lawyer verifies a **sample** rather than 1 400 outputs. **The defensible argument is stronger and is now made rather than assumed:** random-sample verification carrying a stated, sound prevalence bound (FR-22, FR-23, SM-1) is a *better* answer than a claim of systematic review that no firm performs and no product can enforce — and it is measurable, where "systematic" is not. Combined with per-*pièce* *validation acts* (FR-45) over the *retained set*, the firm can state exactly what was individually verified and what was verified by sample. `[ASSUMPTION: random-sample verification with a stated, sound prevalence bound is a better answer to the CNB's fifth criterion than a systematic-review claim no firm performs. This argument has never been put to a bâtonnier, and the criteria themselves remain second-hand — see A-19 and OQ-11.]`
- **GDPR.** Art. 32 (security of processing) and Art. 44 et seq. (transfers) are the applicable provisions, together with the *tenant*'s own role as controller. Residency and egress are covered in §11; **the Art. 32 measures themselves are FR-47…FR-53**, which is why they exist — citing Art. 32 while specifying no security measure was the position this document held until 21 July 2026.
- **The EU AI Act is not a compliance driver for this increment, and must not be used as one.** Legal AI sold to law firms is very likely outside Annex III high-risk (that provision covers use by or on behalf of judicial authorities), and the high-risk regime was deferred to 2 December 2027 by the Digital Omnibus. Art. 50 transparency applies from 2 August 2026. **Leading with "AI Act compliance" signals APX has not read the Omnibus** and a sophisticated general counsel will know it. Still worth a lawyer's confirmation, but it is not a blocking question.
- **Extraterritorial access is not resolved by an EU region.** The strongest available evidence on this point is Microsoft France's sworn testimony to the French Senate on 10 June 2025 that it could not guarantee French data would never be transmitted to US authorities. This is why the model provider sits behind an adapter (§9) — it makes the choice reversible as a configuration line rather than a rewrite. It is mitigated, not resolved. See OQ-12.
- **No compliance certification is claimed or pursued in this increment**, and no accuracy or hallucination figure is published (§5).

---

## 13. Audit Trail / Decision Provenance

*The formal requirement, consolidated. Mechanisms are in §4.5; this states what the record must be able to answer.*

Given only the exported *audit record* for a *matter*, a reader with no access to the system must be able to answer, for any *pièce*:

1. **Did it enter the *corpus*?** If not, why not, and is it in the *failure register* with which error class — and was it ever retried, by whom?
2. **Where did the tool place it, and on what basis?** Its confidence — and how that confidence was derived, since no model reports it about itself (FR-42) — its label, its one-line justification, and the *retained extracts* behind it, each resolving to a *chunk* and a source position.
3. **Relevant to what question?** Which *case theory*, at which version, or the explicit statement that none existed and which intrinsic signals were used instead (FR-37, FR-38). This is the first question anyone contesting the triage will ask, and until 21 July 2026 the record could not answer it.
4. **Where was **the line** at the time?** Who put it there, when, against which *ranking version*, what priced statement were they shown when they moved it, and was this *pièce* pinned across it by anyone (FR-43)?
5. **Did a human look at it?** Was its value accepted as-is or modified — "accepted" only where a *validation act* occurred (FR-45), never by default and never by elapsed time — was the *pièce* opened in the viewer first, and was the act performed individually or as part of a bulk gesture, and over how many.
6. **Was any machine assertion overridden?** By whom, when, and with what stated reason.
7. **What can be said about what was set aside?** Which *sampling runs* were performed, over which frozen draw, with which verdicts, producing which *confidence bound*, at which confidence level, against which *ranking version*, which position of **the line** and which *RBAC scope*.
8. **What was the *denominator*** — and which one, the *matter*'s or a scope's — at the moment any of the above was asserted.

Properties: append-only; scoped by *tenant* and *RBAC scope*; every entry attributed, timestamped and **sequenced from a single authority**; **chained, so that a gap or a truncation is detectable by a reader holding only the export** (FR-53); system-initiated entries attributed to the system component rather than to a user; and self-contained on export, so that every number in it is recomputable from the export alone (SM-1).

The gap, stated rather than smoothed: this record proves a *human decision was made and recorded*. It does not prove the decision was *correct*. That is what the sampling *confidence bound* is for, and the *confidence bound* is itself a probabilistic statement — it bounds the risk, it does not eliminate it.

---

## 14. Platform

- **One workspace, three verbs.** The client surface is a single workspace whose verbs are ***consult*, *add* and *draft***, with regulatory *veille* as a separate module (§1). This increment builds the *add* verb — *ingestion*, triage, the home screen and the reading surfaces — **inside that shell rather than beside it**. Navigation, *matter* selection and the home screen are built as the workspace's, not as a triage tool's: *consult* is served thinly here by retrieval (§4.3) and the viewer (FR-44); *draft* is absent and its absence must not be designed around. A navigation that has to be discarded when drafting arrives is the specific outcome this constraint exists to prevent, and it is the default outcome of building §4 in isolation.
- **Web application**, usable on a standard workstation without an installation step for the daily user. `[ASSUMPTION: the sources state a "VS Code-style local packaging" direction for on-premise delivery but do not specify the client surface for this increment; a browser-reachable application served by the installed system is the reading that satisfies both the hosted-development tier and the single-machine installation.]`
- **Deployment-agnostic core.** The same code must run in a hosted deployment and on a single machine inside a firm with no internet connection. Hosted versus on-premise is a **packaging decision per *tenant***, never a fork. The acceptable/not-acceptable boundary is in `addendum.md` §1.
- **Local filesystem and removable-drive access** are required for FR-1 — this is the whole onboarding story and it constrains the client surface.
- **Languages: FR and EN** at parity (FR-34). Italian is OQ-3.
- **No mobile surface** in this increment.
- **Offline capability**: an on-premise installation must function without internet access except for the configured model provider, whose absence must degrade loudly (§9) rather than silently. **Which capabilities survive that absence is enumerated by the CI job of FR-55, not described in prose** — and the *confidence bound* sentence is explicitly among those that must render offline from the *audit record*, because a statistical statement that depends on a network call is not self-sufficient in the way SM-1 promises. "Degrade loudly" is otherwise satisfied by a product that does nothing.

---

## 15. Integration and Dependencies

*In scope for this increment:*

- **The filesystem** — the only ingestion integration. Folders, subfolders, removable drives (FR-1).
- **A language model provider**, behind a provider-agnostic adapter so the choice is a configuration line. The **largest** outbound path carrying *tenant* content — carrying the substance of every *pièce* judged at stage 3 of FR-38's cascade, not merely a query and its context — under a zero-retention contract clause (§9, §11). The adapter must admit a **locally hosted model** as one of its configurations without a code change, because OQ-20 may make that necessary rather than premium.
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

**The genuinely unsolved problem, stated as unsolved.** Signed, offline-installable, reversible migrations that run against a live 100 000-*pièce* index without re-indexing, at a site APX cannot see, is the one technical problem in this programme that has no answer yet. It is **deferred out of this increment, not solved.** Deferring it is correct for one installation. It is not correct past the second: version drift across blind installations compounds and is unrecoverable once it starts. See OQ-13.

**No auto-update channel** in this increment (§5). Updates are generated and shipped blind, installed by agreement, and their outcome is reported back only by a user-initiated *content-free projection* (FR-32).

---

## 17. Operational Requirements

- **Support model: telephone and human communication, with no telemetry.** APX cannot see the installation. Every operational requirement below follows from that single constraint.
- **The product must be self-diagnosing.** The state a support call needs is on the *worklist* (FR-27) and in the *denominator* (FR-28): what failed, how many, of what class, and what the user can do about it — all in the lawyer's language, with the technical detail one click behind.
- **Error classes are enumerated, stable and translated** (FR-5, FR-34). A support conversation refers to a class the user can read on screen, not to a message that varies by machine.
- **Version readability** as stated in §16.
- **The diagnostic export is the only escalation path**, is user-initiated, is inspectable in full before it leaves, and is content-free by test (FR-31, FR-32).
- **No on-call, no SLA, and no uptime commitment is defined in this increment.** `[NOTE FOR PM]` **This is a flat contradiction with the stated ambition, not a gap to be closed later.** The brief is explicit that a firm which misses a filing deadline because APX was down does not send a support ticket, and the corollary the brainstorming session ended on — *"without APX you cannot be a law firm" demands infrastructure status; infrastructure status forbids breaking* — is incompatible with a team that cannot answer a telephone at 22:00 on a Sunday. Either the ambition is downgraded in what is said to clients, or capacity is added before an installation exists. This is a decision, it belongs to the APX partners, and it should be made before SM-10 rather than after. See OQ-10. `[ASSUMPTION: no availability commitment is written, because the current capacity cannot underwrite one. This contradicts the stated ambition and is recorded as a contradiction rather than smoothed.]`
- **Every on-premise installation carries operations that somebody performs, and the figure is public: 0.5–1 FTE per site** (`04-competitive-landscape.md` §7.2). `addendum.md` §4 files that number as an argument about the *buyer's* total cost. It is also — and more sharply — a statement about **APX's** capacity, and in that register it is the hardest number in the whole input set. The team is one non-hands-on CTO plus AI agents. §10 prices every shipped feature at "three blind deployments maintained forever"; this is the multiplier standing in front of that sentence, and it applies before a single feature is counted. It is the same contradiction OQ-10 names, with a number attached, and it lands on R-1 as well as here.
- **Backup and restore are the operational floor**, and they are a requirement (FR-52), not a runbook. A backup whose failure nobody knows about is the most likely way an installation ends a client relationship.
- **Documentation must not lie in load-bearing places.** Every configuration key named in documentation exists and is asserted to exist by a test (FR-30). *(v1 defect: keys named in documentation appeared in zero source files; a module referenced throughout the documentation did not exist; a described ranking boost was applied uniformly and was therefore a no-op on ordering.)*
- **Decisions are recorded when superseded.** *(v1 defect: superseded architectural decisions were never marked, so the recorded default model and the recorded hosting provider both silently ceased to be true.)*
- **Nothing ships from a branch that is not the deployed one.** *(v1 defect: the head of development sat three commits ahead of the main branch, stranding the audit trail off the deployed branch — the sold differentiator was written and not deployed.)*

---

## 18. Risk and Mitigations

| # | Risk | Consequence if it lands | Mitigation in this PRD | Residual |
|---|---|---|---|---|
| R-1 | **Scope exceeds capacity, and this revision made it worse.** 60 FRs for one non-hands-on CTO plus AI agents, up from 36 — **and the build is not the whole of it: an on-premise site implies 0.5–1 FTE of operations, per site, on the same team** (§17). | The increment is half-built and untested — v1 again, faster. Or it is built and the second installation consumes the capacity that would have maintained the first. | Sequencing against the spine (`addendum.md` §3.3); tests as the substitute for absent engineers (§9); **§6.3: a named minimum-viable subset, a cut order with the cost of each cut stated and a criterion (cut toward the service wrapper), an item that may never be cut (FR-54), and a sequencing gate before the triage layer.** | **High and accepted, now with a response.** The previous residual — "no mitigation makes the list smaller" — was a statement that the risk was unmanaged. §6.3 does not make the list smaller either; it decides in advance what goes first, which is the only thing a document can do. The operations multiplier has no response at all and belongs with OQ-10. |
| R-2 | **No pilot client.** Drift toward what is buildable rather than what is wanted. | The exact mechanism by which v1 failed, repeated. | §8: measurement against public benchmarks; SM-10 as a binary; the standing acquisition ask for one real anonymised *matter*. | **High.** Benchmarks make it measurable, not wanted. Nothing in this document fixes this. |
| R-3 | **The *payload schema* is the only irreversible decision** and is made before anyone has seen a real *matter*. | A schema change after installation means a blind migration against a live 100 000-*pièce* index — the unsolved problem in §16. | FR-8 (explicit versioning, rejection rather than lossy migration); front-loaded sequencing; §15's note on accommodating an external-authority reference now. | **Medium.** Versioning limits the damage; it does not remove the lock-in. |
| R-4 | **A cross-*matter* or cross-*tenant* leak.** | A professional-conduct violation, silently, with no error message. The product's entire premise is void. | FR-14 pre-filter **with a scope-mutating adversarial suite**; FR-49 re-stamping on re-scope; **FR-1's scope ceiling and traversal boundary — the guard on the *ingestion* gesture, which is the widest attack surface in the product (§4.1) and not an edge case at the margin of a convenience feature**; FR-29; SM-6 with a zero target; fail-closed (§9); and the security baseline FR-47…FR-51, without which the application-logic controls are irrelevant. | **Medium.** The previous rating — "Low if the tests hold" — was defensible only against the application-logic vector, and only against a suite that did not mutate scopes. Against a stolen laptop, an unencrypted volume, a shared credential or a restored backup, the tests are irrelevant. The rating moves with the controls, not with confidence. |
| R-5 | **The *confidence bound* is wrong or misapplied.** A lawyer says a number in court that does not hold. | Worse than having said nothing. The north-star metric becomes the north-star liability. | §0.2 (the estimand corrected and the correction recorded); FR-23 (prevalence, hypergeometric, confidence level stated, scope stated, banned phrasings enforced structurally); SM-1's **soundness** target alongside reproducibility; SM-17 calibration; OQ-4 made a **blocking prerequisite** on FR-19 and FR-23 with a stated fallback. | **High.** Escalated from Medium-high. The estimand was not merely unchosen — it was chosen, written into a glossary, three FRs and a north-star metric, and **wrong**, and it survived every prior review of this document. The estimator remains unresolved (OQ-4) and no statistician is on the team. |
| R-6 | **The audit surface becomes noise** users learn to dismiss. | Every mechanism in §4.5 becomes ceremony, and the record documents consent that was never given. | Targeted friction not uniform friction (§10); FR-27 actionable-lines-only; SM-C2 as an explicit counter-metric. | **Medium.** This failure is gradual and invisible without observation, and there is no telemetry. |
| R-7 | **The market wedge does not convert.** Article 145 CPC demand is episodic; willingness to pay is unproven; the qualifying question — *"Refusez-vous des dossiers aujourd'hui ?"* — may be answered no. **Underneath the symptom is the billable-hour paradox:** on hourly billing the hours this product saves *shrink* the invoice, so efficiency destroys revenue unless the firm moves to fixed fees or absorbs more volume. APX Advisory sells *forfait*; its prospects bill by the hour. | The increment is well-built and unsold — or bought once and not renewed, because the buyer's own pricing model punishes the saving. | Nothing in this PRD, and the mechanism decides which claim is honest: **not hours saved, but *matters* the firm could not previously bid.** That is why FR-39's review-effort estimate carries the revenue thesis rather than being a convenience (§2.1). | **High.** Belongs to the APX partners. Rated on the mechanism now, not on the symptom. |
| R-8 | **Distribution asymmetry.** An incumbent reaches 7 500 French firms with essentially this product through software they already pay for; the cheapest competitor has the strongest sovereignty claim at €19/month. | APX loses on price and on distribution simultaneously. | Positioning, not product — plus **two product consequences the previous row named none of.** First: that competitor's sovereignty claim rests on a national qualification scheme that **excludes AI services by construction**, so its inference is not itself qualified and no hosted vendor, APX included, can claim the scheme end to end — **which is precisely the argument full on-premise wins** (verify before using it: OQ-25). Second: where capacity binds, cut **toward** the service wrapper, not away from it (§6.3). Never TCO, never general productivity: risk elimination for a named confidentiality-critical workflow. | **High and structural** — but no longer unanswered. The rebuttal exists and is unverified, which is the state OQ-25 records. |
| R-9 | **Zero-retention is a contract clause, not a technical property.** | The sovereignty claim is weaker than the pitch implies, and a client's counsel who looks closely will find it. | Stated honestly in §10; provider behind an adapter so the decision is reversible; the fully local model is the premium tier, out of scope. | **Medium, acknowledged rather than closed.** |
| R-10 | **Version drift across blind installations** once there is more than one. | Unrecoverable. Two firms on different code, neither observable. | §16 states it as unsolved and bounds it: correct to defer for one installation, not for two. | **Deferred, not mitigated.** OQ-13. |
| R-11 | **The one-line justification (FR-18, FR-41) is model-generated and could be wrong or fluent-but-empty.** | The user trusts a sentence that explains nothing, and the *audit drawer* documents the trust. | FR-41 derives every justification from named *retained extracts* resolving to *chunks* and source positions, verified by exact containment at display time; the interface says plainly that the extracts are what to check. | **Medium.** The extracts are the control; the sentence is not evidence. Justification quality has no automated measure and none is claimed. |
| R-12 | **Loss of an installation: disk failure, ransomware, a machine replaced.** One machine, inside a firm, no ops staff, no telemetry, an append-only record of asserted legal weight. | The *audit record* the firm may need in front of a *bâtonnier* is gone, and APX cannot see that it happened. | FR-52 (backup, exercised restore, failure surfaced on the *worklist*, storage footprint computed, pre-flight capacity check); FR-53 (continuity verified on restore). | **Medium-high.** New in this revision — this appeared in no section, no risk row and no open question before 21 July 2026, and it is the single most likely way an installation ends a client relationship. |
| R-13 | **The per-*pièce* LLM judgement is unaffordable, too slow, or unacceptable to a *bâtonnier*.** FR-38 sends the substance of a *matter* to a hosted provider as normal operation. | The economics of OQ-2 are decided by a number nobody has computed; UJ-1 dies if the first ranking takes longer than a weekend; and the confidentiality pitch is contradicted by the product's own normal operation. | The cascade (FR-38) bounds volume; near-the-line justification (FR-18) cuts it further; SM-18 makes cost, egress and latency visible; the adapter admits a local model without a code change (§15). | **High and open.** OQ-20. The honest possibility is that a fully local model is necessary rather than premium, which changes the cost base and the hardware conversation entirely. |
| R-14 | **The product concentrates the firm's risk.** An *ordonnance 145 CPC* or a *perquisition* now finds one indexed, searchable, deduplicated appliance instead of scattered mailboxes. | The product materially increases exposure in exactly the scenario it is sold for, and a client's counsel will say so. | Nothing in this PRD removes it. FR-47 (encryption at rest) and FR-49 (grant-time authorisation) limit who can exploit it; they do not change the concentration. | **Accepted and previously unstated.** It is an inherent property of doing the job, and it is better said by APX first than discovered by a prospect's counsel. |
| R-15 | **Hand-rolled authentication and authorisation.** `addendum.md` §1.2 forbids the off-the-shelf identity layer and row-level security, correctly, for portability. | The highest-risk code in the product is written by AI agents, reviewed by one non-hands-on person, and a mistake is silent and criminal. | FR-48, FR-49, FR-56 structural properties, SM-6's mutating adversarial suite, SM-15. Tests are the only control. | **High.** The forbidding is right and its price is real; this row exists so the price is on the register rather than implied. |
| R-16 | **The delivery model itself is one the adjacent market leader is actively retiring.** The dominant e-discovery platform is withdrawing its on-premise server product, raised its price on 1 April 2026 to force migration, and requires all new matters in the cloud from 1 January 2028 — after more than three quarters of its business had already moved. Everything in this document is built for on-premise. | *"If on-premise were viable, why is that vendor killing it?"* is asked in the first serious commercial conversation, and an improvised answer loses it. | **The answer, written down so it is not improvised: different buyer, different risk.** That vendor sells to litigation-services providers optimising cost across thousands of matters at scale, for whom cloud is simply cheaper. This product sells to a partner optimising for *secret professionnel* — a criminal obligation in Luxembourg — for whom the machine staying inside the walls **is** the purchase rather than a deployment preference. §2.2 already names those providers as non-users, which is the answer's first half without the question. Nothing in the build changes. | **Accepted and unmitigated.** The answer is good; the question is still a headwind, because one vendor's retreat gets cited as evidence against the whole posture and it will be cited. Detail and dates: `addendum.md` §12. |

---

## 19. Open Questions

*Each item carries an explicit `OQ-n` label. Until 21 July 2026 this was an unlabelled ordered list while `OQ-n` was cited 23 times across this document and its addendum — every reference resolved by position only, and a downstream agent grepping `OQ-4` found four citations and no definition. The numbering below preserves the previous positions exactly, so every existing reference still resolves.*

**OQ-1.** **Is the "same associates, more matters" narrative confirmed?** The brief assumes capacity expansion rather than headcount reduction, because the alternative gives the daily user a reason to sabotage the tool. The product cannot tell both stories. **Belongs to the APX partners, not the CTO.**

**OQ-2.** **Consulting forfait versus subscription.** The locked decision says forfait; the only quote ever issued priced monthly recurring cost with no development forfait at all; the market evidence points hard at forfait. Unresolved, and it changes what "configuration-as-data" has to absorb — a consultancy says yes to bespoke requests. **Belongs to the APX partners.**

**OQ-3.** **Is Italian in scope, and when?** Several Italian firms are in discussion with the APX partners; one recorded prospect holds ~15 years of documents on a physical server in Italy, which is an on-premise deployment. FR-34…FR-36 make adding a language data rather than a project, but the decision affects sequencing and the *gold set*. **Counterweight, from the input this question was framed without:** the brief holds that **Luxembourg deserves disproportionate attention** — the sharpest version of the whole argument, barely contested, and a jurisdiction where breaching professional secrecy is a criminal offence — and Luxembourg needs no third language, being already covered by FR/EN. The Italy signal is pulling the third language toward Italian; the jurisdiction the strategy points at is pulling nowhere. Decide against both inputs rather than against the louder one (`addendum.md` §12).

**OQ-4.** ~~**Blocking prerequisite**~~ — **RESOLVED IN APPROACH, 21 July 2026. No longer blocking; downgraded to a design question with a decided method.** The estimand was already settled (§0.2: a hypergeometric prevalence bound with its confidence level stated). What was framed here as needing "a statistician's answer rather than a guess" overstated the problem: a hypergeometric upper confidence bound is standard, documented statistics, and the five difficulties below are design decisions, not open research.

**Decided method.** Each difficulty below is answered explicitly in the design and recorded with its rationale; the resulting estimator is then **validated by simulation against populations whose truth is known** — generate populations at varying relevant-item prevalence and varying duplicate structure, run the sampling procedure many times, and assert that a stated 95% bound holds in at least 95% of runs. An estimator that fails that test is unsound and must not ship; one that passes it is defensible without an external authority. This is a testable engineering property, in the same family as every other guarantee in this document, and it belongs in CI.

**What this does not license.** Simulation validates the estimator against the model it assumes. It cannot validate the assumption that a real *discarded set* resembles the simulated ones — that is what the *gold set* and calibration (SM-17) are for, and where the honest residual uncertainty lives. Say so rather than implying the simulation settles everything.

**The five difficulties, each of which a naive estimator gets wrong, and each of which must be answered in the design:**
- **Near-duplicates and thread families (FR-38).** A *discarded set* of 1 400 in which 300 *pièces* are 40 variants of eight email threads is not a population of 1 400 independent units. Drawing 200 from it violates the independence a textbook estimator assumes, and the bound stated to a judge is **narrower than the evidence supports**. What is the unit of the draw — the *pièce*, or the family?
- **Census versus sample (FR-22).** Where the required sample equals the population, the honest output is *"every discarded pièce was reviewed; none was relevant"*, not a residual-risk figure over a fully reviewed population. Where is the crossover, and what does the sentence say near it?
- **Repeated sampling (FR-22).** Two runs over the same population is a multiple-comparisons problem that a record showing both runs does not repair, because the sentence travels alone. Do independent runs pool, and if so how, and what does a second run's sentence say about the first?
- **Population freezing (FR-22, FR-58).** The draw is reconstructible only against a frozen, identically-ordered population, and the population changes on ingestion, re-ranking, a pin or a line move. What is the exact freezing contract, and what invalidates a run mid-flight?
- **The projection at an unsampled position (FR-19).** The priced figure is not a sampling bound at all; it is a calibrated model estimate, and calibration requires labelled data from a comparable corpus. The only labelled corpus in the plan is TREC Legal Track — English, e-discovery, a different task and a different relevance definition from *ordonnance 145 CPC* review. Is that calibration admissible, and what does SM-17 do when it is not?

**OQ-5.** **What recall target does SM-2 assert, and what is its floor?** No target exists in the sources. Setting one before the *gold set* has ever been run would be inventing a number. Must be set from the first measured baseline, and then may only improve. **What is added here: a ratchet with no floor institutionalises whatever the first measured figure happens to be**, permanently defended by a green build, and a strict ratchet on a stochastic measure produces flaky builds that get disabled — which is how a gold set stops running for the second time. SM-2 now requires both a floor and a significance rule; what those values are is this question.

**OQ-6.** **What are the performance targets at 100 000 *pièces*?** Import wall-clock, exhaustive-search latency, time to first ranking. None are stated in the sources; SM-C4 depends on the answer.

**OQ-7.** **Partial evidence: ranking over an incomplete *corpus*, and an incomplete ranking over a complete one.** Two conditions on the same surface, widened from one:
- *(as originally asked)* **Can triage run over a partially ingested *corpus*?** Desirable (SM-C4), but it interacts with the inventory guarantee: a *denominator* that is still moving, and **the line** placed on incomplete evidence.
- *(added 21 July 2026)* **What is valid over a complete *corpus* that is only partly ranked** — the model provider rate-limited or dropped halfway through? FR-38 requires unscored *pièces* to be excluded rather than sorted to the bottom, and FR-17's refusal threshold covers the extreme case; what remains open is whether **the line** may be placed at all over a partially ranked population, what the priced statement means when it is, and what the *worklist* offers. This is a different condition from the first and was previously not flagged anywhere.

**OQ-8.** **How does "never hard-delete" coexist with lawful erasure?** A firm has statutory retention obligations per *matter*, and a data subject may request erasure. FR-21 and §11 name the tension and do not resolve it.

**OQ-9.** **How are SM-C2 and SM-C3 observed with no telemetry?** They are the counter-metrics that protect the audit surface from becoming noise, and they are precisely the ones a firm would have to volunteer. §7 states the three-part protocol — evaluation sessions, whatever a *tenant* pushes through FR-32, and computation **inside** the installation carried out as counts in the *content-free projection*. What remains open is whether the third part reaches enough of SM-C2 to be worth building, and what is recorded as unobserved when none of the three reaches a figure.

**OQ-10.** **What availability is committed, if any?** §17 declines to write one. The brief is explicit that a firm missing a filing deadline because APX was down does not send a support ticket. The ambition and the capacity are in open contradiction here.

**OQ-11.** **Obtain the CNB March 2026 guide itself.** Its hosting and nationality criteria are currently second-hand from a practitioner reading and are doing a great deal of load-bearing work in §12.

**OQ-12.** **Cloud Act acceptability.** "EU region" is not sufficient against a US-operated provider. Mitigated but not resolved by the provider-agnostic adapter, which makes the choice reversible as a configuration line. **Belongs to the APX partners and, ideally, to a client's counsel.**

**OQ-13.** **On-premise update delivery.** Signed, offline-installable, reversible migrations against a live 100 000-*pièce* index, at a site APX cannot see. Genuinely unsolved (§16). Must be answered before the second installation, not the second increment.

**OQ-14.** **Scale beyond the design target.** Is 100 000 → 1 000 000 *pièces* just more compute? Unanswered in every upstream document. **One real data point exists and has never been brought to this question:** the recorded Italian prospect of OQ-3 holds **~15 years of a practice's documents** on a physical server. Fifteen years of a practice, counted in *pièces* after container expansion (FR-57), is plausibly an order of magnitude above the 100 000 *design target* at which every scale-sensitive consequence in §4 is asserted. The question stays unanswered; it need not also stay un-evidenced.

**OQ-15.** **Should the human baseline be measured?** The honest comparison for triage is not perfect human review but what happens today — skimming under deadline — and it can be measured by sampling a lawyer's own past triage. Telling a client you measured their error rate is a delicate sales choice, and it is a choice, not an engineering decision.

**OQ-16.** **Does the triage taxonomy carry over?** v1's nine-label taxonomy is on the salvage list. Whether it is the right taxonomy for *ordonnance 145 CPC* review is unvalidated — it is *configuration-as-data* (FR-30), so getting it wrong is cheap, but shipping it unexamined would be inheriting a v1 assumption unexamined. **This question cannot be answered empirically in this increment.** SM-19 measures that labels are applied and not silently remapped; **nothing measures whether a label is correct** (§7), because no *gold set* available here carries judgements in a French firm's triage taxonomy. The answer is a practitioner's reading or nothing.

**OQ-17.** **Can one real anonymised *matter* be obtained before build starts?** Named as the highest-value acquisition for this increment (§8). It has never arrived, and the most likely reason is that it was always asked for in the abstract. **§6.3 now makes it a sequencing gate rather than a wish**: no triage-layer work begins until it is in hand or its absence is re-accepted in writing with a date.

*Added by the revision of 21 July 2026:*

**OQ-18.** **Is *custodian* the right unit, and what else does e-discovery treat as mandatory?** FR-4 collapses two copies of one document into one *pièce*, and *who held it* is frequently the fact in issue in *ordonnance 145 CPC* work. FR-8 now makes custodian a mandatory, queryable, dedup-surviving field, which is the minimum. Whether a practitioner would also require date-received, message-id families, or a chain-of-custody attestation is a question for a practitioner, and getting the *payload schema* wrong here is the one mistake that cannot be undone cheaply (R-3).

**OQ-19.** **The *audit record* as a sword.** Stated in full at §11, *Data governance*: the firm manufactures and keeps forever a dated record in which it was told an estimated prevalence and proceeded. Discoverability, standing under *secret professionnel*, protected-work-product status and whether a firm would rationally want a retention limit are all unanalysed, and the analysis belongs to a practitioner. **It is needed before build, not after** — a client's own counsel will raise it before signing.

**OQ-20.** **What does one triage run cost, in money, in time and in egress — and does a *bâtonnier* accept it at all?** FR-38 sends the substance of a *matter* to a hosted model provider as the product's normal operation. SM-18 makes the figures exist. Three decisions ride on them: OQ-2's pricing model is being argued without the input that decides it; UJ-1 is invalid if the first ranking takes longer than a weekend; and if a firm — or its *bâtonnier*, applying the CNB's model-hosting and model-provider-nationality criteria — refuses the hosted provider, **a fully local model becomes necessary rather than premium**, which changes the cost base, the hardware conversation and §5's non-goal list. Related: whether the corrected, honest *confidence bound* sentence (§0.2) still sells, which nobody has ever tested on a client.

**This question was written as though there were two options, and there are three.** As posed it reads "hosted provider, or buy a box in the firm". **MeluXina-AI** (LuxProvide) — a national sovereign GPU facility with more than 2 100 accelerators, entering service in **H2 2026**, positioned explicitly so that organisations can work with specialised models **without exporting sensitive data** — comes online in the same half-year, in the jurisdiction where breaching professional secrecy is a criminal offence and which the brief says deserves disproportionate attention. §15 already requires the model-provider adapter to admit a locally hosted model without a code change; sovereign hosted capacity is the configuration that sits between that and a US-operated provider, and it belongs in the hardware conversation before the hardware is bought (`addendum.md` §12).

**OQ-21.** **What is the near-duplicate policy, in product terms rather than statistical ones?** FR-38 groups thread families for ranking and OQ-4 needs the same threshold for sampling. But the lawyer-facing question is separate: does she see 40 near-copies of a thread, or one entry with 39 behind it; does the *bordereau* (FR-46) list them all; and does a *validation act* over the representative validate the family? A wrong answer here is visible to the user in a way the statistics are not.

**OQ-22.** **Single sign-on, and identity in a firm that already has a directory.** FR-48 makes the application own identity, which `addendum.md` §1.2 requires for portability. A 30-lawyer firm with Active Directory will very likely require SSO on day one. Deferred (§5), named, and not solved.

**OQ-23.** **Legal hold — sealing a *matter* once litigation is live.** Nothing freezes a *matter* against further ranking, so FR-16 can produce a new *ranking version* underneath a *confidence bound* already quoted to a court. Append-only helps; it is not a seal.

**OQ-24.** **Does a *matter* ever learn from its own corrections?** FR-20 rightly forbids automatic regeneration on edit, and this increment provides no user-initiated alternative either: Marc corrects fifty misclassifications and the remaining 1 650 keep the same basis forever. The prohibition must not be relaxed — it came from a practising associate and it is the architectural invariant of the system — so any answer is an **additional explicit action**, never a softening of FR-20.

*Added by the reconciliation pass of 21 July 2026:*

**OQ-25.** **Verify that the sovereignty qualification the cheapest competitor relies on excludes AI services.** The competitive record states that the French qualification scheme in question excludes AI services by construction — so that vendor's inference is not itself qualified, **and no hosted vendor, APX included, can honestly claim the scheme end to end, which is precisely the argument full on-premise wins.** The landscape document calls this its own highest-value open question and says outright: *verify that before using it.* It is currently the only answer this document has to R-8, a risk rated High and structural, and it is also the strongest available justification for FR-55's offline fitness function and for the §1.2 forbiddings that cost the programme R-15. Same shape as OQ-11 and it should be closed the same way — obtain the qualification's own scope statement rather than a summary of it. Names and citations: `addendum.md` §12.

**OQ-26.** **What is the largest *sampling run* a real senior lawyer will actually complete — and does the estimator have to work at that size rather than at 200?** FR-22 asks for one individual verdict per sampled *pièce*; bounding a *discarded set* of 1 400 at 1.5% takes 200 of them. The constraint this product was shaped by is the opposite (§2.1): *the lawyer keeps an eye on it; the whole point is to automate the tedious part.* Nothing anywhere establishes that 200 verdicts is a thing that happens, and SM-C3 only measures the failure afterwards. **Three mitigations exist and each has a statistical cost that must be paid explicitly rather than assumed:** **batching** across sessions (free, and FR-22 now requires it); **stratified draws** over the ranked order, which buy a tighter bound per verdict and change the estimator; and **sequential or curtailed sampling**, stopping as soon as the evidence is conclusive — the largest available saving, and **unsound unless the stopping rule is part of the validated estimator**, because optional stopping applied to a fixed-size bound is how a defensible number becomes an indefensible one. Answer this before FR-19 and FR-23 are built: it changes what OQ-4's simulation has to validate. If the honest answer is "sixty verdicts, not two hundred", the estimator has to be designed for sixty.

**OQ-27.** **Who produces the deontological dossier, and who carries the liability?** Two of the four components the competitive analysis calls the actual value are unowned. **The dossier** — the documented, mechanical answer a partner gives his *bâtonnier* and his insurer (§2.1) — is a document, not a feature. The material for it already exists inside the build (versions, the three egress paths of §11, the structural properties of FR-56, §12's CNB analysis); no requirement, no non-goal until now, and no person produces it. **Liability** — what APX warrants, what it excludes, and what its own professional indemnity covers when a triage run misses the *pièce* that decides a case — appears nowhere in this document or in any of its inputs. Neither is engineering, both belong to the APX partners with a practitioner's help, and neither is optional before a first installation.

---

## 20. Assumptions Index

*Every `[ASSUMPTION]` in this document, surfaced for confirmation. Correcting any of these is cheaper now than after §4 has been built.*

| # | Section | Assumption |
|---|---|---|
| A-1 | §2.2 | Italian-speaking users are non-users of this increment; Italian is treated as an open question rather than a requirement, despite Italian firms being in discussion with the APX partners. |
| A-2 | §2.3 | Persona names are illustrative composites drawn from the discovery record. No firm and no client is named anywhere in this document. *(Now carries an inline `[ASSUMPTION]` tag; it was previously an index row with no inline site — the one entry that did not round-trip.)* |
| A-3 | §2.3 UJ-1 edge case | The user is told how many *pièces* were recognised as already present rather than having them silently skipped — silence reads as data loss to a user promised that nothing is ever deleted. |
| A-4 | §2.3 UJ-2 | The sceptical senior lawyer's random-sampling audit journey is an inference from the requirement, not a narrated scene from discovery. |
| A-5 | §2.3 UJ-3 | The associate's cell-by-cell correction journey is an inference from the requirement, not a narrated scene. |
| A-6 | §2.3 UJ-3 edge case, FR-20 | Concurrent editing within one *matter* is in scope. The sources do not address it; a shared *matter* with a partner and two associates makes it near-certain. |
| A-7 | §2.3 UJ-4 | The line-moving journey is an inference; the priced sentence itself is from source. |
| A-8 | FR-2 | No wall-clock target is set for an *import job* at the *design target*; the sources state none. A **ceiling** is derived from UJ-1 (the *retained set* must be readable over a weekend) rather than invented, and a build that misses it has invalidated a user journey. |
| A-9 | FR-3 | The OCR quality signal and its threshold are *configuration-as-data*; no threshold value is fixed. |
| A-10 | FR-11 | Exact-containment verification is built in this increment and now has a consumer **inside** it — FR-41's justifications and FR-26's *audit drawer* — rather than being justified by cheapness alone. |
| A-11 | FR-13 | No absolute latency target is set for exhaustive search at the *design target*; the requirement is that the figure is measured, recorded from the first baseline, and does not regress. |
| A-12 | FR-19 | The priced figure is a **projection from the ranking**, not a sampling bound, and it requires calibration against the *gold set* to be defensible. The sources state the sentence, not the method. See OQ-4 and SM-17. |
| A-13 | FR-21, §11 | A firm will eventually require lawful erasure of a *matter*; "never hard-delete" and lawful erasure are in tension, named and not resolved. |
| A-14 | FR-25 | A minimum meaningful length is enforced on *override* reasons and repeated identical reasons are surfaced as a quality signal. The source specifies "a required one-line reason" and no more. |
| A-15 | SM-10 | No date is attached to "installed at a real firm"; no engagement exists to attach one to. |
| A-16 | SM-C2 | No thresholds are set for *worklist* dismissal or *override* reason quality; these are trend metrics whose direction is the signal. |
| A-17 | SM-C4 | Partial triage over a partially-ingested *corpus* is desirable but is not specified as an FR; it interacts with the inventory guarantee in a way the sources do not address. |
| A-18 | §9 | No per-operation latency or throughput target is set anywhere in this document. |
| A-19 | §12 | The CNB March 2026 criteria are reported second-hand from a practitioner reading; the source PDF has not been obtained. |
| A-20 | §14 | A browser-reachable application served by the installed system is the client surface. The sources state a local-packaging direction but do not specify the surface for this increment. |
| A-21 | §15 | The *payload schema* is designed now to accommodate an external-authority reference on a *chunk*, though nothing in this increment writes one — because this is the one mistake that cannot be undone cheaply. |
| A-22 | §17 | No availability commitment is written, because the current capacity cannot underwrite one. This contradicts the stated ambition and is recorded as a contradiction rather than smoothed; it now also carries a `[NOTE FOR PM]`. |
| A-23 | §2.3 UJ-1 second edge case, FR-57 | Containers are expanded rather than registered as single failures. A litigation dump delivered as archives makes expansion the difference between a *denominator* that is right and one wrong by two orders of magnitude. |
| A-24 | §2.3 UJ-2 | The corrected, honest *confidence bound* sentence is still worth buying. No client has ever been shown either version. See OQ-20. |
| A-25 | §2.3 UJ-4 second edge case | The empty-*retained set* case is handled symmetrically with the empty-*discarded set* case. The sources handle only the bottom of the range. |
| A-26 | FR-1 | Traversal is confined to the selected subtree and links pointing outside it are refused, because the pre-filter cannot detect material that was mislabelled at the ingestion boundary. |
| A-27 | FR-4 | A `supersedes` relation between *pièces* is required. The sources address duplication and not versioning. |
| A-28 | FR-6 | A configured filesystem-noise exclusion list is required and is surfaced as its own count, rather than polluting the *corpus* or dominating the *failure register*. |
| A-29 | FR-7 | Concurrent *import jobs* into one *matter* are serialised. Allowing them requires a distributed count no source asks for. |
| A-30 | FR-13 | Accent-insensitive, case-insensitive, elision-aware, hyphenation-joining matching is the default normalisation of a *deterministic expression*, with the applied normalisation declared on the result. The sources specify none of this. |
| A-31 | FR-16 | Retained *ranking versions* are bounded by configuration, with versions referenced by a bound, a *pin*, an export or an *audit record* entry exempt. |
| A-32 | FR-17 | The three refusal conditions — size floor, score dispersion, unscored share — and their form are an inference. The sources require a refusal and define none. |
| A-33 | FR-18 | Justifications are generated near **the line** with on-demand backfill, rather than for all 100 000 *pièces*. This cuts cost, latency and egress by roughly an order of magnitude and costs nothing a user notices. |
| A-34 | FR-19 | **The line** needs a concurrency rule of its own; FR-20's cell rule does not reach it. |
| A-35 | FR-20, FR-24 | Ordering is decided by a server-assigned monotonic sequence, not by a workstation clock. An air-gapped installation has no NTP. |
| A-36 | FR-23 | A post-hoc declaration that a *ranking version* is unfit is required, at a configured K/N threshold. FR-17's refusal is evaluated before ranking and never again. |
| A-37 | FR-27 | The *worklist* aggregation key, its cap and its partial-completion semantics are an inference. The sources show aggregated lines and specify no rule. |
| A-38 | FR-48 | MFA is required to exist; its enforcement is a *tenant* policy decision. The sources specify no authentication requirement at all. |
| A-39 | FR-50 | The configuration and provisioning surface is the smallest thing that closes the FR-30 / "no admin cockpit" contradiction — a settings screen and a provisioning step, not a cockpit. |
| A-40 | FR-52 | The whole of backup, restore and disaster recovery is an inference. It appears in no source document, and it is the single most likely way an installation ends a client relationship. |
| A-41 | FR-53 | *Audit record* sequencing and chaining are required, so that incompleteness is detectable by a reader holding only the export. |
| A-42 | FR-55 | The *confidence bound* sentence must be renderable offline from the *audit record*, by template rather than by model call, or SM-1's self-sufficiency is untrue on an on-premise installation. |
| A-43 | §9 | Capacity boundaries — *pièce* size, nesting depth, attachments, *matters* per *tenant*, retained versions, export rows — are required and none is specified upstream. The defaults belong to architecture; their existence does not. |
| A-44 | §9 | Keyboard reachability of every *worklist* action and triage-table edit is the accessibility requirement committed to; no WCAG level is claimed, because claiming one without auditing it is the unaudited-number failure §5 forbids. |
| A-45 | §12 | Random-sample verification with a stated, sound prevalence bound is a **better** answer to the CNB's "systematic verification" criterion than a systematic-review claim no firm performs — but this argument is untested with a *bâtonnier*, and the criteria themselves remain second-hand (A-19, OQ-11). |
| A-46 | FR-13 | *Pièce* names and titles are inside the searched set of a *deterministic expression*, and the *failure register* is searchable by name separately, a match there returning as a register hit rather than a *corpus* hit. The sources record the user's request for an exact-name search; no requirement implemented it. |
| A-47 | FR-31 | An **attestation floor** — a text-derived value may be emitted only where it is attested across a configured minimum of *pièces* and *matters* — is the structural form of content-freedom, and is what lets the next increment's style extractor reuse the primitive rather than fork it. The sources specify one primitive with three consumers and never say how the third stays content-free. |
| A-48 | FR-59 | A recorded review gate — a versioned phrasing checklist with dated verdicts, plus keyboard reachability and one token set — is the strongest answer available to "ease of use" in an increment with no user. The sources name it as one of three promises and specify no mechanism. Whether the product is in fact usable is decided by SM-10, which has no date. |
| A-49 | FR-60 | *Matter* progress belongs on the home screen as a second, separate zone below the *worklist*. The upstream decision made the worklist the top **zone** rather than the whole screen; the alternative — no matter progress on the home screen at all — is coherent, cheaper, and is what §6.3's cut produces. |

---

## 21. Revision log

### 2026-07-21 (second pass) — reconciliation against the four upstream inputs

Input: `reconcile-inputs.md` in this folder — a gap report reading this document against the brief, the brief addendum, `brainstorm-intent.md`, the raw session record `.memlog.md` and `04-competitive-landscape.md` §7–§8. It raised 22 gaps. **All 22 are resolved below; none was judged wrong.** **FR count: 58 → 60.** Three shapes account for most of them, and they are worth naming because they will recur: *the threat was kept and its rebuttal dropped*; *a principle survived in a §4.x Description while the FRs beneath it contradicted it*; *the requirement survived and the material that made it hard did not*.

| Change | Gap it answers |
|---|---|
| §1 restores the **three-verb information architecture** — one workspace, *consult / add / draft*, *veille* separate — and states that this increment is the *add* verb inside that shell. §14 carries the binding navigational constraint. | 1.1 — its absence made a standalone triage application the default outcome, which is the "three-tool navigation" the session put in WON'T |
| §1 restores the **offers-versus-promises frame** with the empty-directory diagnosis; §7 states the promise asymmetry outright; **§4.14 and FR-59** give promise 2 a gate — a versioned phrasing checklist with recorded verdicts, keyboard reachability, one token set — and **SM-20** measures that the gate ran. | 3.1 — ease of use was an adjective in §9 plus an admission in §7, which is the v1 failure shape this document exists to prevent |
| **SM-19** measures that labelling happens and is honest about itself; §7 states plainly that **label accuracy has no metric**; OQ-16 records that it therefore cannot be answered empirically. | 1.2 — FR-40 was validated by nothing and §7's honest list did not admit it |
| §6.3 gains the **service-wrapper criterion** on the cut order, with the status of all four wrapper components and the admission that **cut #2 removes the only one in scope**. R-8 gains product consequences. | 4.2 — the value is the wrapper, not the model, and the cut order was derived without it |
| R-8 carries the **SecNumCloud rebuttal** (the qualification excludes AI services by construction, so only full on-premise can claim it end to end) with **OQ-25** to verify it; **R-16** carries the *"if on-premise were viable, why is the market leader killing it?"* question and its answer — different buyer, different risk. `addendum.md` §12 holds the named detail. | 4.1, 4.3 — both threats were kept and both rebuttals dropped |
| §2.1 and R-7 carry the **billable-hour paradox** as the mechanism under the symptom, and name FR-39's review-effort estimate as what carries the revenue thesis. | 2.1 |
| **FR-31 becomes a registry, not a closed enumeration**: projectors, an attestation floor for text-derived values, the seeded-token test run against every registered projector, and the next increment's style extractor named as the second consumer. Glossary and §5 follow. | 3.2 — the enumeration foreclosed the consumer the primitive was specified for |
| **§4.6 becomes two zones** — the *worklist* on top, **FR-60**'s *matters* zone beneath it — with the Glossary corrected to "top zone, not the whole screen". | 3.4 — the description promised what FR-27 prohibited |
| §2.1 carries the user's constraint verbatim (*the lawyer just keeps an eye on it*); §4.10 states the boundary — reading is the job above **the line**, supervising below it; **FR-22 sizes the ritual before it starts**, requires batching, and puts early stopping inside the estimator; **OQ-26** asks what size of run a senior lawyer actually completes and prices the three mitigations. | 3b.1 — FR-22 asks for 200 individual verdicts, which is the monotonous reviewing the product exists to remove, and nothing sized it |
| **FR-13 puts *pièce* names inside the searched set**, with register hits distinguished from *corpus* hits. | 3b.3 — the user's own Ctrl+F, which neither engine performed |
| §4.1 states that **the intake gesture is the widest attack surface in the product**; §4.11 states that security does not begin downstream of it; R-4 follows. | 3b.2 |
| §0.3 records that **the context pack and the earlier project artefacts are stale** on the prospect relationships, where a reader meets the upstream pointers. | 2.2 |
| §5 records that the **blind two-document test moves to the next increment** with its two proxies. | 1.4 |
| §5 and **OQ-27** name the **deontological dossier and liability** as unowned; §2.1's partner job is marked unserved. | 1.3, and the liability half of 4.2 |
| §10 *Safety* states **blocking-not-warning** and **prevention-over-filtering** as rules, and names FR-23's banned-phrasing check as a backstop rather than the primary defence. | 3.6 |
| §9's visual bullet gains a verb — structural property plus review — and states the **mockup-fidelity** half of the v1 defect that had none. | 3.5 |
| §17 and R-1 carry **0.5–1 FTE of operations per on-premise site** as a statement about APX's capacity, not only the buyer's cost. | 4.6 |
| OQ-3 gains the **Luxembourg counterweight**; OQ-14 gains the Italian prospect's **~15 years**; OQ-20 gains **MeluXina-AI** as the third option it was written without. | 1.5, 2.3, 4.4 |
| `addendum.md` gains **§7…§11** — which the previous revision promised in its own header and in PRD §0.1 and never wrote — plus **§12** (market judgement: the wrapper, the SecNumCloud rebuttal, the Relativity question, Luxembourg and MeluXina, the [UNVERIFIED] size of the addressable base, the FTE figure), and records the **cockpit-visibility reversal** in its telemetry row. | 3.3, 4.5, and a dangling-reference defect found in passing |

**Nothing was renumbered.** FR-59 opens the new §4.14; FR-60 sits in §4.6 beside FR-27 and FR-28. SM-19, SM-20, OQ-25…OQ-27, A-46…A-49 and R-16 are appended.

**What this pass did not fix.** The promise asymmetry is *stated*, not closed: no mechanism in this document establishes that a non-technical lawyer can use the product, and none can before SM-10. OQ-26 may invalidate the size FR-22 is written at, and it is unanswered. The wrapper criterion makes §6.3's cut order arguable in two directions and does not decide it. Two of the four wrapper components remain documents nobody has written.

### 2026-07-21 — consolidated revision resolving three independent reviews

Inputs: `review-rubric.md` (quality rubric), `review-adversarial.md` (hostile read), `review-edge-cases.md` (exhaustive boundary walk). Every **critical** and **high** finding across the three is resolved below, and the medium findings that were cheap to close are resolved with them. **FR count: 36 → 58.** Sections §4.9…§4.13, §0.1, §0.2, §0.3, §6.3 and this log are new.

**The three decisions this revision applied, which are not reopened here.**

1. **The relevance model is hybrid, with an LLM judgement at its centre**, informed by an **optional *case theory*** and, absent one, by named intrinsic signals. FR-1's "exactly three inputs" is relaxed to admit an optional fourth field that blocks nothing. *(Answers: rubric §4 critical "no FR produces the ranking"; adversarial F2; edge-case L-2, L-7.)*
2. **Scope: absorb everything, and say plainly that the increment is larger than one person can comfortably build** (§0.3, §6.3, R-1). Nothing was dropped to keep the list tidy, and every individually large requirement says so where it is stated — FR-3, §4.10, §4.11, FR-54.
3. **The confidence-bound claim was mathematically false and is corrected** to a hypergeometric **prevalence** bound, everywhere it appears — Glossary, UJ-2, FR-23, SM-1 — with a permanent dated note in §0.2 and SM-1 asserting **soundness** alongside reproducibility. *(Answers: adversarial F1, F12; rubric §3, §4.)*

**New requirements.**

| New FRs | What they close | Review |
|---|---|---|
| FR-37…FR-39 — *case theory*, the relevance cascade, the ranked order and the *ranking version* | The ranking had no requirement, no input and no reproducibility contract | rubric critical 1; adversarial F2; edge-case L-1, L-6, L-7 |
| FR-40 — per-*pièce* labelling | Glossary defined *Triage* as ranking **and labelling** and no FR applied a label | rubric critical 2 |
| FR-41, FR-42 — justification derived from named extracts; confidence derived, never self-reported | Fluent-but-empty justifications; a model's made-up number feeding a statistical sentence | adversarial F1, R-11 |
| FR-43 — the *pin* | UJ-3's premise was impossible: one *pièce* could not cross **the line** without dragging it past everything above | edge-case L-4 |
| FR-44 — the *pièce* viewer | Reading is the job and had one clause | adversarial F11 |
| FR-45 — the *validation act*, bulk acceptance never undetectable | "This document was read by a human" was a phrase | adversarial F5; edge-case A-6 |
| FR-46 — retained-set export | The product produced no deliverable | adversarial F11 |
| FR-47…FR-52 — encryption, authentication and sessions, grant-time authorisation, the configuration and provisioning surface, key management, backup and restore | **No security requirements existed at all** while §12 cited GDPR Art. 32 | adversarial F4, F6; edge-case E-5, E-6 |
| FR-53 — *audit record* continuity | An action could succeed while its record failed, undetectably | edge-case A-2 |
| FR-54 — the corpus and *gold set* pipeline, with a merge gate | §8 was a strategy with no requirement — the item most likely to be quietly dropped, and v1's defect exactly | adversarial F8 |
| FR-55 — the offline fitness function as a CI job | The programme's most important invariant was prose in an addendum | adversarial F9 |
| FR-56 — structural properties enforced in CI | "Asserted by test" on undecidable universal negatives | rubric §4; adversarial F14 |
| FR-57 — container expansion and the unit of the *denominator* | *submitted* counted files while *indexed* counted *pièces*; one register entry stood for 500 hidden *pièces* | edge-case I-1, I-2, I-3; rubric §5 |
| FR-58 — freshness and staleness | Ingestion was not a staleness trigger, so a bound could grow false and stay exportable as current | edge-case L-5, S-5 |

**Corrections to existing requirements.** FR-1 (optional *case theory*, traversal boundary, scope ceiling at import, custodian); FR-2 (per-unit memory, poison-pill quarantine, frozen enumeration, derived weekend ceiling); FR-3 (extractor version, `extracted-empty`, corpus-wide OCR figures, scale honesty); FR-4 (identity is content+*matter*, not path — the self-contradiction; custodian survives dedup; `supersedes`; near-duplicates named as unsolved here); FR-5 (resolution by state change, new error classes, credential supply, bulk retry, RBAC on the register); FR-6 (unit in *pièces*, "not indexed" label, *denominator* vs *scoped denominator*, declared exclusion list); FR-7 (one job per *matter*); FR-8 (custodian, full text stored, in-flight version rule); FR-11 (named consumer, failed resolution); FR-13 (OCR qualification, full-text search, French normalisation semantics, scope disclosed in the exported wording); FR-14 (scope-mutating adversarial suite, revocation reaches sessions, register in scope); FR-16, FR-17 (version referent, tie-break, defined refusal conditions, line as ordinal + last retained *pièce*, partial-scope users may not move it); FR-18 (near-the-line generation); FR-19 (prevalence wording, calibration, concurrency, `[NOTE FOR PM]` blocked-on-OQ-4); FR-20 (monotonic sequence, bulk always detectable); FR-21 (bounded probe over an enumerated action registry); FR-22 (census, without replacement, frozen population and identifier list, repeated sampling declared); FR-23 (the corrected sentence, hypergeometric, banned phrasings enforced structurally, scope in the sentence, unfitness declaration, ingestion staleness); FR-24 (case theory and scope grants recorded, sequence numbers); FR-26 (two export tiers, named as the third egress path, recorded); FR-27 (aggregation, cap, review-not-test verb); FR-28 (*scoped denominator*); FR-30 (surface named, structural-property honesty about "behaviour"); FR-32, FR-33 (structural properties).

**Metrics.** SM-1 gains a **soundness** target. SM-2 gains a **floor** and a **significance rule**. SM-5 gains model-provider, audit-store and disk-full faults. SM-8 gains a refusal-case figure. **SM-11** (retained-set size — the metric that actually opposes recall, closing the degenerate optimum where placing **the line** at the bottom satisfied every metric while delivering no triage), **SM-12** (FR-8), **SM-13** (FR-13, FR-15), **SM-14** (FR-34…FR-36), **SM-15** (security), **SM-16** (ranking reproducibility), **SM-17** (calibration), **SM-18** (cost, egress and latency of the judgement) are new. **SM-C1 is corrected**: it is a restatement of SM-2 in a lawyer's unit, not a counterbalance, and it says so. A non-telemetry observation protocol is stated for SM-C2…SM-C4, and what has **no** metric is listed rather than dressed as measurement. *(Answers: rubric §3 and §6; adversarial F8, F12, F15.)*

**Cross-cutting.** §9 states the per-*pièce* LLM judgement as the largest inference cost and largest egress in the system, with the cascade as a requirement and a **fully local model as possibly necessary rather than premium**; §9 adds capacity boundaries and replaces the accessibility adjective with one bounded requirement; §11 declares **three** egress paths and describes the first honestly; §11 adds storage growth and the audit-record-as-sword problem; §12 stops claiming the CNB's "systematic verification" criterion is satisfied and makes the stronger sample-based argument instead; §13 gains the "relevant to what question?" and bulk-versus-individual questions; §17 escalates the availability contradiction to a `[NOTE FOR PM]`. Risk table: **R-1 gains a response** (§6.3), **R-4 moves Low → Medium**, **R-5 moves Medium-high → High**, and **R-12 (loss of an installation), R-13 (LLM cost and acceptability), R-14 (risk concentration) and R-15 (hand-rolled auth)** are new.

**Vocabulary and mechanics.** *document*, *item* and *file* are banned as substitutes for *pièce*; the *design target* is defined in *pièces*; *denominator* is split into two named quantities; *audit trail* inside the Glossary corrected to *audit record*; new entries for *index*, *case theory*, *relevance judgement*, *ranking version*, *sampling run*, *validation act*, *retained extracts*, *pin*, *custodian*, *container*, *deterministic expression*, *structural property*, *design target*, *scoped denominator*. **§19's open questions are now labelled `OQ-1`…`OQ-24`**, preserving every prior position so the 23 existing references still resolve; **OQ-4** absorbs near-duplicates, census-versus-sample, repeated sampling, population freezing and the calibration problem; **OQ-7** widens to partial *ranking* over a complete *corpus*; **OQ-18…OQ-24** are new. The Assumptions Index round-trips again: A-2 gains its inline tag and A-23…A-45 are added.

**What this revision did not fix, and cannot.** OQ-4 still has no statistician. No client and no real *matter* exists (R-2), and §6.3's sequencing gate is a decision to be honoured, not a mechanism. The increment is now demonstrably larger than the capacity available to build it, and saying so is the only honest thing this document can do about it.
