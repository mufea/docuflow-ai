from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from docuflow.ai.chunking import chunk_pages, retrieve
from docuflow.ai.providers import MockAIProvider
from docuflow.conversion.engines import ConversionService, write_simple_docx
from docuflow.pdf.engine import PdfEngine
from tests.pdf.conftest import write_text_pdf


def test_mock_summary_uses_real_pages(tmp_path: Path) -> None:
    pdf = write_text_pdf(tmp_path / "ai.pdf", ["Quarterly revenue grew in Jakarta.", "Hiring plan for Bandung office."])
    extracted = PdfEngine().extract_text(pdf)
    chunks = chunk_pages(extracted.metadata["pages"])
    result = MockAIProvider().generate(instruction="Summarize", chunks=chunks)
    cited_pages = {item["page"] for item in result.citations}
    assert cited_pages.issubset({1, 2})
    assert "Jakarta" in result.text or "Bandung" in result.text or "Page" in result.text


def test_retrieval_ranks_relevant_chunk() -> None:
    pages = [
        {"page": 1, "text": "Apples are harvested in autumn."},
        {"page": 2, "text": "The contract value is 12 billion rupiah."},
        {"page": 3, "text": "Unrelated weather notes."},
    ]
    chunks = chunk_pages(pages)
    found = retrieve(chunks, "contract value rupiah")
    assert found[0].page == 2


def test_pdf_to_xlsx_exports_tables(tmp_path: Path) -> None:
    import fitz

    path = tmp_path / "table.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Name  Amount")
    page.insert_text((72, 92), "Ada   10")
    page.insert_text((72, 112), "Grace 20")
    doc.save(path.as_posix())
    doc.close()
    dest = tmp_path / "out.xlsx"
    result = ConversionService().pdf_to_xlsx(path, dest)
    assert dest.is_file()
    assert result.output_format == "xlsx"
    workbook = load_workbook(dest)
    assert workbook.sheetnames


def test_pdf_to_docx(tmp_path: Path) -> None:
    pdf = write_text_pdf(tmp_path / "letter.pdf", ["Dear team, please find the report attached."])
    dest = tmp_path / "letter.docx"
    result = ConversionService().pdf_to_docx(pdf, dest)
    assert dest.is_file()
    assert result.output_format == "docx"
    assert result.limitations


def test_docx_fixture_roundtrip_kind(tmp_path: Path) -> None:
    from docuflow.pdf.sniff import sniff_file

    path = write_simple_docx(tmp_path / "note.docx", ["Hello from DocuFlow"])
    assert sniff_file(path).kind == "docx"
