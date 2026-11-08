# Phase 9.14 — Recovery drill cleanup and evidence preservation

Documentation and owner-gated cleanup only. **This agent did not delete
any Render resource.** Production DSN was not opened. No application code
changed. Phase 9.15 (backup/PITR assurance) was **not** executed.

Time: **8 Nov 2026, 15:44 Asia/Jakarta (WIB)**.
Baseline `origin/main`: `b9e34f5` (PR #31 merged). Earlier 9.14 write-up
used `73b2bbe`.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (this report + status + owner procedure) | **YES** |
| LOCALLY VERIFIED | **YES** (git baseline, identity grep, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only; no suite required) |
| OWNER VERIFIED (delete confirmation line) | **YES** (8 Nov 2026, 15:44 Asia/Jakarta) |
| INFRASTRUCTURE VERIFIED (resource gone) | **NOT EXECUTED** |
| BLOCKED | Owner must click Delete in Render on the drill instance only, then report names/times |

PHASE 9.14 IMPLEMENTATION: **COMPLETE**.
PHASE 9.14 INFRASTRUCTURE CLEANUP: **BLOCKED / OWNER ACTION REQUIRED**
(dashboard click + gone-from-list evidence).

## 1. Recovery evidence audit (preserve 9.13B)

Source: `docs/reports/PHASE_9_13B_RECOVERY_DRILL_READINESS.md` on `73b2bbe`.
This phase does **not** rewrite that evidence.

| Required field | Present | Value / gap |
| --- | --- | --- |
| Drill date / timestamps | **PARTIAL** | Restore time used **22:25** (7 Nov 2026, Asia/Jakarta inferred). Instance reported **22:34**. SQL **8 Nov 2026, 09:33**. Restore start / available times **NOT PROVIDED**. RTO **NOT COMPUTED**. |
| Source database | **YES** | Service `docuflow-db`, instance `dpg-dbiqe70ae00c73cdif7g-a` |
| Isolated restore identity | **YES** | Service `docuflow-db-restore-drill-20261107`, instance `dpg-dbnk595g1s2s73cuafl0-a`, database `docuflow_db_q32a_d7gs` |
| Identity gate | **YES** | `classification isolated-restore` exit 0 |
| Alembic | **YES** | `0003_cost_efficient_reliability` (SQL on drill; matches repo heads) |
| Required tables | **YES** | `users`, `documents`, `jobs`, `cleanup_leases`, `storage_deletions` |
| Index | **YES** | `ix_storage_deletions_lease_until` |
| Record counts | **YES** | users 2, documents 131, jobs 52, credit_ledger 142, storage_deletions 131, cleanup_leases 1 |
| Foreign keys | **YES** | 7 |
| Production remained untouched | **YES** (procedure) | No cutover recorded. Live `/health` `/ready` stayed 200 after restore and after SQL. Live DSN **not** opened. |
| Known limitations | **YES** | Live prod Alembic inferred from copy; PITR/retention **NOT VERIFIED**; RTO untimed; R2 not rolled back with DB |
| Drill outcome | **YES** | RESTORE DRILL VERIFIED **YES**. PRODUCTION RECOVERY READY **YES** (isolated restore only) |

Evidence is already on `main` (PRs #28, #29, #30). Do not invent missing RTO or PITR.

## 2. Resource identity gate

Cleanup candidate **must** match all three:

| Field | Expected | Distinct from production |
| --- | --- | --- |
| Service | `docuflow-db-restore-drill-20261107` | Not `docuflow-db` |
| Instance | `dpg-dbnk595g1s2s73cuafl0-a` | Not `dpg-dbiqe70ae00c73cdif7g-a` |
| Database | `docuflow_db_q32a_d7gs` | Production database name **NOT VERIFIED** on live DSN |

Protected: `docuflow-db`. Staging (`docuflow-staging-db` /
`dpg-dbn71tec6qcc73cric9g-a` / `docuflow_staging_db`) is **not** a cleanup
target.

`infra/render.yaml` does **not** name the drill instance (grep). Identity
for cleanup: **PASS** (names from 9.13B owner evidence + git). This agent
has **no** Render dashboard; live presence of the drill instance is
**OWNER-REPORTED**, not independently verified here.

If any of the three identifiers differ in the dashboard, **STOP**. Do not
delete.

## 3. Cleanup readiness

| Check | Result | Evidence class |
| --- | --- | --- |
| Recovery drill complete | **YES** | Git: 9.13B on `73b2bbe` |
| Evidence preserved | **YES** | PRs #28–#30 merged to `main` |
| Restore instance not serving API/CMS | **LIKELY** | Independently: production `/health` `/ready` HTTP 200 at 15:31. Cutover never authorized. Dashboard `DATABASE_URL` host **UNKNOWN** (DSN not opened) |
| No app env points at drill | **LIKELY** | Repo Blueprint has no drill host. Agent never set Render env. Dashboard env **UNKNOWN** |
| No cron/worker depends on drill | **LIKELY** | Architecture: cleanup cron uses production DB; no worker. Dashboard **UNKNOWN** |
| No other active recovery on this instance | **YES** | This phase is cleanup of that drill only |
| Identity matches expected isolated restore | **YES** | All three identifiers match 9.13B |

Safe to **prepare** deletion. Not safe for **this agent** to delete.
Dashboard confirmation of “not attached” remains **UNKNOWN** until the
owner checks Connect / env on `docuflow-api`, `docuflow-web`, and
`docuflow-cleanup`.

## 4. Owner approval

| Approval | Status |
| --- | --- |
| Workflow (Phase 9.14 prompt) | **YES** (8 Nov 2026, 15:31 Asia/Jakarta) |
| Destructive delete line | **YES** — owner sent `Delete docuflow-db-restore-drill-20261107` at **15:44 Asia/Jakarta** |
| Dashboard Delete click | **NOT EXECUTED** (this agent cannot click Render) |

Production cutover remains **unauthorized**. This agent will **not** delete
the resource.

## 5. Owner-executable delete procedure

This agent will **not** click Delete.

Workspace: production (has `docuflow-db`). Do **not** open staging.

1. Confirm evidence is on `main` (`73b2bbe` or later) and this report exists.
2. Render Dashboard → PostgreSQL → find **`docuflow-db-restore-drill-20261107`**.
3. Open it. Confirm instance id **`dpg-dbnk595g1s2s73cuafl0-a`**.
4. Confirm database name **`docuflow_db_q32a_d7gs`** if shown.
5. Confirm it is **not** `docuflow-db` and **not** `dpg-dbiqe70ae00c73cdif7g-a`.
6. Check `docuflow-api`, `docuflow-web`, and `docuflow-cleanup` env: none
   use this hostname. If any does, **STOP**.
7. Delete line already received in chat (15:44 Asia/Jakarta).
8. Delete **only** `docuflow-db-restore-drill-20261107`.
9. Confirm that service is gone from the list.
10. Confirm **`docuflow-db`** is still listed.

Reply with names and times only (no DSN, no password):

```
deleted_service: docuflow-db-restore-drill-20261107
deleted_instance: dpg-dbnk595g1s2s73cuafl0-a
deleted_at (Asia/Jakarta):
docuflow-db still present: YES/NO
```

## 6. Post-cleanup verification (after owner report)

**NOT EXECUTED.** Delete line received. Dashboard click and
gone-from-list evidence are still outstanding.

After that report, this phase will record deletion time, then re-check
read-only `GET https://docuflowai.site/health` and `/ready`. Expected:
HTTP 200, `broker=inline`, `rq_workers=0`, `database=true`, `storage=true`.

Dashboard “resource gone” will remain **OWNER VERIFIED** unless this
environment gains Render access (it does not).

## 7. Production protection (this pass)

Independently verified **8 Nov 2026, 15:31 Asia/Jakarta** (read-only):

- `GET https://docuflowai.site/health` HTTP 200 `status=ok` `service=docuflow-api`
- `GET https://docuflowai.site/ready` HTTP 200 `broker=inline` `rq_workers=0`
  `database=true` `storage=true`

No uploads, downloads, SQL, or env changes.

## 8. Remaining risks / limitations

- Drill instance **still bills** until owner deletes it.
- Attachment of production `DATABASE_URL` is **UNKNOWN** without dashboard.
- Live production Alembic still inferred from the 9.13B copy.
- RTO / PITR / retention still **NOT VERIFIED** (Phase 9.15, not this phase).
- Deleting the drill does **not** change production backups or R2.

## 9. Files

- this report (new)
- `docs/IMPLEMENTATION_STATUS.md` (Phase 9.14 section)
- `docs/DEPLOYMENT.md` (cleanup status pointer)

No `apps/`, `src/`, migrations, Blueprint, or env changes.

## 10. Handoff — Phase 9.15 (not started)

Backup and PITR assurance on **`docuflow-db` only** (dashboard names):
automated backups, last restore point, retention window, PITR yes/no, RPO,
restore-creates-new-instance. No production cutover. No drill unless newly
authorized.
