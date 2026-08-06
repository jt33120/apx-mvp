# Story 4.6: Per-pièce confidence and a justification derived from named evidence

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer reading a ranking,
I want each *pièce* to show why it is where it is, in one line, backed by extracts I can verify,
so that the tool's assessment is checkable rather than a fluent sentence I must trust.

## Acceptance Criteria

**AC-1 (FR-18, FR-41 — the justification is derived from a stated, named input set).**
**Given** a *pièce* in a ranking,
**When** its justification is shown,
**Then** it carries a **confidence value** (the derived one from Story 4.4 — never imputed) and a **one-line
justification** in the user's language, readable without opening the *pièce*, generated from a **stated input
set** — the *case theory* version **or** the named intrinsic signals — **and** the **specific *retained
extracts* the judgement used, each named by *chunk* identifier** and resolvable to a source position.
**And** the checkable part of a justification is its **named evidence** (the *retained extracts* / the named
intrinsic signals), never the free-text sentence alone — the sentence is a summary, the extracts are the
control (FR-41, R-11). A justification cannot exist without named evidence.

**AC-2 (FR-41, FR-11 — verified by exact containment at show time).**
**Given** a justification with named *retained extracts*,
**When** it is shown,
**Then** **every** extract passes **exact-containment verification** against its source *at the moment it is
shown* (re-resolved through the FR-11 primitive, scope-gated); a justification whose extracts do **not** all
resolve is shown as **unverified**, never as ordinary. An extract that no longer resolves is surfaced as such
(with its resolution cause), never displayed as though it did.

**AC-3 (FR-18 — expandable to the evidence, reversible, audited).**
**Given** a shown justification,
**When** the lawyer opens it,
**Then** it expands to the *retained extracts* behind it (each resolving to a *chunk* by identifier and to a
source position), **and** the lawyer can **reject the tool's assessment** for that *pièce* in **one action**,
recorded in the *audit record* and itself **reversible** (a rejection sets the assessment aside — it is never
a deletion, and a re-instatement is a recorded act).

**AC-4 (FR-41, FR-36 — the source language is stated where it differs).**
**Given** a justification whose source *pièce* is in a language other than the interface language,
**When** it is shown,
**Then** it states the source *pièce*'s language; where the source language equals the interface language,
no such note is made.

**AC-5 (structural — the honesties are enforced, not just implemented).**
**Given** the build,
**When** the structural-properties harness runs,
**Then** two new checks are live and fail on their failure-path fixtures: (a) a justification's checkable part
is its **named evidence**, never the sentence alone (one construction path, evidence-or-signals required);
(b) the justification **read seam containment-verifies every extract at show time** — a read that surfaces a
justification routes each extract through the FR-11 resolver, so an unresolved extract can only ever be
**unverified**, never ordinary.

## Tasks / Subtasks

- [x] **Task 1 — Domain: the named-evidence justification value object + show-time verification (AC-1, AC-2, AC-4)**
  - [x] New module `apx/core/domain/justification.py`.
  - [x] `JustificationBasis` — the **stated input set, named**: a tagged value over `basis_kind ∈ {"case-theory","intrinsic"}`. `case-theory` carries `case_theory_version_id: str`; `intrinsic` carries `intrinsic_signals: tuple[IntrinsicSignal, ...]` (reuse `IntrinsicSignal` from `apx/core/domain/cascade.py:56-67`). A `.named` property renders the basis as a stable non-content string. `__post_init__` enforces the tag (case-theory ⇒ a version id present, no signals; intrinsic ⇒ ≥1 signal, no version id).
  - [x] `EvidenceExtract(chunk_id: str, quoted_text: str)` — one **named retained extract**: the *chunk* identity plus the exact quoted passage the judgement used (what gets containment-checked at show time). Frozen.
  - [x] `Justification(piece_id, sentence, basis: JustificationBasis, evidence: tuple[EvidenceExtract, ...], source_language: str | None, confidence: float | None, confidence_signals: tuple[ConfidenceSignal, ...])`. **Invariant (`__post_init__`): the justification names checkable evidence** — `evidence` is non-empty **or** `basis` is intrinsic with ≥1 signal; a `Justification` whose only content is the `sentence` is rejected (ValueError). This is the structural spine of AC-1 / R-11.
  - [x] `build_justification(judgement: PieceJudgement, *, sentence, basis, evidence, source_language, confidence, confidence_signals) -> Justification | None` — assemble from a **stage-3 JUDGED** `PieceJudgement` (the pièces the LLM actually judged, whose `retained_extract_chunk_ids` name the extracts — `cascade.py:105,132-138`). Returns `None` when there is nothing to derive (not stage-3 judged, or no evidence) — a pièce with no derivable justification is shown as such, **never imputed** (mirror `derive_confidence` returning `None`, `piece_confidence.py:109-111`). Assert `{e.chunk_id for e in evidence} ⊆ set(judgement.retained_extract_chunk_ids)` so the persisted evidence is exactly the extracts the judgement used.
  - [x] Show-time verification types: `ExtractVerification(chunk_id, verified: bool, cause: str | None)`; `VerifiedJustification(justification, extracts: tuple[ExtractVerification, ...], rejected: bool)` with a computed `is_unverified` property = **there exist evidence extracts and at least one failed containment** (an intrinsic-only justification with zero extracts is not "unverified" — it has no extracts to fail; its checkable part is its named signals). `verify_justification(justification, resolve: Callable[[str, str], ResolvedPassage | FailedResolution]) -> VerifiedJustification` — for each `EvidenceExtract` call `resolve(chunk_id, quoted_text)`; a `FailedResolution` ⇒ `verified=False` with `cause=<failure cause>`; a `ResolvedPassage` ⇒ `verified=True`. Pure domain (the resolver is injected — the store supplies `resolve_chunk`).
  - [x] `source_language_note(justification, *, interface_language: str) -> str | None` — the source language string **only where it differs** from `interface_language`, else `None` (AC-4).
  - [x] Reuse, do NOT rebuild: `resolve_passage` / `FailedResolution` / `ResolvedPassage` (`apx/core/domain/chunking.py:141-201`) and the store's `resolve_chunk(chunk_id, tenant, scopes, *, expected_text=...)` (`store.py:1294-1324`). The containment primitive already exists and is the seam.

- [x] **Task 2 — Persistence: version-bound justification + its named extracts + a reversible rejection ledger (AC-1, AC-3)**
  - [x] Migration `apx/adapters/store_postgres/migrations/versions/0029_piece_justification.py`, `down_revision = "0028_pin_entry"`. **Built as TWO tables, not three** (deviation, deliberate): the named extracts are an **encrypted JSON blob** (`piece_justification.evidence_json`, a list of `[chunk_id, quoted_text]`) rather than a `justification_extract` child table. Rationale: every extract's `quoted_text` is client content and is read only as a whole with its justification (never queried by extract), so one encrypted column keeps the AD-31 rekey surface at one row per justification instead of N, and removes a child table whose only key would duplicate the parent's. No behaviour in the ACs depends on the extracts being separately addressable. No backfill (pre-feature rows do not exist). Reversible `downgrade` drops both.
  - [x] `PieceJustification` (table `piece_justification`) — **version-bound** (the justification is the output of one ranking version's judgement). Columns: `id` (String(64) PK = `sha256(ranking_version_id \x00 piece_id)`), `tenant`, `matter`, `ranking_version_id` (String(64), FK → `ranking_version.id`, **no ondelete**, like `LinePlacement.ranking_version_id`), `piece_id`, `sentence` (**EncryptedText** — model content), `basis_kind` (String, categorical), `case_theory_version_id` (String(64), nullable — a hash), `intrinsic_signals` (String, comma-joined categorical, `""` when case-theory basis), `source_language` (String, nullable, a language tag), `at` (DateTime). `UniqueConstraint(tenant, matter, ranking_version_id, piece_id)` — one justification per pièce per version.
  - [x] ~~`JustificationExtract` (a child table)~~ → **built as `piece_justification.evidence_json`** (**EncryptedText**), a JSON list of `[chunk_id, quoted_text]` preserving order. The chunk ids stay the named evidence identity; the quotes are the containment targets at show time. See the deviation note above.
  - [x] `JustificationRejection` (table `justification_rejection`) — **version-INDEPENDENT** per-pièce append-only ledger (rejecting the tool's assessment is a human act on the *pièce*, surviving re-ranking; mirror `PinEntry`, `models.py:733-773`). Columns: `id` (PK = `sha256(tenant \x00 matter \x00 piece_id \x00 seq)`), `tenant`, `matter`, `piece_id`, `seq` (int, per-pièce monotonic), `action` (String, `"rejected" | "restored"`), `reason` (**EncryptedText**, nullable — an optional note; FR-18 does **not** mandate a reason for a rejection, unlike the FR-25 override), `set_by` (**EncryptedText**), `at` (DateTime). `UniqueConstraint(tenant, matter, piece_id, seq)`.
  - [x] **Lockstep — encryption + backfill (the 4.5 regression class):**
    - `apx/adapters/store_postgres/backfill.py` `ENCRYPTED_COLUMNS` += `("piece_justification","id","sentence",…)`, `("piece_justification","id","evidence_json",…)`, `("justification_rejection","id","reason",…)`, `("justification_rejection","id","set_by",…)`. Every `EncryptedText` column MUST appear or `test_rekey_covers_every_encrypted_column` fails (it passes).
    - `apx/checks/encryption.py` allowlist the **plaintext categorical / hash** columns: `("PieceJustification","basis_kind")`, `("PieceJustification","case_theory_version_id")`, `("PieceJustification","intrinsic_signals")`, `("PieceJustification","source_language")`, `("JustificationRejection","action")` in `_PLAINTEXT_ALLOWLIST_QUALIFIED` (`encryption.py:69-106`). `ranking_version_id`, `piece_id`, `chunk_id`, `justification_id` are sha-256 hashes (non-content) — allowlist them if the check flags them (mirror `("RankedEntry","confidence_signals")` precedent).
  - [x] **Lockstep — backup coverage:** both tables added to `store.py::_BACKUP_TABLES` (the literal DOES exist, at `store.py:132`, and `tests/adapters/test_backup_restore.py` iterates it).

- [x] **Task 3 — Store methods (AC-1, AC-2, AC-3)**
  - [x] `record_justification(*, tenant, matter, actor, piece_id, version_no=None, sentence, basis, evidence, source_language) -> None` — resolve the ranking version (latest or `version_no`), write one `PieceJustification` (evidence as the encrypted JSON blob) atomically, audited (`justification_recorded`). **Write-once** per (version, piece): a duplicate is a **loud refusal** (`ValueError`). Scope-gated + `ScopeDenied`.
  - [x] `read_justification(*, tenant, matter, scopes, piece_id, version_no=None) -> VerifiedJustification | None` — scope pre-filter (non-disclosing `None` when out of scope or absent, `store.py:1554-1582` shape). Load the `PieceJustification` + decode its evidence blob; rebuild the domain `Justification`; **verify at show time** by calling `verify_justification(justification, resolve=lambda cid, q: self.resolve_chunk(cid, tenant, scopes, expected_text=q))`; fold in the current rejection state (max-`seq` of `JustificationRejection` — `rejected` iff the last action is `"rejected"`). Return the `VerifiedJustification`. **The read MUST route every extract through `resolve_chunk` — never return raw evidence unverified** (this is what structural check (b) enforces).
  - [x] `reject_justification(*, tenant, matter, actor, piece_id, reason=None, expected_seq=None) -> None` and `restore_justification(*, tenant, matter, actor, piece_id, reason=None, expected_seq=None) -> None` — append a `JustificationRejection` entry (`_append_justification_rejection` helper, mirror `_append_pin_entry`, `store.py:3490+`), audited `justification_rejected` / `justification_restored`, serialised via `expected_seq` → `StaleJustification`. `restore` requires a currently-rejected pièce (else a loud `ValueError`, mirror `remove_pin`); `reject` requires a currently-non-rejected pièce. Both INSERT-only (append-only; a restore does not delete the rejection row).
  - [x] `StaleJustification` exception (mirror `StalePin`, `store.py:180-183`). `PieceJustificationView` / reuse `VerifiedJustification` as the returned DTO.
  - [x] `resolve_chunk` already scope-checks and re-verifies containment (`store.py:1294-1324`) — call it unchanged.

- [x] **Task 4 — Port + use-case seam (AD-4)**
  - [x] `apx/core/ports/justification.py` — a `Protocol` (`JustificationStore`) with `record_justification`, `read_justification`, `reject_justification`, `restore_justification` (mirror `ports/pin.py`).
  - [x] `apx/core/app/justification.py` — orchestrator functions importing Domain + Ports only, touching no store (mirror `app/pin.py`). No adapter import (import-linter AD-4 / AD-27 / AD-45 must stay 3/0).

- [x] **Task 5 — Two structural checks + full lockstep (AC-5)**
  - [x] `apx/checks/justification_names_its_evidence.py` — `justification_names_its_evidence` (FR-41, AD-33): the `Justification` value object cannot be constructed without named evidence (evidence extracts OR intrinsic signals); the free-text sentence is never the checkable part. Model on `apx/checks/confidence_derivation.py:confidence_has_one_derivation` (one construction site + the invariant proven). Include a **failure-path fixture** that constructs a sentence-only justification and asserts it is refused.
  - [x] `apx/checks/justification_verified_at_show_time.py` — `justification_verified_at_show_time` (FR-11, AD-33): the justification **read seam** routes every extract through the containment resolver (`resolve_chunk` / `resolve_passage`), so an unresolved extract can only surface as **unverified**. AST/behavioural check that `read_justification` references the resolver AND that `VerifiedJustification.is_unverified` fires when any extract fails (a failure-path fixture with a non-containing extract).
  - [x] **Lockstep — the 3 canonical sites (a drift fails the build):**
    - `apx/checks/registry.py` — `import` both modules (near `pin_not_a_ranking_input`, line ~37) **and** append both callables to the `CHECKS` list (near line ~156-157).
    - `apx/checks/manifest.py` — `import` both modules (line ~53) **and** add two `_p(key, fr, ad, name, check_callable, inspects)` rows to `PROPERTY_MANIFEST` (meta-checks match by **check callable identity + FR/AD**, not the prose).
    - `README.md` — add two rows to the `<!-- structural-properties -->` block (`388`-`470`); keep it byte-consistent with the manifest or `meta-manifest-matches-readme` / `meta-readme-lists-every` fail.
  - [x] Check count grows **71 → 73** (confirm the exact base at gate time; the harness is the authority).

- [x] **Task 6 — Tests (all ACs) — red first, then green**
  - [x] `tests/domain/test_justification.py` — the invariant (sentence-only refused; evidence-or-signals required); `build_justification` (stage-3 judged ⇒ Justification; non-judged / no-evidence ⇒ `None`; evidence ⊆ judgement's chunk ids); `verify_justification` (all-contain ⇒ verified, `is_unverified` False; one non-contain ⇒ that extract `verified=False`, `is_unverified` True; intrinsic-only zero-extracts ⇒ not unverified); `source_language_note` (differs ⇒ stated; equal ⇒ `None`).
  - [x] `tests/adapters/test_justification_store.py` (SQLite, mirror `test_pin_store.py`) — record → read returns the justification with confidence + named extracts; **show-time verification** (mutate the pièce's `full_text` so a stored extract no longer contains ⇒ that extract `verified=False`, `is_unverified` True, justification shown **unverified** not ordinary); reject → read shows `rejected=True`, both rows remain, `justification_rejected` audited; restore → `rejected=False`, audited, append-only (rows accumulate); `StaleJustification` on a stale `expected_seq`; reads are scope-gated + non-disclosing (`None` / `ScopeDenied`); rejection survives re-ranking (version-independent).
  - [x] `tests/adapters/test_justification_migration.py` — 0029 upgrades/creates the three tables and downgrades cleanly (mirror `test_pin_entry_migration.py`).
  - [x] `tests/app/test_justification_use_case.py` — the port/use-case seam (mirror `test_pin_use_case.py`).
  - [x] `tests/checks/test_justification_names_its_evidence.py` + `tests/checks/test_justification_verified_at_show_time.py` — each check passes on the real tree AND fires on its failure-path fixture.
  - [x] `test_rekey_covers_every_encrypted_column` and the encryption/backup meta-tests stay green (the lockstep in Task 2).

## Dev Notes

### What is ALREADY built — reuse, do not rebuild

- **Confidence (Story 4.4, FR-42)** — `apx/core/domain/piece_confidence.py`. `CONFIDENCE_METHOD = "margin-agreement-v1"` recorded in the ranking identity (`ranking.py:213`); `ConfidenceSignal` enum (`piece_confidence.py:53-64`); `derive_confidence(judgement, config) -> Confidence | None` (`None` = not derived, never imputed, `:109-111,132-133`). The per-pièce **confidence value + signals are already persisted** on `RankedEntry.confidence` / `confidence_signals` and hydrated into `RankedEntryView` (`store.py:459-476, 3031-3037`). **Story 4.6 does not recompute confidence** — it carries the already-derived value alongside the justification (AC-1).
- **Named evidence linkage (Story 4.2)** — `PieceJudgement.retained_extract_chunk_ids` (`cascade.py:105,132-138`) is populated at stage 3 only, from `CascadeUnit.chunk_ids` (`cascade.py:78-86`), in the orchestrator (`app/cascade.py:147-150`). This is the pièce's retained-extract chunk ids. **It is computed but currently discarded before persistence** — `_to_row` (`ranking.py:313-320`) and `RankedEntry` (`models.py:602-643`) drop it. Story 4.6 is the story that persists the named evidence (in `piece_justification` / `justification_extract`), so it does **not** need to widen `RankedEntry`.
- **The one-line sentence** — the judge `Verdict` (`apx/core/domain/triage.py:24-33`) carries `label` + a **never-empty `rationale`**. The cascade currently reads only `verdict.label` and **discards `verdict.rationale`** (`app/cascade.py:124-127,147-150`). The rationale is the natural one-line justification sentence. **No new LLM call is introduced by this story** — the sentence is the judge's already-produced rationale, passed into `record_justification` by the caller. (Production wiring of the full ranking→justification pipeline is deferred with the rest of the unwired ranking act — `produce_ranking` has no production caller yet, a documented deferral; Story 4.6 delivers the seam + verification + reversal and proves them by test.)
- **Exact containment at show time (FR-11)** — **fully built.** Domain `resolve_passage(*, ..., expected_text=None) -> ResolvedPassage | FailedResolution` (`chunking.py:167-195`); the containment guard is `if expected_text is not None and expected_text not in passage.text: return FailedResolution(CONTAINMENT_FAILED)` (`:193-194`). Closed failure set `PIECE_GONE / TEXT_CHANGED / CONFIG_SUPERSEDED / POSITION_OUT_OF_RANGE / CONTAINMENT_FAILED` (`:141-145`); `is_degraded(...)` (`:198-201`). Scope-gated store wrapper `resolve_chunk(chunk_id, tenant, scopes, *, expected_text=None)` (`store.py:1294-1324`) — re-chunks the pièce's `Piece.full_text` and verifies containment, non-disclosing `ScopeDenied` on scope. **Story 4.6 calls this at show time with `expected_text=<stored quoted extract>`; any `FailedResolution` ⇒ that extract is unverified ⇒ the justification is unverified, never ordinary.** Verification is against `Piece.full_text` (AD-10/AD-31 named plaintext exception, `models.py:80-92`) — there is no per-chunk stored text.
- **Chunk identity (FR-11, AD-40)** — `Chunk` model `models.py:147-195`; deterministic `chunk_id = sha256(piece_id \x00 full_text_version \x00 position \x00 chunking_config_version)` (`identity.py:36-60`). A chunk stores only `position` + versions; passage span + text are recovered at read time (never stored).
- **Ranking version identity (Story 4.3)** — `RankingIdentity` (frozen, `ranking.py:91-169`) records `case_theory_version_id`, `confidence_method`, model + embedder + chunking-config identity; `.fingerprint` = sha256 of canonical JSON. `RankingVersion` names the version (`version_no` per-matter monotonic + `version_id`, `ranking.py:216-239`). The justification's **basis** draws `case_theory_version_id` from here (case-theory path) or the `CascadeResult.intrinsic_signals` (`cascade.py:168`) (intrinsic path).

### The seam patterns to mirror exactly (do not invent)

- **Append-only ledger** (`_append_*_entry` + per-key monotonic `seq` + typed `StaleX` on `expected_seq` + INSERT-only + atomic `_append_audit`): `_append_pin_entry` (`store.py:3490+`), `_append_label_entry` (`store.py:3048+`). Current-state = **max-`seq` view** (`read_current_line` `store.py:3355-3383`; the pin/label current views). The `JustificationRejection` ledger mirrors `PinEntry` (`models.py:733-773`) exactly.
- **Version-bound writer inside `_audited_tx`** (mint id from the version, INSERT children, one audit entry atomic): `record_ranking` (`store.py:2882-2948`), `place_line` (`store.py`), and the head-journal chaining `_capture_heads`/`_write_heads` (`store.py:764-792`). `record_justification` mirrors this.
- **Scope pre-filter, non-disclosing** — `read_piece` store impl (`store.py:1554-1582`): `if not scopes: return None`; scope joined into the WHERE (never a post-filter); out-of-scope is indistinguishable from absent (`None`). `read_justification` mirrors this; write paths raise `ScopeDenied` (`store.py:139`).
- **EncryptedText + AAD** — `crypto_types.EncryptedText` with per-column context `"table.column"` (`crypto_types.py:37-66`); every such column listed in `backfill.ENCRYPTED_COLUMNS` (`:30-66`, asserted by `test_rekey_covers_every_encrypted_column`); precedents `piece_label.rationale` (`backfill.py:42`), `pin_entry.reason` / `pin_entry.set_by`.
- **Migration shape** — mirror `0028_pin_entry.py` (new tables, `UniqueConstraint`, reversible `downgrade`); `down_revision = "0028_pin_entry"`; new revision id `0029_piece_justification`.
- **Structural-check lockstep — 3 sites** — `apx/checks/registry.py` (import + `CHECKS` list), `apx/checks/manifest.py` (import + `PROPERTY_MANIFEST` `_p(...)` row; meta-checks match by **check callable identity + FR/AD**), `README.md` `<!-- structural-properties -->` block. Two new checks → **71 → 73** (confirm at gate). Check module shape: `apx/checks/pin_ledger_ownership.py`, `apx/checks/confidence_derivation.py`.

### Structural honesties this story must make true (the point of the story)

1. **The extracts are the control, not the sentence (FR-41, R-11).** A `Justification` cannot exist without named evidence. The interface (frontend, out of scope here) states once that the sentence is a model summary and the extracts are what to check; the **backend guarantees the extracts are named, resolvable and containment-verified**. Enforced by check (a).
2. **Unverified is a first-class state, never a silent pass (FR-11, FR-41).** A justification whose extract no longer exact-contains at show time is **unverified**, surfaced with its cause — never rendered as ordinary. Enforced by check (b) + `VerifiedJustification.is_unverified` + the store read routing through `resolve_chunk`.
3. **A rejection sets aside, never deletes (FR-18, non-negotiable "never destroy").** Rejecting the tool's assessment is an append-only, reversible, audited act (a restore re-instates). Nothing is hard-deleted (the future 4.12 probe will exercise this).
4. **No imputation (AD-19).** A pièce with no derivable justification returns `None`, never a fabricated sentence or a default confidence — mirroring `derive_confidence`.

### Scope boundaries — what this story is NOT

- **No new LLM call / no generation engine.** The sentence is the judge's existing `rationale`. Generating-near-the-line + on-demand backfill (FR-18) is a *caller* concern; the seam `record_justification` is the generation write-point, exercised by test, wired to a real ranking run later with the rest of the unwired pipeline.
- **No frontend.** The triage table, the audit-drawer expansion, the "extracts are the control" copy, and the reject button are the React surface (EXPERIENCE-EPIC4 contract) — a later frontend story. This story delivers the backend the surface reads.
- **No change to `RankedEntry` / the ranked order.** The justification is a separate version-bound artefact; it never affects rank, band, or the confidence already stored (AD-23 / FR-42 unchanged).
- **No language detection.** `source_language` is a **stated** attribute passed to `record_justification` (there is no language column on `Piece`); AC-4 is "state it where it differs", not "detect it".
- **Not the audit-drawer export** (FR-26) — Epic 5. This story records the reject/restore acts in the *audit record* (already built) and returns the extracts for expansion; the drawer UI + export are later.

### Project Structure Notes

- New files: `apx/core/domain/justification.py`; `apx/core/ports/justification.py`; `apx/core/app/justification.py`; `apx/checks/justification_names_its_evidence.py`; `apx/checks/justification_verified_at_show_time.py`; `apx/adapters/store_postgres/migrations/versions/0029_piece_justification.py`; tests as listed.
- Updated files: `apx/adapters/store_postgres/models.py` (3 tables); `apx/adapters/store_postgres/store.py` (methods + `StaleJustification` + DTO + `_append_justification_rejection`); `apx/adapters/store_postgres/backfill.py` (ENCRYPTED_COLUMNS); `apx/checks/encryption.py` (allowlist); `apx/checks/registry.py`; `apx/checks/manifest.py`; `README.md`; the backup-coverage site.
- Hexagonal boundaries hold: domain imports nothing from adapters; the app seam imports domain + ports only; import-linter AD-4 / AD-27 / AD-45 must stay **3 kept / 0 broken**.

### Testing standards

- uv-managed backend; run from `apx-mvp` with `export PATH="$PWD/.venv/bin:$PATH"` **in the same shell call** as pytest/ruff (shell state does not persist between calls). **Never** `export DATABASE_URL`. ruff line-length 100 — accented chars (`pièce`, `é`, `→`, `§`) push lines over; reflow by hand. Import sort: `ruff check --fix --select I001`.
- Store tests run on **SQLite** (`create_engine("sqlite://", StaticPool)`), mirror `tests/adapters/test_pin_store.py`. An UNSCORED-pièce edge (justification `None` when not stage-3 judged) mirrors the 4.11 dormant-pin regression: exercise a pièce that never reached the LLM.
- Every structural check ships with a **failure-path fixture that actually fires** (a check that cannot fail is not live) — mandated by the PRD verb discipline (`prd.md:1048`).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-4.6] — AC text (lines 1168-1183).
- [Source: _bmad-output/planning-artifacts/prds/prd-apx-mvp-2026-07-20/prd.md#FR-41] (838-847), #FR-11 (407-416), #FR-18 (510-519), #FR-42 (849-858), #FR-36 (771-775), #R-11 (1496), #A-10/A-33 (1599,1622).
- [Source: apx/core/domain/piece_confidence.py] — confidence derivation (Story 4.4).
- [Source: apx/core/domain/cascade.py:56-150] — `IntrinsicSignal`, `PieceJudgement.retained_extract_chunk_ids`, stage-3.
- [Source: apx/core/domain/triage.py:24-33] — `Verdict.rationale` (the sentence).
- [Source: apx/core/domain/chunking.py:141-201] — `resolve_passage` / `FailedResolution` / `is_degraded` (FR-11 containment).
- [Source: apx/adapters/store_postgres/store.py:1294-1324] — `resolve_chunk` (scope-gated show-time verifier).
- [Source: apx/adapters/store_postgres/models.py:733-773] — `PinEntry` (ledger shape to mirror); :602-643 `RankedEntry`; :147-195 `Chunk`.
- [Source: apx/adapters/store_postgres/backfill.py:30-66] — `ENCRYPTED_COLUMNS`; apx/checks/encryption.py:69-106 — allowlist.
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC4.md] — the justification surface (show-time verification, "extracts are the control").

## Dev Agent Record

### Agent Model Used

claude-opus-4-8 (1M context)

### Debug Log References

- Baseline commit: `11d5466` (Story 4.11).
- Gate at completion: ruff clean · **72 structural checks** (70 → 72) · import-linter **3 kept / 0 broken** · **1301 passed / 12 skipped** (1258 → 1301, +43 new, incl. 8 post-review regression tests).
- ~48 `E501` reflowed by hand (accented characters push docstring lines over ruff's 100-char limit); 3 `F401` auto-fixed with `ruff check --fix`.

### Completion Notes List

**What was built.** The per-*pièce* justification as a **named-evidence artefact**, not a sentence:

1. **Domain (`core/domain/justification.py`)** — `JustificationBasis` (the *stated input set*, tagged: `case-theory:<version>` or `intrinsic:<named signals>`), `EvidenceExtract(chunk_id, quoted_text)`, and `Justification` whose `__post_init__` **refuses a justification with no named evidence** (extracts, or intrinsic signals) — the R-11 mitigation made structural. `build_justification` assembles only from a **stage-3 JUDGED** `PieceJudgement` and refuses evidence outside that judgement's `retained_extract_chunk_ids`; it returns `None` (never an imputed sentence) when nothing is derivable (AD-19, mirroring `derive_confidence`). `verify_justification(justification, resolve)` is the **pure** show-time check — the containment resolver is injected. `rebuild_justification` is the single read-path reconstruction, re-running the invariant.

2. **Persistence (migration `0029`)** — `piece_justification`, **version-bound** (one per *ranking version* per *pièce*, write-once, `sentence` + `evidence_json` encrypted); `justification_rejection`, an **append-only, version-INDEPENDENT** per-*pièce* ledger (`rejected`/`restored`, per-*pièce* monotonic `seq`, `StaleJustification` on a stale `expected_seq`) so a rejection survives re-ranking and a restore reverses it **without a delete** (AD-7).

3. **Store seam** — `record_justification` (write-once, audited `justification_recorded`, atomic), `read_justification` (**the show-time verifier**: rebuilds the domain object, routes **every** extract through the scope-gated `resolve_chunk(..., expected_text=…)`, folds in the current rejection state, carries the **already-derived** confidence from `RankedEntry`), `reject_justification` / `restore_justification` / `read_justification_rejection_log`.

4. **Two structural checks (70 → 72)** — `justification-names-evidence` (FR-41/AD-19: `Justification` is constructed only in its owning module, so the named-evidence invariant cannot be bypassed) and `justification-verified-show-time` (FR-11/AD-10: the read seam routes evidence through `resolve_chunk` + `verify_justification`, so an unresolved extract can only surface as **unverified**). Both ship failure-path fixtures that actually fire.

**Reused, not rebuilt.** The FR-11 containment primitive (`resolve_passage` / `resolve_chunk`) and the Story-4.4 confidence derivation are consumed unchanged — this story is their first real consumer, as FR-11 anticipated.

**Deferred, stated plainly.** No new LLM call (the sentence is the judge's existing `rationale`, passed in by the caller); no frontend (the triage-table / audit-drawer surface is a later story); no change to `RankedEntry` or the ranked order; no language *detection* (`source_language` is stated, per AC-4). Wiring the ranking pipeline to a production caller remains the pre-existing deferral it was before this story.

### File List

**New:**
- `apx/core/domain/justification.py`
- `apx/core/ports/justification.py`
- `apx/core/app/justification.py`
- `apx/checks/justification_names_its_evidence.py`
- `apx/checks/justification_verified_at_show_time.py`
- `apx/adapters/store_postgres/migrations/versions/0029_piece_justification.py`
- `tests/domain/test_justification.py`
- `tests/adapters/test_justification_store.py`
- `tests/adapters/test_justification_migration.py`
- `tests/app/test_justification_use_case.py`
- `tests/checks/test_justification_names_its_evidence.py`
- `tests/checks/test_justification_verified_at_show_time.py`

**Updated:**
- `apx/adapters/store_postgres/models.py` (`PieceJustification`, `JustificationRejection`)
- `apx/adapters/store_postgres/store.py` (methods, `StaleJustification`, `JustificationRejectionEntry`, `_BACKUP_TABLES`)
- `apx/adapters/store_postgres/backfill.py` (`ENCRYPTED_COLUMNS` ×4)
- `apx/checks/encryption.py` (plaintext allowlist ×3)
- `apx/checks/registry.py` · `apx/checks/manifest.py` · `README.md` (the 3-site check lockstep)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Senior Developer Review (AI)

**Date:** 2026-08-06 · **Method:** adversarial 3-lens workflow review (correctness · security/isolation · architecture/scope), every finding independently skeptic-verified with a default of REFUTED (a claim that cannot be demonstrated is refuted). 20 agents.

**Outcome: 17 findings raised → 2 CONFIRMED → both fixed. 15 refuted.**

### CONFIRMED (both lenses found the SAME defect independently — correctness + architecture/scope)

**The named-evidence invariant ran only on READ, so the write seam could persist an unreadable, unrepairable justification.** `record_justification` serialised its arguments straight into a row and never constructed or validated a domain `Justification`; `read_justification` rebuilds one, re-running `__post_init__`. So an argument shape the domain refuses — a case-theory basis with `evidence=()`, or a blank sentence — was **accepted, committed, and audited** on write, then raised `ValueError` on **every** subsequent read. Because recording is write-once and **AD-7 forbids a delete**, that *(ranking version, pièce)* justification would be **unreadable forever** (only DB surgery could clear it), and the version-pinned read (AD-23) stayed poisoned even after a re-rank. AC-1's central claim — *"a justification cannot exist without named evidence"* — was **false in the database**, and AD-10 was violated: the container did not degrade, it threw. Reproduced by the skeptic against the real `SqlStore` **and** through the AD-4 app seam, so it was not "caller misuse another layer prevents" — nothing prevented it.

**Fix (the invariant becomes domain-owned and runs at BOTH seams, mirroring `pin.validate_pin_reason`):**
1. `core/domain/justification.py` — the rule is factored into `validate_named_evidence(sentence, basis, evidence)`; `Justification.__post_init__` delegates to it, so there is **one** source of truth. It additionally refuses an **empty quote** on a named extract (`"" in text` is vacuously true, so an empty quote would pass containment forever — a nearby hole closed while the invariant was open).
2. `store.py::record_justification` — calls `validate_named_evidence` as its **first statement**, before the serialisation and before the transaction: a refusal leaves **no row and no audit entry**.
3. `checks/justification_names_its_evidence.py` — grew a **second leg**: the check now also asserts that `record_justification` calls the validator, so the regression cannot silently return. (The blind spot was structural: a check that only forbids constructing `Justification` elsewhere cannot catch a path that never constructs one at all.)
4. Tests — 8 new: the write-path refusal for each shape (no evidence / blank sentence / empty quote), each asserting **0 rows and 0 audit entries**; the domain validator directly; and the check's new leg passing/firing/missing-seam fixtures.

**Verified after the fix** (the reviewer's own scenario, through the app seam): `REFUSED · rows persisted=0 · audit entries=0 · read → None`.

### Refuted — the notable ones, and why

- **"The show-time check is a name-mention AST check that cannot fail."** Mechanically true of that check *alone*, but the behavioural leg exists and is ungameable: the skeptic patched `read_justification` to discard the verdict (keeping the AST check green) and the store tests failed. Two-legged enforcement, the same shape as `encryption.py`'s startup gate.
- **"Persisted evidence is never checked against the judgement's retained extracts."** Real mechanically, but `retained_extract_chunk_ids` is **never persisted**, so the store has nothing to compare against; the check can only happen where the `PieceJudgement` is live — which is `build_justification`, where it does happen. The bound is honest, not a hole.
- **"A cross-matter extract could be shown as verified."** Refused by `build_justification` on the supported path; and the scope-dependent verdict is AD-13 working (out-of-scope is indistinguishable from absent), not failing.
- **"The read surface names no ranking version (AD-23)."** Premise wrong: the sibling per-*pièce* row DTOs (`RankedEntryView`, `LabelCoverage`) carry no version either; AD-23 binds the set/aggregate artefacts. Not a deviation introduced here.
- **"`interface_language` is accepted and ignored."** Accurate observation; AC-4 is delivered by the tested pure domain function `source_language_note` over the `source_language` the read carries — no consumer is misled, nothing imputed.

### Integrity

**Integrity manifest clean** — of the 19 code/doc files snapshotted before the review, **all 19 were byte-identical afterwards**: the review agents mutated nothing (they probed in `/tmp`). **Secret scan clean**; the LLM key stays env-only.

**Gate after the fix:** ruff clean · **72 structural checks** · import-linter **3 kept / 0 broken** · **1301 passed / 12 skipped**.
