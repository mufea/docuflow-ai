# Phase 10.4B-SR7 — Runtime database and object storage isolation

Read-only. Time: **12 Nov 2026, 17:15 Asia/Jakarta (WIB)**.
No application-code change. No Blueprint sync. No deploy, migrate,
cleanup, HeadBucket from this workspace, SQL connect, object write, or
functional smoke.

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
| `origin/main` | `7700188264fc151cad9e8cbf9505c1e4839f789d` (PR [#81](https://github.com/mufea/docuflow-ai/pull/81) merge) |
| Main CI | [43181164350](https://github.com/mufea/docuflow-ai/actions/runs/43181164350) **SUCCESS** (**12 Nov 2026, 15:15 Asia/Jakarta**) |
| Auditor | Cursor Agent (this workspace) |
| Authorized owner | EDY ALAMSAH (**owner-reported**) |

`src/` and `infra/` are unchanged vs the 10.4B-S safety audit.

## 3. Services inspected

| Service | Architecture | Inspected how |
| --- | --- | --- |
| `docuflow-staging-api` | Free web, `JOB_BROKER=inline` | Blueprint + public GET |
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
| Staging Postgres | `docuflow-staging-db` | `docuflow_staging_db_ikpz` / `docuflowstagingdb_hbnd_user` |
| Production Postgres | `docuflow-db` | `docuflow_db_q32a` / `docuflow_db_q32a_user` |
| Staging R2 | `docuflowai-staging` | staging Access Key ID (owner-confirmed; **not** present here) |
| Production R2 | `docuflowai-documents` | **not retrieved** |

Production DSN, production passwords, and production storage secrets
were **not** read.

## 5. Database runtime identity

**NOT VERIFIED** for both API and cleanup.

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

## 6. Storage runtime identity

**NOT VERIFIED** for API and cleanup.

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
| Live API `current_database` = `docuflow_staging_db_ikpz` | **NOT VERIFIED** | Render Shell missing |
| Live API `current_user` = `docuflowstagingdb_hbnd_user` | **NOT VERIFIED** | Render Shell missing |
| Live cleanup uses the same staging DB identity | **NOT VERIFIED** | cron not entered |
| Live `S3_BUCKET` = `docuflowai-staging` | **NOT VERIFIED** | env unread; HeadBucket not run |
| Live Access Key ID is the staging credential | **NOT VERIFIED** | key unset here |
| Token cannot access `docuflowai-documents` | **NOT VERIFIED** | no dashboard; production bucket not probed |
| `/health` HTTP 200 on `350v` | **PASS** | INDEPENDENTLY VERIFIED |
| `/ready` database+storage true | **PASS** reachability | INDEPENDENTLY VERIFIED; **not** isolation |
| Agent DSN is not staging | **PASS** (negative) | INDEPENDENTLY VERIFIED identity parse; no connect |

## 10. Production exclusion

- Production public hosts were not requested.
- Production PostgreSQL was not connected.
- Production `DATABASE_URL` was not read as a staging DSN (ambient agent
  URL was identity-parsed only and **rejected**).
- Production R2 was not called.
- Production passwords, access keys, and secret keys were not printed.

## 11. Commands executed

```
git status --short
git fetch origin main
# redacted identity parse of ambient DATABASE_URL via database_identity()
# NO sqlalchemy/psycopg connect
curl --max-redirs 0 GET https://docuflow-staging-api-350v.onrender.com/health
curl --max-redirs 0 GET https://docuflow-staging-api-350v.onrender.com/ready
```

SQL identity `SELECT`: **NOT RUN**.
`head_bucket`: **NOT RUN** from this workspace.
`python -m docuflow.cleanup` / migrate: **NOT RUN**.

## 12. Mutations

None. No INSERT/UPDATE/DELETE, no object Put/Delete, no env changes,
no deploy, no credential rotation.

## 13. Outstanding gaps (owner actions)

1. **G1 — Staging API DB identity.** On Render Shell for
   `docuflow-staging-api`, run only the identity `SELECT` above. Record
   database_name / database_user / host label. Do not paste `DATABASE_URL`.
   Separate authorization: **yes** for Shell; **no** extra product change.
2. **G2 — Staging cleanup DB identity.** Same query in the cleanup
   service runtime (or a one-off Shell with the cleanup env). Do **not**
   run `python -m docuflow.cleanup`.
3. **G3 — Staging R2 metadata.** Redacted screenshot or owner transcript
   of `STORAGE_BACKEND`, `S3_BUCKET`, `S3_ENDPOINT_URL` host, masked
   `S3_ACCESS_KEY_ID` (first/last 4 only). Confirm `S3_BUCKET` is
   `docuflowai-staging` and not `docuflowai-documents`.
4. **G4 — Token scope.** Cloudflare dashboard evidence that the staging
   token is limited to `docuflowai-staging`.
5. **G5 — Optional HeadBucket.** Only after G3, from the **staging API
   runtime** (existing `ping()`), not from this agent and not against
   production.

## 14. Final readiness decision

| Decision | Result |
| --- | --- |
| CONFIGURATION ISOLATION | **PASS** (template + owner-named identities are distinct; live values unread) |
| RUNTIME DATABASE ISOLATION | **NOT VERIFIED** |
| RUNTIME STORAGE ISOLATION | **NOT VERIFIED** |
| OVERALL RUNTIME ISOLATION | **NOT VERIFIED** |
| Functional smoke | **NOT AUTHORIZED** |
| Staging verification | **NOT COMPLETE** |
| Production verification | **NOT VERIFIED** |

Further staging tests require a **separate owner approval** after
reviewing this SR7 evidence. This audit does not authorize smoke,
uploads, jobs, or credit operations.
