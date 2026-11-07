# Phase 9.13 — Production reliability and recovery audit

Read-only operational audit. **No** backup restore, **no** production SQL
writes, **no** Alembic upgrade/downgrade/stamp against production, **no**
plan or env changes, **no** paid provisioning, **no** application-code
changes.

Evidence time: **7 Nov 2026, 21:09 Asia/Jakarta (WIB)**.

## Executive summary

Phase 9.12 left production **functionally verified**. Phase 9.13 asks whether
that database can be **recovered**.

Owner-reported (Phase 9.11): `docuflow-db` is Render **Basic**, backups
**enabled**. That is **backup configured**, not restore-tested.

Repository Alembic is a single linear head `0003_cost_efficient_reliability`.
Production `alembic_version` was **not** inspected this phase (no safe DSN;
`ipAllowList: []`). Staging inspect (9.10D) is not production evidence.

An isolated restore drill is **designed** in
`docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`. It was **not**
executed. A second Postgres instance would bill until deleted; owner
approval is required.

| Classification | Status |
| --- | --- |
| IMPLEMENTED (audit + runbook) | **YES** (this PR) |
| LOCALLY VERIFIED | **YES** (Alembic heads/history; docs) |
| PRODUCTION CONFIGURATION VERIFIED | **PARTIAL** (owner: backups on; frequency/PITR/last backup **NOT VERIFIED**) |
| RECOVERY DRILL VERIFIED | **NO** |
| PRODUCTION RECOVERY READY | **NO** |

## Baseline commit

| Item | Value |
| --- | --- |
| Required baseline | `3f178af` (PR #24 merge) |
| `origin/main` at audit | `3f178af44ec4ef43949980471736252a55e97fdb` |
| Production API | `https://docuflowai.site` |
| Production CMS | `https://docuflowai.online` |
| Broker | inline; Redis/worker absent |
| Postgres | `docuflow-db` (`0.1c-256mb` / Basic), instance `dpg-dbiqe70ae00c73cdif7g-a` |
| Bucket | `docuflowai-documents` |

## Production architecture (unchanged)

Inline jobs in the Free API process. Cleanup cron every 15 minutes. S3/R2
for objects. Boot command still runs `python -m docuflow.migrate` (advisory
lock `86420138`) then uvicorn. That **can** upgrade schema on boot; this
phase did **not** trigger a deploy.

## Backup audit

| Question | Finding | Status |
| --- | --- | --- |
| Automated backups enabled | Owner (7 Nov, 17:23): **yes** | **OWNER VERIFIED** |
| Frequency | Typical Render Basic: daily logical backups. Dashboard not inspected here | **NOT VERIFIED** |
| Retention | Typical Basic: about 7 days. Confirm in dashboard | **NOT VERIFIED** |
| PITR | Typical Basic: **no** WAL PITR (Pro-class). Confirm | **NOT VERIFIED** |
| How restore starts | Render dashboard restore, usually a **new** Postgres instance | **NOT VERIFIED** (procedure documented) |
| Separate recovery DB | Yes — restore/provision a **new** name, never overwrite `docuflow-db` | Documented; **not provisioned** |
| Operator `pg_dump` cron | Not in Blueprint (by design) | **NOT APPLICABLE** |
| Backup available (list of restore points) | No timestamp list received | **NOT VERIFIED** |
| Restore tested | Not run | **NOT VERIFIED** |
| Recovery verified | Not run | **NOT VERIFIED** |

**Limitations of Render Basic (confirm on the live instance):** no Free-tier
expiry, managed backups exist, PITR often absent, restore granularity is
the last daily copy (RPO up to ~24h unless you also take `pg_dump`). Object
storage is a **separate** domain: a DB restore does not roll back R2.

## Alembic inspection

Local, no production connection:

```
uv run python -m alembic heads
→ 0003_cost_efficient_reliability (head)

uv run python -m alembic history
→ 0001_initial → 0002_runtime_reliability → 0003_cost_efficient_reliability
```

Single head. `EXPECTED_ALEMBIC_HEAD` in `src/docuflow/staging_checks.py`
matches. Chain: `0001` → `0002` → `0003`.

`alembic current` was **not** pointed at production. A local run used
`alembic.ini` (`127.0.0.1` dev placeholder) and failed auth there. That is
not a production error.

| Check | Result |
| --- | --- |
| Repo head | **VERIFIED** `0003_cost_efficient_reliability` |
| Multiple heads | **VERIFIED** none |
| Production `alembic_version` | **NOT VERIFIED** |
| Staging `alembic_version` (9.10D) | `0003` on `docuflow_staging_db` only |

Safe compare (owner, Render Shell on **production** API, SELECT only):
see runbook §8. Abort if host/name contains `staging`. Do **not** run
`alembic upgrade`, `downgrade`, `stamp`, or `python -m docuflow.migrate`
for this inspect.

## Recovery drill readiness

| Item | Status |
| --- | --- |
| Isolated target identified | New Render Postgres, name `docuflow-db-restore-drill` (or dated) |
| Isolation rules | Distinct DSN; do not change production `DATABASE_URL`; API/CMS stay on `docuflow-db` |
| Integrity checks | SELECT 1; `alembic_version`; required tables; `COUNT(*)` only |
| Cleanup | Delete the drill instance after evidence |
| Drill executed | **NO** — **BLOCKED** on owner approval (second DB costs money) |

## Reliability risks (document only)

| Risk | Impact | Note |
| --- | --- | --- |
| Basic backup RPO ~daily, likely no PITR | Up to ~24h data loss | Confirm dashboard |
| Restore untested | Unknown restore time / surprise | Drill required for READY |
| R2 not in Postgres dump | Restored rows can point at missing objects | Versioning **NOT VERIFIED** |
| Free API spin-down | In-flight **inline** jobs die; up to 100 `queued` re-enqueued on boot; `processing` wait stale cleanup | Accepted in 9.12 |
| Pool `pool_size=5` `max_overflow=10` | Fine for Free web; not HA | `src/docuflow/db.py` |
| Boot migrate | Accidental schema change on deploy | Do not deploy this phase |
| No independent monitoring | `/health` `/ready` only | Gap |
| Memory rate limiter | Resets on spin-down | Informational |

Do **not** add Redis or a worker in this phase.

## Outstanding owner actions

1. Dashboard (names only): last backup time, retention, PITR yes/no, restore
   creates a new instance yes/no.
2. Render Shell **read-only** inspect of production `alembic_version` (runbook §8).
3. If you want **RECOVERY DRILL VERIFIED**: authorize a **temporary extra**
   Basic Postgres restore target (will bill until deleted). This agent will
   **not** click Restore.

Do not paste DSNs or keys.

## Verification evidence

- `git` on `3f178af`; this phase is documentation-only after the audit.
- `uv run python -m alembic heads` / `history` as above.
- No production host mutations this phase.
- Gate 0 from 9.12A still stands; not re-probed (avoid extra production calls).

## Explicit limitations

- This environment has no Render dashboard and no production DSN.
- Owner “backups enabled” ≠ restorable.
- Staging Alembic inspect ≠ production.
- Counts on a restore DB must not dump customer rows into git/chat.

## Production safety confirmation

| Action | Occurred |
| --- | --- |
| Production modified | **NO** |
| Restore executed | **NO** |
| Paid resource provisioned | **NO** |
| Application code changed | **NO** |
| Production deployment | **NO** |
