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

## Retention

Uploads and results expire. `cleanup_expired_files` deletes storage objects and marks rows deleted. Account deletion deletes the user's stored files and revokes sessions.
