# Phase 9.20 — Owner backup-evidence capture

Record the owner Recovery screenshot for **`docuflow-db`**. **Not** a
restore, export, plan change, or 9.15 closure. Application code unchanged.

Time: **10 Nov 2026, 11:29 Asia/Jakarta (WIB)** (`2026-11-10T11:29:00+07:00`).
Baseline `origin/main`: **`04a0e90`** (PR #38 merge; expected).

9.15 addendum: `docs/reports/PHASE_9_15_BACKUP_PITR_ASSURANCE.md` §J.

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (screenshot transcribed) | **YES** |
| OWNER SCREENSHOT — AGENT VIEWED | **YES** (this image, this phase) |
| LOCALLY VERIFIED | **YES** (identity match, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| Restore / Create export / Connect | **NOT EXECUTED** |
| BACKUP ASSURANCE COMPLETE | **NO** |
| Phase 9.15 | **OPEN — latest restorable PITR timestamp UNKNOWN** |

## 1. What the screenshot shows

Header: PostgreSQL **`docuflow-db`**, plan **`0.1c-256mb`**, **Blueprint
managed**, Service ID **`dpg-dbiqe70ae00c73cdif7g-a`**. Page title
**Recovery**. **Connect** closed — no DSN in the crop.

Point-in-Time Recovery (exact words): restore from any timestamp in the
past **3 days**. **Restore database** visible. Pro upsell: 7-day window
(not the current window).

Export: retained at least **7 days**. One file **November 7, 2026 at
5:27 PM**, **`.dir.tar.gz`**. Timezone **not shown**. **Create export**
not clicked.

This confirms the 9.16 prompt fields that the 9.15/9.16 write-ups marked
**OWNER-REPORTED** without an agent-viewed image. It does **not** add a
restorable **clock**.

## 2. Paste template filled from the screenshot

```
inspection_time (Asia/Jakarta): 2026-11-10 11:29 (screenshot receipt)
service_name: docuflow-db
resource_id: dpg-dbiqe70ae00c73cdif7g-a
database_name: UNKNOWN (not on Recovery header)
status_available (YES/NO): UNKNOWN (not on this crop)
is_restore_drill (YES/NO): NO
plan_displayed: 0.1c-256mb
workspace_plan_if_shown: not labeled; Pro 7-day upsell present
recovery_page_title: Recovery
automated_backups_available: PITR section present
automated_backups_enabled: no named toggle; Restore database offered
backup_frequency: NOT DISPLAYED
backup_schedule: NOT DISPLAYED
latest_backup_timestamp: NOT DISPLAYED
latest_backup_timezone: NOT DISPLAYED
backup_status: NOT DISPLAYED
latest_restore_point_timestamp: UNKNOWN
latest_restore_point_label (exact UI words): any timestamp in the past 3 days
point_in_time_selection (YES/NO/UNKNOWN): Restore database visible; picker not opened
retention_or_recovery_window: 3 days
oldest_restore_point: NOT DISPLAYED
newest_restore_point: NOT DISPLAYED
pitr_section_present (YES/NO): YES
pitr_available (YES/NO/UNKNOWN): YES
pitr_enabled (YES/NO/UNKNOWN): UNKNOWN (no toggle)
logical_exports_listed (YES/NO): YES (1)
did_not_click_restore (YES): YES
did_not_click_create_export (YES): YES
```

## 3. Impact on 9.15 / RPO

| Prior gap (9.19) | After this screenshot |
| --- | --- |
| G-01 backup schedule | Still **NOT DISPLAYED** as a schedule. PITR copy is “any timestamp in the past 3 days” (continual window, not a cron). |
| G-02 latest restorable timestamp | Still **UNKNOWN**. Do **not** open Restore to find a picker. |
| G-03 enabled toggle | Still **no named switch**. PITR is **presented** with Restore database. |
| 3-day window / export 7 Nov 5:27 PM | Now **SCREENSHOT-VIEWED**, not only prompt text. |

**OBSERVED RPO: NOT DETERMINABLE** (no restorable clock vs 11:29 inspection).
Business RPO 24 hours remains **NOT DEMONSTRATED**. A 3-day window **could**
cover 24 hours; that is **not** a measured gap.

Phase 9.15 is **not** closed.

## 4. Safety

| Action | This phase |
| --- | --- |
| Application code / Blueprint / env / plan | **NO** |
| Production DSN / SQL / restore / export / cutover | **NO** |
| Screenshot committed to git | **NO** (avatar / Connect control; transcript only) |
| New infrastructure | **NO** |

## 5. Remaining owner input (only if visible without Restore)

If Recovery (or another **read-only** DB page) later shows a latest
restorable datetime, paste that timestamp and timezone. If it never
appears without clicking Restore, leave it **UNKNOWN**.

Do not Restore, Create export, Upgrade, or open Connect for this gap.
