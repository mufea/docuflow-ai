from __future__ import annotations

from pathlib import Path

import fitz
from pypdf import PdfReader

from docuflow.exceptions import (
    EmptyDocumentError,
    EncryptedPdfError,
    FileTooLargeError,
    InvalidFileError,
    PageRangeError,
    TooManyPagesError,
    UnsupportedFormatError,
    UnsupportedOperationError,
)
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.sniff import sniff_file
from docuflow.pdf.workdir import work_directory
from tests.pdf.conftest import write_text_pdf


def _text(path: Path, password: str | None = None) -> str:
    doc = fitz.open(path.as_posix())
    if password:
        assert doc.authenticate(password)
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def test_sniff_rejects_extension_only(not_a_pdf: Path) -> None:
    try:
        sniff_file(not_a_pdf)
        raise AssertionError("expected sniff failure")
    except UnsupportedFormatError:
        pass


def test_merge_concatenates_pages(engine: PdfEngine, sample_pdf: Path, second_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "merged.pdf"
    result = engine.merge([sample_pdf, second_pdf], dest)
    assert dest.is_file()
    assert dest.stat().st_size > 0
    info = engine.inspect(dest)
    assert info.page_count == 6
    text = _text(dest)
    assert "ALPHA-1" in text
    assert "Second document page 2" in text
    assert result.metadata["page_count"] == 6
    assert sample_pdf.read_bytes() != dest.read_bytes()


def test_split_by_ranges(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "parts"
    result = engine.split(sample_pdf, "1-2,4", out)
    assert len(result.outputs) == 2
    assert engine.inspect(result.outputs[0]).page_count == 2
    assert engine.inspect(result.outputs[1]).page_count == 1
    assert "ALPHA-4" in _text(result.outputs[1])
    assert "ALPHA-3" not in _text(result.outputs[1])


def test_extract_preserves_requested_order(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "extract.pdf"
    engine.extract_pages(sample_pdf, [4, 1, 3], dest)
    text = _text(dest)
    assert text.index("ALPHA-4") < text.index("ALPHA-1") < text.index("ALPHA-3")
    assert engine.inspect(dest).page_count == 3


def test_reorder_permutation(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "reordered.pdf"
    engine.reorder(sample_pdf, [4, 3, 2, 1], dest)
    text = _text(dest)
    assert [line for line in text.splitlines() if "ALPHA-" in line] == [
        "Page 4 unique marker ALPHA-4",
        "Page 3 unique marker ALPHA-3",
        "Page 2 unique marker ALPHA-2",
        "Page 1 unique marker ALPHA-1",
    ]


def test_reorder_rejects_partial_order(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.reorder(sample_pdf, [1, 2], tmp_path / "bad.pdf")
        raise AssertionError("expected page range error")
    except PageRangeError:
        pass


def test_rotate_pages(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "rotated.pdf"
    engine.rotate(sample_pdf, {1: 90, 3: 180}, dest)
    reader = PdfReader(str(dest))
    assert int(reader.pages[0].get("/Rotate") or 0) % 360 == 90
    assert int(reader.pages[2].get("/Rotate") or 0) % 360 == 180
    assert int(reader.pages[1].get("/Rotate") or 0) % 360 == 0


def test_delete_pages_keeps_remainder(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "deleted.pdf"
    engine.delete_pages(sample_pdf, [2, 4], dest)
    text = _text(dest)
    assert "ALPHA-1" in text and "ALPHA-3" in text
    assert "ALPHA-2" not in text and "ALPHA-4" not in text
    assert engine.inspect(dest).page_count == 2


def test_delete_all_pages_rejected(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.delete_pages(sample_pdf, [1, 2, 3, 4], tmp_path / "none.pdf")
        raise AssertionError("expected rejection")
    except UnsupportedOperationError:
        pass


def test_compress_produces_valid_pdf(engine: PdfEngine, image_pdf: Path, tmp_path: Path) -> None:
    dest = tmp_path / "compressed.pdf"
    result = engine.compress(image_pdf, dest, level="high")
    assert dest.is_file()
    assert engine.inspect(dest).page_count == 1
    assert dest.read_bytes()[:5] == b"%PDF-"
    assert result.metadata["result_bytes"] > 0


def test_images_to_pdf(engine: PdfEngine, jpeg_image: Path, png_image: Path, tmp_path: Path) -> None:
    dest = tmp_path / "from-images.pdf"
    result = engine.images_to_pdf([jpeg_image, png_image], dest)
    assert engine.inspect(dest).page_count == 2
    assert dest.read_bytes()[:5] == b"%PDF-"
    assert result.metadata["page_count"] == 2


def test_pdf_to_png_and_jpeg(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    pngs = engine.pdf_to_images(sample_pdf, tmp_path / "png", image_format="png", pages=[1, 2])
    jpgs = engine.pdf_to_images(sample_pdf, tmp_path / "jpg", image_format="jpeg", pages="3-4")
    assert len(pngs.outputs) == 2
    assert pngs.outputs[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(jpgs.outputs) == 2
    assert jpgs.outputs[0].read_bytes()[:3] == b"\xff\xd8\xff"


def test_extract_text_includes_page_markers(engine: PdfEngine, sample_pdf: Path) -> None:
    result = engine.extract_text(sample_pdf, pages="2-3")
    assert "ALPHA-2" in result.metadata["text"]
    assert "ALPHA-3" in result.metadata["text"]
    assert "ALPHA-1" not in result.metadata["text"]
    pages = result.metadata["pages"]
    assert pages[0]["page"] == 2


def test_protect_and_unlock_roundtrip(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    locked = tmp_path / "locked.pdf"
    unlocked = tmp_path / "unlocked.pdf"
    engine.protect(sample_pdf, locked, user_password="s3cret-pass")
    try:
        engine.inspect(locked)
        raise AssertionError("encrypted pdf should require a password")
    except EncryptedPdfError:
        pass
    info = engine.inspect(locked, password="s3cret-pass")
    assert info.encrypted
    engine.unlock(locked, unlocked, password="s3cret-pass")
    assert "ALPHA-1" in _text(unlocked)
    try:
        engine.unlock(locked, tmp_path / "nope.pdf", password="wrong-password")
        raise AssertionError("wrong password should fail")
    except EncryptedPdfError:
        pass


def test_encrypted_source_requires_password(engine: PdfEngine, encrypted_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.extract_pages(encrypted_pdf, [1], tmp_path / "x.pdf")
        raise AssertionError("expected encrypted error")
    except EncryptedPdfError:
        pass
    dest = tmp_path / "ok.pdf"
    engine.extract_pages(encrypted_pdf, [1], dest, password="correct-horse")
    assert "Confidential page 1" in _text(dest)


def test_out_of_range_pages(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.extract_pages(sample_pdf, [99], tmp_path / "x.pdf")
        raise AssertionError("expected range error")
    except PageRangeError:
        pass


def test_empty_file_rejected(engine: PdfEngine, tmp_path: Path) -> None:
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    try:
        engine.inspect(empty)
        raise AssertionError("expected empty error")
    except (EmptyDocumentError, InvalidFileError):
        pass


def test_oversized_file_rejected(tmp_path: Path, sample_pdf: Path) -> None:
    tiny = PdfEngine(max_bytes=64, max_pages=10)
    try:
        tiny.inspect(sample_pdf)
        raise AssertionError("expected size error")
    except FileTooLargeError:
        pass


def test_too_many_pages_rejected(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "long.pdf", [f"p{n}" for n in range(8)])
    tiny = PdfEngine(max_bytes=10_000_000, max_pages=3)
    try:
        tiny.extract_text(path)
        raise AssertionError("expected page cap error")
    except TooManyPagesError:
        pass


def test_malformed_pdf_rejected(engine: PdfEngine, not_a_pdf: Path) -> None:
    try:
        engine.inspect(not_a_pdf)
        raise AssertionError("expected invalid pdf")
    except (UnsupportedFormatError, InvalidFileError):
        pass


def test_thumbnails(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    result = engine.thumbnails(sample_pdf, tmp_path / "thumbs", pages=[1])
    assert result.outputs[0].suffix == ".png"
    assert result.outputs[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_original_not_overwritten(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    original = sample_pdf.read_bytes()
    engine.rotate(sample_pdf, {1: 90}, tmp_path / "out.pdf")
    assert sample_pdf.read_bytes() == original


def test_work_directory_cleans_up(sample_pdf: Path) -> None:
    with work_directory() as folder:
        target = folder / "copy.pdf"
        target.write_bytes(sample_pdf.read_bytes())
        assert target.exists()
        saved = folder
    assert not saved.exists()


def test_invalid_rotation(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.rotate(sample_pdf, {1: 45}, tmp_path / "bad.pdf")
        raise AssertionError("expected unsupported rotation")
    except UnsupportedOperationError:
        pass


def test_merge_requires_two_files(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    try:
        engine.merge([sample_pdf], tmp_path / "x.pdf")
        raise AssertionError("expected merge error")
    except UnsupportedOperationError:
        pass
