from __future__ import annotations

import shutil

from fastapi import APIRouter, Request

from docuflow.billing.plans import DEFAULT_OPERATION_COSTS
from docuflow.jobs.operations import JOB_OPERATIONS
from docuflow.ocr.engine import OcrEngine

router = APIRouter(prefix="/v1/meta", tags=["meta"])

TOOLS = [
    {
        "slug": "merge",
        "name": "Merge PDFs",
        "description": "Combine two or more PDFs into a single document.",
        "inputs": "pdf+",
        "available": True,
    },
    {
        "slug": "split",
        "name": "Split PDF",
        "description": "Split a PDF into separate files by page ranges.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "extract",
        "name": "Extract pages",
        "description": "Keep only the pages you need, in any order.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "reorder",
        "name": "Reorder pages",
        "description": "Rearrange every page without dropping content.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "rotate",
        "name": "Rotate pages",
        "description": "Rotate selected pages by 90, 180, or 270 degrees.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "delete_pages",
        "name": "Delete pages",
        "description": "Remove selected pages and keep the rest intact.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "compress",
        "name": "Compress PDF",
        "description": "Reduce file size with configurable quality.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "images_to_pdf",
        "name": "Images to PDF",
        "description": "Build a PDF from JPEG, PNG, GIF, or WebP images.",
        "inputs": "image+",
        "available": True,
    },
    {
        "slug": "pdf_to_images",
        "name": "PDF to images",
        "description": "Export pages as PNG or JPEG.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "extract_text",
        "name": "Extract text",
        "description": "Pull text with page markers from a born-digital PDF.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "protect",
        "name": "Protect PDF",
        "description": "Encrypt a PDF with an AES-256 password.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "unlock",
        "name": "Unlock PDF",
        "description": "Remove a password only when you supply the correct one.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "pdf_to_docx",
        "name": "PDF to Word",
        "description": "Convert a PDF to DOCX. Layout is approximate.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "pdf_to_xlsx",
        "name": "PDF to Excel",
        "description": "Extract detected tables into an XLSX workbook.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "docx_to_pdf",
        "name": "Word to PDF",
        "description": "Convert DOCX to PDF using LibreOffice when installed.",
        "inputs": "docx",
        "available": bool(shutil.which("soffice") or shutil.which("libreoffice")),
    },
    {
        "slug": "ocr",
        "name": "OCR scanned PDF",
        "description": "Recognize text on scanned pages with Tesseract.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "summarize",
        "name": "Summarize",
        "description": "Summarize extracted PDF text with page citations.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "ask",
        "name": "Ask a PDF",
        "description": "Ask a question grounded in extracted text and citations.",
        "inputs": "pdf",
        "available": True,
    },
    {
        "slug": "extract_structured",
        "name": "Extract structured data",
        "description": "Pull schema-bound fields from document text.",
        "inputs": "pdf",
        "available": True,
    },
]


@router.get("/tools")
def tools(request: Request) -> dict:
    ocr = OcrEngine(enabled=request.app.state.ctx.settings.ocr_enabled).status()
    catalog = []
    for tool in TOOLS:
        item = dict(tool)
        if item["slug"] == "ocr":
            item["available"] = ocr["available"]
        item["credits"] = DEFAULT_OPERATION_COSTS.get(str(item["slug"]), 1)
        catalog.append(item)
    return {
        "tools": catalog,
        "operations": sorted(JOB_OPERATIONS),
        "privacy": {
            "retention_hours_uploads": request.app.state.ctx.settings.file_retention_hours,
            "retention_hours_results": request.app.state.ctx.settings.result_retention_hours,
            "ai_provider": request.app.state.ctx.settings.ai_provider,
            "documents_sent_to_ai_provider": request.app.state.ctx.settings.ai_provider != "mock",
        },
        "ocr": ocr,
        "docx_to_pdf": {
            "available": bool(shutil.which("soffice") or shutil.which("libreoffice")),
        },
    }
