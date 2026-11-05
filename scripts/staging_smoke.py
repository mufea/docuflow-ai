#!/usr/bin/env python3
"""Lightweight staging smoke checks. Does not deploy or migrate.

Requires STAGING_API_URL. Exits 2 with NOT EXECUTED when unset so CI stays green.
Never prints secrets, DSNs, or signed URLs.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT_SECONDS = 15
FORBIDDEN_FRAGMENTS = (
    "postgres://",
    "postgresql://",
    "redis://",
    "rediss://",
    "x-amz-signature",
    "aws_secret",
    "password=",
)


def _get(url: str) -> tuple[int, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit("STAGING_API_URL must be an http:// or https:// URL.")
    request = urllib.request.Request(url, method="GET")  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def _assert_no_secrets(payload: str) -> None:
    lowered = payload.lower()
    for fragment in FORBIDDEN_FRAGMENTS:
        if fragment in lowered:
            raise SystemExit("Refusing to continue: response looked like it contained a secret fragment.")


def main() -> int:
    base = os.environ.get("STAGING_API_URL", "").strip().rstrip("/")
    if not base:
        print("NOT EXECUTED: STAGING_API_URL is not set. No staging environment was contacted.")
        return 2
    health_status, health_body = _get(f"{base}/health")
    _assert_no_secrets(health_body)
    ready_status, ready_body = _get(f"{base}/ready")
    _assert_no_secrets(ready_body)
    health = json.loads(health_body)
    ready = json.loads(ready_body)
    print(f"health_http={health_status} health_status={health.get('status')}")
    print(f"ready_http={ready_status} ready_status={ready.get('status')} checks={ready.get('checks')}")
    if health_status != 200 or health.get("status") != "ok":
        return 1
    if ready_status != 200 or ready.get("status") != "ready":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
