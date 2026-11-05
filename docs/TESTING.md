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
uv run ruff check src tests
uv run ruff format --check src tests
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

Objects are written only under `docuflow-phase95/<uuid>/` and that key is
deleted afterward. Do not point these variables at the production bucket or
production prefixes.

## Verification layers

Passing local or CI tests is not a production deploy.

| Layer | Evidence |
| --- | --- |
| Local | Commands in this file, run on a laptop or cloud agent |
| CI | GitHub Actions on the commit (`postgres:16` service for `-m integration`) |
| Provider | Dedicated `TEST_S3_*` bucket; **pending** in Phase 9.5 |
| Staging deploy | Separate Render (or other) environment; not done in Phase 9.5 |
| Production deploy | Owner-approved live workspace; **not performed** |
