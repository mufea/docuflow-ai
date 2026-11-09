# Business continuity and disaster recovery

Owner-led policy for DocuFlow production. **Not** an SLA. **Not** a
restore authorization.

Timezone: **Asia/Jakarta**. Record UTC too if the dashboard shows it.

Related:

- Objectives and gaps: `docs/reports/PHASE_9_18_BUSINESS_CONTINUITY_DR_OBJECTIVES.md`
- Incidents: `docs/runbooks/PRODUCTION_INCIDENT_RESPONSE.md`
- Database restore procedure: `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`
- Ops: `docs/OPERATIONS.md`

Do **not** open production DSN, restore into `docuflow-db`, cut over, or
provision infrastructure unless a **separate** approval line is on the
chat.

## Owner-approved targets

| Objective | Target | Capability |
| --- | --- | --- |
| Business RTO | **4 hours** | **NOT YET VERIFIED** |
| Business RPO | **24 hours** | **NOT YET VERIFIED** |

Isolated database restore last measured **15 minutes** (Phase 9.16 T0/T1).
That is **not** business RTO. Observed RPO is **NOT DETERMINABLE**. Phase
9.15 backup assurance is **still open**.

## Disaster definition

A **disaster** is a SEV-1 (or owner-elevated SEV-2) event where normal
incident response (restart, wait for Render, credential fix in dashboard)
cannot restore **critical business services** to a usable state, or where
data loss / corruption is suspected.

The **Business / Service Owner** declares or rejects. Technical operators
do not self-declare.

## RTO / RPO clocks

| Clock | Starts | Stops | Breach |
| --- | --- | --- | --- |
| Business RTO | Owner **declaration** timestamp | Owner confirms usable state: `/health` and `/ready` 200 with database+storage true, CMS reachable, critical workflows usable, no blocking integrity defect | Elapsed **> 4 hours** |
| Business RPO | Disaster time **or** owner recovery reference | Latest **consistent recoverable** data timestamp actually used | Restore point **> 24 hours** before that reference |

`/health` 200 or Postgres Available **does not** stop RTO.

Critical workflows: authentication, upload, inline processing, authorized
download, credit ledger remaining internally consistent.

## Recovery priorities

1. PostgreSQL (availability + recoverable state + schema/integrity).
2. API (process, DB, storage, auth, critical APIs). Inline jobs live here.
3. Object storage (required objects; no diagnostic uploads/deletes).
4. CMS / web access.
5. Cleanup cron and pending `storage_deletions` / job residuals.

Existing API, CMS, cron, and bucket are usually **reused**. Typical
technical recovery is **new isolated Postgres** then **owner-approved
cutover**. Redis/worker are absent by design.

## Authority

| Decision | Who |
| --- | --- |
| Declare disaster; RTO start | Owner |
| Recovery point; restore; replace DB; cut over | Owner |
| Customer communication; resumption (RTO stop) | Owner |
| Inspect, evidence, approved procedure, timeline | Technical operator |

## Continuity while down

**BUSINESS CONTINUITY MODE: CONTROLLED SERVICE SUSPENSION.**

No manual PDF processing, no hand-edited credits, no production SQL
workarounds, no laptop processing against production. Owner may scale
API/cron down to stop writes if corruption is ongoing.

## DR stages (policy)

1. **Detect** — preserve logs; classify using the incident runbook.
2. **Declare** — owner yes/no; record timestamp.
3. **Plan** — recovery points from dashboard (names/times only); estimate loss.
4. **Authorize** — procedure, point-in-time, new instance name, cutover yes/no.
5. **Validate isolated** — identity gate; schema; counts; FKs. Never use staging as a drill.
6. **Production recovery** — only a separate approval. Not implied here.
7. **Business validate** — critical workflows.
8. **Close** — RTO, RPO, downtime, residual risk, cleanup approval.

Render PITR: cannot restore inside the last **10 minutes**; blank target
means latest available — write that down for RPO.

## Evidence for any future exercise

Record exercise id, date, scope, environment, source, **recovery point
used**, T0/DB-ready/app-ready/business-ready/done, integrity results,
which RTO clock was used, RPO math, owner approvals, cleanup (`docuflow-db`
still present).

Do not run a drill from this page.
