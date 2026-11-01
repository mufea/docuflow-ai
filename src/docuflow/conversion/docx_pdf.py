from __future__ import annotations

import html
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

import fitz
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from docuflow.exceptions import InvalidFileError

logger = logging.getLogger("docuflow.conversion")

BUILTIN_DOCX_TO_PDF_LIMITS = [
    "Built-in converter: layout, fonts, headers, and floating objects are approximate.",
    "LibreOffice is used when installed for closer Word pagination.",
    "Macros are never executed. Embedded scripts are not processed.",
]

_HTML_STYLE = """
body { font-family: sans-serif; font-size: 11pt; color: #111; }
h1 { font-size: 20pt; margin: 0 0 12pt 0; }
h2 { font-size: 16pt; margin: 14pt 0 8pt 0; }
h3 { font-size: 13pt; margin: 12pt 0 6pt 0; }
p { margin: 0 0 8pt 0; line-height: 1.35; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
td, th { border: 1px solid #444; padding: 4pt 6pt; vertical-align: top; }
img { max-width: 100%; }
.center { text-align: center; }
.right { text-align: right; }
"""


def find_libreoffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def docx_to_pdf_available() -> bool:
    return True


def convert_docx_with_builtin(source: Path, output: Path, *, max_pages: int = 400) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="docuflow-docx-") as raw_media:
        media_dir = Path(raw_media)
        markup = _docx_to_html(source, media_dir)
        _html_to_pdf(markup, output, max_pages=max_pages)
    return output


def _iter_blocks(document: Any) -> Any:
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _docx_to_html(source: Path, media_dir: Path) -> str:
    document = DocxDocument(str(source))
    parts = [f"<html><head><style>{_HTML_STYLE}</style></head><body>"]
    wrote = False
    for block in _iter_blocks(document):
        if isinstance(block, Paragraph):
            chunk = _paragraph_html(block, document, media_dir)
        else:
            chunk = _table_html(block, document, media_dir)
        if chunk:
            parts.append(chunk)
            wrote = True
    if not wrote:
        parts.append("<p></p>")
    parts.append("</body></html>")
    return "".join(parts)


def _paragraph_html(paragraph: Paragraph, document: Any, media_dir: Path) -> str:
    pieces: list[str] = []
    if _has_page_break(paragraph):
        pieces.append('<div style="page-break-before:always"></div>')
    inner: list[str] = []
    for run in paragraph.runs:
        for image in _save_images(run._element, document, media_dir):
            inner.append(_img_tag(image))
        text = run.text or ""
        if text:
            inner.append(_styled_run(run, text))
    if not inner:
        for image in _save_images(paragraph._element, document, media_dir):
            inner.append(_img_tag(image))
    if not inner:
        return "".join(pieces)
    if _is_list_item(paragraph):
        inner.insert(0, "• ")
    tag = _heading_tag(paragraph)
    css_class = _align_class(paragraph)
    class_attr = f' class="{css_class}"' if css_class else ""
    pieces.append(f"<{tag}{class_attr}>{''.join(inner)}</{tag}>")
    return "".join(pieces)


def _table_html(table: Table, document: Any, media_dir: Path) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            cell_parts: list[str] = []
            for paragraph in cell.paragraphs:
                cell_parts.append(_paragraph_html(paragraph, document, media_dir) or "<p></p>")
            cells.append(f"<td>{''.join(cell_parts)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    if not rows:
        return ""
    return f"<table>{''.join(rows)}</table>"


def _styled_run(run: object, text: str) -> str:
    escaped = html.escape(text).replace("\n", "<br/>")
    bold = bool(getattr(run, "bold", False))
    italic = bool(getattr(run, "italic", False))
    underline = bool(getattr(run, "underline", False))
    if bold:
        escaped = f"<strong>{escaped}</strong>"
    if italic:
        escaped = f"<em>{escaped}</em>"
    if underline:
        escaped = f"<u>{escaped}</u>"
    return escaped


def _heading_tag(paragraph: Paragraph) -> str:
    name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    if name in {"title", "heading 1"} or name.startswith("heading 1"):
        return "h1"
    if name.startswith("heading 2"):
        return "h2"
    if name.startswith("heading 3"):
        return "h3"
    return "p"


def _align_class(paragraph: Paragraph) -> str:
    alignment = paragraph.alignment
    if alignment == WD_ALIGN_PARAGRAPH.CENTER:
        return "center"
    if alignment == WD_ALIGN_PARAGRAPH.RIGHT:
        return "right"
    return ""


def _is_list_item(paragraph: Paragraph) -> bool:
    ppr = paragraph._p.pPr
    if ppr is not None and ppr.numPr is not None:
        return True
    name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
    return "list" in name


def _has_page_break(paragraph: Paragraph) -> bool:
    if paragraph.paragraph_format.page_break_before:
        return True
    breaks = paragraph._element.xpath('.//*[local-name()="br"]')
    for node in breaks:
        kind = node.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type")
        if kind == "page":
            return True
    return False


def _save_images(element: Any, document: Any, media_dir: Path) -> list[Path]:
    embeds = element.xpath(".//*[local-name()='blip']/@*[local-name()='embed']")
    saved: list[Path] = []
    for index, embed in enumerate(embeds):
        part = document.part.related_parts.get(str(embed))
        if part is None or not getattr(part, "blob", None):
            continue
        suffix = Path(str(getattr(part, "partname", "image.png"))).suffix or ".png"
        dest = media_dir / f"{embed}-{index}{suffix}"
        dest.write_bytes(part.blob)
        saved.append(dest)
    return saved


def _img_tag(path: Path) -> str:
    return f'<img src="{html.escape(path.resolve().as_uri())}" />'


def _html_to_pdf(markup: str, output: Path, *, max_pages: int) -> None:
    story = fitz.Story(markup)
    mediabox = fitz.paper_rect("a4")
    where = fitz.Rect(48, 48, mediabox.width - 48, mediabox.height - 48)
    partial = output.with_name(f"{output.name}.partial")
    if partial.exists():
        partial.unlink()
    writer = fitz.DocumentWriter(partial.as_posix())
    more = True
    pages = 0
    try:
        while more:
            device = writer.begin_page(mediabox)
            more, _filled = story.place(where)
            story.draw(device)
            writer.end_page()
            pages += 1
            if pages > max_pages:
                raise InvalidFileError("DOCX to PDF exceeded the page limit.")
    except Exception:
        writer.close()
        if partial.exists():
            partial.unlink()
        raise
    writer.close()
    if pages == 0 or not partial.is_file() or partial.stat().st_size == 0:
        if partial.exists():
            partial.unlink()
        raise InvalidFileError("DOCX to PDF produced an empty file.")
    if partial.read_bytes()[:5] != b"%PDF-":
        partial.unlink()
        raise InvalidFileError("DOCX to PDF produced an invalid PDF.")
    partial.replace(output)
