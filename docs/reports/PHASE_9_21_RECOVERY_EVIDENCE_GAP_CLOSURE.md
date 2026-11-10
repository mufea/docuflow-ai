# Phase 9.21 — Recovery evidence gap closure

Evidence-assessment only. **Not** a restore, export, cutover, R2 mutate, or
application change. Does **not** close Phase 9.15.

Time: **10 Nov 2026, 12:55 Asia/Jakarta (WIB)** (`2026-11-10T12:55:00+07:00`).
Baseline `origin/main`: **`04a0e90`** (PR #38 merge).

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (this assessment) | **YES** |
| LOCALLY VERIFIED | **YES** (git baseline, targeted code/docs, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| STAGING VERIFIED (this phase) | **NOT EXECUTED** |
| PRODUCTION VERIFIED (this phase) | **NOT VERIFIED** |
| OWNER ACTION REQUIRED | **YES** (9.15 timestamp; PR #39 merge is owner choice) |
| BLOCKED | **NO** (assessment can complete without dashboard) |

PHASE 9.21 DOCUMENTATION: **COMPLETE**.
PHASE 9.15: **OPEN**.
BACKUP ASSURANCE: **INCOMPLETE**.
PRODUCTION DR READINESS: **NOT DEMONSTRATED**.
BUSINESS RTO: **NOT DEMONSTRATED**.
BUSINESS RPO: **NOT DEMONSTRATED**.

## 1. Executive summary

Four domains were classified against existing reports and targeted storage /
job / credit code. No live dashboard, DSN, or R2 console was used.

**Available vs configured vs observed vs tested vs business assurance are
not the same.** PITR is **available** on the Recovery UI (historical
screenshot). Isolated Postgres restore was **tested** (9.13B / 9.16).
**Observed RPO** is still **NOT DETERMINABLE**. **Business** 4-hour RTO and
24-hour RPO remain **NOT DEMONSTRATED**. R2 versioning and object restore
are **NOT VERIFIED**.

PR **#39** (Phase 9.20 screenshot transcription) is **OPEN** and **not** on
this baseline. 9.21 does not duplicate that file. Screenshot facts below are
**historical** (10 Nov 2026, 11:29 Asia/Jakarta), not a fresh live check.

## 2. Baseline commit

| Item | Value |
| --- | --- |
| `origin/main` | **`04a0e90`** |
| Phase 9.20 on main | **ABSENT** |
| PR #39 | **OPEN** https://github.com/mufea/docuflow-ai/pull/39 @ `34a569e` |
| Working tree at start | 9.20 branch local; 9.21 cut from `origin/main` |

## 3. Scope and exclusions

**In:** Postgres/PITR evidence classification; R2 recovery from repo + prior
docs; static DB↔object consistency; RTO/RPO vs 9.18 targets.

**Out:** Restore, export, SQL, DSN, R2 uploads/deletes, env/plan, app code,
alerting enablement, merging #39.

Historical production `/health` `/ready` **18:49 9 Nov 2026** is **not**
current health. **NOT EXECUTED** this phase.

## 4. PostgreSQL backup assessment

Identity is **consistent** across 9.11–9.19 and the 10 Nov Recovery crop:
`docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` / `0.1c-256mb`.

| Question | Answer | Class |
| --- | --- | --- |
| Identity documented? | **YES** | REPOSITORY-DOCUMENTED + historical screenshot |
| Backup schedule documented? | **NO** — UI had **no** schedule field | UNKNOWN / NOT DISPLAYED |
| Latest backup timestamp? | **NO** | UNKNOWN |
| Availability vs restore test? | UI restore control ≠ a dated backup job. Isolated **new-instance** restores **were** tested (9.13B, 9.16) | Mixed |
| Logical export sufficient for assurance? | Proves **one** export existed | Not cadence, not RPO |
| Export retention documented? | UI copy **≥ 7 days** | Historical screenshot |
| Independently measured RPO? | **NO** | NOT DETERMINABLE |
| Independently measured business RTO? | **NO** | 15 min is isolated DB only |

Do **not** infer a backup cron from PITR. Paid Render PITR is described as
continual WAL-style recovery in **official docs**, which is **not** this
account’s schedule field.

## 5. PITR evidence assessment

| Item | Status | Notes |
| --- | --- | --- |
| Window | **3 days** | Historical Recovery text; not a live re-check |
| Latest restorable **clock** | **UNKNOWN** | Not on Recovery without Restore (forbidden) |
| PITR available (UI) | **YES** (historical) | Restore database visible; **not** clicked |
| PITR enabled toggle | **NOT DISPLAYED** | |
| Restore-creates-new-instance | **OWNER-REPORTED** / isolated drills | 9.13B, 9.16 |
| 10-minute rule | Platform constraint | 9.16 |
| Current live Recovery page | **NOT INDEPENDENTLY VERIFIED** this phase | |

Isolated restore **procedure** is evidenced. **Current** restorable instant
is not.

## 6. Cloudflare R2 recovery assessment

Production bucket name **OWNER-REPORTED** (9.11): `docuflowai-documents`.
`STORAGE_BACKEND=s3`. App uses `delete_object` **without** `VersionId`
(`src/docuflow/storage/s3.py`). No `restore_object` / version-list path.
`NoSuchVersion` is classified as **missing**, not as a restore API.

Postgres PITR **does not** roll back R2 bytes (9.13, recovery runbook,
DEPLOYMENT § backup).

| Control | Assessment |
| --- | --- |
| Bucket identity | Documented (owner-reported name). Live R2 console **UNKNOWN** this phase |
| Object versioning | **NOT VERIFIED** (9.11, 9.13, 9.17, DEPLOYMENT recommend-only) |
| Lifecycle policy | **NOT VERIFIED** |
| Retention policy | App `FILE_RETENTION_HOURS` / `RESULT_RETENTION_HOURS` **REPOSITORY-DOCUMENTED**. R2 lifecycle **UNKNOWN** |
| Object deletion behavior | App outbox **REPOSITORY-DOCUMENTED**; staging/prod smoke deleted **test** objects (9.10B / 9.12). Not version-recovery |
| Recovery from accidental deletion | **NOT DEMONSTRATED** |
| Recovery from overwrite | **NOT DEMONSTRATED** |
| Access control | Env **names** documented; values **not** inspected |
| R2 credentials isolation | Staging vs prod **bucket names** documented; live IAM **NOT INDEPENDENTLY VERIFIED** |

A configured bucket ≠ tested object recovery. Versioning, even if later
enabled, ≠ demonstrated restore.

## 7. Database / object consistency

Static review only. No production queries.

| Scenario | Class | Evidence |
| --- | --- | --- |
| DB row exists, R2 object missing | **Potential risk** | PITR restores metadata only. Download uses `storage_key`. `/ready` pings **bucket**, not keys |
| R2 object exists, DB row missing | **Potential risk** | No orphan inventory (9.17). Cleanup deletes only `storage_deletions` after `deleted_at` |
| Job completed, output object gone | **Potential risk** | `Job.result_document_ids` → `Document.storage_key`. Insufficient live evidence |
| `processing` after API death | **Existing mitigation** | Stale fail+refund (`JOB_STALE_MINUTES`); `queued` re-enqueue (`jobs/recovery.py`, cap 100) |
| Credit reserved without settle/refund | **Existing mitigation** | Idempotent `reserve:` / `settle:` / `refund:` keys; fail+refund one txn; stranded terminal refund in cleanup |
| Cleanup deletes object before metadata | **Existing mitigation** | Mark deleted, then outbox. Failed object delete **never undeletes** the row (object may remain; metadata stays deleted) |

No **confirmed** production consistency incident was found in-repo. Inline
in-flight jobs dying with the process is an **accepted** architecture limit
(9.17–9.18), not a 9.21 code defect.

**Insufficient evidence** for live orphan counts (would need DSN or R2
list — both prohibited here).

## 8. RTO / RPO assessment

Targets unchanged (9.18): business RTO **4 hours**, business RPO **24 hours**.

| Objective | Classification | Why |
| --- | --- | --- |
| Isolated DB restore duration | **PARTIALLY DEMONSTRATED** | OWNER-REPORTED **15 minutes** (9.16 T0/T1) |
| Business RTO (4 h, declaration→usable services) | **NOT DEMONSTRATED** | Detection, auth, cutover, storage, workflows unmeasured |
| PITR retention window | **OWNER-SCREENSHOT-AGENT-VIEWED** (historical, PR #39 / chat) | **Not** observed RPO |
| Logical export | Same | **Not** RPO |
| Business RPO (24 h) | **NOT DEMONSTRATED** | Latest restorable clock **UNKNOWN** → observed RPO **NOT DETERMINABLE** |

Missing evidence is **not** a proven miss of 24 hours. Do not upgrade.

## 9. Evidence register

| ID | Domain | Description | Source | Date | Class | Method | Gap | Next |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E-01 | PG identity | `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` | 9.11–9.19; 10 Nov crop | 10 Nov 11:29 WIB (crop) | OWNER-SCREENSHOT-AGENT-VIEWED (historical) | Image in chat / PR #39 | Not a live re-check | Reconfirm only if identity changes |
| E-02 | PITR window | “past 3 days” | Recovery crop | 10 Nov 11:29 WIB | OWNER-SCREENSHOT-AGENT-VIEWED (historical) | Image | Not on `main` until #39 | Merge #39 optional |
| E-03 | PITR clock | Latest restorable timestamp | Recovery crop | 10 Nov | UNKNOWN | Not displayed | Blocks observed RPO | Paste if visible **without** Restore |
| E-04 | Backup schedule | Cron/frequency | Recovery crop | 10 Nov | UNKNOWN | Not displayed | G-01 | Leave UNKNOWN; do not infer |
| E-05 | Backup enabled toggle | Named switch | Recovery crop | 10 Nov | UNKNOWN | Not displayed | G-03 | Leave UNKNOWN |
| E-06 | Logical export | 7 Nov 2026 5:27 PM `.dir.tar.gz` | Recovery crop | 10 Nov viewed | OWNER-SCREENSHOT-AGENT-VIEWED (historical) | Image | TZ unknown; one-shot | Do not Create export |
| E-07 | Export retention copy | ≥ 7 days | Recovery crop | 10 Nov | OWNER-SCREENSHOT-AGENT-VIEWED (historical) | Image | Not a schedule | — |
| E-08 | Isolated restore | 9.13B / 9.16 new instance + SQL | Phase reports | 7–9 Nov | OWNER-REPORTED + identity gate | Prior phases | Not cutover; not current window | Do not repeat without approval |
| E-09 | Isolated DB duration | 15 min T0/T1 | 9.16 | 9 Nov | OWNER-REPORTED | Owner clocks | Not business RTO | Preserve |
| E-10 | Observed RPO | Inspection − restorable clock | — | — | UNKNOWN | Cannot compute | E-03 | — |
| E-11 | R2 bucket name | `docuflowai-documents` | 9.11 | 7 Nov | OWNER-REPORTED | Owner | Console not viewed | Read-only R2 settings optional |
| E-12 | R2 versioning | Enabled? | 9.11/9.13/9.17 | — | NOT-INDEPENDENTLY-VERIFIED | Docs only | Object DR | Owner dashboard names only |
| E-13 | R2 lifecycle | Bucket lifecycle | — | — | UNKNOWN | — | Object DR | Same |
| E-14 | App delete path | `storage_deletions` + idempotent delete | Code + 9.12 smoke | 7 Nov smoke | REPOSITORY-DOCUMENTED; prod delete of **test** docs PRODUCTION-VERIFIED (9.12) | Prior | Not version restore | Do not prod-delete for DR |
| E-15 | Object undelete | Restore deleted/overwritten keys | — | — | NOT DEMONSTRATED | — | Accidental delete | Do not test on prod |
| E-16 | Credit/job recovery | Ledger + stale fail | `ledger.py`, `refunds.py`, `recovery.py` | — | REPOSITORY-DOCUMENTED | Code read | Not a DR drill | — |
| E-17 | Business RTO/RPO targets | 4 h / 24 h | 9.18 | 9 Nov | REPOSITORY-DOCUMENTED | Policy | Capability not shown | Do not change targets |
| E-18 | PR #39 | 9.20 transcription | GitHub | 10 Nov | NOT on `main` | `gh pr view` | Merge is owner | Do not auto-merge |
| E-19 | Live `/ready` | Current health | — | — | UNKNOWN this phase | Not probed | — | Optional read-only GET |

Never treat a repository sentence as live production verification.

## 10. Unresolved gaps

1. Latest restorable PITR **clock** (E-03) — 9.15 cannot close.
2. Backup schedule / enabled **not displayed** (E-04, E-05).
3. Observed RPO **NOT DETERMINABLE**.
4. R2 versioning / lifecycle / object restore **NOT VERIFIED**.
5. End-to-end business RTO unmeasured.
6. PR #39 not on `main`.
7. Live production Alembic via DSN still **not** independently verified (unchanged; DSN still prohibited).

## 11. Risk ranking

| Pri | Risk | Impact |
| --- | --- | --- |
| P0 | No restorable PITR clock | Cannot show 24 h RPO |
| P0 | 9.15 still open | Backup assurance incomplete |
| P1 | R2 outside PITR; versioning unknown | DB restore can reference missing objects |
| P1 | Business RTO unmeasured | 15 min ≠ 4 h service |
| P2 | Orphan objects / missing bytes | No inventory |
| P2 | Alerting **NOT EXECUTED** (9.17) | Detection delay |
| P3 | PR #39 unmerged | Screenshot transcript not on `main` |

## 12. Recommended owner actions

1. Do **not** click Restore, Create export, Connect, or R2 mutate.
2. If a **read-only** screen shows a latest restorable datetime, paste timestamp + timezone; else leave **UNKNOWN**.
3. Merge or close PR #39 at owner discretion (does **not** close 9.15).
4. Optional: R2 dashboard **names only** — versioning on/off for `docuflowai-documents`.
5. Treat 4 h / 24 h as objectives, not guarantees.

No infrastructure purchase is justified by this assessment.

## 13. Production safety declaration

| Action | This phase |
| --- | --- |
| Production DSN / SQL / migrate | **NOT EXECUTED** |
| Restore / export / cutover / plan | **NOT EXECUTED** |
| R2 upload/delete/overwrite/restore | **NOT EXECUTED** |
| Env / restart / jobs | **NOT EXECUTED** |
| Application / Blueprint changes | **NONE** |
| Credentials in git | **NONE** |
| `env` / `printenv` / `.env` | **NOT EXECUTED** |

## 14. Final phase status

**COMPLETE — DOCUMENTATION AND EVIDENCE ASSESSMENT.**

Separately:

- BACKUP ASSURANCE: **INCOMPLETE**
- PRODUCTION DR READINESS: **NOT DEMONSTRATED**
- BUSINESS RTO: **NOT DEMONSTRATED**
- BUSINESS RPO: **NOT DEMONSTRATED**
- Phase 9.15: **OPEN**
