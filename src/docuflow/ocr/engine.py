from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from docuflow.exceptions import EncryptedPdfError, EngineUnavailableError
from docuflow.pdf.sniff import require_pdf


@dataclass
class OcrPage:
    page: int
    text: str


@dataclass
class OcrResult:
    pages: list[OcrPage]
    engine: str
    available: bool
    limitations: list[str]


class OcrEngine:
    def __init__(self, *, enabled: bool = True, language: str = "eng") -> None:
        self.enabled = enabled
        self.language = language

    def status(self) -> dict[str, Any]:
        tesseract = shutil.which("tesseract")
        return {
            "enabled": self.enabled,
            "tesseract": bool(tesseract),
            "available": bool(self.enabled and tesseract),
            "language": self.language,
        }

    def run(self, source: Path, *, password: str | None = None, pages: list[int] | None = None) -> OcrResult:
        status = self.status()
        if not status["available"]:
            raise EngineUnavailableError("OCR is unavailable. Install Tesseract and keep OCR_ENABLED=true.")
        import pytesseract
        from PIL import Image

        require_pdf(source)
        doc = fitz.open(source.as_posix())
        if doc.is_encrypted:
            if not password or not doc.authenticate(password):
                doc.close()
                raise EncryptedPdfError("This PDF is encrypted. Supply the document password to continue.")
        results: list[OcrPage] = []
        try:
            selected = pages or list(range(1, doc.page_count + 1))
            for page_no in selected:
                page = doc.load_page(page_no - 1)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                text = pytesseract.image_to_string(image, lang=self.language)
                results.append(OcrPage(page=page_no, text=text.strip()))
        finally:
            doc.close()
        return OcrResult(
            pages=results,
            engine="tesseract",
            available=True,
            limitations=[
                "OCR accuracy depends on scan quality, language, and fonts.",
                "Handwriting and low-contrast scans may produce incomplete text.",
            ],
        )
