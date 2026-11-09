# Phase 9.16 — Measured RTO/RPO and recovery validation

Isolated PITR is **authorized**. **This agent did not click Restore.**
Production DSN was not opened. Production cutover is **not authorized**.
No application code changed.

Time: **9 Nov 2026, 17:53 Asia/Jakarta (WIB)** (`2026-11-09T17:53:00+07:00`).
Baseline `origin/main`: **`eefec9e`** (PR #34 merged).

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (method assessment + resource spec + this report) | **YES** |
| LOCALLY VERIFIED | **YES** (git baseline, 10-minute PITR rule check) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| OWNER APPROVAL (billable isolated restore) | **YES** (9 Nov 2026, 17:52 Asia/Jakarta) |
| RECOVERY EXECUTION | **BLOCKED** — Render forbids restore within 10 minutes of now; approved PITR **17:50** was ~3 minutes old at 17:53. Earliest click for that target: **18:00 Asia/Jakarta**. Then owner clicks Restore. |
| Isolated RTO | **NOT MEASURABLE** (no T0) |
| Isolated RPO | **NOT DETERMINABLE** (no recovered-data timestamp) |
| Business RTO / guaranteed RPO | **NOT ESTABLISHED** |

PHASE 9.16 IMPLEMENTATION: **PARTIAL**.
PHASE 9.16 RECOVERY EXECUTION: **BLOCKED / OWNER ACTION REQUIRED**
(wait until 18:00 WIB or pick an older timestamp, then click Restore on a **new** instance only).

## A. Metadata

| Field | Value |
| --- | --- |
| Phase | 9.16 |
| Drill ID | `docuflow-rto-rpo-drill-20261108` (**authorized; not created**) |
| Branch | `cursor/phase-9-16-owner-pitr-authorization-8f43` |
| Recovery method | Method A — isolated PITR. **NOT EXECUTED** |
| Source | `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` |
| Selected PITR timestamp | **2026-11-09 17:50 Asia/Jakarta** (`2026-11-09T17:50:00+07:00`) |
| Destination | Proposed `docuflow-rto-rpo-drill-20261108` — identity **UNKNOWN** until created |
| Owner approval | **RECORDED** |

## B. Safety evidence

| Item | Result |
| --- | --- |
| Production DSN access | **NONE** |
| Production restore | **NONE** |
| Production mutations | **NONE** |
| Production cutover | **NONE** |
| Isolated resource identity | **UNKNOWN** (not provisioned) |
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

## F. Isolated resource specification (not provisioned)

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

Then this agent will run `scripts/recovery_identity_gate.py` (`RECOVERY_MODE=drill`)
against that hostname. Proceed to PSQL only if `classification isolated-restore`.

## H. RTO evidence (empty until T0)

| Event | Timestamp |
| --- | --- |
| Recovery initiated T0 | **NOT MEASURABLE** |
| Database available T1 | **NOT MEASURABLE** |
| Integrity validation complete T2 | **NOT MEASURABLE** |
| Recovery validation complete T3 | **NOT MEASURABLE** |

| Metric | Result |
| --- | --- |
| Database restoration duration (T1−T0) | **NOT MEASURABLE** |
| Database validation duration (T2−T1) | **NOT MEASURABLE** |
| End-to-end isolated recovery (T3−T0) | **NOT MEASURABLE** |
| Isolated database recovery time | **NOT MEASURABLE** |
| Isolated recovery validation time | **NOT MEASURABLE** |
| Business RTO | **NOT ESTABLISHED** |

9.13B had restore time used 22:25 and instance reported 22:34; that is **not**
T0/T1 and is **not** Phase 9.16 RTO.

## I. RPO evidence

| Field | Result |
| --- | --- |
| Reference timestamp | **UNKNOWN** (no incident; owner may set inspection time as reference) |
| Source backup consistency timestamp | **UNKNOWN** |
| Export completion timestamp | OWNER-REPORTED export created 7 Nov 2026, 5:27 PM (timezone **UNKNOWN**) — unused unless Method B |
| Selected PITR timestamp | **2026-11-09 17:50 Asia/Jakarta** (authorized; restore not started) |
| Actual recovered data timestamp | **UNKNOWN** |
| Observed recovery-point gap | **NOT DETERMINABLE** |
| Guaranteed RPO | **UNKNOWN** (3-day window is a retention claim, not a measured gap) |

## J. Integrity evidence (not run)

9.13B historical counts (7 Nov restore copy) — **do not treat as expected
for a different PITR point**:

users 2, documents 131, jobs 52, credit_ledger 142, storage_deletions 131,
cleanup_leases 1, FK 7, Alembic `0003_cost_efficient_reliability`.

| Check | Expected | Actual | Status |
| --- | --- | --- | --- |
| Database availability | isolated dest responds | | NOT EXECUTED |
| Alembic version | compare to dest only | | NOT EXECUTED |
| Required tables | users, documents, jobs, cleanup_leases, storage_deletions | | NOT EXECUTED |
| Index `ix_storage_deletions_lease_until` | present if 0003 | | NOT EXECUTED |
| Foreign keys | count only | | NOT EXECUTED |
| Table counts | **not** assumed equal to 9.13B | | NOT EXECUTED |

No `alembic upgrade` / `stamp` / `migrate` if schema fails. Record failure.

## K. Independent conclusions (this pass)

| Result | Meaning |
| --- | --- |
| PITR capability | **PARTIALLY VERIFIED** (owner: 3-day window) / **NOT EXECUTED** operationally |
| Logical export recovery capability | Export **OWNER-REPORTED** present; restore **NOT EXECUTED** |
| Isolated restore capability | **VERIFIED** historically (9.13B); this dated drill **NOT EXECUTED** |
| Measured restoration duration | **NOT MEASURABLE** |
| Measured validation duration | **NOT MEASURABLE** |
| Observed RPO | **NOT DETERMINABLE** |
| Guaranteed RPO | **UNKNOWN** |
| Business RTO target | **NOT ESTABLISHED** |

## L. Limitations

- No T0 from owner/execution log.
- Latest restorable PITR instant unknown.
- 3-day window is owner-reported screenshot text, not viewed here.
- Second Basic Postgres bills until deleted.
- No production cutover → cannot claim application RTO.
- R2 objects are a separate recovery domain.

## M. Cleanup (later, separate line)

After evidence: `Delete docuflow-rto-rpo-drill-20261108`.
Never delete `docuflow-db`.

## N. Files

- this report (new)
- `docs/IMPLEMENTATION_STATUS.md` (Phase 9.16)
- `docs/DEPLOYMENT.md` (pointer)

No `apps/`, `src/`, migrations, Blueprint, or env changes.
