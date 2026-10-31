from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from docuflow.exceptions import PageRangeError, TooManyPagesError, UnsupportedOperationError
from docuflow.pdf.engine import PdfEngine
from docuflow.pdf.workdir import work_directory
from tests.pdf.conftest import write_text_pdf


def write_animated_gif(path: Path, frames: int) -> Path:
    images = [Image.new("RGB", (24, 24), (index * 20, 40, 80)) for index in range(frames)]
    images[0].save(path, save_all=True, append_images=images[1:], duration=40, loop=0, format="GIF")
    return path


def test_inspect_rejects_over_max_pages(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "long.pdf", [f"page-{n}" for n in range(8)])
    engine = PdfEngine(max_bytes=10_000_000, max_pages=3)
    with pytest.raises(TooManyPagesError) as caught:
        engine.inspect(path)
    assert caught.value.code == "too_many_pages"
    assert "3" in caught.value.message


def test_split_rejects_over_max_pages(tmp_path: Path) -> None:
    path = write_text_pdf(tmp_path / "long.pdf", [f"page-{n}" for n in range(8)])
    engine = PdfEngine(max_bytes=10_000_000, max_pages=3)
    with pytest.raises(TooManyPagesError) as caught:
        engine.split(path, "1-2", tmp_path / "parts")
    assert caught.value.code == "too_many_pages"
    assert not (tmp_path / "parts").exists() or not any((tmp_path / "parts").iterdir())


def test_reversed_tuple_range_rejected(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(PageRangeError) as caught:
        engine.split(sample_pdf, [(4, 2)], tmp_path / "parts")
    assert caught.value.code == "invalid_page_range"
    assert "less than or equal" in caught.value.message


def test_zero_page_tuple_rejected(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(PageRangeError) as caught:
        engine.split(sample_pdf, [(0, 2)], tmp_path / "parts")
    assert caught.value.code == "invalid_page_range"
    assert "1-indexed" in caught.value.message


def test_tuple_beyond_page_count_rejected(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(PageRangeError) as caught:
        engine.split(sample_pdf, [(1, 999)], tmp_path / "parts")
    assert caught.value.code == "invalid_page_range"
    assert "999" in caught.value.message


def test_empty_tuple_rejected(engine: PdfEngine, sample_pdf: Path, tmp_path: Path) -> None:
    with pytest.raises(PageRangeError) as caught:
        engine.split(sample_pdf, [()], tmp_path / "parts")  # type: ignore[list-item]
    assert caught.value.code == "invalid_page_range"


def test_output_same_path_as_input_rejected(engine: PdfEngine, sample_pdf: Path) -> None:
    original = sample_pdf.read_bytes()
    with pytest.raises(UnsupportedOperationError) as caught:
        engine.extract_pages(sample_pdf, [1], sample_pdf)
    assert "overwrite" in caught.value.message
    assert sample_pdf.read_bytes() == original


def test_relative_and_absolute_same_file_rejected(
    engine: PdfEngine, sample_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = sample_pdf.read_bytes()
    monkeypatch.chdir(sample_pdf.parent)
    with pytest.raises(UnsupportedOperationError) as caught:
        engine.compress(sample_pdf, Path(sample_pdf.name))
    assert "overwrite" in caught.value.message
    assert sample_pdf.read_bytes() == original


def test_merge_cannot_overwrite_an_input(engine: PdfEngine, sample_pdf: Path, second_pdf: Path) -> None:
    first = sample_pdf.read_bytes()
    second = second_pdf.read_bytes()
    with pytest.raises(UnsupportedOperationError) as caught:
        engine.merge([sample_pdf, second_pdf], sample_pdf)
    assert "overwrite" in caught.value.message
    assert sample_pdf.read_bytes() == first
    assert second_pdf.read_bytes() == second


def test_animated_gif_frames_respect_max_pages(tmp_path: Path) -> None:
    gif = write_animated_gif(tmp_path / "anim.gif", frames=6)
    original = gif.read_bytes()
    dest = tmp_path / "from-gif.pdf"
    engine = PdfEngine(max_bytes=10_000_000, max_pages=3, max_images=10)
    with pytest.raises(TooManyPagesError) as caught:
        engine.images_to_pdf([gif], dest)
    assert caught.value.code == "too_many_pages"
    assert gif.read_bytes() == original
    assert not dest.exists()
    assert not dest.with_name(f".{dest.name}.partial").exists()


def test_failed_image_conversion_leaves_no_partial_pdf(tmp_path: Path) -> None:
    gif = write_animated_gif(tmp_path / "anim.gif", frames=5)
    dest = tmp_path / "partial.pdf"
    engine = PdfEngine(max_bytes=10_000_000, max_pages=2, max_images=10)
    with pytest.raises(TooManyPagesError):
        engine.images_to_pdf([gif], dest)
    assert not dest.exists()
    leftovers = list(tmp_path.glob("*.partial")) + list(tmp_path.glob(".*.partial"))
    assert leftovers == []


def test_source_unchanged_after_failed_operation(engine: PdfEngine, sample_pdf: Path) -> None:
    original = sample_pdf.read_bytes()
    with pytest.raises(PageRangeError):
        engine.extract_pages(sample_pdf, [99], sample_pdf.with_name("should-not-exist.pdf"))
    assert sample_pdf.read_bytes() == original
    assert not sample_pdf.with_name("should-not-exist.pdf").exists()


def test_work_directory_cleans_up_after_exception(sample_pdf: Path) -> None:
    with pytest.raises(RuntimeError, match="forced failure"):
        with work_directory() as folder:
            target = folder / "copy.pdf"
            target.write_bytes(sample_pdf.read_bytes())
            assert target.exists()
            saved = folder
            raise RuntimeError("forced failure")
    assert not saved.exists()
