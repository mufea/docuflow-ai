# Phase 10.4C-A — Runtime isolation assurance

Read-only Stage A. Time: **12 Nov 2026, 18:50 Asia/Jakarta (WIB)**.
A1 gap-closure update: **12 Nov 2026, 20:52 Asia/Jakarta (WIB)**
(Gap 2) and **12 Nov 2026, 21:38 Asia/Jakarta (WIB)** (Gap 1 labeled
cleanup Shell).
No application-code change. No Blueprint sync. No deploy, migrate,
cleanup, object write, or functional smoke. SR7 API identity SQL and
HeadBucket were **not** repeated. Stage B is **NOT AUTHORIZED** and
was **not** started.

This report does **not** claim RUNTIME ISOLATION VERIFIED.

## 1. Objective and scope

Determine whether the current Staging architecture provides adequate
isolation from Production, using repository architecture plus existing
runtime evidence. Public `/health` and `/ready` remain reachability
only. Successful Staging database identity and R2 HeadBucket do **not**
prove complete cross-environment isolation. Repository CI SUCCESS does
**not** prove runtime isolation.

Out of scope: Stage B functional tests, Production probes, negative
access tests against Production, credential rotation, env edits,
Blueprint apply, and any SQL/HeadBucket replay.

## 2. Repository baseline

Verified this pass (`git fetch origin main`):

| Field | Value |
| --- | --- |
| `origin/main` | `9b76e84cd888117f4dda23e39d552d416e8d2d56` |
| Subject | Merge pull request #85 |
| Commit date | `2026-11-12 18:29:16 +0700` / **12 Nov 2026, 18:29 Asia/Jakarta** |
| PRs #83 / #84 / #85 | **MERGED** |
| Main CI after #85 | [43209567342](https://github.com/mufea/docuflow-ai/actions/runs/43209567342) **SUCCESS** (**12 Nov 2026, 18:31 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| Stage A docs PR | [#86](https://github.com/mufea/docuflow-ai/pull/86) **MERGED** `f0043ee4c41a95573310dcdeba496e748f5d792c` (**12 Nov 2026, 18:45 Asia/Jakarta**). Merge is git status, not isolation |
| PR #86 repository CI | [43211699221](https://github.com/mufea/docuflow-ai/actions/runs/43211699221) **SUCCESS** (**12 Nov 2026, 18:46 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| `main` CI after #86 | [43211953700](https://github.com/mufea/docuflow-ai/actions/runs/43211953700) **SUCCESS** (**12 Nov 2026, 18:47 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**) |
| Working tree at start | clean at `origin/main` |

`src/` and `infra/` were inspected read-only. No application files
changed.

Prior evidence reused (not re-run):
`docs/reports/PHASE_10_4B_SR7_RUNTIME_ISOLATION_VERIFICATION.md`.

## 3. Audit scope

Inspected:

| Area | Path |
| --- | --- |
| SR7 runtime evidence | `docs/reports/PHASE_10_4B_SR7_RUNTIME_ISOLATION_VERIFICATION.md` |
| 10.4B-S safety audit | `docs/reports/PHASE_10_4B_S_STAGING_SAFETY_CONFIGURATION_AUDIT.md` |
| Staging Blueprint | `infra/render.staging.yaml` |
| Production Blueprint | `infra/render.yaml` |
| Settings / env | `src/docuflow/config.py` |
| DB engine | `src/docuflow/db.py` |
| S3/R2 client | `src/docuflow/storage/s3.py`, `storage/factory.py` |
| Staging validators | `src/docuflow/staging_checks.py` |
| Cleanup CLI | `src/docuflow/cleanup.py` |
| Job broker | `src/docuflow/jobs/broker.py` |
| Health/ready | `src/docuflow/api/routes/health.py` |
| Production fail-fast | `src/docuflow/main.py` `_enforce_production_configuration` |

Local check: `audit_staging_blueprint(infra/render.staging.yaml)` →
zero errors, zero warnings (**REPOSITORY VERIFIED**). That is a
template check, not live Render state.

## 4. Architecture findings

### 4.1 Database connection selection

The API and cleanup both bind SQLAlchemy to `Settings.database_url`
(`DATABASE_URL`). There is no second connection pool, no
environment-specific DSN override in code, and no runtime check that
the connected database name equals `docuflow_staging_db_ikpz`.

Isolation is therefore **injection of `DATABASE_URL`**, not an
application-enforced allow-list.

Staging Blueprint: API and cleanup `fromDatabase.name=docuflow-staging-db`.
Production Blueprint: API and cleanup `fromDatabase.name=docuflow-db`.
Declared names do not overlap.

`validate_staging_configuration()` can reject a production-looking DSN
**if invoked**. It is used by staging preflight helpers. It is **not**
called from `cleanup.py` or from API request handlers. API startup
fail-fast (`_enforce_production_configuration`) requires PostgreSQL in
`DOCUFLOW_ENV=production` but does **not** require the database name to
contain `staging`.

Owner-provided API identity (SR7, not repeated): database
`docuflow_staging_db_ikpz`, user `docuflow_staging_db_ikpz_user`,
`10.26.149.13:5432`, one row. That is runtime **name** evidence for the
API process. The private IP is not a Render resource hostname, so the
Render resource id remains **NOT VERIFIED**. Cleanup identity remains
**NOT VERIFIED**.

### 4.2 Object storage endpoint and bucket selection

`S3Storage` uses `settings.s3_bucket`, `settings.s3_endpoint_url`, and
the configured access keys with no key prefix. The Blueprint comment
is accurate: prefix isolation is not implemented. Bucket name is the
storage isolation boundary.

Code default `S3_BUCKET` is `docuflow-documents`. Owner production
bucket is `docuflowai-documents`. Those names differ. If `S3_BUCKET`
were unset while `STORAGE_BACKEND=s3`, API fail-fast still requires a
non-empty bucket, so the code default could be used. Live API
`S3_BUCKET=docuflowai-staging` is **OWNER-PROVIDED** (SR7). HeadBucket
of that name from the API Shell is **OWNER-PROVIDED PASS**. Endpoint
host was not recorded. Cleanup HeadBucket was not run.

`staging_checks.DEFAULT_PRODUCTION_BUCKETS` is `{docuflow-documents}`.
The validator does **not** treat `docuflowai-documents` as a default
production bucket unless `production_s3_bucket` is passed in. That is a
**preflight gap**, not proof of live misconfiguration.

### 4.3 Credential selection and fallback paths

S3 keys are `sync: false` on the staging API (owner-supplied) and
copied onto cleanup `fromService: docuflow-staging-api`. Production
Blueprint copies from `docuflow-api`. The application has no code path
that reads a second “production” credential set. Missing keys fail
`S3Storage.__init__` / production readiness. There is no silent
fallback to Production keys in source.

Live Access Key ID identity and Cloudflare token scope are unread.
HeadBucket success does not prove the token cannot access
`docuflowai-documents`. Production R2 was **not** probed (forbidden
negative test).

### 4.4 Whether Staging can access Production resources

Not independently proven. Distinct names reduce accidental selection in
the **template**. Live risk paths that remain open:

1. Staging API/cleanup env manually pointed at Production DSN or
   Production bucket (dashboard drift vs Blueprint).
2. Staging R2 token scoped to more than `docuflowai-staging`.
3. Staging and Production sharing a Render workspace (Free Postgres is
   one-per-workspace; paid Production Postgres can coexist with a Free
   staging database in one workspace). Workspace membership is
   **NOT VERIFIED** from this agent.
4. Cleanup cron using a drifted env that the API identity query did not
   observe.

None of these were demonstrated. None were disproven without Production
access.

### 4.5 Accidental Production selection

Application defaults that can select non-staging resources if env is
omitted:

| Setting | Default | Staging Blueprint |
| --- | --- | --- |
| `S3_BUCKET` | `docuflow-documents` | owner `sync: false` |
| `DATABASE_URL` | local SQLite | `fromDatabase: docuflow-staging-db` |
| `DOCUFLOW_ENV` | `development` | `production` (fail-fast; **do not** change to `staging`) |

`Settings.env` is only `development|test|production`. Staging uses
`DOCUFLOW_ENV=production` so fail-fast applies. This audit does **not**
recommend `DOCUFLOW_ENV=staging`.

`AI_PROVIDER=mock` and `EMAIL_BACKEND=console` on the staging template
limit outbound AI/email blast radius. Live values unread except as
template.

### 4.6 Cleanup jobs

`python -m docuflow.cleanup` loads the same `get_settings()` / storage
factory as the API. It **mutates** expired jobs and storage objects in
whatever database and bucket the process env names. It does **not**
call `_enforce_production_configuration`. Target isolation is entirely
the cleanup service env.

Template: staging cleanup DSN and S3 vars copy from staging API, not
from `docuflow-api`. Live cleanup process identity: **NOT VERIFIED**.
This audit did **not** run cleanup.

### 4.7 Job processing boundary

Staging API `JOB_BROKER=inline`. No staging worker, no staging Redis.
Inline jobs run in the API process against the API engine and
`S3Storage` instance. Job-broker isolation therefore follows API
runtime identity. Historical `/ready` reported `broker=inline`,
`rq_workers=0` (**12 Nov 2026, 17:15 Asia/Jakarta**). That is
reachability plus declared broker, not a second identity proof.

RQ fallback exists in code (`RQBroker` can inline-fallback). Staging
template does not set `JOB_BROKER=rq` or `REDIS_URL`. Live broker other
than inline is **NOT VERIFIED** beyond the historical `/ready` body.

### 4.8 Shared workspace / network

Blueprints declare separate service names. They do not encode Render
workspace id. Private Postgres `ipAllowList: []` is private-network
only. Agent has no Render dashboard. Shared-workspace risk remains
**NOT VERIFIED**. SR6 A0 (dedicated staging workspace) remains
historically unassigned in the ledger.

### 4.9 Remaining evidence that could be closed read-only

Without Production access or infrastructure mutation:

- Cleanup Shell: same identity `SELECT` as SR7 (do **not** run
  `python -m docuflow.cleanup`).
- Redacted `S3_ENDPOINT_URL` host and masked access key id from staging
  API Shell (names/host only).
- Cloudflare dashboard: token limited to `docuflowai-staging`.
- Render workspace service list: no `docuflow-api` / `docuflow-db` in
  the staging workspace.

This Stage A pass did **not** request those repeats. Identity SQL and
HeadBucket already succeeded for the API; they were not replayed.

## 5. Isolation assurance matrix

Class rules: **PASS** requires direct evidence of the expected
condition. Intended configuration alone is not PASS for a runtime
dimension. **NOT VERIFIED** is used when evidence is missing,
ambiguous, or would require a forbidden Production probe.

| Isolation dimension | Required evidence | Result | Evidence class |
| --- | --- | --- | --- |
| PostgreSQL identity | Runtime database and user | **PASS** API and cleanup (`docuflow_staging_db_ikpz` / `docuflow_staging_db_ikpz_user` / `10.26.149.13:5432`) | OWNER-PROVIDED Shells (API SR7; cleanup A1 labeled) |
| Database endpoint | Staging-specific endpoint/resource mapping | **NOT VERIFIED** as Render resource. Observed `10.26.149.13:5432` (OWNER-PROVIDED). Template `fromDatabase: docuflow-staging-db` is **REPOSITORY VERIFIED** only | OWNER-PROVIDED IP; template ≠ live mapping |
| R2 bucket | Runtime bucket identity | **PASS** for API access to `docuflowai-staging`. Cleanup: **NOT VERIFIED** | OWNER-PROVIDED HeadBucket + `S3_BUCKET` name |
| R2 credentials | Staging credential-to-bucket mapping | **PASS** API masked key present (`6c01…2307`). Exclusive Cloudflare scope: **NOT VERIFIED** | OWNER-PROVIDED API Shell (A1). Gap 3 missing |
| R2 endpoint | Correct account and endpoint | **PASS** API host `26d06bf0ca16ba951f1d19d5989e6663.r2.cloudflarestorage.com` (Cloudflare R2) | OWNER-PROVIDED API Shell (A1); no second HeadBucket |
| Environment configuration | No Production fallback | Template: **PASS** (no production `fromDatabase` / `fromService`). Live dashboard drift: **NOT VERIFIED**. Code default bucket `docuflow-documents` is a fallback **if** `S3_BUCKET` unset; live API name is owner-confirmed staging | REPOSITORY VERIFIED template; live partial |
| Cleanup isolation | Staging-only target configuration | **PASS** for DB identity (same as API). Cleanup R2 env/HeadBucket: **NOT VERIFIED**. Template copies staging API S3 vars | OWNER-PROVIDED cleanup Shell DB; template S3 |
| Job processing | Correct broker and execution boundary | **PASS** as architecture for inline API jobs (same process as API). Historical `/ready` `broker=inline`. Not a second DB/bucket proof | REPOSITORY VERIFIED + historical INDEPENDENTLY VERIFIED `/ready` |
| Service configuration | Staging resources mapped correctly | **PASS** for Blueprint names. Live API on `350v`. Live cleanup DB identity **PASS**. Cleanup bucket live: **NOT VERIFIED** | REPOSITORY VERIFIED + OWNER-PROVIDED Shells |
| Production separation | Evidence of prevented unintended access | **NOT VERIFIED**. Distinct names are not proof. Negative Production tests were not run and must not be run | limitation |

`audit_staging_blueprint()` on current `infra/render.staging.yaml`:
**PASS** (zero issues). That is configuration isolation of the
**template**, not overall runtime isolation.

## 6. Owner-provided versus independently obtained

| Fact | Class |
| --- | --- |
| API `current_database` / `current_user` / `10.26.149.13:5432` | **OWNER-PROVIDED** (SR7 screenshots; not re-run) |
| `S3_BUCKET=docuflowai-staging` | **OWNER-PROVIDED** |
| `HeadBucket docuflowai-staging` PASS | **OWNER-PROVIDED** (one request; not re-run) |
| GET `/health` and `/ready` on `docuflow-staging-api-350v` | **INDEPENDENTLY VERIFIED** historically (**12 Nov 2026, 17:14–17:15 Asia/Jakarta**); not repeated this pass |
| Blueprint names, `fromDatabase`, inline broker, mock AI, console email | **REPOSITORY VERIFIED** this pass |
| `audit_staging_blueprint()` empty | **REPOSITORY VERIFIED** this pass |
| Main CI SUCCESS | **REPOSITORY CI** — not isolation |
| Cleanup runtime identity | **PASS** OWNER-PROVIDED A1 labeled `docuflow-staging-cleanup` Shell (**12 Nov 2026, 21:38 Asia/Jakarta**). Earlier unlabeled SQL remains historical |
| API R2 endpoint host + masked Access Key ID | **OWNER-PROVIDED** A1 (`docuflow-staging-api` Shell) |
| R2 token exclusive scope | **NOT VERIFIED** |
| Render workspace exclusivity | **NOT VERIFIED** (A1 shows account label `docuflowai` and service `docuflow-staging-api` only; full list not shown) |

This agent did **not** independently execute identity SQL or HeadBucket.

## 7. Remaining risks

1. Cleanup cron DB identity now matches the API. Cleanup bucket live
   values remain unread (template copies API S3 vars).
2. Staging R2 token may be able to access `docuflowai-documents`.
3. Staging and Production may share a Render workspace.
4. Live env can drift from Blueprint without this repository noticing.
5. No object-key prefix; a wrong bucket name selects a whole bucket.
6. `is_production_bucket()` does not default-flag `docuflowai-documents`.
7. Cleanup CLI does not run API production fail-fast.
8. Private DB IP does not identify the Render database resource.

No FAIL was observed. Absence of FAIL is not overall PASS.

## 8. Production safety confirmation

This Stage A pass:

- Did not access Production API Shell.
- Did not connect to Production PostgreSQL (ambient agent DSN was not
  used).
- Did not access Production R2.
- Did not read or export Production data.
- Did not run migrations, cleanup, deploys, restarts, or credential
  rotation.
- Did not print `DATABASE_URL`, passwords, access keys, secret keys,
  API tokens, session secrets, or full env dumps.
- Did not modify application code, Blueprint, environment variables,
  database data, or storage objects.

Production isolation was **not** independently tested. Not all
cross-environment paths are proven impossible.

## 9. Stage A decision

| Label | Result |
| --- | --- |
| IMPLEMENTATION COMPLETE | **MERGED** for Phase 10.4B heartbeat work; this pass is documentation |
| REPOSITORY CI SUCCESS | **YES** on `main` after #85 — not isolation |
| CONFIGURATION ISOLATION (template) | **PASS** |
| RUNTIME DATABASE ISOLATION | **PASS** API (**OWNER-PROVIDED**). Cleanup **NOT VERIFIED** |
| RUNTIME STORAGE ISOLATION | **PASS** API HeadBucket access (**OWNER-PROVIDED**). Exclusive token **NOT VERIFIED** |
| RUNTIME ISOLATION VERIFIED | **NO** — overall **NOT VERIFIED** |
| FUNCTIONAL STAGING VERIFIED | **NO** — Stage B **NOT AUTHORIZED** / **NOT EXECUTED** |
| PRODUCTION VERIFIED | **NO** |

Stage A does **not** authorize Stage B.

Critical dimensions that are not PASS: cleanup identity, R2 credential
scope, R2 endpoint, database Render resource mapping, workspace
separation, and prevented Production access. Stage B preconditions
require either those items to become PASS or **explicit owner
acceptance** of each remaining limitation.

## 10. Recommended next actions

Owner decision only (do not auto-start Stage B):

1. Review this report.
2. Optionally close read-only gaps (cleanup identity SELECT; redacted
   endpoint/key; Cloudflare token scope; workspace service list). Do
   not probe Production. Do not run cleanup.
3. If remaining **NOT VERIFIED** items are accepted in writing, issue a
   **separate** Stage B authorization that names the exact tests.
4. Until that authorization exists, functional smoke remains
   **NOT AUTHORIZED**.

### Proposed Stage B scope (NOT APPROVED, not executed)

For later authorization only. Exact Staging target:
`https://docuflow-staging-api-350v.onrender.com` (digit `0`). Synthetic
data only. No Production, payments, real email, billing, load, or
restore.

| ID | Case | Expected mutations |
| --- | --- | --- |
| B-A1 | Register / login / session / logout with a synthetic user | user + session rows in staging DB |
| B-B1 | Upload one small synthetic PDF | one staging object + document row |
| B-B2 | One inline processing job | job rows; possible result object in staging bucket |
| B-C1 | Confirm test object in `docuflowai-staging` | none (read) |
| B-E1 | Delete only test-owned objects/rows after approval | test resources only |

Cleanup strategy: delete only identifiers created by the test. No
`python -m docuflow.cleanup` unless separately authorized. Rollback of
expired Free-instance data is limited; do not assume PITR on staging
Free Postgres.

Estimated impact: Free API cold start; a few staging DB rows and one
small object. No Production impact **if** isolation limitations above
are accepted.

## 11. Mutations

None.

## 12. Authorization gate

**STOP.** Stage A complete. Waiting for the owner's explicit decision.
Stage A does not transition to Stage B.

## 13. Phase 10.4C-A1 — owner evidence gap closure

Time: **12 Nov 2026, 20:52 Asia/Jakarta (WIB)**. Evidence class:
**OWNER-PROVIDED** screenshots. Agent did not run SQL, HeadBucket, or
env inspection. No Production resource was accessed. Secret Access
Key was not printed.

### 13.1 Gap 1 — Cleanup database identity

#### 13.1.0 Unlabeled SQL (historical) — **NOT VERIFIED** as cleanup

**12 Nov 2026, 20:52 Asia/Jakarta.** Read-only identity row matched
staging (`docuflow_staging_db_ikpz` /
`docuflow_staging_db_ikpz_user` / `10.26.149.13:5432`) but showed no
Render service name. That screenshot remains historical and is not
cleanup PASS.

#### 13.1.1 Labeled cleanup Shell — **PASS**

**12 Nov 2026, 21:38 Asia/Jakarta.** Evidence class:
**OWNER-PROVIDED**. Render Web Shell chrome is
**`docuflow-staging-cleanup`** (cron). Account label `docuflowai`.
One identity row:

| Field | Observed |
| --- | --- |
| Database | `docuflow_staging_db_ikpz` |
| Database user | `docuflow_staging_db_ikpz_user` |
| Server address | `10.26.149.13` |
| Port | `5432` |

Classification: **PASS** — staging cleanup runtime database identity.
Matches the API identity. Production PostgreSQL was not queried.
Cleanup was **not** executed (`python -m docuflow.cleanup` not run).
Cleanup R2 bucket/env was not read in this screenshot.

### 13.2 Gap 2 — R2 endpoint and credential mapping — **PASS** (API)

Service chrome: Render Web Shell **`docuflow-staging-api`**, instance
`gchn9`, account label `docuflowai`. Fail-closed env script (no R2
API call). Observed print:

| Field | Observed |
| --- | --- |
| `STORAGE_BACKEND` | `s3` |
| `S3_BUCKET` | `docuflowai-staging` |
| `S3_ENDPOINT_HOST` | `26d06bf0ca16ba951f1d19d5989e6663.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY_ID` | masked `6c01…2307` |

Classification: **PASS** — API runtime uses Cloudflare R2 endpoint,
staging bucket name, and a non-empty access key. Consistent with
intended Staging storage mapping.

This does **not** prove the token cannot access `docuflowai-documents`.
Cleanup env was not read. Secret key was not requested.

### 13.3 Gap 3 — Cloudflare token scope — **NOT VERIFIED**

No dashboard screenshot of token-to-bucket restriction. Masked key
`6c01…2307` is not exclusive-scope evidence.

### 13.4 Gap 4 — Render workspace exclusivity — **NOT VERIFIED**

The A1 Shell screenshot shows Render account/workspace label
`docuflowai` and service `docuflow-staging-api`. A full service list
was not provided. Different names do not prove the workspace contains
no `docuflow-api` / `docuflow-db`. Workspace name `docuflowai` is not
itself a dedicated-staging proof.

### 13.5 A1 risk reassessment

| # | Concern | After A1 |
| --- | --- | --- |
| 1 | Cleanup may use a different DB/bucket than the API | DB **closed** (same identity as API). Cleanup bucket live: still unread |
| 2 | Staging R2 token may reach `docuflowai-documents` | **Live gap** — Gap 3 open |
| 3 | Shared Render workspace | **Live gap** — Gap 4 open |
| 4 | Unset `S3_BUCKET` defaults to `docuflow-documents` | **Source risk**. Live API bucket reconfirmed staging |
| 5 | `is_production_bucket()` omits `docuflowai-documents` | **Source risk** — no code change |
| 6 | Cleanup CLI has no API fail-fast | **Source risk** — no code change |
| 7 | No object-key prefix | **Architecture** — bucket name remains the boundary |

### 13.6 A1 decision

| Label | Result |
| --- | --- |
| Gap 1 cleanup DB identity | **PASS** (OWNER-PROVIDED labeled Shell) |
| Gap 2 API R2 endpoint + masked key | **PASS** (OWNER-PROVIDED) |
| Gap 3 Cloudflare token scope | **NOT VERIFIED** |
| Gap 4 workspace exclusivity | **NOT VERIFIED** |
| RUNTIME ISOLATION VERIFIED | **NO** |
| FUNCTIONAL STAGING VERIFIED | **NO** — Stage B **NOT AUTHORIZED** |
| PRODUCTION VERIFIED | **NO** |

Remaining owner actions: (1) Cloudflare token scope screenshot
restricted to `docuflowai-staging` with no Production bucket; (2) full
staging workspace service list. Or explicit written acceptance of each
remaining gap. Do not run cleanup. Do not probe Production.
