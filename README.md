# DocuFlow AI

DocuFlow AI is a PDF processing SaaS for individuals, professionals, and small teams. It provides real server-side PDF tools, background jobs, credit-based usage, and optional AI analysis.

This repository is a monorepo:

- `apps/web` — Next.js 16 application (TypeScript, Tailwind, shadcn/ui)
- `src/docuflow` — FastAPI backend, workers, PDF/conversion/AI engines (imported by `apps/api` and `apps/worker`)
- `packages/shared` — shared TypeScript contracts
- `infra/render.yaml` — Render Blueprint
- `docs/` — architecture, setup, security, operations, and implementation status

The Python package is shared by the API process and the background worker so job execution cannot drift from the HTTP contract.

## What works locally

- Merge, split, extract, reorder, rotate, delete, compress, images↔PDF, text extraction, protect/unlock, thumbnails
- Upload validation by file contents, not extension
- Account registration, session cookies, CSRF, document isolation
- Background jobs with durable PostgreSQL/SQLite status (`queued → processing → completed | failed | cancelled`)
- Integer credit ledger with reservations, settlement, and refunds
- Stripe and Midtrans webhook adapters with signature verification (sandbox; live billing is not activated)
- Mock AI summaries, Q&A, and structured extraction with page citations
- OCR when Tesseract is installed; Word→PDF with a built-in converter (LibreOffice used when present)

## Quick start

Requirements: Python 3.12+, Node 22+, pnpm, and optionally PostgreSQL 16 and Redis 7.

```bash
cp .env.example .env
# Python
uv sync --extra dev
uv run pytest
uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124

# Web
pnpm install
pnpm --filter web dev -- --port 43123
```

The API uses SQLite + filesystem storage + an inline job broker when those values are set in `.env`. That is the supported local path. Production on Render must use PostgreSQL, Redis, S3-compatible storage, and `JOB_BROKER=rq`.

Default local demo admin (development only): create an account in the UI, or see `docs/SETUP.md`.

## Commands

| Task | Command |
| --- | --- |
| Python tests | `uv run pytest` |
| Python lint | `uv run ruff check src tests` |
| Python types | `uv run mypy src/docuflow` |
| API | `uv run uvicorn docuflow.main:app --host 127.0.0.1 --port 43124` |
| Worker | `JOB_BROKER=rq uv run python -m docuflow.worker` |
| Web dev | `pnpm --filter web dev -- --port 43123` |
| Web lint | `pnpm --filter web lint` |
| Web typecheck | `pnpm --filter web typecheck` |
| Web tests | `pnpm --filter web test` |
| Web production build | `pnpm --filter web build` |
| Migrations | `uv run alembic upgrade head` |
| Format | `uv run ruff format src tests` |

## Architecture decisions

- **RQ over Celery.** RQ is Redis-native, easier to operate on Render, and sufficient for document jobs. Celery would add broker/result-backend complexity without a current need for canvas/routing.
- **Durable job state in Postgres.** Redis is a delivery mechanism, not the source of truth.
- **Inline broker in development.** Jobs still persist to the database; Redis is not required to exercise the product locally.
- **S3-compatible storage in production.** Render disks are ephemeral. Local development uses a filesystem adapter under `data/storage`.
- **Mock AI by default.** Core PDF tools never require an AI API key. Live providers are opt-in and are not called in automated tests.

## Deployment

See `docs/DEPLOYMENT.md` and `infra/render.yaml`. This repository is **not claimed as deployed** until a Render deploy is authorized and verified.

## License

MIT
