# Phase 9.13B — PostgreSQL recovery drill readiness

Owner created the isolated restore instance and ran read-only SQL in its
PSQL prompt. **This agent did not click Restore** and did not connect to
the drill database. Production and staging were not modified. Production
`DATABASE_URL` was not cut over.

Time: **8 Nov 2026, 09:34 Asia/Jakarta (WIB)**.
Baseline `origin/main`: `018b34a`.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (gate + runbook + this report) | **YES** |
| LOCALLY VERIFIED | **YES** (`tests/test_phase913b_recovery_identity.py`, 9 passed) |
| OWNER VERIFIED (dashboard backup fields) | **PARTIAL** (restore-creates-new-instance **YES**; retention/PITR window still open) |
| IDENTITY GATE | **PASS** (`classification isolated-restore`) |
| SCHEMA / ALEMBIC SQL | **PASS** (`0003_cost_efficient_reliability`; required tables + index present) |
| INTEGRITY COUNTS | **PASS** (counts only; no row contents) |
| RESTORE DRILL VERIFIED | **YES** |
| PRODUCTION RECOVERY READY | **YES** (isolated restore procedure proven; **no** production cutover) |
| BLOCKED | None for the drill. Drill instance still bills until owner deletes it |

Authoritative product flags: STAGING VERIFIED **YES**; PRODUCTION VERIFIED
**YES**; RESTORE DRILL VERIFIED **YES**; PRODUCTION RECOVERY READY **YES**
(isolated restore only). Production cutover remains **unauthorized**.

## Audit answers

| Q | Answer |
| --- | --- |
| A. Was §5.1 strict enough? | **No.** An approved `restore`/`drill` name plus an unknown host could classify as `isolated-restore` without a dashboard hostname match. |
| B. Did it prove DSN host belongs to the approved service? | **No.** The DSN has no Render service name. |
| C. Could prod/staging be `isolated-restore`? | Known instance ids were rejected first. **Unknown** hosts could still pass. |
| D. Service vs instance vs hostname vs database? | Named in the runbook; the gate now requires `EXPECTED_RESTORE_HOSTNAME`. |
| E. `DEPLOYMENT.md` contradictions? | 9.13A aligned. 9.13B status: restore drill **VERIFIED**, recovery ready **YES** (no cutover). |
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

## Owner drill SQL (8 Nov 2026, 09:33 Asia/Jakarta)

Owner ran the read-only block in the **drill** PSQL prompt
(`docuflow_db_q32a_d7gs=>`). This agent did not connect. Prompt database
name matches the approved drill instance.

| Check | Result |
| --- | --- |
| `SELECT 1` | **1** |
| `current_database()` | `docuflow_db_q32a_d7gs` |
| `alembic_version` | `0003_cost_efficient_reliability` |
| Repo `alembic heads` (this environment, no DSN) | `0003_cost_efficient_reliability (head)` |
| `alembic current` CLI on drill | **NOT EXECUTED** (PSQL only; SQL version matches repo head) |
| Required tables | `users`, `documents`, `jobs`, `cleanup_leases`, `storage_deletions` **present** |
| Index `ix_storage_deletions_lease_until` | **present** |
| Public tables (15) | `alembic_version`, `audit_logs`, `cleanup_leases`, `credit_accounts`, `credit_ledger`, `documents`, `email_tokens`, `jobs`, `operation_costs`, `payment_events`, `plans`, `sessions`, `storage_deletions`, `subscriptions`, `users` |

Counts only (no row contents):

| Table / catalog | Count |
| --- | ---: |
| users | 2 |
| documents | 131 |
| jobs | 52 |
| credit_ledger | 142 |
| storage_deletions | 131 |
| cleanup_leases | 1 |
| foreign keys (public) | 7 |

Runbook §10 drill criteria: identity `isolated-restore`, not production DSN,
`SELECT 1`, Alembic `0003`, required tables, counts without error, production
API still on original `docuflow-db`. **All met.**

Production after SQL evidence (09:34 Asia/Jakarta): `GET https://docuflowai.site/health` HTTP 200 `service=docuflow-api`; `GET /ready` HTTP 200 `broker=inline` `rq_workers=0` `database=true` `storage=true`.

`python -m alembic current` was not run on the drill host. SQL
`alembic_version` matching repo heads is the evidence used.

Live production DSN was still not opened. Alembic on production at restore
point **22:25 on 7 Nov 2026** is inferred from this copy only.

Do not run `alembic upgrade` / `downgrade` / `stamp` /
`python -m docuflow.migrate` / `pg_restore` onto production, staging, or the
drill instance for this check.

## RTO/RPO evidence template (do not invent values)

```
Selected backup timestamp: 22:25 (owner-reported; recorded as 7 Nov 2026, 22:25 Asia/Jakarta)
Incident/reference timestamp: NOT PROVIDED (drill, not an incident)
Estimated RPO (backup time vs incident): NOT COMPUTED
Restore start (Asia/Jakarta): NOT PROVIDED
Database available (Asia/Jakarta): NOT PROVIDED (instance reported by owner 7 Nov 2026, 22:34)
Verification complete (Asia/Jakarta): 8 Nov 2026, 09:34
Total restore duration (RTO): NOT COMPUTED (start/available times not provided)
Schema result: alembic_version 0003_cost_efficient_reliability; required tables + ix_storage_deletions_lease_until present
Integrity result: users=2 documents=131 jobs=52 credit_ledger=142 storage_deletions=131 cleanup_leases=1 fk=7
R2 limitation: restored rows may reference objects not rolled back
```

Identity-gate PASS plus this SQL is the restore drill. RTO remains
unmeasured. Dashboard PITR/retention window remains **NOT VERIFIED**.
Production cutover was **not** performed.

## Cleanup (separate approval)

Do **not** delete automatically.

After evidence is recorded, production still uses `docuflow-db`, and no
service uses the drill DSN, owner may send:

`Delete docuflow-db-restore-drill-20261107`

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
