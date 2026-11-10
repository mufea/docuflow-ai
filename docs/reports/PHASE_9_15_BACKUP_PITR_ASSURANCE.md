# Phase 9.15 — Backup and PITR assurance

Read-only owner-dashboard audit of **`docuflow-db`**. **No** backup settings
changed. **No** restore. **No** SQL. **No** DSN. **No** application code.
Phase 9.16 was **not** executed.

Time: **8 Nov 2026, 16:03 Asia/Jakarta (WIB)**.
Baseline `origin/main`: **`9de55d2`** (PR #32 merge; 9.14 cleanup
OWNER VERIFIED).

## Status

| Label | Status |
| --- | --- |
| IMPLEMENTED (checklist + this report) | **YES** |
| LOCALLY VERIFIED | **YES** (git baseline, identity from prior phases, `git diff --check`) |
| CI VERIFIED | **NOT EXECUTED** (docs-only) |
| OWNER VERIFIED (dashboard Recovery fields) | **NO** |
| INFRASTRUCTURE VERIFIED | **NOT EXECUTED** (this agent has no Render dashboard) |
| BACKUP ASSURANCE COMPLETE | **NO** |
| BLOCKED | Owner must inspect `docuflow-db` → **Recovery** and paste names/timestamps only |

PHASE 9.15 IMPLEMENTATION: **PARTIAL / DOCUMENTATION COMPLETE**.
PHASE 9.15 OWNER VERIFICATION: **BLOCKED / EVIDENCE REQUIRED**.

A successful 9.13B isolated restore does **not** prove current retention or
PITR. Live production Alembic remains inferred from that copy only.

## A. Metadata

| Field | Value |
| --- | --- |
| Phase | 9.15 |
| Inspection date | 8 Nov 2026 |
| Inspection time | 16:03 |
| Timezone | Asia/Jakarta (WIB, UTC+7) |
| Repository baseline | `9de55d2` |
| Production resource name | `docuflow-db` |
| Production resource ID | `dpg-dbiqe70ae00c73cdif7g-a` (prior owner; **reconfirm** on dashboard) |
| Production database name | **NOT VERIFIED** on live DSN |
| Verification method | Owner Dashboard Verification (this agent does not open Render) |

## B. Evidence classification (this pass)

| Finding | Class | Note |
| --- | --- | --- |
| Prior identity `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` | **OWNER-REPORTED** | Phases 9.11 / 9.13B. Reconfirm this phase. |
| 9.11 “backups enabled” | **OWNER-REPORTED** | Not a Recovery-page field dump. Insufficient for 9.15. |
| 9.13B restore-creates-new-instance | **OWNER-REPORTED** | Historical drill. Not current retention/PITR. |
| Render product PITR windows by **workspace** plan | **OFFICIAL DOCUMENTATION** | https://render.com/docs/postgresql-backups (fetched 8 Nov 2026). **Not** this account. |
| This workspace Hobby vs Pro | **UNKNOWN** | |
| This DB Recovery-page values | **UNKNOWN** | Dashboard not inspected this phase |
| Restore / PITR test in 9.15 | **NOT EXECUTED** | Forbidden |
| Guaranteed RPO | **UNKNOWN** | No provider commitment captured for this account |

## C. Evidence table

| Evidence | Observed value | Status | Evidence source |
| --- | --- | --- | --- |
| Production DB identity | Service `docuflow-db`; instance `dpg-dbiqe70ae00c73cdif7g-a` (prior) | OWNER-REPORTED / reconfirm | 9.11 / 9.13B |
| Automated backups | | UNKNOWN | Dashboard Recovery not read |
| Backup enabled | Owner said yes (9.11); current toggle **UNKNOWN** | UNKNOWN | Do not reuse 9.11 as 9.15 |
| Backup frequency | | UNKNOWN | |
| Latest backup | 9.13B restore time used 22:25 is **not** a current latest-backup field | UNKNOWN | |
| Latest restore point | | UNKNOWN | |
| Retention duration | Official docs: Hobby 3d / Pro+ 7d **if** paid PITR applies; **this account UNKNOWN** | UNKNOWN | Official docs ≠ dashboard |
| Oldest restore point | | UNKNOWN | |
| PITR available | Official: paid Postgres, not Free compute. This DB plan on Recovery page **UNKNOWN** | UNKNOWN | |
| PITR enabled | | UNKNOWN | Distinct from available |
| Historical selection | | UNKNOWN | |
| Recovery window | | UNKNOWN | |
| RPO observed gap | | NOT DETERMINABLE | Need observation time + latest restorable timestamp |
| Guaranteed RPO | | UNKNOWN | No contractual/policy evidence |
| Restore test | Not executed | NOT EXECUTED | 9.15 forbids restore |

## D. Official documentation (not this account)

Source: https://render.com/docs/postgresql-backups (8 Nov 2026).

- Paid Render Postgres: continual backup for **point-in-time recovery**.
  Restore creates a **new** instance. Cannot restore within ten minutes of now.
- Recovery window by **workspace** plan: Hobby past **3 days**; Pro or higher
  past **7 days**. Upgrade does not backfill.
- Free **compute** plan: **no** recovery capabilities.
- Logical exports: retained **seven days** after creation; not created on Free
  compute. Creating an export is a mutation — **do not** click Create export
  in this phase.

Do **not** treat these rows as `docuflow-db` facts until the dashboard shows
the same values.

## E. Owner dashboard checklist (you click; read-only)

Open **production** workspace. **Not** staging. **Not** the deleted drill
`docuflow-db-restore-drill-20261107`.

Do **not** click Restore Database, Start Recovery, Create export, plan
change, or any credential copy into chat.

### Check 1 — Identity

1. Open **`docuflow-db`**.
2. Confirm it is **not** the deleted restore-drill name.
3. Record instance id (`dpg-…`) if shown.
4. Record database name if shown (not the URL).
5. Record Available / status.
6. Record inspection time (Asia/Jakarta).

If the name is not `docuflow-db`, or the id is
`dpg-dbnk595g1s2s73cuafl0-a`, **STOP**.

### Check 2–5 — Recovery page

Open **Recovery** (sometimes labeled Backups). Copy **exact dashboard
words** for:

- Automated backups available / enabled
- Frequency or schedule
- Latest successful backup timestamp + timezone
- Backup status
- Latest restore point / restorable time (use Render’s label, not a synonym)
- PITR section present? Restore Database button visible? (do not click)
- Recovery window (e.g. 3 days / 7 days) if shown
- Oldest and newest restore bounds if shown
- Logical export table present? (do not Create export)
- Plan name and workspace plan if shown

### Check 6 — RPO

Do not calculate until both of these exist:

- Inspection timestamp (Asia/Jakarta)
- Latest **restorable** timestamp from the Recovery page (with timezone)

Then: observed gap = inspection time − latest restorable time.
That is **not** a guaranteed RPO.

### Paste back (names and times only)

```
inspection_time (Asia/Jakarta):
service_name:
resource_id:
database_name:
status_available (YES/NO):
is_restore_drill (YES/NO):
plan_displayed:
workspace_plan_if_shown:
recovery_page_title:
automated_backups_available:
automated_backups_enabled:
backup_frequency:
backup_schedule:
latest_backup_timestamp:
latest_backup_timezone:
backup_status:
latest_restore_point_timestamp:
latest_restore_point_label (exact UI words):
point_in_time_selection (YES/NO/UNKNOWN):
retention_or_recovery_window:
oldest_restore_point:
newest_restore_point:
pitr_section_present (YES/NO):
pitr_available (YES/NO/UNKNOWN):
pitr_enabled (YES/NO/UNKNOWN):
logical_exports_listed (YES/NO):
did_not_click_restore (YES):
did_not_click_create_export (YES):
```

No DSN, password, or screenshot that shows Connect URLs.

If a field is missing on the page, write **UNKNOWN** for that field.

## F. Limitations (current)

- Dashboard Recovery fields not captured this phase.
- 9.11 “backups enabled” is not retention, frequency, or PITR.
- 9.13B drill is restorability at one past point, not the live window.
- Workspace plan (Hobby vs Pro) unknown → official 3d/7d window not applicable yet.
- RPO **NOT DETERMINABLE**.
- No backup monitoring/alerting evidence.
- No 9.15 restore test (by design).

## G. Recommended next action

Owner completes section E. Then this phase can fill the evidence table
without guessing. Phase 9.16 (measured RTO/RPO) stays separate and needs
a **new** isolated restore authorization if a timing drill is wanted.

## H. Safety

| Action | This phase |
| --- | --- |
| Dashboard opened by this agent | **NO** |
| Backup settings changed | **NO** |
| Restore / export created | **NO** |
| Production DSN / SQL | **NO** |
| Application code / Blueprint | **NO** |
| Production cutover | **NO** |

## I. Later owner-reported screenshot (Phase 9.16 prompt)

**8 Nov 2026, 17:04 Asia/Jakarta.** This agent did **not** view the
screenshot. Class: **OWNER-REPORTED**.

- `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` / plan `0.1c-256mb` / Blueprint managed
- PITR recovery window **3 days** (Pro 7-day window mentioned, not used)
- Logical export successful; created 7 Nov 2026, 5:27 PM; `.dir.tar.gz`; ≥7 day retention

Still unknown at that write-up: latest restorable PITR timestamp; backup
schedule/enabled; operational PITR restore; measured RPO/RTO. Do not treat
addendum I as BACKUP ASSURANCE COMPLETE.

## J. Owner Recovery screenshot viewed (10 Nov 2026)

**10 Nov 2026, 11:29 Asia/Jakarta (WIB).** Owner sent a Recovery-page
screenshot in chat. **This agent viewed the image.** Class: **OWNER
SCREENSHOT — AGENT VIEWED**. This agent still has **no** Render dashboard
session and did **not** click Restore, Create export, Connect, or Upgrade.

Identity on the crop (matches protected production):

| Field | Value on screenshot |
| --- | --- |
| Header | PostgreSQL **`docuflow-db`** |
| Plan | **`0.1c-256mb`** |
| Blueprint | **Blueprint managed** |
| Service ID | **`dpg-dbiqe70ae00c73cdif7g-a`** |
| Page | **Recovery** |
| Connect | Dropdown **closed** (no DSN / URL in the crop) |

Exact PITR UI words:

> Recreate your database from a backup. You can choose to restore from
> any timestamp in the past **3 days**.

**Restore database** is visible and was **not** clicked. A Pro upsell
offers a **7-day** window; that is an offer, not this workspace’s current
window.

Export UI: “All database export files are retained for at least **7
days**.” One listed export: **November 7, 2026 at 5:27 PM**, file
**`.dir.tar.gz`**. **Create export** visible, **not** clicked. Export
clock timezone **not shown**.

| Evidence | Value from this screenshot | Class |
| --- | --- | --- |
| Production identity | `docuflow-db` / `dpg-dbiqe70ae00c73cdif7g-a` | **SCREENSHOT-VIEWED** |
| PITR section present | **YES** | **SCREENSHOT-VIEWED** |
| PITR available | **YES** (section + Restore database) | **SCREENSHOT-VIEWED** |
| PITR enabled toggle | **NOT DISPLAYED** | **UNKNOWN** as a named switch |
| Recovery window | **3 days** | **SCREENSHOT-VIEWED** |
| PITR selection | “any timestamp in the past 3 days” | **SCREENSHOT-VIEWED** (no clock) |
| Latest restorable PITR timestamp | **NOT DISPLAYED** | **UNKNOWN** |
| Backup schedule / frequency | **NOT DISPLAYED** (no cron/daily field) | **NOT INDEPENDENTLY CAPTURED** |
| Latest backup timestamp | **NOT DISPLAYED** | **UNKNOWN** |
| Database name | **NOT DISPLAYED** on this crop | **UNKNOWN** |
| Logical export | 1 row, 7 Nov 2026 5:27 PM, `.dir.tar.gz` | **SCREENSHOT-VIEWED** |
| Export retention copy | at least 7 days | **SCREENSHOT-VIEWED** |
| Observed RPO | still needs a restorable clock | **NOT DETERMINABLE** |

Do **not** click Restore to hunt for a datetime picker. If Recovery does
not show a latest restorable clock, leave it **UNKNOWN**.

PHASE 9.15: **OPEN — OWNER EVIDENCE REQUIRED** (latest restorable PITR
timestamp still **UNKNOWN**). BACKUP ASSURANCE COMPLETE: **NO**.
Full capture: `docs/reports/PHASE_9_20_OWNER_BACKUP_EVIDENCE.md`.
