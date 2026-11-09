# Phase 9.16 — Measured RTO/RPO and recovery validation

Owner reported the isolated instance Available. **This agent did not click
Restore** and did not connect. Production DSN was not opened. Production
cutover is **not authorized**. No application code changed.

Time: **9 Nov 2026, 18:17 Asia/Jakarta (WIB)** (`2026-11-09T18:17:00+07:00`).
Baseline `origin/main` at this branch: **`eefec9e`**.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED | **YES** |
| IDENTITY GATE | **PASS** (`classification isolated-restore`) |
| OWNER APPROVAL | **YES** |
| Owner restore (new instance) | **OWNER-REPORTED** |
| Isolated DB recovery time (T1−T0) | **PARTIALLY VERIFIED** 15 min (owner clocks) |
| Integrity SQL (T2) | **PASS** (owner PSQL; this agent did not connect) |
| Isolated RTO (end-to-end T3−T0) | **INFERRED** 26 min using SQL-result chat receipt 18:16 as T2/T3 (owner did not send T2) |
| Isolated RPO | **NOT DETERMINABLE** (`PITR timestamp used` blank) |
| Business RTO / guaranteed RPO | **NOT ESTABLISHED** |

PHASE 9.16 IMPLEMENTATION: **COMPLETE** (isolated exercise; limitations below).
PHASE 9.16 RECOVERY EXECUTION: **COMPLETE** for schema/counts. RPO **NOT DETERMINABLE**.
PHASE 9.16 CLEANUP: **BLOCKED** — delete line received; dashboard Delete **NOT EXECUTED**.

## A. Metadata

| Field | Value |
| --- | --- |
| Phase | 9.16 |
| Drill ID | `docuflow-rto-rpo-drill-20261108` |
| Recovery method | Method A — isolated PITR. Owner reported instance Available |
| Source | `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` |
| Authorized PITR timestamp | **2026-11-09 17:50 Asia/Jakarta** |
| PITR timestamp used (dashboard) | **UNKNOWN** (owner left field blank) |
| Destination service | `docuflow-rto-rpo-drill-20261108` |
| Destination instance | `dpg-dboq68bm8hqs73en0rpg-a` |
| Destination database | `docuflow_db_q32a_7751` |
| Distinct from production | **YES** |
| Distinct from deleted 9.13B drill | **YES** (`dpg-dbnk595g1s2s73cuafl0-a`) |

## B. Safety evidence

| Item | Result |
| --- | --- |
| Production DSN access | **NONE** |
| Production restore | **NONE** |
| Production mutations | **NONE** |
| Production cutover | **NONE** |
| Isolated resource identity | **VERIFIED** (gate: host/db match approved drill; not prod/staging) |
| Owner approval | **RECORDED** |

Protected: `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a`. Do not reuse deleted
`docuflow-db-restore-drill-20261107` / `dpg-dbnk595g1s2s73cuafl0-a`.

## C. Stage A — Preflight (read-only)

Inspected: `origin/main` `c44cafa`; `docs/IMPLEMENTATION_STATUS.md`;
9.13B / 9.14 / 9.15 reports; recovery runbook §5–§9; `scripts/recovery_identity_gate.py`;
`infra/render.yaml` (`docuflow-db` `plan: 0.1c-256mb`, Postgres **16**).

Reuse: identity gate + runbook read-only SQL on the **drill** PSQL only.
No new scripts. No second 9.13B-style drill without new approval.

## D. Owner-reported 9.15 screenshot fields (this prompt)

This agent **did not view** a screenshot. Values below are **OWNER-REPORTED**
from the Phase 9.16 prompt. They are **not** independently verified.

| Field | Owner-reported value | Class |
| --- | --- | --- |
| Name | `docuflow-db` | OWNER-REPORTED |
| Service ID | `dpg-dbiqe70ae00c73cdif7g-a` | OWNER-REPORTED |
| Plan | `0.1c-256mb` | OWNER-REPORTED |
| Blueprint managed | yes | OWNER-REPORTED |
| PITR recovery window | **3 days** | OWNER-REPORTED |
| Pro workspace window | 7 days (stated as offer, not this window) | OWNER-REPORTED |
| Logical export | successful; created **7 Nov 2026, 5:27 PM**; `.dir.tar.gz`; retained ≥7 days | OWNER-REPORTED |

Still **UNKNOWN** (this prompt): latest restorable PITR timestamp; automated
backup schedule/enabled toggle; PITR operational restore result; actual RPO;
actual RTO. Export clock timezone not stated (do not assume WIB).

Do **not** create another export. Creating an export is a mutation.

## E. Recovery method assessment

| Method | Use | Proves | Risk |
| --- | --- | --- | --- |
| **A. Isolated PITR** | Render Recovery → Restore Database → **new** instance named `docuflow-rto-rpo-drill-20261108` | PITR path + timed T0–T3 if owner records clocks | Billable second DB until deleted. **STOP** if UI would overwrite `docuflow-db` |
| **B. Logical export** | Existing 7 Nov 2026 5:27 PM `.dir.tar.gz` into a **new** empty isolated Postgres | Logical-export path only | Still billable dest DB. Does **not** prove PITR. Needs dest + `pg_restore` without production DSN |

**Selected for execution (when approved): Method A.** Reasons: 9.16 needs PITR
operational result; 9.13B already showed restore-creates-new-instance; official
docs (new instance, not in-place); do not run both methods; do not create a
new export.

If Restore would replace `docuflow-db`, **do not click it**.

## F. Isolated resource specification (owner-reported created)

| Item | Spec |
| --- | --- |
| Suggested name | `docuflow-rto-rpo-drill-20261108` |
| Engine | PostgreSQL **16** (Blueprint) |
| Region | **Copy production** `docuflow-db` region (value **UNKNOWN** here) |
| Plan | `0.1c-256mb` (same class as production; do not change production) |
| Storage | Default for that plan; do not resize production |
| Source | `docuflow-db` PITR |
| Recovery timestamp | **2026-11-09 17:50 Asia/Jakarta** — inside owner-reported 3-day window. At 17:53 it was **only ~3 minutes** old. Render: cannot restore within 10 minutes of now. Earliest Start Recovery for this target: **18:00 Asia/Jakarta**. |
| Expected lifetime | Until T2/T3 evidence, then separate `Delete …` approval |
| Cleanup | Delete **only** this named instance; never `docuflow-db` |
| Billable | **YES** (second paid Postgres until deleted) |
| Expected cost | **UNKNOWN** in currency. Same plan class as the 9.13B drill. Bills while it exists |
| Expected duration | **UNKNOWN** until T0–T1. Do not reuse 9.13B as RTO |
| Attach to API/web/cleanup | **NO** |
| Production `DATABASE_URL` | **unchanged** |

## G. Owner approval (recorded)

Owner (9 Nov 2026, **17:52 Asia/Jakarta**) sent the exact authorization,
including `PITR timestamp: 2026-11-09 17:50 Asia/Jakarta` and
`Creates billable resource: YES`.

**STOP before Restore until** either:

- clock is **18:00 Asia/Jakarta or later** (17:50 + 10 minutes), or
- owner instead uses an older PITR time already ≥10 minutes in the past.

This agent will **not** click Restore.

Then owner-only dashboard steps:

1. `docuflow-db` → Recovery → Point-in-Time Recovery → Restore Database.
2. Confirm destination is a **new** instance, not in-place.
3. Name it **exactly** `docuflow-rto-rpo-drill-20261108`.
4. Set the approved PITR timestamp (not within 10 minutes of now).
5. Record **T0** when Start Recovery is clicked (Asia/Jakarta + UTC if shown).
6. Do **not** attach the new DB to production services.
7. When status is Available, record **T1**, hostname `dpg-…`, database name.
8. Reply names and times only (no DSN).

## G.2 Identity gate (this environment, no connection)

Synthetic DSN (placeholder password). Script does not connect.

```
RECOVERY_MODE=drill
OWNER_APPROVED_RECOVERY_TARGET=docuflow-rto-rpo-drill-20261108
EXPECTED_RESTORE_HOSTNAME=dpg-dboq68bm8hqs73en0rpg-a
host dpg-dboq68bm8hqs73en0rpg-a
database docuflow_db_q32a_7751
classification isolated-restore
proceed isolated-restore
exit 0
```

Negative: actual production host `dpg-dbiqe70ae00c73cdif7g-a` → `production` STOP.

Production after owner restore (18:09 Asia/Jakarta, read-only):
`GET /health` HTTP 200 `docuflow-api`; `GET /ready` HTTP 200 `broker=inline`
`rq_workers=0` `database=true` `storage=true`.

## H. RTO evidence

Owner-reported (9 Nov 2026, 18:08 Asia/Jakarta). Class: **OWNER-REPORTED**.

| Event | Timestamp |
| --- | --- |
| Recovery initiated T0 | **17:50 Asia/Jakarta** (`2026-11-09T17:50:00+07:00`) |
| Database available T1 | **18:05 Asia/Jakarta** (`2026-11-09T18:05:00+07:00`) |
| Integrity validation complete T2 | **INFERRED** 18:16 Asia/Jakarta (`2026-11-09T18:16:00+07:00`) from SQL-result message time. Owner did **not** send T2. |
| Recovery validation complete T3 | Same as T2 (no application cutover) |

| Metric | Result |
| --- | --- |
| Database restoration duration (T1−T0) | **15 minutes** (OWNER-REPORTED clocks) |
| Database validation duration (T2−T1) | **11 minutes** if T2=18:16 receipt (**INFERRED**; includes chat delay) |
| End-to-end isolated recovery (T3−T0) | **26 minutes** if T3=18:16 (**INFERRED**) |
| Isolated database recovery time | **15 minutes** (T1−T0; not application RTO) |
| Isolated recovery validation time | **11 minutes** (**INFERRED** receipt clock) |
| Business RTO | **NOT ESTABLISHED** |

Gaps: `PITR timestamp used` was blank. T0 equals the **authorized** PITR
time 17:50; it may be click time or the target. Recorded as stated. If T0
was the click at 17:50 targeting 17:50, that would have been inside
Render’s 10-minute window; the instance existing does not resolve which
clock was which.

9.13B had restore time used 22:25 and instance reported 22:34; that is **not**
T0/T1 and is **not** Phase 9.16 RTO.

## I. RPO evidence

| Field | Result |
| --- | --- |
| Reference timestamp | **UNKNOWN** (no incident; owner may set inspection time as reference) |
| Source backup consistency timestamp | **UNKNOWN** |
| Export completion timestamp | OWNER-REPORTED export created 7 Nov 2026, 5:27 PM (timezone **UNKNOWN**) — unused unless Method B |
| Selected PITR timestamp | Authorized **2026-11-09 17:50**; dashboard “used” value **UNKNOWN** (blank) |
| Actual recovered data timestamp | **UNKNOWN** |
| Observed recovery-point gap | **NOT DETERMINABLE** |
| Guaranteed RPO | **UNKNOWN** (3-day window is a retention claim, not a measured gap) |

## J. Integrity evidence (owner PSQL, 18:16 Asia/Jakarta)

Prompt `docuflow_db_q32a_7751=>`. This agent did not connect. Class:
**OWNER-REPORTED**.

| Check | Expected | Actual | Status |
| --- | --- | --- | --- |
| Database availability | `SELECT 1` | 1 | **PASS** |
| current_database | `docuflow_db_q32a_7751` | `docuflow_db_q32a_7751` | **PASS** |
| Alembic version | dest only; repo head 0003 | `0003_cost_efficient_reliability` | **PASS** |
| Required tables | users, documents, jobs, cleanup_leases, storage_deletions | all present | **PASS** |
| Index `ix_storage_deletions_lease_until` | present if 0003 | present | **PASS** |
| Foreign keys | count only | 7 | **PASS** (count returned) |

Public tables (17): `alembic_version`, `audit_logs`, `cleanup_leases`,
`credit_accounts`, `credit_ledger`, `documents`, `email_tokens`, `jobs`,
`operation_costs`, `payment_events`, `pg_stat_statements`,
`pg_stat_statements_info`, `plans`, `sessions`, `storage_deletions`,
`subscriptions`, `users`. Extra vs 9.13B: `pg_stat_statements`,
`pg_stat_statements_info` (extension catalog; not app tables). Not a fail.

Counts (not required to match 9.13B; a different restore point):

| Table | 9.13B copy (7 Nov) | This drill | Status |
| --- | ---: | ---: | --- |
| users | 2 | 2 | same integer; timestamps differ |
| documents | 131 | 131 | same integer; timestamps differ |
| jobs | 52 | 52 | same integer; timestamps differ |
| credit_ledger | 142 | 142 | same integer; timestamps differ |
| storage_deletions | 131 | 131 | same integer; timestamps differ |
| cleanup_leases | 1 | 1 | same integer; timestamps differ |

No `alembic upgrade` / `stamp` / `migrate` was run.

## K. Independent conclusions (this pass)

| Result | Meaning |
| --- | --- |
| PITR capability | **PARTIALLY VERIFIED** (3-day window + owner new instance) |
| Logical export recovery | Export present; restore **NOT EXECUTED** |
| Isolated restore this drill | **OWNER-REPORTED** Available + identity **PASS** + SQL **PASS** |
| Measured restoration duration | **PARTIALLY VERIFIED** 15 min (owner T0/T1) |
| Measured validation duration | **INFERRED** 11 min (chat receipt T2) |
| Observed RPO | **NOT DETERMINABLE** |
| Guaranteed RPO | **UNKNOWN** |
| Business RTO target | **NOT ESTABLISHED** |

## L. Limitations

- T0/T1 owner-reported; T0 equals authorized PITR 17:50 (possible mix-up).
- Dashboard “PITR timestamp used” blank → RPO not determinable.
- T2 not sent by owner; 18:16 is SQL-result chat receipt (**INFERRED**).
- 3-day window is owner-reported screenshot text, not viewed here.
- Second Basic Postgres bills until the owner deletes it in Render.
- No production cutover → cannot claim application RTO.
- R2 objects are a separate recovery domain.

## M. Cleanup

Owner (9 Nov 2026, **18:18 Asia/Jakarta**) sent:

`Delete docuflow-rto-rpo-drill-20261108`

This agent will **not** click Delete.

Delete **only** this instance:

| Field | Must match | Stop if |
| --- | --- | --- |
| Service | `docuflow-rto-rpo-drill-20261108` | `docuflow-db` |
| Instance | `dpg-dboq68bm8hqs73en0rpg-a` | `dpg-dbiqe70ae00c73cdif7g-a` |
| Database | `docuflow_db_q32a_7751` | staging names |

1. Production workspace (not staging).
2. Open `docuflow-rto-rpo-drill-20261108`. Confirm id and database name.
3. Confirm API/web/cleanup do **not** use this hostname. If any does, stop.
4. Delete **only** that service.
5. Confirm it is gone and **`docuflow-db` is still listed**.

Reply (no DSN):

```
deleted_service: docuflow-rto-rpo-drill-20261108
deleted_instance: dpg-dboq68bm8hqs73en0rpg-a
deleted_at (Asia/Jakarta):
docuflow-db still present: YES/NO
```

Dashboard Delete: **NOT EXECUTED**.

## N. Files

- this report (new)
- `docs/IMPLEMENTATION_STATUS.md` (Phase 9.16)
- `docs/DEPLOYMENT.md` (pointer)

No `apps/`, `src/`, migrations, Blueprint, or env changes.
