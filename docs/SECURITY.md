# Security

## Untrusted documents

PDFs, Office files, and images are treated as hostile input.

- File type is determined from magic bytes / package contents, not the filename.
- Embedded scripts and macros are never executed.
- LibreOffice is launched headless with a stripped environment when present. Otherwise Word→PDF uses the built-in renderer and never executes macros.
- Conversion and OCR run in temporary directories that are deleted afterwards.
- Original uploads are never overwritten.

## Access control

- Session cookie is HttpOnly.
- CSRF token required on POST/PATCH/DELETE.
- Documents and jobs are owned by the authenticated user. Admins are an explicit role.
- Download URLs for S3 are short-lived signed URLs. Filesystem mode streams through the API after an auth check.

## Passwords and tokens

- Argon2 password hashes.
- Session and email tokens stored hashed.
- Password reset and email verification tokens expire.

## Webhooks

Paid entitlements are granted only after signature verification and idempotent persistence of the provider event id. A browser redirect or client-provided `?status=paid` cannot change a plan.

## Logging

Logs must not include document text, passwords, or provider secrets. Request payloads redact `password`, `token`, `secret`, and similar keys.

## Headers

API responses set `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and HSTS in production.

## Authentication rate limits

Login, register, forgot-password, reset-password, and verify-email are limited
per process using the TCP peer from `request.client.host`. Application code
does not trust `X-Forwarded-For`, `X-Real-IP`, or `Forwarded`.

Uvicorn may still rewrite that peer from forwarding headers when the
connector is in `FORWARDED_ALLOW_IPS` (default `127.0.0.1` if unset). Do not
set `FORWARDED_ALLOW_IPS=*`. See `docs/DEPLOYMENT.md` (Uvicorn proxy headers).
This does not enable proxy-aware rate limiting by itself. Production and
staging values are **NOT VERIFIED** here.

## Retention

Uploads and results expire. Cleanup marks rows deleted first, then removes storage objects through the `storage_deletions` outbox. Expired `in_progress` deletion leases are reclaimed; completion and failure require the claiming owner token. Already-missing objects count as success. Failed object deletes never undelete the document row. Account deletion deletes the user's stored files and revokes sessions.
