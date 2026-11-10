from __future__ import annotations

from starlette.requests import Request


def rate_limit_client_id(request: Request) -> str:
    """Process-local rate-limit identity from the direct TCP peer.

    Does not read ``X-Forwarded-For``, ``X-Real-IP``, or ``Forwarded``.
    Those headers are attacker-controlled unless a trusted proxy is
    configured, and this app has no trusted-proxy list. Behind a reverse
    proxy, many clients may share one peer address.
    """
    client = request.client
    if client is None or not client.host:
        return "unknown"
    return client.host
