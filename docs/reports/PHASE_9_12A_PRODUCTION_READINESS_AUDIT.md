# Phase 9.12A — Production readiness audit (read-only)

Audit-only. No production login, upload, extract, download mutation,
delete, or cross-user mutation. No application-code changes. No Blueprint
apply. Secrets, cookies, and passwords are not recorded.

Evidence timestamp: **7 Nov 2026, 18:39 Asia/Jakarta (WIB)**.

Repository: `https://github.com/mufea/docuflow-ai`
`origin/main` at audit: `26e6ba02623277c651323b2fdfed4c17df6f5257` (PR #22 merge).

## 1. Current production architecture

| Layer | Production state | Source |
| --- | --- | --- |
| API | `https://docuflowai.site` FastAPI/uvicorn behind Cloudflare | Owner + Gate 0 |
| CMS / web | `https://docuflowai.online` Next.js; rewrites `/health` `/ready`; proxies `/v1` | Owner + Phase 9.11 |
| Broker | `JOB_BROKER=inline` (in-process `InlineBroker` thread pool). `rq_workers=0` | `/ready` |
| Redis | Owner: **absent**. `/ready` `checks.redis=true` is the **inline default** (no ping) | Owner 18:05 |
| Worker service | Owner: **absent** | Owner 18:05 |
| Postgres | `docuflow-db` Basic, backups yes, YAML `0.1c-256mb` | Phase 9.11 owner |
| Object storage | `STORAGE_BACKEND=s3`, bucket `docuflowai-documents` | Phase 9.11 owner |
| Cleanup | Owner: cron **running** | Owner 18:14 |
| AI / email | mock / console (accepted) | Phase 9.11 |
| Auth | HttpOnly `df_session` + readable `df_csrf`; `COOKIE_SECURE` in production | `src/docuflow/api/routes/auth.py` |
| Jobs | Create → `queued` → `InlineBroker.enqueue` → `JobRunner.process` | `jobs.py`, `broker.py` |
| Storage keys | `{user_id}/{uuid}{ext}` — **not** in `DocumentOut` | `documents.py` `_store` |

**Classification so far:** DEPLOYED + HEALTH VERIFIED (public). **Not** FUNCTIONALLY VERIFIED, SECURITY VERIFIED, or PRODUCTION VERIFIED.

## 2. Endpoint inventory (from code)

Prefixes from routers in `src/docuflow/api/routes/*.py`, mounted in `src/docuflow/main.py`.

### 2.1 In scope for Phase 9.12 functional tests

| ID | Feature | Method | Path | Auth | CSRF | Mutates | Expected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-H1 | Health | GET | `/health` | no | no | no | 200 `service=docuflow-api` |
| P-H2 | Ready | GET | `/ready` | no | no | no | 200 `broker=inline` |
| P-W1 | CMS | GET | `https://docuflowai.online/` | no | no | no | 200 HTML |
| A1 | Login valid | POST | `/v1/auth/login` | no | no | session | 200; Set-Cookie `df_session`, `df_csrf` |
| A2 | Login invalid | POST | `/v1/auth/login` | no | no | no (failed) | 401 `unauthenticated` `"Invalid email or password."` |
| A3 | Me | GET | `/v1/auth/me` | session | no | no | 200 user; no session → 401 |
| A4 | Logout | POST | `/v1/auth/logout` | cookie optional | no | session revoke | 200 `{ok:true}`; later `/me` 401 |
| U1 | List | GET | `/v1/documents` | session | no | no | 200 array; **own rows only** |
| U2 | Upload PDF | POST | `/v1/documents` | session | **yes** | **yes** | 200 `DocumentOut` |
| U3 | MIME reject | POST | `/v1/documents` | session | **yes** | no (reject) | 400/415 `unsupported_format` / `invalid_file` |
| U4 | Get | GET | `/v1/documents/{id}` | session | no | no | owner 200; other 403; missing 404 |
| X1 | Create extract | POST | `/v1/jobs` | session | **yes** | **yes** | 200 `operation=extract_text` then poll |
| X2 | Get job | GET | `/v1/jobs/{id}` | session | no | enqueue if queued | owner 200; other 403 |
| D1 | Download | GET | `/v1/documents/{id}/download` | session | no | no* | owner **302** (S3 signed URL, default 600s); other 403 |
| DEL1 | Delete | DELETE | `/v1/documents/{id}` | session | **yes** | **yes** | owner 200 `{ok:true}`; then GET 404; other 403 |

\*Download does not mutate the document; it issues a time-limited signed URL.

CSRF (mutating methods): header `X-CSRF-Token` must match session CSRF; `Origin` must be allowed (`https://docuflowai.online` in production). See `require_csrf` in `src/docuflow/api/deps.py`.

Job create body (`JobCreateRequest`):

```json
{"operation":"extract_text","document_ids":["<id>"],"params":{}}
```

Extracted text is in `result_payload.text` (and `pages`), not a new document. `extract_text` is in `SYNC_SAFE_OPERATIONS`. Cost: 1 credit (`DEFAULT_OPERATION_COSTS`).

Upload: content sniffed (`sniff_file`); client MIME/extension **not** trusted. Default `MAX_UPLOAD_BYTES` = 50 MiB → HTTP **413** `file_too_large`. Empty file → 400 `invalid_file`.

### 2.2 Out of scope / do not call

| Path | Why |
| --- | --- |
| `POST /v1/auth/register` | Creates production users |
| `DELETE /v1/auth/me` | Deletes the account and all its documents |
| `PATCH /v1/auth/me` | Profile mutation; CSRF-only check can wait |
| Password reset / verify-email | Console email; no inbox |
| `/v1/admin/*` | Admin-only |
| `/v1/billing/checkout`, `/v1/webhooks/*` | Payments |
| merge/split/OCR/AI jobs | Extra cost/load; keep `extract_text` + mock AI |
| 50 MiB size-limit upload | Bandwidth; skip unless owner wants it |

## 3. Existing test coverage

### 3.1 Local (pytest) — authorization/upload

| Test | File | What it proves |
| --- | --- | --- |
| Cross-user GET/download/job 403 | `tests/test_jobs_and_security.py` `test_cross_user_document_access_denied` | IDOR on document + extract job |
| Cross-user download 403, no signed URL leak | `tests/test_phase95_readiness.py` `test_cross_user_cannot_download_another_users_file` | Download isolation |
| Cross-user DELETE 403 | `tests/test_phase91_cleanup.py` `test_user_cannot_purge_another_users_document` | Delete isolation |
| Cross-user job GET 403 | `tests/test_phase9_integrity.py` `test_cross_user_job_access_denied` | Job IDOR |
| Spoofed PDF rejected | `tests/test_jobs_and_security.py` `test_upload_rejects_spoofed_pdf` | Content sniff |
| Login/logout/401 | `tests/test_auth_api.py` | Session cookies |
| Invalid login generic | `tests/test_auth_api.py` `test_invalid_login_is_generic` | No password echo |
| CSRF required | `tests/test_auth_api.py` | 403 without token / bad origin |
| Staging smoke refuses prod hosts | `tests/test_phase99_staging.py` | `docuflowai.site` / `.online` refused |

Local tests are **not** production evidence.

### 3.2 Staging live (Phase 9.10D) — not production

Auth, upload, `extract_text`, download 302, delete, cross-user 403, unauth 401. Hosts were `docuflow-staging-*`.

### 3.3 Production (Phase 9.11 + Gate 0 this audit)

| Check | Result | When |
| --- | --- | --- |
| GET `/health` | PASS 200 | 18:39 WIB (repeat of 18:00) |
| GET `/ready` | PASS `broker=inline` db/storage true | 18:39 |
| GET CMS `/` | PASS 200 | 18:39 |
| GET `/v1/auth/me` no cookie | PASS 401 | 18:39 |
| Login / upload / extract / download / delete / isolation | **NOT TESTED** | — |

`scripts/staging_smoke.py` **must not** be aimed at production (`is_production_public_host`). There is **no** production smoke script. Reuse the 9.10D owner-run `httpx` pattern with production origins after approval.

## 4. Missing production verification

| Area | Production status |
| --- | --- |
| Authentication (valid/invalid/logout) | NOT TESTED |
| Upload (PDF + MIME reject) | NOT TESTED |
| Extraction (`extract_text`, inline complete, text present) | NOT TESTED |
| Download (owner 302; do not log Location) | NOT TESTED |
| Delete (owner 200 then 404) | NOT TESTED |
| Cross-user isolation (B GET/list/download/DELETE 403) | NOT TESTED |
| Signed URL expiry live | NOT TESTED |
| Direct S3 object guess | NOT TESTED (keys not in API JSON) |
| Hosted Alembic head on `docuflow-db` | NOT TESTED |
| File-size 413 with a 50 MiB body | SKIP recommended |

**Informational (code, not a blocker):** `get_owned` returns **404** if missing/deleted and **403** if it exists but is not owned — existence oracle, no content leak (`src/docuflow/services/documents.py`).

## 5. Production test prerequisites

1. Two **owner-created** production users (A and B). No customer data. **Not** staging accounts. **Do not paste passwords into chat.**
2. One small **synthetic** PDF (harmless text). Not a customer file.
3. Mutations only against those accounts / that file.
4. CSRF: send `X-CSRF-Token` from `df_csrf` and `Origin: https://docuflowai.online`.
5. HTTP client: `follow_redirects=false` on download; **never print** `Location` (signed URL).
6. After tests: DELETE only the test document as user A (Gate 3).
7. Do **not** set `STAGING_*` to production URLs.
8. Do **not** `POST /v1/auth/register` or `DELETE /v1/auth/me`.
9. Keep `AI_PROVIDER=mock`. One `extract_text` job (1 credit).
10. Accept Free-web spin-down may delay inline jobs; retry GET job, do not re-upload blindly.

## 6. Safety risks

| Risk | Mitigation |
| --- | --- |
| Staging smoke against prod | Script refuses `docuflowai.site` / `.online` |
| Password in chat | Owner runs locally; sanitize HTTP codes only |
| Signed URL in logs | `follow_redirects=false`; record status only |
| Customer data | Dedicated test users + synthetic PDF |
| Account wipe | Never `DELETE /v1/auth/me` |
| Extra users | Never register |
| CSRF fail | Origin must be CMS URL |
| Rate limit | Login 10/min/IP; upload 30/min/user (`MemoryRateLimiter`) |
| Inline + spin-down | Short extract_text only |
| Broad delete | Delete only the ID created in this test |
| Blueprint Redis | Do not sync `infra/render.yaml` |

**Gate 0 (this phase): allowed and done.** Gates 1–3: **BLOCKED** until owner approval.

## 7. Recommended sequence (after approval)

Owner-run on a laptop (same model as Phase 9.10D). Print **status codes only**.

1. **Gate 1** — A login 200; invalid password 401; `/me` 200; B login 200; A logout then `/me` 401; A login again.
2. **Gate 2** — A upload synthetic PDF 200; capture `doc_id`. Upload non-PDF 400/415. A `extract_text` 200 → poll GET job until `completed`; `result_payload.text` present. A download **302**.
3. **Isolation (before delete)** — B `GET /v1/documents` does not contain `doc_id`. B GET/download/DELETE that id → **403**. Unauth GET → **401**.
4. **Gate 3** — A DELETE `doc_id` 200. A GET → **404**. Stop.

Do not follow the download redirect. Do not dump cookies or JSON emails if avoidable (user id + HTTP codes are enough).

## 8. Exact owner approvals required

Reply with this text if you authorize **Gates 1–3** (auth + one upload + extract + download + isolation + delete of **that** test document only):

```
Authorize Gates 1-3 on production.
Two dedicated test accounts exist (no customer data).
Synthetic PDF only.
Delete only those test documents.
I will run the tests locally and paste HTTP status codes only.
```

Optional narrower replies:

- `Authorize Gate 1 only` — login/logout/invalid password only.
- `Authorize Gates 1-2` — plus upload/extract/download; **no** delete.

Owner approved Gates 1–3 at 18:53 Asia/Jakarta. Execution is **owner-run**
(`docs/reports/PHASE_9_12B_OWNER_RUNBOOK.md`). This agent does not log in.

Do **not** send passwords, session cookies, signed URLs, or DSNs.

## 9. Gate 0 evidence (this audit)

```
GET https://docuflowai.site/health  → 200 {"status":"ok","service":"docuflow-api"}
GET https://docuflowai.site/ready   → 200 broker=inline rq_workers=0 checks all true
GET https://docuflowai.online/      → 200
GET https://docuflowai.site/v1/auth/me (no cookie) → 401 unauthenticated
```

## 10. Status

| Flag | Value |
| --- | --- |
| STAGING VERIFIED | YES |
| PRODUCTION AUTHORIZED | YES (inline) |
| PRODUCTION DEPLOYED | YES |
| HEALTH VERIFIED | YES (public) |
| FUNCTIONALLY VERIFIED | NO |
| SECURITY VERIFIED | NO |
| PRODUCTION VERIFIED | NO |

Application code changed this phase: **NO**.
