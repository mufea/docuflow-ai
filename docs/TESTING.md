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
claims, retry recovery, concurrent processing, and Alembic migrations. They
must not use the production database.

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
