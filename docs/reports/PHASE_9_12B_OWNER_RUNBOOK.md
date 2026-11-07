# Phase 9.12B — Owner-run production Gates 1–3

Owner authorized Gates 1–3 on 7 Nov 2026, **18:53 Asia/Jakarta**.

This agent does **not** have production test passwords and will **not**
log in to production. Owner runs `scripts/production_smoke.py` locally
and pastes **status labels only**.

## Expected output (do not paste emails, cookies, or URLs)

```
A_invalid_login 401
A_login 200
A_me 200
B_login 200
B_me 200
A_logout 200
A_me_after_logout 401
A_login2 200
A_upload 200
A_upload_id SET
A_upload_spoof 415
A_extract_create 200
A_extract_http 200
A_extract_status completed
A_extract_text present
A_download 302
B_list 200
B_list_has_A_doc no
B_GET 403
B_download 403
B_DELETE 403
unauth_GET 401
A_DELETE 200
A_GET_after 404
```

`A_upload_spoof` may be `400` or `415`. Either is acceptable.

## Commands

From the repo, with `uv` (do **not** export `STAGING_*`):

```bash
unset STAGING_API_URL STAGING_HOST_CONFIRM STAGING_SMOKE_MUTATIONS
export PRODUCTION_SMOKE_MUTATIONS=1
export PRODUCTION_HOST_CONFIRM=docuflowai.site
export PRODUCTION_API_URL=https://docuflowai.site
export PRODUCTION_TEST_A_EMAIL='...'
export PRODUCTION_TEST_A_PASSWORD='...'
export PRODUCTION_TEST_B_EMAIL='...'
export PRODUCTION_TEST_B_PASSWORD='...'
export PRODUCTION_SMOKE_PDF=/path/to/synthetic.pdf
uv run python scripts/production_smoke.py
```

Paste the printed lines only. Do **not** paste passwords.

The script only talks to `https://docuflowai.site`, uses CSRF origin
`https://docuflowai.online`, does not follow download redirects, and
deletes only the document it uploaded.
