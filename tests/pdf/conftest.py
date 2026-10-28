from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from PIL import Image
from pypdf import PdfWriter

from docuflow.pdf.engine import PdfEngine


@pytest.fixture
def engine() -> PdfEngine:
    return PdfEngine(max_bytes=10 * 1024 * 1024, max_pages=50, max_images=10)


def write_text_pdf(path: Path, pages: list[str], *, password: str | None = None) -> Path:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), text, fontsize=16)
        page.insert_text((72, 120), "DocuFlow fixture — non-sensitive synthetic document.", fontsize=10)
    if password:
        doc.save(
            path.as_posix(),
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw=password,
            owner_pw=password,
        )
    else:
        doc.save(path.as_posix())
    doc.close()
    return path


def write_image_pdf(path: Path, color: tuple[int, int, int] = (30, 90, 160), size: int = 900) -> Path:
    image = Image.new("RGB", (size, size), color)
    image.putpixel((10, 10), (255, 0, 0))
    buf_path = path.with_suffix(".png")
    image.save(buf_path)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=buf_path.as_posix())
    doc.save(path.as_posix())
    doc.close()
    buf_path.unlink(missing_ok=True)
    return path


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    return write_text_pdf(tmp_path / "sample.pdf", [f"Page {n} unique marker ALPHA-{n}" for n in range(1, 5)])


@pytest.fixture
def second_pdf(tmp_path: Path) -> Path:
    return write_text_pdf(tmp_path / "second.pdf", ["Second document page 1", "Second document page 2"])


@pytest.fixture
def encrypted_pdf(tmp_path: Path) -> Path:
    return write_text_pdf(
        tmp_path / "secret.pdf", ["Confidential page 1", "Confidential page 2"], password="correct-horse"
    )


@pytest.fixture
def image_pdf(tmp_path: Path) -> Path:
    return write_image_pdf(tmp_path / "photo.pdf")


@pytest.fixture
def jpeg_image(tmp_path: Path) -> Path:
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (320, 240), (12, 80, 40)).save(path, format="JPEG", quality=90)
    return path


@pytest.fixture
def png_image(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    Image.new("RGB", (200, 300), (200, 40, 40)).save(path, format="PNG")
    return path


@pytest.fixture
def empty_pdf_header(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")
    return path


@pytest.fixture
def not_a_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "notes.pdf"
    path.write_text("this is not a pdf")
    return path


@pytest.fixture
def blank_writer_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as handle:
        writer.write(handle)
    return path
