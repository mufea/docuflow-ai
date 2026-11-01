# Local setup

## Tools used in this environment

- Python 3.12
- Node.js 22 / pnpm 10
- uv 0.13
- PostgreSQL 16 and Redis 7 (optional; installed for realism)
- Tesseract OCR (optional)
- LibreOffice is optional. Word→PDF uses a built-in converter when `soffice` is missing. Install LibreOffice for closer Word pagination.

## 1. Environment

```bash
cp .env.example .env
```

For a zero-infrastructure local run:

```
DATABASE_URL=sqlite+pysqlite:///./data/docuflow.db
STORAGE_BACKEND=filesystem
STORAGE_LOCAL_PATH=./data/storage
JOB_BROKER=inline
AI_PROVIDER=mock
COOKIE_SECURE=false
```

## 2. Install

```bash
uv sync --extra dev
pnpm install
```

## 3. Database

SQLite: the API creates tables on startup.

PostgreSQL:

```bash
createdb docuflow
uv run alembic upgrade head
```

Set `DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/docuflow`.

## 4. Run

Terminal A:

```bash
uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124
```

Terminal B:

```bash
pnpm --filter web dev -- --port 43123
```

Open `http://127.0.0.1:43123`.

## 5. Tests

```bash
uv run pytest
pnpm --filter web test
pnpm --filter web lint
uv run ruff check src tests
uv run mypy src/docuflow
```

## Secrets

Never put API keys in the Next.js bundle. `NEXT_PUBLIC_*` is limited to the public API prefix. Stripe, Midtrans, S3, SMTP, and AI keys stay on the API.
