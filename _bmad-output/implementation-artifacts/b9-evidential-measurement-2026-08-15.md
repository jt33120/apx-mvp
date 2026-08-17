# B9 — the evidential path's two unmeasured costs, measured

**Date:** 2026-08-15 · **Action item:** B9 (Epic 5 retrospective) · **Instrument:**
`apx/timedrun/evidential.py`, tests in `tests/timedrun/test_evidential.py` · **Contract under
question:** AD-44 (high-volume machine-generated events are partitioned per worker and sealed into
the chain)

Stories 5.8 and 5.9 each closed by naming a figure nobody had, and the retrospective made measuring
them B9. Both are now measured. **Both are linear, and neither trips AD-44 at the design target.**

---

## 1. What was measured, and on what

| | |
|---|---|
| Machine | dev hardware (Apple silicon), Python 3.13.13 |
| Store | **SQLite in-memory** — the suite's baseline store |
| Writers | **one** |
| Instrument | `apx.timedrun.evidential`, which times the product's **own** call (`SqlStore.validate_pieces`), injected rather than re-implemented |

**What this is a measurement of, stated before the numbers.** It bounds how the cost **grows with
N** — the question Stories 5.8 and 5.9 actually left open. It is **not** a target-hardware figure and
it is **not** a contention measurement. AD-44's subject is many concurrent writers serialising on one
chain head under `SELECT … FOR UPDATE`; that needs the real PostgreSQL and belongs with the 2.13 run.
Nothing here licenses a claim about it, and `apx/timedrun/measurements.json` was **not touched** — the
2.13 record stays honestly `pending` (NFR-2).

---

## 2. The bulk *validation act* (Story 5.8, FR-45(b))

One transaction: one `IN (…)` predicate, one `validation_act` ledger row and **two** audit entries
per *pièce*, all allocated against **one** chain head row. Story 5.8 declined to chunk it on purpose —
FR-45(b) makes the batch one gesture, and splitting the commit would let half of it land.

| *pièces* | the act (s) | ms per *pièce* | peak RSS (MiB) |
|---:|---:|---:|---:|
| 100 | 0.119 | **1.19** | 133 |
| 425 | 0.518 | **1.22** | 138 |
| 1 700 | **2.096** | **1.23** | 151 |
| 3 400 | 3.833 | **1.13** | 159 |

**The cost is linear.** Per-*pièce* cost is flat from 100 to 3 400 — 1.13 to 1.23 ms, no trend — so
the single `IN (…)` predicate, the 1 700 ledger rows and the 3 400 audit entries against one head row
carry **no super-linear term**. Peak RSS rises 133 → 159 MiB across a 34× growth in N: the batch does
not accumulate the corpus in memory.

**What it costs a firm.** A select-all over ~1 700 *pièces* is **≈ 2 seconds** of held transaction on
this store. The consequence is not a refusal: contention is deliberately excluded from
`AuditUnwritable` (Story 5.9, AD-22's named trap), so a concurrent act on the same *matter* **waits**
rather than failing. Two seconds is a wait a lawyer would not notice and a second writer would.

**Verdict: AD-44 is not tripped by this path.** The decision exists for high-volume
*machine-generated* events. The validation act is human-generated, once per gesture, and linear.

---

## 3. The head journal (Story 1.11 / AD-35, deferral re-affirmed by 5.9)

Written **once per commit and per chain touched** — `_write_heads` keeps the highest `seq` per chain
from the commit, so the 1 700-*pièce* batch above produces **one or two lines**, not 3 400. Parsed
once per reconciliation, which runs at start-up and on every restore.

| lines | file (MiB) | parse (s), median of 5 | µs per line |
|---:|---:|---:|---:|
| 1 000 | 0.21 | 0.010 | 10.16 |
| 10 000 | 2.08 | 0.041 | 4.12 |
| 100 000 | 20.91 | **0.447** | 4.47 |
| 500 000 | 104.93 | **2.379** | 4.76 |

**Linear at ≈ 4.5 µs per line**, with the 1 000-line figure's 10 µs being fixed open-and-read cost
amortising away. 500 000 lines — a quarter of a million write transactions across 20 *matters* — is a
**105 MiB** file parsed in **2.4 seconds**.

**Story 1.11's deferral of compaction holds, and now holds with a number rather than an intuition.**
At the single-firm design target the journal is immaterial. The crossover worth writing down: at
**~1 000 000 lines the parse reaches ≈ 5 s per reconciliation** and the file ≈ 210 MiB. Since
reconciliation runs at every boot, that is where a start-up delay becomes visible — and it is the
point at which the compaction Story 5.9 kept `witness_upto` for (retain the latest head per scope)
should be built, not before.

---

## 4. What is still not measured

- **Contention.** Many writers on one chain head under `SELECT … FOR UPDATE`, on PostgreSQL. This is
  AD-44's actual subject and the figure that would decide whether partition-and-seal is needed. It
  belongs with the 2.13 target-hardware run — and with **B5**, which must give AD-44 an owner.
- **PostgreSQL absolute wall-clock.** SQLite in-memory has no WAL fsync and no network. The *shape*
  (linear, flat memory) transfers; the constants do not.
- **The 5 000-*pièce* concurrent ingestion run** (Story 2.13) remains pending the €2 000 machine, both
  inference profiles, the real BGE-M3 and Tesseract. Untouched by this measurement, and still
  `measured: false` in `measurements.json`.

---

## 5. Reproducing it

`apx/timedrun/evidential.py` ships the two measurements; the arrangement (ingest, rank, place the
line) is the caller's, so the thing timed is the act and not its setup. The driver used for the
figures above built a SQLite store, ingested N *pièces*, ranked them, placed the line, and passed
`SqlStore.validate_pieces` to `measure_validation_batch`.

One thing worth recording: `measure_journal_parse` **refused a run** during this session, because a
journal file left over from an earlier invocation made it parse 2 000 lines where 1 000 were written.
The instrument declining to report a number over a file it had not fully written is the same
discipline as the rest of this build — a measurement over a journal that does not read back is not a
measurement.
