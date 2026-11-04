from __future__ import annotations

from pathlib import Path

import pytest

from docuflow.exceptions import EncryptedPdfError, EngineUnavailableError
from docuflow.ocr.engine import OcrEngine, OcrPage, builtin_ocr_available, texts_from_rapidocr
from tests.pdf.conftest import write_scanned_text_pdf, write_text_pdf


def test_ocr_status_available_without_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docuflow.ocr.engine.find_tesseract", lambda: None)
    monkeypatch.setattr("docuflow.ocr.engine.builtin_ocr_available", lambda: True)
    status = OcrEngine().status()
    assert status["enabled"] is True
    assert status["tesseract"] is False
    assert status["rapidocr"] is True
    assert status["available"] is True
    assert status["engine"] == "rapidocr"


def test_ocr_disabled_keeps_flag_contract(tmp_path: Path) -> None:
    engine = OcrEngine(enabled=False)
    status = engine.status()
    assert status["enabled"] is False
    assert status["available"] is False
    with pytest.raises(EngineUnavailableError, match="OCR_ENABLED=true"):
        engine.run(tmp_path / "unused.pdf")


def test_ocr_prefers_tesseract_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docuflow.ocr.engine.find_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr("docuflow.ocr.engine.builtin_ocr_available", lambda: True)
    monkeypatch.setattr(
        OcrEngine,
        "_ocr_tesseract",
        lambda self, frames: [OcrPage(page=frames[0][0], text="TESSERACT HIT")],
    )
    source = write_scanned_text_pdf(tmp_path / "scan.pdf")
    result = OcrEngine().run(source)
    assert result.engine == "tesseract"
    assert result.available is True
    assert result.pages[0].text == "TESSERACT HIT"


def test_ocr_falls_back_when_tesseract_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docuflow.ocr.engine.find_tesseract", lambda: "/usr/bin/tesseract")
    monkeypatch.setattr("docuflow.ocr.engine.builtin_ocr_available", lambda: True)

    def boom(self: OcrEngine, frames: list) -> list[OcrPage]:
        raise RuntimeError("tesseract missing at runtime")

    monkeypatch.setattr(OcrEngine, "_ocr_tesseract", boom)
    monkeypatch.setattr(
        OcrEngine,
        "_ocr_rapidocr",
        lambda self, frames: [OcrPage(page=frames[0][0], text="RAPID HIT")],
    )
    source = write_scanned_text_pdf(tmp_path / "scan.pdf")
    result = OcrEngine().run(source)
    assert result.engine == "rapidocr"
    assert "RapidOCR" in result.limitations[0]
    assert result.pages[0].text == "RAPID HIT"


def test_ocr_encrypted_requires_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("docuflow.ocr.engine.find_tesseract", lambda: None)
    monkeypatch.setattr("docuflow.ocr.engine.builtin_ocr_available", lambda: True)
    monkeypatch.setattr(
        OcrEngine,
        "_ocr_rapidocr",
        lambda self, frames: [OcrPage(page=frames[0][0], text="ok")],
    )
    source = write_text_pdf(tmp_path / "secret.pdf", ["hidden"], password="correct-horse")
    with pytest.raises(EncryptedPdfError):
        OcrEngine().run(source)
    result = OcrEngine().run(source, password="correct-horse")
    assert result.available is True
    assert result.pages[0].page == 1
    assert result.pages[0].text == "ok"


def test_texts_from_rapidocr_shapes() -> None:
    class Output:
        txts = ("Hello", "World")

    assert texts_from_rapidocr(Output()) == "Hello\nWorld"
    assert texts_from_rapidocr([[[(0, 0), (1, 0), (1, 1), (0, 1)], "INVOICE", 0.99]]) == "INVOICE"
    assert texts_from_rapidocr(([[None, "48291", 0.8]], 0.12)) == "48291"
    assert texts_from_rapidocr(None) == ""


@pytest.mark.slow
def test_ocr_reads_image_only_pdf_without_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not builtin_ocr_available():
        pytest.skip("RapidOCR ONNX is not installed")
    monkeypatch.setattr("docuflow.ocr.engine.find_tesseract", lambda: None)
    source = write_scanned_text_pdf(tmp_path / "invoice.pdf", "INVOICE 48291")
    result = OcrEngine().run(source)
    blob = " ".join(page.text for page in result.pages).upper()
    assert result.engine == "rapidocr"
    assert result.available is True
    assert "INVOICE" in blob
    assert "48291" in blob.replace(" ", "")
