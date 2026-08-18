# APX MVP

AI platform for law firms (France / Luxembourg), built by APX Advisory.
Rebuild — planned and executed with the **BMAD Method v6**.

## Start here

Read [`docs/context/00-README.md`](docs/context/00-README.md). It indexes the full
context pack: clients and their stated requirements, a retrospective of the previous
build with salvage verdicts, the design inventory, the competitive landscape, and the
verbatim source documents.

> **⚠️ Read the context pack with this correction in hand.** `docs/context/01-…` and the
> sources under `docs/context/00-sources/` (notably `state-snapshot.json`) describe the
> prospect relationships as live. **They are stale. No client engagement has been won,
> and no client corpus exists.** The product is built for the *use case*, not for a named
> firm; requirements gathered in discovery are kept on their merits, not their provenance.
> Established 20 July 2026 — see `_bmad-output/planning-artifacts/briefs/brief-apx-mvp-2026-07-20/addendum.md` §1.

**Current state of planning.** The first increment is **mass-document triage** (reversed
against Syllogisme on 20 July 2026, on commercial and competitive evidence). The
authoritative documents, in dependency order:
`_bmad-output/brainstorming/…/brainstorm-intent.md` → `…/briefs/brief-apx-mvp-2026-07-20/`
→ `…/prds/prd-apx-mvp-2026-07-20/` (60 FRs). Reviews and the revision log sit beside the PRD.

The previous implementation lives at `../apx-platform/` — **reference only, never an
edit target**. Ditto `../APX/`, `../legal-rag-core/`, `../maquettes/`,
`../../Resources/`, `../../Agents/`.

## Non-negotiables (blocking)

EU-only · zero-retention · no fine-tuning on client data · strict RAG with citations or
an honest "not in the corpus" · human-in-the-loop everywhere (no auto-delete, auto-send,
auto-sign) · triage is reversible labelling, never deletion · recall over precision in
triage · full audit trail · RBAC by matter (Chinese walls).

Rationale and provenance: `docs/context/00-README.md`.

## Language

Agents converse in **French**. Documents, code, comments and commits are **English**.
French legal terms of art (*ordonnance 145 CPC*, *conclusions*, *veille*) stay in French.

## BMAD

Installed under `_bmad/`, skills exposed in `.claude/skills/` (86 skills across bmm, cis,
wds, tea, bmb, core). Outputs land in `_bmad-output/` (planning + implementation
artifacts) and `design-artifacts/` (WDS).

Lost? Invoke the `bmad-help` skill and ask it what to do next.

## Where the state is

`_bmad-output/implementation-artifacts/sprint-status.yaml` is the **single source of
truth** for what is done, what is next, and every open action item. Read it in full
before starting anything — each story's line carries a long note saying what that story
actually made true. The two retrospectives (`epic-4-retro-2026-08-07.md`,
`epic-5-retro-2026-08-14.md`) carry the lessons and the open action items **A5, B1–B9**.

## The story cycle

Every story runs the same full cycle, and it is not negotiable:

1. `bmad-create-story` — the story file, with acceptance criteria and tasks.
2. `bmad-dev-story` — implement, red-green-refactor, no task ticked until its tests pass.
3. **Adversarial review** — several named lenses over the whole diff, each finding put to
   **two independent skeptics instructed to REFUTE and to default to refuted when
   uncertain**. Keep the standing lenses: the **wrong referent** (*for every comparison,
   is the right-hand side the same thing as the left?*), the **seams** (HTTP↔seam,
   client↔server, check legs — this is where the defects live, not in the engines), and
   *which decision or requirement does this diff claim to implement, and is every clause
   of it reachable?*
4. **Report the coverage lost.** Any lens or skeptic that errored or stalled is named in
   the story's review section. A silent lens is not a clean bill of health, and an
   unadjudicated finding is not a refuted one.
5. Fix **every** confirmed finding, each with a regression that fails without it. A
   check that fires is answered by **removal or by strengthening, never by weakening**.
6. Re-run the full gate, then commit, then mark done, then report to Julian in French.

## The gate — green before every commit, no exceptions

Run from the repo root, in **one** Bash call (shell state does not persist, and a
`cd apx/web` resets the working directory — re-anchor with the absolute path):

```bash
cd <repo-root> && export PATH="$PWD/.venv/bin:$PATH" && \
  ruff check . && lint-imports && python -m apx.checks && \
  python -m apx.fitness && pytest -q
cd <repo-root>/apx/web && npm run typecheck && npm run build
```

Expected as of Story 7.2 (2026-08-18): ruff clean · `Contracts: 3 kept, 0 broken` ·
**106** structural checks passed · fitness frame green, 6 asserted / 7 pending ·
**2 173 passed, 12 skipped** · client typecheck and build clean.
*(Close of Epic 5: 103 checks, 2 077 tests. Story 7.1: 104, 2 113. Retro B2: 105, 2 141.)*

- **uv only** — `.venv/bin/ruff`, `.venv/bin/python`. Never `pip`. `uv sync --group dev`
  on a fresh clone; `cd apx/web && npm ci` for the client.
- **`ruff format` is not part of the gate** — the codebase is not ruff-formatted, and
  running it would rewrite 367 files. Lint only.
- **Never export `DATABASE_URL`.** The suite runs on SQLite; exporting it breaks it.
- `pytest` has no `--timeout` plugin here.
- ruff line length is **100**, and accented characters (*pièce*, é, →, §) push a line
  past it where the formatter's arithmetic does not. **Reflow by hand.**
- `python -m apx.checks | tail -2` alone hides a failure behind the README meta-checks —
  read the count line **and** grep `[FAIL]` separately.

## Committing

Commit on `master`. **Enumerate the files explicitly — never `git add -A`**, because
unrelated working-tree changes are usually present. Review
`git diff --cached --name-status` before committing, and **scan the staged diff for
secrets** (API keys, tokens, private keys, connection strings with credentials) as the
last act before `git commit`. A commit message says what the change made true, not what
files moved.

**Secrets never enter the repository, in any form, including tests and fixtures** — the
environment only (FR-51/AD-47). The repository is **public**.

