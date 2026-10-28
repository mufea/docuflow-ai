"""Page-number and range parsing. Public APIs are 1-indexed inclusive."""

from __future__ import annotations

import re

from docuflow.exceptions import PageRangeError

_TOKEN = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+)\s*)?$")


def parse_page_ranges(spec: str, page_count: int) -> list[tuple[int, int]]:
    if not spec or not spec.strip():
        raise PageRangeError("Page range is empty.")
    ranges: list[tuple[int, int]] = []
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        match = _TOKEN.match(token)
        if not match:
            raise PageRangeError(f"Invalid page range token: {token!r}.")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        ranges.append(_normalize_range(start, end, page_count))
    if not ranges:
        raise PageRangeError("Page range is empty.")
    return ranges


def _normalize_range(start: int, end: int, page_count: int) -> tuple[int, int]:
    if start < 1 or end < 1:
        raise PageRangeError("Page numbers are 1-indexed and must be >= 1.")
    if start > end:
        raise PageRangeError("Range start must be less than or equal to range end.")
    if start > page_count or end > page_count:
        raise PageRangeError(f"Page range {start}-{end} is outside the document ({page_count} pages).")
    return start, end


def validate_pages(pages: list[int], page_count: int, *, allow_duplicates: bool = True) -> list[int]:
    if not pages:
        raise PageRangeError("At least one page number is required.")
    seen: set[int] = set()
    ordered: list[int] = []
    for page in pages:
        if not isinstance(page, int) or isinstance(page, bool):
            raise PageRangeError("Page numbers must be integers.")
        if page < 1 or page > page_count:
            raise PageRangeError(f"Page {page} is outside the document ({page_count} pages).")
        if not allow_duplicates and page in seen:
            raise PageRangeError(f"Page {page} is duplicated.")
        seen.add(page)
        ordered.append(page)
    return ordered


def expand_ranges(ranges: list[tuple[int, int]]) -> list[int]:
    pages: list[int] = []
    for start, end in ranges:
        pages.extend(range(start, end + 1))
    return pages
