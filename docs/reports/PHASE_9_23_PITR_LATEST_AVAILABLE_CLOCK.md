# Phase 9.23 — PITR latest-available clock capture

Transcribe the owner Point-in-Time Recovery **picker** screenshot. **Not** a
restore. **Start Recovery was not clicked.** Do **not** click it. Click
**Cancel** if the dialog is still open.

Time: **10 Nov 2026, 15:42 Asia/Jakarta (WIB)** (`2026-11-10T15:42:00+07:00`)
screenshot receipt. Baseline `origin/main`: **`4625642`** (PR #41 merge).

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (transcription) | **YES** |
| OWNER SCREENSHOT — AGENT VIEWED | **YES** |
| Start Recovery / new instance | **NOT EXECUTED** |
| PHASE 9.15 clock gap | **CAPTURED** (this inspection only) |
| PHASE 9.15 overall | **OPEN** (schedule/enabled toggle still not displayed) |
| BACKUP ASSURANCE COMPLETE | **NO** |
| BUSINESS RPO capability | **NOT DEMONSTRATED** (one observed gap ≠ SLA) |

## 1. What the screenshot shows

Dialog title: **Point-in-Time Recovery**. Subtitle: pick a date and time to
recover or restore. Restore creates a **new** database (field **Database
Name**).

| Field | Value on screenshot |
| --- | --- |
| Proposed new service name | `docuflow-db-copy-2` (**not** `docuflow-db`) |
| Restore Date & Time label | “The latest available time is shown below.” |
| Date | **2026-11-10** |
| Time | **15:31:47** |
| Timezone | **UTC+07:00** (Asia/Jakarta) |
| Copy existing settings | “Yes, copy existing settings” highlighted |
| Start Recovery | Visible, **not** clicked |
| Cancel | Visible |

Exact latest-available instant:

`2026-11-10T15:31:47+07:00`

No DSN, password, or Connect URL in the crop.

## 2. Observed gap (this inspection only)

| Clock | Value |
| --- | --- |
| Latest available (UI) | 15:31:47 UTC+7 |
| Screenshot receipt | 15:42 Asia/Jakarta (seconds not in the chat stamp) |
| Observed restorable lag | **~10 minutes** |

That lag matches Render’s **10-minute** “cannot restore inside last 10
minutes” rule. It is **not** a guaranteed RPO. It **is** one measured
inspection: restorable data was about ten minutes behind wall-clock, which
is **inside** the 24-hour **business RPO target** at that moment.

9.16 drill RPO remains **NOT DETERMINABLE** (`PITR timestamp used` was
blank). This screenshot does **not** rewrite 9.16.

## 3. What this does not authorize

- Do **not** click **Start Recovery**.
- Do **not** create `docuflow-db-copy-2` (billable new Postgres).
- Do **not** overwrite or attach this DSN to production API/CMS/cron.
- If the dialog is still open: **Cancel**.

## 4. Phase 9.15 impact

| Prior gap | After this screenshot |
| --- | --- |
| Latest restorable PITR **clock** | **CAPTURED** for 10 Nov 2026, 15:31:47 UTC+7 |
| Backup schedule | Still **NOT DISPLAYED** |
| Enabled toggle | Still **NOT DISPLAYED** (picker existing is not a named switch) |
| 3-day window / 7 Nov export | Unchanged (9.20) |

PHASE 9.15: **OPEN**. BACKUP ASSURANCE: **INCOMPLETE**.

## 5. Safety

| Action | This phase |
| --- | --- |
| Application / Blueprint / env / plan | **NO** |
| Start Recovery / export / DSN | **NO** |
| Screenshot committed to git | **NO** |

Later consolidation (do not treat ~10 min as guaranteed RPO):
`docs/reports/PHASE_9_24_RECOVERY_ASSURANCE.md`.
