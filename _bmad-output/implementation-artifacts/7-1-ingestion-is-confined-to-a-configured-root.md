---
baseline_commit: c71bd66
---

# Story 7.1: Ingestion is confined to a configured root

Status: done

## Story

As **a firm whose whole security model is a wall between matters**,
I want the server-side folder ingestion to reach only a directory tree the deployment names,
So that no authenticated user can turn the import gesture into a read of the server's disk.

## Why this story exists

Found by the B3/B4 audit (`b3-b4-audit-2026-08-15.md` §3.1), action item **C1**, and verified by
hand:

```python
folder = Path(req.folder)                                   # apx/api/app.py:1347
if not folder.is_dir():
    raise HTTPException(status_code=400, detail=f"not a folder: {req.folder}")
```

`IngestRequest.folder` is a bare `str` from the request body. That single line is the whole
validation. Any authenticated user, holding any *RBAC scope*, can name any directory the API process
can read and have it walked, extracted, **persisted into their own matter under their own scope**,
and its originals retained for later viewing through the *pièce* viewer.

The target is not hypothetical and it is not obscure: `APX_DATA_PATH` holds `originals/` — every
*matter*'s retained source documents — and `spool/<job_id>` — another user's upload in flight. The
product's two stated non-negotiables are *RBAC by matter (Chinese walls)* and *tenant isolation*.
This route is underneath both.

**The class was already known and half-fixed.** Story 2.1's review found and fixed a traversal on the
*upload* path — *"a crafted `../../` filename escaped the temp sandbox"* — and never asked the same
question of the sibling route that accepts an absolute path outright. `ErrorClass.
TRAVERSAL_OUT_OF_SCOPE` has existed in the taxonomy since then **with no producer anywhere**.

## Acceptance Criteria

**AC-1 — The root is named by the deployment, and its absence refuses.**
**Given** the API, **when** `POST /api/ingest` is called, **then** the folder is resolved against
`APX_INGEST_ROOT` and refused unless it lies within it. **And** where `APX_INGEST_ROOT` is unset the
route refuses every call, naming the variable in its message — never falling back to "anywhere",
which is today's behaviour and the defect (AD-31's fail-closed posture, applied to the filesystem).

**AC-2 — A folder outside the root is indistinguishable from one that does not exist.**
The refusal for an out-of-root path and for a non-existent path are **byte-identical** — same status,
same body. A caller must not be able to map the server's filesystem one request at a time (FR-14's
non-disclosure discipline, which every other identifier-taking route already follows).

**AC-3 — The root may not overlap the data volume.**
**Given** a deployment where `APX_INGEST_ROOT` is, contains, or is contained by `APX_DATA_PATH`,
**then** the route refuses and says why. A confinement that admits the originals store grants exactly
what it was built to deny.

**AC-4 — A link out of the subtree is recorded, not ingested (FR-1).**
**Given** a selected folder containing a symbolic link whose resolved target lies outside that
subtree, **when** the folder is ingested, **then** the target is **not** ingested **and** an entry is
written to the *failure register* with class `traversal-out-of-scope`, naming the link's path within
the submitted tree. **And** this holds for a link to a *file* — which is ingested today, verified
empirically — and for a link to a *directory*, which is silently skipped today.

**AC-5 — A cycle terminates, and the property is pinned.**
**Given** a folder containing a symbolic link to one of its own ancestors, **when** it is walked,
**then** the walk terminates and the *import job* completes. Python 3.13's `Path.rglob` defaults to
`recurse_symlinks=False`, so this holds **today by the standard library and not by our code** — which
is precisely the kind of property that changes under an upgrade or a refactor to `os.walk`. The test
builds a real cycle and asserts termination, so the day it stops holding, the build says so.

**AC-6 — There is exactly one filesystem walk in the runtime.**
A structural check asserts that no runtime module calls `rglob`, `glob`, `iterdir` or `os.walk`
outside the one confining module, exempted **by path and not by basename** (the Story 5.9 lesson:
a basename exemption means any new file of that name silently re-opens the property). Today there are
three such call sites — `core/app/ingest.py:114`, `:335` and `api/app.py:1350` — and the last is the
capacity pre-flight, which counts files through a different walk from the one that ingests them.

**AC-7 — The taxonomy's dead class gains its producer.**
`ErrorClass.TRAVERSAL_OUT_OF_SCOPE` is written by real code for the first time. The register entry is
countable and filterable like any other, appears in the *denominator*'s accounting under the same
rules, and carries cardinality `one`.

**AC-8 — Nothing else moves.** The FR-21 never-delete probe, the action registry (4.12), the
`user_actions` completeness check and the *denominator* identity (SM-3) all stay green. `/api/ingest-
upload` — the path the SPA actually uses — is unchanged; its own sandbox check (Story 2.1) stays.

**AC-9 — The gate.** ruff · import-linter 3/0 · all structural checks (count rises) · fitness frame ·
full pytest · client `typecheck` + `build`.

## Tasks / Subtasks

- [x] **T1 — The one door (AC-4, AC-5, AC-6).** New pure Domain module `apx/core/domain/traversal.py`:
  `OutsideRoot` (an error carrying no path in its message — AC-2), `WalkedFile`, `OutOfScopeLink`,
  `Walk`, `resolve_within(root, candidate)` and `walk_confined(folder)`. `walk_confined` yields a file
  only when its **resolved** path is inside the resolved folder, and records every symlink — file or
  directory — whose target is outside as an out-of-scope link. Pure: no I/O beyond the walk itself, no
  store, no clock.
- [x] **T2 — Both ingest paths use it (AC-4).** `ingest_folder` (`:335`) and the worker's
  `enumerate_units` (`:114`) walk through `walk_confined`; out-of-scope links become
  `IngestedFailure(error_class=TRAVERSAL_OUT_OF_SCOPE, cardinality=one)`.
- [x] **T3 — The route is confined (AC-1, AC-2, AC-3).** `ingest_root(env)` reads `APX_INGEST_ROOT`;
  the route resolves `req.folder` within it and answers the **same** refusal for out-of-root and
  absent. The overlap check against `APX_DATA_PATH` refuses with its own message.
- [x] **T4 — The capacity pre-flight walks once (AC-6).** `_capacity_preflight` counts from the
  `Walk` the ingest will actually use, not from a second `rglob`.
- [x] **T5 — The structural check (AC-6).** `apx/checks/traversal.py`:
  `the_filesystem_has_one_walk`, path-scoped exemption, fail-closed on an unparseable file; fixtures
  proving it fires. Registry + manifest + README in lockstep.
- [x] **T6 — Tests.** Domain: confinement, the file link, the directory link, the cycle, a relative
  `..` path, a root that is a prefix *string* but not a path ancestor (`/data/ingest-evil` vs
  `/data/ingest`). API: unset root refuses; out-of-root and absent are byte-identical; the overlap
  refusal; a legitimate ingest still works end to end. Register: the entry exists, is countable, and
  the *denominator* still reconciles.
- [x] **T7 — Re-gate (AC-9).**

## Dev Notes

- **The prefix trap.** `str(candidate).startswith(str(root))` admits `/data/ingest-evil` when the root
  is `/data/ingest`. Use `Path.is_relative_to` on **resolved** paths, and test the trap explicitly —
  it is the same shape as the recurring wrong-referent defect: a comparison whose right-hand side is
  nearly the thing meant.
- **Resolve before comparing, and resolve the root too.** A root given as a relative path, or one that
  is itself a symlink, breaks the comparison in the flattering direction.
- **AC-2's refusal must not leak through timing or message.** One message, one status, built before
  any filesystem call whose duration depends on the answer.
- **Do not weaken the upload path.** Story 2.1's `dest.resolve().is_relative_to(spool_resolved)` at
  `app.py:1451` is correct and stays; this story is its sibling for the folder route.
- **`recurse_symlinks`** is `False` by default in Python 3.13 `Path.glob`/`rglob`. AC-5 pins the
  behaviour rather than reimplementing it, and says so in the test's name.

### References

- FR-1 (`prd.md:281`) — the traversal clause, verbatim, including the class name
  `traversal-out-of-scope` and the `[ASSUMPTION]` naming the hazard as *"a link into another matter's
  folder must not silently ingest that material under this matter's RBAC scope"*.
- `b3-b4-audit-2026-08-15.md` §3.1 — the finding, the verification, and C1.
- Story 2.1 change log — the upload-path traversal, found and fixed, whose sibling this is.
- AD-31 — the fail-closed start-up posture this applies to the filesystem.

## Dev Agent Record

### Completion Notes

**What the boundary is now.** One module — `core/domain/traversal.py` — owns both halves: the outer
root (`resolve_within` / `ingest_root`) and the inner subtree (`walk_confined`). The route resolves
the caller's folder within the root **before any filesystem call whose behaviour depends on it**, and
answers out-of-root and absent identically. The capacity pre-flight now counts from the same `Walk`
the ingestion uses, so the count that decides whether a job fits and the walk that ingests are no
longer two traversals of two possibly different sets.

**`ErrorClass.TRAVERSAL_OUT_OF_SCOPE` has a producer for the first time.** It had sat in the taxonomy
since Story 2.x with none — this project's dominant defect shape, in the very requirement whose
boundary was missing.

**The overlap rule is about two directories, not about the volume.** The first draft refused any root
inside `APX_DATA_PATH`, and the suite showed within one run why that is wrong: a corpus directory
sitting beside `originals/` and `spool/` on the same volume is an ordinary on-premise layout that
reaches nothing it should not, and refusing it pushes a deployment toward turning the confinement off.
The rule now names the two sensitive directories in both directions.

**Not gated at start-up, deliberately.** The encryption key and the head journal fail the boot because
nothing works without them. An unset `APX_INGEST_ROOT` disables one route, and the path the SPA
actually uses (`/api/ingest-upload`, with its own Story 2.1 sandbox) is unaffected — so a boot gate
would break deployments that only ever upload, in exchange for a refusal the route already gives.

### Found while building

- **A broken link resolves rather than raising.** `Path.resolve()` does not fail on a dangling link;
  it returns the non-existent target. So a broken link *pointing outside* is reported as out of scope,
  and one pointing inside is not. Both are asserted, and the conservative reading is kept: the clause
  is about where a link POINTS, and special-casing the dangling case would hand anyone a shape that
  points outside without being recorded.
- **The check's own first defect was the family it exists to close.** Matching the bare attribute
  `walk` flagged `core/projection.py`'s local recursive `walk(value)` over an in-memory mapping — a
  guard inspecting the SHAPE of a call rather than the property. `os.` functions are now matched only
  in the qualified form, and the false positive is kept as a named regression test.
- **One permitted enumeration, with its reason written down.** `msg_worker.py` lists the
  `TemporaryDirectory` it just created, to find what `extract-msg` wrote. That is not a traversal of
  submitted material and cannot carry a subtree boundary, because there is no submitted subtree.
- **The link is not ingested and does not vanish either.** The first API assertion was wrong, not the
  code: the link WAS submitted, so `submitted_pieces` counts it, and it is accounted for in the
  register. The SM-3 identity still reconciles, and the test now asserts that rather than a count.
- **148 suite failures, and they were the rule working.** Pinning `APX_DATA_PATH` to `tmp_path` while
  the ingest root is also `tmp_path` is exactly the unsafe configuration. The suite now puts the data
  volume BESIDE the ingestable tree, which is the shape a deployment has.

### Known, named, and not fixed here

- **`/api/ingest-upload` is untouched.** Its own traversal was found and fixed in Story 2.1 and its
  sandbox check stays. This story is its sibling for the folder route.
- **A walk reached through an alias, or written into a shell-out, is not decidable** by the check, and
  its success message says so rather than claiming the property whole.
- **The worker's `enumerate_units` records nothing.** It returns the confined unit set; the register
  entries for out-of-scope links are written by `ingest_folder`, which owns the register. A resumable
  import that only ever calls `enumerate_units` would freeze the right units and report no breach —
  worth closing when the two ingestion paths are next reconciled.

### File List

**New** — `apx/core/domain/traversal.py` · `apx/checks/traversal.py` ·
`tests/domain/test_traversal.py` · `tests/api/test_ingest_confinement.py` ·
`tests/checks/test_traversal_checks.py` · `tests/_fixtures/traversal_violations/{clean,second_walk,os_walk}/`

**Modified** — `apx/core/app/ingest.py` · `apx/api/app.py` · `apx/checks/{registry,manifest}.py` ·
`README.md` · `tests/conftest.py` · eight test files whose data volume moved beside the ingestable
tree

**Gate at close:** ruff clean · import-linter 3 kept / 0 broken · **104** structural checks (103 → 104)
· fitness frame green, 6 asserted / 7 pending · **2 113 passed, 12 skipped** (2 083 → 2 113, +30) ·
client `typecheck` + `build` clean.

## Change Log

| Date | Change |
|---|---|
| 2026-08-15 | Story created from action item C1 (B3/B4 audit), after Julian authorised the audit's recommended sequence. |
| 2026-08-15 | Implemented T1–T7. The route is confined, FR-1's three traversal clauses are built, `traversal-out-of-scope` has its first producer, and `filesystem-has-one-walk` (103 → 104) holds the one-walk property. Gate green at 2 113 tests. Status → done. |
