# Testing

Automated tests never connect to production. They use an isolated SQLite file by
default, or an isolated PostgreSQL database when `TEST_DATABASE_URL` is set.

## Unit tests (SQLite)

Fast path. No Postgres or Redis required.

```bash
uv sync --extra dev
uv run pytest -q -m "not integration"
```

`uv run pytest -q` also works. Integration tests are skipped unless
`TEST_DATABASE_URL` is set.

## PostgreSQL integration tests

These cover credit refund transactions, cleanup leases, storage deletion
claims, retry recovery, concurrent processing, and Alembic migrations
including upgrade from `0002_runtime_reliability` to
`0003_cost_efficient_reliability` with existing rows intact. They must not
use the production database. Downgrade is only exercised against disposable
local databases.

```bash
createdb docuflow_test   # or any empty local database
export TEST_DATABASE_URL=postgresql+psycopg://USER:PASS@127.0.0.1:5432/docuflow_test
uv run pytest -q -m integration
```

Each integration test creates and drops its own database so runs do not share
state. The user in `TEST_DATABASE_URL` needs `CREATEDB`.

CI runs unit tests first, then PostgreSQL integration tests against a
`postgres:16` service. Redis is not started in CI; the default broker is inline.

## Other checks

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src/docuflow
uv run alembic upgrade head   # against a local DATABASE_URL only
pnpm --filter web lint
pnpm --filter web typecheck
pnpm --filter web test
pnpm --filter web build
git diff --check
```

Do not point `DATABASE_URL` or `TEST_DATABASE_URL` at Render production.

## Optional live S3-compatible provider tests

Mocked S3 tests do **not** prove Cloudflare R2 / AWS S3 / MinIO compatibility.
A skipped roundtrip exists as `tests/test_phase95_readiness.py` (`provider`
marker). It runs only when all of the following are set to a **dedicated
test** bucket and credentials — never production:

```bash
export TEST_S3_BUCKET=...
export TEST_S3_ACCESS_KEY_ID=...
export TEST_S3_SECRET_ACCESS_KEY=...
# optional
export TEST_S3_ENDPOINT_URL=...
export TEST_S3_REGION=auto
uv run pytest -q -m provider
```

Objects are written only under `docuflow-test/<uuid>/` and that key is
deleted afterward (including on failure). The test also fetches a
presigned URL without logging it. It fails if `TEST_S3_BUCKET` looks like
the production bucket (`docuflow-documents` or `PRODUCTION_S3_BUCKET`).
Do not point these variables at the production bucket or production
prefixes. CI does not set `TEST_S3_*`, so the test is skipped and must not
fail the suite.

Provider verified: **NOT EXECUTED — missing dedicated test credentials.**

## Staging operator scripts

All three scripts are opt-in. Unset flags/URLs print `NOT EXECUTED` and
exit 2 so CI stays green. They never print secrets, DSNs, or signed URLs.

```bash
python scripts/staging_preflight.py          # needs STAGING_PREFLIGHT=1
python scripts/staging_migrate_verify.py     # needs STAGING_MIGRATE_VERIFY=1
python scripts/staging_smoke.py              # needs STAGING_API_URL
```

`staging_preflight.py` audits `infra/render.staging.yaml` and the current
environment for fail-fast settings, inline broker, dedicated PostgreSQL/S3,
and production resource reuse. It does not create Render services.

`staging_migrate_verify.py` prints database host/name, refuses
production-looking identities, and applies Alembic `0003` only when
`STAGING_MIGRATE=1` and `STAGING_DATABASE_CONFIRM` matches. It never
downgrades.

`staging_smoke.py` always checks `/health` and `/ready`. Extended
authentication, upload, `extract_text`, download, cross-user 403, delete,
and frontend checks stay `SKIPPED` until their dedicated env vars are set.
Skipped checks are never reported as `PASS`.

Without `STAGING_API_URL` the smoke script prints `NOT EXECUTED` and exits
2. It is not a substitute for the full checklist in `docs/DEPLOYMENT.md`.

## Verification layers

Passing local or CI tests is not a production deploy.

| Layer | Evidence |
| --- | --- |
| Local | Commands in this file, run on a laptop or cloud agent |
| CI | GitHub Actions on the commit (`postgres:16` service for `-m integration`) |
| Provider | Dedicated `TEST_S3_*` bucket; **NOT EXECUTED** in Phase 9.8 |
| Staging deploy | Separate Render workspace; template only; **not performed** in Phase 9.8 |
| Production deploy | Owner-approved live workspace; **not performed** |
