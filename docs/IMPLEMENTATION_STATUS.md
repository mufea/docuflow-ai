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
- Automated tests use SQLite; production is PostgreSQL. Credit `FOR UPDATE` locking is fully meaningful on Postgres.
- Next.js “Publish to Vercel” is not the production path: the product needs API + worker + Redis + Postgres + object storage on Render.

## Phase 9 — Production safety and data integrity — on `cursor/phase-9-production-safety-3b1a`

Base: GitHub `main` @ `11dbfd0`. `main` was not modified by this work.

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
- GitHub Actions CI runs Python tests/lint/typecheck and web lint/typecheck/tests/build. No secrets. No Postgres/Redis services.

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

Live deployment verification: **not performed**. Render env, DNS, and production data were not accessed.

## Next recommended work

1. Review and merge Phase 9. Do not merge from this agent unless authorized.
2. Push the branch to GitHub `mufea/docuflow-ai` if CI should run there, then authorize a Render deploy separately.
3. Optionally install LibreOffice (Word pagination) or Tesseract (OCR) in a custom image; neither is required.
4. Provide sandbox Stripe/Midtrans keys only if billing should be exercised end-to-end. Live charges stay off.
5. Provide an AI key only if live analysis should replace the mock provider.
