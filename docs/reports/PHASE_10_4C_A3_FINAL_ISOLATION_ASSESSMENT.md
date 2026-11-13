# Phase 10.4C-A3 — Final isolation evidence and source risk assessment

Documentation-only assessment. Time: **13 Nov 2026, 10:48 Asia/Jakarta
(WIB)**. No application-code change. No Blueprint, env, deploy,
migrate, cleanup execution, object write, Production probe, Staging
functional smoke, or Stage B.

This report does **not** claim RUNTIME ISOLATION VERIFIED.
Phase 10.4C-B remains **NOT AUTHORIZED**.

## 1. Executive summary

Phase 10.4C-A3 re-audited `origin/main` at
`e62962bd51b7fd7ff8eed089ebd8c2acde84c6e2` (expected baseline;
exact match). Owner-provided Render topology, Staging project
membership, Team Members inventory, Staging R2 env, and Staging
database identity remain **PASS** as **OWNER-PROVIDED**. Those
records are not independent Render or Cloudflare verification.

Source inspection of the four mandated risks:

| Risk | Result | Evidence type |
| --- | --- | --- |
| A — Production bucket identification | **FAIL** | source code |
| B — Cleanup CLI safety | **FAIL** | source code |
| C — Storage boundary | **PARTIALLY VERIFIED** | source + owner-provided env |
| D — Database boundary | **PARTIALLY VERIFIED** | source + owner-provided identity |

`is_production_bucket()` still defaults to
`{"docuflow-documents"}` and does **not** treat the owner-recorded
Production bucket `docuflowai-documents` as production unless that
name is passed as `production_bucket`. The cleanup CLI still does
not call `_enforce_production_configuration`, has no dry-run flag,
and does not reject a Production bucket before mutating.

Overall runtime isolation: **NOT VERIFIED**. Workspace topology
**PASS** does not imply runtime isolation **PASS**. Cross-workspace
access isolation remains **NOT VERIFIED**. Phase 10.4C-B is **not**
authorized by this assessment.

## 2. Audited repository SHA

Verified this pass (`git fetch origin main`;
`merge-base --is-ancestor e62962b origin/main`):

| Field | Value |
| --- | --- |
| Expected baseline | `e62962bd51b7fd7ff8eed089ebd8c2acde84c6e2` |
| Ancestor check | **ANCESTOR_OK** (exact match of `origin/main`) |
| `origin/main` HEAD | `e62962bd51b7fd7ff8eed089ebd8c2acde84c6e2` |
| Subject | Merge pull request #93 |
| Commit date | `2026-11-13 10:31:10 +0700` / **13 Nov 2026, 10:31 Asia/Jakarta** |
| Open PRs at start | none targeting `main` |
| `main` CI after #93 | [43359503777](https://github.com/mufea/docuflow-ai/actions/runs/43359503777) **SUCCESS** — repository CI, **not** runtime isolation |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**) |
| Working tree at start | clean at `origin/main` |

`src/` and `infra/` were inspected read-only. No application files
changed.

Prior evidence reused (not re-run, not rewritten):

- `docs/reports/PHASE_10_4C_A_RUNTIME_ISOLATION_ASSURANCE.md`
- `docs/reports/PHASE_10_4C_A2R_POST_MERGE_RECONCILIATION.md`
- `docs/IMPLEMENTATION_STATUS.md` Phase 10.4C ledger

## 3. Owner evidence inventory

All rows below are **OWNER-PROVIDED** unless marked otherwise.
Screenshots are not independent verification. Secret values, DSNs,
full Access Key IDs, Cloudflare token strings, and the owner email
are **not** copied here.

| Item | Recorded observation | Classification | Source |
| --- | --- | --- | --- |
| Production workspace | `docuflowai`; ID `tea-d84phnqa8673blqsn0`; Hobby | **PASS — OWNER-PROVIDED** | A2 §17 |
| Staging workspace | `docuflowai staging`; ID `tea-d9f6cddc9c73dqpab0`; Hobby | **PASS — OWNER-PROVIDED** | A2 §17 |
| Staging project | `DocuflowAI`; environment Staging; All 4 | **PASS — OWNER-PROVIDED** | A2 §16 |
| Staging services | `docuflow-staging-api` Deployed; `docuflow-staging-web` Deployed; `docuflow-staging-db` Available; `docuflow-staging-cleanup` Successful build | **PASS — OWNER-PROVIDED** | A2 §16 |
| Team Members | one Admin on each workspace; no extra members shown | **PASS — OWNER-PROVIDED** | A2 Team Members (PR #93) |
| Staging API R2 | `STORAGE_BACKEND=s3`; `S3_BUCKET=docuflowai-staging`; R2 endpoint host; Access Key ID mask `6c01…2307` | **PASS — OWNER-PROVIDED** | A1 Gap 2 / A2 Gap 2 |
| Staging cleanup R2 | same bucket, backend, endpoint family, and key mask as API (`echo` only; not HeadBucket; not `python -m docuflow.cleanup`) | **PASS — OWNER-PROVIDED** | A2 §17 |
| Cloudflare token scope | token named for `docuflowai-staging`; read/write/list; bucket `docuflowai-staging` only | **PASS — OWNER-PROVIDED** | A2 Gap 3 |
| Staging API database | user `docuflow_staging_db_ikpz_user`; intended DB `docuflow_staging_db_ikpz` | **PASS — OWNER-PROVIDED** | A1 Gap 1 / SR7 |
| Staging cleanup database | same identity as API (labeled Shell) | **PASS — OWNER-PROVIDED** | A1 Gap 1 |
| Env groups | none shown in either workspace | observational, not an isolation PASS | A2 §17 |
| 2FA / SSO | not enforced | observational, not an isolation PASS | A2 Team Members |

Shared solo-owner Admin on both Hobby workspaces is expected. It is
**not** recorded as a runtime security breach. It is also **not**
proof that the two workspaces cannot access each other.

## 4. Render workspace and membership assessment

### 4.1 Workspace separation — **PASS — OWNER-PROVIDED**

Distinct workspace names and IDs are recorded. This phase did not
open Render and does not claim independent workspace verification.

Limitation: workspace exclusivity is not network isolation, not
credential isolation, and not cross-workspace access denial.

### 4.2 Staging service membership — **PASS — OWNER-PROVIDED**

Project `DocuflowAI` / environment Staging All 4 contains the four
expected Staging-named services. No Production-named services appear
in that inventory. `Successful build` is **not** a cleanup run.

Limitation: membership screenshots do not prove Render project
exclusivity independently of owner chrome.

### 4.3 Team membership inventory — **PASS — OWNER-PROVIDED**

Each workspace screenshot shows one Admin. Email is not recorded.
This inventory does **not** prove cross-workspace access denial.

## 5. R2 credential and bucket assessment

Live Staging configuration (API and cleanup) is **PASS —
OWNER-PROVIDED** for `S3_BUCKET=docuflowai-staging` with
`STORAGE_BACKEND=s3` and a Staging-scoped token. Production
negative-access tests were **not** performed.

Source limitation (Risk A): the repository helper that is supposed
to recognize Production buckets does not default-flag
`docuflowai-documents`. See §7.A. Live Staging env **PASS** does
not convert that helper into **PASS**.

## 6. Database identity assessment — **PASS — OWNER-PROVIDED**

Previously recorded Staging API and cleanup Shell identity evidence
shows both services using the intended Staging database identity
(`docuflow_staging_db_ikpz` / `docuflow_staging_db_ikpz_user`).
This phase did not connect to any database and did not run SQL.

Limitation: identity evidence is owner-provided Shell output, not
an independent DSN comparison. Source configuration still injects
whatever `DATABASE_URL` Render supplies (Risk D).

## 7. Source risk assessment

Inspected at SHA `e62962bd51b7fd7ff8eed089ebd8c2acde84c6e2`. No
prior finding was assumed still active without a current read.

### 7.A Risk A — Production bucket identification — **FAIL**

**Control / risk identifier:** RISK-A
**Evidence source:** `src/docuflow/staging_checks.py`
(`DEFAULT_PRODUCTION_BUCKETS`, `is_production_bucket`,
`is_forbidden_live_test_bucket`, `validate_staging_configuration`);
`src/docuflow/config.py` (`s3_bucket` default);
`tests/test_phase98_staging.py`; local helper invocation.
**Evidence type:** source code (plus local static check).
**Current observation:** `DEFAULT_PRODUCTION_BUCKETS` is
`{"docuflow-documents"}`. `is_production_bucket("docuflowai-documents")`
returns `False`. The owner-recorded Production bucket is recognized
only when `production_bucket="docuflowai-documents"` is passed.
Empty string returns `False` (not treated as production). Comparison
is case-normalized via `.strip().lower()`. Call sites are confined
to `staging_checks.py` (preflight / staging validators). The cleanup
CLI and API storage init do **not** call this helper. Settings
default `S3_BUCKET` remains `docuflow-documents`. Tests assert
`docuflow-documents` is production and do not cover
`docuflowai-documents`.
**Security implication:** a Staging preflight that omits the
`production_s3_bucket` argument will not reject
`S3_BUCKET=docuflowai-documents`. Isolation then depends entirely on
correct live env injection, not on the default helper.
**Remaining limitation:** live Staging `S3_BUCKET=docuflowai-staging`
is owner-provided **PASS** and is a different control. This FAIL is
the default identifier, not a claim that Staging currently points at
Production.
**Recommended next action:** separately authorized source change to
include `docuflowai-documents` in `DEFAULT_PRODUCTION_BUCKETS` and
extend unit tests. Not in this documentation PR.

Local check (no live resources):

```
is_production_bucket("docuflow-documents")     True
is_production_bucket("docuflowai-documents")   False
is_production_bucket("docuflowai-staging")     False
is_production_bucket("")                       False
is_production_bucket("docuflowai-documents",
    production_bucket="docuflowai-documents")  True
audit_staging_blueprint(infra/render.staging.yaml)
    0 errors, 0 warnings
```

### 7.B Risk B — Cleanup CLI safety — **FAIL**

**Control / risk identifier:** RISK-B
**Evidence source:** `src/docuflow/cleanup.py`;
`src/docuflow/jobs/retention.py` (`run_runtime_cleanup`);
`src/docuflow/main.py` (`_enforce_production_configuration`);
`src/docuflow/storage/factory.py`; `src/docuflow/storage/s3.py`.
**Evidence type:** source code.
**Current observation:** `python -m docuflow.cleanup` loads
settings, opens a database session, builds storage, and calls
`run_runtime_cleanup`, which deletes expired objects and fails stale
jobs. It does **not** call `_enforce_production_configuration`. It
does **not** call `is_production_bucket`. There is no CLI
authorization flag and no dry-run mode. `CleanupStats.skipped` means
the cleanup lease is already held, not that the run is non-mutating
by request. Missing S3 keys raise in `S3Storage.__init__`. A missing
`S3_BUCKET` env var does **not** fail closed: Settings default to
`docuflow-documents`. Staging cron (`infra/render.staging.yaml`)
runs migrate then cleanup with `CLEANUP_INTERVAL_SECONDS=0`.
**Security implication:** a mis-injected Production DSN or bucket
on the cleanup service would be used, not rejected, before any
destructive work. Live Staging cleanup env is owner-recorded as
Staging R2/DB, which is a different control.
**Remaining limitation:** this phase did not execute cleanup and
did not prove live mutation behavior. Dry-run cannot be claimed
because the CLI has no dry-run path.
**Recommended next action:** separately authorized fail-fast on
cleanup startup (reuse production-readiness errors; reject known
Production buckets; refuse empty bucket; optional explicit
authorization / dry-run). Not in this documentation PR. Do **not**
run live cleanup to “prove” safety.

### 7.C Risk C — Storage boundary — **PARTIALLY VERIFIED**

**Control / risk identifier:** RISK-C
**Evidence source:** `src/docuflow/storage/factory.py`,
`src/docuflow/storage/s3.py`, `src/docuflow/config.py`,
`src/docuflow/services/documents.py` (`_store` key
`{user.id}/{uuid}{ext}`), owner-provided Staging R2 env.
**Evidence type:** source code plus owner-provided configuration.
**Current observation:** API and cleanup both call
`build_storage(settings)` and use `settings.s3_bucket` with no
object-key environment prefix. Isolation is bucket-name plus
credential injection. Staging live env and token scope are
owner-provided **PASS** for `docuflowai-staging`. Production bucket
`docuflowai-documents` is a distinct name. There is no application
allow-list that would refuse the Production bucket at runtime.
**Security implication:** a shared or swapped credential/bucket
would write and delete objects in that bucket using the same key
pattern. Absence of an object-key prefix is an architectural
property, not a defect requiring migration in this phase.
**Remaining limitation:** no independent HeadBucket, ListObjects, or
negative Production access test was performed. Token exclusivity
beyond the owner screenshot is not re-proven here.
**Recommended next action:** keep bucket-name isolation; do not
introduce an object-key migration. Optional later source fail-fast
on Production bucket names (Risk A/B). Owner may supply independent
token/bucket verification if overall isolation PASS is required.

### 7.D Risk D — Database boundary — **PARTIALLY VERIFIED**

**Control / risk identifier:** RISK-D
**Evidence source:** `src/docuflow/config.py` (`database_url` /
`DATABASE_URL`); `src/docuflow/db.py`
(`create_engine_from_settings`); `src/docuflow/cleanup.py`;
`src/docuflow/staging_checks.py` (`is_production_database`);
owner-provided Staging API and cleanup identity.
**Evidence type:** source code plus owner-provided identity.
**Current observation:** both API and cleanup use
`get_settings().database_url` with no environment-specific
allow-list at runtime. `is_production_database()` is used by
staging preflight, not by cleanup or API startup. Default Settings
URL is local SQLite; production-readiness errors reject SQLite when
`DOCUFLOW_ENV=production` **on API startup only**. Cleanup does not
run that check. Live Staging identity evidence shows the intended
Staging database on both services.
**Security implication:** isolation is Render `DATABASE_URL`
injection. A swapped DSN would be accepted by cleanup and, if
PostgreSQL, by API fail-fast as well.
**Remaining limitation:** DSNs were not opened. No SQL was run.
Source has no runtime Staging-vs-Production database allow-list.
**Recommended next action:** keep current injection model. Optional
later cleanup fail-fast. Do not connect to live databases for this
assessment.

## 8. Targeted testing performed

Allowed local / repository checks only:

| Check | Result |
| --- | --- |
| `git fetch origin main` + ancestor of `e62962b` | exact match |
| Open PRs targeting `main` | none at assessment start |
| `main` CI after PR #93 | SUCCESS (repository CI) |
| `is_production_bucket` local invocations | Risk A FAIL reproduced |
| `audit_staging_blueprint(infra/render.staging.yaml)` | 0 errors, 0 warnings (template only) |
| Read-only inspection of cleanup / storage / db / config | Risk B FAIL; C/D PARTIALLY VERIFIED |
| Full test suite | **not** run |
| Live HTTP, Shell, SQL, HeadBucket, cleanup, upload, delete | **not** performed |

## 9. Findings and limitations

### 9.1 Findings (one classification each)

| ID | Classification | Evidence type | Observation | Security implication | Remaining limitation | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| CONTROL-WS | **PASS** | owner-provided | Distinct workspace IDs `tea-d84phnqa8673blqsn0` vs `tea-d9f6cddc9c73dqpab0` | Topology separation is recorded | Not independent Render verification; not network isolation | Keep as owner-provided; do not treat as runtime PASS |
| CONTROL-MEMBERSHIP | **PASS** | owner-provided | Staging project `DocuflowAI` All 4 matches expected services | Staging-named inventory is complete in chrome | Screenshot ≠ exclusivity proof | No Stage B from this row |
| CONTROL-TEAM | **PASS** | owner-provided | One Admin per workspace; no extra members | Inventory complete; shared Admin expected | Not cross-workspace denial | Do not record owner email |
| CONTROL-R2 | **PASS** | owner-provided | Staging API + cleanup `S3_BUCKET=docuflowai-staging`; token scoped to that bucket | Live Staging storage target is Staging | `echo` ≠ HeadBucket; no Production negative test | Do not probe Production |
| CONTROL-DB-IDENTITY | **PASS** | owner-provided | API and cleanup share intended Staging DB identity | Both Staging compute services point at Staging DB in recorded Shell | Not a live reconnect | Do not run SQL |
| RISK-A | **FAIL** | source code | Default helper omits `docuflowai-documents` | Preflight can miss the real Production bucket | Live Staging bucket is still staging | Separate source fix if authorized |
| RISK-B | **FAIL** | source code | Cleanup mutates without production fail-fast, bucket reject, or dry-run | Mis-injected Production resources would be used | Not executed live | Separate CLI hardening if authorized; do not run cleanup |
| RISK-C | **PARTIALLY VERIFIED** | source + owner-provided | Bucket-name isolation; no object-key prefix; live Staging bucket owner-provided | Boundary is env injection, not an app allow-list | No independent storage proof this phase | No key migration |
| RISK-D | **PARTIALLY VERIFIED** | source + owner-provided | `DATABASE_URL` injection; live identity owner-provided | Boundary is env injection | No live DSN inspect | No database connection |
| CONTROL-XWS | **NOT VERIFIED** | none independent | Same solo Admin; no access-denial evidence | Cannot claim workspaces cannot reach each other | Would need independent Render/IAM proof | Do not convert to PASS |

Owner-provided, source-code, automated-test, and independent
operational evidence are **not** combined into one unsupported PASS.

### 9.2 Limitations (unchanged rules)

- CI SUCCESS is not runtime isolation.
- MERGED is not DEPLOYED.
- Distinct workspace IDs are not credential isolation.
- Separate buckets by name are not proven exclusive access.
- `Successful build` is not a cleanup run.
- This phase is not authorization for Stage B.

## 10. Overall isolation decision

| Assessment | Decision |
| --- | --- |
| Render workspace separation | **PASS** (OWNER-PROVIDED) |
| Staging service membership | **PASS** (OWNER-PROVIDED) |
| Team membership inventory | **PASS** (OWNER-PROVIDED) |
| Staging R2 configuration | **PASS** (OWNER-PROVIDED) |
| Database identity evidence | **PASS** (OWNER-PROVIDED) |
| Production bucket protection | **FAIL** (source helper) |
| Cleanup CLI safety | **FAIL** (source) |
| Storage boundary | **PARTIALLY VERIFIED** |
| Database boundary | **PARTIALLY VERIFIED** |
| Cross-workspace access isolation | **NOT VERIFIED** |
| Overall runtime isolation | **NOT VERIFIED** |

Overall runtime isolation is **not** PASS. Critical controls remain
unverified or failed at the source layer (Risk A, Risk B,
CONTROL-XWS). Phase 10.4C is **not** complete because this
assessment report exists.

## 11. Remaining owner actions

1. Do **not** treat this report as Stage B authorization.
2. If overall isolation PASS is required, supply independent
   evidence of cross-workspace access denial, or accept in writing
   that CONTROL-XWS stays **NOT VERIFIED**.
3. If Risk A should be closed in source: authorize a documentation-
   separate code change to default-flag `docuflowai-documents` and
   add unit tests.
4. If Risk B should be closed in source: authorize cleanup CLI
   fail-fast / Production-bucket reject / optional dry-run. Do not
   execute live cleanup as a substitute.
5. Do not rotate credentials, edit Render env, or deploy as part of
   this assessment.
6. Phase 10.4C-B functional Staging tests remain **NOT AUTHORIZED**
   until the owner explicitly authorizes them after accepting this
   isolation decision.

## 12. Explicit authorization boundary

This phase assessed evidence. It did **not** authorize operations.

Safety declaration:

- No Production probes were performed.
- No Production or Staging Shell commands were executed.
- No live database connections were made.
- No cleanup operation was executed.
- No storage objects were read, written, or deleted.
- No migrations were executed.
- No restore or export operations were performed.
- No credentials or DSNs were exposed.
- No infrastructure or application configuration was changed.
- No deployment was performed.
- Phase 10.4C-B was not authorized or executed.
