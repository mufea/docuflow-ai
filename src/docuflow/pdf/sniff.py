"""Content-based file identification. Extensions and MIME types are never trusted."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from docuflow.exceptions import InvalidFileError, UnsupportedFormatError

PDF_MAGIC = b"%PDF-"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGICS = (b"\xff\xd8\xff",)
GIF_MAGICS = (b"GIF87a", b"GIF89a")
WEBP_RIFF = b"RIFF"
WEBP_WEBP = b"WEBP"
ZIP_MAGIC = b"PK\x03\x04"  # DOCX/XLSX/PPTX are zip packages
DOCX_HINT = b"word/"
XLSX_HINT = b"xl/"


@dataclass(frozen=True, slots=True)
class FileKind:
    kind: str
    mime: str
    extension: str


def _read_prefix(path: Path, size: int = 16) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def sniff_file(path: Path | str) -> FileKind:
    target = Path(path)
    if not target.is_file():
        raise InvalidFileError("File does not exist or is not a regular file.")
    if target.stat().st_size == 0:
        raise InvalidFileError("File is empty.")
    prefix = _read_prefix(target, 16)
    if prefix.startswith(PDF_MAGIC):
        return FileKind("pdf", "application/pdf", ".pdf")
    if prefix.startswith(PNG_MAGIC):
        return FileKind("image", "image/png", ".png")
    if prefix.startswith(JPEG_MAGICS[0]):
        return FileKind("image", "image/jpeg", ".jpg")
    if prefix.startswith(GIF_MAGICS[0]) or prefix.startswith(GIF_MAGICS[1]):
        return FileKind("image", "image/gif", ".gif")
    if prefix.startswith(WEBP_RIFF) and target.stat().st_size >= 12:
        with target.open("rb") as handle:
            header = handle.read(12)
        if header[8:12] == WEBP_WEBP:
            return FileKind("image", "image/webp", ".webp")
    if prefix.startswith(ZIP_MAGIC):
        kind = _sniff_office_zip(target)
        if kind:
            return kind
    raise UnsupportedFormatError("File contents are not a supported document or image type.")


def _sniff_office_zip(path: Path) -> FileKind | None:
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return None
    joined = " ".join(names)
    if "[Content_Types].xml" not in names:
        return None
    if any(name.startswith("word/") for name in names) or "word/" in joined:
        return FileKind("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
    if any(name.startswith("xl/") for name in names):
        return FileKind("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
    return None


def require_pdf(path: Path | str) -> Path:
    target = Path(path)
    kind = sniff_file(target)
    if kind.kind != "pdf":
        raise UnsupportedFormatError("Expected a PDF file based on file contents.")
    return target


def require_image(path: Path | str) -> Path:
    target = Path(path)
    kind = sniff_file(target)
    if kind.kind != "image":
        raise UnsupportedFormatError("Expected an image file based on file contents.")
    return target
