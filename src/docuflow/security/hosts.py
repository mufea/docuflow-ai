from __future__ import annotations

from urllib.parse import urlparse


def hostname_from_header(host_header: str) -> str:
    value = host_header.strip().lower()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    return value.split(":", 1)[0]


def host_is_allowed(host_header: str, allowed_hosts: list[str]) -> bool:
    hostname = hostname_from_header(host_header)
    if not hostname:
        return False
    for pattern in allowed_hosts:
        item = pattern.strip().lower()
        if not item:
            continue
        if item == "*":
            return True
        if hostname == item:
            return True
        if item.startswith(".") and (hostname.endswith(item) or hostname == item[1:]):
            return True
        if item.startswith("*.") and (hostname.endswith(item[1:]) or hostname == item[2:]):
            return True
    return False


def normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def origin_variants(url: str) -> list[str]:
    raw = normalize_origin(url)
    if not raw:
        return []
    parsed = urlparse(raw)
    host = parsed.hostname
    if not parsed.scheme or not host:
        return [raw]
    port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    variants = [f"{parsed.scheme}://{host}{port}"]
    if host.startswith("www."):
        variants.append(f"{parsed.scheme}://{host[4:]}{port}")
    else:
        variants.append(f"{parsed.scheme}://www.{host}{port}")
    return variants


def origin_is_allowed(
    origin: str,
    allowed_origins: list[str],
    *,
    allowed_hosts: list[str] | None = None,
    web_host: str = "",
    require_https: bool = False,
) -> bool:
    raw = origin.strip()
    if not raw:
        return True
    if raw.lower() == "null":
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    hostname = parsed.hostname.lower()
    if require_https and parsed.scheme != "https" and hostname not in {"127.0.0.1", "localhost"}:
        return False
    comparable = {normalize_origin(item) for item in allowed_origins if item.strip()}
    for variant in origin_variants(raw):
        if variant in comparable:
            return True
    if normalize_origin(raw) in comparable:
        return True
    web = hostname_from_header(web_host)
    if web and web == hostname:
        return True
    if allowed_hosts and host_is_allowed(hostname, allowed_hosts):
        return True
    return False
