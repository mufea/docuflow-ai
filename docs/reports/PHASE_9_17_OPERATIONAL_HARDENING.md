# Phase 9.17 — Production operational hardening

Documentation audit and runbooks only. **No** application code, Blueprint,
env, plan, restore, or alerting integration was changed. Production DSN was
not opened. Phase 9.15 was **not** closed.

Time: **9 Nov 2026, 18:49 Asia/Jakarta (WIB)** (`2026-11-09T18:49:00+07:00`).
Baseline `origin/main`: **`001fc4e`** (expected; confirmed).

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (audit + alerting matrix + incident runbook) | **YES** |
| LOCALLY VERIFIED | **YES** (git baseline, code/docs inspect, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| OWNER VERIFIED (dashboard metrics/alerts) | **NO** |
| INFRASTRUCTURE VERIFIED (new monitors) | **NOT EXECUTED** (none added) |
| ALERTS CONFIGURED | **NO** |

PHASE 9.17 IMPLEMENTATION: **COMPLETE** (documentation).
PHASE 9.17 ALERTING: **NOT EXECUTED** (specification only).

Preserved: 9.16 isolated restore **15 min** (owner T0/T1). Observed RPO
**NOT DETERMINABLE**. Business RTO **NOT ESTABLISHED**. 9.15 backup fields
remain open.

## 1. Executive summary

Production is an inline Free API + CMS + Basic Postgres + 15-minute cleanup
cron. Observability today is `/health` (liveness), `/ready` (database +
storage ping; Redis skipped in inline mode), JSON logs, and whatever Render
dashboard metrics the owner already has (**UNKNOWN** here). There is **no**
in-repo alerting, on-call, or backup-failure monitor.

A limited read-only probe at **18:49 Asia/Jakarta**: `/health` HTTP 200
(0.22s); `/ready` HTTP 200 `broker=inline` `rq_workers=0` `database=true`
`storage=true` (0.69s). HTTP 200 `/health` is not full business health.

Do **not** add Redis or a worker. Do **not** install paid APM.

## 2. Repository baseline

`001fc4e`. Reports reused: 9.15, 9.16, recovery runbook, `docs/OPERATIONS.md`.
Inspected: `src/docuflow/api/routes/health.py`, `infra/render.yaml`,
cleanup/storage notes in OPERATIONS.

## 3. Production architecture

| Piece | State | Evidence |
| --- | --- | --- |
| API | `https://docuflowai.site` Free web, `healthCheckPath=/health` | Blueprint + 9.12 |
| CMS | `https://docuflowai.online` | 9.12 |
| Postgres | `docuflow-db` `0.1c-256mb` | Owner / Blueprint |
| Broker | `JOB_BROKER=inline` | `/ready` + Blueprint |
| Redis / worker | **Absent by design** | Owner 9.11; not a defect |
| Cleanup | Cron `docuflow-cleanup` `*/15 * * * *` | Blueprint; owner “running” 9.11 |
| API in-process cleanup | `CLEANUP_INTERVAL_SECONDS=0` | Blueprint |

## 4. Observability audit

| Item | Classification | Evidence source |
| --- | --- | --- |
| API `/health` | **AVAILABLE** | `health.py`; live 18:49 |
| API `/ready` | **AVAILABLE** | `health.py`; live 18:49 |
| HTTP status (public) | **PARTIALLY AVAILABLE** | Endpoints exist; no SLO scrape in-repo |
| API latency | **PARTIALLY AVAILABLE** | This probe only (0.22s / 0.69s); no timeseries |
| Application error logs | **AVAILABLE** (platform) / **UNKNOWN** (retention/alerts) | `LOG_JSON=true`; Render logs not inspected |
| DB connection errors | **PARTIALLY AVAILABLE** | `/ready` `database`; `ready_database_failed` log |
| Storage failures | **PARTIALLY AVAILABLE** | `/ready` `storage`; TransientError classification in code |
| Job processing failures | **PARTIALLY AVAILABLE** | Job rows + admin; no alert |
| Cleanup cron execution | **PARTIALLY AVAILABLE** | Render Cron history **OWNER/UNKNOWN**; not read here |
| Cleanup cron failure visibility | **UNKNOWN** | Dashboard not inspected |
| Resource utilization | **UNKNOWN** | Render metrics not inspected |
| PostgreSQL availability | **PARTIALLY AVAILABLE** | `/ready` database true |
| DB storage capacity | **UNKNOWN** | No DSN; no dashboard |
| DB connection usage | **UNKNOWN** | Pool 5+10 in code; live usage unknown |
| Application restart events | **UNKNOWN** | Render events not inspected |
| Deployment failures | **UNKNOWN** | Dashboard not inspected |
| Backup/PITR failure alerts | **NOT AVAILABLE** in-repo | 9.15 still open |

## 5. Health and readiness

Code (`health.py`):

- `/health` — process up only. Render uses this path (spin-down/outage of
  dependencies will **not** mark the service fully dead).
- `/ready` — `SELECT 1`; `storage.ping()`; Redis ping **only** if
  `JOB_BROKER=rq`. Inline sets `redis=true` without pinging. `rq_workers`
  informational. HTTP 503 `status=degraded` if a required check fails.

Live **9 Nov 2026, 18:49 Asia/Jakarta** (this phase, one pair):

| Check | Result |
| --- | --- |
| `/health` | HTTP 200 `status=ok` `service=docuflow-api` ~0.22s |
| `/ready` | HTTP 200 `ready` database/storage true `broker=inline` `rq_workers=0` ~0.69s |

Historical **18:20** (9.16 post-delete) remains historical.

## 6. PostgreSQL monitoring

| Topic | Assessment |
| --- | --- |
| Availability | `/ready` database check **AVAILABLE** |
| Connections / CPU / disk | **UNKNOWN** (no dashboard; DSN prohibited) |
| Backups / PITR / retention | **PARTIALLY VERIFIED** via 9.15 owner screenshot (3-day window; export 7 Nov 5:27 PM). Latest restorable instant **UNKNOWN**. Schedule/enabled **NOT INDEPENDENTLY CAPTURED**. Phase 9.15 **not closed** |
| Backup failure visibility | **NOT AVAILABLE** in-repo |

Do not SQL production. Do not change plan or PITR.

## 7. Storage monitoring

S3/R2 via `STORAGE_BACKEND=s3`. `/ready` pings storage. Deletes go through
`storage_deletions` with leases, `STORAGE_DELETE_MAX_ATTEMPTS=8`, bounded
SDK retries (`docs/OPERATIONS.md`). No production upload/download/delete
this phase.

Gaps: no alert on repeated `storage_deletions` failures; orphan inventory
**NOT AVAILABLE** as a monitor; bucket versioning **NOT VERIFIED**.

## 8. Cleanup cron

| Field | Value | Class |
| --- | --- | --- |
| Schedule | `*/15 * * * *` | Blueprint |
| Command | `python -m docuflow.migrate && python -m docuflow.cleanup` | Blueprint |
| Last success | Owner 9.11 “is running”; last run **UNKNOWN** | OWNER-REPORTED / UNKNOWN |
| Overlap | `cleanup_leases` atomic acquire + renew | Code/docs |
| Duplicate HTTP trigger | Not on request path | OPERATIONS |
| Alerting | **NOT AVAILABLE** in-repo | |
| Manual trigger this phase | **NOT EXECUTED** | |

Cron `migrate` on each run uses the same advisory lock as API boot. That is
existing behavior, not changed here.

## 9. Inline broker

Jobs run in the API process. Postgres is source of truth. Claim is atomic
on `queued`. Credits: reserve/settle/refund idempotency keys. Stale
`processing` failed after `JOB_STALE_MINUTES=90` with refund. Free API
spin-down kills in-flight inline work; up to 100 `queued` re-enqueued on
boot. Absence of Redis/worker is **NOT APPLICABLE** as a defect.

Limits: shared CPU with HTTP; timeouts on large PDFs; no separate worker
metrics.

## 10. Alerting requirements matrix (proposed, not configured)

| Condition | Signal | Source | Severity | Response | Exists? | Extra cost? |
| --- | --- | --- | --- | --- | --- | --- |
| API unavailable | `/health` fail or Render down | Render health check | SEV-1 | Runbook scenario 1 | Render restart on `/health` only | Prefer existing |
| Readiness failure | `/ready` 503 | Manual/curl; no scrape | SEV-1/2 | Scenario 1 | **NO** auto-alert | External uptime = cost |
| DB unavailable | `/ready` database false; Render Postgres | Logs + dashboard | SEV-1 | Scenario 2; **no** restore without 9.13 procedure | **NO** | Dashboard only |
| Storage unavailable | `/ready` storage false | Logs | SEV-2 | Scenario 3 | **NO** | |
| Elevated errors | JSON error logs | Render logs | SEV-2 | Inspect logs | **UNKNOWN** | |
| Elevated latency | Not collected | — | SEV-3 | Measure if needed | **NO** | |
| Cleanup cron failure | Cron failed run | Render Cron | SEV-3 | Scenario 4; do not rerun without approval | **UNKNOWN** | |
| Repeated storage delete failures | `storage_deletions` attempts | Needs SQL/admin | SEV-3 | Scenario 3 | **NO** | DSN still prohibited |
| DB disk high | Render metric | Dashboard | SEV-2 | Owner; do not autoscale here | **UNKNOWN** | |
| Connection exhaustion | Pool errors in logs | Logs | SEV-2 | Scenario 2 | **NO** | |
| Backup/PITR gaps | 9.15 unknowns | Dashboard Recovery | SEV-4 | Complete 9.15 | **NO** | |
| Unexpected restart | Render events | Dashboard | SEV-3 | Correlate with spin-down | **UNKNOWN** | |
| Deploy failure | Render deploy | Dashboard | SEV-2 | Owner | **UNKNOWN** | |

Do **not** enable email/Slack/PagerDuty without owner approval. Do **not**
buy APM this phase.

## 11. Incident response readiness

New: `docs/runbooks/PRODUCTION_INCIDENT_RESPONSE.md`.
Existing short list in `docs/OPERATIONS.md` now points there.
DB restore remains `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`.

## 12. Recovery readiness

Unchanged from 9.16: isolated PITR **15 min** owner T0/T1; schema/counts
passed; drill deleted. Production still on `docuflow-db`. Business RTO
**NOT ESTABLISHED**. Observed RPO **NOT DETERMINABLE**. Live Alembic on
production DSN **NOT VERIFIED**.

## 13–14. Risks and recommended improvements

See risk register below. Lowest-cost next steps (owner):

1. Finish 9.15 Recovery-page paste (latest restorable time, schedule).
2. Confirm Render Cron last success for `docuflow-cleanup`.
3. Optional: one **external** HTTP uptime check on `/ready` (costs money if
   not already free). Do not add Redis/worker.
4. Agree a business RTO/RPO target separately (policy, not a measurement).

## 15. Cost implications

This phase: **zero** new services. Proposed alerts use existing Render
health/logs. Paid uptime or log drains are **owner-optional**. Second
Postgres for drills still bills only when a drill exists (none now).

## 16. Owner actions required

- Dashboard: cron last run; Postgres disk/connections (names only).
- Complete 9.15 fields if still missing.
- Approve any alert destination before configuration.
- Do not treat this spec as alerts already firing.

## Risk register

| Risk | Impact | Likelihood | Existing safeguard | Recommended action | Cost |
| --- | --- | --- | --- | --- | --- |
| No `/ready` alerting | Outage unnoticed until user report | Medium | Render `/health` keep-alive only | Optional external `/ready` check after approval | Low–paid |
| DB capacity unknown | Writes fail | Unknown | Basic plan; `/ready` | Owner reads disk metric | Free |
| Backup visibility gaps | Missed failed backup | Medium | 9.13B/9.16 drills; 3-day window owner-reported | Finish 9.15 | Free |
| PITR instant unknown | Wrong restore target | Medium | Owner picks time; 10-min rule | Record latest restorable time | Free |
| Observed RPO unknown | Cannot quote data-loss bound | Known gap | 3-day window is retention not RPO | Policy RPO + next drill timestamps | Free / drill bill |
| Business RTO unset | 15 min ≠ app recovery | Known | Isolated T0/T1 measured | Owner defines completion condition | Free |
| Storage failure visibility | Deletes stall | Low–med | `storage_deletions` + leases | Admin/log review; no prod mutate | Free |
| Cron failure visibility | Retention slips | Medium | Leases; 15-min schedule | Owner checks Cron history | Free |
| Inline jobs die on spin-down | In-flight work lost | Accepted | queued re-enqueue; stale fail+refund | Keep inline; document | None |
| No paging | Slow SEV-1 | High | Manual | Owner-approved notify later | Varies |

## Safety this phase

| Action | Occurred |
| --- | --- |
| Application code | **NO** |
| Production DSN / SQL | **NO** |
| Restore / cutover / env / plan | **NO** |
| New infrastructure | **NO** |
| Alerts enabled | **NO** |
| Live `/health` `/ready` | **YES** once (18:49) |
