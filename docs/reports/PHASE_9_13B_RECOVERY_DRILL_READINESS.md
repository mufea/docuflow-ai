# Phase 9.13B — PostgreSQL recovery drill readiness

Preparation only. **No restore executed.** **No paid instance created by
this agent.** Production and staging were not modified.

Time: **7 Nov 2026, 21:52 Asia/Jakarta (WIB)**.
Baseline `origin/main`: `018b34a`.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (gate + runbook + this report) | **YES** |
| LOCALLY VERIFIED | **YES** (`tests/test_phase913b_recovery_identity.py`, 9 passed) |
| OWNER VERIFIED (dashboard backup fields) | **NO** |
| RESTORE DRILL VERIFIED | **NO** |
| PRODUCTION RECOVERY READY | **NO** |
| BLOCKED | Owner authorized the drill (22:00 Asia/Jakarta). **Agent cannot click Restore.** Waiting on dashboard restore of `docuflow-db-restore-drill-20261107` plus hostname evidence |

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
| F. Backup details? | Retention, PITR, last backup, restore-creates-new-instance still **NOT VERIFIED**. |

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
PostgreSQL service name:
Plan:
Backups enabled (YES/NO):
Latest backup timestamp:
Retention:
PITR (YES/NO):
Restore creates a new instance (YES/NO):
Production region:
Intended restore-target region:
```

Until this is filled, backup configuration is **not** fully verified.
Owner previously: backups enabled (9.11). That does not prove restore.

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
Postgres. The owner must create/restore that **new** service in the
dashboard.

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

**Restore executed by this agent: NO.**

After the owner restores in the dashboard:

1. Copy hostname from the **new** service (not from production).
2. Run `scripts/recovery_identity_gate.py` with `RECOVERY_MODE=drill`.
3. STOP unless `classification isolated-restore`.
4. Use the **drill** shell only. Read-only `SELECT 1`, `current_database()`,
   `alembic_version`, table/index existence, `COUNT(*)` only, FK count.
5. Repo expected head: `0003_cost_efficient_reliability`. Do **not** assume
   production currently matches. Production Alembic remains **NOT VERIFIED**.
6. Do not run `alembic upgrade` / `downgrade` / `stamp` /
   `python -m docuflow.migrate` / `pg_restore` onto production or staging.

## RTO/RPO evidence template (do not invent values)

```
Selected backup timestamp:
Incident/reference timestamp:
Estimated RPO (backup time vs incident):
Restore start (Asia/Jakarta):
Database available (Asia/Jakarta):
Verification complete (Asia/Jakarta):
Total restore duration (RTO):
Schema result (alembic_version / required tables):
Integrity result (counts only):
R2 limitation: restored rows may reference objects not rolled back
```

`SELECT 1` alone is **not** recovery readiness.

## Cleanup (separate approval)

Do **not** delete automatically.

After evidence is recorded, production still uses `docuflow-db`, and no
service uses the drill DSN, owner may send:

`Delete docuflow-db-restore-drill-YYYYMMDD`

Do not delete production or staging databases.

## Safety

| Action | This phase |
| --- | --- |
| Restore executed | **NO** |
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
