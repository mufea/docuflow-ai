from __future__ import annotations

import hashlib
import hmac
import secrets


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def digest_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
