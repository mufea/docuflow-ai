# Recovery readiness checklist

Operator checklist for DocuFlow production. **Not** authorization to
restore or cut over. **Not** a DR certification.

Timezone: **Asia/Jakarta**. Record UTC if the dashboard shows it.

Related: `docs/reports/PHASE_9_19_RECOVERY_CAPABILITY_GAP_ASSESSMENT.md`,
`docs/runbooks/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md`,
`docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`,
`docs/runbooks/PRODUCTION_INCIDENT_RESPONSE.md`.

Do **not** open production DSN, click Restore, Create export, Delete, or
change env/plan unless a **separate** approval line names that action.

Steps marked **NOT EXECUTED** were not performed in Phase 9.19.

## Owner pre-incident

- [ ] Treat business RTO **4 hours** and RPO **24 hours** as objectives, not SLAs. (**DOCUMENTED** 9.18)
- [ ] Complete Phase 9.15 Recovery-page fields for `docuflow-db` (schedule, enabled, latest restorable timestamp + timezone). **NOT EXECUTED** — 9.15 **OPEN**
- [ ] Confirm identity: production is `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a`. Staging and deleted drills are **not** production.
- [ ] Optional: name Business Owner and Technical Operator. **NOT EXECUTED** (roles only)
- [ ] Do not enable alerts until a destination is approved. Alerting **NOT EXECUTED** (9.17)

## Recovery evidence to keep

For any future **approved** exercise record: id, date, scope, environment
(`isolated-restore` vs production), source, **recovery point used**,
declaration/T0, DB-ready, app-ready, business-ready, done, integrity
results, which RTO clock, RPO math, approvals, cleanup (`docuflow-db`
still present).

9.16 preserved: isolated restore **15 minutes**; observed RPO **NOT
DETERMINABLE**; production not cut over. **Do not** reuse those clocks as
business RTO.

## Disaster declaration

- [ ] Incident classified (incident runbook). Detection **does not** start RTO unless owner backdates.
- [ ] Owner **declares** or rejects. Record declaration timestamp. **RTO start.**
- [ ] Continuity mode until reopen: **controlled service suspension** (no manual PDF/credit/SQL workarounds).

**NOT EXECUTED** (no disaster in 9.19).

## Recovery authorization (separate from this page)

Required before restore: procedure, recovery point, **new** instance name
containing `restore` or `drill` (never `staging`, never `docuflow-db`),
whether cutover is in scope. Cutover is **never** implied.

**NOT EXECUTED.**

## Recovery-point selection

- [ ] Read Recovery page times only (no DSN).
- [ ] Prefer newest consistent point **before** the incident and **≥ 10 minutes** ago.
- [ ] If the UI target is blank, latest available is used — write that down (RPO otherwise **NOT DETERMINABLE**).
- [ ] Latest restorable instant is currently **UNKNOWN** (9.15).

**NOT EXECUTED.**

## Recovery stages

Use the recovery runbook for identity gate and isolated SQL. Production
restore/cutover remains **blocked** without new approval.

| Stage | Check | 9.19 |
| --- | --- | --- |
| Isolated provision | New instance; DSN **not** attached to API/CMS/cron | **NOT EXECUTED** |
| Identity gate | Host/db match approved drill; not prod/staging | **NOT EXECUTED** |
| DB integrity | Below | **NOT EXECUTED** |
| Storage | Below | **NOT EXECUTED** |
| API / CMS | Below | **NOT EXECUTED** |
| Inline jobs | Below | **NOT EXECUTED** |
| Cleanup cron | Below | **NOT EXECUTED** |
| Workflows | Below | **NOT EXECUTED** |
| Reopen | Owner stop-clock | **NOT EXECUTED** |

## Database integrity (isolated DSN only)

After identity **PASS**, on the **drill** database only:

- [ ] `SELECT 1`
- [ ] `current_database()` matches approved drill name
- [ ] `alembic_version` equals repo head (`0003_cost_efficient_reliability` at 9.16)
- [ ] Required tables: `users`, `documents`, `jobs`, `cleanup_leases`, `storage_deletions`
- [ ] Index `ix_storage_deletions_lease_until` if head is 0003
- [ ] Foreign-key count recorded
- [ ] Do **not** `upgrade` / `stamp` / migrate

Live production Alembic via production DSN: **NOT independently verified**.
Do not open production DSN from this checklist.

**NOT EXECUTED** in 9.19.

## Storage consistency

- [ ] `/ready` `storage=true` (read-only) after API points at the intended DB — only if that API is **not** production unless cutover was approved
- [ ] DB object keys are **not** proof that bytes exist
- [ ] No production upload/download/delete for diagnosis

**NOT EXECUTED.**

## API / frontend

- [ ] `GET https://docuflowai.site/health` — process only
- [ ] `GET https://docuflowai.site/ready` — database + storage; inline `redis=true` is **not** a Redis ping
- [ ] CMS `https://docuflowai.online` HTTP GET
- [ ] Historical 18:49 9 Nov 2026 probe is **not** current

**NOT EXECUTED** in 9.19.

## Inline jobs

- [ ] `JOB_BROKER=inline`; no Redis/worker expected
- [ ] `queued` may re-enqueue on boot (up to 100); `processing` stale-fail + refund after `JOB_STALE_MINUTES`
- [ ] In-flight work on a dead API process is lost (accepted)
- [ ] Do not enqueue production jobs for a drill

**NOT EXECUTED.**

## Cleanup cron

- [ ] `docuflow-cleanup` `*/15 * * * *` — last run result from dashboard
- [ ] Overlap protected by `cleanup_leases`
- [ ] Do **not** manually run production cleanup

**NOT EXECUTED.** Last success **UNKNOWN**.

## Critical business workflows

Usable state (9.18): sign-in, upload, inline process, authorized download,
credit reserve/settle/refund internally consistent.

Mutating checks against production need **separate** approval and must not
put passwords in git. 9.12 functional PASS is **not** a DR rehearsal.

**NOT EXECUTED.**

## Service reopening

- [ ] Owner confirms stop-clock criteria
- [ ] Record RTO (declaration → acceptance) and RPO (reference − restore point used)
- [ ] Residual risks (missing objects, unknown RPO, etc.)
- [ ] Isolated extras deleted only with a **delete** approval; `docuflow-db` still present

**NOT EXECUTED.**

## Incident closure and evidence retention

Keep clocks, service/instance/database **names**, integrity labels, and
approvals in the phase report. **No** DSNs, passwords, row dumps, or
Connect URLs in git.

Phase 9.19 performed **none** of the restore/cutover/workflow steps above.
