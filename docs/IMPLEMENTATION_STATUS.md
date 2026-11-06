# Implementation status

Phases are marked complete only when commands below were executed and passed.

## Environment inspected (Phase 0)

- OS: Ubuntu 24.04.5, x86_64
- Workspace: empty git repo on `main` (`Initialize project` only)
- Python 3.12.3, Node v22.23.4, pnpm 10.33.4, uv 0.13.6
- Docker: not available
- PostgreSQL 16 and Redis 7 installed for local use; default app path is SQLite + inline jobs
- Tesseract OCR is optional; RapidOCR ONNX is bundled. LibreOffice not installed
- PixelForge was not present and was not modified

## Phase 0 — Discovery and scaffold — verified

Implemented: monorepo layout, uv Python package, pnpm workspace, `.env.example`, docs, Render Blueprint, docker-compose for optional deps.

## Phase 1 — Core PDF engine hardening — verified on `feat/phase-1-pdf-engine-hardening`

Base: `main` @ `da4ee00`. `main` was not modified.

Fixes in `PdfEngine`:

- `max_pages` is enforced by `inspect()`, `split()`, and the existing `_check_pages` path used by extract/reorder/rotate/delete/compress/images/text/thumbnails/merge.
- `_check_tuple()` now uses `validate_range_tuple()` so reversed, zero, oversize, and malformed tuples raise `PageRangeError`.
- `_guard_output()` blocks writing to a path that resolves to an input (relative, absolute, or symlink).
- Writes go through a `.partial` file then `replace`, so a failed conversion does not leave a half-written PDF.
- `images_to_pdf()` counts GIF frames toward `max_pages` before emitting pages. `max_images` still limits input files.

Engine limits that remain: encryption still needs a password; compression may not shrink every file; LibreOffice is not required.

Verification for this hardening branch:

```
uv run pytest tests/pdf -q
# 38 passed

uv run pytest -q
# 66 passed

uv run ruff check src tests
# All checks passed

uv run ruff format --check src/docuflow/pdf tests/pdf
# 9 files already formatted

uv run mypy src/docuflow/pdf
# Success: no issues found in 5 source files

git diff --check
# clean
```

Full-repo `uv run ruff format --check src tests` still wants to reformat
`tests/test_database_url.py` (pre-existing on main; not changed here).
Full-repo `uv run mypy src/docuflow` still fails in `services/seed.py` on
`DEFAULT_PLANS` dict types (pre-existing on main; not changed here).

## Phase 2–7 — Persistence, web, conversion, AI, billing, admin — implemented and covered by suite

Not every operational path (live Stripe, live OpenAI, LibreOffice) is exercised; those are mocked or marked unavailable.

## Render signup JSON proxy — verified on `feat/phase-1-pdf-engine-hardening`

Word→PDF no longer requires LibreOffice. The job uses a built-in
python-docx + PyMuPDF renderer when `soffice` is missing, so Render Free
hosts can convert DOCX. Complex Word layout stays approximate.

Signup/login through `/v1` now retries HTML, 502/503, and truncated JSON; maps
Starlette `Invalid host header` to JSON; rejects a self-proxy
`API_INTERNAL_URL`; and production host checks return JSON. Register no longer
fails after the user row is committed if verify-email sending throws.

```
uv run pytest -q
# 71 passed

pnpm --filter web test
# 15 passed
```

## Phase 8 — Render production readiness — merged

Merged to `main` as `11dbfd0bb21eb29d87db073142d96bda9c08e46c`
(`Merge pull request #1 from mufea/feat/phase-8-render-readiness`).
GitHub `main` was verified at that commit before Phase 9 work began.

Hardening in this phase:

- `/ready` actually pings storage (S3 `head_bucket` or writable filesystem).
- Production readiness checks for secret, Postgres, S3 credentials, and RQ Redis.
- Job runner claims `queued` rows atomically so duplicate enqueue cannot double-charge.
- RQ enqueue uses `WORKER_TIMEOUT_SECONDS` and ignores stale worker heartbeats.
- API boot migrations use `python -m docuflow.migrate` with a Postgres advisory lock.
- Blueprint documents two modes: API `JOB_BROKER=inline` (minimal cost) vs worker `rq`.
- Docs no longer claim `JOB_BROKER=rq` is mandatory in production.

Local tests for Phase 8 were recorded on `feat/phase-8-render-readiness`.
Live Render deployment was **not** verified from this environment.

Verification recorded on that branch:

```
uv run pytest -q
# 93 passed

uv run ruff check src tests
# All checks passed

uv run ruff format --check src tests
# Would reformat tests/test_database_url.py (pre-existing on main; not changed)

uv run mypy src/docuflow
# Fails in services/seed.py DEFAULT_PLANS dict types (pre-existing)
# New Phase 8 modules typecheck clean

pnpm --filter web test
# 15 passed

pnpm --filter web lint
# passed

pnpm --filter web typecheck
# passed

pnpm --filter web build
# passed

git diff --check
# clean
```

## Commands executed

```
uv run pytest -q
# 45 passed

uv run ruff check src tests
# All checks passed

uv run ruff format --check src tests
# 71 files already formatted

uv run mypy src/docuflow
# Success: no issues found in 61 source files

pnpm --filter web test
# 2 passed

pnpm --filter web lint
# passed (0 errors)

pnpm --filter web typecheck
# passed after replacing Next generated LayoutProps/PageProps with explicit types

curl http://127.0.0.1:43124/health
# {"status":"ok","service":"docuflow-api"}

curl http://127.0.0.1:43124/ready
# {"status":"ready","checks":{"database":true,"redis":true,"storage":true}}

curl http://127.0.0.1:43123/
# HTTP 200 (landing, tools, pricing, register, login, merge workspace)
```

## OCR without Tesseract — verified on `feat/phase-8-render-readiness`

Render native Python does not ship `tesseract`. OCR stays enabled with
`OCR_ENABLED=true` and uses RapidOCR ONNX (`rapidocr` + `onnxruntime`) when
Tesseract is missing. Tesseract is still preferred when it is on PATH.

```
uv run pytest -q
# 101 passed
```

## Honest limitations

- Word→PDF uses a built-in python-docx + PyMuPDF converter when LibreOffice is missing. Complex Word layout is approximate.
- OCR uses RapidOCR ONNX when Tesseract is missing. Accuracy depends on scan quality; handwriting may be incomplete.
- Live Stripe/Midtrans/OpenAI calls are not made. Webhooks and the mock AI provider are tested with fixtures.
- Render deployment has not been performed or verified.
- Automated unit tests use SQLite. PostgreSQL integration tests run locally when `TEST_DATABASE_URL` is set, and in GitHub Actions against an isolated `postgres:16` service. Credit `FOR UPDATE` locking is fully meaningful on Postgres.
- Next.js “Publish to Vercel” is not the production path. The default Render stack is web + API + Postgres + object storage + one cleanup cron. A paid worker and Redis are optional scaling pieces (`JOB_BROKER=rq`), not required for inline jobs.

## Phase 9 — Production safety and data integrity — merged

Merged to `main` as `61294af2f0f2c1445b64e480d58f728d0584af55`
(`Merge pull request #2 from mufea/cursor/phase-9-production-safety-3b1a`).

Fixes:

- `seed_reference_data()` no longer mass-updates `User.plan_slug` to Free.
- Catalog seed may insert missing plans/costs, update name/`is_public`, and raise (never lower) plan limits. Feature flags are merged. Credit balances and ledger rows are untouched.
- `CreditService.grant()` is idempotent on the ledger key before mutating balance.
- Monthly period refresh checks the grant ledger key before adding allowance, after locking the account.
- Abandoned `processing` jobs refund reserved credits.
- Completed jobs record `credits_settled`.
- Duplicate payment events that race the unique constraint return `duplicate`.
- Subscription webhooks upsert by provider subscription id instead of inserting a new row each time.
- `customer.subscription.updated` no longer invents a credit grant.
- Document delete marks the row deleted, then removes storage (orphan object is preferred over an accessible row whose bytes are already gone).
- GitHub Actions CI at this merge ran Python tests/lint/typecheck and web lint/typecheck/tests/build, with no Postgres or Redis services. Later phases added a `postgres:16` CI service for integration tests; see Phase 9.2. Redis is still not started in CI.

Local verification (this branch):

```
uv run pytest -q
# 110 passed

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 65 source files

pnpm --filter web lint
# passed

pnpm --filter web typecheck
# passed

pnpm --filter web test
# 15 passed

pnpm --filter web build
# passed

git diff --check
# clean
```

Local verification for Phase 9 was recorded on `cursor/phase-9-production-safety-3b1a` (110 passed).
Live deployment verification: **not performed**.

## Phase 9.1 — Runtime reliability hardening — merged

Merged to `main` as `bce1a60` (`Merge pull request #3 from mufea/cursor/phase-9-1-runtime-reliability-3b1a`).
Recorded on feature branch `cursor/phase-9-1-runtime-reliability-3b1a` before that merge.

- Abandoned-job and expired-file cleanup run on a 15-minute Render Cron (`python -m docuflow.cleanup`) and on an in-process interval thread in the API/worker. Cleanup is not attached to HTTP requests.
- Overlapping cleanup is serialized (`cleanup_leases`). Phase 9.2 later replaced session-level PostgreSQL advisory locks on this path because they are unsafe with connection pooling. Job fail uses an atomic `processing` claim; refunds stay ledger-idempotent.
- Stale threshold is `JOB_STALE_MINUTES` (default 90), never below worker timeout plus grace. Active jobs with a recent `heartbeat_at` are left alone.
- Storage deletes go through `storage_deletions` with bounded exponential backoff. A failed object delete never undeletes the document row.
- Structured logs count abandoned jobs, refunded credits, expired documents, storage failures/retries, and duration. No secrets, keys, URLs, or file contents.

Local verification (this branch):

```
uv run pytest -q
# 119 passed

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 67 source files

pnpm --filter web lint
# passed

pnpm --filter web typecheck
# passed

pnpm --filter web test
# 15 passed

pnpm --filter web build
# passed

git diff --check
# clean
```

GitHub Actions: **not observed from that feature-branch environment.** Later `main` CI (from Phase 9.2 onward) is recorded below. Live deployment verification: **not performed**.

## Phase 9.2 — Cost-efficient reliability — merged

Merged to `main` as `6be627d9102ee5eaa9e1f393a7ddb60d934e1bf1`
(`Merge pull request #5 from mufea/cursor/phase-9-2-cost-efficient-reliability-8f43`)
on 5 Nov 2026, 16:19 Asia/Jakarta. Feature branch
`cursor/phase-9-2-cost-efficient-reliability-8f43` is historical.

Implemented:

- Job failure status and credit refund commit in one transaction (`fail_job_and_refund`). Ledger key `refund:{job_id}` remains the idempotency mechanism; concurrent duplicates hit the unique constraint and are treated as already refunded. Settled jobs are not refunded. Missing or partial reserved balances never drive `reserved` negative. Cleanup also refunds stranded `failed`/`cancelled` rows.
- Cleanup coordination uses the `cleanup_leases` table on every database (atomic `UPDATE` of an expired or unowned row). Session-level PostgreSQL advisory locks were removed because they are unsafe with connection pooling. Owner-only release/renew; expired leases are reclaimable after a crash.
- Storage deletion outbox reclaims `in_progress` rows whose lease expired. Object delete is idempotent. Completed rows are not processed again.
- Render default stack: `JOB_BROKER=inline`, no paid worker service, one cleanup cron, API `CLEANUP_INTERVAL_SECONDS=0`. Redis remains listed for compatibility and is unused while jobs are inline. Queue scaling is documented in `infra/render.scaling.yaml`.
- CI runs SQLite unit tests and PostgreSQL integration tests against an isolated `postgres:16` service. Tests never use production.

Not implemented (explicit non-goals): live AI providers, payment/pricing changes, production RQ migration, production deploy, production migrations.

Database: Alembic `0003_cost_efficient_reliability` (additive, backward compatible). **Not applied to production.**

Live deployment verification: **NOT DEPLOYED — Awaiting owner approval.**

Verification recorded on the merged commit (do not treat as a production deploy):

Local (feature branch, before merge) and GitHub Actions on `main` @ `6be627d`
([CI run 42001480346](https://github.com/mufea/docuflow-ai/actions/runs/42001480346), conclusion **success**, 5 Nov 2026, 16:19 Asia/Jakarta):

```
uv run pytest -q -m "not integration"
# 152 passed, 9 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 9 passed, 152 deselected

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 70 source files

pnpm --filter web lint / typecheck / test / build
# lint passed; typecheck passed; 15 tests passed; production build passed
```

CI starts an isolated `postgres:16` service for integration tests. It does not use production. Redis is not started in CI.

Staging deployment: **not performed.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration of Alembic `0003`: **not applied / not verified.**

## Phase 9.3 — Documentation accuracy, lease follow-up, cost docs — merged

Merged to `main` as `15a9e278d64ad8ee17ba3b2b2403d79d48196388`
(`Merge pull request #6 from mufea/cursor/phase-9-3-docs-reliability-followup`)
on 5 Nov 2026, 17:33 Asia/Jakarta. Feature branch
`cursor/phase-9-3-docs-reliability-followup` is historical.

Base at the time of the work: GitHub `main` @ `6be627d9102ee5eaa9e1f393a7ddb60d934e1bf1` (Phase 9.2 already merged). This phase did not repeat Phase 9.2.

Implemented:

- Documentation now states that Phase 9.2 is merged, records the merge commit, and separates local verification, GitHub Actions CI, staging deployment, and production deployment.
- Storage deletion: S3 HTTP connect/read timeouts are bounded so one delete attempt (including client retries) stays under half of `STORAGE_DELETE_LEASE_MINUTES`. Timeouts are `TransientError` (retry), not “object missing.” Finish/fail/renew updates remain owner-token conditional. Duplicate object deletes are still possible if a provider ignores the timeout; they are idempotent.
- Cleanup: the runtime lease is heartbeaten between expired-document rows and between storage-deletion items. A process that loses the cleanup lease stops remaining work. No SQLAlchemy session is shared across threads; there is no heartbeat *during* a single blocking storage call.
- Staging migration procedure and rollback limits are documented. Alembic `0003` is **not** applied to production from this environment.
- Default Render stack is unchanged: web + API + Postgres + cleanup cron + optional Free Key Value. No paid worker. `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`.

Not implemented (explicit non-goals): production deploy, production migration, live AI/email/billing, Redis upgrade, new always-on worker, architectural rewrite.

Local verification (this branch):

```
uv run pytest -q -m "not integration"
# 158 passed, 9 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 9 passed, 158 deselected

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 71 source files

pnpm --filter web lint
# passed

pnpm --filter web typecheck
# passed

pnpm --filter web test
# 15 passed

pnpm --filter web build
# passed

git diff --check
# clean
```

GitHub Actions: observed on `main` after merge as part of later CI history; this section records the Phase 9.3 local counts above. Staging and production were **not** deployed in Phase 9.3.

Staging deployment: **not performed.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration: **not performed.**

## Phase 9.4 — Storage reliability and retry hardening — merged

Merged to `main` as `72beac5fb47438bf0589cf7521192eadab917e7d`
(`Merge pull request #7 from mufea/cursor/phase-9-4-storage-reliability`)
on 5 Nov 2026, 18:46 Asia/Jakarta. Implementation commit
`de5e8363edcd2ecd1b374759a9bb9afaa28f683f`. Feature branch
`cursor/phase-9-4-storage-reliability` is historical.

Base at the time of the work: GitHub `main` @ `15a9e278d64ad8ee17ba3b2b2403d79d48196388` (Phase 9.3 already merged). This phase did not repeat Phase 9.3.

Implemented:

- Botocore client retries use `total_max_attempts=2` (one initial HTTP request and at most one retry). `max_attempts` is not used; on botocore 1.43 that key means extra retries and would have allowed three tries.
- Timeout budget: `attempts × (connect + read)` stays at or below half of `STORAGE_DELETE_LEASE_MINUTES`. Designed ceiling adds the documented 20s standard-mode backoff cap per retry. This is **not** a hard SDK wall-clock deadline (jitter, Retry-After, DNS, providers that ignore client timeouts).
- S3 `ClientError` is classified: missing (`NoSuchKey` / HTTP 404) vs authorization (`AccessDenied`, invalid keys, 403) vs transient (5xx, `SlowDown`, throttling) vs permanent (`NoSuchBucket` and other config failures). `AccessDenied` cannot complete a deletion or look like a missing object. Public messages stay generic; logs record operation, classification, code, and HTTP status only.
- Download transfer retries are not stacked (`num_download_attempts=1`); application `storage_deletions` retries remain the separate bounded outbox.
- Cleanup lease heartbeats and owner-token finish rules from Phase 9.3 are unchanged.

Not implemented: production deploy, production migration, live object-storage verification, new infrastructure.

Local verification (this branch):

```
uv run pytest -q tests/test_phase94_storage.py tests/test_phase93_reliability.py tests/test_phase92_storage.py tests/test_phase92_leases.py tests/test_phase91_cleanup.py
# 57 passed

uv run pytest -q -m "not integration"
# 178 passed, 9 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 9 passed, 178 deselected

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 71 source files

git diff --check
# clean
```

Web lint/typecheck/tests/build: **not run** (no frontend or shared-interface changes).

GitHub Actions on the merge commit `72beac5` (workflow **CI**,
[run 42021659758](https://github.com/mufea/docuflow-ai/actions/runs/42021659758),
conclusion **success**, created 5 Nov 2026, 18:46 Asia/Jakarta):

- unit: 178 passed, 9 deselected
- integration: 9 passed, 178 deselected (`postgres:16`)
- ruff passed; mypy 71 files; web 15 tests + production build passed

Staging deployment: **not performed.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration: **not performed.**

## Phase 9.5 — Staging and production readiness verification — merged

Merged to `main` as `068d6afadc445218336f8702e66a5c89c94055af`
(`Merge pull request #8 from mufea/cursor/phase-9-5-staging-readiness`).
Feature branch `cursor/phase-9-5-staging-readiness` is historical.

Base at the time of the work: GitHub `main` @ `72beac5fb47438bf0589cf7521192eadab917e7d` (Phase 9.4 already merged; matches the expected merge SHA). Implementation commit of Phase 9.4 is `de5e8363edcd2ecd1b374759a9bb9afaa28f683f`. This phase did not repeat Phases 9.1–9.4.

Scope: verification-first. No product features, no paid worker, no Redis requirement, default `JOB_BROKER=inline`, `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`. No production deploy, no production migration, no live Stripe/Midtrans/AI/email.

### Status vocabulary used below

| Label | Meaning |
| --- | --- |
| Implemented | Code or docs exist in this repository |
| Locally tested | Executed in this environment |
| CI verified | GitHub Actions on the named commit |
| Provider verified | Live S3-compatible bucket with dedicated test credentials |
| Staging verified | Applied to a non-production Render (or equivalent) environment |
| Production verified | Owner-approved live workspace |

### Workstream results

**A. Repository and CI audit — CI verified on `main` @ `72beac5` and on this branch @ `a52929d`.**

- Repository: `https://github.com/mufea/docuflow-ai`
- `origin/main` HEAD: `72beac5fb47438bf0589cf7521192eadab917e7d` (Merge PR #7). Matches the expected baseline.
- Phase 9 through 9.4 are on `main`. Python lockfile, Alembic chain `0001` → `0002_runtime_reliability` → `0003_cost_efficient_reliability`, GitHub Actions workflow **CI**, Render Blueprint, health/ready, storage, cleanup scheduling, and `JOB_BROKER=inline` were inspected and left in place.
- GitHub Actions on latest `main` (do not treat this as this feature branch):

  | Field | Value |
  | --- | --- |
  | Workflow | CI |
  | Run URL | https://github.com/mufea/docuflow-ai/actions/runs/42021659758 |
  | Commit SHA | `72beac5fb47438bf0589cf7521192eadab917e7d` |
  | Conclusion | success |
  | Timestamp | 5 Nov 2026, 18:46 Asia/Jakarta (`createdAt` 2026-11-05T11:46:21Z) |

  CI workflow itself was not modified.

- GitHub Actions on this feature branch (implementation commit `a52929d`):

  | Field | Value |
  | --- | --- |
  | Workflow | CI |
  | Run URL | https://github.com/mufea/docuflow-ai/actions/runs/42024681610 |
  | Commit SHA | `a52929d8c48822fdd1330ce9a39b2250c37794c9` |
  | Conclusion | success (2 checks: Python tests and checks; Web lint, typecheck, tests, and build) |
  | Timestamp | 5 Nov 2026, 19:08 Asia/Jakarta (`createdAt` 2026-11-05T12:08:55Z) |

**B. Database migration `0003_cost_efficient_reliability` — locally tested on isolated PostgreSQL; not staging verified; not production verified.**

- Upgrade from `0002_runtime_reliability` keeps existing `storage_deletions` rows and the seeded `cleanup_leases.token`.
- New nullable columns: `cleanup_leases.acquired_at` / `updated_at`; `storage_deletions.started_at` / `lease_until` / `owner_token`.
- Index `ix_storage_deletions_lease_until` is created.
- After upgrade, `alembic` current equals head `0003_cost_efficient_reliability`, and `acquire_lease` / `release_lease` work against the migrated schema.
- Downgrade was run only on a disposable local database. It drops those columns and the lease index. Pre-existing `storage_key` / `attempts` survive. In-flight lease timestamps and deletion owner tokens are lost. That is **not** a lossless production rollback.

**C. S3-compatible storage — locally tested with mocks; provider verification pending.**

Phase 9.4 classification/retry/timeout logic was not rewritten. Added regression coverage for signed URL success, signed-URL ClientError returning `None` without leaking signatures, `InvalidAccessKeyId`, and a successful mocked `put`/`exists`. Existing Phase 9.4 tests already cover missing objects, AccessDenied, NoSuchBucket, HTTP 500/503, SlowDown, retries, timeout budget, and cleanup outbox authorization/transient paths.

Live provider test `test_optional_live_s3_provider_roundtrip` is skipped unless dedicated `TEST_S3_BUCKET` / `TEST_S3_ACCESS_KEY_ID` / `TEST_S3_SECRET_ACCESS_KEY` are set. It uses prefix `docuflow-phase95/<uuid>/` and deletes only that object. **Mocked tests do not establish real provider compatibility.**

**D. Cleanup and reliability — locally tested (existing Phase 9.2/9.3 suites; no code change).**

Existing tests already cover lease acquisition, heartbeat, owner-token finish, expired reclaim, concurrent skip, crash during deletion, transient storage failure, authorization failure, duplicate deletion, retry exhaustion, owner-token mismatch, and not processing another worker’s active lease. Credit refund idempotency remains in the Phase 9.2 refund suite. No extra always-on worker was added.

**E. Health and readiness — locally tested; not staging verified.**

`/health` remains process liveness (`status` + `service`). `/ready` checks database, storage, and Redis-only-when-RQ, and returns `ready` or `degraded` without credentials, connection strings, signed URLs, or exception text. A regression test now poisons storage with a fake DSN/signature/traceback and asserts those strings never appear in the JSON body. Endpoints were not duplicated.

**F. Render deployment readiness — documented and locally asserted; not deployed.**

`infra/render.yaml` still has Next.js web, FastAPI API (`JOB_BROKER=inline`, `AI_PROVIDER=mock`, `EMAIL_BACKEND=console`), PostgreSQL, cleanup cron (`python -m docuflow.migrate && python -m docuflow.cleanup`), optional Free Redis, `healthCheckPath: /health`, and migrate-on-boot. No paid worker. Blueprint was not applied. Production environment settings were not modified.

**G. Security and billing regression — locally tested; live payments not activated.**

Cross-user GET/download/delete remain 403. CSRF, credit reservation/settlement/refund, duplicate payment webhooks, and subscription upsert coverage from earlier phases still pass in the unit suite. No live Stripe or Midtrans calls.

Implemented in this phase (smallest verification gaps only):

- Isolated PostgreSQL Alembic scenarios for `0003` (upgrade from `0002`, data preservation, index, current/head, app lease compatibility, disposable downgrade).
- Readiness secret-leak regression, signed-URL mocks, `InvalidAccessKeyId`, optional skipped live S3 test, download isolation assertion, Blueprint `EMAIL_BACKEND` / health-check / migrate assertions.
- Documentation of actual verification layers.

Bugs fixed: none in application code. Phase 9.4 storage behavior was preserved.

Not implemented: production deploy, production migration, staging deploy, live object-storage verification, live billing, live AI, paid worker, Redis as a required service.

Local verification (this branch):

```
uv run pytest -q -m "not integration"
# 184 passed, 1 skipped, 10 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 10 passed, 186 deselected

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 71 source files

git diff --check
# clean
```

The skipped test is the optional live S3 provider roundtrip (no `TEST_S3_*` credentials in this environment). Web lint/typecheck/tests/build were **not run locally** (no frontend or shared-interface changes); GitHub Actions ran them on this branch and they passed.

GitHub Actions for this feature branch on `a52929d` (workflow **CI**,
[run 42024681610](https://github.com/mufea/docuflow-ai/actions/runs/42024681610),
conclusion **success**, 5 Nov 2026, 19:08 Asia/Jakarta):

- unit: 184 passed, 1 skipped, 10 deselected
- integration: 10 passed, 185 deselected (`postgres:16`)
- ruff passed; mypy 71 files; web 15 tests passed (lint/typecheck/build job succeeded)

Staging deployment: **not performed.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration: **not performed.**

## Phase 9.6 — Production safety and reliability — merged

Merged to `main` as `d65f087771f43e50780ea2ab87466b8a93f80dc5`
(`Merge pull request #9 from mufea/cursor/phase-9-6-production-safety`)
on 5 Nov 2026, 21:13 Asia/Jakarta. Implementation commit
`956c66deb8afc4de5b4a9d382483748d515e4808`. Documentation follow-up
`d29a9649597dd8e41ba2259fe3b659bb5a4a61ee`. Feature branch
`cursor/phase-9-6-production-safety` is historical.

Base at the time of the work: GitHub `main` @ `068d6afadc445218336f8702e66a5c89c94055af` (Phase 9.5 already merged via PR #8). This phase did not repeat Phases 9.1–9.5.

Scope: fail-fast production configuration, `/ready` HTTP semantics, queued-job recovery on process start, database backup documentation, optional live S3 test hygiene, and documentation layers. No product features, no paid worker, no new Redis requirement, no production deploy.

### Workstream results

**A. Production configuration fail-fast — implemented and locally tested.**

`DOCUFLOW_ENV=production` (`Settings.env`, not a separate `APP_ENV` flag) now refuses to start when critical configuration is unsafe: weak/default/short secret, SQLite, non-S3 storage or missing S3 credentials, or `JOB_BROKER=rq` without a `redis://` / `rediss://` URL. Optional gaps (`AI_PROVIDER=mock`, `EMAIL_BACKEND=console`) are warnings only and do not block startup. Redis is not required for `JOB_BROKER=inline`. Development and test environments still start on SQLite. Secret values and DSNs are not written to logs.

**B. Readiness HTTP status — implemented and locally tested.**

`/health` remains process liveness and stays HTTP 200 when dependencies fail. `/ready` returns HTTP 200 when required dependencies are up and HTTP 503 when database, storage, or (only if `JOB_BROKER=rq`) Redis fails. Zero RQ workers remain informational. Render `healthCheckPath` is still `/health`.

**C. Background job recovery — implemented and locally tested.**

On API lifespan start, up to 100 durable `queued` rows are re-enqueued. Duplicate delivery is safe because the runner claims only `status=queued`. `processing` rows are not reset; stale-job cleanup still fails them after `JOB_STALE_MINUTES` with a single refund. No new queue, schema, or paid worker.

**D. Database backup documentation — documented; not executed against any hosted database.**

`docs/DEPLOYMENT.md` now has a practical `pg_dump` / restore checklist. It does **not** claim that a live production database is on the Render Free plan. Backup/restore was not run against staging or production.

**E. Optional live S3 provider test — implemented; provider verification pending.**

The existing skipped roundtrip still requires dedicated `TEST_S3_*` credentials, uses prefix `docuflow-test/<uuid>/`, and deletes only that key. **Not provider verified.**

**F. Deployment documentation — updated.**

Verification layers distinguish implemented / locally tested / CI verified / provider / staging / production. Phase 9.5 historical results are unchanged except the verified merge of PR #8 onto `main` @ `068d6af`.

Bugs fixed:

- Production could boot with SQLite, filesystem storage, or the development secret (errors were logged only).
- `/ready` returned HTTP 200 while reporting `degraded`, which is not a usable readiness signal.
- `queued` jobs after an API restart waited for a client GET before re-enqueue (now also recovered at startup).

Not implemented: production deploy, production/staging migration, live S3, live billing, live AI, paid worker.

Local verification (this branch):

```
uv run pytest -q -m "not integration"
# 197 passed, 1 skipped, 10 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 10 passed, 198 deselected

uv run ruff check src tests
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 72 source files

git diff --check
# clean
```

The skipped test is the optional live S3 provider roundtrip (no `TEST_S3_*` credentials). Web lint/typecheck/tests/build were **not run locally** (no frontend or shared-interface changes); GitHub Actions ran them on this branch and they passed.

GitHub Actions for this feature branch on `956c66d` (workflow **CI**,
[run 42041167330](https://github.com/mufea/docuflow-ai/actions/runs/42041167330),
conclusion **success**, 5 Nov 2026, 21:02 Asia/Jakarta):

- unit: 197 passed, 1 skipped, 10 deselected
- integration: 10 passed, 198 deselected (`postgres:16`)
- ruff passed; mypy 72 files; web 15 tests passed (lint/typecheck/build job succeeded)

Staging deployment: **not performed / not verified.**
Live S3 provider verification: **pending.**
PostgreSQL migration `0003`: locally tested (Phase 9.5); **not staging verified.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration: **not performed.**
Production deployment authorized: **NO.**

## Phase 9.7 — Staging readiness and deployment verification — merged

Merged to `main` via PR #10. Merge commit: `e16956aaa09b446cf9f41ef2ecdd453a32e9a73e` (6 Nov 2026, 06:13 Asia/Jakarta). Feature branch was `cursor/phase-9-7-staging-readiness`. Implementation commit: `8e7eb329dea06bf0a7388b9079316306d31c981b`. `main` CI on the merge: [run 42127934723](https://github.com/mufea/docuflow-ai/actions/runs/42127934723), success.

Base at the time: GitHub `main` @ `d65f087771f43e50780ea2ab87466b8a93f80dc5` (Phase 9.6 already merged via PR #9). This phase does not repeat Phases 9.1–9.6.

Scope: documentation accuracy after the Phase 9.6 merge, isolated staging Blueprint template, migration/S3/smoke checklists, and regression coverage. No product features, no paid worker, no Render apply, no production deploy.

### Workstream results

**A. Documentation consistency — implemented.** Phase 9.6 is recorded as merged. Staging, provider, and production remain unverified.

**B. Staging configuration — template prepared; staging verified: no.** `infra/render.staging.yaml` uses isolated service names and `JOB_BROKER=inline`. Apply only in a dedicated Render workspace after owner approval. Production `infra/render.yaml` service settings are unchanged.

**C. PostgreSQL migration 0003 — locally tested (existing Phase 9.5 integration tests); staging verified: no.** Staging migration checklist is in `docs/DEPLOYMENT.md`.

**D. S3 provider — live test still skipped without `TEST_S3_*`; provider verified: no.** Owner procedure documented. Mocked tests are not provider verification.

**E. Production safety — locally tested (Phase 9.6 regression tests).** Fail-fast and `/health`/`/ready` semantics unchanged.

**F. Queued-job recovery — locally tested (Phase 9.6 regression tests).** Limit remains 100 queued rows.

**G. Staging smoke — procedure prepared; NOT EXECUTED against a staging environment.** `scripts/staging_smoke.py` exits 2 when `STAGING_API_URL` is unset.

**H. Readiness report —** `docs/PHASE_9_7_READINESS_REPORT.md`.

Local verification (this branch):

```
uv run pytest -q -m "not integration"
# 201 passed, 1 skipped, 10 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 10 passed, 202 deselected

uv run ruff check src tests scripts
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 72 source files

git diff --check
# clean
```

The skipped test is the optional live S3 provider roundtrip (no `TEST_S3_*`).
`scripts/staging_smoke.py` without `STAGING_API_URL`: **NOT EXECUTED** (exit 2).
Web lint/typecheck/tests/build: **not run locally**. GitHub Actions for this
feature branch: **CI verified** on `2cbecde` (workflow **CI**,
[run 42046952750](https://github.com/mufea/docuflow-ai/actions/runs/42046952750),
conclusion **success**, 5 Nov 2026, 21:38 Asia/Jakarta): unit 201 passed,
1 skipped, 10 deselected; integration 10 passed; ruff passed; mypy 72 files;
web 15 tests passed (lint/typecheck/build job succeeded).

Staging deployment: **not performed / not verified.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**

## Phase 9.8 — Staging provisioning and live infrastructure verification — merged

Merged to `main` via PR #11. Merge commit: `f098afe700a17fe3d20585d73d3ba5448d85367d` (6 Nov 2026, 09:59 Asia/Jakarta). Feature branch was `cursor/phase-9-8-staging-live-verification`. Implementation commit: `9bb37e948bb2f6b052575f43df11a48d723931bb`. `main` CI on the merge: [run 42153765764](https://github.com/mufea/docuflow-ai/actions/runs/42153765764), success (6 Nov 2026, 10:01 Asia/Jakarta).

Implementation is complete as repository tooling. Staging deployment was **not verified**. Live S3 provider was **NOT EXECUTED**. Production remains **NOT DEPLOYED**.

Base at the time: GitHub `main` @ `e16956aaa09b446cf9f41ef2ecdd453a32e9a73e` (Phase 9.7 already merged via PR #10). Implementation commit: `9bb37e948bb2f6b052575f43df11a48d723931bb`. This phase does not repeat Phases 9.1–9.7.

Scope: staging Blueprint audit (remove unused Redis), staging preflight, PostgreSQL/S3/smoke operator scripts, end-to-end verification procedure. No product features, no paid worker, no Render apply, no production deploy.

### Workstream results

**A. Staging infrastructure audit — implemented, locally tested.** `infra/render.staging.yaml` keeps isolated names and `JOB_BROKER=inline`, and omits Redis because inline jobs do not use it. Production `infra/render.yaml` still lists optional Free Redis. Blueprint was not applied.

**B. Staging environment safety — implemented, locally tested.** `scripts/staging_preflight.py` (opt-in `STAGING_PREFLIGHT=1`) checks fail-fast settings, dedicated PostgreSQL/S3, mock AI, console email, and production resource reuse. Secrets are not printed.

**C. PostgreSQL live verification — procedure ready; staging verified: no.** `scripts/staging_migrate_verify.py` confirms identity, refuses production-looking DSNs, and applies `0003` only with `STAGING_MIGRATE=1`. No hosted staging database was contacted. Existing integration tests still cover disposable upgrade/downgrade.

**D. Live S3 provider — implemented; provider verified: no.** Existing `pytest -m provider` roundtrip still requires dedicated `TEST_S3_*`. It now refuses production-looking bucket names and fetches a presigned URL without logging it. **NOT EXECUTED — missing dedicated test credentials.**

**E. Staging smoke — implemented, locally tested against a loopback server; staging verified: no.** `scripts/staging_smoke.py` retains exit 2 / `NOT EXECUTED` without `STAGING_API_URL`, prints PASS/FAIL/SKIPPED, and optionally exercises auth/upload/job/download/cross-user/delete/frontend when env vars are set.

**F. End-to-end procedure — implemented as documentation.** See `docs/DEPLOYMENT.md`. Queued-job recovery limit remains 100.

**G. Tests — locally tested.** New `tests/test_phase98_staging.py`. CI ruff now includes `scripts`.

**H. Readiness report —** `docs/PHASE_9_8_READINESS_REPORT.md`.

Local verification (this branch):

```
uv run pytest -q -m "not integration"
# 218 passed, 1 skipped, 10 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 10 passed, 219 deselected

uv run ruff check src tests scripts
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 73 source files

uv run python scripts/staging_smoke.py
# NOT EXECUTED, exit 2
uv run python scripts/staging_preflight.py
# NOT EXECUTED, exit 2
uv run python scripts/staging_migrate_verify.py
# NOT EXECUTED, exit 2

git diff --check
# clean
```

The skipped test is the optional live S3 provider roundtrip (no `TEST_S3_*`).
Web lint/typecheck/tests/build: **not run locally**. GitHub Actions for this
feature branch: **CI verified** on `3f1d870` (workflow **CI**,
[run 42148242619](https://github.com/mufea/docuflow-ai/actions/runs/42148242619),
conclusion **success**, 6 Nov 2026, 09:08 Asia/Jakarta): unit 218 passed,
1 skipped, 10 deselected; integration 10 passed; ruff passed; mypy 73 files;
web 15 tests passed (lint/typecheck/build job succeeded).

Staging deployment: **not performed / not verified.**
Live S3 provider verification: **NOT EXECUTED — missing dedicated test credentials.**
PostgreSQL migration `0003` on staging: **not executed / not verified.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production migration: **not performed.**
Production deployment authorized: **NO.**

## Phase 9.9 — Staging environment execution and live verification — on `cursor/phase-9-9-staging-execution-verification`

Base: GitHub `main` @ `f098afe700a17fe3d20585d73d3ba5448d85367d` (Phase 9.8 already merged via PR #11). Implementation commit: `343a035fc92283efb979d376f77ccbda9aa31425`. This phase does not repeat Phases 9.1–9.8.

Scope: record the Phase 9.8 merge accurately, harden staging smoke mutations, add disposable Postgres migrate-verify coverage, and document the owner-operated staging procedure. No product features, no paid worker, no Render apply, no production deploy.

### Workstream results

**A. Phase 9.8 documentation — implemented.** PR #11 is recorded as merged. Staging, provider, and production remain unverified.

**B. Staging safety — implemented, locally tested.** Mutating smoke checks require `STAGING_SMOKE_MUTATIONS=1`. Registration also requires `STAGING_SMOKE_REGISTER=1`. Non-loopback targets require `STAGING_HOST_CONFIRM`. Production API hosts are refused. Uploaded smoke documents are deleted on failure paths.

**C. PostgreSQL verification — locally tested on disposable databases; staging verified: no.** Incorrect confirmation is refused. Pending `0003` without `STAGING_MIGRATE=1` fails closed. Already-current and apply-on-disposable paths were exercised against isolated Postgres.

**D. Live S3 — unchanged optional provider test; provider verified: no.** **NOT EXECUTED — missing dedicated test credentials.**

**E. Staging smoke — locally tested (loopback); staging verified: no.** Loopback `/health`+`/ready` is local verification, not staging verification.

**F. Operator procedure — implemented** in `docs/DEPLOYMENT.md`.

**G. Readiness report —** `docs/PHASE_9_9_READINESS_REPORT.md`.

Local verification (this branch, 6 Nov 2026, 12:02 Asia/Jakarta):

```
uv run pytest tests/test_phase98_staging.py tests/test_phase99_staging.py -q
# 27 passed

uv run pytest -q -m "not integration"
# 228 passed, 1 skipped, 13 deselected

TEST_DATABASE_URL=postgresql+psycopg://docuflow:docuflow@127.0.0.1:5432/docuflow_test \
  uv run pytest -q -m integration
# 13 passed, 229 deselected

uv run ruff check src tests scripts
# All checks passed

uv run mypy src/docuflow
# Success: no issues found in 73 source files

uv run python scripts/staging_smoke.py
# NOT EXECUTED, exit 2
uv run python scripts/staging_preflight.py
# NOT EXECUTED, exit 2
uv run python scripts/staging_migrate_verify.py
# NOT EXECUTED, exit 2

git diff --check
# clean
```

The skipped test is the optional live S3 provider roundtrip (no `TEST_S3_*`).
Web lint/typecheck/tests/build: **not run locally**. GitHub Actions for this
feature branch: recorded after push.

Staging deployment: **not performed / not verified.**
Live S3 provider verification: **NOT EXECUTED — missing dedicated test credentials.**
PostgreSQL migration `0003` on hosted staging: **NOT EXECUTED.**
Production deployment: **NOT DEPLOYED — Awaiting owner approval.**
Production deployment authorized: **NO.**

## Next recommended work

1. Review Phase 9.9. Do not merge or deploy from this agent unless authorized.
2. If staging should exist, apply `infra/render.staging.yaml` in a **dedicated** Render workspace after owner approval. Do not sync it into a workspace that already has `docuflow-api`.
3. Run `STAGING_PREFLIGHT=1 python scripts/staging_preflight.py` before applying secrets to Render.
4. Apply Alembic `0003` only on an approved **staging** database (`scripts/staging_migrate_verify.py`). Do not run it against production.
5. Confirm the actual Render Postgres plan in the dashboard. Free Postgres has no managed backups.
6. Provide dedicated non-production `TEST_S3_*` credentials if live object-storage compatibility should be recorded.
7. After staging exists, set `STAGING_API_URL`, `STAGING_HOST_CONFIRM`, and optionally `STAGING_SMOKE_MUTATIONS=1` with a dedicated test account and PDF.
8. Keep `AI_PROVIDER=mock` and `EMAIL_BACKEND=console` on staging.
9. Queue-based scaling remains a later phase (`JOB_BROKER=rq` + paid worker).
