from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    page: int
    text: str
    start_char: int
    end_char: int


def chunk_pages(pages: list[dict[str, object]], *, max_chars: int = 1200, overlap: int = 120) -> list[Chunk]:
    chunks: list[Chunk] = []
    index = 0
    for item in pages:
        page_no = int(str(item["page"]))
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            piece = text[start:end].strip()
            if piece:
                chunks.append(
                    Chunk(
                        chunk_id=f"p{page_no}-c{index}",
                        page=page_no,
                        text=piece,
                        start_char=start,
                        end_char=end,
                    )
                )
                index += 1
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks


def retrieve(chunks: list[Chunk], query: str, *, limit: int = 6) -> list[Chunk]:
    terms = [term.lower() for term in query.split() if len(term) > 2]
    if not terms:
        return chunks[:limit]
    scored: list[tuple[int, Chunk]] = []
    for chunk in chunks:
        hay = chunk.text.lower()
        score = sum(hay.count(term) for term in terms)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for _score, chunk in scored[:limit]]
    if selected:
        return selected
    return chunks[:limit]
