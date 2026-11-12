# Phase 10.4B-SR7 — Runtime database and object storage isolation

Read-only. First pass: **12 Nov 2026, 17:15 Asia/Jakarta (WIB)**.
Owner-evidence update: **12 Nov 2026, 18:08 Asia/Jakarta (WIB)**.
No application-code change. No Blueprint sync. No deploy, migrate,
cleanup from this workspace, no agent SQL connect, no object write, and
no functional smoke. The agent did **not** repeat the owner Shell
identity query or HeadBucket.

## 1. Objective and scope

Establish whether staging API and cleanup **runtime** connections use
the dedicated staging PostgreSQL database and Cloudflare R2 staging
bucket. Public `/health` and `/ready` remain reachability checks only.

Out of scope: mutating smoke, credential rotation, Render env edits,
production DSN/secret retrieval, List/Get/Put/Delete object, any SQL
other than a staging-service identity `SELECT` (not available here).

## 2. Repository baseline

| Field | Value |
| --- | --- |
| Audit start branch | `cursor/phase-10-4b-s-staging-safety-reprobe-8f43` @ `72d46084d4cc4cf6395a56e7c5bb912a348f0419` |
| Working tree | clean |
| First-pass `origin/main` | `7700188264fc151cad9e8cbf9505c1e4839f789d` (PR [#81](https://github.com/mufea/docuflow-ai/pull/81) merge) |
| First-pass main CI | [43181164350](https://github.com/mufea/docuflow-ai/actions/runs/43181164350) **SUCCESS** (**12 Nov 2026, 15:15 Asia/Jakarta**) |
| Evidence-update `origin/main` | `7628da1805f18052b154c6246ce6f3f4faa5022e` (PR [#82](https://github.com/mufea/docuflow-ai/pull/82) merge) |
| Evidence-update main CI | [43199979912](https://github.com/mufea/docuflow-ai/actions/runs/43199979912) **SUCCESS** (**12 Nov 2026, 17:26 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| Owner-evidence PR | [#83](https://github.com/mufea/docuflow-ai/pull/83) **MERGED** `4ae51235ae543ae1857e4c8010c43e62521af1f5` (**12 Nov 2026, 18:15 Asia/Jakarta**) |
| PR #83 repository CI | [43206679114](https://github.com/mufea/docuflow-ai/actions/runs/43206679114) **SUCCESS** (**12 Nov 2026, 18:11 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| Post-merge `main` CI after #83 | [43207572179](https://github.com/mufea/docuflow-ai/actions/runs/43207572179) **SUCCESS** (**12 Nov 2026, 18:17 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| Recon PR | [#84](https://github.com/mufea/docuflow-ai/pull/84) **MERGED** `82d94f073224225ae8d862630c757de83926fb86` (**12 Nov 2026, 18:20 Asia/Jakarta**) |
| PR #84 repository CI | [43207968097](https://github.com/mufea/docuflow-ai/actions/runs/43207968097) **SUCCESS** (**12 Nov 2026, 18:20 Asia/Jakarta**) — repository CI, **not** runtime isolation |
| `main` CI after #84 | [43208360239](https://github.com/mufea/docuflow-ai/actions/runs/43208360239) **IN PROGRESS** at this write — repository CI, **not** runtime isolation |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**) |

`src/` and `infra/` are unchanged vs the 10.4B-S safety audit.

## 3. Services inspected

| Service | Architecture | Inspected how |
| --- | --- | --- |
| `docuflow-staging-api` | Free web, `JOB_BROKER=inline` | Blueprint + public GET; owner Shell identity SQL + one HeadBucket (screenshots) |
| `docuflow-staging-cleanup` | Cron `*/15 * * * *` | Blueprint only |
| Staging worker | none | **NOT APPLICABLE** |
| Redis | omitted while inline | **NOT APPLICABLE** |

Existing diagnostics: `/health`, `/ready` (`SELECT 1` + `head_bucket`
via `S3Storage.ping`). No identity-echo endpoint. Logs redact
`database_url` / `access_key` keys (`src/docuflow/logging.py`). This
audit did **not** add diagnostics.

## 4. Expected identities (assertions, not access)

Owner-provided. Not independently confirmed in a Render/Cloudflare UI
from this workspace.

| Role | Render / bucket | Database / user |
| --- | --- | --- |
| Staging Postgres | `docuflow-staging-db` | expected database `docuflow_staging_db_ikpz`; observed runtime user is in §5.1 (not the earlier asserted `docuflowstagingdb_hbnd_user`) |
| Production Postgres | `docuflow-db` | `docuflow_db_q32a` / `docuflow_db_q32a_user` |
| Staging R2 | `docuflowai-staging` | staging Access Key ID (owner-confirmed; **not** present here) |
| Production R2 | `docuflowai-documents` | **not retrieved** |

Production DSN, production passwords, and production storage secrets
were **not** read.

## 5. Database runtime identity

### 5.0 Agent workspace (historical)

**NOT VERIFIED** from this agent workspace for API and cleanup.

Required evidence: run on the **staging service runtime**:

```sql
SELECT current_database() AS database_name,
       current_user AS database_user,
       inet_server_addr() AS server_address,
       inet_server_port() AS server_port;
```

This workspace has **no** Render Shell, **no** `render` CLI, **no**
`RENDER_API_KEY` / `RENDER_TOKEN`, **no** `STAGING_DATABASE_CONFIRM`,
and **no** staging `DATABASE_URL`.

Ambient agent `DATABASE_URL` (identity parse only; **not connected**):

`host=dpg-dbiqe70ae00c73cdif7g-a database=docuflow_db_q32a_7751`

That database name **starts with** the owner production name
`docuflow_db_q32a`. It does **not** equal
`docuflow_staging_db_ikpz`. Connecting would violate the production
exclusion. **STOP: not used.**

`/ready` `database=true` proves some PostgreSQL answered `SELECT 1`.
It does not prove database name, user, or Render resource.

### 5.1 Owner-provided API Shell identity — **PASS** (API only)

Classification: **PASS** — staging runtime database identity for
`docuflow-staging-api`. Evidence class: **OWNER-PROVIDED** (Render
Shell screenshots). Not independently re-run by this agent.

Service: `docuflow-staging-api` Render Shell. Read-only identity query.
One row.

| Field | Observed |
| --- | --- |
| Database | `docuflow_staging_db_ikpz` |
| Database user | `docuflow_staging_db_ikpz_user` |
| Server address | `10.26.149.13` |
| Port | `5432` |

The observed user is `docuflow_staging_db_ikpz_user`. The earlier
asserted user `docuflowstagingdb_hbnd_user` is **not** the actual
result and is not retained as observed identity.

This matches the expected staging **database name**. It does not by
itself prove the cleanup cron uses the same identity. Production
PostgreSQL was not queried.

## 6. Storage runtime identity

### 6.0 Agent workspace (historical)

**NOT VERIFIED** from this agent workspace for API and cleanup.

Allowed metadata is not readable here: `S3_BUCKET`, `S3_ENDPOINT_URL`,
`S3_ACCESS_KEY_ID`, `STORAGE_BACKEND`, `S3_REGION` are **UNSET** in
this environment. `S3_SECRET_ACCESS_KEY` was not read (unset).

`S3Storage.ping()` is `head_bucket(Bucket=self.bucket)`. HeadBucket
against `docuflowai-staging` was **NOT RUN** (no staging credentials).
Production bucket `docuflowai-documents` was **not** probed.

`/ready` `storage=true` proves a HeadBucket (or equivalent ping)
succeeded inside the live API process. It does not prove bucket name
`docuflowai-staging`, endpoint host, or key identity. Token scope
remains **OWNER-REPORTED** / **NOT VERIFIED**.

Repository note (no code change): `staging_checks.DEFAULT_PRODUCTION_BUCKETS`
is `{docuflow-documents}`. Owner production bucket is
`docuflowai-documents`. The validator would **not** treat the owner
production bucket name as a default production bucket. Live isolation
still requires reading the staging `S3_BUCKET` value.

### 6.1 Owner-provided API HeadBucket — **PASS** (bucket access, API only)

Classification: **PASS** — staging runtime bucket **access** for
`docuflow-staging-api`. Evidence class: **OWNER-PROVIDED** (Render
Shell screenshot of command and result). Not independently re-run by
this agent.

Visible command used boto3 and
`client.head_bucket(Bucket="docuflowai-staging")`.
Observed print: `PASS: HeadBucket docuflowai-staging`.

Owner also confirmed from the same service Shell (names only):
`S3_BUCKET=docuflowai-staging`.

This is access to the staging bucket name. It is **not** independent
proof that the token cannot access `docuflowai-documents`. Production
R2 was not probed. Cleanup service HeadBucket was **NOT RUN**.

## 7. Cross-service configuration

From `infra/render.staging.yaml` (**REPOSITORY VERIFIED**):

| Check | API | Cleanup |
| --- | --- | --- |
| `DATABASE_URL` | `fromDatabase: docuflow-staging-db` | same |
| `STORAGE_BACKEND` | `s3` | `s3` |
| S3 keys | `sync: false` (owner-supplied) | `fromService: docuflow-staging-api` |
| Production service names | absent | absent |
| Worker / Redis | absent | absent |

Live env values on Render were **not** readable. Cleanup cron was
**not** invoked (`python -m docuflow.cleanup` mutates jobs/storage).

## 8. Health, readiness, logs

Unauthenticated GET, `--max-redirs 0`, hostname
`docuflow-staging-api-350v.onrender.com` (staging-classified; no
production redirect).

| URL | Time (Asia/Jakarta) | HTTP | Body | Result |
| --- | --- | --- | --- | --- |
| `/health` | 12 Nov 2026, 17:14:02 | timeout 20s | none | cold-start |
| `/health` retry | 12 Nov 2026, 17:14:50 | 200 in 24.1s | `status=ok`, `service=docuflow-api` | **PASS** reachability |
| `/ready` | 12 Nov 2026, 17:15:16 | 200 in 0.67s | `status=ready`, `database=true`, `storage=true`, `redis=true`, `broker=inline`, `rq_workers=0` | **PASS** reachability |

`redis=true` with `broker=inline` is set without a Redis ping. Render
logs were **not** available (no dashboard/API). Log secret-leakage
review: **NOT VERIFIED**.

## 9. Evidence matrix

| Assertion | Result | Source class |
| --- | --- | --- |
| Staging Blueprint names isolated DB/API/cleanup, no prod services | **PASS** | REPOSITORY VERIFIED |
| Intended staging vs production DB/bucket **names** do not overlap | **PASS** | OWNER-PROVIDED names + repository resource names |
| Live API `current_database` = `docuflow_staging_db_ikpz` | **PASS** | OWNER-PROVIDED Shell screenshot |
| Live API `current_user` | **PASS** observed `docuflow_staging_db_ikpz_user` | OWNER-PROVIDED; prior asserted `docuflowstagingdb_hbnd_user` is not the actual result |
| Live cleanup uses the same staging DB identity | **NOT VERIFIED** | cron / cleanup Shell not entered |
| Live `S3_BUCKET` = `docuflowai-staging` | **PASS** | OWNER-PROVIDED Shell + HeadBucket |
| HeadBucket `docuflowai-staging` from API | **PASS** | OWNER-PROVIDED; one request |
| Live Access Key ID is the staging credential | **NOT VERIFIED** | key not printed; identity unread here |
| Token cannot access `docuflowai-documents` | **NOT VERIFIED** | production bucket not probed; exclusive scope not proven |
| `/health` HTTP 200 on `350v` | **PASS** | INDEPENDENTLY VERIFIED |
| `/ready` database+storage true | **PASS** reachability | INDEPENDENTLY VERIFIED; **not** isolation |
| Agent DSN is not staging | **PASS** (negative) | INDEPENDENTLY VERIFIED identity parse; no connect |

## 10. Production exclusion

- Production public hosts were not requested.
- Production PostgreSQL was not connected (agent ambient DSN rejected;
  owner identity query was on `docuflow-staging-api` only).
- Production R2 was not called. HeadBucket targeted
  `docuflowai-staging` only (owner-run; not repeated here).
- Production passwords, access keys, and secret keys were not printed.
- Production isolation was **not** independently tested.
- Not all possible cross-environment access paths are proven impossible.

## 11. Commands executed

```
git status --short
git fetch origin main
# redacted identity parse of ambient DATABASE_URL via database_identity()
# NO sqlalchemy/psycopg connect
curl --max-redirs 0 GET https://docuflow-staging-api-350v.onrender.com/health
curl --max-redirs 0 GET https://docuflow-staging-api-350v.onrender.com/ready
```

SQL identity `SELECT`: **NOT RUN** in this agent workspace.
Owner ran it in `docuflow-staging-api` Shell (screenshots; not repeated).
`head_bucket`: **NOT RUN** in this agent workspace.
Owner ran exactly one `HeadBucket(Bucket="docuflowai-staging")` in that
Shell (screenshot; not repeated).
`python -m docuflow.cleanup` / migrate: **NOT RUN**.

## 12. Mutations

None. No INSERT/UPDATE/DELETE, no object Put/Delete, no env changes,
no deploy, no credential rotation. No application code, Blueprint,
environment variable, database data, or storage object was modified.
The owner checks were read-only identity SQL and one HeadBucket.

## 13. Outstanding gaps (owner actions)

1. **G1 — Staging API DB identity.** **CLOSED** for the API process
   (owner Shell identity row; see §5.1).
2. **G2 — Staging cleanup DB identity.** Same identity query in the
   cleanup service runtime. Do **not** run `python -m docuflow.cleanup`.
3. **G3 — Staging R2 metadata.** `S3_BUCKET=docuflowai-staging` is
   owner-confirmed. Remaining: redacted endpoint host and masked access
   key if required for credential-identity records. Do not paste secrets.
4. **G4 — Token scope.** Cloudflare dashboard evidence that the staging
   token is limited to `docuflowai-staging`. HeadBucket success is not
   exclusive-scope proof. Production bucket must not be probed.
5. **G5 — API HeadBucket.** **CLOSED** for one owner-run
   `HeadBucket(Bucket="docuflowai-staging")` (see §6.1). Do not repeat
   against production. Cleanup HeadBucket remains **NOT VERIFIED**.

## 14. Final readiness decision

| Decision | Result |
| --- | --- |
| CONFIGURATION ISOLATION | **PASS** (template names + owner-named identities are distinct) |
| RUNTIME DATABASE ISOLATION | **PASS** for `docuflow-staging-api` (**OWNER-PROVIDED**). Cleanup: **NOT VERIFIED** |
| RUNTIME STORAGE ISOLATION | **PASS** for API HeadBucket access to `docuflowai-staging` (**OWNER-PROVIDED**). Exclusive token scope and cleanup: **NOT VERIFIED** |
| OVERALL RUNTIME ISOLATION | **NOT VERIFIED** (cleanup identity and exclusive R2 scope remain open; production isolation was not independently tested; not all cross-environment paths are proven impossible) |
| Functional smoke | **NOT AUTHORIZED** |
| Staging verification | **NOT COMPLETE** |
| Production verification | **NOT VERIFIED** |

Further staging tests require a **separate owner approval** after
reviewing this SR7 evidence. This audit does not authorize smoke,
uploads, jobs, or credit operations.
