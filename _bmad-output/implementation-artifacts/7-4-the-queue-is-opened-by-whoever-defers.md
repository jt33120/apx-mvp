---
baseline_commit: 99d0404
---

# Story 7.4: The queue is opened by whoever defers onto it

Status: done

## Story

As **a firm whose first gesture with this product is dropping a folder on it**,
I want that submission to be accepted,
So that the product has a front door.

## Why this story exists

Found while mapping the terrain for the Epic-4 write surface (C11), and it outranked that story.

`PsycopgConnector.pool` raises `AppNotOpen` until `open_async` has been called:

```python
    @property
    def pool(self) -> psycopg_pool.AsyncConnectionPool:
        if self._async_pool is None:  # Set by open_async
            raise exceptions.AppNotOpen
        return self._async_pool
```

Across the whole of `apx/`, that call existed in **exactly one place** — `manage worker`, which is a
**different process**. The API's `_lifespan` ran the start-up gate, installed log redaction and
reconciled the head journal, and never opened the queue. So on any real PostgreSQL deployment:

```python
    try:
        await enqueue_import(job_id)
    except Exception as exc:  # noqa: BLE001 — a failed enqueue must not wedge the matter's upload
        store.delete_import_job(job_id)
        shutil.rmtree(spool, ignore_errors=True)
        raise HTTPException(status_code=503, detail="file d'import indisponible") from exc
```

…the `defer` raised **before touching the network**, the handler rolled the ledger row back, deleted
the spooled bytes, and answered **503** *« file d'import indisponible »*. Every submission. The one
gesture the product opens with.

### Why eleven epics of green tests said nothing about it

This is the part worth keeping, because the same shape will happen again.

`_connector()` chooses the connector from `DATABASE_URL` **when the module is imported**. The suite
runs on SQLite. SQLite yields `testing.InMemoryConnector` — the one implementation with **no such
guard**. So the defect existed only in the configuration no test uses, a green suite was not
evidence about it in either direction, and **it could not have become evidence by adding more tests
of the same kind**. The Epic-5 retrospective's dominant finding was *a decision recorded and never
implemented reads exactly like one that was*; this is its sibling — **a path exercised only in the
configuration where it cannot fail reads exactly like a path that works**.

The 503 arm made it quieter still: a caller saw an availability message, which is what a queue
outage looks like, so the symptom described a transient condition while the cause was permanent.

## Acceptance Criteria

**AC-1 — deferring opens the queue.** `enqueue_import` opens the connection pool before it defers.
Not a start-up hook alone: a hook is a habit that holds until a second process, a management command
or a harness defers without having run it, and that failure is silent in exactly the same way.

**AC-2 — once per process, under concurrency.** Two uploads arriving together open one pool. A pool
per upload would exhaust PostgreSQL's connection limit on the one path expected to be used in bursts.

**AC-3 — the API opens it at boot too, and closes it on shutdown.** So a queue this process cannot
reach is a failure at container start rather than a 503 handed to the first lawyer who drops a
folder on it.

**AC-4 — a check keeps the next one right.** Every function in the sealed queue package that defers
opens the queue first, asserted structurally — because the next enqueue helper will be written by
copying this one.

**AC-5 — the mechanism is pinned, not assumed.** The library behaviour the whole story rests on is
asserted directly, with no database and no network, so the fix cannot later be read as superstition
and removed.

## Tasks / Subtasks

- [x] T1 — `ensure_open()` / `close_queue()` in the sealed queue package; `enqueue_import` opens
      first (AC-1, AC-2).
- [x] T2 — the API lifespan opens at boot and closes on shutdown (AC-3).
- [x] T3 — the `defer-opens-the-queue` check, registered in the three lockstep sites (AC-4).
- [x] T4 — tests: the mechanism, the property, idempotence, concurrency, the boot (AC-5).

## Dev Agent Record

### Completion Notes

**The property belongs to the act, not to the caller's memory.** The obvious fix is to open the app
in `_lifespan` and stop. That would have worked, and it would have been the same kind of thing that
broke: correct until something else defers. `ensure_open()` sits inside `enqueue_import`, so a
process that enqueues cannot depend on another process having opened anything. The lifespan opens it
as well, which is now an *early warning* rather than the mechanism.

**The guard is a lock with a re-check inside it**, not a bare flag. Two uploads arriving in the same
event loop are the ordinary case for this route, not the corner one.

**The check is scoped to the sealed queue package** and needs no other scope: `procrastinate` may
not be imported anywhere else in the runtime (AD-17, `queue-sealed`), so that package is the entire
surface on which a `defer` can be written. It fails closed if it cannot find `ensure_open` at all —
a check that cannot locate the door it guards is not passing, it is looking at the wrong tree.

**Proven both ways.** Removing `ensure_open()` from `enqueue_import` turns the check red, naming the
function. And the library behaviour is asserted on its own: `PsycopgConnector(conninfo=…).pool`
raises `AppNotOpen` with no database and no network, because the pool is not lazily created — it is
absent.

### Review

Run in-session across the three standing lenses, on top of a four-agent reconnaissance of the queue,
the route, the client and the re-rank blast radius. **Coverage stated**: the fleet mapped, one
reviewer adjudicated.

**The wrong referent** — the 503 itself is one, and it is the reason this survived: *« file d'import
indisponible »* is a claim about the queue's **availability**, while the condition is that this
process never opened it. A transient symptom over a permanent cause, and the flattering direction,
because a caller retries an availability error rather than reporting it.

**The seams** — the boundary between the two connectors is the seam, and no test crossed it. The new
tests do not fix that by adding coverage on the SQLite side; they assert the PostgreSQL connector's
behaviour **directly**, which is the only thing that could have caught this.

**Which decision does this implement** — AD-6, *"the HTTP layer validates, authorises, enqueues and
returns"*. The clause was implemented and the enqueue could not succeed.

### Found while building, not fixed here

**C14 — the queue schema is applied by the worker alone.** Procrastinate's tables are created by
`worker_app.schema_manager.apply_schema()` inside `python -m apx.manage worker`, deliberately kept
out of the Alembic chain (AD-17). `docker/entrypoint.sh` runs `alembic upgrade head` then uvicorn.
So on a deployment where the worker container has not yet started, the API opens the pool
successfully and then defers against a missing `procrastinate_jobs` table — a second, different way
the enqueue fails while the HTTP surface looks healthy. Ordering, not code: it belongs with **B6**
(deciding what the live deployment is for).

**C11 remains open** — the Epic-4 write surface, unchanged by this story and still the next one.
The reconnaissance behind it produced a pattern map that story 7.5 should read before writing a
line: the enqueue/poll route shape, the job ledger, the probe and registry rows a new route needs,
the client's four unrenderable states, and the re-rank blast radius with a judgement on each of its
four effects.

### File List

- `apx/adapters/store_postgres/queue/__init__.py` — `ensure_open`, `close_queue`; `enqueue_import`
  opens before it defers.
- `apx/api/app.py` — the lifespan opens at boot and closes on shutdown.
- `apx/checks/queue_open.py` — **new**, registered in `registry.py`, `manifest.py`, `README.md`.
- `tests/adapters/test_queue_is_opened.py` — **new** (8).

### Change Log

| When | What |
|---|---|
| 2026-08-18 | Found while mapping C11; fixed; gate green at 108 checks. |
