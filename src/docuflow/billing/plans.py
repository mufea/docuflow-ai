from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PLANS = [
    {
        "slug": "free",
        "name": "Free",
        "monthly_credits": 50,
        "max_file_bytes": 10 * 1024 * 1024,
        "max_pages": 25,
        "max_ai_requests_per_day": 5,
        "features": {"ai": True, "ocr": True, "conversion": True, "priority": False},
        "is_public": True,
    },
    {
        "slug": "pro",
        "name": "Pro",
        "monthly_credits": 500,
        "max_file_bytes": 50 * 1024 * 1024,
        "max_pages": 200,
        "max_ai_requests_per_day": 80,
        "features": {"ai": True, "ocr": True, "conversion": True, "priority": True},
        "is_public": False,
    },
    {
        "slug": "business",
        "name": "Business",
        "monthly_credits": 2000,
        "max_file_bytes": 100 * 1024 * 1024,
        "max_pages": 500,
        "max_ai_requests_per_day": 400,
        "features": {"ai": True, "ocr": True, "conversion": True, "priority": True, "admin_sso": False},
        "is_public": False,
    },
]

DEFAULT_OPERATION_COSTS = {
    "merge": 1,
    "split": 1,
    "extract": 1,
    "reorder": 1,
    "rotate": 1,
    "delete_pages": 1,
    "compress": 2,
    "images_to_pdf": 1,
    "pdf_to_images": 2,
    "extract_text": 1,
    "protect": 1,
    "unlock": 1,
    "thumbnails": 1,
    "pdf_to_docx": 6,
    "pdf_to_xlsx": 6,
    "docx_to_pdf": 6,
    "ocr": 8,
    "summarize": 10,
    "ask": 8,
    "extract_structured": 12,
}


@dataclass(frozen=True)
class PricingPolicy:
    """Failed jobs refund reserved credits. Successful jobs settle the reserved amount.
    Duplicate charges are prevented by ledger idempotency keys. Negative balances are
    forbidden unless ALLOW_NEGATIVE_CREDITS is explicitly enabled.
    """

    refund_failed_jobs: bool = True
    allow_negative: bool = False
