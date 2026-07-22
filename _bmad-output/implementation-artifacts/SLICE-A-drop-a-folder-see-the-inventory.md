# Slice A — Drop a folder, see the inventory

**Course correction, 2026-07-22 (user decision).** We stop building Epic 1's 12
foundation stories horizontally before anything is visible, and instead cut the
thinnest VERTICAL slice that reaches a capability a lawyer can see:

> Drop a folder → "97 pieces indexed · 3 unreadable (listed) · 2 excluded as noise."
> `submitted = in corpus + failures + exclusions`, with nothing lost silently.

This is the honest core of the triage product (the **inventory guarantee**), and
it *includes* a minimal real schema — so we skip nothing; we build the foundation
in service of something visible instead of in isolation. **No fixtures, no demo
override (FR-33): real Postgres, real extraction.**

The full 58-story backlog stands. This slice pulls MINIMAL versions of FR-1
(folder intake), FR-3 (extraction), FR-5 (failure register), FR-6 (inventory
denominator), FR-7 (completion summary), FR-8 (payload/piece storage). The heavy
guarantees — RBAC pre-filter (1.4/3.3), audit (5.x), version guard, container
expansion, idempotency — THICKEN this slice in their own stories afterward. Where
this slice does less than the FR, it says so; it never fakes the guarantee.

## Layers (each committed as built)

1. **Domain** (`apx/core/domain`) — pure, no DB: `Piece` identity `(content_hash, matter)`;
   the inventory invariant `submitted = corpus + failures + exclusions` (no unnamed remainder);
   error classes (a subset of FR-5's enumerated set).
2. **Store + migration** (`apx/adapters/store_postgres`) — minimal `piece` and `failure`
   tables (NOT NULL provenance; no cascade FK, AD-7); the first real Alembic migration.
   *(This is a minimal, honest down-payment on story 1.3's schema; the frozen-schema
   rigor — the one-writer check, the scope-write-time reconciliation — lands in 1.3.)*
3. **Ingestion** (`apx/core/app` + `apx/adapters/extraction`) — walk a folder; extract
   `.txt` + PDF (pypdf) to start; create pieces; record failures (`unreadable`,
   `unsupported-format`, `extracted-empty`); count filesystem-noise exclusions.
4. **API** (`apx/api`) — `POST /api/ingest` (folder, matter) → runs ingestion →
   returns the denominator + failures; `GET /api/matters/{id}/inventory`.
5. **Web** (`apx/web`) — one screen: the permanent denominator and the failure list,
   in a lawyer's language. (UX pass still owed; behavioural only.)
6. **Demo** — compose up Postgres, ingest a real folder, show the numbers.

## Non-negotiables carried from the plan

- Inventory invariant holds exactly (SM-3 shape): submitted = corpus + failures + exclusions, no remainder.
- Nothing hard-deleted; failures resolved by state, not removal (FR-5/FR-21) — minimal here.
- No fixture layer, no demo override (FR-33): data enters through the one ingestion path.
- Extraction that yields no text is a `extracted-empty` failure, NOT counted in corpus (FR-3).
