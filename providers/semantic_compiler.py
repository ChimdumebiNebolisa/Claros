"""Closed-world document semantic compiler protocol."""
from __future__ import annotations

from typing import Protocol

from evaluation.pdf_gold_pilot.closed_world import ClosedWorldPageResult, PilotPageInput


class SemanticCompiler(Protocol):
    """Select supplied physical IDs; never author text, coordinates, or write actions."""

    def compile_page(self, page: PilotPageInput, page_image: bytes) -> ClosedWorldPageResult:
        ...
