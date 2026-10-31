from __future__ import annotations


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
