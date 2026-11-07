# Production database recovery runbook

Operational procedure for `docuflow-db`. It is **not** proof that a restore
has been tested. Phase 9.13 status: drill **NOT VERIFIED**.

Never paste `DATABASE_URL`, passwords, or keys into chat, tickets, or git.

## 1. Recovery objectives and scope

| Objective | Target (until measured) |
| --- | --- |
| RPO | Last successful Render backup (often ~daily on Basic) plus any operator `pg_dump` |
| RTO | Hours: provision/restore a **new** DB, verify, then owner-approved cutover |
| In scope | PostgreSQL schema and rows on `docuflow-db` |
| Out of scope | R2/S3 object bytes, Redis (none), in-flight inline jobs, Render disk |

Three modes:

| Mode | Allowed here | Owner approval |
| --- | --- | --- |
| Read-only inspection | SELECT / `alembic current` / `alembic heads` | Low — still do not print secrets |
| Non-production restore | Restore into a **new** isolated Postgres | **Required** (costs money) |
| Production recovery | Point live API at a restored DB or rebuild `docuflow-db` | **Explicit**, separate from a drill |

## 2. Production infrastructure overview

| Piece | Value |
| --- | --- |
| API | `https://docuflowai.site` — `JOB_BROKER=inline` |
| CMS | `https://docuflowai.online` |
| Database service | `docuflow-db`, Postgres 16, plan `0.1c-256mb` (Basic) |
| Instance id (name only) | `dpg-dbiqe70ae00c73cdif7g-a` |
| Network | Private (`ipAllowList: []`). Laptop has no DSN path |
| Objects | Bucket `docuflowai-documents` (separate recovery domain) |
| Redis / worker | Absent |
| Cleanup | Render cron; `CLEANUP_INTERVAL_SECONDS=0` on API |
| Schema expected | Alembic head `0003_cost_efficient_reliability` |
| Boot migrate | `python -m docuflow.migrate && uvicorn …` (lock `86420138`) |

Blueprint `infra/render.yaml` still lists unused Free Redis. **Do not**
full-sync it as part of recovery.

## 3. Backup configuration verification

Dashboard on `docuflow-db` (record names/times only):

1. Plan is **not** Free.
2. Backups **enabled**.
3. Last backup timestamp.
4. Retention (days).
5. Point-in-time recovery **yes/no**.
6. Restore action creates a **new** database **yes/no**.

Owner previously: backups **yes** (7 Nov 2026, 17:23 Asia/Jakarta). Last
backup time, retention, and PITR remain **NOT VERIFIED**.

Optional extra copy (not required for this runbook): `pg_dump --format=custom`
from Render Shell, stored **outside** the instance. Do not put dumps in git.

## 4. Backup selection procedure

1. Identify the incident time (corruption, bad write, lost instance).
2. Pick the newest backup **strictly before** that time.
3. If only daily copies exist, accept RPO up to the backup interval.
4. Record backup id/timestamp in the incident note (no DSN).
5. Prefer restoring that copy onto a **new** instance. Do not restore over
   the only remaining production volume.

## 5. Isolated database provisioning

For a **drill** or a **safe** restore:

1. Create or restore into a new Render Postgres, suggested name
   `docuflow-db-restore-drill` (add a date if the name is taken).
2. Postgres 16. Same region as production if the UI offers it.
3. Do **not** attach this DSN to `docuflow-api` / `docuflow-web` /
   `docuflow-cleanup`.
4. Do **not** reuse production `DOCUFLOW_SECRET_KEY` on a public test API
   pointed at the drill DB.
5. Expect a **second Basic bill** until you delete the instance.

This agent must not click Create/Restore.

## 6. Restore procedure

### 6.1 Non-production drill (required before calling recovery verified)

1. Owner approval in chat: authorize isolated restore (new DB only).
2. Render → `docuflow-db` → backup/restore → **new** instance (not in-place).
3. Wait until the new DB is available.
4. Open a shell **on a service that uses the drill DSN only**, or the
   dashboard shell for that new database — **not** the production API if
   its `DATABASE_URL` still points at `docuflow-db` (see §8 for inspect
   SQL; point it at the drill URL).
5. Run §7–§9. Then §12 cleanup.

### 6.2 Production cutover (separate authorization)

Only if `docuflow-db` is gone or accepted as untrustworthy:

1. Freeze writers: scale API/web/cron to zero (owner).
2. Restore to a **new** instance as in 6.1.
3. Complete §7–§10 against that instance.
4. Point `DATABASE_URL` on API, web (`API_INTERNAL_URL` unchanged), and
   cleanup at the **new** internal DSN.
5. Boot API; `/health` and `/ready` must be 200 with `broker=inline`.
6. Keep the old instance (if it still exists) until the owner confirms;
   then snapshot/delete per Render.

**Never** `pg_restore` onto the live production database that still holds
the only copy.

Logical dump alternative (operator-owned file):

```bash
# Host and DB names only in logs. Auth via .pgpass / Render Shell env.
pg_restore --no-owner --no-acl --dbname DB --host HOST --port 5432 --username USER \
  docuflow-YYYYMMDDThhmmssZ.dump
```

## 7. Database connectivity verification

On the **target** (drill or new prod), print **host and database name only**:

```sql
SET statement_timeout = '5s';
SELECT 1;
SELECT current_database();
SELECT inet_server_addr();  -- optional; skip if noisy
```

Abort if the name/host contains `staging` when you intended production
recovery, or equals production `docuflow-db` when you intended a drill.

## 8. Schema and migration verification (read-only)

Expected: one row `0003_cost_efficient_reliability`. Repo command
(no DSN): `uv run python -m alembic heads`.

**Owner snippet** (Render Shell). Does not import `docuflow`. Does not
upgrade. Prints host, database, revision only:

```python
import os
from urllib.parse import urlparse
import psycopg

raw = os.environ["DATABASE_URL"]
parsed = urlparse(raw)
host = parsed.hostname or ""
name = (parsed.path or "/").lstrip("/")
print("host=", host)
print("database=", name)
if "staging" in host.lower() or "staging" in name.lower():
    raise SystemExit("stop: identity looks like staging")
with psycopg.connect(raw, connect_timeout=10) as conn:
    conn.execute("SET statement_timeout = '5s'")
    conn.execute("SELECT 1")
    print("select_1 ok")
    rows = [r[0] for r in conn.execute("SELECT version_num FROM alembic_version")]
    print("alembic_version", rows)
    print("matches_head", rows == ["0003_cost_efficient_reliability"])
```

Then, from the app directory if Alembic is installed, **read-only**:

```bash
python -m alembic heads
python -m alembic current
```

Do **not** run:

- `alembic upgrade` / `downgrade` / `stamp`
- `python -m docuflow.migrate`
- `STAGING_MIGRATE=1`

`scripts/staging_migrate_verify.py` **refuses production**. Do not override
that to inspect prod.

## 9. Data-integrity checks

Counts and catalog only. **Do not** `SELECT *` from `users` / `documents`
into chat or git.

```sql
SET statement_timeout = '15s';

SELECT table_name FROM information_schema.tables
 WHERE table_schema = 'public' ORDER BY 1;

SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM jobs;
SELECT COUNT(*) FROM credit_ledger;
SELECT COUNT(*) FROM storage_deletions;
SELECT COUNT(*) FROM cleanup_leases;

SELECT COUNT(*) FROM information_schema.table_constraints
 WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public';
```

Required tables (from `expected_schema_gaps`): `users`, `documents`,
`jobs`, `cleanup_leases`, `storage_deletions`. Index
`ix_storage_deletions_lease_until` should exist after `0003`.

Compare counts to a note taken **before** the incident if you have one.
Do not expect R2 objects to exist for every restored `storage_key`.

## 10. Recovery success criteria

Drill (non-production) **PASS** when all are true:

- Target is **not** the production API `DATABASE_URL`.
- `SELECT 1` succeeds.
- `alembic_version` is exactly `0003_cost_efficient_reliability`.
- Required tables exist; `alembic current` equals `alembic heads`.
- Counts return without error (values may be recorded as integers only).
- Production API/CMS still served from original `docuflow-db`.

Production cutover **PASS** additionally:

- `/health` 200 `docuflow-api`
- `/ready` 200 `broker=inline` database and storage true
- Owner confirms no staging names on the DSN host/database

## 11. Failure handling

| Symptom | Action |
| --- | --- |
| Restore instance never becomes ready | Leave production API on old DB; open Render support; do not stamp Alembic |
| `alembic_version` empty or wrong | Stop. Do not `stamp`. Restore an older backup onto another **new** DB |
| Missing tables | Wrong dump or incomplete restore; do not `upgrade` blindly on prod |
| `/ready` database false after cutover | Revert `DATABASE_URL` to previous instance if it still exists |
| Objects 404 after DB restore | R2 independent; restore objects from versioning if enabled (**NOT VERIFIED**) |

## 12. Rollback and cleanup

**Drill**

1. Do not point production at the drill DB.
2. Delete `docuflow-db-restore-drill` (or dated name) in Render after
   evidence is recorded.
3. Confirm production `/health` still 200.

**Failed production cutover**

1. Point `DATABASE_URL` back to the previous instance if it still exists.
2. Redeploy is **code** only; it will not undo SQL.

**Do not** `alembic downgrade` on production as a substitute for restore.

## 13. Security precautions

- Print host and database **names** only.
- Do not log `Location` signed URLs, cookies, or row contents.
- `ipAllowList: []` — do not open the DB to the public internet for a drill
  if a Render Shell on the **drill** instance is enough.
- Drill credentials must not be copied onto the public API.
- Rotate `DOCUFLOW_SECRET_KEY` only if it leaked; that invalidates sessions.

## 14. Owner approval requirements

| Action | Approval text (example) |
| --- | --- |
| Read-only prod Alembic inspect | `Authorize read-only alembic inspect on production API shell` |
| Isolated restore drill | `Authorize isolated restore drill into a new database, not production` |
| Production cutover | `Authorize production DATABASE_URL cutover to restored instance <name>` |
| Delete drill DB | `Delete docuflow-db-restore-drill` |

This agent will not restore or cut over without one of those lines.

## 15. Emergency escalation

1. Confirm the workspace is production (no `docuflow-staging-*`).
2. Freeze writers (scale API to zero) if corruption is ongoing.
3. Capture last known backup timestamp (dashboard).
4. Restore to a **new** instance; verify §7–§9.
5. Owner cutover (§6.2).
6. If Render backups are missing, fall back to operator `pg_dump` copies
   (may not exist).
7. Application/code rollback: previous Render deploy. Data: restore only.

Contacts stay with the owner. Do not publish DSNs in this file.
