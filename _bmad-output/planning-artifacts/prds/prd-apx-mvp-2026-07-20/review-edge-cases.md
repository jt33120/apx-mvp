---
title: "Edge-Case Review — APX MVP PRD, First Increment: Mass-Document Triage"
status: draft
created: 2026-07-21
reviewer: bmad-review-edge-case-hunter + domain boundary analysis
targets:
  - prd.md
  - addendum.md
---

# Edge-Case Review — unhandled boundaries

Method: exhaustive path enumeration over `prd.md` §2–§20 and `addendum.md` §1–§6. Every branching
path and boundary condition was walked; only the ones **not** covered by an existing requirement are
listed. Findings that were nearly flagged and are in fact handled are recorded in §9 with the
requirement that handles them, so the absence of a finding is legible.

No severity labels are assigned. Findings are grouped by the surface where the boundary is reached.

---

## 1. Import

### I-1. A container that opens — archives, PDF portfolios, nested `.msg`

**Boundary.** A `.zip`, a `.7z`, a PDF portfolio, or a `.msg` carrying another `.msg` as an
attachment, which the system *can* open.

**Not covered.** FR-3 enumerates the extracted formats (`.msg`, PDF born-digital, PDF scanned,
`.docx`, `.xlsx`, images) and specifies expansion for exactly one container: "An email with N
attachments yields N+1 *pièces*". Archives appear only as a failure: FR-5's error class
`archive-unopenable`, and UJ-1's *"1 dossier compressé n'a pas pu être ouvert"*. Nothing states
what happens when the archive **does** open. Three sub-boundaries follow, none specified:
recursion depth (an archive inside an archive inside a `.msg`), an archive whose expansion is
unbounded (a zip bomb, against FR-2's "without unbounded memory growth" which is stated for the job,
not for one unit), and whether an opened archive's members become *pièces* at all — if they do not,
`archive-unopenable` is unreachable as a class distinct from `unsupported-format`.

**Consequence.** A litigation dump delivered as a handful of `.zip` files — the normal delivery
shape for a *commissaire de justice* operation — either enters as a dozen *pièces* instead of
thousands, or halts the worker. The lawyer's *denominator* reads plausibly and is wrong by two
orders of magnitude.

### I-2. The inventory guarantee is arithmetically undefined for expanding units

**Boundary.** One submitted file yields more than one *pièce* (FR-3's N+1 rule), or yields none.

**Not covered.** FR-6 states the invariant as `submitted = indexed + failure register entries`, "at
all times, with no third bucket", and SM-3 makes a single violation "a release blocker, not a bug".
But *submitted* is counted at selection time over filesystem entries, while *indexed* is counted in
*pièces*, and the two are only equal when every file yields exactly one *pièce*. An email with three
attachments makes indexed exceed submitted by three. Nothing in FR-6 or the Glossary defines the
unit of the invariant, and nothing defines when the submitted count is frozen.

**Consequence.** The invariant test asserted by SM-3 fails on the first real `.msg` corpus, or is
written against a unit definition invented by the implementer — at which point the *denominator*,
the one number the product promises never to round or hide, means something nobody specified.

### I-3. A container that fails hides an unknown number of *pièces*

**Boundary.** A `.zip` of 500 documents fails to open and produces one `archive-unopenable` entry.

**Not covered.** FR-5 records one *failure register* entry per *pièce* that fails. An unopened
archive is one entry. FR-6's *denominator* therefore reads "· 1 unreadable" for 500 missing
documents, and FR-13's exhaustive absence claim is "qualified by the *failure register* count" —
a count that is off by 499. No requirement asks for an estimated or unknown-cardinality marker on a
container failure.

**Consequence.** Directly defeats the Glossary's own stated purpose for the *failure register*:
"The decisive *pièce* hides statistically in the *failure register*; a corpus claim made without it
is dishonest." Here the claim is made *with* it and is still dishonest, because the register
understates itself.

### I-4. A single *pièce* larger than memory, and the poison pill that follows

**Boundary.** One 6 GB PST, one 2 GB scanned PDF, one video attachment.

**Not covered.** FR-2 bounds memory for the *job* ("An *import job* over 100 000 documents completes
without unbounded memory growth") but no requirement bounds a single unit of work, and FR-5's
enumerated error classes contain nothing for resource exhaustion — no `too-large`,
`resource-exhausted` or `timeout`. Worse, FR-2's resume rule ("resumes from the last committed unit
of work") has no retry cap and no quarantine: the unit that killed the worker is the unit the worker
resumes on.

**Consequence.** An unkillable crash loop. The *import job* never completes, so FR-7's completion
summary never fires, so UJ-1 has no climax. The user sees an indicator that counts to 12 000 and
restarts forever, and the only diagnostic channel (§17, telephone plus FR-32) reports a version
number and a stuck count.

### I-5. The source mutates or disappears during the run

**Boundary.** Files added, modified or deleted in the selected folder after enumeration; the USB key
unplugged; the network share dropped; the laptop lid closed with the drive dismounted — the last of
which UJ-1 narrates explicitly as a supported path ("She closes her laptop lid; when she opens it
again the import has resumed").

**Not covered.** FR-1 requires traversal "to arbitrary depth" and FR-2 requires resume, but no
requirement defines the point at which the submitted set is frozen, nor the behaviour when a file
enumerated as submitted is unreadable at the moment it is reached, nor an error class for a source
that has gone away. `corrupt-file` and `extraction-error` both misattribute the cause.

**Consequence.** Two distinct failure modes collapse into one: a genuinely corrupt document and a
document on a drive that was unplugged both land in the *failure register* under an error class that
tells the lawyer to treat them as damaged. On resume after an unplug, the register fills with
thousands of misclassified entries, permanently, because FR-5 allows removal only by successful
re-ingestion or by an *override* with a reason (FR-25) — one reason per entry.

### I-6. Symbolic links, junctions and traversal outside the selection

**Boundary.** The selected folder contains a symlink to a parent directory (a traversal loop) or to
another *matter*'s folder elsewhere on the share.

**Not covered.** FR-1 states "Subfolders are traversed to arbitrary depth" and says nothing about
link resolution, cycle detection, or a boundary constraining traversal to the selected subtree.

**Consequence.** Either a non-terminating import, or — the confidentiality case — material from
another *matter* is ingested under **this** *matter*'s *RBAC scope*, stamped into the *payload
schema* at write time by FR-8, and thereafter correctly and permanently served to the wrong people.
FR-14's pre-filter cannot detect this: the pre-filter is working perfectly on data that was
mislabelled at the boundary. SM-6's adversarial suite tests queries against scopes, not ingestion
provenance, so the control R-4 relies on does not cover it.

### I-7. Extraction succeeds and yields nothing

**Boundary.** A blank scan, an empty `.docx`, a spreadsheet of numbers with no text, an image with
no recognisable characters, a `.msg` whose body is a signature block.

**Not covered.** The *pièce* did not fail, so FR-5 does not apply; it is "successfully indexed", so
by the Glossary it **is** in the *corpus*. But it produces zero *chunks*, and FR-13's exhaustive
search runs over indexed material. FR-3's OCR rule covers *low-quality* output ("indexed **and**
flagged") but not *empty* output. FR-18 covers the ranking side ("A *pièce* for which no confidence
could be computed is shown as such") and does not reach the corpus-membership side.

**Consequence.** A silent third state that FR-6 says cannot exist: counted as indexed, absent from
retrieval. Every *exhaustive* absence claim — the only claim in the product that can prove a
negative, per FR-13 — is quietly false for these documents, and carries a *denominator* that asserts
they were searched.

### I-8. Same content, different path — FR-4 contradicts itself

**Boundary.** The identical file at `/Dump/A/contrat.pdf` and `/Dump/B/copie de contrat.pdf`.

**Not covered.** FR-4 bullet 1: the identifier is "a deterministic function of its content **and its
provenance**". FR-4 bullet 3: importing A then B where B contains a copy of a file in A "produces one
*pièce* with two recorded provenance paths — not two *pièces*". These cannot both hold. If
provenance (path) is in the identity function, the two copies hash differently and are two *pièces*;
if it is not, the identifier is content-only and bullet 1 is wrong.

**Consequence.** The implementer picks one, and the choice silently determines whether a 100 000-file
dump with the customary 30–40% duplication rate presents as 100 000 *pièces* or 65 000. SM-4
("re-importing an identical folder changes the *corpus* count by zero") passes under either reading
and does not discriminate between them.

### I-9. Same path, changed content — no supersession relation

**Boundary.** `contrat_v3.docx` is imported, edited on the share, and the folder re-imported.

**Not covered.** Under FR-4's content-derived identity this is a new *pièce*. Nothing records that
it supersedes the earlier one; FR-4's idempotency rules address duplication, not versioning, and the
*payload schema* (FR-8) carries provenance and dates but no relation between *pièces*.

**Consequence.** Two *pièces* of the same document rank independently, one may fall either side of
**the line**, and the *bordereau* contains both with no indication of which is current. The
*confidence bound* counts them as two independent draws from the *discarded set* when they are one
document.

### I-10. Circular and quoted email threads — no near-duplicate handling anywhere

**Boundary.** A 40-message thread in which each reply quotes the entire chain beneath it; the same
message present as sender's copy, recipient's copy, and as an attachment on a forward.

**Not covered.** FR-4's deduplication is exact — a deterministic function of content. Quoted-reply
chains are near-duplicates, never byte-identical. No requirement anywhere in the PRD or addendum
mentions threading, near-duplicate detection, or email families, although §8 selects the Enron/EDRM
corpus **specifically because** it has "genuine threading, duplicates, attachments, dead ends".

**Consequence.** Two compounding failures. (a) The ranking is dominated by the most-quoted text: the
40 near-copies of one thread occupy 40 positions around **the line** and crowd out distinct
documents, so recall at **the line** — SM-2, the metric that fails the build on regression — is
measured against an inflated population. (b) The *confidence bound* (FR-23) treats the *discarded
set* as a population of independent units. It is not: drawing 200 from 1 400 where 300 of the 1 400
are 40 variants of eight threads violates the independence the estimator assumes, and the bound
stated to a judge is narrower than the evidence supports. OQ-4 asks for the estimator but does not
name this as an input to it.

### I-11. Every failure resolvable only by an *override* — the password-protected dead end

**Boundary.** Three password-protected PDFs, for which the lawyer has the passwords.

**Not covered.** FR-5 gives every entry "a retry action", and allows removal from the register only
"by successful *ingestion* or by an explicit user action recorded in the *audit record* with a
reason (an *override* per FR-25)". No requirement provides a way to supply a credential, so retry is
deterministic re-failure. Meanwhile UJ-1 puts *"3 pièces protégées par mot de passe"* on the
*worklist* as a human task, and FR-27 states "A line whose click-through leads nowhere actionable is
a defect. Asserted by test."

**Consequence.** An internal contradiction that a test required by FR-27 will surface: the line
exists by FR-27 bullet 4 (generated by *failure register* entries), and its click-through has no
available action. The user's only exit is an *override* — recording, in the permanent *audit record*,
that she deliberately excluded three documents she could in fact have opened.

### I-12. Filesystem noise and the no-third-bucket rule

**Boundary.** `.DS_Store`, `Thumbs.db`, `~$doc.docx` lock files, `desktop.ini`, resource forks — of
which a four-year multi-user share holds thousands.

**Not covered.** FR-6 forbids a third bucket: every submitted item is indexed or in the *failure
register*. No requirement permits an exclusion list, and any exclusion list would itself be a third
bucket unless FR-6 is amended to describe it.

**Consequence.** Either the *corpus* is polluted with thousands of zero-value *pièces* that enter the
ranking, or the *failure register* — and therefore the "· 2 800 unreadable" figure that qualifies
every exhaustive absence claim under FR-13 — is dominated by operating-system detritus. Both make the
*denominator* unreadable as the trust instrument §4.1 and FR-28 intend it to be.

---

## 2. Ranking and **the line**

### L-1. Ties, and the absence of a tie-break rule

**Boundary.** Many *pièces* score identically — the normal case for near-duplicates (I-10), for
boilerplate, and the degenerate case where the model returns a constant.

**Not covered.** FR-16 requires "exactly one ranked order per *matter* per ranking version" and
derives the *retained set* and *discarded set* from that order plus the position of **the line**. No
requirement specifies a deterministic tie-break. §9 requires "Determinism where determinism is
claimed... same inputs, same output, on a different machine and after a restart", but that clause is
scoped to *exhaustive* results and to what is reconstructible from the *audit record*.

**Consequence.** A tie spanning **the line** puts documents on either side by whatever order the
store returned them. Recomputation reshuffles membership without any recorded event, so the
*discarded set* a *confidence bound* was drawn from (FR-22) is not the *discarded set* that exists
when the draw is reconstructed from its recorded seed — and FR-23 requires every number in the
sentence to be "reconstructible from the *audit record* alone. Asserted by test."

### L-2. "Insufficient basis" is a required decision with no decision rule

**Boundary.** A *matter* of one document. Of eleven. A *corpus* where every score is identical.

**Not covered.** FR-17 says "A ranking whose basis is insufficient to place **the line** says so
explicitly and places no line, rather than placing one at an arbitrary position." Nothing anywhere
defines *insufficient*: no minimum *corpus* size, no score-dispersion condition, no confidence floor.
SM-8 measures "100%, or an explicit refusal to place it" — a metric satisfied by any implementation,
including one that never refuses and one that always refuses.

**Consequence.** The single most product-defining behaviour — "the tool commits" (§1, §4.4, SM-8) —
is unspecified at its own boundary. An implementer will place a line on a *corpus* of four, and the
sentence "in my view, everything above this" will be said about a judgement the system did not make.

### L-3. **The line** at position 0

**Boundary.** The line drawn above the first *pièce*: the *retained set* is empty, the *discarded
set* is everything.

**Not covered.** The mirror case is handled with care — FR-19: "Moving **the line** to retain
everything states that the *discarded set* is empty and no *confidence bound* applies — it never
reports a risk of 0%", plus the UJ-4 edge case. The top of the range gets no equivalent. Nothing
says whether the system may place the line there, what "in my view, everything above this" means
with nothing above it, or what the priced statement (FR-19) reads when the *retained set* is empty.

**Consequence.** A conspicuous asymmetry: the handled end was handled because someone walked it. The
unhandled end produces a *matter* where the product recommends reading nothing, states it in words
implying a positive judgement, and offers a *confidence bound* over the entire *corpus*.

### L-4. A human correction cannot cross **the line**

**Boundary.** UJ-3's stated premise: "Marc, junior associate. He knows one *pièce* the tool put in
the *discarded set* is the whole case, because he was on the call it summarises."

**Not covered.** FR-16 is categorical: the two sets "are derived from that order and the position of
**the line**; they are not stored as memberships." FR-20 gives Marc cell-by-cell editing of values,
and FR-18 gives him a one-click rejection of the tool's assessment recorded in the *audit record*.
None of these changes the *rank*, and FR-17 states "Changing **the line** never reorders the
underlying ranked order." So no user action moves one *pièce* from the *discarded set* to the
*retained set*. The only instrument that can is FR-19's line move, which is global.

**Consequence.** The narrated journey has no resolution in the requirements. To retain the one
document that decides the case, Marc must drag **the line** past it and thereby retain every
document ranked above it — UJ-4's own example puts that at 400 more *pièces* to read. The audit
record will show a global line move priced at 400 documents where the actual decision was about one,
and §13's question 2 ("Where did the tool place it, and on what basis?") answers correctly while
question 4 ("Did a human look at it?") records a validation act whose effect was nil. This is the
intersection of the two headline mechanisms — the ranked order and the human-in-the-loop correction
— and they do not meet.

### L-5. The *corpus* grows after **the line** was placed

**Boundary.** A second *import job* into a *matter* that already has a ranking, a placed line and a
completed *confidence bound*. UJ-1's own edge case establishes that partial re-import of a *matter*
is expected.

**Not covered.** Staleness has exactly two triggers in the document: FR-19, "Any existing *confidence
bound* for the *matter* is marked stale **on a move**", and FR-23, "A *confidence bound* computed
against a superseded **ranking version** or a superseded **position of the line**". A new import is
neither. Nothing states that ingesting into a ranked *matter* invalidates the ranking, re-triggers
ranking, or marks the bound stale. FR-30's staleness rule is scoped to configuration changes.

**Consequence.** 300 documents arrive; they are in the *corpus* and outside the ranking, so they are
in neither the *retained set* nor the *discarded set* — a third state FR-16 does not admit. The
*confidence bound* on screen still reads "1 400 in the *discarded set*", is not marked stale, and is
exportable as current under FR-26. The sentence the sceptic is buying (SM-1, the north star) is now
false and the product asserts it is fresh.

### L-6. Is **the line** an ordinal or a threshold?

**Boundary.** Any change to the population under a stored line: a new import (L-5), a re-ranking
(FR-16), or a user whose *RBAC scope* covers 60% of the *matter* (E-3 below).

**Not covered.** FR-17 stores "a position in the single ranked order" and "**The line**'s position
is stored as a per-*matter* parameter with a value". A position is ordinal; a value could be a score.
The document uses both readings and never fixes one. Under the ordinal reading, position 180 of 1 700
becomes position 180 of 2 000 and silently designates a different set. Under the score reading, the
retained count changes instead, and FR-19's priced statement ("400 more *pièces* to read") is
computed against a count that moves on its own.

**Consequence.** The one auditable parameter of the *matter* (Glossary: "An auditable per-*matter*
parameter with a value, an author and a timestamp") has an undefined referent, so the audit record's
answer to §13 question 3 — "Where was **the line** at the time?" — is not reconstructible.

### L-7. Ranking under a partially available model provider

**Boundary.** The configured language model rate-limits or drops halfway through ranking 100 000
*pièces*.

**Not covered.** FR-9 covers the *embedder* comprehensively and FR-10 covers index mismatches. The
ranking stage has no equivalent: no requirement states whether a partially ranked *matter* may carry
**the line**, whether unranked *pièces* are in the *discarded set* by default, or which error class
they take. FR-18's "no confidence could be computed" rule covers the display of a single *pièce* but
not the placement of the line over a population that is partly unscored. OQ-7 flags triage over a
partially *ingested corpus*; this is a fully ingested *corpus* that is partly *ranked*, and it is not
flagged.

**Consequence.** The default for an unscored *pièce* is whatever the sort does with a null — in
practice, the bottom of the order, i.e. the *discarded set*. The *confidence bound* then reports a
risk over a population that includes documents no model ever read, and §9's "never a
plausible-looking wrong answer" is violated at exactly the point the product's claim rests.

---

## 3. Sampling and the *confidence bound*

### S-1. A *discarded set* smaller than the sample size

**Boundary.** The *discarded set* holds 60 *pièces*; the user asks for 200, or asks for a target
bound whose required sample exceeds the population.

**Not covered.** FR-22: "The user sets a sample size, or requests a target *confidence bound* and is
given the sample size that achieves it." No requirement bounds the requested size by the population,
specifies with- or without-replacement drawing, or handles a target bound that no achievable sample
size reaches. The zero case is handled (§9, H-4); the smaller-than-requested case is not.

**Consequence.** At n = M the exercise is a census, not a sample, and the honest output is "every
discarded *pièce* was reviewed; none was relevant" — a stronger and categorically different
statement than FR-23's sentence. Producing "60 *pièces* sampled at random from the 60 in the
*discarded set*, 0 relevant; risk of having missed a relevant document below 4.8%" is a false
statement of residual risk over a fully reviewed population, said out loud, to a judge, by a lawyer
who was told every number in it is reconstructible.

### S-2. Sampling twice — no pooling rule, and no guard against sampling until satisfied

**Boundary.** Emmanuel completes a run, dislikes the number, and starts another over the same
*discarded set*, the same ranking version and the same position of **the line**.

**Not covered.** FR-24's append-only rule and FR-26's export ("all sampling runs and their
*confidence bounds*") ensure both runs are *recorded*. Nothing states which is canonical, whether
independent runs pool into one estimate, whether the second draw excludes *pièces* already verified
in the first, or whether the *confidence bound* displayed on the *matter* is the latest, the best or
the pooled one. FR-23 requires the sentence to be "copyable as text" and SM-1 makes it the north
star; the sentence is an artefact that travels alone.

**Consequence.** Two distinct failures. Statistically, repeated sampling until a favourable result
is a multiple-comparisons problem that invalidates the stated bound, and the record showing all runs
does not repair the copied sentence. Operationally, the second draw over an unfrozen population may
re-present *pièces* already adjudicated, so the reviewer's verdicts are not independent draws. R-5
("the *confidence bound* is wrong or misapplied... worse than having said nothing") is realised
through a path nothing in FR-22, FR-23 or OQ-4 anticipates.

### S-3. The draw's population is not frozen

**Boundary.** A sampling run is in progress while an *import job* runs, while another user edits, or
while another user moves **the line**.

**Not covered.** FR-22 records "its seed or its resulting identifier list — such that it is
reconstructible from the *audit record*". A seed alone is reconstructible only against a frozen,
identically-ordered population. Nothing freezes the *discarded set* for the duration of a run,
nothing rejects a seed-only record when the population is mutable, and L-1's unspecified tie-break
means the ordering the seed indexes into is itself unstable.

**Consequence.** SM-1's target — "100% reproducibility, asserted by an automated test that recomputes
from the export and compares" — is unachievable for any run whose *matter* was touched afterwards.
The north-star test either fails or is written against a frozen fixture, which is the shape of
failure §8 and FR-33 exist to prevent.

### S-4. The reviewer disagrees with every classification

**Boundary.** K = n. The sceptic marks all 200 sampled *pièces* relevant.

**Not covered.** FR-23 handles K > 0 in the direction of widening: "the sentence says so and the
bound widens accordingly; the product never suppresses or reframes an unfavourable result, and offers
to move **the line** rather than silently re-ranking." At K = n the bound is degenerate — the
sentence reads "risk below 100%" or equivalent — and the offered remedy (move **the line**) is
inadequate, because the finding is not that the line is in the wrong place but that the ranking
carries no signal. No requirement defines a point at which the system declares the ranking unfit, and
FR-17's "insufficient basis" refusal (L-2) is evaluated before ranking, never after evidence
contradicts it.

**Consequence.** The product's honest-result guarantee produces a sentence that is technically true
and operationally meaningless, and the *worklist* offers an action that cannot fix the problem. A
secondary effect follows from FR-22's live update ("Marking a sampled *pièce* relevant immediately
updates the projected *confidence bound* shown to the user, before completion"): the reviewer watches
the number degrade with each honest verdict, which is a structural incentive to stop early — measured
by SM-C3 and caused by an FR.

### S-5. The bound after new documents arrive

Covered under L-5. The staleness triggers in FR-19 and FR-23 do not include ingestion, so a
*confidence bound* remains marked current over a *discarded set* that has grown.

### S-6. The stated M is scope-relative but the sentence is absolute

**Boundary.** Two users with different *RBAC scopes* over the same *matter* each run a sample.

**Not covered.** FR-22 draws "over the whole *discarded set* **within the user's *RBAC scope***",
and FR-14 requires that "any *confidence bound* shown to a user are computed within that user's
*RBAC scope*, so the numbers themselves cannot leak". Both are correct as leak controls. But FR-23's
sentence — *"200 pièces sampled at random from the 1 400 in the discarded set"* — states M as a fact
about the *matter*, with no requirement that it be qualified as a fact about a scope. Nothing
reconciles two simultaneously valid, mutually inconsistent bounds for one *matter*.

**Consequence.** A correctly implemented privacy control makes the flagship artefact quietly
conditional. The lawyer says "1 400" to the court; the *matter* holds 2 100 discarded *pièces*, 700 of
them outside her walls. The statement is not false about the system and is false about the *matter*,
and §13's promise that "a reader with no access to the system" can reconstruct every number is
satisfied only if the export declares the scope it was computed under — which FR-26 does not require.

---

## 4. Audit

### A-1. FR-5's retry contradicts FR-21 and §9's append-only rule

**Boundary.** A *failure register* entry is retried and succeeds.

**Not covered.** FR-5: "Retrying a *failure register* entry re-runs *ingestion* for that *pièce*
only, and **on success removes it from the register** and increments the indexed count." FR-21: "No
control in the product performs a hard deletion of a *pièce*, a *chunk*, an *audit record* entry, a
*change log* entry **or a *failure register* entry**." §9: "Append-only where evidence is claimed.
The *audit record*, the *change log* and the *failure register* are append-only." FR-21's own test —
"a full sweep of user-reachable actions produces no reduction in the count of stored *pièces*,
*audit record* entries or *change log* entries" — omits the *failure register* from the swept
counts, which is where the contradiction hides.

**Consequence.** Three requirements cannot all be satisfied. If the entry is removed, §13 question 1
("is it in the *failure register* with which error class — and was it ever retried, by whom?") is
unanswerable and FR-21 is violated. If the entry is retained, FR-6's `submitted = indexed + failure
register entries` double-counts the *pièce* and SM-3 records a violation — which SM-3 defines as "a
release blocker, not a bug". The resolution (a resolved-state flag, and the invariant counting open
entries only) is not stated anywhere, so the invariant test and the retry path will be built by
different agents against different readings.

### A-2. No requirement makes an action fail when its *audit record* entry cannot be written

**Boundary.** The disk is full, the store is read-only, the audit partition is exhausted — and a
user moves **the line**, commits an *override*, or completes a sampling run.

**Not covered.** FR-24 states what the record must contain and that it is append-only. Nothing states
the transactional relationship between an action and its entry. §9's "fail loudly" rule enumerates
the acceptable failure outcomes as "a *failure register* entry, a halt, or a *worklist* line" — all
three of which are themselves writes to stores that are also full.

**Consequence.** The single most load-bearing property in the document degrades silently and in
exactly the way §1 says the rebuild exists to prevent: "every claim this product makes to a lawyer...
must rest on a deterministic, testable mechanism rather than on an intention written in a
specification." An action that succeeds while its record does not is indistinguishable, afterwards,
from an action that never happened — and §13's reader with only the export cannot detect the gap,
because the gap is an absence. There is no sequence number, no hash chain and no continuity check on
the *audit record* anywhere in the PRD, so tampering and truncation are equally undetectable.

### A-3. Two users acting on **the line** simultaneously

**Boundary.** A partner and an associate drag **the line** at the same moment; or one moves it while
the other is mid-sampling-run.

**Not covered.** FR-20 handles concurrency for *cells* — "Concurrent edits to the same cell by two
users are both recorded, in order, attributed; the current value is unambiguous and no edit is lost"
— and A-6 in the Assumptions Index scopes concurrency to "concurrent editing within one *matter*".
**The line** is not a cell; it is a single per-*matter* parameter (FR-17). No requirement gives it a
concurrency rule, and FR-19 requires recording "the priced statement that was shown at the moment of
the move" — a statement computed against a position that a second user has already changed.

**Consequence.** The *audit record* stores a priced statement that was never true, attributed to a
user who was shown it in good faith, against a position she did not move from. For the concurrent
sampling case: the run completes, is marked stale by FR-23 because the line moved beneath it, and an
hour of a senior lawyer's verdicts produces nothing — with no warning at any point that this was
happening, because nothing locks or notifies.

### A-4. An *audit record* entry for a *pièce* later found unreadable

**Boundary.** A *pièce* is indexed, ranked, justified, sampled — and later fails re-extraction, or
its OCR is redone under a new engine version, or storage corrupts it.

**Not covered.** FR-11 requires that "A quoted passage surfaced anywhere in the product resolves to a
*chunk* by identifier and matches its source by exact string containment", and FR-26 requires the
*audit drawer* to show "the retained extracts behind that confidence (each resolving to a *chunk* and
a source position)". Nothing covers a resolution that fails at read time. Nothing states what happens
to a *pièce* that transitions from indexed to unreadable — the *failure register* is defined as
"*pièces* submitted but not indexed", so this one does not qualify for it, and FR-6's invariant has
no bucket for it.

**Consequence.** An exported *audit record* contains an extract that no longer resolves. FR-26's
self-containment test ("a reader with the export and no access to the system can reconstruct every
number in it") passes at export time and the artefact rots afterwards, which is precisely the moment
it is used: the export exists to be read later, by a bâtonnier or a court, without the system.

### A-5. The *audit record* export is an uncontrolled content egress

**Boundary.** FR-26's export leaves the building — that is its purpose.

**Not covered.** §11 states: "Exactly two egress paths exist: the configured model provider... and
the user-initiated *content-free projection* (FR-32). Any third path is a defect, and a test asserts
their absence." The FR-26 audit export is a third path, and it is emphatically **not** content-free:
it carries retained extracts, *override* reasons verbatim, one-line justifications and *failure
register* filenames and submitted paths. Its only stated constraint is FR-26's "The export never
contains material outside the exporting user's *RBAC scope*" — a constraint on who may produce it,
not on what it may contain. No redacted or numbers-only tier is specified, although SM-1 only needs
the numbers, and FR-26 does not require that producing an export be recorded in the *audit record*
(FR-32 requires this for the diagnostic export; FR-26 has no equivalent bullet).

**Consequence.** The egress test asserted by §11 either fails on a required feature or is written to
exempt it, and the exemption is the whole *matter*'s privileged content in one file. An export
handed to opposing counsel to substantiate the *confidence bound* discloses the retained extracts of
every sampled *pièce*. The one act in the product that moves client content out of the firm on
purpose is the one act with no recorded trace of having occurred.

### A-6. No specified surface performs the "explicit validation act"

**Boundary.** Éléonore reads the 180 *pièces* above **the line** and the record must later show that
a human looked at them.

**Not covered.** FR-24 requires that "'Modified' and 'accepted as-is' are distinguishable in the
record. A value the user never touched is recorded as accepted only if she performed an explicit
validation act over it — not by default and not by the passage of time." §13 question 4 repeats it.
No FR in §4 defines the validation act: no control, no bulk affordance, no per-*pièce* gesture. FR-20
gives editing; editing is the *modified* branch.

**Consequence.** The *accepted-as-is* branch is required by the record and unreachable in the
product, so §13's question 4 answers "no human looked at it" for every document a lawyer read and
agreed with — the common case. If a bulk affordance is added late to close the gap, it becomes a
single click asserting human review over 180 documents, which is the record-that-looks-like-consent
failure §10 names explicitly ("ignored friction is worse than none because it produces a record that
looks like consent").

---

## 5. RBAC

### E-1. An *RBAC scope* that changes after indexing

**Boundary.** A *matter* is re-scoped: an associate joins the team, a Chinese wall is erected
mid-matter after a conflict is discovered, a *matter* is reassigned.

**Not covered.** FR-8 stamps the *RBAC scope* onto every *chunk* at write time as a mandatory,
non-nullable field, and asserts "that no code path can produce a *chunk* whose *RBAC scope* was
inherited from a global default rather than from its *matter*". FR-14 filters queries on that stamped
value. FR-30 makes "*RBAC scopes* and their assignment" *configuration-as-data*, editable per
*tenant*, and says a configuration change "is recorded in the *audit record* and marks derived
artefacts stale" — stale is not re-stamped. No requirement describes propagating a scope change to
existing *chunks*, and FR-10 forbids bulk operations on indexed material as a response to any
mismatch.

**Consequence.** The stamped scope and the configured scope diverge, and the pre-filter serves the
stale one, correctly and permanently. This is R-4 — "a professional-conduct violation, silently, with
no error message. The product's entire premise is void" — reached not by an attack but by an ordinary
administrative act. SM-6's adversarial suite issues queries against a static scope assignment and
does not mutate scopes mid-corpus, so the control the risk register names as the mitigation
("**Low if the tests hold. The tests are the control**") does not cover the case.

### E-2. A user losing — or gaining — access mid-session

**Boundary.** A scope is revoked while the user has a *matter* open, a sampling run in progress, an
export being produced.

**Not covered.** FR-14 constrains retrieval at query time. Nothing addresses already-rendered state,
an in-flight export, a resumable sampling run owned by a user who no longer has the scope, or the
lifecycle of that orphaned run (FR-22 requires an incomplete run to produce a *worklist* line to
resume it — on whose worklist?). The reverse case is equally unhandled: FR-28 requires the
*denominator* on screen "at all times" for the user's scope, with no invalidation on a scope change.

**Consequence.** Revocation is not a control until it reaches open sessions; a wall erected at 15:00
after a conflict check is a wall with a session-shaped hole in it. And an incomplete sampling run
belonging to a revoked user is either invisible (its *worklist* line vanishes with the scope, so the
run is abandoned silently — the outcome FR-22's resume line exists to prevent) or visible to someone
who cannot open it (FR-27's non-actionable-line defect).

### E-3. The *retained set* is scope-relative but **the line** is *matter*-global

**Boundary.** A user whose *RBAC scope* covers part of a *matter* opens the triage table.

**Not covered.** FR-16 holds "exactly one ranked order per *matter*"; FR-17 stores **the line** as
one per-*matter* position. Every view of that order is filtered by FR-14's pre-filter. Nothing
defines what a *matter*-global ordinal means inside a filtered view, nor what FR-19's priced
statement computes ("400 more *pièces* to read" — visible ones, or all?), nor whether a partially
scoped user may move a line whose position governs documents she cannot see.

**Consequence.** A user moves **the line** by two positions in her view and, in the *matter*, moves
it past thirty documents she has never seen — recorded in the *audit record*, under FR-19, as her
decision, with a priced statement computed over a different population than the one affected.

### E-4. The *failure register* is an RBAC blind spot carrying filenames and full paths

**Boundary.** FR-5 entries carry "filename, submitted path, *matter*, error class, timestamp". FR-28
puts the unreadable count on the home screen and makes it clickable: "Clicking the unreadable count
opens the *failure register* filtered to it."

**Not covered.** FR-14's pre-filter is specified for *retrieval*; FR-24 scopes the *audit record*;
FR-29 scopes reads by *tenant*. The *failure register* is scoped by neither in any explicit clause.
And structurally it cannot inherit the FR-8 mechanism: a *pièce* that failed ingestion never had a
*chunk* written, so the stamped *RBAC scope* that FR-14 filters on does not exist for it. A file that
failed before its *matter* could be determined has no scope at all.

**Consequence.** In litigation the filename is frequently the privileged fact —
`Fusion_ClientX_offre_revisee_confidentiel.pdf`, `Note_strategie_penale_MmeY.docx`. The register
enumerates them with full submitted paths, is reachable in one click from the home screen, is
exportable ("The *failure register* is exportable as a list, one *pièce* per line"), and is the one
surface where SM-6's zero-leak target has no corresponding pre-filter requirement to test.

### E-5. Nothing constrains the *RBAC scope* selectable at import

**Boundary.** FR-1: the user starts an import by "assigning it to a new or existing *matter* and
confirming its *RBAC scope*".

**Not covered.** FR-1 requires a scope to be present and non-empty and fails the job loudly
otherwise. No requirement constrains the selectable scope to a subset of the importing user's own,
nor states who may create a *matter*, nor who may create a scope.

**Consequence.** Import is a write path with no privilege ceiling. A user assigns a *matter* to a
scope she does not hold (material becomes invisible to her supervisor and to the *denominator* he
sees) or to a scope broader than her own (material she controls becomes readable by a group she chose).
Either direction is a Chinese-wall breach performed through the product's single most-used gesture.

### E-6. No surface exists to administer the configuration the increment requires

**Boundary.** First run of a fresh installation. FR-14: "A user with no *RBAC scope* receives an
empty *corpus*, not the whole *corpus*. Fail-closed is asserted by test, including for administrative
and system identities."

**Not covered.** FR-30 requires *RBAC scopes* and their assignment, the taxonomy, the model provider,
thresholds and interface language to be "editable per *tenant* without a code change or a deployment
of different code". §5 and §2.2 remove the surface that would edit them: "**No admin cockpit.** There
is nothing installed to operate. Its foundation — *configuration-as-data* — is in scope; the operator
interface is not." Nothing bridges the two.

**Consequence.** Correct fail-closed behaviour plus no provisioning surface equals an installation in
which nobody can see anything and nobody can grant access — at a site APX has no telemetry into
(§17) and reaches only by telephone. The scope-assignment surface will be built anyway, late, by
whoever hits the wall on installation day, without the requirements, tests or audit-record coverage
that FR-30 and FR-24 would have given it. That is the shape of every leak this document is written to
prevent.

---

## 6. Operational

### O-1. Disk full, and the append-only stores' own write failures

Covered as A-2 for the *audit record*. The same unhandled boundary applies to the *failure register*
and the *change log*: FR-6's invariant must hold "at all times", and the mechanism that maintains it
is itself a write. No error class in FR-5 covers resource exhaustion (see I-4), and there is no
requirement for a pre-flight capacity check before an *import job* the design target sizes at 100 000
documents.

### O-2. The model provider unreachable, and the offline claim

**Boundary.** An on-premise installation with no internet, or a provider outage.

**Not covered.** §14 requires that an on-premise installation "function without internet access
except for the configured model provider, whose absence must degrade loudly rather than silently",
and §5 puts a fully local model out of scope. Which capabilities survive that absence is never
enumerated. FR-18's one-line justifications, FR-36's language-carrying model calls, the ranking
itself, FR-19's priced statement and FR-23's sentence are all model-dependent to an unstated degree —
FR-36 says the *confidence bound* sentence is machine-generated user-facing text produced by the
model, which makes a statistical statement dependent on a network call.

**Consequence.** "Degrade loudly" is satisfied by a product that does nothing. A firm that bought
on-premise for confidentiality discovers that triage — the increment — requires the one egress path
they bought the product to avoid, and that the *confidence bound* sentence cannot be regenerated
offline from an *audit record* that SM-1 promises is self-sufficient.

### O-3. Clock skew and out-of-order append

**Boundary.** A multi-user installation with an unsynchronised workstation clock; an air-gapped
machine with no NTP; a clock corrected backwards.

**Not covered.** FR-24 requires a timestamp on every entry; FR-20 requires concurrent edits recorded
"in order"; §9 requires reproducibility "on a different machine and after a restart"; FR-23 marks
bounds stale by supersession, which is an ordering judgement. No requirement names an authoritative
clock, requires server-side timestamping, or provides a monotonic sequence independent of wall-clock
time.

**Consequence.** "In order" and "current value is unambiguous" (FR-20) are decided by whichever
workstation is fast. An append-only record whose ordering is wrong is worse than one with no
timestamps, because it is defensible-looking: §13's questions are answered confidently and
incorrectly, and the *change log* shown next to the row attributes the surviving value to the wrong
author.

### O-4. The software is updated while an *import job* is in flight

**Boundary.** §16's update model — "generated and shipped blind, installed by agreement" — meets
FR-2's resumable job, which by design survives restarts and can span days at the design target.

**Not covered.** Nothing requires an update to refuse to start while a job is in flight, nothing
requires a resumed job to complete under the schema, chunking and ranking versions it started under,
and nothing records that a job spanned a version change. FR-2's resume rule ("resumes from the last
committed unit of work") has no version-compatibility condition on the checkpoint. FR-8 rejects a
lossy *migration*; it does not address an in-flight *producer*. FR-11 only requires that chunks
produced under different configurations be *distinguishable* — which they will be, after the fact,
inside one *matter*, with no record of why.

**Consequence.** A single *matter* holds *chunks* from two chunking configurations and two schema
versions, produced by one *import job*, with FR-11's determinism claim ("re-chunking the same *pièce*
with the same configuration produces identical *chunks* with identical identifiers") true in the
letter and useless in practice. The resumed half is not comparable to the first half, the ranking
runs over both, and R-10's version drift arrives inside one installation before there is a second
one.

### O-5. Non-deterministic re-extraction breaks stable identity

**Boundary.** A *failure register* entry is retried after an OCR engine or model version change and
succeeds with different transcribed text.

**Not covered.** FR-4 derives identifiers from content; FR-11 requires deterministic chunk
boundaries and identifiers "with the same configuration". OCR output is configuration-dependent and
version-dependent, and FR-3 records "the extraction method used (e.g. native text, OCR)" without
requiring the engine version on the *pièce* (FR-8 mandates a schema version, not an extractor
version).

**Consequence.** The retried *pièce* hashes to a new identity, so it enters as a new *pièce* rather
than resolving the register entry — compounding A-1. Any *audit record* entry, extract or
*confidence bound* referencing the old identity dangles. The mixed-provenance detection FR-9 provides
for the embedder ("so a mixed-provenance *corpus* is detectable rather than merely suspected") has no
counterpart for OCR.

---

## 7. Cross-cutting

### X-1. The *worklist* becomes a log at the design target

**Boundary.** The PRD's own example *denominator*: "97 200 / 100 000 indexed · 2 800 unreadable".

**Not covered.** FR-27 states that lines are generated by, at minimum, "*failure register* entries,
low-quality OCR flags, *pièces* with no computable confidence, incomplete sampling runs, stale
*confidence bounds*, halted *import jobs*, and index-mismatch halts", that "Completing the action
removes the line", and that "A line is never removed by the passage of time, by a background process,
or by being viewed". UJ-1 shows aggregated lines (*"14 pièces illisibles"*) and FR-27 mentions "a
count where a count applies", but no requirement defines the aggregation key, the aggregate line's
completion semantics (does closing 13 of 14 remove it?), an ordering, a cap, or a bulk action.

**Consequence.** 2 800 *failure register* entries plus OCR flags plus unscored *pièces* produce a home
screen that is exactly what FR-27's own description forbids — "**Not a log.**" — and the user learns
to dismiss it, which is SM-C2's defined failure mode and R-6 realised on day one, at the scale the
PRD selected as its design target. There is also no bulk retry: FR-5 retries "that *pièce* only".

### X-2. Every *pièce* larger than the boundary the requirements never draw

The document sets a design target of 100 000 *documents* per *tenant* and asserts scale-sensitive
consequences at it. It sets no bound on: the size of one *pièce* (I-4), the depth of container
nesting (I-1), the number of attachments on one message, the length of one *chunk*'s source position
reference, the number of *matters* in a *tenant*, the number of concurrent *import jobs* on one
*matter*, or the number of *pièces* in a single *failure register* export. OQ-6 flags the absence of
*performance* targets; it does not flag the absence of *capacity* boundaries, which are the ones that
turn into crashes rather than into slowness.

### X-3. Concurrent *import jobs* into one *matter*

**Boundary.** Two users import two drives into the same *matter* at the same time; or one user starts
a second job before the first completes.

**Not covered.** FR-4 handles "the same *pièce* processed concurrently by two workers" — within the
scope of the deduplication rule. Nothing defines the *denominator* while two jobs are open (FR-6
requires it "at all times"), which job's completion summary reports a *pièce* both jobs submitted
(FR-7 requires the summary to distinguish "newly indexed" from "recognised as already present" — the
second job's answer depends on the first job's progress at an unspecified moment), or whether the
second job may start at all.

**Consequence.** FR-7's counts become racy and non-reproducible, and UJ-1's edge case — the promise
that re-importing overlapping material is reported honestly rather than silently, which A-3 says
exists because "silence here reads as data loss" — produces a number that changes if the same two
jobs are run again.

---

## 8. Summary

**44 genuinely unhandled boundaries.** Distribution: import 12 (I-1…I-12) · ranking and **the line**
7 (L-1…L-7) · sampling 5 (S-1…S-4, S-6; S-5 is a cross-reference to L-5) · audit 6 (A-1…A-6) · RBAC 6
(E-1…E-6) · operational 5 (O-1…O-5) · cross-cutting 3 (X-1…X-3).

Four of them are contradictions **between** existing requirements rather than gaps — A-1 (FR-5 vs
FR-21 vs §9), A-5 (FR-26 vs §11), I-8 (FR-4 vs itself), I-11 (FR-5 vs FR-27 vs UJ-1) — and those are
the cheapest to close, because both halves are already written.

The heaviest by consequence:

1. **E-1** — a scope change after indexing leaves the stamped *RBAC scope* on every *chunk* stale;
   the pre-filter then serves the wrong wall, correctly and silently. R-4's stated mitigation is
   "the tests are the control", and SM-6 does not mutate scopes.
2. **L-5 / S-5** — ingestion into a ranked *matter* is not a staleness trigger, so the *confidence
   bound* stays marked current while its population grows. The sentence a lawyer says to a court
   becomes false and the product asserts it is fresh. R-5, through a path OQ-4 does not reach.
3. **A-2** — no requirement makes an action fail when its *audit record* entry cannot be written, and
   the record has no sequence, hash chain or continuity check. Its incompleteness is undetectable by
   the reader §13 is written for.
4. **L-4** — no mechanism moves one *pièce* across **the line**, so UJ-3's stated premise has no
   resolution: retaining the one document that decides the case requires retaining the 400 above it.
5. **I-1 / I-2 / I-3** — container expansion is unspecified, which leaves FR-6's inventory guarantee
   arithmetically undefined and lets one *failure register* entry stand for 500 hidden *pièces*
   behind a *denominator* that reads "· 1 unreadable".

Two open questions in §19 should absorb findings rather than be answered around them: **OQ-4** (the
estimator) must take I-10 near-duplicates, S-1 census-vs-sample, S-2 repeated sampling and S-3
population freezing as inputs; **OQ-7** (partial *corpus*) should be widened to L-7 partial *ranking*,
which is a different condition on the same surface.

---

## 9. Nearly flagged — handled, with the requirement that handles it

Recorded so that silence is legible.

- **H-1. Empty folder.** FR-1: "Selecting a folder containing zero readable files produces a completed
  *import job* with a *denominator* of 0/0 and an explanatory *worklist* line, not an error dialog and
  not a silent no-op." *(The adjacent case — a folder where every file fails — is not this case, and
  is reached through I-12 and L-2.)*
- **H-2. Re-importing the same folder; an overlapping folder.** FR-4: "Importing the same folder twice
  into the same *matter* leaves the *corpus* count unchanged... and reports the recognised-already-
  present count as its own line in the completion summary. Asserted by test." Plus the UJ-1 edge case
  and SM-4. *(The identity contradiction underneath it is I-8.)*
- **H-3. One document in two *matters*.** FR-4: "Importing the same file into two different *matters*
  produces two *pièces*, because *matter* is part of identity and confidentiality follows the *matter*.
  Cross-*matter* deduplication is explicitly not performed."
- **H-4. A *discarded set* of zero.** FR-19: "Moving **the line** to retain everything states that the
  *discarded set* is empty and no *confidence bound* applies — it never reports a risk of 0%", plus
  the UJ-4 edge case.
- **H-5. The bound after **the line** moves.** FR-19: "Any existing *confidence bound* for the *matter*
  is marked stale on a move and is not reused; a *worklist* line offers re-sampling." FR-23: "A
  *confidence bound* computed against a superseded ranking version or a superseded position of **the
  line** is displayed as stale and cannot be exported as current."
- **H-6. An abandoned sampling run.** FR-22: "An abandoned run produces no *confidence bound*, is
  stored as incomplete, and produces an actionable *worklist* line to resume it. Asserted by test."
  Plus the UJ-2 edge case. *(Its RBAC lifecycle is E-2.)*
- **H-7. An *override* with an empty reason.** FR-25: "An empty or whitespace-only reason is rejected."
  The weak-but-non-empty reason is already flagged by the document itself at A-14 and SM-C2.
- **H-8. Counts and denominators as a leak channel.** FR-14: "The *denominator* and any *confidence
  bound* shown to a user are computed within that user's *RBAC scope*, so the numbers themselves
  cannot leak the existence of material they may not see", and the adversarial suite asserting "zero
  out-of-scope metadata — including counts, snippets, identifiers, filenames and *denominator*
  figures". *(The consequence this control creates for the sayable sentence is S-6; the surface it
  does not reach is E-4.)*
- **H-9. Concurrent edits to one cell.** FR-20: "Concurrent edits to the same cell by two users are
  both recorded, in order, attributed; the current value is unambiguous and no edit is lost."
  *(The line is not a cell — A-3. The ordering it depends on is O-3.)*
- **H-10. A crash mid-import.** FR-2: "Killing the worker process mid-job and restarting it resumes
  from the last committed unit of work... Asserted by test with an induced kill at ≥3 different points
  of a run." *(What it resumes onto is I-4; what it resumes from is I-5; what version it resumes under
  is O-4.)*
- **H-11. Lawful erasure vs never-hard-delete.** Already named and deliberately unresolved: FR-21's
  assumption, §11 Retention, OQ-8 and A-13.
- **H-12. Triage over a partially ingested *corpus*.** Already named: SM-C4, OQ-7, A-17. *(Partial
  ranking over a complete corpus is a different condition — L-7.)*
- **H-13. The index self-deleting on mismatch; the silent fallback embedder.** FR-10 and FR-9, both
  written as explicit negations with tests, plus SM-5.

