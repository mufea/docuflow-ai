# Phase 9.13B — PostgreSQL recovery drill readiness

Owner created the isolated restore instance. **This agent did not click
Restore** and did not connect to the drill database. Production and staging
were not modified.

Time: **7 Nov 2026, 22:35 Asia/Jakarta (WIB)**.
Baseline `origin/main`: `018b34a`.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (gate + runbook + this report) | **YES** |
| LOCALLY VERIFIED | **YES** (`tests/test_phase913b_recovery_identity.py`, 9 passed) |
| OWNER VERIFIED (dashboard backup fields) | **PARTIAL** (restore time recorded; retention/PITR window still open) |
| IDENTITY GATE | **PASS** (`classification isolated-restore`) |
| SCHEMA / ALEMBIC SQL | **NOT EXECUTED** |
| INTEGRITY COUNTS | **NOT EXECUTED** |
| RESTORE DRILL VERIFIED | **NO** |
| PRODUCTION RECOVERY READY | **NO** |
| BLOCKED | Waiting on read-only SQL from the **drill** PSQL shell (not production) |

Authoritative product flags (9.12 / 9.13 / 9.13A): STAGING VERIFIED **YES**;
PRODUCTION VERIFIED **YES**; RECOVERY DRILL VERIFIED **NO**.

## Audit answers

| Q | Answer |
| --- | --- |
| A. Was §5.1 strict enough? | **No.** An approved `restore`/`drill` name plus an unknown host could classify as `isolated-restore` without a dashboard hostname match. |
| B. Did it prove DSN host belongs to the approved service? | **No.** The DSN has no Render service name. |
| C. Could prod/staging be `isolated-restore`? | Known instance ids were rejected first. **Unknown** hosts could still pass. |
| D. Service vs instance vs hostname vs database? | Named in the runbook; the gate now requires `EXPECTED_RESTORE_HOSTNAME`. |
| E. `DEPLOYMENT.md` contradictions? | 9.13A mostly aligned. Status table now states recovery drill **NOT VERIFIED** and recovery ready **NO**. |
| F. Backup details? | Restore-creates-new-instance **YES**. Retention, PITR window, and whether 22:25 is a PITR target still **NOT VERIFIED**. |

## Identity-gate improvements

`scripts/recovery_identity_gate.py` classifies **without connecting** and
without printing the DSN.

- Production service `docuflow-db` and instance `dpg-dbiqe70ae00c73cdif7g-a` → `production` (not a drill).
- Staging service/instance/`docuflow_staging_db` → `staging`.
- Invalid `RECOVERY_MODE` → STOP.
- Drill requires owner-approved name containing `restore` or `drill` **and**
  `EXPECTED_RESTORE_HOSTNAME` **and** DSN hostname match.
- Mismatch / missing expected host / missing hostname → `ambiguous` STOP.

## Owner backup evidence checklist (Render Dashboard)

Fill **names and timestamps only**. Do not paste URLs or passwords.

```
PostgreSQL service name: docuflow-db (source); docuflow-db-restore-drill-20261107 (restore)
Plan: NOT VERIFIED
Backups enabled (YES/NO): YES (restore succeeded)
Latest backup timestamp: 22:25 (owner-reported)
Retention: NOT VERIFIED
PITR (YES/NO): NOT DISTINGUISHED
Restore creates a new instance (YES/NO): YES
Production region: NOT VERIFIED
Intended restore-target region: NOT VERIFIED
```

Until this is filled, backup configuration is **not** fully verified.
Owner previously: backups enabled (9.11). Restore-creates-new-instance is
now **YES** (new hostname, distinct from production). Retention window and
whether 22:25 was a PITR target vs click time remain **NOT DISTINGUISHED**.

## Restore drill preflight (owner-controlled)

Proposed service name: `docuflow-db-restore-drill-YYYYMMDD`

Must be a **new** Postgres 16 service. Must not be `docuflow-db` or
`docuflow-staging-db`. Must not reuse production/staging `DATABASE_URL`.
Must not attach to API/web/cleanup. Must not reuse production app secrets.
Must keep `ipAllowList` private. Record hostname and database name.

A second Basic database **bills until deleted**.

This agent will **not** create, restore, or delete Render resources.

**Authorization required before any restore:**

```
Authorize isolated restore drill into a new database, not production
Approved service name: docuflow-db-restore-drill-YYYYMMDD
```

Owner (7 Nov 2026, **22:00 Asia/Jakarta**) sent the authorization line.
Placeholder `YYYYMMDD` is pinned to **20261107**.

Approved service name: **`docuflow-db-restore-drill-20261107`**.

This agent still **did not** click Restore and **cannot** provision Render
Postgres. The owner created the new service in the dashboard.

### Owner dashboard steps (you click Restore)

Workspace: production (has `docuflow-db`, **no** `docuflow-staging-*`).

1. Open `docuflow-db` → Backups.
2. Confirm backups exist. Record latest backup timestamp (names only).
3. Restore **into a new instance**, not in-place. Name it exactly
   `docuflow-db-restore-drill-20261107`.
4. Do **not** attach it to `docuflow-api`, `docuflow-web`, or
   `docuflow-cleanup`. Do **not** change production `DATABASE_URL`.
5. Keep the database private (`ipAllowList` empty / internal).
6. When it is available, copy from the **new** service only:
   - Render service name (must match)
   - Internal hostname (`dpg-…`)
   - Database name
   - Latest backup timestamp used
   - Restore start / available times (Asia/Jakarta)
7. Reply in chat with those **names and times only**. No DSN, no password.

Then this agent will run `scripts/recovery_identity_gate.py` instructions
against that hostname. If classification is not `isolated-restore`, STOP.

**Restore executed by this agent: NO.** Owner executed Restore in the
dashboard.

## Owner restore instance (7 Nov 2026, 22:34 Asia/Jakarta)

Names only. No DSN. No password.

| Field | Value |
| --- | --- |
| Service | `docuflow-db-restore-drill-20261107` |
| Hostname | `dpg-dbnk595g1s2s73cuafl0-a` |
| Database name | `docuflow_db_q32a_d7gs` |
| Backup/restore time used | **22:25** (owner-reported; timezone not stated; recorded as 7 Nov 2026, 22:25 Asia/Jakarta) |
| Distinct from production instance `dpg-dbiqe70ae00c73cdif7g-a` | **YES** |
| Distinct from staging instance `dpg-dbn71tec6qcc73cric9g-a` | **YES** |
| Database name is not `docuflow_staging_db` | **YES** |

Production still served from the original API after this restore (read-only
probe, 22:35 Asia/Jakarta): `GET https://docuflowai.site/health` HTTP 200
`service=docuflow-api`; `GET /ready` HTTP 200 `broker=inline` `rq_workers=0`
`database=true` `storage=true`.

## Identity gate (this environment, no connection)

Synthetic DSN used only to classify host + database name. Placeholder
password. Script does not connect.

```
RECOVERY_MODE=drill
OWNER_APPROVED_RECOVERY_TARGET=docuflow-db-restore-drill-20261107
EXPECTED_RESTORE_HOSTNAME=dpg-dbnk595g1s2s73cuafl0-a
host dpg-dbnk595g1s2s73cuafl0-a
database docuflow_db_q32a_d7gs
classification isolated-restore
proceed isolated-restore
exit 0
```

Negative checks (same expected host; wrong actual host):

- actual `dpg-dbiqe70ae00c73cdif7g-a` → `classification production` STOP exit 1
- actual `dpg-dbn71tec6qcc73cric9g-a` → `classification staging` STOP exit 1

Do **not** run §8–§9 SQL on production or staging.

## Remaining owner step: read-only SQL on the drill instance

Open **`docuflow-db-restore-drill-20261107`** (not `docuflow-db`) → Connect →
**PSQL**. Paste the block below. Reply with **labels and integers / names
only**. Do not paste DSN, password, user rows, or `SELECT *`.

```sql
SET statement_timeout = '15s';
SELECT 1;
SELECT current_database();
SELECT version_num FROM alembic_version;
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
SELECT indexname FROM pg_indexes
 WHERE schemaname = 'public'
   AND indexname = 'ix_storage_deletions_lease_until';
```

Paste back:

```
current_database:
alembic_version:
tables:
users:
documents:
jobs:
credit_ledger:
storage_deletions:
cleanup_leases:
fk_count:
ix_storage_deletions_lease_until: yes/no
restore_start (Asia/Jakarta, if known):
database_available (Asia/Jakarta, if known):
```

Expected Alembic head in this repo: `0003_cost_efficient_reliability`.
Do **not** assume production currently matches. Production Alembic remains
**NOT VERIFIED**.

Do not run `alembic upgrade` / `downgrade` / `stamp` /
`python -m docuflow.migrate` / `pg_restore` onto production, staging, or the
drill instance during this check.

## RTO/RPO evidence template (do not invent values)

```
Selected backup timestamp: 22:25 (owner-reported; date/timezone inferred 7 Nov 2026 Asia/Jakarta)
Incident/reference timestamp: NOT PROVIDED (drill, not an incident)
Estimated RPO (backup time vs incident): NOT COMPUTED
Restore start (Asia/Jakarta): NOT PROVIDED
Database available (Asia/Jakarta): NOT PROVIDED (instance reported by owner at 22:34)
Verification complete (Asia/Jakarta): NOT COMPLETE (SQL outstanding)
Total restore duration (RTO): NOT COMPUTED
Schema result (alembic_version / required tables): NOT EXECUTED
Integrity result (counts only): NOT EXECUTED
R2 limitation: restored rows may reference objects not rolled back
```

`SELECT 1` alone is **not** recovery readiness. Identity-gate PASS alone is
**not** recovery readiness.

## Cleanup (separate approval)

Do **not** delete automatically.

After evidence is recorded, production still uses `docuflow-db`, and no
service uses the drill DSN, owner may send:

`Delete docuflow-db-restore-drill-YYYYMMDD`

Do not delete production or staging databases.

## Safety

| Action | This phase |
| --- | --- |
| Restore executed by agent | **NO** |
| Restore executed by owner | **YES** (new instance `docuflow-db-restore-drill-20261107`) |
| Paid resource created by agent | **NO** |
| Production / staging modified | **NO** |
| Application code (API/models) | **NO** |
| Blueprint changed | **NO** |
| Deployment | **NO** |

## Files

- `scripts/recovery_identity_gate.py` (new)
- `tests/test_phase913b_recovery_identity.py` (new)
- `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`
- `docs/DEPLOYMENT.md` (status row)
- this report
