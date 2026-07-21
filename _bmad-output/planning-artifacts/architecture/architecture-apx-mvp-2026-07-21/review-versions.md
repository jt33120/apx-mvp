# Review — Version & Reality Check of the Architecture Spine

**Target:** `ARCHITECTURE-SPINE.md` (architecture-apx-mvp-2026-07-21)
**Claimed evidence base:** `docs/context/05-stack-research-2026-07.md` (1203 lines, 2026-07-21)
**Review date:** 2026-07-21
**Lens:** every committed technology decision must have been web-researched or reality-checked,
not asserted from training data — current versions, that each named technology still exists and
fits, and the live defaults of anything the build leans on.

**Method actually used.** Every version, date, licence and CVE below was fetched live from a
primary source on 2026-07-21: the PyPI JSON API, the npm registry, the GitHub Releases and
Contents APIs, `postgresql.org`, `nodejs.org/dist/index.json`, `hub.docker.com`, the Hugging Face
model API, `osv.dev` and the NVD REST API. Where a claim turns on library behaviour rather than a
version number, the library's own source at the pinned tag was read. Nothing here is asserted
from memory.

---

## Verdict

The spine's stack table is **unusually well grounded**: 33 of 34 committed versions are the exact
current release from the project's own registry, and every licence claim checks out. That is a
much better result than this lens usually returns, and the research document deserves the credit —
it is genuinely sourced.

The failures are not in the version numbers. They are in **three things the distillation dropped
or reworded**, and in **one command-line flag that nobody opened the manual for**. The single
critical finding is that `cosign --offline`, on which AD-30's entire air-gapped install gate
rests, is deprecated in cosign 3.x and no longer means what the spine says it means.

**Counts:** 34 committed technology/version pairs. **31 verified exactly** · **1 wrong (stale)** ·
**2 unsupported or under-specified** (Starlette carries no version; psycopg is absent entirely
despite being a mandatory in-process dependency). Plus **1 critical behavioural claim falsified**,
**4 high-severity findings**, **7 medium**.

---

## 1. Extraction — every named technology and version in the spine

Committed in the Stack table (lines 660–694) unless noted. "Verified" = fetched from the primary
registry on 2026-07-21 and found to be the current release with the stated licence.

| # | Technology | Spine claim | Primary-source result | Status |
| --- | --- | --- | --- | --- |
| 1 | Python | 3.13.14 | 3.13.14, 2026-06-10 | ✅ |
| 2 | FastAPI | 0.139.2 | 0.139.2, 2026-07-16, MIT | ✅ (but see **H4**) |
| 3 | Starlette | *no version given* | 1.3.1, 2026-06-12, BSD-3 | ⚠️ **H4** |
| 4 | Uvicorn | 0.51.0 | 0.51.0, 2026-07-08, BSD-3 | ✅ |
| 5 | Pydantic | 2.13.4 (2.14.0a1 alpha) | 2.13.4, 2026-05-06; 2.14.0a1, 2026-05-22 | ✅ |
| 6 | SQLAlchemy | 2.0.51 (2.1.0b3 beta) | 2.0.51, 2026-06-15; 2.1.0b3, 2026-06-28 | ✅ |
| 7 | Alembic | 1.18.5 | 1.18.5, 2026-06-25, MIT | ✅ |
| 8 | PostgreSQL | 18.4 (PG19 at Beta 2) | 18.4, **2026-05-14**, current 18.x minor; PG19 Beta 2, 2026-07-16 | ✅ (see **M8**) |
| 9 | pgvector | ≥ 0.8.5 | 0.8.5, 2026-07-08, latest tag | ✅ (see **M4**) |
| 10 | Procrastinate | 3.9.x | 3.9.0, 2026-06-20, MIT, repo active | ✅ (but see **H1**) |
| 11 | BGE-M3 | 568M, 1024-dim, MIT | `BAAI/bge-m3`, licence **mit** | ✅ |
| 12 | multilingual-e5-large-instruct | 560M, 1024-dim, MIT | `intfloat/…`, licence **mit** | ✅ |
| 13 | Qwen3-Embedding-0.6B | 0.6B, 1024-dim, Apache-2.0 | `Qwen/…`, licence **apache-2.0** | ✅ |
| 14 | vLLM | 0.25.1, pinned by digest | v0.25.1, 2026-07-14, Apache-2.0 | ✅ |
| 15 | Mistral Small 3.2 24B | Apache-2.0, INT8/Q4 on 24 GB | repo exists, **apache-2.0** | ⚠️ **M2**, **M3** |
| 16 | Ollama | 0.32.1 | v0.32.1, 2026-07-16, MIT | ✅ (see **M9**) |
| 17 | extract-msg | 0.56.0, GPL-isolated | 0.56.0, 2026-07-18, **GPL-3.0** | ✅ |
| 18 | pypdf | 6.14.2 | 6.14.2, 2026-06-23, BSD-3 | ✅ |
| 19 | pdfplumber | 0.11.7 | **latest is 0.11.10, 2026-06-15** | ❌ **M1** |
| 20 | Docling | 2.114.0, MIT | 2.114.0, 2026-07-20, MIT, 63.5k★ | ✅ (see **M5**) |
| 21 | Tesseract | 5.5.2, Apache-2.0 | 5.5.2, 2025-12-26, latest, Apache-2.0 | ✅ |
| 22 | python-docx | 1.2.0 | 1.2.0, 2025-06-16, MIT, latest | ✅ |
| 23 | openpyxl | 3.1.5 | 3.1.5, 2024-06-28, MIT, latest | ✅ (see **M10**) |
| 24 | pwdlib[argon2] | 0.3.0 | 0.3.0, 2025-10-25, MIT, 0 advisories | ✅ |
| 25 | argon2-cffi | 25.1.0 | 25.1.0, 2025-06-03, MIT | ✅ |
| 26 | PyJWT | 2.13.0 | 2.13.0, 2026-05-21, MIT | ⚠️ **H2** |
| 27 | pyotp | 2.10.0 | 2.10.0, 2026-06-14, MIT | ✅ |
| 28 | py_webauthn | 3.0.0 | `webauthn` 3.0.0, 2026-06-29, BSD-3; repo **not archived**, 1053★ | ✅ |
| 29 | Vite | 8.1.5 | 8.1.5, 2026-07-16, npm `latest` | ✅ |
| 30 | React Router | 8.2.0 | 8.2.0, 2026-07-08, npm `latest`, MIT | ✅ |
| 31 | Node.js | 24.18.0 LTS | 24.18.0, 2026-06-23, LTS "Krypton" | ✅ |
| 32 | Docker Engine | 29.6.2 | `docker-v29.6.2`, 2026-07-16 | ✅ |
| 33 | Docker Compose | v5.3.1 | v5.3.1, 2026-07-07 | ✅ |
| 34 | cosign | 3.1.2, verified `--offline` | v3.1.2, 2026-07-17 — **but see C1** | ❌ **C1** |
| — | **psycopg** | **absent from the spine** | 3.3.4, 2026-05-01, **LGPL-3.0-only**, hard dep of Procrastinate | ❌ **H1** |

---

## 2. Critical

### C1 — `cosign --offline` is deprecated in cosign 3.x and no longer guarantees no network

**Severity: CRITICAL** (it is the install gate of the air-gapped delivery)

**The claim.** AD-30: *"signed with a **cosign 3.1.2 key pair** and verified `--offline` by the
installer — keyless verification needs Fulcio and Rekor and is unusable air-gapped."* Repeated in
the deployment diagram (`REL -->|"verified --offline by the installer"| SITE`) and in the Stack
table. The research's §7 gives the literal command:
`cosign verify --key cosign.pub --offline --local-image ./bundle`.

**What I found.** Reading cosign's own source at tag `v3.1.2`:

```go
// cmd/cosign/cli/options/verify.go  (v3.1.2, lines 41-43)
cmd.Flags().BoolVar(&o.Offline, "offline", false,
    "only verify an artifact's inclusion in a transparency log using a provided proof, rather than querying the log. May still include network requests to retrieve service keys from a TUF repository")
_ = cmd.Flags().MarkDeprecated("offline", "To verify in an airgapped environment, provide a --bundle with the signature and verification material, and a --trusted-root file with the service keys and certificates")
```

Three separate problems, all confirmed:

1. **The flag is deprecated.** `MarkDeprecated` is called on it in 3.1.2. It still parses, but it
   emits a deprecation warning and is on a removal path — inside an installer that will run on
   machines nobody can reach.
2. **Its meaning changed.** In v2.6.4 the help text is `"only allow offline verification"`. In
   v3.1.2 it is *"…**May still include network requests to retrieve service keys from a TUF
   repository**"*. The spine uses `--offline` as the air-gap guarantee. In cosign 3.x it is not one.
3. **It is gone from the generated documentation.** `doc/cosign_verify.md` at v3.1.2 lists 30
   flags and `--offline` is not among them; at v2.6.4 it is. Anyone reading the current manual
   would not find the flag the spine names.

**Upstream's own replacement**, quoted from the deprecation message: provide `--bundle` with the
signature and verification material, and a `--trusted-root` file with the service keys and
certificates. `--trusted-root` *is* in the v3.1.2 flag list. That is the supported air-gapped path
and neither document mentions it.

**What still works** (checked, so the fix is scoped): `cosign save`, `cosign load`, `--local-image`
and `--key` all exist at v3.1.2 and carry **no** deprecation marker. Only the verification flag is
affected.

**Primary sources**
- https://raw.githubusercontent.com/sigstore/cosign/v3.1.2/cmd/cosign/cli/options/verify.go
- https://raw.githubusercontent.com/sigstore/cosign/v3.1.2/doc/cosign_verify.md
- https://raw.githubusercontent.com/sigstore/cosign/v2.6.4/doc/cosign_verify.md (for the contrast)

**Why the lens caught it.** The research sourced this to a 2024-era blog post
(`some-natalie.dev/blog/cosign-disconnected/`) and cosign issue #3437 — both pre-v3. It then
paired that command with a v3.1.2 version number fetched separately. The version was
reality-checked; **the command was not**. That is exactly the training-data-shaped failure this
review exists to find: two individually-sourced facts fused into a claim that was never true
together.

**Recommendation.** Either pin cosign **2.6.4** (still maintained — released the same day as
3.1.2, 2026-07-17) and keep `--offline`, or move AD-30 to the `--bundle` + `--trusted-root` flow
on 3.1.2. Decide before `deploy/` is written; the installer's verification step is the one thing
that cannot be patched later.

---

## 3. High

### H1 — psycopg (LGPL-3.0-only) is a mandatory in-process dependency and the spine omits it entirely

**Severity: HIGH** (misleads a licence answer, which for this product is a commercial answer)

**The claim.** AD-28 exists to prevent *"a GPL or AGPL dependency contaminating a proprietary core
by a single `import`"*, and enumerates *"the permitted set for this increment"*. The Stack table
has 34 rows. psycopg is in neither.

**What I found.** Procrastinate 3.9.0's `requires_dist` includes **`psycopg[pool]`
unconditionally** — not an extra, not optional:

```
['asgiref', 'attrs', 'croniter', 'packaging', 'psycopg[pool]', 'python-dateutil', 'typing-extensions', ...]
```

And PyPI reports psycopg 3.3.4 (2026-05-01) with `license_expression: **LGPL-3.0-only**`.

So the one copyleft library that ships **in-process, imported directly into the core**, is the one
AD-28 does not name — while AD-28 goes to the trouble of putting `extract-msg` (GPL-3.0) behind a
subprocess boundary and excluding PyMuPDF (AGPL-3.0) outright.

**The evidence base told the spine this.** Research §8: *"psycopg 3 is LGPL-3.0-only. For a
proprietary on-prem product this is almost certainly fine — dynamic import of an unmodified
library — but §3 already committed to counsel review for extract-msg's GPL. **Put psycopg on the
same list.** It costs nothing to ask both questions in one email; it is expensive to discover the
answer late."* The distillation dropped it.

**Primary sources**
- https://pypi.org/pypi/procrastinate/3.9.0/json
- https://pypi.org/pypi/psycopg/json

**Note on substance:** LGPL dynamic linking of an unmodified library is very likely fine here. The
finding is not that the licence is fatal — it is that **AD-28 presents a complete licence position
that is not complete**, and a security questionnaire or a diligence process will find the gap.

### H2 — PyJWT 2.13.0 is itself the fix release for five CVEs, one HIGH — and the spine presents it as the clean choice

**Severity: HIGH** (misleads a security answer)

**The claim.** AD-15 rejects python-jose and Authlib by enumerating their CVE record, then adopts
*"PyJWT 2.13.0 … for **internal service tokens only**, never for user sessions."* No advisory
history is given for PyJWT, in the spine or in the research (§6 says only *"Narrow surface — sign,
verify, nothing else"*).

**What I found.** OSV lists **19 advisories** for PyJWT. **Five were fixed in exactly 2.13.0**,
published 2026-06-15 — six weeks before this spine was written:

| CVE | Severity | Summary | Fixed in |
| --- | --- | --- | --- |
| **CVE-2026-48526** | **HIGH** | Public-key JWK accepted as HMAC secret — enables **forged HS256 tokens** when mixed families are allowed | 2.13.0 |
| CVE-2026-48523 | MODERATE | **Algorithm allow-list bypass** when decoding with `PyJWK`/`PyJWKClient` | 2.13.0 |
| CVE-2026-48525 | MODERATE | Unauthenticated DoS via unbounded Base64URL decoding | 2.13.0 |
| CVE-2026-48522 | MODERATE | `PyJWKClient` missing scheme allowlist — SSRF + token disclosure | 2.13.0 |
| CVE-2026-48524 | LOW | `PyJWKClient` unbounded JWKS requests via attacker-controlled `kid` | 2.13.0 |
| CVE-2026-32597 | HIGH | PyJWT accepts unknown `crit` header extensions | 2.12.0 |

CVE-2026-48526 is **the same bug class** — algorithm confusion / HS256 forgery — that AD-15 cites
as the reason to reject python-jose and to avoid Authlib's JOSE surface. The adopted library had
it, patched six weeks ago, unmentioned.

**Compounding: the mitigation was dropped in distillation.** The research prescribed the concrete
defence — *"symmetric HS256, with `algorithms=["HS256"]` passed **explicitly** to `jwt.decode` —
never inferred from the header."* That single instruction is precisely what neutralises
CVE-2026-48526 and CVE-2026-48523. AD-15 does not carry it. The spine kept the library and lost
the rule that makes it safe.

**Primary sources**
- https://api.osv.dev/v1/query — `{"package":{"name":"pyjwt","ecosystem":"PyPI"}}`
- https://osv.dev/vulnerability/GHSA-xgmm-8j9v-c9wx (CVE-2026-48526)
- https://osv.dev/vulnerability/GHSA-jq35-7prp-9v3f (CVE-2026-48523)

**Note:** 2.13.0 is the correct version to adopt — it is the *patched* one. The finding is the
asymmetry: the rejection reasoning enumerates CVEs for what it rejects and is silent for what it
adopts, and the one compensating control was lost.

### H3 — The python-jose rejection cites a CVE patched 17 months ago

**Severity: HIGH** (a rejection reason stated as a live vulnerability; the kind of line that gets
quoted verbatim into a client security questionnaire)

**The claim.** AD-15 and the Stack exclusions: *"python-jose (**CVE-2024-33663 authentication
bypass**; three releases in five years)."*

**What I found.** NVD, verbatim: *"python-jose **through 3.3.0** has algorithm confusion with
OpenSSH ECDSA keys and other key formats."* OSV records it **fixed in 3.4.0** (2025-02-18). The
current release is **3.5.0** (2025-05-28). The cited vulnerability has not affected a current
python-jose install since February 2025.

The severity is also contested and the spine picks neither side: NVD's CVSS v3.1 vector is
`AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N` = **6.5 Medium**, while the GitHub Advisory
(GHSA-6c5p-j8vq-pqhj) labels it **Critical**. "Authentication bypass" is the GHSA framing.

**The maintenance half of the reason is true and current** — verified: repo not archived, last
push 2026-04-14, **115 open issues**, three releases in five years (3.3.0 2021-06-05, 3.4.0
2025-02-18, 3.5.0 2025-05-28).

**There is a better reason neither document found.** OSV records **CVE-2024-29370**
(PYSEC-2025-185, published 2025-12-17) against python-jose with **no fix version recorded** — an
open, unpatched advisory. That is the argument the spine should be making.

**Primary sources**
- https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-33663
- https://osv.dev/vulnerability/GHSA-6c5p-j8vq-pqhj
- https://api.github.com/repos/mpdavis/python-jose

**Verdict: right outcome, wrong reason.** Keep the rejection; restate it on maintenance and the
unfixed CVE-2024-29370, not on a bug that was fixed before the previous build started.

### H4 — "Starlette moved only in lockstep" is not what FastAPI's packaging does

**Severity: HIGH** (could break a rebuild of the one artefact AD-3 says is built once)

**The claim.** Stack row 2: *"FastAPI | 0.139.2 | HTTP surface; **Starlette moved only in
lockstep**."* Derived from research §8: *"Starlette reached 1.0 in May 2026 and **FastAPI pins it
in a narrow range.**"*

**What I found.** FastAPI 0.139.2's actual `requires_dist`:

```
starlette>=0.46.0
pydantic>=2.9.0
```

An **open lower bound with no upper bound**, spanning the `0.46 → 1.x` major-version boundary.
There is no narrow range and no lockstep. A rebuild of the offline bundle resolved from
`pyproject.toml` alone would silently pull Starlette 1.3.1 — or whatever ships next — across a
major version, and Pydantic likewise.

This matters more here than in a normal project. AD-3 says exactly one artefact is built and every
installation runs it; AD-30 says everything is pinned by digest. The lockfile is therefore
**load-bearing**, and the spine has reworded a *discipline you must impose* into a *property the
dependency graph already has*. It does not.

**Compounding:** the spine names **no Starlette version at all**, so nothing in the architecture
document pins the library it says moves in lockstep. The research had 1.3.1 (2026-06-12); the
distillation dropped the number and kept the (incorrect) reassurance.

**Primary source:** https://pypi.org/pypi/fastapi/0.139.2/json

---

## 4. Medium

### M1 — pdfplumber 0.11.7 is three releases and thirteen months stale

**Claim:** Stack row 19 and AD-28's permitted set: `pdfplumber` **0.11.7**.
**Found:** PyPI's current release is **0.11.10 (2026-06-15)**. 0.11.7 dates from **2025-06-12**.
Intervening: 0.11.8 (2025-11-08), 0.11.9 (2026-01-05), 0.11.10 (2026-06-15).

This is the **one row in the whole stack that is not current**, and the reason is visible in the
research: §3's pdfplumber row is sourced to a **blog benchmark** (`pdfmux.com/blog/pymupdf-vs-
pdfplumber/`), not to the PyPI release history that every other row in that section cites. The
version was copied out of a secondary article and was already stale on the day it was written.

The spine's Stack header says *"Seed — **verified 2026-07-21** against `05-stack-research-2026-07.md`"*.
It was verified against the research; the research was not verified against the registry here.

**Severity: medium** — 0.11.7 exists and installs, so no build break. But it is the exact failure
mode the lens describes, and the honest correction is one character.
**Source:** https://pypi.org/pypi/pdfplumber/json

### M2 — "Mistral Small 3.2 24B" is a superseded generation of a renamed line, and the current 24 GB-class Mistral was in the evidence and never compared

**Claim:** AD-27 and Stack row 15 — *"Mistral Small 3.2 24B (Apache-2.0) … Default judgement model."*

**Found:** `mistralai/Mistral-Small-3.2-24B-Instruct-2506` exists and is **apache-2.0** ✅ — the
licence claim is correct. But it was released June 2025 (`2506`) and last modified 2025-12-22.
Meanwhile, on Mistral's own Hugging Face org:

- **`mistralai/Mistral-Small-4-119B-2603`** — Apache-2.0, created 2026-01-23. The **"Mistral
  Small" product name now denotes a 119B model**, which does not fit 24 GB. A reader in 2026 who
  looks up "Mistral Small" will not find what the spine means.
- **`mistralai/Ministral-3-14B-Instruct-2512`** — Apache-2.0, created 2025-10-31, with 8B and 3B
  siblings in Instruct and Reasoning variants. This is Mistral's **current model line built for
  this hardware class**.

The research's §5 table **names Ministral 3** — *"Released 2025-12-02 … 40+ languages natively;
built for edge/consumer hardware"* — and then Recommendation 5 never compares it against Mistral
Small 3.2. The spine inherits the unrun comparison and commits the older model as the default.

**Severity: medium** — nothing breaks, the model is real and permissively licensed. But AD-27
commits the default judgement model and the hardware story on a comparison its own evidence set up
and did not perform.
**Sources:** https://huggingface.co/api/models/mistralai/Ministral-3-14B-Instruct-2512 ·
https://huggingface.co/api/models/mistralai/Mistral-Small-4-119B-2603 ·
https://huggingface.co/api/models/mistralai/Mistral-Small-3.2-24B-Instruct-2506

### M3 — "INT8/Q4 on 24 GB VRAM" — the INT8 half does not fit the box

**Claim:** AD-27: *"Mistral Small 3.2 24B (Apache-2.0) at **INT8/Q4 on 24 GB VRAM**, 100 000
*pièces* overnight."* Stack row 15 repeats it.

**Found, from the research's own numbers:** its §5 model table gives **Q4_K_M ≈ 14 GB** for this
model. The CCBE quantisation table it quotes (Table 2) gives **INT8 ≈ 0.5× the FP16 footprint**.
FP16 for a 24B model ≈ 48 GB, so **INT8 ≈ 24 GB of weights alone** — before KV cache, activations
and the CUDA context, on a card with 24 GB total. Only the **Q4** path fits the CCBE €2 000
machine. The research wrote "INT8/Q4 on a single 24 GB GPU" in Recommendation 5 and the spine
copied it verbatim.

**Severity: medium** — this is the €2 000-machine commercial claim, and AD-27 says the expected
wall-clock is *"stated honestly to the firm before the job starts"*. Half of the stated
configuration cannot run on the stated hardware. Drop "INT8/" or move the INT8 option to the
RTX Pro 6000 tier where the research already places it.

### M4 — `pgvector ≥ 0.8.5` is the only unbounded version in a bundle AD-30 says is "everything pinned by digest"

**Claim:** Stack row 9 and AD-5: *"pgvector **≥ 0.8.5**"*.
**Found:** 0.8.5 (2026-07-08) is the current tag, and the floor is correctly placed — I verified
**CVE-2026-3172** (pgvector buffer overflow in parallel HNSW index build) against NVD: it affects
**0.6.0 through 0.8.1**, CVSS v3.1 `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:H`, published 2026-02-25,
fixed in 0.8.2. So `≥ 0.8.5` is safely above it and the security reasoning holds.

The issue is internal consistency: `≥` is an open upper bound, and AD-30 in the same document says
*"everything pinned by digest"*. Also worth noting that 0.8.3 and 0.8.4 both fixed **HNSW vacuum
correctness** bugs (`possible index corruption with HNSW vacuuming`; `hnsw graph not repaired`) —
which is a real argument for `== 0.8.5` rather than `≥`, on an index nobody can inspect remotely.

**Severity: medium** (consistency, not a fact error).
**Sources:** https://raw.githubusercontent.com/pgvector/pgvector/master/CHANGELOG.md ·
https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-3172 ·
`pgvector/pgvector:0.8.5-pg18` image confirmed on Docker Hub, updated 2026-07-08.

### M5 — Docling's offline-artifact hazard, the research's loudest operational warning, does not survive into the spine

**Claim:** AD-28 lists *"Docling 2.114.0 with Tesseract 5.5.2 for scanned PDF and layout-heavy
documents"* and nothing else about it.

**Found:** Docling 2.114.0 (2026-07-20), MIT, repo pushed 2026-07-21, 63.5k stars — healthy and
current ✅. But the research devoted a full block to the thing that actually breaks:
`docling-tools models download` pre-fetching into `$HOME/.cache/docling/models`; `artifacts_path`
in pipeline options; the serve env var being `DOCLING_SERVE_ARTIFACTS_PATH` and **not**
`DOCLING_ARTIFACTS_PATH`; and a documented trail of offline bugs (issue #232, issue #2555 —
v2.60.0 ignoring the artifacts path in Docker and looking in `/tmp`). Plus **~9 releases per
month**, so *"an upgrade can silently reintroduce a network fetch."*

The spine carries none of it, and names none of the build-time variables the research required in
the image: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1`.

**Partial mitigation, and it is the right shape:** AD-2 mandates a network-isolated CI job that
boots the whole application and ingests. That structurally catches a runtime network reach. But
AD-2 does not require the *image* to be built with the offline variables set — so a run with a
warm `$HOME/.cache/docling` passes CI and fails at the firm.

**Severity: medium.** One sentence in AD-2 ("the image is built with model artefacts vendored and
`HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` set, and the isolated run starts from a cold cache")
closes it.

### M6 — The Authlib rejection is accurate on the CVE, imprecise on the date and on the present state

**Claim:** AD-15 and Open Risk 2: *"Authlib (twelve advisories including **CVE-2026-27962, CVSS
9.1** signature-verification bypass patched only in **1.6.9 on 2026-03-15**)."*

**Verified true:** CVE-2026-27962 = *"Authlib JWS JWK Header Injection: Signature Verification
Bypass"*, CVSS v3.1 vector `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N` = **9.1** ✅, **CRITICAL** in the
GitHub Advisory Database ✅, **fixed in 1.6.9** ✅. OSV returns 24 advisory records for Authlib —
PYSEC and GHSA duplicates of roughly twelve distinct CVEs — so *"twelve advisories"* is consistent
with the GitHub Advisory Database count ✅. **This is a well-checked rejection.**

Two imprecisions:
- **Date:** the advisory was published **2026-03-16**, not 03-15 (GHSA-wvwj-cvrp-7pv5). Trivial.
- **Present state:** current Authlib is **1.7.2 (2026-05-06)**, and *every* CVE in the research's
  table is patched in it (the two most recent, CVE-2026-41479 and CVE-2026-44681, in 1.7.1). The
  spine's phrasing reads as a present-tense condemnation of the library. The real argument — which
  the research made explicitly and the spine compressed away — is **patch latency on a machine
  nobody can reach**: *"Under C1 there is no air-gapped machine that will pick up a 1.6.9 patch on
  the day it ships."* That argument is stronger and survives Authlib being currently clean.

I also resolved one item the research left open: **CVE-2026-28490** (JWE RSA1_5 Bleichenbacher
padding oracle), marked *"patched version unverified"* in the research, is **fixed in 1.6.9**.
And **CVE-2026-28802** — which the research describes as *"`alg: none` with blank signature passes
verification, affected 1.6.5–1.6.6, patched 1.6.7"* — checks out against NVD: *"From version 1.6.5
to before version 1.6.7…"*, published 2026-03-06 (the research said "Feb 2026").

**Severity: medium.**
**Sources:** https://osv.dev/vulnerability/GHSA-wvwj-cvrp-7pv5 ·
https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-28802 · https://pypi.org/pypi/authlib/json

### M7 — The FastAPI-Users rejection is correct; the CVE the research paired with it is described wrongly

**Claim:** AD-15 and Stack exclusions: *"FastAPI-Users (maintenance mode since 15.0.1)."*

**Verified true, from the project's own words.** The v15.0.1 release notes (2025-10-25) read:
*"**FastAPI Users is now in maintenance mode.** While we'll continue to provide security updates
and dependency maintenance, no new features will be added."* The README carries the same banner
plus *"We're currently working on a new Python authentication toolkit that will ultimately
supersede FastAPI Users."* ✅ The version and date in the spine are both exactly right.

Worth noting for fairness: the repo is **not dead** — last push 2026-07-20, latest release 15.0.5
(2026-03-27), MIT. "Maintenance mode" is the accurate characterisation and the spine uses it
correctly, rather than overclaiming abandonment.

**The research's supporting detail is wrong**, though the spine did not repeat it: research §6
says *"v15.0.2 (2025-12-19) shipped a **CSRF fix in the OAuth2 authorize flow**."* The actual
advisory is **CVE-2025-68481 / GHSA-5j53-63w8-8625**, *"FastAPI Users Vulnerable to **1-click
Account Takeover** in Apps Using FastAPI SSO"*, MODERATE, fixed in 15.0.2. Different bug, more
serious than described.

**Severity: medium** (research-level; spine unaffected).
**Sources:** https://api.github.com/repos/fastapi-users/fastapi-users/releases/tags/v15.0.1 ·
https://raw.githubusercontent.com/fastapi-users/fastapi-users/master/README.md ·
https://osv.dev/vulnerability/GHSA-5j53-63w8-8625

### M8 — PostgreSQL **18.4** is real and current, but its availability on the managed dev tier is asserted in both documents and checked in neither

**The version is verified and I was wrong to doubt it.** The PostgreSQL announcement
*"PostgreSQL 18.4, 17.10, 16.14, 15.18, and 14.23 Released!"* is dated **2026-05-14**, fixes
**11 security vulnerabilities and over 60 bugs**, and 18.4 is the newest 18.x on the source FTP
tree (v18.0–v18.4 present; no v18.5). PG19 Beta 2 (2026-07-16) confirmed on the project homepage.
The spine's *"PostgreSQL 19 is at Beta 2 and must not ship into a firm"* is exactly right.

**The gap.** AD-3 makes managed-dev-tier availability a *build-gating* property — it is the stated
reason pgvectorscale and ParadeDB are excluded. The deployment diagram commits
*"Managed PostgreSQL **18.4** + pgvector"* on the hosted tier. The research verified managed-tier
parity **for the pgvector extension** (*"present on Supabase, Neon, RDS/Aurora, Railway"*) and
**never for the PostgreSQL major version**. Grepping the research for `supabase|neon|railway|managed`
returns 11 hits, all about extensions.

So the one environment-availability fact that AD-3 turns into a rejection criterion for other
components is unverified for the component AD-5 makes mandatory.

**Severity: medium** — a 30-second check before the store is built, and a genuine schedule risk if
the hosted tier is on PG 17.
**Sources:** https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/ ·
https://www.postgresql.org/ftp/source/ · https://www.postgresql.org/

### M9 — Ollama is not pinned the way vLLM is, and a newer build already exists

**Claim:** AD-27 — *"vLLM 0.25.1 **pinned by digest**, … Ollama 0.32.1"*. The digest-pinning
qualifier attaches to vLLM only, in both the AD and the Stack table.

**Found:** v0.32.1 (2026-07-16) is the current stable ✅, MIT ✅ — but **v0.32.2-rc0 was published
2026-07-20**, the day before the spine, and Ollama's cadence is the same weekly pre-1.0 cadence
that the research says makes digest-pinning mandatory: *"**Both projects ship weekly and both are
pre-1.0.** Every release has changed scheduling, KV-cache handling or backend kernels. For an
air-gapped install this means **pin the exact image digest and never auto-update**."* The research
applied the rule to both engines; the spine applied it to one.

**Severity: medium.** AD-30's *"everything pinned by digest"* arguably covers it, but AD-27 singles
vLLM out, which reads as a distinction where the evidence draws none.
**Source:** https://api.github.com/repos/ollama/ollama/releases

### M10 — Two "quiet, finished library" rows rest on assertion — and both check out

Recording these because the lens asks about projects that may be dead:

- **openpyxl 3.1.5 (2024-06-28)** — 25 months with no PyPI release, and the research asserted
  *"reflects a finished library, not an abandoned one"* **with no source**. I checked: upstream at
  `foss.heptapod.net/openpyxl/openpyxl` shows `last_activity_at` **2026-07-21** (today) and is not
  archived. The assertion was right; it is now evidenced.
- **python-docx 1.2.0 (2025-06-16)** — current latest, MIT ✅.
- **Tesseract 5.5.2 (2025-12-26)** — current latest, Apache-2.0, repo pushed 2026-07-21 ✅.
- **argon2-cffi 25.1.0**, **pwdlib 0.3.0**, **py_webauthn 3.0.0** — all current, and **all three
  have zero advisories in OSV** ✅. `duo-labs/py_webauthn` is not archived (1053★, pushed
  2026-06-29), which directly answers the "still exists and is alive" question for the one
  security library with the smallest community.

**Severity: informational.** No action.

---

## 5. Fitness for the constraint set, independent of version

The constraint: *runs unmodified on one machine inside a law firm with no internet, and also on a
hosted dev tier, from one artefact.*

| Component | Fitness | Note |
| --- | --- | --- |
| PostgreSQL 18.4 + pgvector | ✅ strong | `pgvector/pgvector:0.8.5-pg18` image confirmed on Docker Hub (2026-07-08) — arrives as an image layer, zero install steps. Major-version managed-tier availability unchecked (**M8**). |
| Procrastinate | ✅ strong | Same database, no Redis. The queue/ledger-in-one-transaction argument is sound and is the strongest single decision in the spine. |
| Docling | ⚠️ | Offline artefacts are the known failure mode and the spine dropped the mitigations (**M5**). |
| extract-msg | ✅ | GPL-3.0 confirmed; out-of-process boundary is the correct and conventional mitigation. |
| Tesseract | ✅ | CPU-only, static `tessdata`, no network, no models to fetch. The cleanest offline story in the stack. |
| BGE-M3 | ✅ | MIT, 1.4 GB, bakes into the image. Spine correctly records the 2024-generation risk. |
| vLLM / Ollama | ⚠️ | Two profiles behind one OpenAI-compatible interface is right. But **AD-3 says one artefact, three environments** while the GPU profile needs NVIDIA/AMD plumbing that the CPU profile and the hosted tier must not require. That is a Compose-level concern the spine does not address, and the research warned *"if the firm's machine has no suitable GPU, vLLM is not merely slower — it may not run at all."* |
| py_webauthn | ✅ | Secure-context constraint (FQDN + certificate, LAN IP blocked by spec) is carried into AD-15 correctly and completely. Good distillation. |
| cosign | ❌ | **C1.** The verification flag does not do what the spine says on the version the spine names. |
| Vite + React Router | ✅ strong | Deleting the Node runtime from the shipped bundle is the correct call and removes an entire CVE stream from an unpatchable machine. Both versions current. |
| psycopg | ⚠️ | **H1.** In-process LGPL, unnamed. |

---

## 6. Rejections — verified one by one

| Rejected | Spine's stated reason | Verified? |
| --- | --- | --- |
| **PyMuPDF** | AGPL-3.0, unusable without a commercial licence | ✅ **True.** PyPI 1.28.0 (2026-06-29), licence field: *"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex commercial"*. Note the spine's "1.26.1" era is superseded, but the reason is unchanged. |
| **FastAPI-Users** | Maintenance mode since 15.0.1 | ✅ **True and current**, in the project's own words (**M7**). |
| **python-jose** | CVE-2024-33663 authentication bypass | ❌ **Stale.** Patched in 3.4.0, seventeen months ago (**H3**). Maintenance half of the reason is true. |
| **passlib** | Unmaintained since 2020 | ✅ **True.** Last release **1.7.4, 2020-10-08** — 5 years 9 months. Zero advisories, so it is stale rather than vulnerable, which is what the spine says. |
| **Authlib** | 12 advisories, CVE-2026-27962 CVSS 9.1 | ✅ **True**, CVE and score both confirmed; date off by one day and present state overstated (**M6**). |
| **pgvectorscale / ParadeDB** | Unavailable on the managed dev tier | ⚠️ Sourced in the research to a comparison blog + a third-party extension index, not to Supabase's or AWS's own documentation. The conclusion is very likely right; the sourcing is the weakest in §1, and it is load-bearing for AD-3 and Open Risk 1. |
| **Qdrant / LanceDB / Milvus / Weaviate / Chroma / Redis** | Second stateful service (AD-5) | ✅ Reasoning is architectural, not factual, and holds. Research verified Qdrant 1.18.3 and LanceDB 0.34.0 as alive — they are rejected on shape, not on health, which is the honest framing. |
| **SQLite + sqlite-vec** | Abandons PostgreSQL | ✅ Architectural, holds. |
| **Next.js** | Node runtime + patch debt + caching liability | ✅ **True and well-argued.** Research verified Next 16.2.11 / 15.5.21 both shipping security releases on 2026-07-21 itself — the strongest possible evidence for the patch-debt argument. Spine correctly records *"Next.js does work offline, so this is not a functionality argument."* |

**No wrongly-rejected healthy library found** — the only defective rejection is **python-jose**,
where the outcome is right and the stated reason is out of date.

---

## 7. Summary of findings by severity

| ID | Severity | Finding |
| --- | --- | --- |
| **C1** | **CRITICAL** | `cosign --offline` is deprecated in 3.1.2 and may still make network calls; AD-30's install gate names it. |
| **H1** | HIGH | psycopg (LGPL-3.0-only) is a hard Procrastinate dependency, absent from the spine; the research told it to include it. |
| **H2** | HIGH | PyJWT 2.13.0 is the fix release for 5 CVEs incl. a HIGH HS256-forgery; presented as clean, and the `algorithms=["HS256"]` mitigation was dropped. |
| **H3** | HIGH | python-jose rejected on CVE-2024-33663, patched in 3.4.0 seventeen months ago. |
| **H4** | HIGH | "Starlette moved only in lockstep" is false — FastAPI 0.139.2 pins `starlette>=0.46.0`, unbounded; and no Starlette version is committed anywhere. |
| **M1** | MEDIUM | pdfplumber 0.11.7 → current is 0.11.10; the only stale version, sourced from a blog not the registry. |
| **M2** | MEDIUM | Mistral Small 3.2 24B is a superseded generation; Ministral 3 14B was in the evidence and never compared. |
| **M3** | MEDIUM | "INT8/Q4 on 24 GB VRAM" — INT8 for a 24B model is ~24 GB of weights alone. |
| **M4** | MEDIUM | `pgvector ≥ 0.8.5` unbounded, against AD-30's digest pinning; 0.8.3/0.8.4 were HNSW corruption fixes. |
| **M5** | MEDIUM | Docling's offline-artifact hazard and the four telemetry/offline env vars dropped from the spine. |
| **M6** | MEDIUM | Authlib: CVE and CVSS correct; date off by one day, present state overstated, patch-latency argument compressed away. |
| **M7** | MEDIUM | FastAPI-Users rejection correct; research misdescribes CVE-2025-68481 as a CSRF fix (it is 1-click account takeover). |
| **M8** | MEDIUM | PostgreSQL **18** availability on the managed dev tier never checked, though AD-3 makes that a rejection criterion for others. |
| **M9** | MEDIUM | Ollama not digest-pinned in AD-27 although the research applies the rule to both engines; v0.32.2-rc0 already out. |
| **M10** | INFO | openpyxl / python-docx / Tesseract / argon2-cffi / pwdlib / py_webauthn all verified alive and advisory-free. |

---

## 8. What this review says about the process

Two things are worth separating.

**The version discipline is real.** 31 of 34 exact matches against live registries, every licence
claim correct, every model repository existing with the stated licence, PostgreSQL's minor-release
cadence tracked correctly, alpha and beta releases explicitly excluded. Most architecture
documents that name three dozen versions have several that do not exist. This one has zero
fabrications. The research document is doing real work.

**The distillation is where the losses are.** Every high-severity finding is the same shape: a
fact that was in the research and did not survive into the spine (psycopg's licence, the
`algorithms=["HS256"]` rule), or a qualified statement that hardened into an unqualified one on
the way across (FastAPI's dependency range becoming "lockstep", a patched CVE becoming a live
rejection reason, "patch latency on an unreachable machine" becoming "twelve advisories"). The
spine is in several places **more confident than its evidence**, which is precisely what the lens
asks about.

And the one critical finding is neither of those. It is the failure mode the lens exists for: a
correct, freshly-fetched **version number** (cosign 3.1.2) welded to a **command line** taken from
a 2024 blog post, producing a claim that was never true of the two together. Version-checking a
tool is not the same as reality-checking the way you use it.
