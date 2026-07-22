# PostgreSQL Managed-Tier Availability Check — "One Artefact, Three Environments"

**Date of check:** 2026-07-22
**Method:** Primary-source verification (provider docs/changelogs, postgresql.org, Docker Hub,
GitHub, plus a **live query against a real Supabase project** via the Supabase management API).
**Status:** COMPLETE.

---

## The claim under test

The APX architecture assumes it can run **PostgreSQL 18.4 with the pgvector extension** as the
*sole stateful service*, identically across three environments — "from one artefact":

1. a **hosted development tier** (Supabase + Vercel + Railway), and
2. an **air-gapped on-premise install**.

This assumption was used to **reject two alternatives** — `pgvectorscale`/StreamingDiskANN
(Timescale) and ParadeDB's BM25 (`pg_search`) — on the grounds that they are *not available on
the managed dev tier*. The logical trap being tested: **if PostgreSQL 18 + pgvector is itself not
available on that tier, the rejection reasoning is inconsistent** and the "one artefact, three
environments" claim is undermined.

---

## TL;DR verdict

**(b) SOUND WITH A NAMED CAVEAT.** The *functional* assumption holds; the *literal wording*
("PostgreSQL 18.4 … identically … one artefact") does not, because the Supabase managed tier is
on **Postgres 17**, not 18, and you cannot ship your own Postgres image to it. But nothing breaks:
Supabase's pgvector (0.8.0) provides **halfvec + HNSW**, satisfying every real requirement, and the
two rejected extensions are genuinely **absent** from Supabase — so the rejection logic is
*consistent*, not broken. Full four-line verdict at the bottom.

---

## 1. Supabase — Postgres major version & pgvector

### Ground truth (live query, not just docs)
A **real Supabase project owned by this account** was inspected via the Supabase management API
on 2026-07-22:

| Field | Value |
|---|---|
| Project | `mip-rum-poc` (region `eu-west-3`) |
| Created | **2026-06-10** |
| Postgres version | **`17.6.1.127`** |
| Engine | **`17`** |
| Release channel | **`ga`** |

A `pg_available_extensions` query on that same project returned:

| Extension | default_version | installed_version |
|---|---|---|
| `vector` (pgvector) | **`0.8.0`** | (null — available, enable with `CREATE EXTENSION`) |
| `vectorscale` | **not present** | — |
| `pg_search` (ParadeDB BM25) | **not present** | — |

**Interpretation:**
- **Postgres 18 is NOT available for new Supabase projects.** A project created 2026-06-10 is on
  **Postgres 17 (17.6), GA channel.** 17 is the newest major Supabase offers.
- **pgvector shipped: 0.8.0.** Because `halfvec` landed in pgvector **0.7.0** and **HNSW** in
  **0.5.0** (see §3), Supabase's 0.8.0 **supports both `halfvec` and HNSW indexes**, including
  `halfvec` HNSW indexes. Every vector requirement the architecture needs is met **on Postgres 17.**
- **The two rejected extensions are genuinely absent** from Supabase's extension catalogue — this
  *directly corroborates* the architecture's stated reason for rejecting them.

### Roadmap / timeline for Postgres 18 on Supabase
- Supabase's public changelog announcing the current major: **"The upcoming release of Supabase
  Platform will use Postgres 17"** — posted **2025-05-22**. No later changelog entry announces 18
  for new projects. (Source: Supabase Changelog.)
- GitHub discussion **supabase/discussions #42681** ("Support postgres 18?"): the original rough
  target was **January 2026**; that date passed. A Supabase maintainer (`aantti`) commented
  **2026-05-04**: *"For CLI & self-hosted we have to wait for the Postgres team to work on Pg 18 and
  add it to the platform first … it's not very soon, but eventually in 2026."*
- **Net:** as of 2026-07-22, Supabase = **Postgres 17 GA, no 18** (not GA, not a selectable preview);
  18 is roadmapped for "eventually in 2026" with no committed date.

**Sources:** Supabase management API (live project, 2026-07-22); Supabase Changelog
https://supabase.com/changelog (entry 2025-05-22); GitHub discussion
https://github.com/orgs/supabase/discussions/42681 (maintainer comment 2026-05-04).

---

## 2. Railway — official `postgres:18` image + pgvector

Railway does **not** run a managed Postgres control plane that pins the major version — it deploys
**Docker images/templates**, so you bring the image (and therefore the major version) you want.

- **You can run PG18 + pgvector on Railway today.** One-click template **`pgvector-pg18`** deploys
  the **official `pgvector/pgvector:pg18` image**; its description is literally *"like the existing
  pgvector template, but with PostgreSQL v18 instead of PostgreSQL v16."* A second template
  **`pgvector-18-trixie`** also exists. (Source: https://railway.com/deploy/pgvector-pg18.)
- Railway's own default "PostgreSQL" one-click uses the `postgres-ssl` image ("based on the official
  Postgres image from Docker Hub"); pgvector is offered as a marketplace template. There is **no
  managed constraint pinning the major version** — the tag you deploy is the version you get.
  (Source: https://docs.railway.com/databases/postgresql.)

**Conclusion:** Railway can run **PostgreSQL 18 + pgvector** identically to the on-prem artefact
(same `pgvector/pgvector:pg18` image). Railway is **not** the weak link.

**Sources:** https://railway.com/deploy/pgvector-pg18 ; https://docs.railway.com/databases/postgresql
(fetched 2026-07-22).

---

## 3. Official `pgvector/pgvector` Docker image — PG18 tags

The air-gapped install would ship the community **`pgvector/pgvector`** image (Docker Hub), which
bundles Postgres + pgvector. **PG18 tags exist and are current.**

- **Current pgvector version: `0.8.5`** (released **2026-07-08**).
- **PG18 tags available:** `pg18`, `0.8.5-pg18`, `pg18-trixie`, `0.8.5-pg18-trixie`,
  `pg18-bookworm`, `0.8.5-pg18-bookworm`. (Older `0.8.1-pg18` layers also exist.) A Docker
  **Hardened Image** variant (`pgvector/debian-13/0.8-pg18`) is additionally published — relevant
  if the on-prem posture wants a minimal/CVE-scanned base.
- **Feature history (from the pgvector CHANGELOG):** **HNSW added in 0.5.0 (2023-08-28)**;
  **`halfvec` type added in 0.7.0 (2024-04-29)** (which also added `halfvec` HNSW/IVFFlat index
  support). So any pgvector **≥ 0.7.0** satisfies pgvector + halfvec + HNSW; both Supabase's 0.8.0
  and the shippable 0.8.5-pg18 clear that bar.

**Conclusion:** the on-prem artefact `pgvector/pgvector:pg18` (PG18 + pgvector 0.8.5) **exists,
is official, and is current.** This half of the claim is fully sound.

**Sources:** Docker Hub https://hub.docker.com/r/pgvector/pgvector (tags, fetched 2026-07-22);
pgvector CHANGELOG https://raw.githubusercontent.com/pgvector/pgvector/master/CHANGELOG.md
(0.5.0 2023-08-28, 0.7.0 2024-04-29, 0.8.5 2026-07-08).

---

## 4. Reconciliation — is the assumption sound as written?

**Sound as *intent*, wrong as *literal wording* — and, crucially, the rejection logic is
internally consistent.**

1. **The literal "PostgreSQL 18.4, identically, from one artefact across all three" is false for
   Supabase.** Supabase is a **managed control plane**: you never ship it your Postgres image, and
   it currently only offers **major 17**. So on-prem (PG18.4) and Railway (PG18 via image) can be
   byte-identical, but **Supabase cannot** — it is one major behind, by provider policy, not by your
   choice.

2. **But the architecture does not actually depend on 18-specific behaviour.** The real
   requirements are **pgvector + `halfvec` + HNSW**. All three are present on Supabase's **PG17 +
   pgvector 0.8.0**. So the **17-vs-18 gap is a non-issue for development**: the dev tier meets every
   functional need, while the on-prem artefact still ships 18.4. A provider offering a version
   **≥ what pgvector+halfvec+HNSW needs** makes the assumption hold **even though the major number
   differs** — and Supabase clears that bar.

3. **The rejection reasoning is NOT inconsistent.** The feared contradiction ("you rejected X for not
   being on the tier, but your own choice isn't on the tier either") **does not occur**, because
   pgvector **is** on the Supabase tier (on 17) while `vectorscale` and `pg_search` **are provably
   not** (confirmed by the live `pg_available_extensions` query in §1). "Keep the extension the
   managed tier has, drop the two it doesn't" is a **consistent** rule. What was imprecise was
   pinning it to *"Postgres 18.4"* rather than to *"pgvector ≥ 0.8 with halfvec + HNSW, on whatever
   major the tier offers."*

4. **Correct framing:** it is **"one *extension/schema contract*, three environments,"** not "one
   *binary artefact*, three environments." On-prem and Railway share the artefact
   (`pgvector/pgvector:pg18`); Supabase shares the **contract** (pgvector 0.8.0 / halfvec / HNSW on
   PG17). The only residual risk is **major-version parity** (17 dev vs 18 prod) — a real but
   ordinary CI concern (e.g. a query relying on an 18-only planner behaviour or an 18-only SQL
   feature would pass on-prem and fail on Supabase). Mitigation: test against **both** majors, and
   keep the schema/queries to features common to 17 and 18.

**Which providers/configs work:**
- **On-prem (air-gapped):** PG18.4 + `pgvector/pgvector:pg18` (0.8.5). Works, exact.
- **Railway:** PG18 + pgvector via `pgvector-pg18` template. Works, exact match to on-prem.
- **Supabase:** PG**17** + pgvector 0.8.0 (halfvec + HNSW). Works functionally; **not** major-18.
- **Provider genuinely stuck on an older major:** **Supabase (17).** Consequence: you get extension
  parity but not engine parity; pin the contract to the extension, add 17-vs-18 CI, revisit when
  Supabase ships 18.

---

## 5. Caveat check — PG18 stable line vs PG19 beta

- **PostgreSQL 18.4** is the **latest stable release in the 18.x line**, posted **2026-05-14**. There
  is **no 18.5 or newer** stable release yet (confirmed against the postgresql.org release-notes
  index — 18.x tops out at 18.4). So the architecture's "18.4" is current and has **not** moved on.
- **PostgreSQL 19 is in beta:** **19 Beta 2 released 2026-07-16** (feature-freeze; GA expected
  ~Sept/Oct 2026). It must **not** ship into a firm/production — the stack-research caveat is
  **confirmed**. 18.x is the current stable line to build on.

**Sources:** https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/
(18.4, posted 2026-05-14); https://www.postgresql.org/docs/release/ (18.4 = newest 18.x);
https://www.postgresql.org/about/news/postgresql-19-beta-2-released-3350/ (19 Beta 2, 2026-07-16).

---

## VERDICT (4 lines)

1. **(b) Sound with a named caveat** — the *functional* "one pgvector contract, three environments"
   assumption holds; the *literal* "PostgreSQL 18.4 identically from one artefact" does not.
2. **Named caveat:** the **Supabase** managed tier runs **Postgres 17 (GA), not 18**, and you cannot
   bring your own image — so dev (17) and the on-prem artefact (18.4) differ by one **major**, though
   Railway and on-prem can be image-identical (`pgvector/pgvector:pg18`).
3. **Nothing breaks:** Supabase's pgvector **0.8.0 provides `halfvec` + HNSW**, meeting every
   requirement; and the rejection of `pgvectorscale`/ParadeDB is **consistent** — both are *provably
   absent* from Supabase (live-verified), while pgvector is present.
4. **Record in open questions:** pin the invariant to **"pgvector ≥ 0.8 with halfvec + HNSW, on the
   newest major the tier offers"** (NOT "PG 18.4"); add **PG17-vs-18 parity to CI**; on-prem ships
   18.4 + pgvector 0.8.5; **re-evaluate when Supabase ships Postgres 18** (roadmapped "eventually in
   2026", no committed date as of 2026-07-22).

---

## Source list (with dates)

| # | Source | URL | Date / accessed |
|---|---|---|---|
| S1 | Supabase management API — live project `mip-rum-poc` (PG 17.6.1.127, engine 17, GA; pgvector default 0.8.0; no vectorscale/pg_search) | (authenticated API) | queried 2026-07-22 |
| S2 | Supabase Changelog — "upcoming release will use Postgres 17" | https://supabase.com/changelog | posted 2025-05-22 |
| S3 | GitHub — supabase discussion #42681 "Support postgres 18?" (maintainer: 18 "eventually in 2026") | https://github.com/orgs/supabase/discussions/42681 | comment 2026-05-04 |
| S4 | Railway template — pgvector-pg18 (`pgvector/pgvector:pg18`) | https://railway.com/deploy/pgvector-pg18 | accessed 2026-07-22 |
| S5 | Railway Docs — PostgreSQL (image-based, no major pin) | https://docs.railway.com/databases/postgresql | accessed 2026-07-22 |
| S6 | Docker Hub — pgvector/pgvector (pg18 tags, 0.8.5) | https://hub.docker.com/r/pgvector/pgvector | accessed 2026-07-22 |
| S7 | pgvector CHANGELOG (HNSW 0.5.0 / halfvec 0.7.0 / 0.8.5 2026-07-08) | https://raw.githubusercontent.com/pgvector/pgvector/master/CHANGELOG.md | accessed 2026-07-22 |
| S8 | PostgreSQL news — 18.4 released | https://www.postgresql.org/about/news/postgresql-184-1710-1614-1518-and-1423-released-3297/ | posted 2026-05-14 |
| S9 | PostgreSQL release-notes index (18.4 = newest 18.x) | https://www.postgresql.org/docs/release/ | accessed 2026-07-22 |
| S10 | PostgreSQL news — 19 Beta 2 released | https://www.postgresql.org/about/news/postgresql-19-beta-2-released-3350/ | posted 2026-07-16 |
