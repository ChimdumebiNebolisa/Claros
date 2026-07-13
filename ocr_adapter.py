"""OCR adapter boundary for scanned worksheet pages.

No production OCR dependency is wired in this module. Implementations can plug in
later without changing the layout manifest schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OCRTextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = 0.0


@dataclass(frozen=True)
class OCRPageResult:
    page_index: int
    blocks: list[OCRTextBlock]
    engine: str
    warnings: list[str]


class OCRAdapter(Protocol):
    """Adapter interface for future OCR backends (local or cloud)."""

    def extract_page_text(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        """Extract text geometry for one page. Must not mutate the PDF."""


class NullOCRAdapter:
    """Default adapter: OCR is intentionally unavailable."""

    def extract_page_text(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        return OCRPageResult(
            page_index=page_index,
            blocks=[],
            engine="null",
            warnings=["ocr_not_configured"],
        )


def get_ocr_adapter() -> OCRAdapter:
    """Return the active OCR adapter. Production OCR is deferred out of this PR."""
    return NullOCRAdapter()
