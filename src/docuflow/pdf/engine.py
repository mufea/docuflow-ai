"""Server-side PDF operations. Originals are never overwritten."""

from __future__ import annotations

import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageSequence
from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError, PdfReadError

from docuflow.exceptions import (
    EmptyDocumentError,
    EncryptedPdfError,
    FileTooLargeError,
    InvalidPdfError,
    PageRangeError,
    TooManyPagesError,
    UnsupportedOperationError,
)
from docuflow.pdf.ranges import expand_ranges, parse_page_ranges, validate_pages
from docuflow.pdf.sniff import require_image, require_pdf, sniff_file
from docuflow.pdf.workdir import safe_output_path

logger = logging.getLogger("docuflow.pdf")

ROTATION_VALUES = {0, 90, 180, 270, 360, -90, -180, -270}


@dataclass(frozen=True, slots=True)
class PdfInfo:
    page_count: int
    encrypted: bool
    pdf_version: str | None
    metadata: dict[str, str]
    byte_size: int


@dataclass(slots=True)
class ProcessResult:
    outputs: list[Path]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PdfEngine:
    def __init__(
        self,
        *,
        max_bytes: int = 50 * 1024 * 1024,
        max_pages: int = 400,
        max_images: int = 40,
        max_image_pixels: int = 40_000_000,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_images = max_images
        self.max_image_pixels = max_image_pixels

    def inspect(self, path: Path | str, *, password: str | None = None) -> PdfInfo:
        target = self._require_size(Path(path))
        require_pdf(target)
        reader = self._open_reader(target, password)
        metadata = {}
        raw_meta = reader.metadata
        if raw_meta:
            for key, value in dict(raw_meta).items():
                if value is None:
                    continue
                metadata[str(key).lstrip("/")] = str(value)[:500]
        return PdfInfo(
            page_count=len(reader.pages),
            encrypted=bool(reader.is_encrypted),
            pdf_version=getattr(reader, "pdf_header", None),
            metadata=metadata,
            byte_size=target.stat().st_size,
        )

    def merge(self, inputs: Sequence[Path | str], output: Path | str, *, password: str | None = None) -> ProcessResult:
        if len(inputs) < 2:
            raise UnsupportedOperationError("Merge requires at least two PDF files.")
        writer = PdfWriter()
        total_pages = 0
        sources: list[str] = []
        for item in inputs:
            path = self._require_size(Path(item))
            require_pdf(path)
            reader = self._open_reader(path, password)
            pages = len(reader.pages)
            total_pages += pages
            self._check_pages(total_pages)
            writer.append(reader)
            sources.append(path.name)
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(outputs=[dest], metadata={"page_count": total_pages, "sources": sources})

    def split(
        self,
        source: Path | str,
        ranges: str | list[tuple[int, int]],
        output_dir: Path | str,
        *,
        password: str | None = None,
    ) -> ProcessResult:
        path = self._require_size(Path(source))
        require_pdf(path)
        reader = self._open_reader(path, password)
        page_count = len(reader.pages)
        parsed = parse_page_ranges(ranges, page_count) if isinstance(ranges, str) else ranges
        if isinstance(ranges, list):
            parsed = [self._check_tuple(r, page_count) for r in ranges]
        dest_dir = Path(output_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        for index, (start, end) in enumerate(parsed, start=1):
            writer = PdfWriter()
            for page_no in range(start, end + 1):
                writer.add_page(reader.pages[page_no - 1])
            dest = dest_dir / f"split-{index:03d}-p{start}-{end}.pdf"
            self._write_writer(writer, dest)
            outputs.append(dest)
        return ProcessResult(
            outputs=outputs,
            metadata={"source_pages": page_count, "parts": len(outputs)},
        )

    def extract_pages(
        self,
        source: Path | str,
        pages: list[int] | str,
        output: Path | str,
        *,
        password: str | None = None,
    ) -> ProcessResult:
        path, reader, page_count = self._open_pdf(source, password)
        selected = self._pages_arg(pages, page_count, allow_duplicates=True)
        writer = PdfWriter()
        for page_no in selected:
            writer.add_page(reader.pages[page_no - 1])
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(outputs=[dest], metadata={"pages": selected, "source": path.name})

    def reorder(
        self,
        source: Path | str,
        order: list[int],
        output: Path | str,
        *,
        password: str | None = None,
    ) -> ProcessResult:
        path, reader, page_count = self._open_pdf(source, password)
        validated = validate_pages(order, page_count, allow_duplicates=False)
        if sorted(validated) != list(range(1, page_count + 1)):
            raise PageRangeError(
                "Reorder requires a permutation of every page to avoid unintended data loss. "
                "Use extract to keep a subset."
            )
        writer = PdfWriter()
        for page_no in validated:
            writer.add_page(reader.pages[page_no - 1])
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(outputs=[dest], metadata={"order": validated, "source": path.name})

    def rotate(
        self,
        source: Path | str,
        rotations: dict[int, int],
        output: Path | str,
        *,
        password: str | None = None,
    ) -> ProcessResult:
        path, reader, page_count = self._open_pdf(source, password)
        if not rotations:
            raise PageRangeError("At least one page rotation is required.")
        writer = PdfWriter()
        applied: dict[int, int] = {}
        for index in range(page_count):
            page = reader.pages[index]
            page_no = index + 1
            if page_no in rotations:
                angle = rotations[page_no]
                if angle not in ROTATION_VALUES:
                    raise UnsupportedOperationError("Rotation must be a multiple of 90 degrees.")
                page.rotate(angle)
                applied[page_no] = angle
            writer.add_page(page)
        unknown = set(rotations) - set(range(1, page_count + 1))
        if unknown:
            raise PageRangeError(f"Cannot rotate pages that do not exist: {sorted(unknown)}.")
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(outputs=[dest], metadata={"rotations": applied, "source": path.name})

    def delete_pages(
        self,
        source: Path | str,
        pages: list[int] | str,
        output: Path | str,
        *,
        password: str | None = None,
    ) -> ProcessResult:
        path, reader, page_count = self._open_pdf(source, password)
        to_delete = set(self._pages_arg(pages, page_count, allow_duplicates=False))
        remaining = [n for n in range(1, page_count + 1) if n not in to_delete]
        if not remaining:
            raise UnsupportedOperationError("Cannot delete every page from a PDF.")
        writer = PdfWriter()
        for page_no in remaining:
            writer.add_page(reader.pages[page_no - 1])
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(
            outputs=[dest],
            metadata={"deleted": sorted(to_delete), "remaining": remaining, "source": path.name},
        )

    def compress(
        self,
        source: Path | str,
        output: Path | str,
        *,
        level: str = "medium",
        password: str | None = None,
    ) -> ProcessResult:
        path = self._require_size(Path(source))
        require_pdf(path)
        if level not in {"low", "medium", "high"}:
            raise UnsupportedOperationError("Compression level must be low, medium, or high.")
        dest = Path(output)
        warnings: list[str] = []
        doc = self._open_fitz(path, password)
        try:
            self._check_pages(doc.page_count)
            if level in {"medium", "high"}:
                max_dim = 1600 if level == "medium" else 1024
                quality = 72 if level == "medium" else 52
                self._recompress_images(doc, max_dim=max_dim, quality=quality)
            dest.parent.mkdir(parents=True, exist_ok=True)
            doc.save(
                dest.as_posix(),
                garbage=4,
                deflate=True,
                clean=True,
                use_objstms=1,
            )
        finally:
            doc.close()
        original = path.stat().st_size
        result_size = dest.stat().st_size
        if result_size >= original:
            warnings.append(
                "Compressed file is not smaller than the original. "
                "This is common for already-optimized or text-only PDFs."
            )
        return ProcessResult(
            outputs=[dest],
            warnings=warnings,
            metadata={
                "level": level,
                "original_bytes": original,
                "result_bytes": result_size,
            },
        )

    def images_to_pdf(self, images: Sequence[Path | str], output: Path | str) -> ProcessResult:
        if not images:
            raise UnsupportedOperationError("At least one image is required.")
        if len(images) > self.max_images:
            raise UnsupportedOperationError(f"A maximum of {self.max_images} images can be converted at once.")
        dest = Path(output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        doc = fitz.open()
        used: list[str] = []
        try:
            for item in images:
                path = self._require_size(Path(item))
                require_image(path)
                self._insert_image_pages(doc, path)
                used.append(path.name)
            doc.save(dest.as_posix(), deflate=True, garbage=3)
        finally:
            doc.close()
        return ProcessResult(outputs=[dest], metadata={"images": used, "page_count": self._count_pages(dest)})

    def pdf_to_images(
        self,
        source: Path | str,
        output_dir: Path | str,
        *,
        image_format: str = "png",
        dpi: int = 144,
        pages: list[int] | str | None = None,
        password: str | None = None,
    ) -> ProcessResult:
        fmt = image_format.lower()
        if fmt not in {"png", "jpeg", "jpg"}:
            raise UnsupportedOperationError("Image format must be png or jpeg.")
        if fmt == "jpg":
            fmt = "jpeg"
        if dpi < 36 or dpi > 300:
            raise UnsupportedOperationError("DPI must be between 36 and 300.")
        path = self._require_size(Path(source))
        require_pdf(path)
        dest_dir = Path(output_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        doc = self._open_fitz(path, password)
        outputs: list[Path] = []
        try:
            self._check_pages(doc.page_count)
            selected = (
                self._pages_arg(pages, doc.page_count) if pages is not None else list(range(1, doc.page_count + 1))
            )
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            for page_no in selected:
                page = doc.load_page(page_no - 1)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                suffix = "jpg" if fmt == "jpeg" else "png"
                dest = dest_dir / f"page-{page_no:04d}.{suffix}"
                pix.save(dest.as_posix())
                outputs.append(dest)
        finally:
            doc.close()
        return ProcessResult(
            outputs=outputs,
            metadata={"format": fmt, "dpi": dpi, "pages": selected},
        )

    def extract_text(
        self,
        source: Path | str,
        *,
        pages: list[int] | str | None = None,
        password: str | None = None,
    ) -> ProcessResult:
        path = self._require_size(Path(source))
        require_pdf(path)
        doc = self._open_fitz(path, password)
        page_texts: list[dict[str, Any]] = []
        try:
            self._check_pages(doc.page_count)
            selected = (
                self._pages_arg(pages, doc.page_count) if pages is not None else list(range(1, doc.page_count + 1))
            )
            for page_no in selected:
                page = doc.load_page(page_no - 1)
                text = page.get_text("text") or ""
                page_texts.append({"page": page_no, "text": text})
        finally:
            doc.close()
        combined = "\n\n".join(f"[Page {item['page']}]\n{item['text']}".strip() for item in page_texts).strip()
        warnings = []
        if not any((item["text"] or "").strip() for item in page_texts):
            warnings.append("No extractable text was found. The document may be scanned; OCR is a separate operation.")
        return ProcessResult(
            outputs=[],
            warnings=warnings,
            metadata={"pages": page_texts, "text": combined, "page_count": len(page_texts)},
        )

    def thumbnails(
        self,
        source: Path | str,
        output_dir: Path | str,
        *,
        max_width: int = 240,
        pages: list[int] | str | None = None,
        password: str | None = None,
    ) -> ProcessResult:
        path = self._require_size(Path(source))
        require_pdf(path)
        dest_dir = Path(output_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        doc = self._open_fitz(path, password)
        outputs: list[Path] = []
        try:
            self._check_pages(doc.page_count)
            selected = (
                self._pages_arg(pages, doc.page_count)
                if pages is not None
                else list(range(1, min(doc.page_count, 12) + 1))
            )
            for page_no in selected:
                page = doc.load_page(page_no - 1)
                scale = max_width / max(page.rect.width, 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                dest = dest_dir / f"thumb-{page_no:04d}.png"
                pix.save(dest.as_posix())
                outputs.append(dest)
        finally:
            doc.close()
        return ProcessResult(outputs=outputs, metadata={"max_width": max_width})

    def protect(
        self,
        source: Path | str,
        output: Path | str,
        *,
        user_password: str,
        owner_password: str | None = None,
        password: str | None = None,
    ) -> ProcessResult:
        if not user_password or len(user_password) < 4:
            raise UnsupportedOperationError("Password must be at least 4 characters.")
        path, reader, _page_count = self._open_pdf(source, password)
        writer = PdfWriter()
        writer.append(reader)
        owner = owner_password or user_password
        writer.encrypt(user_password=user_password, owner_password=owner, algorithm="AES-256")
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(
            outputs=[dest],
            metadata={"encrypted": True, "algorithm": "AES-256", "source": path.name},
        )

    def unlock(
        self,
        source: Path | str,
        output: Path | str,
        *,
        password: str,
    ) -> ProcessResult:
        if not password:
            raise EncryptedPdfError("A password is required to remove PDF encryption.")
        path = self._require_size(Path(source))
        require_pdf(path)
        reader = self._open_reader(path, password)
        if not reader.is_encrypted:
            raise UnsupportedOperationError("This PDF is not password-protected.")
        writer = PdfWriter()
        writer.append(reader)
        dest = Path(output)
        self._write_writer(writer, dest)
        return ProcessResult(outputs=[dest], metadata={"encrypted": False, "source": path.name})

    def _open_pdf(self, source: Path | str, password: str | None) -> tuple[Path, PdfReader, int]:
        path = self._require_size(Path(source))
        require_pdf(path)
        reader = self._open_reader(path, password)
        page_count = len(reader.pages)
        if page_count == 0:
            raise EmptyDocumentError("The PDF contains no pages.")
        self._check_pages(page_count)
        return path, reader, page_count

    def _open_reader(self, path: Path, password: str | None) -> PdfReader:
        try:
            reader = PdfReader(str(path), strict=False)
        except PdfReadError as exc:
            raise InvalidPdfError("The file is not a readable PDF.") from exc
        except Exception as exc:
            raise InvalidPdfError("The file could not be parsed as a PDF.") from exc
        if reader.is_encrypted:
            if not password:
                raise EncryptedPdfError("This PDF is encrypted. Supply the document password to continue.")
            try:
                result = reader.decrypt(password)
            except Exception as exc:
                raise EncryptedPdfError("The supplied password was not accepted.") from exc
            if result == 0:
                raise EncryptedPdfError("The supplied password was not accepted.")
        if len(reader.pages) == 0:
            raise EmptyDocumentError("The PDF contains no pages.")
        return reader

    def _open_fitz(self, path: Path, password: str | None) -> fitz.Document:
        try:
            doc = fitz.open(path.as_posix())
        except Exception as exc:
            raise InvalidPdfError("The file is not a readable PDF.") from exc
        if doc.is_encrypted:
            if not password:
                doc.close()
                raise EncryptedPdfError("This PDF is encrypted. Supply the document password to continue.")
            if not doc.authenticate(password):
                doc.close()
                raise EncryptedPdfError("The supplied password was not accepted.")
        if doc.page_count == 0:
            doc.close()
            raise EmptyDocumentError("The PDF contains no pages.")
        return doc

    def _write_writer(self, writer: PdfWriter, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with dest.open("wb") as handle:
                writer.write(handle)
        except FileNotDecryptedError as exc:
            raise EncryptedPdfError("The PDF could not be written because it is still encrypted.") from exc
        if dest.stat().st_size < 5:
            raise InvalidPdfError("Failed to write a valid PDF output.")

    def _require_size(self, path: Path) -> Path:
        if not path.is_file():
            raise InvalidPdfError("File does not exist or is not a regular file.")
        size = path.stat().st_size
        if size == 0:
            raise EmptyDocumentError("File is empty.")
        if size > self.max_bytes:
            raise FileTooLargeError(
                f"File exceeds the maximum size of {self.max_bytes} bytes.",
                details={"max_bytes": self.max_bytes, "size": size},
            )
        return path

    def _check_pages(self, page_count: int) -> None:
        if page_count > self.max_pages:
            raise TooManyPagesError(
                f"Document exceeds the maximum of {self.max_pages} pages.",
                details={"max_pages": self.max_pages, "page_count": page_count},
            )

    def _pages_arg(self, pages: list[int] | str, page_count: int, *, allow_duplicates: bool = True) -> list[int]:
        if isinstance(pages, str):
            return expand_ranges(parse_page_ranges(pages, page_count))
        return validate_pages(pages, page_count, allow_duplicates=allow_duplicates)

    def _check_tuple(self, item: tuple[int, int], page_count: int) -> tuple[int, int]:
        start, end = item
        return validate_pages([start, end], page_count)[0], validate_pages([start, end], page_count)[1]

    def _insert_image_pages(self, doc: fitz.Document, path: Path) -> None:
        kind = sniff_file(path)
        if kind.mime == "image/gif":
            with Image.open(path) as image:
                self._guard_pixels(image)
                for frame in ImageSequence.Iterator(image):
                    rgb = frame.convert("RGB")
                    self._insert_pil_page(doc, rgb)
            return
        with Image.open(path) as image:
            self._guard_pixels(image)
            rgb = image.convert("RGB")
            self._insert_pil_page(doc, rgb)

    def _guard_pixels(self, image: Image.Image) -> None:
        width, height = image.size
        if width * height > self.max_image_pixels:
            raise FileTooLargeError("Image exceeds the maximum pixel count.")

    def _insert_pil_page(self, doc: fitz.Document, image: Image.Image) -> None:
        width, height = image.size
        # A4-ish page that preserves aspect ratio at 72 dpi.
        page_width = 595
        page_height = max(1, int(page_width * height / max(width, 1)))
        page = doc.new_page(width=page_width, height=page_height)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        page.insert_image(page.rect, stream=buffer.getvalue())

    def _recompress_images(self, doc: fitz.Document, *, max_dim: int, quality: int) -> None:
        seen: set[int] = set()
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            for img in page.get_images(full=True):
                xref = int(img[0])
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    pix = fitz.Pixmap(doc, xref)
                except Exception:
                    logger.debug("Skipping unreadable image xref %s during compression", xref)
                    continue
                try:
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    scale = min(1.0, max_dim / max(pix.width, pix.height, 1))
                    if scale < 0.99:
                        pix = fitz.Pixmap(pix, fitz.Matrix(scale, scale))
                    if pix.alpha:
                        pix = fitz.Pixmap(pix, 0)
                    jpg = pix.tobytes("jpeg", jpg_quality=quality)
                    replaced = False
                    if hasattr(page, "replace_image"):
                        try:
                            page.replace_image(xref, stream=jpg)
                            replaced = True
                        except Exception:
                            replaced = False
                    if not replaced:
                        try:
                            doc.update_stream(xref, jpg)
                        except Exception:
                            logger.debug("Skipping image xref %s during compression", xref)
                finally:
                    pix = None

    def _count_pages(self, path: Path) -> int:
        with fitz.open(path.as_posix()) as doc:
            return doc.page_count


def copy_to_work(source: Path, work_dir: Path, name: str) -> Path:
    """Copy a file into the work directory. Never writes back to source."""
    dest = safe_output_path(work_dir, name)
    dest.write_bytes(source.read_bytes())
    return dest
