# Phase 9.18 — Business continuity and DR objectives

Owner-led **policy** phase. **No** restore, cutover, DSN, SQL, application
code, plan change, or new infrastructure. Phase 9.15 was **not** closed.
Phase 9.16 evidence is **preserved**, not re-measured.

Time: **9 Nov 2026, 19:30 Asia/Jakarta (WIB)** (`2026-11-09T19:30:00+07:00`).
Baseline `origin/main`: **`6274c73`** (PR #36 merge; expected).

Policy runbook: `docs/runbooks/BUSINESS_CONTINUITY_AND_DISASTER_RECOVERY.md`.
Database procedure: `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`.
Incidents: `docs/runbooks/PRODUCTION_INCIDENT_RESPONSE.md`.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (policy + runbook) | **YES** |
| OWNER APPROVED (business RTO 4 h / RPO 24 h) | **YES** (this prompt) |
| LOCALLY VERIFIED | **YES** (git baseline, docs inspect, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| EVIDENCE VERIFIED (end-to-end business recovery) | **NO** |
| INFRASTRUCTURE VERIFIED (new DR stack) | **NOT EXECUTED** (none added) |
| ALERTS CONFIGURED | **NO** (9.17 alerting **NOT EXECUTED**) |

PHASE 9.18 IMPLEMENTATION: **COMPLETE** (documentation).
BUSINESS RTO TARGET: **OWNER APPROVED — 4 HOURS**.
BUSINESS RTO CAPABILITY: **NOT YET VERIFIED**.
BUSINESS RPO TARGET: **OWNER APPROVED — 24 HOURS**.
BUSINESS RPO CAPABILITY: **NOT YET VERIFIED**.
BACKUP ASSURANCE COMPLETE: **NO** (9.15 still open).

Preserved: 9.16 isolated restore **15 minutes** (owner T0 17:50 → T1 18:05).
Observed RPO **NOT DETERMINABLE**. Production DSN **never opened**. Live
production Alembic via DSN **NOT independently verified**.

## 1. Executive summary

DocuFlow production is an inline Free API + CMS + Basic Postgres
(`docuflow-db` `0.1c-256mb`) + object storage + 15-minute cleanup cron.
Redis and a separate worker are **absent by design**.

The owner approved **business** targets of **4-hour RTO** and **24-hour
RPO**. Those are objectives, **not** SLAs and **not** proven capabilities.
The only timed recovery evidence is an **isolated** database restore
(9.16). That 15-minute interval is one technical stage. It does **not**
equal business recovery.

While primary services are down, the safe continuity mode is **controlled
service suspension**. There is no supported manual processing path.

Do **not** add Redis, a worker, a second always-on database, or paid
monitoring for this policy. Close remaining 9.15 backup fields before
claiming the 24-hour RPO is technically achievable.

## 2. Owner-approved business targets

| Objective | Business target | Technical evidence | Status |
| --- | --- | --- | --- |
| Business RTO | **4 hours** | 9.16 isolated restore only (15 min T0/T1) | Target **OWNER APPROVED**; capability **NOT YET VERIFIED** |
| Business RPO | **24 hours** | Latest restorable PITR instant **UNKNOWN** (9.15 open) | Target **OWNER APPROVED**; capability **NOT YET VERIFIED** |
| Production availability | Business-defined (not an RTO/RPO number) | Historical `/health` `/ready` 18:49 9 Nov 2026 | Not a recovery objective |
| Data integrity | No unacceptable corruption | Isolated schema/count validation (9.13B, 9.16) | **PARTIAL** evidence (drill copies, not live prod DSN) |

These targets are **not** silently redefined below. Clarifications that
do **not** change the numbers:

- Isolated restore duration ≠ business RTO.
- PITR **window** (owner-reported 3 days) ≠ RPO.
- Logical export success ≠ a measured RPO.
- Database Available ≠ business recovery complete.

## 3. RTO definition

**Business RTO (approved):** 4 hours.

Maximum acceptable elapsed time from **formal declaration** of a
business-impacting disaster until **defined critical business services**
are restored to an **agreed usable operating state**.

| Clock | Rule |
| --- | --- |
| Start | Owner **declares** a disaster. Record Asia/Jakarta (and UTC if the dashboard shows it). Detection time is **not** the start unless the owner says the declaration is retroactive. |
| Stop | Owner confirms resumption: API `/health` and `/ready` HTTP 200 with `database=true` and `storage=true`, CMS reachable, critical workflows usable (see §5), no unresolved integrity defect the owner treats as blocking. |
| Not stop | Render Postgres “Available” alone; isolated drill success; `/health` 200 without `/ready`; storage ping without document access. |

Unmeasured stages between start and stop still count toward the 4 hours
(§12).

## 4. RPO definition

**Business RPO (approved):** 24 hours.

Maximum acceptable data-loss window between the disaster event **or** the
agreed recovery reference timestamp and the **latest consistent recoverable
business data**.

| Item | Rule |
| --- | --- |
| Clock | Use a named timestamp: incident time **or** owner-chosen recovery reference, **and** the restore point actually used (PITR instant or export time). |
| Breach | Recoverable consistent data is **older than 24 hours** before that reference. |
| Not proof | Backup retention window; PITR availability window; “backups enabled”; a successful logical export without its timestamp compared to the incident. |

BUSINESS RPO TARGET = 24 HOURS.
TECHNICAL RPO CAPABILITY = NOT VERIFIED.

Latest restorable PITR timestamp is **UNKNOWN**. Observed RPO remains
**NOT DETERMINABLE**.

## 5. Recovery scope

**In scope (critical business services):**

| Service | Required for “usable” |
| --- | --- |
| PostgreSQL `docuflow-db` | Schema/data recoverable; identity is production only after **separate** cutover approval |
| API `https://docuflowai.site` | Process up; DB + storage connectivity; authn/authz |
| Object storage | Required document objects reachable for download/process |
| CMS `https://docuflowai.online` | User-facing access to critical workflows |

**Critical workflows (usable operating state):** sign-in / session;
upload; inline job processing; download of existing authorized objects;
credit reserve/settle/refund remaining consistent with ledger rules.

**Out of scope / not required to stop the RTO clock:** Redis, dedicated
worker, admin convenience, non-critical CMS marketing pages, staging,
deleted drill instances.

**Not restored by a Postgres PITR:** object-storage bytes; in-flight
inline jobs killed with the API process; Render instance disk.

Historical production probe (**not** current health): 9 Nov 2026, 18:49
Asia/Jakarta — `/health` 200, `/ready` 200 `broker=inline` `rq_workers=0`
`database=true` `storage=true`.

## 6. Service recovery priorities

Evaluated against the **current** inline architecture. Sequence is
appropriate. Not every layer needs a separate restore: normally restore
**Postgres into a new instance**, validate, then owner-approved cutover
of the **existing** API / CMS / cron / bucket.

| Priority | Service | Why this order |
| --- | --- | --- |
| 1 | PostgreSQL | Jobs, credits, documents metadata, leases live here. API and cron cannot be healthy without it. |
| 2 | API | Inline jobs run in-process. Auth and critical APIs sit here. Depends on DB + storage. |
| 3 | Object storage | Document bytes. Can be **checked in parallel** with API boot (`/ready` storage; no production mutate). |
| 4 | CMS / web | User access. Depends on API. Can stay up showing errors; recovery still incomplete until API+DB+storage work. |
| 5 | Background ops | Cleanup cron `*/15`; pending `storage_deletions`; inline job residual (`queued` re-enqueue, stale fail+refund). After user-facing path works. |

Absence of Redis/worker is **NOT APPLICABLE** as a recovery defect.

## 7. Recovery dependencies

```
PostgreSQL ──► API (inline jobs) ──► CMS
     │              ▲
     │              │
     └── storage ping / object bytes ──► API + cleanup cron
Cleanup cron ──► PostgreSQL + object storage
```

| Parallel (after authorization) | Serial |
| --- | --- |
| Preserve logs; owner reads Recovery page (names/times only) | Disaster declaration |
| Schema SQL on **isolated** restore only | Isolated restore provision (billable) |
| Storage reachability check (no uploads/deletes) | Production cutover (separate approval) |
| CMS HTTP check | Owner resumption decision |

Do not attach a drill DSN to production API/CMS/cron.

## 8. Decision authority

Role-based until named individuals are assigned. **Do not invent names.**

| Role | Responsibilities |
| --- | --- |
| Business / Service Owner | Declare or reject disaster; approve recovery actions and downtime; approve communications; approve production restore, recovery point, target instance, and cutover; approve resumption. |
| Technical Operator | Inspect status; collect evidence; execute **approved** procedures; validate integrity; keep the timeline; report blockers. Does **not** declare disaster, cut over, or restore production without owner approval. |

**Recovery decision authority (owner retains):** disaster declaration;
production restore; recovery point; production database replacement;
production cutover; customer communication; service resumption.

Agents and operators must not click Restore/Delete/Create, open production
DSN, or rotate credentials unless a **separate** approval line exists.

## 9. Incident escalation matrix

Classifications are **proposed** unless the owner already adopted the
9.17 set. Alert **notifications are not configured** (9.17 **NOT
EXECUTED**). Detection is manual / Render dashboard / user report.

| Level | Meaning | Detection | Initial response | Escalate when | Owner notify | Authority | Preserve | Communicate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SEV-1 | Complete outage; suspected major data loss; DB corruption; critical integrity/security | `/health` fail; `/ready` 503 database; user report; dashboard down | Incident runbook; **no** DSN/restore | Immediate | Yes | Owner for disaster / restore / cutover | Logs, clocks, dashboard names | Owner approves any customer notice |
| SEV-2 | Major degradation; persistent DB/storage fail; critical workflow down | `/ready` storage/database; error logs | Classify app vs DB vs storage | Persists or data at risk | Yes | Owner for env/plan/restore | Logs, `/ready` body (no secrets) | Owner |
| SEV-3 | Recoverable; cleanup cron fail; intermittent non-critical | Cron history; TransientError | Scenario 3/4; do not rerun cron | Repeats or becomes SEV-2 | As needed | Owner for manual cron | Cron result, timestamps | Internal |
| SEV-4 | Informational / maintenance | Deploy events | Record | None | Optional | Owner for maintenance window | Event id | Internal |

SEV-1 does **not** auto-start the RTO clock. The clock starts on **owner
declaration** (§3).

## 10. Business continuity procedures

**BUSINESS CONTINUITY MODE: CONTROLLED SERVICE SUSPENSION.**

No safe manual alternative exists for PDF processing, storage repair, or
credit ledger correction. Do **not** invent spreadsheet processing, manual
SQL grants, or uncontrolled uploads.

| Topic | Procedure |
| --- | --- |
| Customer-facing communication | Owner-approved only. Facts: unavailable / investigating. No DSNs, no restore ETAs unless owner sets them. |
| Temporary unavailability | Leave API/CMS as-is unless owner scales down to stop writes (data-loss / corruption). |
| Upload / processing | Treat as **stopped**. Do not process files on laptops against production. |
| User access | CMS may remain reachable; failed API calls are acceptable during suspension. |
| Credits / billing | Do not edit `credit_ledger` by hand. Idempotent reserve/settle/refund in app code is the control. In-flight inline jobs may die on spin-down; stale fail+refund is existing behavior after `JOB_STALE_MINUTES`. |
| Pending jobs | Postgres remains source of truth. Do not re-queue in production without approval. |
| Data integrity | Stop risky writes if corruption is ongoing. Do not overwrite `docuflow-db`. |
| Resumption | Owner stop-clock criteria in §3. Then cleanup cron may continue on schedule (do not manually trigger). |

## 11. Disaster recovery procedure

High-level policy. **Not executed** in Phase 9.18. Isolated SQL and
identity gate remain in `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`.

| Stage | Action |
| --- | --- |
| 1 Detection | Identify incident; preserve evidence; estimate business impact. |
| 2 Declaration | Owner reviews evidence; declares or rejects; record declaration timestamp (RTO start). |
| 3 Recovery planning | List recovery points (dashboard names/times only); estimate data-loss exposure; confirm target services. PITR 10-minute rule still applies. Blank PITR target restores latest available — record that. |
| 4 Authorization | Owner approves procedure, recovery point, **new** instance name, and whether cutover is in scope. Cutover is **never** implied by a drill. |
| 5 Isolated validation | New instance only. Identity gate. Schema, required tables/index, counts, FKs. Application compatibility = repo Alembic head vs drill `alembic_version` (live prod DSN still prohibited unless separately approved). Storage references: presence of keys in DB is **not** proof objects exist. |
| 6 Production recovery | **Separately authorized.** Not this phase. Never in-place restore onto live `docuflow-db` while it is the only copy. |
| 7 Business validation | Critical workflows; CMS; data consistency the owner accepts. |
| 8 Closure | Record RTO, RPO, downtime, data-loss exposure, residual risk; owner approval; delete isolated resources only with a delete approval. |

## 12. RTO gap analysis

Approved target: **4 hours**. Measured: isolated DB restore **15 minutes**.
That is **not** total business recovery time.

| Recovery activity | Evidence | Duration | Status |
| --- | --- | --- | --- |
| Isolated database restore | Phase 9.16 T0 17:50 → T1 18:05 | **15 minutes** | **Measured** (owner clocks) |
| Incident detection | None | Unknown | **Unmeasured** |
| Owner authorization / declaration | None as a timed drill | Unknown | **Unmeasured** |
| Recovery point selection | 9.16 PITR field blank | Unknown | **Unmeasured** |
| Infrastructure provisioning | Included in 9.16 T0–T1 for isolated Postgres | In the 15 min for DB instance | **Partial** (DB only) |
| Schema / integrity validation | 9.16 owner PSQL; T2 inferred 18:16 chat receipt | Not owner-sent | **Partial** |
| Application deploy / config | Existing API/CMS; cutover **not** done | Unknown | **Unmeasured** |
| Storage validation | `/ready` storage historically; no object inventory | Unknown | **Unmeasured** |
| Business workflow validation | 9.12 functional PASS is **not** a DR exercise | Unknown | **Unmeasured** |
| Service resumption / cutover | Forbidden / not done | Unknown | **Not established** |
| Full business recovery | None | Unknown | **Not established** |

**Conclusion:** 4-hour business RTO is **NOT YET DEMONSTRATED**. Isolated
database restoration is **PARTIALLY SUPPORTED** (15 minutes ≪ 4 hours).
Do **not** mark VERIFIED from the 15-minute restore alone.

## 13. RPO gap analysis

Approved target: **24 hours**.

| Evidence | Current status | Impact |
| --- | --- | --- |
| PITR availability window | Owner-reported **3 days** | Insufficient to establish exact RPO (retention ≠ RPO) |
| Backup schedule / enabled | **NOT INDEPENDENTLY CAPTURED** | Cannot verify cadence |
| Latest restorable instant | **UNKNOWN** | Cannot calculate observed RPO |
| Logical export | Owner-reported success **7 Nov 2026, 5:27 PM**; `.dir.tar.gz` | Additional option; clock zone not assumed |
| Export retention | Owner-reported **≥ 7 days** | Retention only |
| Actual recovery point used (9.16) | Blank → latest available **unknown** | RPO **NOT DETERMINABLE** |
| Render 10-minute PITR boundary | Platform constraint (9.16) | Cannot restore inside last 10 minutes |

BUSINESS RPO TARGET = 24 HOURS.
TECHNICAL RPO CAPABILITY = NOT VERIFIED.

A 3-day window **could** cover 24 hours **if** PITR is actually enabled
and the latest restorable instant is within 24 hours of an incident. That
condition is **not** demonstrated. Phase 9.15 remains **open**.

## 14. Cost-efficient recovery model

Current architecture is the recovery model: restore a **new** Basic
Postgres when separately approved, validate isolated, cut over only with
owner approval, delete the extra instance after. Prefer existing
`docuflow-db` PITR / logical export over new vendors.

| Recommendation | Benefit | Justification | Recurring cost | Complexity | Owner approval? |
| --- | --- | --- | --- | --- | --- |
| Keep inline + current services | Matches deployed, authorized architecture | Redis/worker not required for BC policy | None | Low | No change |
| Finish 9.15 Recovery-page fields | Makes 24 h RPO **evaluable** | Latest instant + schedule still missing | **Free** (dashboard paste) | Low | Owner time |
| Isolated drill only when approved | Measures RPO if PITR timestamp recorded | 9.16 left timestamp blank | Second Basic Postgres while live (**UNKNOWN** exact $; billable) | Medium | **Required** |
| External `/ready` uptime check | Faster detection (RTO hidden time) | 9.17 spec; alerts **NOT EXECUTED** | **UNKNOWN** / possibly paid | Low | **Required** before enable |
| Redis / worker / extra DB / APM | — | **No** documented necessity for 4 h / 24 h policy | Avoid | — | Do **not** add |
| Plan upgrade | Longer PITR window (docs: Pro 7 d) | Owner-reported window already **3 days** > 24 h **if real** | Paid | Low | Only if 9.15 shows window < 24 h |

If cost cannot be verified: **UNKNOWN**. Do not upgrade the database plan
in this phase.

## 15. Recovery validation policy

Future **isolated** exercises (not scheduled here) should record:

1. Exercise identifier (service name containing `restore` or `drill`, never `staging`).
2. Date (Asia/Jakarta).
3. Scope (DB-only vs business).
4. Environment (`isolated-restore` / staging / production — production restore still separately authorized).
5. Recovery source (`docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a`).
6. Recovery point timestamp **used** (not only requested).
7. Start timestamp (declaration or T0 as labeled).
8. Database-ready timestamp (T1).
9. Application-ready timestamp (if in scope).
10. Business-validation timestamp (if in scope).
11. Completion timestamp.
12. Data integrity results (identity gate, schema, counts, FKs).
13. RTO calculation (state which clock: DB vs technical vs business).
14. RPO calculation (incident/reference minus restore point).
15. Owner approval lines.
16. Cleanup evidence (deleted service/instance; `docuflow-db` still present).

Distinguish: **database restore duration** (9.16 = 15 min) vs **technical
service recovery** vs **full business recovery**. Do not execute a new
drill in Phase 9.18.

## 16. Outstanding risks

| Risk | Impact | Likelihood | Existing safeguard | Recommended action | Cost |
| --- | --- | --- | --- | --- | --- |
| 4 h RTO unproven end-to-end | Over-promise recovery | Known | Isolated 15 min DB restore | Keep capability **NOT YET VERIFIED**; optional later timed exercise | Drill bill if run |
| 24 h RPO unverified | Silent RPO breach | Known | Owner-reported 3-day window | Close 9.15 latest instant + schedule | Free |
| Backup schedule unknown | Cadence may exceed 24 h | Unknown | 9.15 open | Owner Recovery-page paste | Free |
| Detection/alerting gap | RTO consumed before declaration | Medium | Manual; `/health` keep-alive | 9.17 matrix; do not enable without approval | Varies |
| Cutover never rehearsed | Extra unmeasured time | Known | Policy forbids unapproved cutover | Accept until a **separate** production-recovery procedure | High risk if improvised |
| Object store not in PITR | Docs missing after DB restore | Medium | Storage separate domain | Validate references; no prod mutate | Free |
| Inline jobs lost on death | In-flight work | Accepted | queued re-enqueue; stale refund | Keep inline | None |

## 17. Owner actions

1. Treat 4 h / 24 h as **objectives**, not guarantees.
2. Complete remaining **Phase 9.15** fields: backup schedule/enabled;
   latest restorable PITR timestamp (names/times only).
3. Assign named people to Owner / Technical Operator when ready (optional).
4. Approve any notification integration before it is configured.
5. Do **not** restore production or cut over from this document.
6. Next isolated drill (if any) must record **PITR timestamp used**.

## 18. Next-phase recommendations — 9.19 (not started)

Recovery capability gap closure and operational readiness (**not**
executed here):

- Obtain missing 9.15 backup evidence.
- Verify backup schedule and enabled state.
- Capture latest restorable PITR timestamp.
- Evaluate technical RPO against the 24-hour **target**.
- Identify RTO bottlenecks against the 4-hour **target** (detection,
  authorization, cutover — still unmeasured).
- Review 9.17 monitoring/notification gaps.
- Prioritized, cost-aware remediation plan.

Do **not** close 9.15 as a side effect. Do **not** run a recovery drill
from this handoff. Do **not** change production architecture.

## Safety this phase

| Action | Occurred |
| --- | --- |
| Application code | **NO** |
| Production DSN / SQL | **NO** |
| Restore / cutover / env / plan | **NO** |
| New infrastructure | **NO** |
| Production `/health` `/ready` re-probe | **NO** (18:49 remains historical) |
