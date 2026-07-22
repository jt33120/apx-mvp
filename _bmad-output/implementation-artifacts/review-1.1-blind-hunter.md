# Blind Hunter — Adversarial Review, Story 1.1 (repository scaffolding)

**Reviewer stance:** no prior context, hostile read. Every claim below was run, not
reasoned. Method + evidence are inline so the author can reproduce.

## Verdict

The product code (`apx/`, `tests/`) is clean and the layering guard **genuinely fires
today** — I disproved my own leading hypothesis (that the fixture was unreachable) by
running it. But two real defects remain, ranked by damage:

1. **CI's Lint step is red the moment this lands** — `ruff check .` lints committed
   `.claude/` tooling that the exclude list misses. README's "all three green / CI runs
   on every push" is false as committed.
2. **The guard has no floor** — a config with zero contracts passes green, so the
   "a cut cannot drop this check" guarantee (AD-3/AD-45) is not actually enforced.
3. The regression test meant to keep the guard honest is **weakly specified** — it
   passes on a tool *error* just as readily as on a real violation.

Everything else is low severity. This is good scaffolding with a broken CI gate and a
guard whose self-tests don't fully pin down what they claim to.

## What I ran (reproducible)

All against the repo's own `.venv` (import-linter 2.13, ruff, pytest 9.1, Python 3.13.13):

- Copied the committed violating fixture and a **clean** twin (no forbidden import) and
  ran `lint-imports --config .importlinter` from each cwd.
- Ran a **zero-contract** config and a **no-config** dir.
- Ran the real harness `python -m apx.checks` from repo root and from a subdir.
- Ran the two committed tests, `ruff check .`, `ruff check apx tests`, and `pytest -q`.
- `git ls-files` to establish what CI actually checks out.

---

## Findings, ranked by damage

### [HIGH] CI Lint step fails on the first push — `ruff check .` escapes into committed `.claude/`
`.github/workflows/ci.yml` — Lint step: `run: uv run ruff check .`
`pyproject.toml` — `[tool.ruff] extend-exclude` (~L76): `["apx/web", "_bmad", "_bmad-output", "Archives-legacy", "apx/adapters/store_postgres/migrations"]`

`.claude/` is **committed** (`git ls-files .claude` → 1637 files, 49 linted `.py`) and is
**not** in `extend-exclude`. The exclude list clearly *tries* to fence out BMad tooling
(`_bmad`, `_bmad-output` are there) but misses `.claude/skills/**`, where the skill scripts
and `*-template.py` files actually live. Result, measured:

```
ruff check .            -> EXIT 1   (195 violations; all 217 locations under .claude/)
ruff check apx tests    -> EXIT 0   (product code is clean)
ruff check . --exclude .claude -> EXIT 0
```

Violations include `F821` (undefined names in `{template-...}` placeholder files that are
not valid Python by design), `I001`, `E501`. So CI goes red at the Lint step on the very
first push, directly contradicting README ("All three are green... CI runs them on every
push"). Note the asymmetry that makes this a config defect in *this* diff: the checks step
is scoped to `apx` and pytest is scoped via `testpaths=["tests"]` (I confirmed pytest
collects exactly 2 items, not the BMad `test_*.py`), but the lint step alone globs `.`.

**Fix:** scope the lint to the product — `ruff check apx tests` — or add `.claude` to
`extend-exclude`. **Caveat honestly stated:** this assumes the CI checkout contains
`.claude/`; it is tracked in this repo, so it will. If the intent is that `.claude/`
should *not* be in the product repo at all, that is a separate (also real) problem.

### [MEDIUM] Dead-guard floor: a zero-contract config passes GREEN
`apx/checks/layering.py` — `run()`: `ok = proc.returncode == 0`

import-linter exits **0** for "0 kept, 0 broken" (measured):

```
config with root_package but NO contracts -> "Contracts: 0 kept, 0 broken." EXIT 0
```

The harness trusts the exit code and asserts nothing about *how many* contracts ran. The
sole `[[tool.importlinter.contracts]]` block is one edit away from removal — pyproject.toml
literally ships three **commented-out** contracts and a "tightened in 1.12" plan, so hands
*will* be in this block. Remove/comment the one live contract and `python -m apx.checks`
stays green while enforcing **nothing** — the exact "so a cut cannot drop them" property
(AD-3/AD-45) the module's own docstring promises. Currently green for the right reason (1
contract), but there is no floor.

**Fix:** have `layering.run()` (or the runner) assert import-linter reported ≥1 contract —
e.g. require `"kept" in output` with a non-zero kept+broken count, or parse the
"Contracts: N kept, M broken" line and fail if `N+M == 0`.

### [MEDIUM] Failure-path test can't tell "contract fired" from "tool errored"
`tests/checks/test_layering_check.py` — `test_layering_check_reports_a_violation_on_a_violating_fixture`, the two asserts (~L46–50): `assert proc.returncode != 0` and `assert "core_fake" in output`

The docstring says this test exists because "a guard that never fires is indistinguishable
from no guard." But the assertions don't distinguish a *violation* from a *tool error*.
Measured — import-linter's package-discovery **error** path satisfies both:

```
config names core_fake but package absent from graph:
  "Could not find package 'core_fake' in your Python path."  EXIT 1
  returncode != 0  -> YES
  "core_fake" in output -> YES        ("BROKEN" -> absent)
```

On this machine the fixture *does* resolve from cwd (import-linter 2.13 puts cwd on the
graph path — I verified the clean twin returns KEPT/EXIT 0 and the violating one returns
BROKEN/EXIT 1), so the test passes for the right reason **today**. But the assertion is not
pinned to that: any future import-linter/grimp/packaging change that stops resolving the
uninstalled cwd fixture would keep this test green while the contract is never evaluated —
precisely the false-green the test is supposed to prevent.

**Fix:** assert on violation-specific output: `"BROKEN" in output` (or `"1 broken"`, or
`"is not allowed to import"`). One line, and it closes the gap.

### [LOW] `layering.run()` off-root produces a confusing (but fail-safe) failure
`apx/checks/layering.py` — `run(config=None)` relies on import-linter discovering
`[tool.importlinter]` in the cwd's `pyproject.toml`.

Run from anywhere but the repo root, import-linter finds no config → "Could not read any
configuration" → non-zero → `ok=False`. That is **fail-safe** (red), which is correct. The
cost is only UX: the full import-linter ASCII banner plus the terse message land in
`result.detail`, with no hint that the actual cause is "wrong cwd." Fine for 1.1; consider
a clearer message when detail contains "Could not read any configuration".

### [LOW] compose healthcheck `${POSTGRES_DB}` is host-interpolated and undefaulted
`deploy/docker-compose.yml` — healthcheck (~L40): `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`

The `environment:` block defaults `POSTGRES_DB: ${POSTGRES_DB:-apx}`, but the healthcheck's
`${POSTGRES_DB}` is interpolated by Compose from the **host** shell at `up` time (not the
container env) and carries **no** `:-apx` default. If the host hasn't exported `POSTGRES_DB`,
the check runs `pg_isready -U <user> -d ""`. Harmless in practice — `pg_isready` reports
server readiness regardless of database — but it is an inconsistency (defaulted in one
place, bare two lines later). `${POSTGRES_USER}` is safe here only because it is `:?`-required.

### [LOW] Alembic env gives a cryptic failure when `DATABASE_URL` is unset
`apx/adapters/store_postgres/migrations/env.py` (~L18): `_db_url = _os.environ.get("DATABASE_URL")`; only sets `sqlalchemy.url` `if _db_url`.

With `DATABASE_URL` unset, `sqlalchemy.url` stays blank and `alembic upgrade` dies inside
SQLAlchemy with an opaque error. Inert in 1.1 (no migrations, no DB), but story 1.3 will
hit it — a `raise` with a clear "set DATABASE_URL" message would fail closed and readably.

## Minor / nits (real, low value)

- **README oversells verification** — "All three are green" is factually false as committed
  (see HIGH). Documentation should not assert a green it doesn't have.
- `env.py` uses `import os as _os` mid-file after the top imports; the alias buys nothing and
  only dodges `E402` because the migrations dir is ruff-excluded.
- `vite.config.ts` is outside the TS project (`tsconfig.json` `include: ["src"]`), so
  `tsc -b` never type-checks it; a type error there surfaces only when Vite loads the config.
- compose publishes Postgres on `0.0.0.0:${POSTGRES_PORT:-5432}` for a product that stresses
  air-gapped/security posture; `127.0.0.1:5432:5432` would be a safer local-dev default.
- `[project.optional-dependencies]` is present but empty (comment only) — parses fine, could
  just be omitted.

## Nearly flagged — verified genuinely fine (saving the author time)

- **import-linter exit-code handling in `layering.py` is correct** for the pass /
  violation / tool-missing / broken-config / no-config cases — all fail safe (red). Only the
  zero-contract case (MEDIUM above) slips through.
- **`shutil.which("lint-imports") is None` → `ok=False`** — correct fail-safe, not a
  swallowed error.
- **setup-node `node-version-file: apx/web/.nvmrc`** is repo-root-relative and **correct**
  despite the job's `working-directory: apx/web` default — that default affects only `run:`
  steps, not `with:` inputs.
- **Alembic escapes `%`** (`set_section_option` does `value.replace("%","%%")`), so a
  percent-encoded password in `DATABASE_URL` will not blow up ConfigParser interpolation.
- **`tsc -b && vite build` with `noEmit: true` on a single non-composite tsconfig** works on
  the pinned TS 5.9.3 (noEmit-in-build-mode supported since 5.6).
- **`react-router` 8.2.0**: importing `createBrowserRouter`/`RouterProvider` from
  `"react-router"` is correct post-v7 consolidation (no `react-router-dom`).
- **No secrets committed**: `sqlalchemy.url` is blank, compose requires `POSTGRES_USER`/
  `POSTGRES_PASSWORD` via `:?`, and the repo `.gitignore` covers `.venv`/`dist`/secrets. The
  no-secret-in-source intent (AD-47) is satisfied.
- **Toolchain resolves**: the `.venv` builds from this `pyproject.toml` and the harness +
  pytest run, so the aggressive version pins resolve and the manifest parses.
- **pytest scoping is correct**: `norecursedirs=["tests/_fixtures"]` + `testpaths=["tests"]`
  → only the 2 real tests collected; the BMad `test_*.py` under `.claude/` are not run.
