# Architecture

## Services

```
Browser → Next.js (apps/web)
            │  /v1/* reverse proxy
            ▼
          FastAPI (src/docuflow)
            │ enqueue job_id
            ▼
          RQ worker  (or inline thread pool in development)
            │
     ┌──────┼──────────┐
     ▼      ▼          ▼
  Postgres Redis   Object storage
```

## Python package layout

`src/docuflow` is the application kernel:

- `pdf/` — deterministic PDF engine
- `conversion/` — DOCX/XLSX adapters
- `ocr/` — Tesseract OCR
- `ai/` — provider interface, chunking, retrieval, citations
- `jobs/` — runner, brokers, retention
- `billing/` — integer ledger and plans
- `payments/` — Stripe and Midtrans adapters
- `api/` — HTTP surface
- `worker.py` — RQ process entrypoint

`apps/api` and `apps/worker` are Render/process entrypoints around the same package.

## Job lifecycle

1. Authenticated API request validates files, plan limits, and CSRF.
2. Credits are reserved in a database transaction.
3. A `jobs` row is written with status `queued`.
4. The broker delivers only the `job_id`.
5. The worker loads the job from Postgres, downloads objects to a temp directory, processes, uploads results, settles or refunds credits, and writes `completed` or `failed`.
6. Temp directories are deleted on success and failure.

Cancellation is supported in `queued`. Jobs already `processing` finish or time out; abandoned processing rows are marked failed by retention cleanup.

## Auth

- Passwords hashed with Argon2.
- Opaque session tokens stored as SHA-256 hashes.
- HttpOnly session cookie + readable CSRF cookie.
- Mutating requests require `X-CSRF-Token` and an allowed Origin.
- Authorization always uses the server-side session, never a client-supplied user id.

## Credits

Balances are integers. `available = balance - reserved`. Ledger idempotency keys prevent double charges on retries. Failed jobs refund reservations. Negative balances are rejected unless `ALLOW_NEGATIVE_CREDITS` is explicitly true (default false).

## AI

Text is extracted locally first. Chunks keep page metadata. The mock provider is deterministic and only cites pages that exist in the extracted text. Document content is wrapped as untrusted data. Live OpenAI-compatible calls require `AI_PROVIDER=openai_compatible` and `AI_API_KEY` on the server.
