---
stepsCompleted: [1]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md
  - _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-apx-mvp-2026-07-21/WORK-BREAKDOWN.md
---

# APX MVP — First Increment: Mass-Document Triage - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for APX MVP — First Increment: Mass-Document Triage, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR-1:** Folder selection as the whole onboarding gesture — An authenticated user can start an *import job* by selecting a filesystem folder (including a mounted removable drive), assigning it to a new or existing *matter* and confirming its *RBAC scope*, with the *case theory* as the only optional field and no further mandatory configuration screen.

**FR-2:** Non-blocking, resumable *import job* — An *import job* runs in the background and survives interruption without losing or duplicating work, resuming from the last committed unit, quarantining a poison unit rather than retrying it forever, and bounding memory per unit as well as per job.

**FR-3:** Multi-format extraction — *Ingestion* extracts text and structure from `.msg` (headers, reply chains, embedded attachments), born-digital PDF, scanned PDF via OCR, `.docx`, `.xlsx` and standalone images, recording the extraction method and extractor version, entering unsupported and empty extractions in the *failure register*, and maintaining a corpus-wide OCR figure per *matter* and per *tenant*.

**FR-4:** Idempotent *ingestion* with stable identifiers — Re-submitting material already in the *corpus* neither duplicates it nor destroys it: every *pièce* identifier is a deterministic function of (content, *matter*), path is an attribute and not identity, every *custodian* survives deduplication, and changed content produces a new *pièce* carrying a `supersedes` relation.

**FR-5:** The *failure register* — Every *pièce* that fails to enter the *corpus* is enumerated with filename, submitted path, *matter*, *custodian*, a stable error class, a cardinality, a resolution state and a retry action; entries are resolved by state change and never removed, every entry's stated action must exist, and a bulk retry produces one *audit record* entry naming the set.

**FR-6:** The inventory guarantee and the permanent *denominator* — The system can always state exactly what it was given and what it did with it: `submitted = in corpus + open failure register entries`, counted in *pièces*, displayed persistently and never rounded, with filesystem noise declared as its own named count and the *scoped denominator* distinguished on its face from the *matter*'s *denominator*.

**FR-7:** Completion summary — When an *import job* finishes the user gets human tasks and a summary rather than a log, opening on the *denominator* and the generated *worklist* lines, distinguishing newly indexed from already present, noise-excluded, container-expanded and registered failures, reachable again later, with only one *import job* open on a *matter* at a time.

**FR-8:** The frozen *payload schema* — Every *chunk* written to the *corpus* carries a complete *payload schema* record with no nullable mandatory field and no default *RBAC scope*, the full extracted text of a *pièce* is stored addressably and separately from its *chunks*, the schema carries an explicit version, and a write missing any mandatory field is rejected at the boundary.

**FR-9:** The embedder fails loudly — Semantic embedding either works as configured or halts the affected unit of work into the *failure register*; there is no hash-based, bag-of-words or fallback embedder available at runtime under any configuration, including test and development.

**FR-10:** The index never deletes itself — No automatic process may destroy indexed material: destructive index operations are reachable from exactly one named administrative entry point, a dimension or schema mismatch halts the unit and leaves the *corpus* intact and queryable, and recovery does not require re-indexing the whole *corpus*.

**FR-11:** Chunking with provenance to source position — Every *chunk* traces to the exact position it came from, chunk boundaries are deterministic under a fixed configuration, every quoted extract is verified by exact string containment at the moment it is shown, and a resolution that fails is surfaced as such and marks the containing export degraded.

**FR-12:** Semantic retrieval, marked *suggestive* — A user can retrieve *pièces* by meaning, ranked with a stated k, and the result set declares *truth status* = **suggestive**, never displays a count phrased as a total, and can never be labelled or exported as **exhaustive** under any similarity threshold.

**FR-13:** Deterministic exhaustive search — A user can obtain the complete, untruncated set of *pièces* matching a *deterministic expression* over the whole indexed *corpus* within their *RBAC scope*, running over stored full text and over names, under declared French normalisation semantics, and every absence statement discloses the *scoped denominator*, the open register entries, the unopened containers of unknown cardinality and the OCR-derived share.

**FR-14:** *RBAC scope* as a query pre-filter — No user ever receives material outside their *RBAC scope* and the filtering happens before retrieval rather than after, asserted by an adversarial suite that mutates scopes mid-*corpus*, mid-session and mid-*sampling run*, extends to counts, snippets, filenames and *scoped denominator* figures, and reaches open sessions within a bounded interval.

**FR-15:** Every result set declares its *truth status* — *Truth status* is a property of every result set returned by any engine, present in the interface, in every export and in the *audit record*, visually and verbally distinct, and no interface element merges results from both engines into one undifferentiated list.

**FR-16:** One ranked order, nothing deleted, nothing categorised — The system holds exactly one ranked order per *matter* per *ranking version*; the *retained set* and *discarded set* are derived from that order, **the line** and the *pins* rather than stored as memberships; no triage operation deletes a *pièce* or excludes it from retrieval; and every surface naming a set names the *ranking version* it means.

**FR-17:** The tool draws **the line** — After ranking, **the line** has a system-chosen position with a stated basis and is stored as an ordinal cut over a named *ranking version* together with the identity of the last retained *pièce*, with three configured refusal conditions, and a user whose scope covers only part of a *matter* may not move it.

**FR-18:** Per-*pièce* confidence and a one-line reversible justification — Every *pièce* in the ranking carries a confidence value and a one-line justification in the user's language, generated above **the line** and in a configured band below it with on-demand backfill elsewhere, expandable into the *audit drawer*, reversible in one recorded action, and never shown with a default or imputed confidence.

**FR-19:** Moving **the line** is priced — While a user repositions **the line**, the interface states for the candidate position the change in the number of *pièces* to read and the change in the estimated prevalence of relevant material in the resulting *discarded set*, labelled on screen as a projection from the ranking rather than a sampling bound, calibration-tested against the *gold set*, serialised against concurrent moves, and recorded with the move.

**FR-20:** The editable cell-by-cell table with a live *change log* — Every editable value is editable in place, committing an edit changes that cell and nothing else, no edit triggers regeneration or re-ranking of any other row, each edit produces an immediate before→after *change log* entry ordered by a server-assigned monotonic sequence, and no bulk operation on the table is undetectable.

**FR-21:** Never hard-delete — No control in the product performs a hard deletion of a *pièce*, a *chunk*, an *audit record* entry, a *change log* entry or a *failure register* entry; anything a user could read as deletion is a reversible, labelled, recorded state change, asserted by a bounded runtime probe over an enumerated registry of user-reachable actions.

**FR-22:** Random draw from the *discarded set* — A user can draw a verifiably random sample without replacement from the *discarded set* within their *RBAC scope*, over a population frozen and recorded as an explicit identifier list bound to a *ranking version*, a position of **the line** and a scope, with the census case labelled as a census, the ritual sized before it starts, batching across sessions, early stopping only inside the validated estimator, and an abandoned run producing no bound.

**FR-23:** The *confidence bound* as a sentence — A completed *sampling run* produces a copyable sentence stating a prevalence bound under a hypergeometric (finite-population) estimator with its confidence level, *matter*, *ranking version*, *case theory* version, position of **the line** and *RBAC scope*, never worded as the probability that nothing was missed, every number reconstructible from the *audit record* alone, and marked stale when its inputs or its population change.

**FR-24:** The *audit record* — Every decision that matters leaves an append-only, attributed, wall-clock-and-sequence-stamped trace scoped by *tenant* and *RBAC scope*, recording validations, *case theory* versions, *ranking versions*, modified-versus-accepted values, every position of **the line**, every *pin*, every *sampling run*, every *override*, every retrieval, every *import job*, every configuration change and every scope grant, revocation and re-scope.

**FR-25:** *Overrides* with a mandatory one-line reason — Any action contradicting a machine assertion made with stated confidence, removing a *failure register* entry without successful *ingestion*, or bypassing a system guard is classified as an *override* and cannot be committed without a free-text reason stored verbatim, attributed, timestamped, exported and countable separately from ordinary modifications.

**FR-26:** The *audit drawer* and its export — From any *pièce* the *audit drawer* opens on its confidence, the *retained extracts* behind it and the proposed *audit record* entry with reversible actions; the *matter*'s record is exportable within the user's *RBAC scope* in two tiers with numbers-only as the default, is self-contained so a reader with no access to the system can recompute every number, and producing it is a named egress path recorded in the *audit record*.

**FR-27:** The *worklist*, actionable lines only — The home screen's top zone is a queue of human tasks, each phrased in the user's language with a count and a single click-through to a surface where the action can be performed, exposing no technical state or job identifier, aggregated by (*matter*, line type, error class) with a configured display cap, and removed only by completing the action.

**FR-28:** The permanent *denominator* on the home screen — The *scoped denominator* is displayed at all times alongside the *worklist* in the stated form, labelled as scope-relative, never as a percentage alone and never as a health indicator, with the not-indexed count clicking through to the filtered *failure register* and recomputed within a bounded interval after a scope change.

**FR-29:** Tenant isolation — Data, configuration and identities belong to exactly one *tenant* and never cross: every stored record carries its *tenant* enforced at the write boundary, every read is constrained by *tenant* before *RBAC scope*, identity and authorisation are properties of the application rather than of the hosting environment, and no *tenant*'s data computes anything shown to another.

**FR-30:** Configuration-as-data — Per-*tenant* behaviour is data rows editable through the FR-50 surface without a code change or a different deployment, no *tenant*-specific identifier or name appears in source, every key named in documentation exists and is asserted to exist by a test, every key has a default, no default disables the guarantee its key governs, and a change affecting retrieval, ranking or the estimator is recorded and marks derived artefacts stale.

**FR-31:** The *content-free projection* primitive — There is exactly one registry of named projectors through which information *about* a *tenant*'s data is emitted, open by construction, with content-freedom enforced structurally by a seeded-token test over every registered projector, a build failure for any emission path outside the registry, and an attestation floor for text-derived projectors.

**FR-32:** The client-pushed diagnostic export — The firm can send APX a diagnostic it has inspected in full in readable form before it leaves; there is no inbound channel by which APX can trigger or fetch one; producing it is recorded; and there is no telemetry, enforced as a structural property over the enumerated outbound adapters.

**FR-33:** One *ingestion* path — no fixture layer, no demo override — No code path substitutes stored, hand-authored or generated content for a live response from a working component under any flag or build configuration; every configured corpus including any evaluation corpus enters through *ingestion* exactly as client material does; test fixtures are unreachable from runtime code; and the v1 fixture layer is deleted rather than disabled.

**FR-34:** Namespaced translation keys, no silent fallback — Every user-visible string is referenced by a structured namespaced key, a natural-language string is never used as a key, a missing translation fails the build rather than falling back silently at runtime, and key-set parity plus per-route coverage are asserted by test.

**FR-35:** Locale-aware dates, numbers and sorting — No date, number or currency format is hard-coded to a locale anywhere in the code; rendered dates use the user's locale while stored and exported dates use an unambiguous locale-independent representation; a *pièce*'s own date and its ingestion timestamp are rendered distinguishably; and list sorting respects the active locale's collation.

**FR-36:** The language reaches the language model — Every request to a language model carries an explicit language for the expected output derived from the user's locale or *tenant* configuration, machine-generated user-facing text is produced in that language, the source *pièce*'s language is stated where it differs, and language selection is *configuration-as-data* per *tenant* and per user.

**FR-37:** The optional *case theory* — The lawyer can state in free text and in her own language what she is trying to establish, at import or at any later moment; it is never mandatory and never blocks anything, every rewrite produces a retained new version recorded in the *audit record* and offers an explicit user-initiated re-rank, and every artefact derived from a ranking names the *case theory* version or states explicitly that none existed.

**FR-38:** The *relevance judgement* — a cascade, cheap filters first — Every *pièce* in a *matter* receives a relevance assessment produced by a three-stage cascade — deterministic filters and near-duplicate grouping, then cheap semantic scoring over existing embeddings, then LLM judgement only on the uncertain band plus a mandatory calibration sample — with the stage-3 share measured per run, near-duplicate families judged as a family, and provider failure leaving a *pièce* explicitly unscored rather than scored zero.

**FR-39:** The ranked order and the *ranking version* — Ranking is an explicit act producing exactly one ranked order per *matter* together with a *ranking version* recording the complete identity of what produced it, reproducible *pièce* for *pièce* under a fixed version and *corpus*, with a deterministic recorded tie-break, and emitting a per-*matter* review-effort estimate; a ranking that cannot be produced fails loudly rather than producing an arbitrary order.

**FR-40:** Per-*pièce* labelling against the *tenant*'s triage taxonomy — Every *pièce* in a ranking carries exactly one label from the *tenant*'s configured triage taxonomy or the explicit value `unlabelled`, with no null and no default; changing a label never changes a *pièce*'s position or moves it across **the line**; a label change is an ordinary cell edit surviving re-ranking as human-set; and a taxonomy change never silently remaps existing labels.

**FR-41:** The justification, derived from named evidence — Every justification is generated from a stated input set — the *case theory* version or the named intrinsic signals, plus the specific *retained extracts* the *relevance judgement* used, each named by *chunk* identifier and resolvable to a source position — each extract passing exact-containment verification when shown, with the interface stating plainly that the extracts are the control and the sentence is not evidence.

**FR-42:** Per-*pièce* confidence is derived, never self-reported — The confidence attached to a *pièce* is derived from observable quantities such as score margin or cross-stage agreement, never from a figure the language model states about itself, with the derivation method recorded in the *ranking version*, calibrated against the *gold set*, and never imputed where it could not be derived.

**FR-43:** Moving a single *pièce* across **the line** — the *pin* — A user can pin a *pièce* into or out of the *retained set* in one action from the triage table, the *audit drawer* or a *sampling run*, changing the *retained set* by exactly one *pièce* without moving **the line** or the ranked order, requiring a one-line reason recorded as an *override*, surviving re-ranking, and marking any existing *confidence bound* stale.

**FR-44:** The *pièce* viewer — Every format FR-3 extracts is rendered rather than merely extracted and is openable at the highlighted passage from any *chunk* or *retained extract*, with progressive loading above a configured bound, the *RBAC scope* pre-filter applied so an out-of-scope *pièce* is not renderable and its existence not disclosed, rendering inside the *tenant* boundary, and every opening recorded.

**FR-45:** The *validation act*, and no undetectable bulk acceptance — "Accepted as-is" exists only where an explicit per-*pièce* *validation act* occurred, never by default, elapsed time, scroll position or screen visit; each act records actor, timestamp, sequence, *matter*, *pièce*, *ranking version*, the values accepted and whether the *pièce* was opened in the viewer first; and a bulk act is permitted but produces one marked entry per *pièce* carrying the batch size and identifier.

**FR-46:** Export of the *retained set* — The *retained set* is exportable within the exporting user's *RBAC scope* as an ordered, numbered list carrying per-*pièce* identity, title, date, *custodian*, label, rank, confidence, justification, validation and any *pin*, in the order adjusted by pins, naming the *ranking version*, *case theory* version, position of **the line** and scope, marking superseded *pièces*, offered machine-readably and in pasteable form, and recorded in the *audit record*.

**FR-47:** Encryption at rest and in transit — All *tenant* data at rest and all network traffic carrying *tenant* data or credentials is encrypted in a hosted deployment and on a firm's own machine alike, with the vector column and the deterministic text index as named exceptions protected by volume- or cluster-level encryption, and a deployment started without encryption or without a key fails to start.

**FR-48:** Authentication and session handling — Identity, authentication and session handling are properties of the application and not delegated to a hosting provider, with a current password-hashing function and per-credential salt, no reversible storage, configured absolute and idle session lifetimes invalidated on password change, scope revocation and sign-out, a configured lockout or rate limit, and *configuration-as-data* multi-factor authentication.

**FR-49:** Grant-time authorisation and *RBAC scope* administration — Creating a scope, granting one, revoking one and re-scoping a *matter* are privileged acts each requiring an explicit administrative grant, recorded with actor, subject, scope, authority and timestamp, and reversible; there is no implicit superuser; and a re-scope takes effect at the next query with nothing to propagate and no half-stamped window.

**FR-50:** The minimal configuration and provisioning surface — One per-*tenant* surface reads and changes every *configuration-as-data* value of FR-30 and provisions a *tenant*, its first administrative user, its *RBAC scopes* and its taxonomy on first run; every change is audited, schema-validated, reversible and marks derived artefacts stale; it is inside the *tenant* boundary, is never cross-*tenant*, and is the only mechanism by which configuration changes.

**FR-51:** Secret and key management — Model-provider credentials, embedder credentials, encryption keys and every other secret are held outside the application's own data stores, are never written to a log, a diagnostic, an export or an *audit record* entry, are never redisplayed after entry, are rotatable without redeployment and without re-indexing, and appear in no source or example configuration.

**FR-52:** Backup, restore and disaster recovery — The product produces a complete, encrypted, restorable backup of a *tenant* on a configured schedule and on demand inside the *tenant* boundary; restore is exercised rather than assumed and reproduces an identical *denominator*, ranked orders, audit sequence and *confidence bounds*; backup failure is a persistent *worklist* line; and the storage footprint at the *design target* is computed and stated, with a pre-flight capacity check refusing an *import job* that cannot fit.

**FR-53:** *Audit record* continuity — An action whose *audit record* entry cannot be written fails, atomically, rather than succeeding unrecorded; entries carry a monotonic sequence number from a single authority and a chain value over the previous entry so that a gap, reordering or truncation is detectable by a reader holding only the export; the chain is verified on restore and a failed verification is surfaced, never silently repaired.

**FR-54:** The corpus and *gold set* pipeline — The evaluation corpora are acquired, licence-cleared and assembled as configured data sources entering through *ingestion*; the mechanical degradation pipeline is part of the test surface, each degradation asserted against the *failure register* class it must produce; the *gold set*'s relevance judgments are mapped onto this product's notion of relevance in a written, versioned, reviewable mapping; and no ranking or triage code merges before recall executes against the *gold set* in CI.

**FR-55:** The offline fitness function, executed in CI — A CI job boots the application in a network-isolated container with no hosted-provider service reachable and no outbound network except a stubbed model endpoint and asserts that it starts, ingests, indexes, retrieves over both engines, ranks, places **the line**, produces an *audit record* and exports; it runs from the first week of the build; and it enumerates which capabilities do not survive the model provider's absence, the *confidence bound* sentence being required to render offline from the *audit record*.

**FR-56:** Structural properties, enforced in CI — Where this document asserts that no code path does something, a named static check over the source decides it and a violation fails the build; each property names the check that enforces it and the file or pattern it inspects; a property with no check is not a property; and the three verbs — *asserted by test*, *enforced as a structural property*, *asserted by review* — are never conflated.

**FR-57:** Container expansion and the unit of the *denominator* — Containers are expanded with configuration-bounded recursion depth and expansion ratio, their members becoming *pièces* carrying provenance through the container and inheriting its *custodian*; a container that cannot be opened is one register entry of cardinality `unknown` stated in words wherever a total appears; and the unit of the inventory guarantee is the *pièce* counted after expansion, frozen at the completion of enumeration-and-expansion.

**FR-58:** Freshness and staleness of derived artefacts — A derived artefact is marked stale when any input in the complete enumerated trigger list changes — including any ingestion into the *matter* — cannot be exported or copied as current while stale, is visually distinct wherever it appears, and is never un-staled by the passage of time, a background recomputation or being viewed, only by an explicit user-initiated recomputation producing a new artefact.

**FR-59:** The usability gate — a checklist, a keyboard and one token set — A versioned phrasing checklist is reviewed against every user-facing surface before a release candidate with each item's verdict recorded with its reviewer and date, a failed item blocking the candidate or being recorded as an accepted exception; every *worklist* action and every triage-table edit is reachable and completable by keyboard alone; and no colour, spacing or type value appears outside one token set.

**FR-60:** The *matters* zone — "where are my matters?" — Below the *worklist*, the home screen lists the *matters* within the user's *RBAC scope* with the state of each — *scoped denominator*, running *import job*, ranking presence and staleness, open *sampling run*, last touched — as navigation and never as a task, bounded and ordered by last activity, never merged with or counted as a *worklist* line, and never pushing the *worklist* off the top of the screen.

**Count: 60 functional requirements, FR-1 through FR-60, no gaps.**

**Ambiguities found during extraction** (recorded, not resolved here):

- **FR-19 and FR-23** are conditional on an estimator that is decided in approach but proven only by simulation in CI. If the validation cannot be made to pass, what ships is the counts-only sentence with no bound and no projected figure. Two materially different shipped behaviours sit behind one FR number each.
- **FR-6** forbids "a third bucket" while itself adding a fourth named count (filesystem noise) and while FR-57 makes an unopened container a non-numeric quantity. Three legitimate readings of the same total exist; AD-38 resolves this by making the *denominator* a record of six disjoint counts with no `int` representation, but the PRD text as written does not.
- **FR-21** states "never hard-delete" while §11 records that lawful erasure and statutory retention are in tension with it and unresolved (OQ-8). The FR does not say what happens on a GDPR erasure request.
- **FR-24** requires every entry to carry a *matter*; AD-43 amends this to "carries a *matter*, or names the *tenant* chain explicitly", because a scope grant belongs to no *matter*. The PRD text still needs that dated correction.
- **FR-17** (the three refusal conditions), **FR-27** (the aggregation key, cap and partial-completion semantics) and **FR-13** (the default normalisation set) carry their defining detail inside `[ASSUMPTION]` tags rather than as settled requirement.
- **FR-59** gates a release candidate against a phrasing checklist that does not exist yet and must be written before the first candidate (PRD §0.1).
- **FR-14** cross-references "FR-49 for the re-stamp mechanism"; no re-stamping mechanism exists after AD-13, and the reference is to be read as the grant-and-revocation mechanism.

### NonFunctional Requirements

The PRD's cross-cutting requirements carry no numbering in the source. They are extracted and numbered here, each with the section it came from.

**Scale, capacity and cost of the machine**

**NFR-1:** Every scale-sensitive consequence in §4 is asserted at the *design target* of **100 000 *pièces* per *tenant*, counted after container expansion**. Demo-scale verification does not satisfy a functional requirement. (§9 Scale; §3 Glossary — *design target*)

**NFR-2:** No per-operation latency or throughput target is set anywhere, and none may be invented. Where a ceiling exists it is *derived* from a user journey — the first *ranking version* must be reachable within the weekend UJ-1 depends on — and a measured figure such as exhaustive-search latency exists, is recorded from the first baseline, and may then only improve. (§9 Scale; FR-2, FR-13)

**NFR-3:** Capacity boundaries are distinct from performance targets and fail differently — capacity turns into crashes, performance into slowness. Each of *pièce* size, container nesting depth, expansion ratio, attachments per message, *matters* per *tenant*, concurrent *import jobs* per *matter*, retained *ranking versions* and rows per export is bounded by configuration with a defined default, and each surfaces as a *failure register* class rather than as an outage. (§9)

**NFR-4:** **The per-*pièce* LLM judgement is the largest inference cost and the largest data-egress event in the system, and it is uncosted.** At the *design target* stage 3 of the cascade is not a query path but a substantial, automatic export of a client's *matter*, performed as the product's normal operation. Nobody has written down what one triage run costs; the figure must be made to exist and be measured per run. (§9; §11 Egress; §15)

**NFR-5:** **The cascade is the mitigation and it is a requirement, not an optimisation.** Deterministic filters, near-duplicate grouping and cheap semantic scoring run before any model call, and justifications are generated only near **the line**. This is what stands between the product and 100 000 model calls per *matter*, and a fully local model may prove necessary rather than premium. (§9; §11; §18 R-13)

**NFR-6:** **Storage growth is computed, not discovered.** Nothing is deleted, *ranking versions* accumulate within their bound and the *audit record* grows forever, so a *tenant*'s storage footprint at the *design target* is computed and stated by the product — a firm buying one machine needs the number before it buys. (§11 Storage growth; §10 Cost)

**Failure behaviour and determinism**

**NFR-7:** **Fail loudly, everywhere.** No component degrades silently under failure: every failure produces exactly one of a *failure register* entry, a halt, or a *worklist* line — and never a plausible-looking wrong answer. (§9)

**NFR-8:** **Fail closed on access.** Every ambiguity in *tenant* or *RBAC scope* resolves to less access, never more, and this holds identically for administrative and system identities; a user with no scope receives an empty *corpus*, not the whole one. (§9)

**NFR-9:** **Blocking, not warning.** Warnings are ignored and blocks are not: where a guarantee cannot be met the product refuses rather than qualifying — a query that cannot guarantee completeness errors, a stale bound cannot be exported as current, an action whose record cannot be written fails, an unscored *pièce* is excluded from the order rather than sorted to the bottom. (§10 Safety)

**NFR-10:** **Determinism where determinism is claimed.** Anything labelled **exhaustive**, anything reconstructible from the *audit record*, and any ranked order under a fixed *ranking version* must reproduce identically on a different machine and after a restart — tie-breaks included. (§9)

**NFR-11:** **Prevention over filtering.** Where an output must not contain something, what can be produced is constrained rather than what was produced screened: the *confidence bound* sentence is templated and rendered locally, and the banned-phrasing check across locales is a backstop, not the primary defence. (§10 Safety)

**NFR-12:** **The product must never present a guess as a proof.** A *similarity threshold* can never yield an **exhaustive** result set; this single rule is the reason *truth status* exists as data. (§10 Safety)

**Safety, reversibility and human control**

**NFR-13:** **Human-in-the-loop everywhere** — no auto-delete, no auto-send, no auto-sign; inherited and not up for debate. The machine partitions and never acts, which is why drawing **the line** is not a violation: nothing is deleted, hidden, sent or signed, and both sets stay searchable and reversible. (§10 Safety)

**NFR-14:** **Recall over precision** in triage, made unarguable by a measured recall metric and restated in a lawyer's unit — and bounded, so that "retain everything" is visible as the non-answer it is rather than a way of satisfying every quality metric while delivering no triage. (§10 Safety)

**NFR-15:** **Never hard-delete.** Triage is reversible labelling; the *audit record*, the *change log* and the *failure register* are append-only; a resolved register entry is a state change and not a removal. (§10 Safety; §11 Retention; §9)

**NFR-16:** **Targeted friction, not uniform friction.** Confirmation is demanded where a decision carries consequence — an *override*, a move of **the line** — and nowhere else, because uniform friction is ignored friction and ignored friction produces a record that looks like consent. (§10 Safety; §18 R-6)

**Confidentiality, residency and egress**

**NFR-17:** **EU-only.** Inherited, not up for debate. (§10 Privacy and confidentiality)

**NFR-18:** **Zero-retention with the model provider, stated honestly as a contract clause and not a technical property.** Every retrieval-augmented request carries client text off the machine unless a fully local model is used, and a fully local model is out of scope for this increment. (§10 Privacy; §18 R-9)

**NFR-19:** **No fine-tuning on client data. Ever.** No *tenant*'s data contributes to model behaviour. (§10 Privacy; §11 Separation of derived data)

**NFR-20:** **Only code travels — meaning APX's channels and nothing more.** APX never accesses, sees or extracts client data; follow-up is by telephone; the price is no telemetry. The qualification is mandatory: this says nothing about the model provider, and stating it unqualified would be materially misleading to the person it is said to. (§10 Privacy)

**NFR-21:** **Exactly three egress paths exist**: the configured model provider (the largest, automatic, the product's normal operation); the user-initiated *content-free projection*; and the user-initiated *audit record* and retained-set exports. Any fourth path is a defect, and its absence is enforced as a structural property rather than by a runtime test. (§11 Egress)

**NFR-22:** **Residency.** All *tenant* data — *pièces*, *chunks*, *payload schema* records, *audit record*, *failure register*, configuration — resides within the *tenant*'s boundary: inside the firm on-premise, within the EU when hosted. Inherited. (§11 Residency)

**NFR-23:** **Classification is a property of the data, not of the surface that displays it.** Every *chunk* carries its *tenant*, its *matter* and its *RBAC scope*, which is what makes a query pre-filter possible at all; every *chunk* traces to a source *pièce* and a position, so nothing in the *corpus* is of unknown origin. (§11 Classification, Provenance)

**NFR-24:** **RBAC by *matter* — Chinese walls — applied as a query pre-filter, never as a post-filter.** A cross-*matter* leak is a professional-conduct violation that happens silently with no error message, and it is the #1 realistic leak vector, ahead of the model provider and ahead of logs. (§10 Privacy; §11 Classification; §18 R-4)

**NFR-25:** **The *audit record* is a sword as well as a shield.** The firm manufactures and retains permanently a dated document in which it was told the estimated prevalence of relevant material below **the line** and proceeded. Its discoverability, its standing under *secret professionnel* and whether a firm might rationally want a retention limit on it are unanalysed. (§11)

**Evidence and audit**

**NFR-26:** **Append-only where evidence is claimed** — the *audit record*, the *change log* and the *failure register*. (§9; §13)

**NFR-27:** **Audit continuity: incompleteness must be detectable.** Every entry is attributed, carries a wall-clock timestamp and a monotonic sequence number from a single authority, and is chained so that a gap, a reordering or a truncation is detectable by a reader holding only the export. An *audit record* whose incompleteness cannot be detected is not evidence. (§13; §9)

**NFR-28:** **Self-containment on export.** Every number in an exported record is recomputable from the export alone, by a reader with no access to the system. (§13)

**NFR-29:** **What the record proves, and what it does not.** The record proves a human decision was made and recorded; it does not prove the decision was correct. That is what the *confidence bound* is for, and the *confidence bound* is itself probabilistic — it bounds the risk, it does not eliminate it. (§13)

**Security and compliance baseline**

**NFR-30:** **Security is a requirement, not an architecture concern.** Encryption at rest and in transit, authentication and session handling, grant-time authorisation, key management, and backup and restore are the GDPR Art. 32 measures and are in scope as requirements. The off-the-shelf identity layer and storage-layer row security are forbidden for portability reasons that are correct, which makes this hand-rolled code written by agents and reviewed by one non-hands-on person, where a mistake is silent and criminal. It is the highest-risk code in the product and it is defended by tests alone. (§9; §12 GDPR; §18 R-15)

**NFR-31:** ***Secret professionnel* is the binding obligation** — Art. 226-13 Code pénal in France, Art. 458 Code pénal plus the Bar's internal regulations in Luxembourg, where it is a **criminal** obligation and therefore the higher bar. This is the obligation tenant isolation and scope enforcement exist to satisfy mechanically. (§12)

**NFR-32:** **The CNB criteria (17 March 2026) are the ones a *bâtonnier* will actually apply.** Data location and server-owner nationality are satisfied by construction. **Model hosting location and model-provider nationality are not satisfied at all in this increment.** Systematic verification of AI output is answered by random-sample verification carrying a stated, sound prevalence bound plus per-*pièce* *validation acts* over the *retained set* — a measurable answer where "systematic" is not. (§12)

**NFR-33:** **The EU AI Act is not a compliance driver for this increment and must not be used as one.** Legal AI sold to law firms is very likely outside Annex III high-risk, and the high-risk regime was deferred to 2 December 2027; Art. 50 transparency applies from 2 August 2026. Leading with it signals the Omnibus has not been read. (§12)

**NFR-34:** **Extraterritorial access is not resolved by an EU region.** It is mitigated by keeping the model provider behind an adapter so the choice is a configuration line rather than a rewrite — mitigated, not resolved. (§12)

**NFR-35:** **No compliance certification is claimed or pursued in this increment, and no accuracy or hallucination figure is published.** (§12)

**NFR-36:** **The product concentrates the firm's risk, and this is accepted rather than mitigated.** An *ordonnance 145 CPC* or a *perquisition* now finds one indexed, searchable, deduplicated appliance instead of scattered mailboxes. Encryption and grant-time authorisation limit who can exploit it; they do not change the concentration. (§18 R-14)

**Portability, platform and dependencies**

**NFR-37:** **The offline fitness function is the central invariant**: *can this run, unmodified, on a single machine inside a law firm with no internet connection?* Anything that fails it goes behind an adapter. No hard dependency on any hosting-provider primitive is permitted in the core. (§9; §14)

**NFR-38:** **Deployment-agnostic core.** The same code runs in a hosted deployment and on a single machine inside a firm with no internet. Hosted versus on-premise is a **packaging decision per *tenant*, never a fork**. (§14)

**NFR-39:** **Reversibility of every third-party choice.** Anything that could be compelled, priced or discontinued by a third party lives behind an interface — applied without exception to the model provider, the embedder, OCR, storage and any queueing mechanism. (§9; §15 Dependency policy)

**NFR-40:** **Every content-processing capability runs inside the *tenant* boundary.** OCR, rendering and format conversion never use a hosted service, in any deployment — which forbids every hosted OCR and preview service. (§15; FR-3, FR-44)

**NFR-41:** **Platform surface.** A web application usable on a standard workstation with no installation step for the daily user, with local filesystem and removable-drive access as a hard constraint of the onboarding gesture, and **no mobile surface** in this increment. Navigation, *matter* selection and the home screen are built as the workspace's — one workspace, three verbs — not as a triage tool's. (§14)

**NFR-42:** **FR and EN at parity.** Italian is an open question, not a requirement of this increment. (§14; §2.2)

**NFR-43:** **Offline capability with loud degradation.** An on-premise installation functions without internet except for the configured model provider, whose absence degrades loudly rather than silently; the surviving capability set is *enumerated by a CI job* rather than described in prose, and the *confidence bound* sentence must render offline from the *audit record*. (§14; §9)

**Observability, operations and support**

**NFR-44:** **Observability without telemetry.** The product must be diagnosable by its user, over the telephone, by someone who cannot see it: state visible on the *worklist*, error classes enumerated, stable and translated, versions readable in the interface, and the *content-free projection* as the only export path. (§9; §17)

**NFR-45:** **The product must be self-diagnosing.** The state a support call needs — what failed, how many, of what class, and what the user can do about it — is on the *worklist* and in the *denominator*, in the lawyer's language, with the technical detail one click behind. The diagnostic export is the only escalation path. (§17)

**NFR-46:** **No on-call, no SLA and no uptime commitment is defined in this increment — and this is recorded as a flat contradiction rather than a gap.** The stated ambition ("without APX you cannot be a law firm" demands infrastructure status; infrastructure status forbids breaking) is incompatible with a team that cannot answer a telephone at 22:00 on a Sunday. No availability commitment is written because the current capacity cannot underwrite one. The decision — downgrade the ambition, or add capacity before an installation exists — belongs to the APX partners. (§17; §18 R-1)

**NFR-47:** **Every on-premise installation carries 0.5–1 FTE of operations that somebody performs**, per site. Against a team of one non-hands-on CTO plus AI agents, this multiplier applies before a single feature is counted. (§17; §18 R-1)

**NFR-48:** **Documentation must not lie in load-bearing places.** Every configuration key named in documentation exists and is asserted to exist by a test; superseded decisions are marked as superseded rather than quietly ceasing to be true; and nothing ships from a branch that is not the deployed one. (§17)

**NFR-49:** **Backup and restore are the operational floor** — a requirement, not a runbook. A backup whose failure nobody knows about is the most likely way an installation ends a client relationship. (§17; §18 R-12)

**Build discipline, usability and cost**

**NFR-50:** **Testability is a first-class requirement.** With one non-hands-on CTO and AI agents as the whole team, **tests are the substitute for the engineers who are not on the team**. Every FR states its consequences in testable form for this reason, and an FR shipped without its consequences asserted is not shipped. (§9)

**NFR-51:** **Three verbs, never conflated:** *asserted by test* (a CI test decides), *enforced as a structural property* (a static check decides), *asserted by review* (a human decides against a checklist). The third is never counted as a passing test. An inflated claim about what the suite proves is the most dangerous inaccuracy this programme can contain. (§9; §10)

**NFR-52:** **Non-technical usability, with exactly one bounded accessibility requirement.** No technical vocabulary in any user-facing surface — *assessed by review against a checklist, not by test*, because no test decides whether a phrasing is in a lawyer's language. The one bounded, testable commitment: **every *worklist* action and every triage-table edit is reachable and completable by keyboard alone.** No WCAG level is claimed, because claiming one without auditing it would be the unaudited-number failure again. (§9)

**NFR-53:** **Visual consistency as a build requirement.** One token set, one colour system, no hard-coded colour, spacing or type value, enforced as a structural property. Fidelity to the salvaged mockup — the increment's single most reusable design asset — is *asserted by review*, the only honest verb available. (§9)

**NFR-54:** **Every shipped feature is a permanent tax**: tested, migrated blind against a 100 000-*pièce* index at every installation, defensible in front of a judge, supportable by telephone with no telemetry. At three on-premise firms, one more feature is three blind deployments maintained forever, and "it's just tokens" is the identified failure belief this capacity makes most tempting. (§10 Cost)

**NFR-55:** **The buyer's reference price is low and public**, and the product cannot be justified on cost of ownership; it is justified on removing a named confidentiality risk. This constrains scope: a feature that costs owning and does not serve that argument does not earn its place. (§10 Cost)

**Deployment and update**

**NFR-56:** **An installation differs from another by configuration rows, never by code.** The application version, the *payload schema* version and the *ranking version* are readable in the interface and present in the *audit record* and the *content-free projection*, so a user on the telephone can read them out. A migration that cannot preserve every mandatory *payload schema* field is rejected rather than run; no migration re-indexes or deletes a *corpus* as a side effect. (§16)

**NFR-57:** **No auto-update channel in this increment.** Updates are generated and shipped blind, installed by agreement, and their outcome is reported back only by a user-initiated *content-free projection*. (§16)

**NFR-58:** **Signed, offline-installable, reversible migration against a live 100 000-*pièce* index at a site APX cannot see is the one technical problem with no answer yet, and it is deferred rather than solved.** Deferring is correct for one installation and is not correct past the second: version drift across blind installations compounds and is unrecoverable once it starts. (§16; §18 R-10)

### Additional Requirements

Technical requirements drawn from `ARCHITECTURE-SPINE.md` (49 ADs) and `WORK-BREAKDOWN.md` (20 units).

#### Starter or paved path — stated plainly

**The spine names no starter template, scaffold, boilerplate or paved-path repository. There is nothing to instantiate.** No AD, no unit card and no stack row references a generator, a template repository or an existing codebase to fork; the previous implementation at `../apx-platform/` is explicitly reference-only and never an edit target.

What stands in its place, and what the first story therefore builds from empty:

- **A prescribed source tree** (spine › Structural Seed): `apx/core/domain/`, `core/ports/`, `core/app/` with `core/app/read/` as the one read entry point, `adapters/{store_postgres,embedder_bgem3,llm_openai_compat,extraction,ocr_tesseract}`, `api/`, `worker/`, `web/`, `checks/`, `eval/`, plus top-level `tests/` and `deploy/`.
- **A hexagonal layering contract with a checked dependency direction** — Domain imports nothing outside itself; Application imports Domain and Ports only; no adapter imports another adapter; enforced by an import-graph rule in CI, not documented (AD-4, Design Paradigm).
- **A check harness in `checks/` from week one**, each check naming its pattern and the AD it enforces, including the package/extension deny-list and the egress check (AD-33, AD-3, AD-45).

The first story of the first epic is therefore repository creation plus the layer directories, the import-graph rule and the check harness — not template instantiation.

#### The stack as committed, with the versions the spine carries

| Component | Version | Role / constraint (AD) |
| --- | --- | --- |
| Python | 3.13.14 | Core and worker language |
| FastAPI | 0.139.2 | HTTP surface; validates, authorises, enqueues, returns (AD-6) |
| Starlette | 1.3.1 | **Pinned here, not inherited** — FastAPI declares an open lower bound across the 0.46 → 1.x boundary |
| Uvicorn | 0.51.0 | ASGI server |
| psycopg | 3.3.4, **LGPL-3.0-only** | Driver, unconditional dependency of Procrastinate, **imported in-process into the core** (AD-28) |
| Pydantic | 2.13.4 | Boundary validation (2.14.0a1 is alpha — do not ship) |
| SQLAlchemy | 2.0.51 | Persistence (2.1.0b3 is beta — do not ship) |
| Alembic | 1.18.5 | Migrations, behind the fail-closed wrapper (AD-46) |
| PostgreSQL | 18.4 | **The one stateful service**; PG19 is at Beta 2 and must not ship into a firm (AD-5) |
| pgvector | **== 0.8.5** exactly | HNSW, 1024-dim `halfvec`; pinned exactly because 0.8.3/0.8.4 were HNSW vacuum-corruption fixes (AD-5, AD-11) |
| Procrastinate | 3.9.x | Job queue, inside the same PostgreSQL (AD-5, AD-6) |
| BGE-M3 | 568M, 1024-dim, MIT | Default embedder, dense **and** sparse from one pass (AD-11) |
| multilingual-e5-large-instruct | 560M, 1024-dim, MIT | Drop-in embedder fallback |
| Qwen3-Embedding-0.6B | 0.6B, 1024-dim, Apache-2.0 | Same-family embedder upgrade path |
| vLLM | 0.25.1, pinned by digest | GPU inference profile (AD-27) |
| Ollama | 0.32.1, pinned by digest | CPU / low-end inference profile (AD-27) |
| Mistral Small 3.2 24B | Apache-2.0 | Default judgement model, **Q4 on 24 GB VRAM** — INT8 does not fit the €2 000 machine (AD-27) |
| extract-msg | 0.56.0, **GPL-3.0** | `.msg`, **out-of-process and GPL-isolated** (AD-28) |
| pypdf | 6.14.2 | Born-digital PDF |
| pdfplumber | 0.11.10 | Table-heavy PDF |
| Docling | 2.114.0, MIT | Layout-aware extraction; model artefacts **vendored into the image** (AD-2) |
| Tesseract | 5.5.2, Apache-2.0 | OCR, inside the *tenant* boundary |
| python-docx / openpyxl | 1.2.0 / 3.1.5 | `.docx` / `.xlsx` |
| pwdlib[argon2] + argon2-cffi | 0.3.0 + 25.1.0 | Argon2id password hashing (AD-15) |
| PyJWT | 2.13.0 | **Internal service tokens only, never user sessions**; `algorithms=["HS256"]` passed explicitly at every decode (AD-15) |
| pyotp / py_webauthn | 2.10.0 / 3.0.0 | TOTP second factor / additive credential gated on per-site FQDN + certificate |
| Vite / React Router | 8.1.5 / 8.2.0 | Static SPA build and routing (AD-29) |
| Node.js | 24.18.0 LTS | **Build-time only; no Node runtime ships** (AD-29) |
| Docker Engine / Compose | 29.6.2 / v5.3.1 | Runtime and composition of the delivered bundle (AD-30) |
| cosign | 3.1.2 | Key-pair signing; verified with `--bundle` + `--trusted-root`, **never `--offline`** (AD-30) |

**Excluded by name so they are not reconsidered by accident:** PyMuPDF (AGPL-3.0); pgvectorscale and ParadeDB (unavailable on the managed dev tier — AD-3, enforced by a deny-list in `checks/`); Qdrant, LanceDB, Milvus, Weaviate, Chroma, Redis (AD-5); SQLite + sqlite-vec; Next.js (AD-29); FastAPI-Users, python-jose, passlib, Authlib (maintenance posture and patch-latency, never "it once had a CVE"). **Supabase Auth and PostgreSQL row-level security are forbidden outright** — each makes the on-premise install impossible, and RLS would additionally place the Chinese wall in a layer the air-gapped install cannot carry (AD-1).

#### Structural invariants that constrain every unit

- **One stateful service.** PostgreSQL 18.4 holds relational data, vectors, the deterministic text index and the job queue; no component may introduce a second stateful service. Anything that appears to require one is an adapter boundary, not a new deployment unit. **Exactly one endpoint** in every environment — no read replica, no hot standby, no routing pooler — and the application refuses to start where `pg_is_in_recovery()` is true. **The collation is part of the artefact**: `LC_COLLATE`, `LC_CTYPE`, the provider and the ICU version are declared and asserted at start-up, and a mismatch fails to start. (AD-5)
- **Every read of *tenant* data goes through one path** — `core/app/read/` — and *read* means far more than search: reads by identifier, byte and image streams, stored full text, render and thumbnail requests, counts, aggregates and derived statistics, the *failure register*, the *worklist*, the *denominator*, the *matters* zone, the completion summary, and every enumeration performed while producing an export. The read port exposes **no method accepting an identifier without a *tenant* and a scope argument**, and no result-set post-processing function accepts a scope. Decided by a check: no SQL text and no ORM query naming a *tenant*-owned table appears outside `core/app/read/`, and every registered action names the read entry point it uses or fails the build. (AD-14, AD-12)
- ***RBAC scope* is resolved at query time and never denormalised.** Authorisation state lives in exactly one place and is joined into every retrieval query as a pre-filter; a scope change takes effect on the next query with no re-indexing, no migration and no window of indeterminate state; **no re-stamping operation exists in the system**. Generalised: **no mutable attribute of a *pièce* or a *matter* is denormalised onto an indexed row.** A long-running job re-resolves the caller's scope at every unit of work. Cost accepted: a join per query. (AD-13)
- ***Pièce* identity is scoped to one *matter*.** Identity is a deterministic function of (content hash, *matter*); provenance path is a recorded attribute and never identity; the same file ingested into two *matters* yields two *pièces* with separate identities, rankings, audit records and lifecycles; cross-*matter* deduplication and "seen before" intelligence are deliberately forfeited, because they are the capability a Chinese wall exists to forbid. Consequence: the scope predicate is an **equality** — the filter shape hardest to get wrong. Identifiers are never allocated from a counter. `supersedes` points newer→older, is acyclic by database constraint, forms a chain not a tree, is written only by the ingestion use case, and is **never derived from a provenance path**. (AD-8, AD-40)
- **One *chunk* write boundary, with the permitted columns enumerated.** Exactly one function writes a *chunk*, taking *tenant*, *matter*, *RBAC scope* and *custodian* as **required arguments with no default value anywhere in the source**. *Tenant* and *matter* are persisted and immutable; ***RBAC scope* is a write-time authorisation check and is never a column**; ***custodian* is likewise a write-time input and never a column** — it is a set on the *pièce*, unioned by every *import job* admitting the same content and resolved by join. The permitted `chunk` columns are exactly `chunk_id`, `piece_id`, `tenant`, `matter`, `position`, `full_text_version`, chunking-configuration identity, schema version, `model_id`, `model_version`, the vector, and the reserved external-authority reference — **any other column fails the build**. (AD-9)
- **1024 dimensions is the interface.** The vector column is 1024-dim `halfvec` and every row carries `model_id` and `model_version`, so changing embedder is a background migration rather than a rebuild and a mixed-provenance *corpus* is detectable rather than suspected. There is **no fallback embedder and no stub embedder anywhere in the artefact**, in any environment including CI and the hosted dev tier: exactly one class implements `Embedder` under `adapters/`, test fakes substitute at the port boundary inside the test process only. Consequence taken deliberately: 1.4 GB of weights ride inside the CI image and inside the shipped tarball, and the on-premise install has no model-download step. (AD-11)
- **No cascade foreign keys, and a `retired` state instead of `DELETE`.** No foreign key in any migration declares `ON DELETE CASCADE`, `SET NULL` or `SET DEFAULT`; every reference to an evidential ledger is `ON DELETE RESTRICT`; the tokens `DELETE FROM`, `TRUNCATE` and `DROP TABLE` appear in no runtime module and in migrations only under a reviewed, dated allow-list. The one named administrative entry point performs a **state transition to `retired`** — excluded from every read and from every total, stated as its own named count, and restorable by the inverse transition. Enforced over the migration files **and re-asserted against the live schema**, because a cascade introduced by a hand-run migration is invisible to a source grep. One named exception: the single-use transient-credential row is purged, and the purge writes an audit entry naming the register entry and never the value. (AD-7, AD-47)
- **The audit head journal lives outside the restorable store.** On every chain seal and every append to a *tenant* chain, the head — chain scope, sequence, chain value, both timestamps, application and schema versions — is appended to an append-only journal on a volume the dump does not cover, plus a copy on every backup target. A dump restore otherwise silently truncates the record and is **undetectable by design**, because a truncation to an earlier consistent point produces a chain whose every link verifies. On start-up and on restore the live head is compared with the journal: **a live head behind the journal is a truncation**, is named as one in the lawyer's language, appears on the face of every subsequent export, clears only by a recorded *override*, and is never repaired. A missing or unwritable journal fails start-up. (AD-35, AD-43, AD-46)
- **Two inference profiles behind one interface.** A GPU profile (vLLM, Mistral Small 3.2 24B at Q4 on 24 GB VRAM, 100 000 *pièces* overnight) and a CPU/low-end profile (Ollama, the same job in two to three weeks), both pinned by image digest, both priced differently, selected by *configuration-as-data*. **Application code never knows which serves it**, and the same interface must admit a locally hosted model and a sovereign hosted facility without a code change. (AD-27)
- **The encryption layer is split by name, and start-up fails closed on both halves.** Everything is encrypted by the application's storage adapters — originals, extracted full text, OCR images, the *audit record*, the *change log*, the *failure register*, configuration, staged exports, the head journal, every backup artefact — **except two named surfaces**: the `halfvec` vector column and the deterministic text index, which cannot be indexed as ciphertext and are protected by volume- or cluster-level encryption on a machine the firm itself owns. Start-up fails on a missing application key **or** on a data volume it cannot verify as encrypted; there is no warning-and-continue and no single-layer configuration. (AD-31)

Additional invariants that bind every unit and belong in the same tier:

- **Work happens in the queue; the HTTP request never does work**, and **every state-changing request carries a client-generated idempotency key** stored with its action in the same transaction — otherwise a double-click on a bulk *validation act* over 1 400 *pièces* writes 2 800 permanent entries that nothing may remove. (AD-6)
- **One owning use case per state transition, and every transition is a conditional commit** naming the state it observed; the spine's ownership table is extended by each unit **before** its first write; any use case that reads then writes runs in one transaction at repeatable-read or stronger, and the isolation level is a declared property of the use case rather than of the adapter. (AD-37)
- **The unit of work is one *pièce***: idempotent, resumable, quarantinable and memory-bounded, with the application-owned ledger as the sole authority for state and for every progress figure, and the attempt counter and the quarantine transition committed in transactions independent of the failing unit's. (AD-17)
- **The *denominator* is a record of six disjoint named counts, not an integer** — `submitted_pieces`, `in_corpus`, `open_register_entries`, `excluded_as_noise`, `retired`, `unknown_cardinality_entries` — with the identity asserted over **known** *pièces* only, `unknown_cardinality_entries` never summed into any total and rendered in words, and **no `int` representation of the *denominator* anywhere in the source**. (AD-38)
- **The *retained set* and *discarded set* are views computed over one ranked order plus *pins*, never stored memberships**; no table and no column names either set. (AD-39)
- **The cascade removes *pièces* from judgement, never from the population.** Every *pièce* is at all times in the ranked order (carrying an enumerated rejection class where stages 1 or 2 rejected it) or in the explicit **unscored** set; there is no third place, and a *sampling run*'s population is the *discarded set* plus the unscored set or the run states the exclusion in words. (AD-36, AD-18)
- ***Truth status* is set at exactly one construction site per engine and is a constant there**; an **exhaustive** set is never truncated — a limit downgrades it to *suggestive* at the construction site and the deterministic engine's constructor accepts no limit parameter — and it is computed in one repeatable-read snapshot, refusing over a *matter* with an open *import job*. Every **exhaustive** set carries all four qualifications in the interface and in every export, or the build fails. (AD-20, AD-42)
- **Exactly three principal kinds and no fourth**: user, matter-bound job (carrying the initiating user's identity and re-resolving scope per unit of work), and tenant-bound maintenance (may read whole *tenant* partitions, **may not** produce a result set, render content, or emit through the projector registry). (AD-48)
- **Every evidential record carries wall-clock and a monotonic counter**; ordering, session expiry and staleness comparisons use the monotonic value, and a backward wall-clock movement appends its own `clock-adjusted` entry. (AD-49)
- **Exactly one ingestion path** — corpora are configured data sources, never fixtures, never fallbacks, never a demo branch. (AD-16)
- **Configuration changes through exactly one audited per-*tenant* surface**; direct store editing is a per-site divergence and is detectable as such. (AD-25)
- **One content-free projection registry**, open by construction, with the seeded-token test run against every projector **and against the union of all projectors' output for one *tenant***, because the attestation floor is not composable. (AD-26)
- **The frontend is a static SPA and nothing carrying *tenant* data is cacheable**: `Cache-Control: no-store`, no `ETag`, asserted over every registered route; the reverse-proxy configuration is part of the signed artefact; no rendering layer holds credentials or performs authorisation. (AD-29)
- **Extraction adapters run out-of-process and licence-isolated**, and subprocess `stdout`/`stderr` are never propagated verbatim into a register entry, a log, a diagnostic or an export — they are mapped to an enumerated error class and the text discarded. (AD-28)

#### The fitness function as a CI job, and the other decidable checks

**The fitness function is not a principle: it is a CI job that fails the build.** *Can this run, unmodified, on a single machine inside a law firm with no internet connection?* (AD-2)

- The job **boots the whole application in a network-isolated container** with no outbound network except a stubbed model endpoint, and asserts that it starts, ingests a folder, indexes it, retrieves over both engines, ranks, places **the line**, writes an *audit record* and exports. **It runs from week one of the build, before any feature is complete.** A failure fails the build.
- **Exactly one edge is stubbed — the language-model endpoint.** The embedder is the real one, running from weights carried inside the artefact. The job **fails if any model weight, tokeniser or layout artefact is fetched** at start-up or first use, and starts from a **cold cache** in an image built with `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1`.
- **The capability set that does not survive the model provider's absence is enumerated by this job**, never described in prose; the *confidence bound* sentence is inside the surviving set, templated and rendered locally from the *audit record* with no model call.
- **It asserts against the live schema what a source grep cannot see**: no `ON DELETE CASCADE`/`SET NULL`/`SET DEFAULT` anywhere; the pinned collation and locale; exactly one reachable PostgreSQL endpoint, not in recovery; and no cache directive in the shipped reverse-proxy configuration applying to `/api`.
- **It exercises the installer's cosign verification with no route to any network** — a run that succeeds only because a name resolved is a failing run.
- **Recorded per run** because a regression would otherwise hide them: the artefact's size, the job's wall-clock, and the cascade's stage-3 share.
- If real embedding in CI proves prohibitive once the measurement gate has run, the answer is **a second job tier** — a fast job that skips indexing and a full job that does not — **never a stub inside the artefact**.

**The static checks the spine makes decidable** (AD-33; shapes in addendum §10). Each names the check that enforces it and the file or pattern it inspects; a property with no check is not a property, and a clause no check can decide is labelled `[NOT ENFORCEABLE]` naming what stands in its place:

import-graph layering (AD-4) · package and extension deny-list (AD-3) · exactly one non-test `Embedder` implementation, none constructed inside an exception handler, none selected by name outside the enumerated list (AD-11) · destructive index operations with exactly one caller (AD-7) · no `DELETE FROM`/`TRUNCATE`/`DROP TABLE` in runtime modules and no cascade in migrations (AD-7) · no SQL or ORM query naming a *tenant*-owned table outside `core/app/read/` (AD-14) · one *chunk* writer with required scope and no default value; the enumerated `chunk` column set (AD-9) · no conditional under `core/` reads a *tenant* identifier, and no *tenant* identifier or name in source (AD-24) · no runtime import from the test tree, no fixture directory read, no environment-variable data-source conditional, no screen rendering from an embedded literal dataset (AD-16) · no natural-language string as a translation key; no hard-coded locale · no outbound call site outside the enumerated adapters (AD-45) · no reversible credential storage; `jwt.decode` without a literal `algorithms=` list fails, and `PyJWK`/`PyJWKClient`/`jwks` appear in no runtime module (AD-15) · no secret in source, committed configuration or example configuration (AD-47) · no field parsed from a model response named or used as a confidence, and one derivation implementation (AD-19) · no banned *confidence bound* phrasing in any locale's string set · the action registry is complete and each action names its read entry point, its state-changing flag and the transitions it owns (AD-33, AD-14, AD-6, AD-37) · no emission path outside the projector registry, and projectors declare attestation counts machine-readably (AD-26) · no colour, spacing or type value outside the token set (AD-29) · no `nextval` and no `Sequence`-backed column on an evidential table (AD-43) · the deterministic engine's constructor accepts no limit parameter (AD-20) · the principal type is a closed enumeration and the maintenance kind has no path to a result-set constructor or a projector (AD-48) · no `subprocess` call outside `adapters/extraction` and no `stderr=None` within it (AD-28) · every response carrying *tenant* data is `no-store` with no `ETag` (AD-29) · a spine clause with neither a check nor a `[NOT ENFORCEABLE]` label fails the spine's own self-check (AD-33).

#### Infrastructure, packaging, upgrade and rollback

- **One artefact, three environments.** Exactly one artefact is built and every installation runs it. Hosted development, the network-isolated CI container and the on-premise install differ by configuration rows and by which adapter implementations are wired — **never by which code was built**. A capability available on the managed dev tier but not on-premise may not be depended on by the core. (AD-3)
- **Delivery is a Docker Compose bundle** as a `docker save` tarball, everything pinned by digest, signed with a **cosign 3.1.2 key pair** — keyless verification needs Fulcio and Rekor and is unusable air-gapped. Verification is `cosign verify --key cosign.pub --bundle <sig.bundle> --trusted-root <trusted_root.json> --local-image ./bundle`, with signature material and service keys **inside the delivered tarball** and nothing fetched. **`--offline` is deliberately not used** — at 3.1.2 it is deprecated and no longer guarantees the absence of network requests. Ruled out and recorded: a single binary (the stack shape forbids it) and a Tauri wrapper (additive only). (AD-30)
- **Upgrade fails closed.** `upgrade.sh` takes a **verified `pg_dump` before every Alembic migration and aborts if the dump cannot be verified**; it records the audit head at which the dump was taken and asserts the pinned collation before proceeding. (AD-46, AD-35, AD-5)
- **Rollback is a dump restore plus re-tagging the recorded image digests — never `alembic downgrade`.** A restore is not complete until the restored head has been reconciled against the head journal and any backward movement named as a truncation; a restore is never "successful" merely because every chain link verifies. (AD-46, AD-35)
- **Backup and restore are product features exercised in CI**, at reduced scale in the pipeline and by documented procedure at the *design target*, with the chain re-verified and the collation asserted before restoring. The product computes and states a *tenant*'s storage footprint, and a **pre-flight capacity check refuses an *import job* that cannot fit** rather than discovering it at 70% — and the same check **states the expected wall-clock for the configured inference profile and records the statement in the *audit record* with the job**, so a sales sentence becomes a screen and a test. (AD-32, AD-27)
- **The licence position is complete and goes to counsel in one email**: `extract-msg` (GPL-3.0) out-of-process with no import into the core; PyMuPDF (AGPL-3.0) excluded outright; **psycopg (LGPL-3.0-only) imported in-process into the core** and unavoidable, shipped as a separate, replaceable, unmodified package. (AD-28)
- **The reverse-proxy configuration ships inside the signed artefact**, and the SPA is static assets served by it alongside `/api`. (AD-29)

#### Sequencing gates

The work breakdown's twenty units are already in dependency order: U1 fitness gates · U2 the measured machine · U3 corpus and gold set · U4 the one store · U5 payload and identity kernel · U6 identity, sessions, grants, keys · U7 tenancy and configuration · U8 the audit spine · U9 the single read path · U10 the extraction bench · U11 embedder and index · U12 the ingestion pipeline · U13 content-free projection · U14 the relevance cascade · U15 ranked order and **the line** · U16 reading, validation and the home screen · U17 estimator and sampling · U18 the deliverable · U19 internationalisation depth · U20 the usability gate.

Four gates bind that order and must be respected by any epic sequence built from it:

1. **The payload schema and the identity model come first** (U5, after U4). The frozen payload record, the one *chunk* write boundary, the (content, *matter*) identity function, chunk provenance to source position, container-expansion arithmetic and the *denominator*'s unit are **the only irreversible decision in the increment**: adding a mandatory field later means re-indexing everything at every installed site, blind, against a live 100 000-*pièce* index — the one technical problem in the programme with no answer. The vector column's shape depends on gate 2. (AD-8, AD-9, AD-10, AD-38, AD-40)
2. **The timed 5 000-document concurrent run gates every retrieval and performance commitment** (U2). One run on the target hardware with **OCR, embedding and LLM judgement all active concurrently**, producing: wall-clock extrapolation to 100 000 *pièces*, measured chunk yield, HNSW p95 under a *matter*-scoped filter, index build within `maintenance_work_mem`, and full-text index size. It is a throwaway harness with spike-quality adapters, **not a unit of the product**. It holds up U5's vector column, U9, U11, U14, U15 **and every wall-clock or throughput commitment made to a firm**; until it exists no number may be quoted and UJ-1's weekend ceiling is unverified. Falsified above ~8 M chunks or ~2 s p95, or if ingestion extrapolates past one weekend, or if Tesseract overtakes the LLM as the bottleneck — in which case the hardware recommendation and the €2 000 story are both wrong. (Open Risks 1 and 3; AD-5, AD-11, AD-18, AD-21, AD-27, AD-28)
3. **The gold-set merge gate precedes all ranking-quality work** (U3 → U14/U15). No ranking or triage code merges before recall against the *gold set* executes in CI and its figure is recorded. The floor is set from the **first measured baseline** and may only rise, and the ratchet is **significance-tested** against measured run-to-run variance — because a strict rule on a noisy measure produces flaky builds, flaky builds get disabled, and that is how a gold set stops running for the second time. Confidence is calibrated against the same set, and the estimator is validated by simulation against populations of known composition before it ships. (AD-34)
4. **The §6.3 sequencing gate** — no triage-layer work (U14 onward) begins until one real anonymised *matter* is in hand, or its absence is explicitly re-accepted in writing, with a date. It is the only structural defence against the drift that produced v1.

Two smaller sequencing facts that change story order: **the i18n key mechanism is not deferrable to U19** — it binds the frontend from its first line and belongs in U16's first story, because retrofitting it means touching every string twice. And **one thirty-second check must precede any reliance on the hosted dev tier**: confirm the managed tier actually offers PostgreSQL major version **18**, asserted in two documents and verified in neither (spine Open Question 5).

#### Salvage from the previous implementation

Paths are relative to `../apx-platform/` — **reference only, never an edit target.**

**LIFT AS-IS**

- **`data/mock/raw/` (140 files) + `data/mock/raw/manifest.json` + `data/mock/processed/` — above all.** A coherent, anonymised, deliberately noisy six-month employment-law dump **with ground-truth routing and pertinence labels per item**: the labelled mock corpus and gold manifest, ranked #1 on the salvage list, the most valuable artefact in the previous repo and the hardest to recreate. Copy the data; do not regenerate it. Feeds the corpus and gold-set unit alongside TREC. **v1 had this and never once executed it.**
- **`tests/unit/test_guardrails.py`** — 184 LOC, 13 tests, the non-negotiables as executable assertions (label reversibility, no bulk delete, out-of-taxonomy labels can never leak, recall-biased quality gate, no network without a key), importing only base dependencies by design. **Adopt as the acceptance floor on day one**, in the fitness-gates unit.
- **`domain/syllogisme/scorer.py`** — pure, deterministic, zero I/O, tested on both sides of the threshold, coupled to nothing. Port the file verbatim with its tests, into the ranked-order unit.
- **`domain/scoring/quality.py`** — cheap, explainable, recall-biased pre-ingestion filter returning a machine-readable rejection reason; tested. Into ingestion.
- **`domain/syllogisme/grounding.py`** — `extract_json` survives code fences and prose wrappers, `truthy` handles `true`/`oui`/`yes`; 6 tests. Into the cascade unit.
- **`domain/classification/labels.py`** — nine flat, mutually exclusive French legal categories with prompt-ready descriptions, adopted **as the default taxonomy row set, not as code**. Unvalidated for *ordonnance 145 CPC* review, so being wrong is cheap — but shipping it unexamined would inherit a v1 assumption unexamined.
- **`domain/syllogisme/builder.py`** prompt patterns, the tolerant parser and the `{"off_corpus": true}` escape hatch — weeks of prompt iteration and a parser that survives partial or malformed model output. Into the cascade unit.

**REFACTOR**

- **`domain/audit/`** (~230 LOC) plus its read/filter API — keep the event vocabulary, factory functions and read API; replace the JSONL-on-local-disk substrate with the append-only table. **It sits on an unmerged branch — retrieve it before it is lost.**
- **The `llm/` provider abstraction** (`base.py`, `factory.py`, `stub.py`, provider clients) — the shape is right: a `Protocol`, deferred SDK imports, a stub that cannot be mistaken for a real answer. Three things must change: `grounded_passage_ids` is passed in and echoed out untouched and **must not be presented as a grounding guarantee**; the hard-coded model id is not valid; and streaming, retries, timeouts and token accounting do not exist.
- **`domain/chunking/strategies.py`** — keep the parent/child plus contextual-header architecture; replace the sentence splitter, which mangles French legal text (`art. L. 1235-3`, `n° 21-12.345`, `M.`, `Cass. soc.` all split mid-citation). **Zero tests exist — write them first.**
- **`web/src/lib/export.ts` and `word-export.ts`** — the citation-renumbering logic genuinely works and the output opens natively in Word and Google Docs; **move generation server-side**, because client-side generation leaves no server-side record of what was exported. "PDF" was `window.print()`.
- **`web/src/app/**` and `components/ui.tsx` — as design reference, not as code.** Real screens real clients have seen, but one page is 870 lines with no tests and no lint, and `translations.ts` keys English strings by their French source text. Alongside it, **`maquette_anfr_v2.html`** — the editable cell-by-cell triage table with its live before→after change log and the fully designed audit drawer (confidence, retained extracts, numbered *Trace d'audit proposée*, four reversible actions) — is the direct design source for the triage table and the *audit drawer*, and the single most directly reusable artefact for this increment.
- Only **the `SearchResult` schema shape** from `retrieval/schemas.py` survives from retrieval — the `parent_text` / `excerpt` split is a good idea.

**REWRITE:** `domain/parsing/*` (eight thin wrappers, zero tests; `parse_pdf` never falls back to OCR so scanned PDFs silently yield nothing; `.eml` handles only `text/plain`) · `domain/retrieval/service.py` (no filtering, so no tenancy; no reranking, no hybrid, no metadata filters) · `domain/ingestion/service.py` (the sequence of steps is right; the implementation is one synchronous function inside the HTTP request accumulating every point in memory before a single upsert) · `domain/documents/repository.py` · `infra/vectorstore/qdrant.py` (silently deletes the whole collection on a vector-size mismatch, wearing a comment that calls it a feature) · `rbac/` **from zero** — a docstring only, while `client_key` and `dossier_key` were persisted and never used as a filter.

**DROP:** `workers/**` (8 files, 0 bytes) · `Dev/legal-rag-core/` · `.env.example` · `generate_mock_corpus.py` · the `demo-data.json` / `demo.ts` mechanism — **deleted, not disabled.**

### UX Design Requirements

**No UX design contract exists for this increment.** The PRD specifies the user-facing surfaces without specifying their design: the *worklist* home screen with its two zones and the *matters* zone beneath it (FR-27, FR-28, FR-60), **the line** and its priced movement (FR-17, FR-19), the editable cell-by-cell triage table with its live *change log* (FR-20), the *pièce* viewer with per-format passage highlighting (FR-44), the *audit drawer* (FR-26), and the *retained set* export (FR-46). Stories touching any of these carry **behavioural acceptance criteria only** — what must be true, testable, in the lawyer's language — and are to be **marked as requiring a UX pass before implementation**; no story should invent layout, hierarchy or visual treatment in the absence of that pass. This is a deliberate decision rather than an omission: **UX runs in parallel and it blocks nothing, because the leading units are all spine work** — fitness gates, the measured machine, the corpus, the store, the payload and identity kernel, identity and sessions, tenancy, the audit spine and the single read path all complete before the first user-facing surface is built. Two constraints already bind whatever design arrives: the salvaged mockup (`maquette_anfr_v2.html`) is the design source for the triage table and the *audit drawer* and nothing designs the retained-set export yet; and the usability gate (FR-59) — one token set, keyboard reachability, a versioned phrasing checklist with dated recorded verdicts — is the falsifiable floor every surface is reviewed against before a release candidate.

### FR Coverage Map

{{requirements_coverage_map}}

## Epic List

{{epics_list}}

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic {{N}}: {{epic_title_N}}

{{epic_goal_N}}

<!-- Repeat for each story (M = 1, 2, 3...) within epic N -->

### Story {{N}}.{{M}}: {{story_title_N_M}}

As a {{user_type}},
I want {{capability}},
So that {{value_benefit}}.

**Acceptance Criteria:**

<!-- for each AC on this story -->

**Given** {{precondition}}
**When** {{action}}
**Then** {{expected_outcome}}
**And** {{additional_criteria}}

<!-- End story repeat -->
</content>
</invoke>
