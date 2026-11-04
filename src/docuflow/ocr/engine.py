from __future__ import annotations

import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
from PIL import Image

from docuflow.exceptions import EncryptedPdfError, EngineUnavailableError
from docuflow.pdf.sniff import require_pdf

logger = logging.getLogger("docuflow.ocr")

TESSERACT_LIMITS = [
    "OCR accuracy depends on scan quality, language, and fonts.",
    "Handwriting and low-contrast scans may produce incomplete text.",
]

RAPIDOCR_LIMITS = [
    "Built-in OCR (RapidOCR ONNX). Tesseract is used when installed.",
    "OCR accuracy depends on scan quality, language, and fonts.",
    "Handwriting and low-contrast scans may produce incomplete text.",
]

_UNAVAILABLE = (
    "OCR is unavailable. Keep OCR_ENABLED=true. The API includes a built-in RapidOCR engine; Tesseract is optional."
)

_rapid_lock = threading.Lock()
_rapid_engine: Any | None = None
_rapid_engine_failed = False


def find_tesseract() -> str | None:
    return shutil.which("tesseract")


def builtin_ocr_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import rapidocr  # noqa: F401
    except ImportError:
        return False
    return True


def _get_rapidocr() -> Any:
    global _rapid_engine, _rapid_engine_failed
    if _rapid_engine is not None:
        return _rapid_engine
    with _rapid_lock:
        if _rapid_engine is not None:
            return _rapid_engine
        if _rapid_engine_failed:
            raise EngineUnavailableError(_UNAVAILABLE)
        try:
            from rapidocr import RapidOCR

            _rapid_engine = RapidOCR()
        except Exception:
            _rapid_engine_failed = True
            logger.exception("RapidOCR engine failed to initialize")
            raise EngineUnavailableError(_UNAVAILABLE) from None
        return _rapid_engine


def _clean_ocr_line(item: Any) -> str:
    if item is None:
        return ""
    return str(item).strip()


def texts_from_rapidocr(result: Any) -> str:
    if result is None:
        return ""
    txts = getattr(result, "txts", None)
    if txts:
        return "\n".join(part for part in (_clean_ocr_line(item) for item in txts) if part)
    payload: Any = result
    if isinstance(result, tuple) and result:
        first = result[0]
        nested = getattr(first, "txts", None)
        if nested:
            return "\n".join(part for part in (_clean_ocr_line(item) for item in nested) if part)
        payload = first
    if isinstance(payload, list):
        lines: list[str] = []
        for item in payload:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                lines.append(_clean_ocr_line(item[1]))
            else:
                lines.append(_clean_ocr_line(item))
        return "\n".join(line for line in lines if line)
    return _clean_ocr_line(result)


def rasterize_pdf_pages(
    source: Path, *, password: str | None = None, pages: list[int] | None = None
) -> list[tuple[int, Image.Image]]:
    require_pdf(source)
    doc = fitz.open(source.as_posix())
    if doc.is_encrypted:
        if not password or not doc.authenticate(password):
            doc.close()
            raise EncryptedPdfError("This PDF is encrypted. Supply the document password to continue.")
    frames: list[tuple[int, Image.Image]] = []
    try:
        selected = pages or list(range(1, doc.page_count + 1))
        for page_no in selected:
            page = doc.load_page(page_no - 1)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            frames.append((page_no, Image.frombytes("RGB", (pix.width, pix.height), pix.samples)))
    finally:
        doc.close()
    return frames


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
        tesseract = bool(find_tesseract())
        rapidocr = builtin_ocr_available()
        engine = None
        if self.enabled and tesseract:
            engine = "tesseract"
        elif self.enabled and rapidocr:
            engine = "rapidocr"
        return {
            "enabled": self.enabled,
            "tesseract": tesseract,
            "rapidocr": rapidocr,
            "available": bool(self.enabled and (tesseract or rapidocr)),
            "engine": engine,
            "language": self.language,
        }

    def run(self, source: Path, *, password: str | None = None, pages: list[int] | None = None) -> OcrResult:
        status = self.status()
        if not self.enabled:
            raise EngineUnavailableError("OCR is disabled. Set OCR_ENABLED=true.")
        if not status["available"]:
            raise EngineUnavailableError(_UNAVAILABLE)
        frames = rasterize_pdf_pages(source, password=password, pages=pages)
        if status["tesseract"]:
            try:
                return OcrResult(
                    pages=self._ocr_tesseract(frames),
                    engine="tesseract",
                    available=True,
                    limitations=list(TESSERACT_LIMITS),
                )
            except Exception as exc:
                if not status["rapidocr"]:
                    raise EngineUnavailableError(_UNAVAILABLE) from exc
                logger.warning("Tesseract OCR failed; using built-in RapidOCR. %s", exc)
        return OcrResult(
            pages=self._ocr_rapidocr(frames),
            engine="rapidocr",
            available=True,
            limitations=list(RAPIDOCR_LIMITS),
        )

    def _ocr_tesseract(self, frames: list[tuple[int, Image.Image]]) -> list[OcrPage]:
        import pytesseract

        return [
            OcrPage(page=page_no, text=pytesseract.image_to_string(image, lang=self.language).strip())
            for page_no, image in frames
        ]

    def _ocr_rapidocr(self, frames: list[tuple[int, Image.Image]]) -> list[OcrPage]:
        engine = _get_rapidocr()
        results: list[OcrPage] = []
        for page_no, image in frames:
            with _rapid_lock:
                raw = engine(image, use_cls=False)
            results.append(OcrPage(page=page_no, text=texts_from_rapidocr(raw)))
        return results
