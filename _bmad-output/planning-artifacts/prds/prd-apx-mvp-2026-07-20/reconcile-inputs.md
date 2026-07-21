---
title: "Reconciliation: PRD against its four upstream inputs"
status: draft
created: 2026-07-21
---

# Reconciliation — what the PRD silently dropped

One pass per upstream input — the brief, the brief addendum, the brainstorming intent brief, and §7–§8
of the competitive landscape — plus a fifth pass (§3b) over the raw session record `.memlog.md`, which
holds four decisions that exist nowhere else. For each item: **what it was**, **where it lived**, **why
the loss matters**, **where it belongs** (PRD body / PRD addendum / nowhere).

This is a gap report. It proposes no wording and edits nothing.

**Method note.** The test applied throughout is not "is this idea mentioned somewhere" but "did it
survive as something *binding* — an FR consequence, a metric, a guardrail, a non-goal, an OQ, a
risk row — or did it evaporate into descriptive prose". A sentence that appears only in a §4.x
**Description** paragraph and is contradicted or unrealised by the FRs under it counts as lost.

Sections marked **[false alarm]** are things that looked missing and are not. They are listed so
the author does not re-litigate settled material.

### Index

| # | Gap | Belongs in |
|---|---|---|
| 1.1 | The three-verb information architecture (consult / add / draft) is gone entirely | PRD body |
| 1.2 | "Classification measured against the gold set" dropped; FR-40 has no metric and §7 does not admit it | PRD body |
| 1.3 | The partner's bâtonnier/insurer job has no requirement and no non-goal | PRD body |
| 1.4 | The blind two-document test disappeared without a recorded decision | PRD body |
| 1.5 | Luxembourg reduced from a strategic instruction to a legal citation | PRD addendum |
| 2.1 | The billable-hour paradox dropped from the risk framing | PRD body |
| 2.2 | The instruction that `state.json` / the context pack are stale was not carried | PRD addendum |
| 2.3 | The Italian prospect's "~15 years of documents" never reached OQ-14 | PRD body |
| 3.1 | "Offers vs promises" gone; promise 2 (ease of use) carried as an adjective | PRD body |
| 3.2 | The content-free projection had three consumers; FR-31's enumeration forecloses one | PRD body |
| 3.3 | "Cockpit visibility is per-tenant config" reversed into "no telemetry, ever" + a CI check, unrecorded | PRD addendum |
| 3.4 | Worklist was the *top zone*; §4.6 promises matter progress and FR-27 forbids it | PRD body |
| 3.5 | The mockup-fidelity trap is unanswered while the plan leans on the mockup | PRD body |
| 3.6 | "Prevention beats filtering" and "blocking, not warning" survive as consequences, not as rules | PRD body |
| 3b.1 | "The lawyer just keeps an eye on it" — the constraint FR-22's 200-verdict ritual runs against | PRD body |
| 3b.2 | The USB key and the dystopia are the same event: intake is the widest attack surface | PRD body |
| 3b.3 | "Type the exact name of the pièce" — neither engine searches names | PRD body |
| 4.1 | The rebuttal to the strongest competitive fact dropped while the fact was kept | PRD addendum |
| 4.2 | "The value is the service wrapper, not the model" — and §6.3 cuts toward the model | PRD body |
| 4.3 | "If on-prem were viable, why is Relativity killing it?" — question and answer both absent | PRD addendum |
| 4.4 | MeluXina-AI (sovereign GPU, H2 2026) never reaches OQ-20 | PRD body |
| 4.5 | The size of the addressable base was dropped, and it is an input to §6.3 | PRD addendum |
| 4.6 | "0.5–1 FTE of ops per on-prem site" filed as a pricing argument, never as a capacity argument | PRD body |

**Most consequential, if only five are actioned:** 4.2, 1.3, 3b.1, 1.2, 3.4.
**Cheapest to close (one clause each):** 1.4, 2.2, 2.3, 3b.3, 4.4.

---

## Input 1 — `../briefs/brief-apx-mvp-2026-07-20/brief.md`

### 1.1 The three-verb information architecture is gone entirely

**What it was.** *"One workspace, three verbs — **consult / add / draft** — with regulatory* veille
*as a separate module. The three previously-separate tools dissolve into this; triage stops being a
product and becomes 'add documents' plus a review queue."*

**Where it lived.** Brief, *The Solution*, first line. Decided (not proposed) in
`brainstorm-intent.md` §2 *Information architecture*.

**Status in the PRD.** Absent. *consult* and *workspace* appear nowhere in `prd.md` or its
`addendum.md`; the only occurrence of "three verbs" is addendum §4's unrelated *"Three verbs: asserted
by test, enforced as a structural property, asserted by review"*. §14 Platform describes a web
application; §4.6 describes the worklist
home screen; nothing states that this increment's shell is one workspace of which triage is the
*add* verb.

**Why the loss matters.** This was the decision that stopped triage being a product. Without it the
increment has no stated navigational frame, and the default outcome of building §4.1–§4.13 in
isolation is a standalone triage application whose navigation must be discarded when drafting
arrives next increment — which is exactly the "three-tool navigation" that `brainstorm-intent.md` §4
puts in **WON'T**. It also silently reopens a decision the session closed. The PRD is careful to
record every other reversal (§21 revision log, addendum §4 rejected alternatives); this one is
neither carried nor recorded as dropped.

**Belongs in.** PRD body — §14 Platform, or a one-paragraph constraint in §4.6. It is a capability
constraint on the client surface, not a technology choice.

### 1.2 "Classification measured against the gold set" was dropped; FR-40 has no metric at all

**What it was.** Brief *Success Criteria* 4: *"**Retrieval and classification** measured against the
gold eval set that already exists in v1 and was never once executed."*

**Where it lived.** Brief §Success Criteria, item 4. Also `brainstorm-intent.md` §5 item 5.

**Status in the PRD.** Half-carried. SM-2 measures **recall at the line** against the *gold set* and
validates FR-16, FR-17, FR-18, FR-37…FR-39, FR-54. **No success metric anywhere validates FR-40**
(per-*pièce* labelling) — verified: `FR-40` appears in the Glossary, in its own FR, in FR-46's export
row, in §6.1 and in the revision log, and in **zero** `Validates FR-…` lists. §7's closing paragraph
*"What has no metric, said plainly"* enumerates justification quality, worklist phrasing,
"self-diagnosing" and "no technical vocabulary" — and does not mention label accuracy.

**Why the loss matters.** The Glossary defines *Triage* as ranking **and** labelling. The revision of
21 July added FR-40 because no requirement applied a label; it did not add the metric. So one of the
two halves of the increment's defining verb ships unmeasured, and — worse — unmeasured *without the
document admitting it*, in a §7 whose stated discipline is to list what it cannot measure. This is
the same shape as the v1 defect the whole document is organised against: a capability that exists and
is never checked. It also interacts with OQ-16 (is the v1 nine-label taxonomy right?): with no metric,
OQ-16 can never be answered empirically.

**Belongs in.** PRD body — §7, either as a new SM or as an explicit line in "What has no metric, said
plainly". The cheap honest option is the second.

### 1.3 The partner's second job — the documented answer for the bâtonnier and the insurer — has no requirement and no non-goal

**What it was.** The brief's one-sentence defensible position: *"the only French provider that will
install a legal AI inside your walls, where nothing leaves, verified against free public sources,
**documented so your bâtonnier and your insurer can both sign off**."*

**Where it lived.** Brief, *What Makes This Different*, closing sentence; and *Who This Serves*.

**Status in the PRD.** The **job** survives verbatim in §2.1: *"When my insurer or my bâtonnier asks
how AI is used in this firm, I want a documented, mechanical answer, so that the conversation ends."*
**No FR realizes it.** Every other JTBD in §2.1 maps to FRs or is explicitly bounded (the partner's
pricing job is bounded by §5's pre-ingestion non-goal and partially served by FR-39). FR-26 exports a
*per-matter* audit record; that is evidence about one matter, not the firm-level, product-level
deontological dossier the sentence promises. `bâtonnier` and `insurer` appear elsewhere in the PRD
only as motivations for §4.11 and FR-48 — never as consumers of an artefact the product produces.

**Why the loss matters.** This is the differentiator, stated as such by both the brief and the
competitive research (see 4.2 below: *"APX's value must be the service wrapper… deontological
documentation"*). Leaving a stated job unserved and unbounded is precisely the pattern §0.3 says this
revision refused: absorb it or name it as out of scope. Right now a downstream `bmad-create-epics`
run has a persona with a job and nothing to build.

**Belongs in.** PRD body — either §5 as an explicit non-goal ("no deontological documentation pack in
this increment; the partner's second job in §2.1 is not served") or as an FR. Naming it as a non-goal
is the honest minimum, because the material to produce it (versions, egress paths, structural
properties, the CNB analysis of §12) already exists inside the build.

### 1.4 The blind two-document test disappeared without a recorded decision

**What it was.** The brief's parenthetical: *"(The blind two-document test remains the north star for
Syllogisme and moves with it to the next increment, along with the style profile and statistical
fingerprint.)"*

**Where it lived.** Brief, end of *Success Criteria*. Originates in `brainstorm-intent.md` §5 item 1,
labelled **"(user, non-negotiable)"** — Julian's own acceptance criterion.

**Status in the PRD.** Absent. *two-document* and *blind test* do not occur; the sole occurrence of
*indistinguishable* is FR-53's unrelated assumption about a missing audit entry. §5 defers *"the style
profile and the statistical style fingerprint"* — the two *proxies* for the test — and never names the
test itself.

**Why the loss matters.** The brief made an explicit decision (it *moves* to the next increment); the
PRD dropped the decision along with the item, so the record of where the user's own non-negotiable
went now exists only in the brief. The two things the PRD does defer are the *measurement apparatus*
for the criterion; deferring the apparatus while losing the criterion is how a non-negotiable becomes
an oversight. Cost is small now, high later: the next increment's PRD will be written from this one.

**Belongs in.** PRD body — one clause inside §5's first bullet. It is a deferral record, not a
requirement.

### 1.5 Luxembourg was reduced from a strategic instruction to a legal citation

**What it was.** *"Luxembourg is the sharpest version of the whole argument and is barely contested…
MeluXina-AI — a national sovereign GPU facility — enters service in H2 2026"*, and *"**Luxembourg
deserves disproportionate attention** within it."*

**Where it lived.** Brief, *What Makes This Different* and *Vision*.

**Status in the PRD.** Reduced. Art. 458 CP survives in §12 and as the motivation for §4.11's
severity; Luxembourg's fatality for v1's i18n survives in §4.8. The *instruction* — that Luxembourg
gets disproportionate attention — and the MeluXina fact are gone (see 4.4 below for why the second
one is load-bearing on OQ-20).

**Why the loss matters.** Mostly this is positioning, and positioning is legitimately not the PRD's
job. One consequence is not: OQ-3 pushes i18n scope toward Italian on the strength of the Italy
signal, while the jurisdiction the brief says deserves disproportionate attention is already covered
by FR/EN. A sequencing question ("which third language, and when") is being framed by the input the
PRD kept and not by the input it dropped.

**Belongs in.** PRD addendum (market judgement), with one sentence in OQ-3.

### [false alarm] — checked and handled

- **"The sale is never TCO; it is risk elimination."** Handled, and handled as a *binding scope
  constraint*, not a slogan: §10 *Cost* — *"features that cost owning and do not serve that argument
  do not earn their place"* — plus R-8's mitigation row and addendum §4 (*Selling on total cost of
  ownership*).
- **"APX must never present itself as a research tool."** Handled twice: §2.2 non-users and §5.
- **The narrative fork (fewer associates vs same associates, more matters).** Handled as OQ-1,
  correctly assigned to the APX partners.
- **"Never publish an unaudited hallucination rate."** Handled in §5 and addendum §4.
- **The associate's negative requirement** (*do not make me look stupid, do not lose my edits, do not
  make me check your work*). Carried verbatim in §2.1 and realised in FR-20, SM-9.
- **"A firm that misses a filing deadline because APX was down does not send a support ticket."**
  Handled, and escalated: §17 `[NOTE FOR PM]` + OQ-10 + A-22.
- **The corpus strategy (real content vs real mess; Enron / TREC / degraded French text).** Handled
  in §8 and promoted into a requirement (FR-54) with a merge gate — a strengthening, not a loss.

---

## Input 2 — `../briefs/brief-apx-mvp-2026-07-20/addendum.md`

This input is the most thoroughly absorbed of the four. §1 (no pilot client), §2 (corpus strategy),
§3 (infrastructure contradiction), §4 (capacity and sequencing) and §7 (deferrals) are all carried,
and in most cases strengthened — §3's fitness function became FR-55, §2's strategy became FR-54,
§4's sequencing became addendum §3.3. The gaps below are narrow.

### 2.1 The billable-hour paradox was dropped from the risk framing

**What it was.** *"The partner — signs, does not use. Buys capacity, margin and competitive standing.
**Vulnerable to the billable-hour paradox: efficiency shrinks the invoice unless the firm shifts to
fixed fees or absorbs more volume.**"* Stated more sharply in `brainstorm-intent.md` §6: *"on the
billable hour, saving three hours **shrinks** the invoice — APX destroys revenue unless the firm
moves to fixed fees or takes more volume. APX Advisory already sells forfait, not TJM; the client
firms still bill by the hour."*

**Where it lived.** Brief addendum §6; brief *Open Decisions* ("Aggravated by the billable hour…");
`brainstorm-intent.md` §6.

**Status in the PRD.** Gone. `billable` occurs zero times in `prd.md` and `addendum.md`. R-7 carries
the qualifying question (*"Refusez-vous des dossiers aujourd'hui ?"*) and *"willingness to pay is
unproven"*, which is the symptom, not the mechanism.

**Why the loss matters.** The mechanism is what makes the risk structural rather than commercial. It
is also the reason §2.1's partner job is about **pricing a matter** (FR-39's review-effort estimate)
rather than about hours saved — under hourly billing, hours saved are revenue lost, so the only
partner-facing value the product can honestly claim is *matters you could not previously bid*. Drop
the mechanism and FR-39's review-effort estimate reads as a nice-to-have instead of as the single
requirement carrying the revenue thesis. R-7 is rated High on a symptom.

**Belongs in.** PRD body — one clause in R-7, or in §2.1's partner paragraph.

### 2.2 The instruction that upstream project artefacts are stale was not carried

**What it was.** *"Superseding fact… no engagement has been won… **Earlier project artefacts
(`state.json`, the context pack) record that relationship as live and should be read as stale on this
point.**"*

**Where it lived.** Brief addendum §1, first paragraph.

**Status in the PRD.** The *fact* is carried emphatically (§0, §2.3, R-2, SM-10). The *instruction
about the other documents* is not.

**Why the loss matters.** `CLAUDE.md` sends every agent to `docs/context/00-README.md` first, and that
context pack records the prospect relationship as live. The PRD's downstream consumers are named as
`bmad-architecture` and `bmad-create-epics-and-stories`; both will read the context pack, and nothing
in the PRD tells them it is stale on the one fact that changes the whole framing. This is a
documentation-lies-in-load-bearing-places hazard of exactly the kind §17 forbids the *product* from
committing.

**Belongs in.** PRD addendum — one line under the "Upstream" pointer in its header.

### 2.3 The Italian prospect's "~15 years of documents" never met the design target

**What it was.** *"The context pack recorded one Italian prospect with ~15 years of documents on a
physical server in Italy. That is an on-premise deployment, not a hosted one."*

**Where it lived.** Brief addendum §5.

**Status in the PRD.** Carried in OQ-3, as evidence for on-premise packaging. **Not** carried into
OQ-14 (*"Is 100 000 → 1 000 000 documents just more compute?"*) or into the *Design target* glossary
entry.

**Why the loss matters.** Fifteen years of a practice, post-container-expansion in *pièces*, is
plausibly an order of magnitude above the 100 000 design target at which *every scale-sensitive
consequence in §4 is asserted*. The one concrete data point anybody has about a real prospect's volume
sits in the language question and never reaches the scale question it actually bears on. OQ-14 is
currently unanswered *and* un-evidenced; it could at least be un-answered and evidenced.

**Belongs in.** PRD body — one clause in OQ-14.

### [false alarm] — checked and handled

- **"Ask by shape and volume, not in the abstract."** Carried verbatim into §8 and addendum §2, and
  promoted into a sequencing gate (§6.3, OQ-17).
- **"Tests are the substitute for the engineers who are not on the team."** §9 and addendum §3.1.
- **"Front-load the irreversible; the payload schema is the only true lock-in."** Addendum §3.2,
  §3.3 step 1, R-3, and §15's forward-accommodation note.
- **The acceptable / not-acceptable infrastructure table.** Carried verbatim into PRD addendum §1.2
  and given a cost section (§1.5) and a risk row (R-15) it did not have upstream.
- **"Fully local model — only worth building once a firm refuses the hosted LLM in writing."**
  Carried into addendum §4, then correctly *escalated* by §9/§5/OQ-20/R-13 into "possibly necessary
  rather than premium". A strengthening.
- **The three stakeholders and "design for the sceptic and the other two follow."** §2.1 verbatim.

---

## Input 3 — `../../brainstorming/brainstorm-apx-mvp-rebuild-2026-07-20/brainstorm-intent.md`

### 3.1 "Offers vs promises" — the reframe that made simplicity a promise — is gone, and simplicity is the promise the PRD carries worst

**What it was.** The user's own reframe, marked **decided**:

| The three OFFERS (features) | The three PROMISES (the actual product) |
|---|---|
| RAG / search over firm data | Security & confidentiality |
| Syllogisme (drafting) | Ease of use for non-technical collaborators |
| Veille | Volume — decades of activity |

*"A firm does not buy RAG; it buys the right to put its matters in without risking liability. **v1
built all three offers and skipped all three promises** — each promise maps onto an empty directory:
security → empty `rbac/`; simplicity → no settings surface, 3 unreconciled colour systems, broken
i18n; volume → 8 empty `workers/` files."*

**Where it lived.** `brainstorm-intent.md` §2, *Offers vs promises (user reframe, decided)*.

**Status in the PRD.** The *diagnosis rows* survive scattered across FR-1, FR-33, FR-34, §9 and §17.
The *frame* does not. `promises` occurs once in `prd.md`, in an unrelated sentence.

**Why the loss matters.** The frame is what ranks the three. Promise 1 (security) now has FR-47…FR-53,
SM-6, SM-15 and three risk rows. Promise 3 (volume) has FR-2, FR-57, SM-3 and the design target
asserted at every scale-sensitive consequence. **Promise 2 (ease of use for non-technical
collaborators) has one §9 bullet, no metric, and the PRD says so:** §9 — *"no technical vocabulary in
any user-facing surface — assessed by review against a checklist, not by test"* — and §7 — *"'no
technical vocabulary' (§9) has no acceptance criterion."* One of the three things the user says the
firm actually buys is carried as an adjective and an admission. That is defensible only if it is a
recorded decision; as written it looks like attrition. The frame's other function was diagnostic —
*each promise maps onto an empty directory* — which is the argument for why the promise, not the
feature, is what must be gated.

**Belongs in.** PRD body — §7 or §9. Not as prose: the useful version is a decision about whether
promise 2 gets an acceptance criterion (e.g. the FR-27 phrasing checklist and the keyboard
requirement of §9 formalised as a gate) or an explicit statement that it does not and why.

### 3.2 The *content-free projection* was specified as one primitive with three consumers; the PRD builds it for one and forecloses another

**What it was.** Non-negotiable mechanism #10: *"**Content-free projection as a single reusable
primitive**, built once and used three times: (a) the on-premises **style extractor** emitting a
content-free profile, (b) the client-pushed diagnostic export, (c) the cockpit that sees THAT 2 800
failed but not WHICH."* Reinforced in §5: *"Anonymisation leaves the critical path: ship the extractor
to the firm, documents never move, only the content-free profile comes out."*

**Where it lived.** `brainstorm-intent.md` §3 mechanism #10 and §5 *Style-profile sourcing*.

**Status in the PRD.** FR-31 builds the primitive; FR-32 is consumer (b); §5 defers consumer (c) as
part of the admin cockpit. **Consumer (a) is never named** — `style extractor` and `phrasebook` occur
zero times in `prd.md` and `addendum.md`. Worse, FR-31's consequence list is an *enumeration*: *"The
primitive emits **only**: counts, enumerated error classes, version identifiers, timing figures, and
diagnostics passed through a redaction step."* A style profile — sentence-length distribution,
connector frequency, section lengths, a phrasebook of the firm's own formulae — is none of those five,
so FR-31 as specified **cannot** serve consumer (a) without being amended.

**Why the loss matters.** This is a forward-compatibility break introduced silently. The style profile
is next increment's most confidentiality-sensitive mechanism and the whole reason it is tractable is
that the extractor runs at the firm and only a content-free profile leaves. If FR-31 is built to its
current enumeration, the next increment either amends it (cheap) or builds a second content-free path
(which FR-31's last consequence — *"A second, ad-hoc path is a defect"* — forbids, and which SM-7
would then not cover). The PRD deferred the *style profile* correctly; it did not notice it had also
narrowed the primitive underneath it.

**Belongs in.** PRD body — one consequence or note on FR-31 naming the third consumer and stating
whether the enumeration is closed. Alternatively addendum §6, as an explicit "not decided here".

### 3.3 "Cockpit visibility is per-tenant config; SaaS tenants can be live-monitored" was reversed into "no telemetry, ever" and enforced by a CI check — without recording the reversal

**What it was.** *"Hard boundary (decided): only CODE travels… Price of that boundary: no telemetry.
Mitigation is *not* telemetry but a self-diagnosing product plus a client-initiated, content-free
diagnostic export… **Cockpit visibility is itself per-tenant config: SaaS tenants can be
live-monitored, on-prem tenants stay dark.**"*

**Where it lived.** `brainstorm-intent.md` §2, *Deployment posture (decided)*.

**Status in the PRD.** The first half is carried faithfully and repeatedly. The last sentence is
reversed: §5 — *"**No telemetry, ever.** The client pushes a content-free projection; APX never
pulls. This is a constraint, not a gap"* — and FR-32 makes it a **structural property**: *"every
outbound network call originates from an enumerated set of adapters… a static check asserts no other
outbound call site exists."* `cockpit visibility` and `live-monitor` occur zero times.

**Why the loss matters.** Two reasons. (i) It is a decision reversal that the PRD's own discipline
requires to be recorded — §21's revision log and addendum §4's rejected-alternatives table exist for
exactly this, and addendum §4's *Telemetry, of any kind* row rejects telemetry without noting that the
session had permitted it for hosted tenants. (ii) It has teeth: brief addendum §3 and PRD addendum §1
both keep a **future hosted tier** alive as the justification for the whole Supabase/Vercel/Railway
compromise, and FR-32's structural check makes that tier permanently unmonitorable by a build-failing
grep. If the reversal is intended — and it may well be, since a per-tenant exception to a structural
property is not a structural property — it should be stated as intended.

**Belongs in.** PRD addendum §4 (rejected alternatives), amending the existing telemetry row.

### 3.4 The worklist is "the top zone", not the whole home screen — and "which matters are moving" is now forbidden by the requirement that describes it

**What it was.** *"**Home screen = the human-in-the-loop queue.** It opens on 'what needs you?', not
'what can I do?': what bugged, what errored, what needs re-reading or sorting, **plus ongoing matters
and tasks**… **Design rule (decided): the top zone is a WORKLIST, not a log.**"*

**Where it lived.** `brainstorm-intent.md` §2; echoed in the brief (*"which matters are moving"*).

**Status in the PRD.** The design rule survives and is binding — Glossary *Worklist* (*"**Not a log.**
A line that is not actionable does not belong on it"*), §4.6's description, FR-27. But the PRD
collapses *top zone* into *the whole home screen*: the Glossary defines **Worklist — the home
screen**. §4.6's description still says the home screen shows *"which matters are moving"*, and then
FR-27's consequences (i) enumerate the line types and do **not** include a matter-progress line, and
(ii) forbid it — *"A line that is not actionable does not belong on it"*, *"A line whose click-through
leads nowhere actionable is a defect"*. FR-28 adds the *scoped denominator*. Nothing else is
specified.

**Why the loss matters.** A description promises something the requirements under it prohibit. The
build will resolve this by dropping the matters — leaving a home screen that answers *"what needs
you?"* and cannot answer *"where are my matters?"*, on a product whose daily user opens it at 21:00
on a Friday and whose first UJ has her working two matters at once. It is also the specific mechanism
by which the design rule erodes in the other direction: if matters must appear and the worklist is
the only surface, they will be added as worklist lines, which is the log FR-27 exists to prevent. The
brainstorm's own wording ("top zone") already contained the answer.

**Belongs in.** PRD body — §4.6, as either a second home-screen element or an explicit statement that
matter progress is not on the home screen in this increment.

### 3.5 The mockup-fidelity trap is unanswered while the plan leans on the mockup

**What it was.** v1 trap register row: *"3 unreconciled colour systems, ~20 hard-coded hexes, no
settings surface → Per-firm `.docx` templates and per-client veille profiles are unbuildable.
**Mockups and shipped app share almost no visual DNA.**"*

**Where it lived.** `brainstorm-intent.md` §9, and §8 salvage rank 5 (`maquette_anfr_v2.html`).

**Status in the PRD.** The first half is answered — §9 *"Visual consistency as a build requirement.
One token set, one colour system, no hard-coded values"*, and the consequence (per-tenant
configuration unbuildable) is stated. The second half — **the shipped app did not resemble the
mockups** — is dropped. Meanwhile PRD addendum §5 records `maquette_anfr_v2.html` as *"the design
source for PRD FR-20 and FR-26 — the most directly reusable artefact in the whole salvage list"*.

**Why the loss matters.** The plan's most reusable asset is a mockup, and the trap register's warning
is that in v1 mockups did not survive into the build. Every other trap in the register got a
mechanism; this one got neither a mechanism, a metric, nor a structural property, and §9's visual
bullet is the only NFR in the document with no verb attached (§7's honest list of unmeasured things
does not include it). Low severity, but it is a named v1 defect that is answered by adjective only —
and the task's question for this register is precisely "answered, or merely mentioned?".

**Belongs in.** PRD body — §7's "what has no metric" list, or §9 with a verb (*asserted by review*
would be honest and consistent with FR-56's three-verb rule).

### 3.6 "Prevention beats filtering" and "blocking, not warning" survive as consequences but not as stated rules

**What it was.** Two general design principles stated as sentences for drafting mechanisms:
mechanism #13 — *"**Prevention over filtering.** Constrain generation to the firm's own phrasebook…
Keep a banned-patterns blacklist as config, **not as the primary defence**"*; mechanism #3 —
*"**Blocking, not warning.** Warnings are ignored; blocks are not."*

**Where it lived.** `brainstorm-intent.md` §3, mechanisms #3 and #13.

**Status in the PRD.** Neither sentence appears. Both are *implemented* in places: blocking-not-warning
in FR-13 (a query that cannot guarantee completeness errors rather than returning a labelled partial
set), FR-23/FR-58 (a stale bound **cannot be exported as current**), FR-53 (an action whose record
cannot be written **fails**), FR-45's confirmation, FR-25's mandatory reason. Prevention-over-filtering
is implemented in FR-42 (derive confidence rather than filter a model's self-report) and A-42
(template the *confidence bound* sentence rather than generate and screen it).

**Why the loss matters.** Moderately, and mostly for consistency: §10 *Safety* does state one such
rule as a rule (*"Targeted friction, not uniform friction"*, with its rationale), so the section
exists and these two are simply not in it. The one place the absence bites is FR-23's banned-phrasing
structural check across locales — a blacklist doing primary-defence work, which is the exact pattern
#13 warns against; it is mitigated by A-42's templating, but nothing in the document connects the two
or says which is the primary defence.

**Belongs in.** PRD body — §10 *Safety*, alongside targeted friction. Two sentences.

### [false alarm] — checked and handled

- **"The top zone is a worklist, not a log."** Binding: Glossary, §4.6, FR-27, with FR-27's aggregation
  rule and cap added so it stays true at the design target. Honest about being review-assessed. (The
  separate "top zone vs whole screen" issue is 3.4 above.)
- **"The tool commits" / draws the line.** Binding and everywhere: Vision, §4.4, FR-17, FR-19, SM-8,
  and addendum §4's *A ranked list with no committed line* row. Also given a defined refusal condition
  it did not have upstream.
- **"Targeted friction, not uniform friction."** Carried as a stated guardrail in §10 with its
  rationale (*"ignored friction… produces a record that looks like consent"*), realised in FR-25 and
  FR-19, and counter-measured by SM-C2.
- **"The home screen answers 'what needs you?', not 'what can I do?'."** §4.6 verbatim.
- **"An LLM checking an LLM shares its blind spots and will confirm a hallucination."** The drafting
  mechanism it belonged to is deferred, but its generalisation is implemented and argued: FR-42 (no
  self-reported confidence, enforced structurally) and FR-41 (*"the extracts are the control; the
  sentence is not evidence"*).
- **"Recall over precision", the omission failure mode, and the human baseline.** §10, SM-2, SM-C1,
  OQ-15 — including the sales caveat about measuring a client's own error rate.
- **"It's just Claude Code tokens"** and the closing corollary (*infrastructure status forbids
  breaking*). §10 *Cost*, addendum §3.4, §17.
- **The v1 trap register, rows 1–10 and 12–14.** Each is answered by a mechanism, not mentioned: FR-10,
  FR-9, FR-33, FR-4, FR-1/FR-2/FR-14, FR-24 + §17's deployed-branch rule, §9 testability, FR-30's
  documented-key test, FR-30's no-disabling-default rule, FR-16/FR-21/FR-45, FR-34…FR-36 + SM-14, §17's
  superseded-decision rule. The zero-data day-one loop is answered by sequencing (addendum §3.3 step 2)
  and by §6.3's gate. Only the mockup-fidelity row (3.5) and the commercial-decision row (moot, no
  client) are not.
- **MoSCoW, arbitrations and salvage.** All three arbitrations are recorded, including the coach caveat
  that *"'easy to write' is the cousin of 'just tokens'"* (addendum §4). Salvage list filtered
  correctly to this increment (addendum §5) with the deferred items named.

---

## Input 3b — the session record, `.memlog.md` (110 entries)

Read as a supplement to `brainstorm-intent.md`. Four items are recorded **only** here, and one of
them is a user constraint that bears directly on the increment's north-star mechanism.

### 3b.1 "The lawyer just keeps an eye on it" — the rejected reversal that says lawyers will not do the sampling ritual

**What it was.** Entry 93, a **user** insight, recorded as a rejected reversal:

> *REVERSAL 1 REJECTED ('the lawyer sorts, the tool checks'): lawyers hate it, it is monotonous.
> **The lawyer just keeps an eye on it.** The whole point is to automate the tedious part. Rejection
> confirms this is a real constraint, not a habit.*

**Where it lived.** `.memlog.md` entry 93. **It does not appear in `brainstorm-intent.md`** — only its
*output* does (entry 94: random sampling as the mechanism for "keeping an eye"). It does not appear
in the brief, the brief addendum, the PRD or the PRD addendum.

**Why the loss matters.** This is the constraint the whole product is shaped by, and it is in direct
tension with two of the increment's largest requirements:

- **FR-22 asks a senior lawyer to read 200 discarded *pièces* one at a time and record a verdict on
  each.** That is precisely "the lawyer sorts" — the pattern the user rejected as monotonous work
  lawyers hate — reintroduced as the north-star mechanism. The coach's own framing (entry 94) was
  that sampling is how you *keep an eye* rather than sort; nothing in the PRD carries the constraint
  that made that framing necessary, so nothing constrains the ritual's size, cost or ergonomics.
- **§4.10's opening sentence is *"Reading is the job."*** True for the *retained set*, and it is the
  opposite of the user's sentence, which is that the tool exists to automate the tedious part and the
  lawyer supervises. Both can be true at once, but the PRD never states the boundary between them —
  and the boundary is exactly what decides whether FR-45's per-*pièce* *validation act* over 180
  *pièces* is the product working or the product failing.

The PRD does arrive at part of the same worry independently: SM-C3 — *"A high first figure means the
ritual is too expensive and the confidence bound is theatre"* — and FR-22's consequence that *"the
interface must not make honest verdicts feel expensive"*. Those are good, and they are measurements
of the symptom. The user's sentence is the design constraint they should have been derived from, and
it would have raised a question nobody has asked: **what is the largest sampling run a real senior
lawyer will actually complete**, and does OQ-4's estimator have to work at that size rather than at
200?

**Belongs in.** PRD body — §2.1 (the sceptic's persona, where "he verifies rather than sorts" is the
missing clause), and as an input to OQ-4 and SM-C3. It is a constraint, not prose.

### 3b.2 The USB key and the dystopia are the same event

**What it was.** Entry 106: *"SYNTHESIS CONNECTION 3 — the USB key and the dystopia are the same
event: 100 000 confidential documents entering in one gesture, no IT department, 19h10, non-technical
user. **Best adoption idea and widest attack surface simultaneously. Whatever guards the folder-import
path separates 'clients in Italy, France and the USA' from 'leak at a Paris firm'.**"*

**Where it lived.** `.memlog.md` entry 106; absent from `brainstorm-intent.md`.

**Status in the PRD.** The *mitigations* exist and are good: FR-1 constrains the selectable *RBAC
scope* in both directions, refuses a null scope loudly, and confines traversal to the selected subtree
(A-26); R-4's mitigation row cites *"FR-1's traversal boundary"*. What is absent is the **ranking** —
that the ingestion path is the widest attack surface in the product. §4.1's description sells the
gesture (*"no connector, no API, no IT project, no meeting with anyone's systems people"*) and says
nothing about what that costs; §4.11 was written as though security lived downstream of intake.

**Why the loss matters.** Mostly for §6.3 and for sequencing. Addendum §3.3 puts security at step 0
and ingestion at step 2, which is right — but the reason recorded is *"every later step writes tenant
data"*, not *"the intake gesture is the attack surface"*. If capacity binds and FR-1's scope-ceiling
and traversal consequences read as edge cases rather than as the guard on the product's widest
surface, they are cheap to lose and their loss is silent.

**Belongs in.** PRD body — §4.1's description, one sentence; or R-4's row.

### 3b.3 "Type the exact name of the pièce, like on a classic computer" — the user's Ctrl+F, and FR-13 does not do it

**What it was.** Entry 40, a **user** idea: *"Deterministic search fallback: **type the exact name of
the piece**, like on a classic computer — a Ctrl+F escape hatch behind the semantic search."* This is
the origin of the two-engine architecture (entry 41 is the coach turning it into *truth status*).

**Where it lived.** `.memlog.md` entry 40. `brainstorm-intent.md` §3 mechanism #1 carries the coach's
generalisation and not the user's literal request.

**Status in the PRD.** FR-13 is a *deterministic expression* over **the stored full extracted text of
each *pièce*** — *"never over chunks"* — with specified French normalisation. Neither engine searches
*names*: FR-12 is semantic over *chunks*; filenames appear only in the *failure register* (FR-5) and
in the retained-set export (FR-46). So a lawyer who knows a *pièce* by its name and types it gets a
text search that may or may not hit, with no stated behaviour.

**Why the loss matters.** Small in build terms, disproportionate in use. It is the user's own instinct
about what the escape hatch is *for*, it is one line of an FR consequence, and its absence is the kind
of thing that makes a non-technical user conclude the tool cannot find a document she can see in the
list. It also matters to FR-13's own honesty contract: an *exhaustive* result set declares completeness
over "the searched set", and the searched set silently excludes the one field the user asked to search.

**Belongs in.** PRD body — one consequence on FR-13 stating whether names and titles are inside or
outside the searched set, and saying so on the result.

### [false alarm] — memlog items checked and handled

- **The DocuSign warning.** Entry 81: *"a DocuSign-style 'I have read and accept' is the most reliably
  ignored pattern ever invented… a **LIABILITY TRANSFER dressed as a safeguard** — the same failure
  shape as the score-threshold 'hors corpus'."* Fully answered, and in the same register: FR-45
  (*"1 400 documents marked 'read by a human' in four minutes, which is documented consent that was
  never given"*), §10 (*"ignored friction… produces a record that looks like consent"*), SM-C2, and
  the per-*pièce* rather than terminal gesture, which is the memlog's own FIX 1 applied to triage.
- **"Everything must be compliant: AI Act, GDPR, Cloud Act."** Entry 75, a user instruction. The AI
  Act half is **reversed** by the PRD (§5, §12: no AI Act compliance claim) — but the reversal is
  argued, evidenced and recorded in three places upstream and downstream, and was already recorded in
  the brief's *Open Decisions* as "downgraded, not open". GDPR → §12 and FR-47…FR-53; Cloud Act →
  OQ-12 and the provider adapter. This is a user instruction correctly overturned with a paper trail.
- **"A solution that enriches itself"** (entry 63, utopia). Named and refused: §5 — *"No feedback path
  from human corrections back into the ranking… stated so it is not mistaken for an oversight"* — plus
  OQ-24, which also protects FR-20 from being softened as the answer.
- **The three leak vectors in order** (entry 65). All three carried, in order, with the ranking intact:
  §10 and FR-14 (#1, *"ahead of the model provider and ahead of logs"*), §11 and R-9 (#2), FR-31 and
  SM-7 (#3, with content-freedom enforced by a seeded-token test exactly as the entry demands).
- **"The tool commits"** (entry 95, rejected reversal 2). Carried everywhere, with the user's reasoning
  intact (*"a ranked list refuses to commit and pushes the judgement back onto the human, which is
  exactly what they are paying to avoid"* → §1 Vision, FR-17, addendum §4).
- **The correction entry** (entry 110). The confidence-bound correction was propagated to every
  document in the chain and given a permanent dated note (§0.2), a structural check (FR-23, FR-56) and
  a soundness metric (SM-1). This is the cleanest piece of reconciliation in the whole set.

---

## Input 4 — `docs/context/04-competitive-landscape.md` §7 and §8

The PRD deliberately carries competitive material **anonymised** — *"an incumbent reaches 7 500 French
firms"*, *"the cheapest competitor… at €19/month"* — which is a defensible choice for a build
contract. The gaps below are not about names; they are about judgements and rebuttals that went
missing with them.

### 4.1 The rebuttal to the strongest competitive fact was dropped while the fact was kept

**What it was.** §7.1 item 2 and §8.2: *"Only one legal-AI vendor (Haiku) is on SecNumCloud-qualified
infrastructure, and **even that claim excludes AI services by construction**… nobody — including APX
— can honestly claim end-to-end SecNumCloud without going fully on-prem. **That is precisely the
argument on-prem wins.**"* And: *"must have a specific answer to 'why not Haiku?' — the honest one
being that S3NS's SecNumCloud qualification explicitly excludes AI services, so Haiku's inference is
not qualified. **Verify that before using it.**"*

**Where it lived.** `04-competitive-landscape.md` §7.1 item 2, §8.2, Appendix item 5 (*"Highest-value
open question in this document"*).

**Status in the PRD.** The **threat** is carried: R-8 — *"the cheapest competitor has the strongest
sovereignty claim at €19/month"* — and addendum §4 — *"€19/month on SecNumCloud-qualified
infrastructure"*. The **rebuttal** is not: `SecNumCloud` appears once in the PRD addendum, inside the
threat, and the "excludes AI services" qualifier appears nowhere. Neither does the verification action
(Appendix item 5), while its sibling verification action (obtain the CNB PDF, §8.6a) *was* carried, as
OQ-11.

**Why the loss matters.** As it stands the PRD records a competitor with a better sovereignty story at
a twentieth of the price, rated *High and structural*, with no answer — when the input supplies the
answer and flags it as its own highest-value open question. This is the single fact the landscape
document calls *"the hardest single fact in this document for the APX thesis"*, and the PRD kept the
hard half. It also matters to the build: if the qualifier holds, the argument that only full on-premise
gets end-to-end qualification is the strongest available justification for FR-55's offline fitness
function and for the §1.2 forbiddings that cost the programme R-15.

**Belongs in.** PRD addendum §4 (it names a vendor and a certification scheme) — plus the verification
as an OQ alongside OQ-11, which already exists for the sibling item.

### 4.2 "The value is the service wrapper, not the model" — and three of the four wrapper components are out of scope

**What it was.** §7.2 item 3: *"The CCBE published the recipe… Any technically-minded partner — or
their nephew — can now price a DIY alternative. **APX's value must be the *service wrapper*:
verification against Judilibre/Légifrance, deontological documentation, maintenance, liability. Not
the model.**"* Reinforced by §7.2 item 9: *"A consultancy competes on **service depth and proximity**,
or not at all."*

**Where it lived.** `04-competitive-landscape.md` §7.2 items 3 and 9, §7.3.

**Status in the PRD.** The **premise** is carried well: §10 *Cost* has the CCBE €2 000–20 000 hardware
anchor and the €7k–79k buyer reference price, and draws a real scope constraint from it (*"features
that cost owning and do not serve that argument do not earn their place"*). The **conclusion** —
*service wrapper, not model* — is not carried, and the four wrapper components stand as follows in
this increment: verification against Judilibre/Légifrance → **deferred** (§5); deontological
documentation → **unbuilt and unnamed** (see 1.3); maintenance → §17, with no SLA, no on-call and an
acknowledged contradiction (OQ-10); liability → **unaddressed anywhere**.

**Why the loss matters.** This is the most consequential omission in this pass. The judgement is that
the *product* is not the differentiator, and the PRD is 58 requirements of product. The constraint it
should impose is exactly the one §6.3 is trying to derive under capacity pressure: when cutting, cut
toward the wrapper. Instead §6.3's cut order is derived purely from internal dependency (what breaks
what), and its cut #2 — the *content-free projection* and diagnostic export — removes *"the only
support channel there is"*, i.e. it cuts **maintenance**, the one wrapper component that is in scope.
The input says that is the value; the PRD's own cut order puts it second.

**Belongs in.** PRD body — §6.3, as an explicit criterion on the cut order, and/or §18 R-8's
mitigation row (which currently says *"Positioning, not product"* and then names no product
consequence).

### 4.3 "If on-prem were viable, why is Relativity killing it?" — the question and its answer are both absent

**What it was.** §7.2 item 8: *"The market leader in the adjacent category concluded on-prem was not
worth supporting. Relativity is retiring Server, raised Server pricing on 1 April 2026 to push
migration, and requires all new matters on the cloud from 1 January 2028 — after >75% of its business
had already moved. **APX should have a crisp answer to 'if on-prem were viable, why is Relativity
killing it?'** The honest answer is *different buyer, different risk*… **But the question will be
asked.**"*

**Where it lived.** `04-competitive-landscape.md` §7.2 item 8.

**Status in the PRD.** Absent. `Relativity` occurs zero times in `prd.md` and `addendum.md`. The
adjacent-category framing survives only as §2.2's non-user bullet (*"Large-scale litigation-services
providers and their reviewers. The e-discovery platforms serve them; this product does not"*), which
is the *answer's* first half without the question.

**Why the loss matters.** This is the direct challenge to the deployment posture that everything in
the PRD is built around: on-premise is why FR-29 forbids hosting-provider identity, why FR-55 exists,
why FR-47's encryption must live in the storage adapters, why FR-52 exists at all, and why R-15
accepts hand-rolled auth. The risk register has rows for distribution (R-8), for price, for the wedge
not converting (R-7) — and no row for *the delivery model itself being one the adjacent market leader
is actively retiring*. §2.2 contains the beginning of the answer and does not know it is answering
anything.

**Belongs in.** PRD addendum §4 (rejected alternatives / posture justification) at minimum; a risk row
in §18 would be defensible, since the residual is real and unmitigated.

### 4.4 MeluXina-AI — a national sovereign GPU facility entering service H2 2026 — never reaches OQ-20

**What it was.** §7.1 item 5 and §7.3: *"**MeluXina-AI** (LuxProvide) with **>2 100 GPU accelerators
entering service in H2 2026**, explicitly positioned so organisations can fine-tune specialised models
**without exporting sensitive data**… That is a concrete Luxembourg-specific opening: a national
sovereign GPU facility coming online in the same half-year, in a jurisdiction where breaching
professional secrecy is a criminal offence."*

**Where it lived.** `04-competitive-landscape.md` §6.4 (quoted at §7.1 item 5) and §7.3.

**Status in the PRD.** Absent. `MeluXina` occurs zero times.

**Why the loss matters.** OQ-20 is the PRD's own open question about whether a fully local model is
*necessary rather than premium*, and R-13 rates it **High and open**, with the stated consequence that
it *"changes the cost base, the hardware conversation and §5's non-goal list"*. The single most
relevant external fact about that hardware conversation — sovereign GPU capacity coming online in the
same half-year, in the jurisdiction the brief says deserves disproportionate attention, explicitly
positioned for exactly this use — is in the input and not in the question. OQ-20 as written implies
the only options are "hosted provider" or "buy a box"; the input names a third.

**Belongs in.** PRD body — one clause in OQ-20; or PRD addendum §1/§6 where the model-provider adapter
is discussed (§15 already requires the adapter to admit a locally hosted model without a code change,
which is where this fact lands).

### 4.5 The size of the addressable base was dropped, and it is an input to §6.3

**What it was.** §8.5: *"France has **77 190 lawyers**… but **36% practise individually** and only 32%
are partners in a structure… Décideurs' business-law ranking covers **150 firms in total**, of which
~55% have 6–50 lawyers… **A precise census of French firms in the 20–40-lawyer band is [UNVERIFIED],
but the order of magnitude is low hundreds at most — and many of them are Paris business-law firms
already being sold to by Harvey and Legora.**"* And §7.3: *"perhaps a few dozen French firms and a
smaller number in Luxembourg."*

**Where it lived.** `04-competitive-landscape.md` §7.3 and §8.5.

**Status in the PRD.** Dropped. The brief carried it (*"the order of magnitude is low hundreds of
French firms in the 20–40-lawyer band, many of them Paris business-law firms already being sold to by
Harvey and Legora"*); the PRD carries neither the figure nor the qualification. R-7 states the wedge
may not convert; §1 states triage is *"a wedge, not a market"*.

**Why the loss matters.** §0.3 and §6.3 make an explicit, honest argument that the increment is larger
than the capacity available. The missing input to that argument is how large the prize is: 58
requirements, a permanent ownership tax per feature, three blind deployments per feature at three
firms — against an addressable base of *low hundreds, most already being sold to*. The PRD reasons
about cost with real numbers (§10) and about market size with adjectives. It does not change what to
build, but it is the number that makes §6.3's cut line arguable rather than reluctant.

**Belongs in.** PRD addendum (market judgement, and it is [UNVERIFIED] in the source, which the
addendum can say and the PRD body should not assert).

### 4.6 "On-prem implies 0.5–1 FTE of ops" is filed as a pricing argument, never as a capacity argument

**What it was.** §7.2 item 4: *"On-prem economics are against APX. Break-even vs cloud requires ~80%
sustained GPU utilisation; a 30-lawyer firm reaches nothing like it, **and on-prem implies 0.5–1 FTE
of ops.**"*

**Where it lived.** `04-competitive-landscape.md` §7.2 item 4, §8.5.

**Status in the PRD.** Carried once, into PRD addendum §4's *Selling on total cost of ownership* row —
where it is an argument about **the buyer's** cost. `0.5` does not occur in `prd.md` at all. §17
(Operational Requirements) and R-1 (scope exceeds capacity) never meet it.

**Why the loss matters.** The same figure is a statement about **APX's** capacity, and in that
register it is the sharpest number in the whole input set. The team is one non-hands-on CTO plus AI
agents. Every on-premise installation carries 0.5–1 FTE of operations that somebody performs; §17
answers this with telephone support, no on-call, no SLA and no uptime commitment, and escalates the
*availability* half to a `[NOTE FOR PM]` and OQ-10 — while the *staffing* half, which is quantified in
the input, is never stated. §10's cost bullet says every feature is *"three blind deployments
maintained forever"* at three firms; the input supplies the multiplier for that sentence and the PRD
uses it only to argue that the buyer should not think about TCO.

**Belongs in.** PRD body — §17 alongside the existing `[NOTE FOR PM]`, or R-1. It is the same
contradiction OQ-10 already names, with a number attached.

### [false alarm] — checked and handled

- **The CNB March 2026 criteria as the deontological argument.** Handled, and this is where the PRD is
  *better* than its input: §12 stops claiming satisfaction it does not have, states that criteria 3 and
  4 (model hosting, model-provider nationality) are **not** satisfied because of FR-38's egress, and
  makes a stronger sample-based argument on criterion 5 — recorded as A-45 with its own untested
  caveat, and routed to OQ-20 and OQ-11. The one nuance lost is the *form* of the argument
  (deontological, addressed to a bâtonnier, "the argument French avocats actually respond to"), which
  is positioning rather than build material.
- **"Drop the EU AI Act from the pitch."** Handled in §5, §12 and addendum §4, including the Digital
  Omnibus deferral to 2 December 2027, Art. 50 from 2 August 2026, and the Microsoft France sworn
  Senate testimony as the replacement evidence.
- **"Never promise tier (c) citation verification; never publish an unaudited hallucination rate."**
  Handled: §5 twice, addendum §4.
- **"Article 145 CPC triage: real pain, episodic demand, unproven willingness to pay."** Handled
  faithfully, including the discomfort: §1 — *"This is a **wedge, not a market**: demand is episodic and
  unproven, and the honest read is that it opens a door rather than fills a pipeline"* — and R-7.
- **"Corpus depth is unwinnable; APX must never pretend to be a research tool."** §2.2, §5, addendum §4.
- **"Priced and staffed as a consultancy or as a SaaS — those are different companies."** OQ-2, and the
  consultancy consequence for configuration-as-data is carried into OQ-2's own wording.
- **Distribution asymmetry (7 500 firms through existing practice-management software).** R-8, §1,
  addendum §4 — anonymised but intact, including the zero-switching-cost point.

---

## Cross-cutting observations

**Three shapes account for almost every item above.**

**1. The threat was kept and the answer was dropped; the job was kept and the deliverable was
dropped.** 4.1 (SecNumCloud rebuttal), 4.3 (the Relativity question), 1.3 (the bâtonnier dossier),
4.2 (the service wrapper). The PRD's declared discipline is to state uncomfortable things plainly and
it does that unusually well — §0.2, §0.3, §6.3, R-14, §17's `[NOTE FOR PM]` are all better than what
they came from. But the same filter appears to have selected *for* uncomfortable material and
*against* the load-bearing rebuttals and the non-engineering deliverables that sat beside it in the
inputs. The result is a build contract that is scrupulously honest about what it cannot do and silent
about several things the inputs said were the actual product.

**2. A design principle survived in a §4.x *Description* paragraph while the FRs beneath it did not
implement it, or forbade it.** 3.4 is the clean case (§4.6 promises matter progress; FR-27 prohibits
it). 3.1 is the diffuse case (ease of use as a promise → an adjective in §9 plus an admission in §7).
This document's own convention — stated in §0.1 and enforced throughout — is that FRs are contract
and everything else is orientation. **Anything that survives only in a Description is, functionally,
already dropped**, and a Description that contradicts its own FRs is worse than a silent one because
it reads as coverage.

**3. Qualitative material that made a requirement *mean something* was compressed out while the
requirement itself survived.** 3b.1 is the sharpest instance: FR-22 is intact, and the user sentence
that says a lawyer will not sit through it ("the lawyer just keeps an eye on it") is gone, so nothing
sizes the ritual. Same shape in 2.1 (R-7 keeps the symptom, loses the billable-hour mechanism) and
1.2 (FR-40 exists, its measurement does not). In each case the *what* was preserved and the *why it
is hard* was not — which is exactly the material that a functional-requirement structure sheds, and
exactly the material that decides whether a requirement is built well or built to the letter.

**One thing worth saying in the other direction.** The reconciliation is, on the whole, unusually
good. Every item in `brainstorm-intent.md` §3's fourteen non-negotiable mechanisms is present as a
mechanism rather than an intention; the v1 trap register is answered row by row with FRs rather than
mentioned; the corrected *confidence bound* was propagated to every document in the chain and given a
structural check; and §12 is *more* honest than its input rather than less. The gaps above are real,
but they are the residue of a careful pass, not the symptom of a careless one.
