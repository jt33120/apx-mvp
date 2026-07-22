# Edge Case Hunter Review — Story 1.1 (repository scaffolding)

**Method:** `bmad-review-edge-case-hunter` (exhaustive path enumeration) applied to
`story-1.1.diff`, then extended with build/CI-scaffolding boundary analysis. The diff
is entirely new files (`new file mode 100644`), so the Step 4 deletion check is **N/A**.

**Not reasoned — executed.** The tools are installed in `.venv`
(import-linter 2.13, grimp 3.15, pytest 9.1.1, procrastinate 3.9.0, fastapi 0.139.2,
ruff 0.15.22, npm 11.12). Every finding and every dismissal below was verified by
running the actual harness, pytest, `lint-imports`, `npm ci --dry-run`, and `ruff`.
Three of my strongest theoretical suspects (missing lockfile, basename-only
`norecursedirs`, module-level construction failing) were **empirically defeated** and
moved to "Handled". What remains is real.

**Verdict:** Green on the happy path (repo-root `uv run` invocation) — all three Python
gates and the web build genuinely pass. But the layering guard's liveness is coupled to
*how* and *from where* it is invoked, and its live/dead signal is derived from an
overloaded exit code, so it can both cry wolf and, after a future edit, silently die.

---

## Findings (skill output — JSON)

```json
[
  {
    "location": "apx/checks/layering.py:48-51",
    "trigger_condition": "harness run from any directory other than the repo root",
    "guard_snippet": "cmd = [exe, \"--config\", str(config or _REPO_PYPROJECT)]  # never rely on cwd discovery",
    "potential_consequence": "import-linter 'Could not read any configuration' (exit 1) reported as [FAIL] AD-4 layering violation"
  },
  {
    "location": "apx/checks/layering.py:52",
    "trigger_condition": "lint-imports exits non-zero for a config/tool error, or exits 0 with zero contracts collected",
    "guard_snippet": "ok = proc.returncode == 0 and \"broken\" in proc.stdout.lower()  # confirm a contract was actually evaluated",
    "potential_consequence": "tool errors masquerade as AD-4 violations; a dropped contract reports PASS on a dead guard"
  },
  {
    "location": "tests/checks/test_layering_check.py:41-50",
    "trigger_condition": "import-linter loads config then errors (or is changed) instead of evaluating the contract",
    "guard_snippet": "assert \"BROKEN\" in output and \"1 broken\" in output  # not merely returncode != 0 and name-in-output",
    "potential_consequence": "guard-liveness test stays green though no BROKEN verdict was produced — the exact rot it exists to catch"
  },
  {
    "location": "apx/api/app.py:10 ; apx/worker/app.py:15",
    "trigger_condition": "module-level FastAPI()/procrastinate App() construction breaks after a dependency bump",
    "guard_snippet": "def test_boundaries_import(): import apx.api.app, apx.worker.app  # grimp static-analyses, never executes these",
    "potential_consequence": "broken boundary object ships green: no check or test ever imports either module"
  },
  {
    "location": "apx/adapters/store_postgres/migrations/env.py:18-20",
    "trigger_condition": "alembic invoked with DATABASE_URL unset (latent: no migrations exist in 1.1)",
    "guard_snippet": "if not _db_url: raise SystemExit(\"DATABASE_URL not set\")  # no else on the if _db_url guard",
    "potential_consequence": "opaque SQLAlchemy 'could not parse empty url' error instead of a clear message; surfaces at story 1.3"
  },
  {
    "location": "apx/checks/__main__.py:31-32",
    "trigger_condition": "a registered check raises instead of returning a CheckResult (relevant once 1.12 adds checks)",
    "guard_snippet": "try: result = check()\nexcept Exception as e: result = CheckResult(check.__name__, \"?\", False, repr(e))",
    "potential_consequence": "one raising check aborts the harness; all later checks skipped, no [FAIL] line emitted"
  },
  {
    "location": "deploy/docker-compose.yml:32-36 (healthcheck)",
    "trigger_condition": "first-boot postgres initdb window; pg_isready flaps before the server is truly ready",
    "guard_snippet": "healthcheck: { start_period: 30s, ... }  # keep init-window failures off the retry budget",
    "potential_consequence": "cold-volume init can consume the 5x10s retry budget and mark the service unhealthy"
  }
]
```

---

## Extended boundary analysis (build/CI scaffolding)

For each: the exact boundary, why the shipped code does not handle it, the concrete
consequence, and the empirical evidence.

### 1. Checks harness / layering check

**1a. Spurious AD-4 failure when run from anywhere but the repo root. [HIGH]**
`layering.run()` builds `cmd = [exe]` (plus `--config` only if a `config` arg is passed,
which neither `__main__` nor the passing test ever does) and calls
`subprocess.run(cmd, ...)` with no `cwd=`. `lint-imports` therefore discovers
`[tool.importlinter]` by looking in the **process working directory's** `pyproject.toml`.
Verified: from the repo root the harness prints `[PASS] core imports no adapter (AD-4)`
(exit 0); from `cd apx` it prints:

```
[FAIL] core imports no adapter (AD-4)
...Could not read any configuration.
```

The consequence is a false "architecture violated (AD-4)" signal from any caller that
does not happen to be cwd'd at the repo root — a pre-commit hook, an IDE task runner, or
any monorepo tool that invokes from a package subdirectory. Nothing pins the config path
or the cwd. CI is safe only incidentally, because it runs `uv run python -m apx.checks`
from the checkout root.

**1b. Exit-code conflation — the guard can both cry wolf and die silently. [HIGH]**
`ok = proc.returncode == 0`. `lint-imports`'s exit code is overloaded, verified three ways:
- real contract violation → exit **1** (fixture: "Contracts: 0 kept, 1 broken");
- could-not-read-config → exit **1** (the 1a case);
- **zero contracts collected → exit 0** ("Contracts: 0 kept, 0 broken.").

So the harness (a) cannot distinguish "the architecture is broken" from "the check could
not run", and reports both as `[FAIL] AD-4`; and (b) more dangerously, if a future edit
to the `[tool.importlinter]` block ever drops or mis-names the contract so that **zero**
contracts are collected, `lint-imports` exits 0 and the harness prints
`[PASS] core imports no adapter (AD-4)` — a dead guard reporting green. The runner never
confirms that at least one contract was actually evaluated. This is the precise
"a guard that never fires is indistinguishable from no guard" risk the failure-path test
was written to prevent, reintroduced one layer up in the harness itself.

**1c. Missing-tool case is handled — but misattributed.** `exe = shutil.which("lint-imports"); if exe is None: return CheckResult(..., ok=False, detail="lint-imports not found on PATH — run \`uv sync --group dev\`.")` is a genuine guard. Residual nit (verified by
running `.venv/bin/python -m apx.checks` with the venv bin off `$PATH`): because
`shutil.which` searches `$PATH` rather than the running interpreter's environment, a
direct-interpreter or non-activated-venv invocation reports the tool missing **even though
it is installed in the same venv**, and it surfaces under the `[FAIL] core imports no
adapter (AD-4)` line — reading as a layering violation rather than a tooling gap. Not
counted as unhandled (the message is clear), but the AD-4 framing is misleading.

**1d. Empty tree imports cleanly — verified, so this is a coverage gap, not a crash.**
`apx.worker.app` does build `App(connector=testing.InMemoryConnector())` at import time and
`apx.api.app` builds `FastAPI(...)`; I imported both — they construct without error under
the pinned procrastinate 3.9.0 / fastapi 0.139.2. The real gap (finding 4) is that
**nothing exercises them**: import-linter/grimp analyses statically without executing module
bodies, and the only test imports `apx.checks.layering`. A future regression in either
module-level construction ships green.

### 2. The failure-path test

**2a. Assertions don't verify the BROKEN verdict. [MEDIUM]**
`test_layering_check_reports_a_violation_on_a_violating_fixture` asserts only
`proc.returncode != 0` and `"core_fake" in output`. Verified against real `lint-imports`
output: the string `core_fake` appears in the contract-title header
("core_fake imports no adapter_fake (fixture of AD-4)") **whenever the config loads,
regardless of kept vs broken**, and `returncode != 0` is produced by a broken contract
*or* by any import-linter error that occurs after the config is read. So the two
assertions together are satisfied by "loaded the config, then errored for any reason" —
they do not specifically confirm a BROKEN verdict. Assert on `"BROKEN"` / `"1 broken"`.

**2b. cwd/sys.path for the fixture — handled, verified.** `subprocess.run([...], cwd=FIXTURE)`
plus import-linter inserting the working directory means grimp resolves `core_fake` /
`adapter_fake` from the fixture dir. Verified: "Analyzed 2 files, 1 dependencies. ... 0
kept, 1 broken" — a genuine contract violation, not a ModuleNotFound masquerade.

**2c. `tests/_fixtures` collection — handled, verified.** `norecursedirs = ["tests/_fixtures"]`
is effective on pytest 9.1.1 (the version `pytest>=8.0` resolves to). Clean-room control:
with a non-matching `norecursedirs` value a probe test under `tests/_fixtures/...` IS
collected; with `tests/_fixtures` it is NOT — pytest 9 matches the pattern against the
relative path, not merely the basename. The real suite collects exactly 2 tests and
passes. (My basename-only theory was wrong for this pytest version.)

**2d. Fixture `.importlinter` resolves — verified** via `--config .importlinter` with
`cwd=FIXTURE`.

### 3. CI vs local

- **`shutil.which` on PATH under CI — handled.** CI wraps every Python step in `uv run`,
  which puts `.venv/bin` on `$PATH`, so `lint-imports` resolves. (Local direct-interpreter
  runs are the 1c nit.)
- **`.nvmrc` 24.18.0 vs `setup-node` — handled.** `node-version-file: apx/web/.nvmrc`
  pins an exact version; `package.json` `engines` (`>=24.18 <27`) is consistent.
- **`npm ci` lockfile — handled, verified.** `package-lock.json` **is** committed
  (`git ls-files` returns it; not gitignored) and **in sync**: `npm ci --dry-run` in
  `apx/web` reports "up to date" (exit 0). The "no lockfile → CI web job dies" theory is
  false. `dist/` and `tsconfig.tsbuildinfo` on disk confirm `tsc -b && vite build` runs.
- **web job `working-directory` / `node-version-file` path — handled, correct.**
  `defaults.run.working-directory: apx/web` applies only to `run:` steps; the
  `node-version-file:` under `with:` is resolved from `GITHUB_WORKSPACE`, and the value is
  the repo-root-relative `apx/web/.nvmrc` — correct precisely because the full path was
  used rather than a bare `.nvmrc`.
- **ubuntu vs macOS case — no issue.** The only relative imports are `./App` → `App.tsx`
  and `./tokens.css` → `tokens.css`; case matches, so case-sensitive Linux resolves them.
- **ruff over the intentionally-violating fixture — handled.** `tests/_fixtures` is NOT in
  `extend-exclude`, so `ruff check .` lints `core_fake/__init__.py` (which imports the
  forbidden edge). Verified: `ruff check tests/` → "All checks passed!" (the `# noqa: F401`
  covers the one rule it would trip).

### 4. docker-compose

- **Required-var `:?` — handled by design.** `${POSTGRES_USER:?...}` / `${POSTGRES_PASSWORD:?...}`
  make `docker compose config`/`up` fail closed with the given message when unset. The
  `${POSTGRES_USER}` / `${POSTGRES_DB}` inside the healthcheck are compose-interpolated at
  parse time (the required var guarantees a value; `POSTGRES_DB` defaults to `apx`), so the
  healthcheck string is well-formed. One residual: the file cannot be `docker compose
  config`-validated in CI without dummy creds injected — worth knowing before a compose-lint
  step is added.
- **Healthcheck correctness — minor gap (finding 7).** `pg_isready -U ... -d ...` is right,
  but there is no `start_period`; on a cold-volume first boot the initdb window can flap and
  eat into the 5×10s retry budget. Low consequence at current scale.

### 5. Empty-dir git tracking — handled, verified

The only genuinely empty directory, `.../migrations/versions/`, is kept by
`apx/adapters/store_postgres/migrations/versions/.gitkeep` (empty blob in the diff). Every
other directory in the tree contains at least one tracked file (`__init__.py`, source, or
config), so none is silently dropped. `migrations/README` has no trailing newline — cosmetic
only.

---

## Handled boundaries I nearly flagged (quoted)

| Boundary | Handling (verified) |
|---|---|
| `lint-imports` missing | `exe = shutil.which("lint-imports"); if exe is None: return CheckResult(..., ok=False, detail="lint-imports not found on PATH ...")` |
| Empty `versions/` dropped by git | `apx/adapters/store_postgres/migrations/versions/.gitkeep` |
| `tests/_fixtures` collected by pytest | `norecursedirs = ["tests/_fixtures"]` — effective on pytest 9.1.1 (relative-path match); suite collects 2 tests, passes |
| `npm ci` needs an in-sync lockfile | `apx/web/package-lock.json` committed & in sync (`npm ci --dry-run` → "up to date") |
| `node-version-file` vs `working-directory` | `node-version-file: apx/web/.nvmrc` (repo-root-relative, unaffected by `run.working-directory`) |
| compose required creds unset | `${POSTGRES_USER:?...}` / `${POSTGRES_PASSWORD:?...}` fail closed |
| module-level `App()` / `FastAPI()` construction | imports cleanly under pinned procrastinate 3.9.0 / fastapi 0.139.2 (gap is coverage, finding 4, not a crash) |
| ruff over the violating fixture | `# noqa: F401` on the forbidden import; `ruff check tests/` clean |
