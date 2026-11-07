# Phase 9.13A — Documentation consistency and recovery safety

Documentation-only. No restore, no production mutation, no application
code, no deploy.

Evidence time: **7 Nov 2026, 21:25 Asia/Jakarta (WIB)**.

## A. Baseline

| Item | Value |
| --- | --- |
| Working baseline | `581db69` (PR #25 merge; newer than the 9.13 note `3f178af`) |
| Phase 9.12 | **PRODUCTION VERIFIED** (owner smoke, 20:33 Asia/Jakarta) |
| Phase 9.13 | Audit + runbook **IMPLEMENTED**. Recovery drill **NOT VERIFIED**. Production Alembic **NOT VERIFIED**. |
| Production API / CMS | `https://docuflowai.site` / `https://docuflowai.online` |

## B. Documentation consistency (`docs/DEPLOYMENT.md`)

| Outdated statement | Correction | Evidence |
| --- | --- | --- |
| Stack listed PostgreSQL as Free | Blueprint `0.1c-256mb` (Basic); live plan owner-reported Basic | `infra/render.yaml`; 9.11 owner |
| “This repository is **NOT DEPLOYED**” | Production **is** deployed (9.12) | 9.12 report |
| Production layer “NOT DEPLOYED — Awaiting owner approval” | **PRODUCTION VERIFIED** (9.12); recovery/Alembic still **NOT VERIFIED** | 9.12 / 9.13 |
| Production “Exists today? NOT DEPLOYED” | Yes, with public URLs | 9.12 |
| Status table: Render **NOT DEPLOYED**; staging Blueprint/migration “not applied/performed”; production `0003` “not performed” | Production verified; staging apply + 9.10D inspect; prod `alembic_version` **NOT VERIFIED** | 9.10D / 9.12 / 9.13 |
| Mode A: `docuflow-db` Free | Git plan `0.1c-256mb`; live Redis absent | Blueprint; 9.11 owner |
| “Change … `docuflow-db` … to Free” with no warning | Do **not** downgrade production Postgres to Free | 9.11 paid Basic + backups |

Historical Free Postgres limits (30-day expiry, no backups) remain in the
doc as **staging / Free-tier** facts, not as the live production plan.

**Still NOT VERIFIED:** backup retention, frequency, PITR, last backup
timestamp, restore drill, production `alembic_version`.

## C. Recovery safety (`docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`)

**Previous weakness:** identity checks treated `staging` in host/name as
the main abort, and compared a drill to `docuflow-db` only in prose. A
drill DSN could still be production (`dpg-dbiqe70ae00c73cdif7g-a`) if the
operator skipped the prose.

**New gate (§5.1):** classify `production` / `staging` / `isolated-restore`
/ `ambiguous`. Restore proceeds **only** for `isolated-restore`.

| Requirement | How |
| --- | --- |
| Expected target | Owner-approved service name containing `restore` or `drill` |
| Actual host | Printed; must not contain production instance id |
| Database name | Printed; not guessed; unknown vs prod name → `ambiguous` → STOP |
| Environment classification | Four-way label above |
| Production rejection | Service `docuflow-db` or instance `dpg-dbiqe70ae00c73cdif7g-a` |
| Staging rejection | Staging is a live env, not a drill |
| Isolation | New instance; not attached to `docuflow-api` |
| Owner approval | Named target in chat **before** Restore |
| Failed check | **STOP** before dashboard Restore or `pg_restore` |
| Cleanup | Delete drill instance only; leave `docuflow-db` |

No executable restore automation was added (docs-only).

## D. Safety verification

| Action | Occurred |
| --- | --- |
| Production database mutation | **NO** |
| Database restore | **NO** |
| Paid infrastructure provisioned | **NO** |
| Production deployment | **NO** |
| Application code changed | **NO** |

## E. Outstanding limitations

- Backup retention **NOT VERIFIED**
- PITR **NOT VERIFIED**
- Last backup timestamp **NOT VERIFIED**
- Isolated restore drill **NOT VERIFIED** / **BLOCKED** on owner approval
- Production Alembic revision **NOT VERIFIED**
- Production SQL database **name** **NOT VERIFIED** (instance id is known)

## Status labels

| Item | Status |
| --- | --- |
| Deployment doc vs 9.12 | Corrected |
| Recovery production-target rejection | Documented |
| Recovery drill | **NOT VERIFIED** |
| Production recovery ready | **NO** |
