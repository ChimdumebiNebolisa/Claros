"""Thin materialization boundary for closed-world compiler results."""
from __future__ import annotations

from document_model import DocumentBlock, DocumentPage
from evaluation.pdf_gold_pilot.closed_world import (
    PilotPageInput,
    PilotPhysicalBlock,
    PilotResponseCandidate,
    derive_tasks,
)
from providers.semantic_compiler import SemanticCompiler


def build_closed_world_page_input(
    *,
    document_id: str,
    source_reference: str,
    page: DocumentPage,
    blocks: list[DocumentBlock],
    image_reference: str,
) -> PilotPageInput:
    """Convert deterministic physical evidence into the compiler's ID-only input."""
    page_blocks = [block for block in blocks if block.page_index == page.page_index]
    physical_blocks = [
        PilotPhysicalBlock(
            id=block.id,
            page_index=block.page_index,
            reading_order=block.reading_order,
            text=block.text,
            block_label=block.block_label,
            bbox=block.bbox,
            polygon=block.polygon,
            confidence=block.confidence,
            source=block.source.value,
            semantic_role=block.semantic_role.value,
        )
        for block in page_blocks
        if block.semantic_role.value != "response_area"
    ]
    response_candidates = [
        PilotResponseCandidate(
            id=block.id,
            page_index=block.page_index,
            reading_order=block.reading_order,
            layout_label=block.block_label,
            bbox=block.bbox,
            confidence=block.confidence,
            source=block.source.value,
            safe_for_writing=(
                block.block_label in {"answer_line", "form_field"} and block.confidence >= 0.85
            ),
            safety_suggestion=(
                "safe_physical"
                if block.block_label in {"answer_line", "form_field"} and block.confidence >= 0.85
                else "ambiguous"
            ),
        )
        for block in page_blocks
        if block.semantic_role.value == "response_area"
    ]
    return PilotPageInput(
        pilot_id=f"{document_id}:page:{page.page_index}",
        source_pdf=source_reference,
        page_number=page.page_index + 1,
        page_index=page.page_index,
        page_width_points=page.width_points,
        page_height_points=page.height_points,
        rotation=page.rotation,
        image=image_reference,
        blocks=physical_blocks,
        response_candidates=response_candidates,
        warnings=page.warnings,
    )


def compile_and_materialize(compiler: SemanticCompiler, page: PilotPageInput, page_image: bytes) -> list[dict]:
    """Compile one page and derive only source-backed text and candidate geometry."""
    return derive_tasks(page, compiler.compile_page(page, page_image))
