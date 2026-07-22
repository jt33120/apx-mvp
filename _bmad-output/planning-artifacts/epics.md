---
stepsCompleted: [1, 2, 3, 4]
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

- **FR-1:** Epic 2 — Folder selection as the whole onboarding gesture
- **FR-2:** Epic 2 — Non-blocking, resumable *import job*
- **FR-3:** Epic 2 — Multi-format extraction
- **FR-4:** Epic 2 — Idempotent *ingestion* with stable identifiers
- **FR-5:** Epic 2 — The *failure register*
- **FR-6:** Epic 2 — The inventory guarantee and the permanent *denominator*
- **FR-7:** Epic 2 — Completion summary
- **FR-8:** Epic 1 — The frozen *payload schema*
- **FR-9:** Epic 2 — The embedder fails loudly
- **FR-10:** Epic 2 — The index never deletes itself
- **FR-11:** Epic 2 — Chunking with provenance to source position
- **FR-12:** Epic 3 — Semantic retrieval, marked *suggestive*
- **FR-13:** Epic 3 — Deterministic exhaustive search
- **FR-14:** Epic 3 — *RBAC scope* as a query pre-filter
- **FR-15:** Epic 3 — Every result set declares its *truth status*
- **FR-16:** Epic 4 — One ranked order, nothing deleted, nothing categorised
- **FR-17:** Epic 4 — The tool draws **the line**
- **FR-18:** Epic 4 — Per-*pièce* confidence and a one-line reversible justification
- **FR-19:** Epic 4 — Moving **the line** is priced
- **FR-20:** Epic 4 — The editable cell-by-cell table with a live *change log*
- **FR-21:** Epic 4 — Never hard-delete
- **FR-22:** Epic 5 — Random draw from the *discarded set*
- **FR-23:** Epic 5 — The *confidence bound* as a sentence
- **FR-24:** Epic 5 — The *audit record*
- **FR-25:** Epic 5 — *Overrides* with a mandatory one-line reason
- **FR-26:** Epic 5 — The *audit drawer* and its export
- **FR-27:** Epic 2 — The *worklist*, actionable lines only
- **FR-28:** Epic 2 — The permanent *denominator* on the home screen
- **FR-29:** Epic 1 — Tenant isolation
- **FR-30:** Epic 1 — Configuration-as-data
- **FR-31:** Epic 1 — The *content-free projection* primitive
- **FR-32:** Epic 6 — The client-pushed diagnostic export
- **FR-33:** Epic 2 — One *ingestion* path
- **FR-34:** Epic 6 — Namespaced translation keys, no silent fallback
- **FR-35:** Epic 6 — Locale-aware dates, numbers and sorting
- **FR-36:** Epic 6 — The language reaches the language model
- **FR-37:** Epic 4 — The optional *case theory*
- **FR-38:** Epic 4 — The *relevance judgement*
- **FR-39:** Epic 4 — The ranked order and the *ranking version*
- **FR-40:** Epic 4 — Per-*pièce* labelling against the *tenant*'s triage taxonomy
- **FR-41:** Epic 4 — The justification, derived from named evidence
- **FR-42:** Epic 4 — Per-*pièce* confidence is derived, never self-reported
- **FR-43:** Epic 4 — Moving a single *pièce* across **the line**
- **FR-44:** Epic 3 — The *pièce* viewer
- **FR-45:** Epic 5 — The *validation act*, and no undetectable bulk acceptance
- **FR-46:** Epic 6 — Export of the *retained set*
- **FR-47:** Epic 1 — Encryption at rest and in transit
- **FR-48:** Epic 1 — Authentication and session handling
- **FR-49:** Epic 1 — Grant-time authorisation and *RBAC scope* administration
- **FR-50:** Epic 1 — The minimal configuration and provisioning surface
- **FR-51:** Epic 1 — Secret and key management
- **FR-52:** Epic 1 — Backup, restore and disaster recovery
- **FR-53:** Epic 5 — *Audit record* continuity
- **FR-54:** Epic 2 — The corpus and *gold set* pipeline
- **FR-55:** Epic 1 — The offline fitness function, executed in CI
- **FR-56:** Epic 1 — Structural properties, enforced in CI
- **FR-57:** Epic 2 — Container expansion and the unit of the *denominator*
- **FR-58:** Epic 4 — Freshness and staleness of derived artefacts
- **FR-59:** Epic 6 — The usability gate
- **FR-60:** Epic 2 — The *matters* zone

## Epic List

### Epic 1: A firm installs APX, and it is safe from the first minute

A firm's IT contact installs APX on a machine the firm owns, it starts or refuses to start, and a lawyer signs in. The *payload schema* — the only irreversible decision in the increment — is frozen here, and the offline fitness function runs in CI from the first week so no dependency can quietly make the product un-installable. For on-premise software, a working, secured, accountable installation is a user outcome, not plumbing.

**FRs covered:** FR-8, FR-29, FR-30, FR-31, FR-47, FR-48, FR-49, FR-50, FR-51, FR-52, FR-55, FR-56  ·  **12 requirements**

### Epic 2: A lawyer hands over a matter and every document is accounted for

A lawyer selects a folder — a USB key, a network share — and leaves. On return: every *pièce* is in the *corpus*, in the *failure register*, or in a declared exclusion, with nothing in two of them and nothing in none. The *denominator* is permanent and on screen, the *worklist* says what needs a human, and the completion summary is readable by someone who is not technical. Closes with the timed 5 000-document concurrent run that gates every performance commitment downstream.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10, FR-11, FR-27, FR-28, FR-33, FR-54, FR-57, FR-60  ·  **16 requirements**

### Epic 3: A lawyer finds a pièce, and can prove another does not exist

Two engines with different truth status: one that finds and never claims completeness, one that proves and returns the whole match set. Every result declares which it is, in the interface and in any export. The *RBAC scope* is a pre-filter on the query itself, so a wall cannot leak silently. And the *pièce* viewer, because reading the document is the job.

**FRs covered:** FR-12, FR-13, FR-14, FR-15, FR-44  ·  **5 requirements**

### Epic 4: A lawyer receives a ranked working set and keeps control of it

An optional *case theory*, a cascade that spends the model only where cheap filters cannot decide, one ranked order with nothing deleted and nothing categorised, and **the line** the tool commits to and the lawyer moves at a priced cost. Confidence is derived, never self-reported. Every edit is a per-*pièce* diff with a live *change log*, and a single *pièce* can cross **the line** without dragging it.

**FRs covered:** FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-37, FR-38, FR-39, FR-40, FR-41, FR-42, FR-43, FR-58  ·  **14 requirements**

### Epic 5: A sceptic audits what was set aside and says a defensible sentence

A random draw from the *discarded set*, verdicts recorded, and a *confidence bound* stated as a prevalence bound a lawyer can say to a client or a judge — or counts only, if the estimator cannot be proven sound. The *audit record* is atomic, chained, and detectably incomplete rather than silently so; *overrides* carry a written reason; the *validation act* is real and bulk acceptance is never undetectable.

**FRs covered:** FR-22, FR-23, FR-24, FR-25, FR-26, FR-45, FR-53  ·  **7 requirements**

### Epic 6: The work leaves the building, in the firm's own language

The *retained set* comes out as a deliverable rather than staying inside the tool. The client-pushed diagnostic export carries counts and never content. The interface, dates, sorting and the model's own instructions all follow the firm's language. And the usability gate is exercised against a real non-technical reader.

**FRs covered:** FR-32, FR-34, FR-35, FR-36, FR-46, FR-59  ·  **6 requirements**

---

**Coverage:** 60 of 60 functional requirements, each in exactly one epic.

**Dependencies run strictly forward.** Epic 2 depends on Epic 1; Epic 3 on 1–2; Epic 4 on 1–3 (the cascade uses retrieval); Epic 5 on 4 (there must be a *discarded set* to audit); Epic 6 on the rest. **No epic requires a later epic to function.**

**Two gates.** The timed 5 000-*pièce* concurrent run — OCR, embedding and inference together — closes Epic 2 and gates every performance and retrieval commitment in Epics 3–5; until it exists, wall-clock claims are speculation. The *gold set* merge gate (FR-54, Epic 2) precedes ranking-quality work in Epic 4.

**No UX design contract exists.** Stories touching the *worklist*, **the line**, the editable table, the viewer, the *audit drawer* and the export carry behavioural acceptance criteria only and are marked as requiring a UX pass before implementation.


<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: A firm installs APX, and it is safe from the first minute

A firm's IT contact installs APX on a machine the firm owns, it starts or refuses to start, and a lawyer signs in. The *payload schema* — the only irreversible decision in the increment — is frozen here, and the offline fitness function runs in CI from the first week so no dependency can quietly make the product un-installable.

**Definition of done for the epic:**
- A network-isolated CI job boots the application, ingests a folder, indexes, retrieves, ranks, audits and exports — with no hosted-provider service reachable — and fails the build if any step needs the network (FR-55).
- The *payload schema* is frozen: exactly one *chunk* writer, `RBAC scope` a required argument with no default anywhere in source, asserted by a static check (FR-8, FR-56).
- A deployment started without encryption or a key, or with an unencrypted data volume, fails to start — no permissive default (FR-47).
- A *tenant* can be provisioned, its first administrative grant established, a user signed in, and a restore into an empty installation reproduces it identically (FR-50, FR-49, FR-48, FR-52).

### Story 1.1: The repository, born from empty, with the layering rule enforced

As the APX build (one lead plus agents),
I want the repository created from nothing with the prescribed source tree, the hexagonal layering rule and an empty `checks/` harness in place,
So that every later story is written against a structure a static check already guards, rather than one that drifts.

**Acceptance Criteria:**

**Given** no repository exists and the spine names no starter or paved path,
**When** Story 1.1 is complete,
**Then** the source tree matches the spine's prescribed layout (a hexagonal core with adapter boundaries), a `checks/` harness runs in CI and is green on an empty project, and the pinned stack versions from the spine are declared in the lockfiles (PostgreSQL 18.4, pgvector ≥ 0.8.5, Procrastinate 3.9.x, FastAPI 0.139.2, Starlette 1.3.1, Vite 8.1.5, React Router 8.2.0).
**And** a static check asserts the layering rule — the core imports no adapter — and fails the build on violation (per AD's hexagonal-core rule).
**And** *(failure path)* a deliberately introduced import from the core to an adapter turns the build red, proving the check is live and not decorative.

### Story 1.2: The offline fitness function, running in CI from week one

As the APX build,
I want a CI job that boots the application in a network-isolated container and drives it end to end,
So that "portable to an air-gapped firm machine" is measured continuously rather than discovered in front of the first client.

**Acceptance Criteria:**

**Given** a network-isolated container with no hosted-provider service reachable and no outbound network except a stubbed model-provider endpoint,
**When** the fitness job runs,
**Then** it asserts the application starts, ingests a folder, indexes it, retrieves over both engines, ranks, places **the line**, produces an *audit record* and exports — and a failure of any step fails the build (FR-55).
**And** the job enumerates which capabilities do **not** survive the model provider's absence — the ranking, the justifications, the priced statement — rather than describing them.
**And** the *confidence bound* sentence is asserted to be regenerable from the *audit record* with **no** model call (FR-55, `[ASSUMPTION]` carried: a statistical claim must never depend on a network call).
**And** *(failure path)* introducing a hard dependency on a hosted-provider SDK in the core turns this job red.

### Story 1.3: The frozen payload schema

As a lawyer whose matters must stay walled apart for years,
I want every indexed *chunk* to carry a complete, versioned provenance and scope record that cannot be written incomplete,
So that the one decision that cannot be undone later — what travels on every *chunk* — is made once and made right.

**Acceptance Criteria:**

**Given** the *payload schema* writer,
**When** a *chunk* is written,
**Then** it carries every mandatory non-nullable field — *tenant*, *matter*, *RBAC scope*, *custodian*, source *pièce* identifier, source position, extraction method and extractor version, schema version, ingestion timestamp, and the *pièce*'s own date or an explicit "undetermined" (FR-8).
**And** the full extracted text of a *pièce* is stored addressably, separately from its *chunks*, with its own identity and version recorded on the *pièce* (FR-8, so FR-13's exhaustive search has a target).
**And** the *pièce*'s borne date and its ingestion date are stored separately and neither is ever substituted for the other.
**And** a static check asserts there is exactly one *chunk* writer, that it takes *RBAC scope* as a required argument, and that no default value for that argument exists anywhere in source (FR-8, FR-56; per AD-40 scope is a write-time check, never a column, and the permitted `chunk` columns are enumerated).
**And** *(failure path)* a *chunk* write missing any mandatory field is rejected at the boundary, fails the *import job* loudly, and enters the *failure register* — never written with a default, never with an empty *RBAC scope*.
**And** *(failure path)* an *import job* that spans a schema or chunking version change completes under the versions it started with, or halts and restarts — it never produces two generations of *chunks* inside one *matter*.

### Story 1.4: Tenant isolation, enforced at the boundary

As a firm whose data must never touch another firm's,
I want every record bound to exactly one *tenant* and every read constrained by *tenant* before anything else,
So that isolation holds identically whether APX runs hosted or on our own machine.

**Acceptance Criteria:**

**Given** any stored record,
**When** it is written,
**Then** it carries its *tenant*, enforced at the write boundary, and a record without a *tenant* cannot be written (FR-29).
**And** every read is constrained by *tenant* before *RBAC scope* is applied (FR-29, then AD-13's query-time scope).
**And** an adversarial test asserts zero cross-*tenant* results, counts or metadata across every retrieval, export and diagnostic surface.
**And** no *tenant*'s data is used to compute anything shown to another *tenant*, including aggregate statistics and model behaviour.
**And** *(failure path)* a query deliberately crafted to omit the *tenant* constraint fails closed — returning nothing — rather than returning another *tenant*'s rows.

### Story 1.5: Authentication and sessions the application owns

As a lawyer signing in to a tool holding privileged material,
I want authentication and sessions handled by the application itself, not by a hosting provider,
So that the same identity model works air-gapped and hosted, and no third party stands between me and the wall.

**Acceptance Criteria:**

**Given** the authentication surface,
**When** a credential is stored,
**Then** it uses a current password-hashing function (Argon2id via `pwdlib[argon2]`) with a per-credential salt, and a static check asserts no reversible credential storage exists anywhere (FR-48, FR-56).
**And** sessions are opaque, server-side, with a configured absolute and idle lifetime, invalidated on password change, on scope revocation and on explicit sign-out, with identifiers that are not guessable and not reusable (FR-48; per AD's owned-auth decision, no JWT for user sessions).
**And** a configured lockout or rate limit applies to repeated authentication failure, and every failure and lockout is recorded in the *audit record*.
**And** multi-factor authentication exists and is *configuration-as-data* per *tenant* (FR-48, `[ASSUMPTION]` carried).
**And** *(failure path)* a revoked scope invalidates the live session that held it, at the next request, not at the next login (ties FR-14, FR-49).

> SSO against a firm's directory is explicitly out of scope for this increment and recorded as a probable day-one ask (OQ-22) — not a surprise.

### Story 1.6: Grant-time authorisation and scope administration

As a firm's supervising partner,
I want creating, granting, revoking and re-scoping *RBAC scopes* to be privileged, recorded and reversible acts,
So that a Chinese wall cannot be widened by anyone who happens to have access — a wall anyone can move is not a wall.

**Acceptance Criteria:**

**Given** scope administration,
**When** a scope is created, granted, revoked, or a *matter* re-scoped,
**Then** each is a privileged act requiring an explicit administrative grant held by a named user of the *tenant*, each recorded in the *audit record* with actor, subject, scope, authority and timestamp, and each reversible (FR-49).
**And** the administrative grant is itself granted by the same mechanism, its first holder established at *tenant* provisioning, with no implicit superuser and no identity that bypasses FR-14 — fail-closed applies to administrative and system identities alike.
**And** a re-scope takes effect at the next query with nothing to propagate and no half-stamped window (FR-49 as amended, AD-13), recorded as one operation with its before and after scope.
**And** *(failure path)* the mutating adversarial suite re-scopes a *matter* mid-*corpus* and asserts the wall holds in its new position immediately and in its old position never.

### Story 1.7: Encryption at rest and in transit, with a fail-closed start

As a firm whose *secret professionnel* is a criminal obligation,
I want everything at rest encrypted and the application to refuse to start without it,
So that a stolen disk or a restored backup yields nothing.

**Acceptance Criteria:**

**Given** any *tenant* data at rest — originals, extracted text, *chunks*, embeddings, OCR images, the *audit record*, the *failure register*, configuration, staged exports,
**When** it is stored,
**Then** it is encrypted by the application's storage adapters, in a hosted deployment and a single-machine install alike, **except** the two named searchable surfaces — the vector column and the deterministic text index — which are protected by volume- or cluster-level encryption instead (FR-47 as amended, AD-31/47).
**And** all network traffic carrying *tenant* data or credentials is encrypted in transit, including between the application and its own stores.
**And** a seeded-token inspection of the raw stores finds no plaintext token, excluding the two named surfaces, which are asserted differently.
**And** *(failure path)* a deployment started with encryption disabled, without a key, or with an unencrypted data volume, fails to start — no permissive default, no warning-and-continue, both layers covered by one startup gate.

### Story 1.8: Secret and key management

As a firm,
I want every secret held outside the data stores, never logged or exported, and rotatable without redeployment,
So that the one mistake that ends a client relationship — a secret in the wrong place — is designed out.

**Acceptance Criteria:**

**Given** model-provider credentials, embedder credentials and encryption keys,
**When** they are held,
**Then** they live outside the application's own data stores, are never written to a log, diagnostic, export or *audit record* entry, and are never displayed after entry (FR-51).
**And** every secret is rotatable without a redeployment and without re-indexing, and rotation is recorded in the *audit record*.
**And** a static check asserts no secret value appears in source, in committed configuration, or in any example configuration (FR-51, FR-56).
**And** the *content-free projection* is asserted against seeded secret values as well as seeded content tokens (ties FR-31).
**And** *(failure path)* a seeded secret placed in a log line or an export turns the build red.

### Story 1.9: Configuration-as-data and the provisioning surface

As APX operating one codebase for many firms,
I want per-*tenant* behaviour to be data rows edited through one audited surface, and a *tenant* provisioned through it,
So that saying yes to a firm's bespoke need never becomes a per-site code fork — the failure that is fatal at eight clients.

**Acceptance Criteria:**

**Given** the configuration surface (FR-50),
**When** a *tenant* is provisioned,
**Then** its first administrative grant is established, and its taxonomy, *RBAC scopes*, model provider and endpoint, sources, chunking configuration, exclusion list, cascade and refusal thresholds, and interface language are all editable as data without a code change or a different deployment (FR-30, FR-50).
**And** configuration is edited only through that surface — direct database editing is not the mechanism, because it produces no *audit record* entry, no validation and no rollback (FR-30).
**And** a static check asserts no *tenant*-specific identifier or name appears anywhere in source, and one artefact is built and every installation runs it (FR-30, FR-56).
**And** every configuration key referenced in any documentation exists in the surface and is asserted to exist by a test; every key has a default, and a test asserts no default disables the guarantee its key governs (FR-30; v1 defects: keys that existed in zero source files, the off-corpus gate disabled by default).
**And** *(failure path)* a documented key with no backing entry, or a default that disables its own guarantee, fails the build.

> **UX pass required before implementation.** No UX design contract exists yet. The provisioning and configuration surface is user-facing.

### Story 1.10: The content-free projection primitive

As APX supporting an installation I can never see into,
I want a single audited primitive that emits counts, versions, error classes and redacted diagnostics and provably no *tenant* content,
So that "only code travels" is one enforceable mechanism reused three times, not a promise repeated in three places.

**Acceptance Criteria:**

**Given** the *content-free projection* (FR-31),
**When** it emits anything — a client-pushed diagnostic export, a cockpit signal, or the style-profile output of a later increment,
**Then** the output passes an assertion that seeded content tokens and seeded secret values do not appear in it, and the content-freedom is enforced by a structural property rather than by an allow-list that a later field could quietly break (FR-31, AD's open-registry-with-attestation decision).
**And** the egress check lives in a unit that cannot be cut from the build (per AD-45, moved off the unit an adversarial review predicted would be dropped).
**And** *(failure path)* adding a new projected field without an attestation that it is content-free turns the build red.
*Note: an adversarial review named the content-free projection among the components most likely to be quietly dropped under pressure. It is load-bearing for the sovereignty claim.*

### Story 1.11: Backup, restore and disaster recovery

As a firm running APX on one machine with no ops staff,
I want scheduled encrypted backups, a restore that is exercised not assumed, and a stated storage footprint,
So that a disk failure does not destroy a record I may need in front of a *bâtonnier*.

**Acceptance Criteria:**

**Given** a *tenant* at scale,
**When** a backup runs,
**Then** it produces a complete restorable backup — originals, extracted text, index, *audit record*, *failure register*, configuration — encrypted, inside the *tenant* boundary, on a schedule and on demand (FR-52).
**And** a restore into an empty installation reproduces a *tenant* whose *denominator*, ranked orders, *audit record* sequence and *confidence bounds* are identical to the source, asserted by CI test at reduced scale (FR-52).
**And** the storage footprint at the *design target* is computed and stated by the product, and a pre-flight capacity check refuses an *import job* that cannot fit rather than discovering it at 70%.
**And** backup success or failure is a *worklist* line in the lawyer's language, and a *tenant* with no successful backup within the configured interval says so persistently on the home screen.
**And** *(failure path)* on a full disk, writes to the append-only stores fail closed, the *import job* halts with a *worklist* line, and no partial state is presented as complete (ties FR-53).
*Note: this entire FR is an inference — backup and restore appear in no source document, and their absence is the single most likely way an installation ends a client relationship. Do not drop it as "not in the PRD".*

### Story 1.12: The structural-properties harness

As the APX build standing in for the engineers who are not on the team,
I want every "no code path does X" claim in the PRD backed by a named static check in CI,
So that a guarantee is decided by a machine, not by a human remembering to look.

**Acceptance Criteria:**

**Given** the set of structural properties the PRD enumerates,
**When** the harness runs,
**Then** each named property has a check — grep, lint, import-graph or architecture rule — that fails the build on violation, and a property with no check is itself a build failure (FR-56).
**And** the set includes at minimum: no fallback embedder (FR-9), destructive index operations reachable from one entry point only (FR-10), no post-filter in retrieval (FR-14), one *chunk* write boundary with a required scope argument (FR-8), no *tenant*-specific identifier in source (FR-30), no runtime import from the test tree and no fixture path (FR-33), no natural-language string as a translation key (FR-34), no hard-coded locale (FR-35), no outbound call site outside the enumerated adapters (FR-32), no reversible credential storage (FR-48), no secret in source (FR-51), no model-reported confidence field consumed (FR-42), and no banned *confidence bound* phrasing in any locale (FR-23).
**And** each property names the check that enforces it and the file or pattern it inspects.
**And** where a claim cannot be decided by a check or a test, the document's verb is honoured — *asserted by test*, *enforced as a structural property*, or *asserted by review* — and the third is never counted as a passing test (FR-56).

**Epic 1 covers:** FR-8, FR-29, FR-30, FR-31, FR-47, FR-48, FR-49, FR-50, FR-51, FR-52, FR-55, FR-56.

---

## Epic 2: A lawyer hands over a matter and every document is accounted for

A lawyer selects a folder — a USB key, a network share — and leaves. On return: every *pièce* is in the *corpus*, in the *failure register*, or in a declared exclusion, with nothing in two of them and nothing in none. The *denominator* is permanent and on screen, the *worklist* says what needs a human, and the completion summary is readable by someone who is not technical. Closes with the timed 5 000-*pièce* concurrent run that gates every performance commitment downstream.

**Definition of done for the epic:**
- `submitted = in corpus + open failure register entries + declared exclusions` holds after every *import job* and every retry, at the *design target*, asserted by an invariant test (FR-6, FR-57).
- A folder ingests non-blockingly and survives a worker kill at three or more points without losing or duplicating a *pièce* (FR-2, FR-4).
- No fixture layer and no demo override exists anywhere in runtime code, asserted statically (FR-33).
- The timed 5 000-*pièce* concurrent run has produced a real number for OCR + embedding + inference together, and no downstream performance claim precedes it (gate).

### Story 2.1: Folder selection as the whole onboarding gesture

As a lawyer with four years of a *matter* on a USB key,
I want to start an import by choosing the folder, the *matter* and the *RBAC scope* and nothing else mandatory,
So that onboarding is a gesture, not an IT project.

**Acceptance Criteria:**

**Given** an authenticated user,
**When** she starts an *import job*,
**Then** exactly three inputs are mandatory — folder, *matter*, *RBAC scope* — with exactly one optional input on the same screen, the *case theory*, which can be skipped and whose skipping blocks nothing, and no further mandatory configuration screen exists on this path (FR-1, FR-37).
**And** subfolders are traversed to arbitrary depth and the submitted folder structure is reconstructible from the *payload schema* record alone.
**And** the *RBAC scope* selectable is constrained to scopes the user holds or may grant, asserted by test in both directions — she cannot narrow material out of her supervisor's sight nor broaden it to a group she chose (FR-1, FR-49).
**And** the *custodian* is captured at import as a mandatory field, `custodian-undeclared` where genuinely unknown, never blank.
**And** *(failure path)* a folder of zero readable files produces a completed job with a 0/0 *denominator* and an explanatory *worklist* line — not an error dialog, not a silent no-op.
**And** *(failure path)* an attempt to write a *pièce* with a null or empty *RBAC scope* fails the job loudly rather than defaulting to permissive.

> **UX pass required before implementation.** No UX design contract exists yet. The onboarding screen is user-facing.

### Story 2.2: The non-blocking, resumable import job

As a lawyer who wants to keep working while four years of a *matter* import,
I want the job to run in the background and survive a crash without losing or repeating work,
So that a machine restart at hour six does not mean starting over.

**Acceptance Criteria:**

**Given** a running *import job*,
**When** the user does anything else,
**Then** no screen is blocked and no modal shown, and progress is a persistent, collapsed, non-blocking indicator of processed-against-submitted (FR-2).
**And** killing the worker mid-job and restarting resumes from the last committed unit — no indexed *pièce* re-indexed as new, no unprocessed *pièce* skipped — asserted with an induced kill at three or more points (FR-2; Procrastinate over PostgreSQL makes resume a transaction property per AD).
**And** memory is bounded per unit of work: no single *pièce*, however large, need fit in memory whole, and a unit exceeding the bound enters the *failure register* as `resource-exhausted` rather than killing the worker.
**And** *(failure path)* a poison unit that kills the worker is quarantined after a configured number of attempts, entered in the register with its class, and the job proceeds and completes — asserted with a deliberately poisonous unit.
*Note: resumable ingestion is flagged by the work breakdown as likely underestimated. The quarantine rule is what stops resume from looping forever onto the unit that killed it.*

### Story 2.3: Multi-format extraction — the largest surface

As a lawyer whose *matter* is mostly `.msg` with attachments and scanned PDFs,
I want text and structure extracted from every format a litigation *matter* actually contains,
So that the corpus is the *matter*, not the subset that happened to be easy to read.

**Acceptance Criteria:**

**Given** *ingestion*,
**When** it processes a *pièce*,
**Then** it extracts `.msg` (headers, reply chains, embedded attachments), born-digital PDF, scanned PDF via OCR, `.docx`, `.xlsx`, and standalone images via OCR, with OCR running **inside the *tenant* boundary** — no hosted OCR service (FR-3, §15; extract-msg out-of-process and GPL-isolated, Docling + Tesseract 5.5.2 per the stack research).
**And** an email with N attachments yields N+1 *pièces*, each with a stable identifier, provenance to its parent, and the parent's *custodian* inherited.
**And** every *pièce* records extraction method and extractor version, so a transcription is distinguishable from a text layer and a re-extraction is detectable.
**And** *(failure path)* an unsupported format enters the register as `unsupported-format`, counted in the *denominator* — never silently vanished.
**And** *(failure path)* an extraction that yields no text — blank scan, empty `.docx` — enters the register as `extracted-empty` and is **not** counted as in the *corpus*, because otherwise an absence claim would assert it was searched.
*Note: this is the largest single engineering surface in the increment — `.msg` alone is compound-file parsing, RTF-compressed bodies, TNEF, nested messages, charset recovery, reply-chain reconstruction — and the work breakdown flags it as months, not weeks. Do not size it as one story in practice; it is written as one here for traceability and must be split at implementation.*

### Story 2.4: Container expansion and the unit of the denominator

As a lawyer,
I want archives, PDF portfolios and nested messages expanded, with every hidden *pièce* counted,
So that a `.zip` of 500 documents is not recorded as one missing file.

**Acceptance Criteria:**

**Given** a container — `.zip`, `.7z`, PDF portfolio, mailbox export, `.msg` nested in `.msg`,
**When** it is ingested,
**Then** members become *pièces* carrying provenance through the container and inheriting its *custodian*, asserted with a container three levels deep (FR-57).
**And** recursion depth and expansion ratio are bounded by configuration, and a container exceeding either enters the register as `container-unopenable` with the reason — a zip bomb is a register entry, not an outage.
**And** a container that cannot be opened is one entry with cardinality `unknown`, and every *denominator* and absence claim states the unknown explicitly — *"1 archive unopened, contents unknown"*, never "· 1 not indexed".
**And** the unit of the inventory guarantee is the *pièce* counted after expansion, and *submitted* is frozen at completion of enumeration-and-expansion, declaring itself provisional while expansion is in progress.

### Story 2.5: Idempotent ingestion with stable identity

As a lawyer who might import overlapping folders,
I want re-submitting material to neither duplicate nor destroy it, and every *custodian* kept,
So that who held a document — often the fact in issue in *ordonnance 145 CPC* work — is never lost to deduplication.

**Acceptance Criteria:**

**Given** *ingestion*,
**When** a *pièce* is identified,
**Then** its identifier is a deterministic function of **(content, *matter*)** — provenance path is not part of identity — stable across runs, processes and installations, never from a restarting counter (FR-4; per AD-40, `(content, matter)` identity).
**And** importing the same folder twice into the same *matter* leaves the *corpus* count unchanged, every prior *pièce* readable and unmodified, and reports the recognised-already-present count as its own line — asserted by test (FR-4; the v1 defect was ids reused from 1, so a second upload overwrote the first).
**And** importing a file present in two folders yields one *pièce* with two recorded provenance paths and **every *custodian* retained as a queryable set** — deduplication may never collapse two custodians into one.
**And** importing the same file into two different *matters* yields two *pièces*, because *matter* is part of identity — cross-*matter* deduplication is never performed.
**And** *(failure path)* under an induced write conflict — the same *pièce* processed by two workers — the *corpus* contains exactly one copy and the job does not fail.

### Story 2.6: The failure register

As a lawyer,
I want every *pièce* that failed to index enumerated, attributed and actionable, resolved by state change and never by removal,
So that the decisive document that would not open is on a list I can act on, not silently gone.

**Acceptance Criteria:**

**Given** a *pièce* that fails at any stage,
**When** it is recorded,
**Then** the register entry carries filename, submitted path, *matter*, *custodian*, error class, cardinality, resolution state, timestamp and a retry action, with error classes drawn from the enumerated stable set and an unclassified failure recorded as `unknown` with its redacted diagnostic — never dropped (FR-5).
**And** entries are resolved by state change: retrying re-runs *ingestion* for that *pièce* only, a success moves the entry to `resolved` and keeps its history, and the *inventory guarantee* counts open entries only.
**And** a `password-protected` entry offers a credential-supply action; an entry whose only exit is an *override* is a defect of this FR, because it would force a lawyer to record that she excluded a document she could in fact have opened.
**And** a **bulk retry** exists over a filtered set — by class, *matter*, *custodian* — producing one *audit record* entry naming the set, not one per *pièce*.
**And** the register is exportable one *pièce* per line, within the exporting user's *RBAC scope*, recorded in the *audit record*; entries whose *matter* could not be determined are visible only to the *tenant*-wide administrative grant holder (FR-5, FR-49).

> **UX pass required before implementation.** No UX design contract exists yet. The register is a user-facing surface.

### Story 2.7: The inventory guarantee and the permanent denominator

As a lawyer who must one day tell a court what was and was not reviewed,
I want a permanent, on-screen accounting where every submitted *pièce* is in exactly one of three named, countable places,
So that "nothing relevant was silently lost" is a number, not a hope.

**Acceptance Criteria:**

**Given** any *matter*,
**When** its *denominator* is computed,
**Then** `submitted = in corpus + open failure register entries + declared exclusions` holds at all times, each term separately countable and displayed as its own line, nothing in two terms or in none, with no fourth bucket and no unnamed remainder — asserted by an invariant test after every *import job* and every retry, at the *design target* (FR-6 as corrected 21 July 2026, FR-57).
**And** filesystem noise is a declared, configured, countable exclusion class reported as its own line — *"1 240 excluded as filesystem noise"* — one click from the list of what was excluded, neither silently dropped nor dominating the register.
**And** the *denominator* is permanent and visible on the home screen and carries the *failure register* count and the unknown-cardinality containers explicitly (FR-28, ties FR-57).
**And** *(failure path)* a deliberately induced miscount — a *pièce* in two terms, or in none — fails the invariant test, which is a release blocker (SM-3).

### Story 2.8: The embedder fails loudly and the index never deletes itself

As a firm whose *corpus* took days to build,
I want embedding to stop the work rather than degrade silently, and no automatic process to ever wipe the index,
So that one transient error cannot turn retrieval into noise or destroy the *corpus*.

**Acceptance Criteria:**

**Given** the embedder,
**When** it fails — unavailability, rate limit, timeout, dimension mismatch, auth failure,
**Then** it halts the affected unit, records it in the register with its class, generates a *worklist* line, and never produces a *chunk* (FR-9).
**And** there is no fallback embedder: a static check asserts the embedder interface has exactly one non-test implementation, no exception handler in the embedding path constructs an embedder, and no configuration selects one outside the enumerated provider list (FR-9, FR-56; v1 defect: silent 1024→256 hash fallback).
**And** no code path performs a bulk deletion, recreation or truncation of indexed material in response to any error, schema, dimension or version difference — the destructive operations are reachable from exactly one named administrative entry point, asserted statically (FR-10, FR-56; v1 defect: the whole collection wiped on any vector-size mismatch).
**And** a dimension or schema mismatch halts that unit, surfaces an actionable *worklist* line, and leaves the existing *corpus* intact and queryable, with recovery not requiring a full re-index.
**And** *(failure path)* injecting a transient embedder failure into a 1 000-*pièce* job leaves some indexed, the failed ones in the register, the *denominator* consistent, and a retry that completes them — asserted by test.

### Story 2.9: Chunking with provenance to the exact passage

As a lawyer,
I want every *chunk* traceable to the exact place in the source it came from, and a failed resolution shown as failed,
So that an extract in an export a court reads later cannot silently be pointing at nothing.

**Acceptance Criteria:**

**Given** a *chunk*,
**When** the interface resolves it,
**Then** it opens the source *pièce* and locates the passage, and re-chunking the same *pièce* with the same configuration produces identical *chunks* with identical identifiers (FR-11).
**And** a resolution that fails at read time — *pièce* gone, text changed under re-extraction, containment check fails — is surfaced as such wherever the extract appears and marks the containing *audit record* export as degraded; an extract that no longer resolves is never displayed as though it did.
**And** chunking configuration is *configuration-as-data*, recorded on the *chunk*, so *chunks* under different configurations are distinguishable.

### Story 2.10: The completion summary — tasks, not a log

As a lawyer returning to the machine after dinner,
I want a summary whose first element is the *denominator* and whose second is the human tasks this job created,
So that I see what needs me, not a wall of technical events.

**Acceptance Criteria:**

**Given** a finished *import job*,
**When** the user opens the completed indicator,
**Then** the first element is the *denominator* and the second is the *worklist* lines this job generated, each phrased as an action in the lawyer's language and clickable through to its referent; a non-actionable line is not shown here (FR-7, FR-27).
**And** the summary distinguishes with counts: newly indexed, recognised as already present, excluded as filesystem noise, expanded from containers, and entered in the register broken down by error class.
**And** the summary is reachable again later from the *matter* and from the *audit record* — not a transient notification.

> **UX pass required before implementation.** No UX design contract exists yet. The *worklist* and completion summary are user-facing.

### Story 2.11: The worklist and the matters zone

As a lawyer opening APX,
I want the home screen to open on what needs me, with my *matters* below it as navigation,
So that the queue is never pushed off the screen by a firm with three hundred *matters*.

**Acceptance Criteria:**

**Given** the home screen,
**When** it renders,
**Then** the top zone is the *worklist* — actionable lines only, each an action in the lawyer's language, never a technical state; a non-actionable line is not shown there (FR-27), with aggregation and a cap so that at the *design target* it does not become the log it forbids.
**And** below it the *matters* zone lists *matters* within the user's *RBAC scope* with each one's *scoped denominator*, whether a job is running, whether a ranking exists and is stale, whether a *sampling run* is open, and when the user last touched it (FR-60).
**And** a *matters* line is navigation, not a task: no line type appears in both zones, asserted by test, and the *worklist* is always the top zone (FR-60).
**And** *(failure path)* a *tenant* with three hundred *matters* does not push the *worklist* off the screen — the *matters* zone is bounded and ordered by last activity with the remainder one click away.

> **UX pass required before implementation.** No UX design contract exists yet. The home screen is the most-seen surface in the product.

### Story 2.12: The corpus and gold-set evaluation pipeline

As the APX build with no client corpus,
I want the evaluation corpora acquired, licence-cleared, degraded and merged behind a gate that blocks ranking work until recall is measured,
So that ranking quality is measurable from the first line rather than asserted — the exact thing v1 never did.

**Acceptance Criteria:**

**Given** the evaluation corpora (Enron/EDRM, TREC Legal Track, mechanically degraded French public text),
**When** they are assembled,
**Then** they enter through *ingestion* as configured data sources, never as fixtures, with licence verification of the specific distribution used an explicit recorded step (FR-54, FR-33).
**And** the degradation pipeline is part of the test surface: each mechanical degradation of real French public text is asserted against the *failure register* class it must produce — a corrupted `.msg` → `corrupt-file`, a password-protected PDF → `password-protected`, an unopenable archive → `container-unopenable`.
**And** the *gold set*'s relevance judgments are mapped onto this product's notion of relevance — its *case theory*, taxonomy and **the line** — and the mapping is written down, versioned and reviewable.
**And** a **merge gate** blocks any ranking or triage code from merging before SM-2 executes against the *gold set* in CI (FR-54; this gate precedes all of Epic 4).
**And** the pipeline runs at the *design target*, not extrapolated, and the *denominator* is verified against it.
*Note: this is a product-sized build with no user-visible output, and an adversarial review named it among the components most likely to be quietly dropped. It has a numbered requirement precisely so that dropping it is a visible decision. Salvage: the v1 labelled mock corpus and its gold `manifest.json` are ranked the single most valuable thing to lift, per the retrospective — they are a ready-made eval set.*

### Story 2.13: The timed 5 000-pièce concurrent run — the gate

As the APX build,
I want a real measurement of OCR, embedding and inference running **concurrently** on one machine over 5 000 *pièces*,
So that every wall-clock promise downstream rests on a number rather than on three components each sized as if it owned the machine alone.

**Acceptance Criteria:**

**Given** one machine at each supported inference profile (the GPU profile and the CPU profile),
**When** 5 000 real *pièces* — including scanned PDFs requiring OCR — are ingested with extraction, OCR, embedding and LLM judgement running concurrently,
**Then** the wall-clock, peak memory and peak VRAM are measured and recorded, not extrapolated from single-component benchmarks (Open Risk 3 from the spine: nobody summed the machine).
**And** the measured figures are the basis for any latency or throughput ceiling stated anywhere downstream; until they exist, no such ceiling may be asserted (NFR-2, ties SM-C4).
**And** the run is documented as a **measurement, not a feature** — it ships no user-visible capability and exists to falsify or confirm the machine sizing.
**And** *(failure path)* if the concurrent run exceeds the CCBE €2 000 machine's envelope, that is a recorded finding that revises the hardware ask or the cascade aggressiveness — it is not smoothed over.
*Note: this story closes Epic 2 and gates Epics 3, 4 and 5. It is the first thing to measure and it is written last in the epic so that there is something real to measure.*

**Epic 2 covers:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10, FR-11, FR-27, FR-28, FR-33, FR-54, FR-57, FR-60.

---

## Epic 3: A lawyer finds a pièce, and can prove another does not exist

Two engines with different truth status: one that finds and never claims completeness, one that proves and returns the whole match set. Every result declares which it is, in the interface and in any export. The *RBAC scope* is a pre-filter on the query itself, so a wall cannot leak silently. And the *pièce* viewer, because reading the document is the job.

**Definition of done for the epic:**
- A semantic result never labels itself complete and a deterministic result always carries its *denominator*, asserted at the one construction site per engine (FR-12, FR-13, FR-15).
- An adversarial suite whose highest-similarity matches are deliberately out of *RBAC scope* returns zero out-of-scope results and zero out-of-scope metadata across both engines (FR-14).
- The viewer opens every extracted format at the highlighted passage, inside the *tenant* boundary, applying the scope pre-filter (FR-44).

### Story 3.1: Semantic retrieval, marked suggestive

As a lawyer looking for *pièces* about a topic,
I want ranked results that never pretend to be the complete set,
So that I am never misled into thinking a suggestion was a proof.

**Acceptance Criteria:**

**Given** a semantic query,
**When** results return,
**Then** they are ranked with a stated k and the result set declares *truth status* = **suggestive**, each result carrying its *pièce* identity and *chunk* provenance and openable at the source position (FR-12).
**And** the set never displays or exports a count phrased as a total; it says "top N of the corpus by similarity" or equivalent wording that cannot be read as completeness.
**And** a static check asserts *truth status* is set at exactly one construction site per engine and is constant there, so no similarity threshold in any configuration can label a semantic set **exhaustive** (FR-12, FR-56).
**And** any **similarity threshold** used is *configuration-as-data*, recorded with the result, with a defined default, and a default that disables the behaviour it governs is a defect (FR-12; the v1 instance is `addendum.md` §4).

### Story 3.2: Deterministic exhaustive search — the one thing that can prove absence

As a lawyer who must tell a court a term appears nowhere in the *corpus*,
I want an exact search over the full stored text that returns the complete match set with its *denominator*,
So that I can say "searched everything indexed, zero occurrences" and defend it.

**Acceptance Criteria:**

**Given** a deterministic query over the stored full text (FR-8's addressable text, PostgreSQL-native full-text per AD-21),
**When** it runs,
**Then** it returns the complete match set — not a top-k, not a sample — and the result set declares *truth status* = **exhaustive** and carries its *denominator*, including the *failure register* count and any unknown-cardinality containers (FR-13, FR-57).
**And** the search normalises French correctly — accents, elision, hyphenation, case — by a defined, tested rule, so that "l'état" and "etat" and "État" behave as specified rather than by accident (FR-13).
**And** an absence claim carries its *RBAC scope* and its *denominator* in the exported wording — *"searched everything indexed within this scope; the register lists 2 800 unreadable and 1 archive of unknown contents"* — never a bare "not found".
**And** *(failure path)* a *pièce* whose OCR was too poor to index is qualified in the absence claim, because it is in the *corpus* but its text may not be, and an unqualified claim would be v1's "guess in the costume of a proof" relocated to the extraction layer.

> **UX pass required before implementation.** No UX design contract exists yet. Search results and the absence statement are user-facing.

### Story 3.3: RBAC scope as a query pre-filter, never a post-filter

As a firm bound by Chinese walls,
I want the scope constraint applied inside the query itself and impossible to bypass,
So that a cross-*matter* leak — silent, and a professional-conduct violation — cannot happen through any read.

**Acceptance Criteria:**

**Given** any read of *tenant* data — both engines, the viewer, exports, aggregates, every non-search screen,
**When** it executes,
**Then** the *RBAC scope* predicate is applied as a constraint on the query itself, resolved at query time from the single authoritative source, never a post-filter and never denormalised onto rows (FR-14, per AD-13 and AD-14 which binds **every** read, not only search).
**And** a static check asserts exactly one code path constructs a tenant-data read and no read filters after returning (FR-14, FR-56).
**And** an adversarial suite issues queries whose highest-similarity matches are deliberately outside the caller's scope, over both engines, and asserts zero out-of-scope results and zero out-of-scope metadata — counts, snippets, identifiers, filenames, *denominator* figures (FR-14).
**And** the *denominator* and any *confidence bound* shown are computed within the user's scope, so the numbers cannot leak the existence of material she may not see.
**And** *(failure path)* the mutating adversarial suite revokes a scope while a session is open and grants one mid-*sampling run*, asserting the wall holds in its new position immediately and its old never (FR-14, FR-49).
**And** *(failure path)* a user with no scope receives an empty *corpus*, not the whole one — fail-closed, asserted for administrative and system identities alike.

### Story 3.4: Every result set declares its truth status

As a lawyer,
I want finding and proving to be visibly and permanently distinct, carried by the data,
So that the distinction survives into an export a court reads without the system.

**Acceptance Criteria:**

**Given** any result set from any engine,
**When** it is shown or exported,
**Then** its *truth status* is present in the interface, in every export, and in the *audit record* entry for the query, with the two statuses visually and verbally distinct and the distinction surviving export to any format offered (FR-15).
**And** no interface element combines results from both engines into one undifferentiated list.
**And** an exported **suggestive** set carries wording that cannot be read as completeness; an exported **exhaustive** set carries its *denominator*.

### Story 3.5: The pièce viewer

As a lawyer,
I want to read any *pièce* inside the product, at the passage, for every format,
So that reading the document — the actual job — never requires leaving the tool or sending content outside the firm.

**Acceptance Criteria:**

**Given** any format FR-3 extracts,
**When** the lawyer opens a *pièce*,
**Then** it is **rendered**, not merely extracted: `.msg` with headers, body and reply chain and navigation to each attachment as its own *pièce*; born-digital PDF; scanned PDF with the OCR text layer over the page image; `.docx`; `.xlsx`; images — and a format that cannot be rendered offers the original and says so, never an empty pane (FR-44).
**And** from any *chunk* or *retained extract* the viewer opens the source at the highlighted passage, asserted per format with a planted passage.
**And** the viewer applies the *RBAC scope* pre-filter: a *pièce* outside scope is not renderable, not downloadable, and its existence is not disclosed (FR-44, FR-14).
**And** opening a *pièce* is recorded in the *audit record* and is the fact that distinguishes a *validation act* performed after reading from one performed from the list (ties FR-45).
**And** rendering happens inside the *tenant* boundary — no *pièce* content sent to any third-party rendering or conversion service, in any deployment.
**And** *(failure path)* a *pièce* larger than the configured rendering bound opens progressively or offers the original; it never blocks the interface or exhausts the client.

> **UX pass required before implementation.** No UX design contract exists yet. The viewer is a central user-facing surface.

**Epic 3 covers:** FR-12, FR-13, FR-14, FR-15, FR-44.

---

## Epic 4: A lawyer receives a ranked working set and keeps control of it

The heart of the product. An optional *case theory*, a cascade that spends the model only where cheap filters cannot decide, one ranked order with nothing deleted, and **the line** the tool commits to and the lawyer moves at a priced cost. Confidence is derived, never self-reported. Every edit is a per-*pièce* diff with a live *change log*, and a single *pièce* can cross **the line** without dragging it.

**Definition of done for the epic:**
- Re-running a fixed *ranking version* over a fixed *corpus* reproduces the same order, *pièce* for *pièce*, with a deterministic tie-break (FR-39).
- A *pièce* in the *discarded set* is still returned by exhaustive search — nothing is deleted or excluded (FR-16, FR-21).
- No user edit re-ranks or overwrites another row, and human-set values survive re-ranking marked as such (FR-20).
- No ranking or triage code was merged before the *gold set* merge gate (Epic 2) executed SM-2 in CI.

### Story 4.1: The optional case theory

As a lawyer who knows what she is trying to establish,
I want to state it in my own words at any time and have the ranking be relative to it,
So that relevance is a relation to my question, not a property the tool guessed at.

**Acceptance Criteria:**

**Given** a *matter*,
**When** the lawyer writes, rewrites or deletes a *case theory*,
**Then** it is free text in her language, optional at import and writable at any later moment, never mandatory, and its absence never blocks *ingestion*, ranking or anything else (FR-37, FR-1).
**And** writing or rewriting produces a new version, retains previous versions readably, is recorded in the *audit record* with actor and timestamp, and offers a re-rank that is explicit and never automatic (FR-37).
**And** a re-rank under a new *case theory* version produces a new *ranking version*, and human-set values, *validation acts* and *pins* survive it marked as human-set.
**And** *(failure path)* deleting the *case theory* does not delete the rankings computed under it, which remain readable bound to the version that produced them.

### Story 4.2: The relevance judgement — a cascade, cheap filters first

As a firm paying for inference,
I want relevance assessed by a staged cascade that reaches the language model only for the *pièces* cheap filters cannot separate,
So that cutting the model's workload ten-fold is cheaper than buying ten times the machine — the difference between the €2 000 box and the €20 000 one.

**Acceptance Criteria:**

**Given** the *pièces* of a *matter*,
**When** ranking runs,
**Then** the cascade has three stages, its boundaries *configuration-as-data*: (1) deterministic filters and near-duplicate grouping — type, participant roles, dates against the *case theory*'s period, exact and near-duplicate families, obvious noise; (2) cheap semantic scoring over the FR-9 embeddings; (3) an **LLM judgement applied only to the uncertain band**, plus a mandatory sample of the confident bands so calibration is measurable (FR-38).
**And** the **share of *pièces* reaching stage 3 is measured and recorded per run** (SM-18) — the number that decides cost, latency and egress, and that a regression would otherwise hide.
**And** near-duplicate families are grouped and judged as a family, one representative carrying it, members retaining their own identity, provenance and *custodian*, so forty near-copies of one thread do not occupy forty positions and are not counted by a *sampling run* as forty independent draws (FR-38; the near-duplicate threshold is an input to OQ-4).
**And** *(failure path)* the LLM provider being unreachable halts stage 3, records the affected units, and leaves stages 1–2 results intact — it does not fail the whole run silently.
*Note: the per-*pièce* LLM judgement is the largest inference cost and the largest egress event in the system (NFR). The cascade is load-bearing, not an optimisation.*

### Story 4.3: The ranked order and the reproducible ranking version

As a lawyer who may have to defend a ranking in front of a court,
I want one ranked order per *matter* that reproduces exactly from its recorded version, with a specified tie-break,
So that "reconstructible from the audit record alone" is true, not aspirational.

**Acceptance Criteria:**

**Given** a ranking act,
**When** it completes,
**Then** it produces exactly one ranked order plus a *ranking version* recording the full identity of what produced it — *case theory* version, model identity, prompt version, temperature and every sampling parameter, cascade configuration, embedder identity, chunking configuration, schema version (FR-39).
**And** re-running a fixed *ranking version* over a fixed *corpus* reproduces the same order *pièce* for *pièce*, asserted by test; where the model is non-deterministic at the configured temperature, the *ranking version* records the scores so the order is reconstructible even where the judgement is not repeatable.
**And** the tie-break is deterministic and specified — ties broken by a stable key recorded in the *ranking version*, never by the order a store returned — because a tie spanning **the line** would otherwise reshuffle set membership on recomputation with no recorded event and silently invalidate any *sampling run* drawn from it (FR-39).

### Story 4.4: Confidence is derived, never self-reported

As a lawyer whose *confidence bound* must mean something,
I want the per-*pièce* confidence derived from observable quantities and never from a number the model made up about itself,
So that a statistical statement does not rest on the model's own opinion of its certainty.

**Acceptance Criteria:**

**Given** a *pièce* in a ranking,
**When** its confidence is computed,
**Then** it is derived from observable quantities — score margin, agreement across cascade stages, agreement across repeated judgements — never from a figure the model states about itself, and a static check asserts no field parsed from a model response is named or used as a confidence and the derivation has one implementation (FR-42, FR-56).
**And** the derivation method is recorded in the *ranking version* and reproducible from it.
**And** confidence is calibrated against the *gold set*: among *pièces* assigned a given band, the observed relevant share is measured and recorded (SM-17), and a systematically overconfident derivation fails the build.

### Story 4.5: Per-pièce labelling against the taxonomy

As a lawyer,
I want every *pièce* to carry exactly one label from my firm's taxonomy, changeable without moving it in the ranking,
So that classifying a document and ranking it are two acts, not one.

**Acceptance Criteria:**

**Given** a ranking,
**When** labels are assigned,
**Then** every *pièce* carries exactly one label from the *tenant*'s configured taxonomy, or the explicit `unlabelled` — no null, no default (FR-40, FR-30).
**And** changing a label never changes a *pièce*'s position and never moves it across **the line** (that is FR-43).
**And** a label change is an ordinary cell edit: it produces a *change log* entry, survives re-ranking marked as human-set, and is reversible from the *change log* (FR-40, FR-20).

### Story 4.6: Per-pièce confidence and a justification derived from named evidence

As a lawyer reading a ranking,
I want each *pièce* to show why it is where it is, in one line, backed by extracts I can verify,
So that the tool's assessment is checkable rather than a fluent sentence I must trust.

**Acceptance Criteria:**

**Given** a *pièce* in the ranking,
**When** its justification is shown,
**Then** it carries a confidence value and a one-line justification in the user's language readable without opening the *pièce* (FR-18), generated from a stated input set — the *case theory* version or the named intrinsic signals, and the specific *retained extracts* the judgement used, each named by *chunk* identifier and resolvable to a source position (FR-41).
**And** every *retained extract* passes exact-containment verification against its source at the moment it is shown; a justification whose extracts do not resolve is shown as **unverified**, never as ordinary (FR-41, FR-11).
**And** the justification expands into the *audit drawer* showing the extracts behind it, and is reversible in one action recorded in the *audit record* (FR-18).
**And** the justification states the source *pièce*'s language where it differs from the interface language (FR-41, FR-36).

> **UX pass required before implementation.** No UX design contract exists yet. The ranking table and per-*pièce* justification are central user-facing surfaces.

### Story 4.7: One ranked order, nothing deleted, nothing categorised

As a firm bound by "never destroy a document",
I want triage to be one ranked order with the *retained* and *discarded* sets derived from it, nothing stored as membership,
So that reversibility is a structural property, not a promise someone must keep.

**Acceptance Criteria:**

**Given** a *matter*,
**When** it is ranked,
**Then** the system holds exactly one ranked order per *matter* per *ranking version*, and the *retained set* and *discarded set* are derived from that order, the position of **the line** and the *pins* — never stored as memberships (FR-16, FR-43).
**And** no triage operation deletes a *pièce*, removes it from the *corpus* or excludes it from retrieval — asserted by test: a *pièce* in the *discarded set* is still returned by exhaustive search (FR-16, FR-13).
**And** re-running ranking produces a new *ranking version*; previous versions remain readable, and every *confidence bound*, *audit record* entry, *pin* and **the line** position stays bound to the version it was computed against.
**And** every surface naming "the discarded set" or "the retained set" names the *ranking version* it means, and the number of retained versions is bounded by configuration with those referenced by a bound, a *pin*, an export or the *audit record* exempt.

### Story 4.8: The tool draws the line and commits

As a lawyer who is paying not to make the judgement herself,
I want the tool to commit to a recommended cut with a stated basis, not hand me an undifferentiated ranking,
So that a ranked list that refuses to decide does not push the work back onto me.

**Acceptance Criteria:**

**Given** a completed ranking,
**When** **the line** is placed,
**Then** it has a position chosen by the system with a stated basis — the *case theory* where one exists, or the named intrinsic signals — and the interface states the commitment in words, "in my view, everything above this", not merely a divider (FR-17).
**And** **the line**'s position is stored as an ordinal cut over a named *ranking version* together with the identity of the last retained *pièce*, with author and timestamp — never a bare score, never a bare integer (FR-17).
**And** *(failure path)* an import that adds *pièces* does not silently move what **the line** designates, because it is stored against the last retained *pièce*, not a bare position 180 that becomes position 180 of a larger set.
**And** changing **the line** never reorders the underlying ranked order.

> **UX pass required before implementation.** No UX design contract exists yet.

### Story 4.9: Moving the line is priced

As a lawyer deciding how much to read,
I want to see the cost and the benefit of moving **the line** before I move it, honestly labelled,
So that the recall/precision trade-off is a dial I control with a price shown, not a hidden default.

**Acceptance Criteria:**

**Given** a user repositioning **the line**,
**When** she considers a candidate position,
**Then** the interface states the change in the number of *pièces* to read and the change in the **estimated prevalence of relevant material in the resulting discarded set** — "400 more pièces to read; the estimated share of the discarded set that is relevant falls from about 3% to about 0.4%" — and never states a "risk of having missed a relevant document", which is not what any estimator here produces (FR-19, §0.2).
**And** the priced figure is labelled on screen as a **projection from the ranking**, not a sampling bound: it is a model estimate where nothing has been sampled, and a completed *sampling run*'s statement is never shown in the same visual register (FR-19).
**And** *(failure path)* where the projection cannot be produced, the move still shows the change in *pièces* to read, and says the prevalence projection is unavailable rather than inventing one.

> **UX pass required before implementation.** No UX design contract exists yet. The priced move is a subtle and dangerous surface — the labelling that separates projection from bound is the safeguard.

### Story 4.10: The editable cell-by-cell table with a live change log

As a lawyer correcting the tool,
I want to edit any cell without the tool undoing my other edits, with each change logged beside the row,
So that correcting the machine never costs me the correction I made a minute ago — the named requirement that turned out to be the architecture's invariant.

**Acceptance Criteria:**

**Given** the triage table,
**When** the lawyer edits a cell,
**Then** committing changes that cell and nothing else — asserted by test: after N edits across N rows, all N values hold (FR-20).
**And** no user edit triggers regeneration, re-ranking or re-classification of any other row; any re-ranking is a separate explicit user-initiated act producing a new *ranking version* that never overwrites edits — edited values survive re-ranking marked as human-set (FR-20, FR-16).
**And** each edit produces a *change log* entry beside the row immediately: previous value, new value, author, timestamp.
**And** *(failure path)* an explicit re-rank after edits preserves every human-set value and marks it as such, rather than replacing it with a fresh machine value.

> **UX pass required before implementation.** No UX design contract exists yet. This is the surface the whole "the document is the source of truth, the AI only proposes" principle lives on.

### Story 4.11: The pin — moving a single pièce across the line

As a lawyer who knows one discarded document is decisive,
I want to move that one *pièce* across **the line** without dragging the line past everything above it,
So that retaining the decisive piece does not force me to retain four hundred others.

**Acceptance Criteria:**

**Given** a ranked *matter*,
**When** the lawyer pins a *pièce* into or out of the *retained set*,
**Then** the *retained set* changes by exactly one *pièce*, the ranked order does not change, **the line** does not move, and no other *pièce*'s membership changes (FR-43).
**And** a pin requires a one-line reason and is recorded as an *override* (FR-25), because it contradicts a machine assertion.
**And** pins survive re-ranking and carry to new *ranking versions* marked as human-set until explicitly removed, and removing a pin is itself a recorded reversible act.

### Story 4.12: Never hard-delete, proven by a bounded probe

As a firm,
I want no user-facing action anywhere to destroy data, proven by exercising every action,
So that "triage never destroys" is checked against reality, not asserted about all possible behaviour.

**Acceptance Criteria:**

**Given** the registry of user-reachable actions (whose completeness is a structural property, FR-56),
**When** the bounded runtime probe runs,
**Then** it executes each action and asserts no reduction in the count of stored *pièces*, *audit record* entries, *change log* entries or *failure register* entries (FR-21).
**And** no control performs a hard deletion of a *pièce*, *chunk*, *audit record* entry, *change log* entry or *failure register* entry; any action a user could read as deletion is a reversible, labelled, recorded state change (FR-21, FR-5).
**And** *(failure path)* an action added to the product but not to the registry fails the build (FR-56).

### Story 4.13: Freshness and staleness of derived artefacts

As a lawyer who must not read a false number off the screen,
I want any derived artefact marked stale the instant an input changes — including a new import,
So that the north-star sentence can never be exported as current while its population has grown underneath it.

**Acceptance Criteria:**

**Given** a derived artefact — a ranked order, **the line**'s position, a review-effort estimate, a *confidence bound*, an *exhaustive* result set,
**When** any input changes,
**Then** it is marked stale, on the complete trigger list: a new *ranking version*; a move of **the line**; a *pin* added or removed; a *case theory* revision; a configuration change affecting retrieval, ranking or the estimator; an *RBAC scope* change affecting the population; **and any ingestion into the *matter*** (FR-58).
**And** *pièces* ingested into a ranked *matter* are in neither set — a third state FR-16 forbids — so ingestion marks the ranking and any *confidence bound* stale, generates a *worklist* line offering a re-rank, and states the count of unranked *pièces* wherever the sets are counted (FR-58).
**And** a stale *confidence bound* cannot be exported as current, cannot be copied as text without its staleness in the copied string, and is visually distinct wherever it appears.
**And** staleness is resolved only by explicit user-initiated recomputation producing a new artefact — never by elapsed time, a background job or being viewed.

**Epic 4 covers:** FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-37, FR-38, FR-39, FR-40, FR-41, FR-42, FR-43, FR-58.

---

## Epic 5: A sceptic audits what was set aside and says a defensible sentence

A random draw from the *discarded set*, verdicts recorded, and a *confidence bound* stated as a prevalence bound a lawyer can say to a client or a judge — or counts only, if the estimator cannot be proven sound. The *audit record* is atomic, chained, and detectably incomplete rather than silently so; *overrides* carry a written reason; the *validation act* is real and bulk acceptance is never undetectable.

**Definition of done for the epic:**
- A *sampling run* freezes its population by explicit identifier list and invalidates itself in flight if the population changes (FR-22).
- The estimator ships only if a simulation harness shows a stated 95% bound holds in at least 95% of runs against populations whose truth is known; otherwise the product emits counts only (FR-23, SM-1).
- An action whose *audit record* entry cannot be written fails, and a gap in the chain is detectable by a reader holding only the export (FR-53).

### Story 5.1: Random draw from the discarded set, population frozen

As a sceptical senior lawyer,
I want a verifiably random sample from the whole *discarded set*, frozen for the duration,
So that an hour of my verdicts cannot silently become worthless because the population moved underneath me.

**Acceptance Criteria:**

**Given** a *matter* with a *discarded set*,
**When** a *sampling run* is started,
**Then** the user sets a sample size or requests a target *confidence bound* and is given the size achieving it under the hypergeometric estimator, drawn **without replacement** over the whole *discarded set* within her *RBAC scope* — not a convenient or already-loaded subset (FR-22).
**And** where the required size equals the *discarded set* the run is a **census**, labelled as one, producing "every discarded pièce was reviewed; none was relevant" — a categorically stronger statement than a bound; where a target bound is unreachable at any size, the tool says so and offers the best achievable.
**And** the population is frozen: the run records the *ranking version*, the position of **the line**, the *RBAC scope* and the **explicit identifier list** of the drawn *pièces* — a seed alone is insufficient.
**And** *(failure path)* ingestion, re-ranking or a line move during a run marks it **invalidated-in-flight** and tells the user immediately, rather than letting the verdicts silently become worthless (FR-22, FR-58).

### Story 5.2: The hypergeometric estimator and the census crossover

As the APX build,
I want the prevalence estimator implemented as standard hypergeometric statistics with the census crossover handled,
So that the number behind the north-star sentence is sound by construction rather than by hope.

**Acceptance Criteria:**

**Given** a completed draw of size n from a *discarded set* of size N with k relevant found,
**When** the estimator computes,
**Then** it produces a **hypergeometric** (finite-population) upper confidence bound on the **prevalence** of relevant material in the *discarded set* at a stated confidence level — never a probability that nothing was missed (§0.2, FR-23).
**And** the estimator's five hard inputs are each answered explicitly in the design and recorded: near-duplicate family structure (a family is not n independent draws), the census-versus-sample crossover, repeated sampling over one population, population freezing, and the projection at an unsampled position (OQ-4, FR-22, FR-38).
**And** the near-duplicate grouping of FR-38 feeds the unit of the draw, so a family counts as it should rather than as its member count.
*Note: the work breakdown flags the estimator as the most likely single point to be underestimated. It is split across 5.2, 5.3 and 5.4 for that reason.*

### Story 5.3: The simulation gate — the estimator ships only if proven

As a firm that will say this number to a judge,
I want the estimator validated by simulation against populations whose truth is known, in CI,
So that an unsound estimator cannot ship — the exact discipline the false "1.5%" claim failed.

**Acceptance Criteria:**

**Given** the estimator,
**When** the simulation harness runs in CI,
**Then** it generates populations at varying relevant-item prevalence and varying duplicate structure, runs the sampling procedure many times, and asserts a stated C% bound holds in at least C% of runs — and an estimator that fails does not ship (FR-23, SM-1).
**And** SM-1 asserts **soundness**, not merely reproducibility of the number.
**And** the harness records explicitly that it validates the estimator against its assumed model, **not** the assumption that a real *discarded set* resembles the simulated ones — which is what the *gold set* and calibration (SM-17) are for, and where the honest residual uncertainty lives.
**And** *(failure path)* if the simulation cannot be made to pass, the product emits the counts-only fallback and no bound (ties 5.4).

### Story 5.4: The confidence bound as a sentence, or counts only

As a sceptical lawyer,
I want a completed run to give me a sentence I can say to a client or a court, or honest counts if no defensible bound exists,
So that I am never handed a number nobody can defend.

**Acceptance Criteria:**

**Given** a completed *sampling run* with a proven estimator,
**When** the sentence is produced,
**Then** it reads "N pièces sampled at random from the M discarded; K relevant. With C% confidence, at most X% of the discarded set — about Y pièces — is relevant.", copyable as text, carrying its *RBAC scope* and its staleness state in the copied string (FR-23, FR-58).
**And** where the estimator is not proven sound, the product emits **counts only** — "200 pièces sampled at random from the 1 400 discarded; none relevant" — with no bound and no projected figure, and says so (FR-23).
**And** the sentence is regenerable from the *audit record* with **no** model call — a statistical claim never depends on the network (FR-55, FR-36).
**And** a static check asserts no banned phrasing — "risk of having missed", or any wording implying a probability that nothing remains — appears in any locale's string set (FR-23, FR-56).

> **UX pass required before implementation.** No UX design contract exists yet. The sentence and its visual register — distinct from the priced projection of FR-19 — are the product's most consequential text.

### Story 5.5: The audit record

As a firm that may have to defend every decision,
I want an append-only record of everything that matters, each entry sequenced and attributed,
So that "auditability is non-negotiable" — the one named client requirement — becomes a mechanism rather than a slide.

**Acceptance Criteria:**

**Given** the *audit record*,
**When** any recordable act occurs,
**Then** it appends an entry and never edits or removes one — a correction is a new entry (FR-24).
**And** the record captures at minimum: who validated what and when via a *validation act*; every *case theory* and revision; the *ranking version*, *payload schema* version and application version; modified-versus-accepted values; every position of **the line** with author and priced statement; every *pin*; every *sampling run* with its draw, frozen identifier list, verdicts and *confidence bound*; every *override* with reason; every retrieval with *truth status* and *RBAC scope*; every *import job* with *denominator*; every configuration change; every scope grant, revocation and re-scope with its authority (FR-24).
**And** every entry carries an actor, a wall-clock timestamp, a **monotonic sequence number from a single authority**, and a *matter*; system-initiated entries name the system component as actor (FR-24; per AD-43 the sequence authority is decided, and matterless acts like scope grants are handled by a named tenant-level chain).

### Story 5.6: Overrides with a mandatory one-line reason

As a firm,
I want every act that contradicts the machine or bypasses a guard to cost one written sentence,
So that a deliberate exception is a recorded, arguable decision rather than an invisible one.

**Acceptance Criteria:**

**Given** an action that contradicts a machine assertion made with stated confidence, removes a *failure register* entry without successful *ingestion*, or bypasses a system guard,
**When** the user commits it,
**Then** it is classified as an *override* and cannot be committed without a free-text reason, stored verbatim, attributed and timestamped, and appearing in the export (FR-25).
**And** *overrides* are countable and filterable in the *audit drawer* and the export, separately from ordinary modifications.
**And** *(failure path)* an *override* submitted with an empty reason is refused — the reason is mandatory, not encouraged.

### Story 5.7: The audit drawer and its export

As a sceptical lawyer and as a *bâtonnier* reading later,
I want the reasoning behind any one *pièce* and the record for a whole *matter*, both readable and both exportable as documents,
So that the trust mechanism leaves the building in a form a court can read without the system.

**Acceptance Criteria:**

**Given** any *pièce*,
**When** the *audit drawer* opens,
**Then** it shows the *pièce*'s confidence, the *retained extracts* behind it (each resolving to a *chunk* and source position), the proposed *audit record* entry in readable form, and reversible actions each producing an *audit record* entry (FR-26).
**And** the *audit record* for a *matter* is exportable as a document within the user's *RBAC scope*, containing the *scoped denominator*, the *case theory* and revisions, the position history of **the line**, all *pins*, all *sampling runs* and their *confidence bounds*, all *overrides* with reasons, the *validation acts*, and the modified-versus-accepted breakdown (FR-26).
**And** an extract that no longer resolves is shown as such and marks the export degraded (FR-11) — self-containment is verified at read time, not only at export time.

> **UX pass required before implementation.** No UX design contract exists yet. The *audit drawer* is the trust surface the sceptic lives in; it is fully designed in the v1 mockup `maquette_anfr_v2.html` (salvage candidate).

### Story 5.8: The validation act

As a supervising partner,
I want "a human read this" to be a real per-*pièce* gesture that records whether the document was actually opened, with no undetectable bulk acceptance,
So that a click-through cannot masquerade as review — the failure the whole trust architecture must not end in.

**Acceptance Criteria:**

**Given** a *pièce*,
**When** a lawyer performs a *validation act* from the table, the viewer or the *audit drawer*,
**Then** it states its meaning in her language — "I have read this pièce and I accept the tool's assessment of it" — and produces one *audit record* entry carrying actor, timestamp, sequence number, *matter*, *pièce*, *ranking version*, the values accepted, and **whether the *pièce* was opened in the viewer before the act** (FR-45, FR-44).
**And** "accepted as-is" exists **only** where a *validation act* occurred — no default, no elapsed time, no scroll position, no screen visit produces it — asserted by test: a *matter* left open and scrolled end to end yields zero accepted-as-is entries (FR-45).
**And** *(failure path)* there is no bulk-accept control that produces undetectable acceptance; any bulk gesture records per-*pièce* entries each marked as accepted-from-the-list rather than read, and SM-C2 observes the ratio.

### Story 5.9: Audit record continuity

As a *bâtonnier* holding only the exported record,
I want an action whose entry cannot be written to fail, and any gap in the record to be detectable,
So that the blessed backup restore cannot quietly truncate the audit trail and still pass its own check.

**Acceptance Criteria:**

**Given** a recordable action,
**When** its *audit record* entry cannot be written,
**Then** the action fails — moving **the line**, committing an *override*, completing a *sampling run*, a *validation act*, granting a scope and changing configuration are each atomic with their record — asserted by test with the audit store made read-only mid-action (FR-53).
**And** entries carry a monotonic sequence number from a single authority and a **chain value over the previous entry**, so a gap, reordering or truncation is detectable by a reader holding only the export, and a continuity check runs on export with its result on the export's face (FR-53).
**And** the chain is verified on restore and a failed verification is surfaced, never silently repaired (FR-53, FR-52); the chain head is held outside the restorable store so a restore cannot forge a clean chain (per AD-35).

**Epic 5 covers:** FR-22, FR-23, FR-24, FR-25, FR-26, FR-45, FR-53.

---

## Epic 6: The work leaves the building, in the firm's own language

The *retained set* comes out as a deliverable rather than staying inside the tool. The client-pushed diagnostic export carries counts and never content. The interface, dates, sorting and the model's own instructions all follow the firm's language. And the usability gate is exercised against a real non-technical reader.

**Definition of done for the epic:**
- The *retained set* exports as an ordered numbered list that is the basis for a *bordereau de pièces*, and the product says it does not claim to produce a court-ready one (FR-46).
- A missing translation fails the build and no natural-language string is used as a key, asserted statically (FR-34).
- The usability checklist has a recorded, dated verdict per surface, and every *worklist* action and table edit is keyboard-reachable (FR-59).

### Story 6.1: Export of the retained set

As a lawyer,
I want the *retained set* handed back as an ordered, numbered, attributed list,
So that I have the basis for a *bordereau de pièces* rather than a working set trapped inside the tool.

**Acceptance Criteria:**

**Given** a ranked *matter*,
**When** the lawyer exports the *retained set*,
**Then** it comes out within her *RBAC scope* as an ordered numbered list, one row per *pièce*, carrying at minimum sequence number, *pièce* identity, title or filename, *pièce* date, *custodian*, label, rank, confidence, the one-line justification, whether validated and by whom, and any *pin* (FR-46).
**And** the order is the ranked set as adjusted by pins, and the export names the *ranking version*, the *case theory* version, the position of **the line** and the *RBAC scope* it was produced under.
**And** superseded *pièces* are marked as superseded and the current version named (FR-46, FR-4).
**And** the export states that it is the basis for a *bordereau de pièces* and that the product does **not** claim to produce a court-ready *bordereau* — an honest boundary, not a silent overclaim.

> **UX pass required before implementation.** No UX design contract exists yet. The export's face is read outside the system.

### Story 6.2: The client-pushed diagnostic export

As a firm running APX where APX can never see in,
I want to send APX a diagnostic that I initiate and can read in full first, carrying counts and never content,
So that support is possible without a channel by which APX could ever pull my data.

**Acceptance Criteria:**

**Given** a *tenant*,
**When** a diagnostic export is produced,
**Then** it is initiated by a user of the *tenant*, never by a remote request, with no inbound channel by which APX can trigger it — asserted by test (FR-32).
**And** it is produced by the *content-free projection* (FR-31), inspectable by the user in full readable form before it leaves — no opaque blob — and contains at minimum the *denominator*, *failure register* counts by error class, component and schema versions, and redacted diagnostics.
**And** *(failure path)* a seeded content token or secret placed in the source data does not appear in the export (FR-31, FR-51).

### Story 6.3: Namespaced translation keys, no silent fallback

As a firm in Luxembourg working across French and English,
I want every string keyed and every missing translation to fail the build,
So that the v1 failure — French source strings used as keys, silent fallback — cannot recur.

**Acceptance Criteria:**

**Given** the interface,
**When** it is built,
**Then** every user-visible string is referenced by a structured namespaced key, a natural-language string is never used as a key (asserted statically), and a missing translation fails the build rather than falling back silently at runtime (FR-34, FR-56).
**And** a test asserts key-set parity across all supported languages — no key present in one and absent in another.
**And** coverage is asserted across every route and surface, including *worklist* lines, *failure register* error classes, justifications, the *confidence bound* sentence and every export; a route with zero translated strings fails the build (FR-34).
*Note: i18n depth is flagged by the work breakdown as likely to be quietly dropped. The Luxembourg market makes it load-bearing, not optional.*

### Story 6.4: Locale-aware dates, numbers and sorting

As a lawyer,
I want dates, numbers and sorting to follow my locale while stored dates stay unambiguous,
So that a date is never misread and the *pièce*'s own date is never conflated with when it was ingested.

**Acceptance Criteria:**

**Given** the interface,
**When** it renders locale-sensitive values,
**Then** no date, number or currency format is hard-coded to a locale anywhere in the code (asserted statically), dates shown to a user use that user's locale, and dates stored and in exports use an unambiguous locale-independent representation (FR-35, FR-56).
**And** a *pièce*'s own date and its ingestion timestamp are rendered distinguishably and never conflated (FR-35, FR-8).
**And** sorting of user-visible lists respects the active locale's collation.

### Story 6.5: The language reaches the language model

As a lawyer working in French,
I want every model request to carry an explicit output language,
So that a justification or a sentence never comes back in the wrong language because the model guessed.

**Acceptance Criteria:**

**Given** a request to a language model,
**When** it is made,
**Then** it carries an explicit output language derived from the user's active locale or *tenant* configuration, and machine-generated user-facing text — justifications, the priced statement, the *confidence bound* sentence — is produced in that language, asserted by test with the locale switched (FR-36).
**And** where the source *pièce* language differs from the interface language, the output states the source language rather than silently translating without saying so.
**And** language selection is *configuration-as-data* per *tenant* and per user, never a build-time constant.

### Story 6.6: The usability gate

As the daily non-technical user whose adoption is voluntary,
I want every surface reviewed against a phrasing checklist with a recorded verdict, and everything reachable by keyboard,
So that the least-instrumented promise — ease of use — has at least a dated, arguable gate rather than nothing.

**Acceptance Criteria:**

**Given** a release candidate,
**When** the usability gate runs,
**Then** every user-facing surface — every *worklist* line type, every *failure register* error class, the completion summary, the priced statement, the *confidence bound* sentence, the *audit drawer*, the viewer's controls, the *matters* zone, the face of every export — is reviewed against the **versioned phrasing checklist** (no technical vocabulary, no component name, no error code as primary text, no job identifier, no untranslated string, an action and its object on every line), and **each item's verdict is recorded with its reviewer and date** (FR-59, SM-20).
**And** a failed item blocks the release candidate or is recorded as an accepted exception with a reason in the same register; an unrecorded verdict counts as a failure.
**And** every *worklist* action and every triage-table edit is reachable and completable by keyboard alone, asserted by test; no WCAG level is claimed.
**And** this gate is **asserted by review**, the third verb of FR-56, and is never counted as a passing test — its value is that the review happened, is dated and is arguable.
*Note: FR-59 cannot be closed by a test. It needs a real non-technical reader, and SM-10 has no date because no client engagement exists. Written honestly rather than dressed as automatable.*

> **UX pass required before implementation.** No UX design contract exists yet — and this gate is where its absence is most consequential.

**Epic 6 covers:** FR-32, FR-34, FR-35, FR-36, FR-46, FR-59.
