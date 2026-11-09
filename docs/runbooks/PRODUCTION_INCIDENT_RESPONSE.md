# Production incident response

Owner-operated. Do **not** open production DSN, run migrations, restore
into `docuflow-db`, change env/plans, or rotate secrets unless a **separate**
approval line is on the chat. Do not paste credentials.

Timezone for notes: **Asia/Jakarta**. Record UTC too if the dashboard shows it.

Related:

- Recovery: `docs/operations/PRODUCTION_DATABASE_RECOVERY_RUNBOOK.md`
- Ops/logging: `docs/OPERATIONS.md`
- Audit: `docs/reports/PHASE_9_17_OPERATIONAL_HARDENING.md`

Severity (proposed): SEV-1 service down or data integrity; SEV-2 major
degradation; SEV-3 recoverable; SEV-4 informational.

## Common first steps

1. `GET https://docuflowai.site/health` then `/ready` (read-only).
2. `/health` 200 only means the process is up.
3. `/ready` 503 `status=degraded` names `database` / `storage` (inline
   `redis=true` is not a Redis ping).
4. Render dashboard: API, `docuflow-db`, `docuflow-cleanup` — status and
   recent logs (no DSN copy into chat).
5. Write incident start time. Write resolve time when `/ready` is 200 and
   the user-facing symptom is gone.

## Scenario 1 — API unavailable

1. Render → `docuflow-api` status (deploy, crash, spin-down).
2. Recent deploys and logs (`docuflow.*`, JSON).
3. `/health`. If it fails, the process is down — do not SQL.
4. `/ready` if `/health` works.
5. Classify app vs database vs storage from `/ready.checks`.
6. Escalate to owner for restart/deploy. Do not change `JOB_BROKER`.

## Scenario 2 — Database unavailable

1. Render → `docuflow-db` (`dpg-dbiqe70ae00c73cdif7g-a`). Available?
2. Metrics if shown (CPU, disk, connections) — names only.
3. API logs for `ready_database_failed`.
4. **No** DSN, SQL, migrate, stamp, or restore.
5. Restore only via the recovery runbook **and** a new isolated-restore
   approval. Never restore in-place onto `docuflow-db` while it is the live
   copy.
6. Isolated restore duration last measured **15 minutes** (9.16 T0/T1).
   That is **not** business RTO.

## Scenario 3 — Storage failure

1. `/ready` `storage` false or logs `ready_storage_failed` / TransientError.
2. Transient vs persistent (timeouts, 5xx, SlowDown vs AccessDenied).
3. Deletion path: `storage_deletions` outbox (leases, max 8 attempts). Do
   not run cleanup by hand.
4. No production upload/download/delete for diagnosis.
5. Keep log timestamps. Owner fixes credentials/bucket in dashboard.

## Scenario 4 — Cleanup cron failure

1. Render Cron `docuflow-cleanup` (`*/15 * * * *`). Last run result.
2. Logs for migrate lock or cleanup errors.
3. Overlap is handled by `cleanup_leases`; do not start a second job.
4. Do **not** manually run production cleanup. Owner approval required.
5. Do not change the schedule this incident.

## Scenario 5 — Suspected data loss

1. Stop writes if corruption is ongoing (owner scales API/cron).
2. Preserve logs and clocks. Do not overwrite `docuflow-db`.
3. Recovery points: dashboard PITR window (owner-reported **3 days**);
   logical export (7 Nov 2026, 5:27 PM, retention ≥7 days). Latest
   restorable instant **UNKNOWN** (9.15 open). Observed RPO **NOT
   DETERMINABLE**.
4. Isolated restore only, new name, identity gate, then owner cutover
   approval if ever needed. Cutover is **not** pre-authorized.

## Scenario 6 — Suspected credential exposure

1. Do not reprint the secret.
2. Record time, where it appeared, and which name (not value).
3. Notify owner. Rotation is owner-operated (`DOCUFLOW_SECRET_KEY`
   invalidates sessions; DB/S3 keys in Render/R2).
4. Agents must not rotate autonomously.

## After-action

- Incident start/end (Asia/Jakarta).
- Customer impact (yes/no, no PII).
- Root cause class (api / db / storage / cron / deploy / unknown).
- Follow-up (complete 9.15, alerts approval, etc.).
- No DSNs, passwords, or row dumps in git.
