"""Runtime bridge from GPT-5.6 closed-world output to the document pipeline."""
from __future__ import annotations

import logging

from document_compiler import build_closed_world_page_input
from document_model import BlockSemanticRole, DocumentBlock, DocumentPage
from evaluation.pdf_gold_pilot.closed_world import derive_tasks
from providers.openai_semantic_compiler import OpenAISemanticCompiler
from semantic_classifier import (
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)

logger = logging.getLogger(__name__)

_REJECTION_ROLES = {
    "teacher_instruction": BlockSemanticRole.teacher_instruction,
    "answer_key_content": BlockSemanticRole.answer_key_content,
    "example": BlockSemanticRole.example,
    "rubric": BlockSemanticRole.rubric,
    "standard": BlockSemanticRole.standard,
    "reference_value": BlockSemanticRole.table_or_reference_value,
    "navigation": BlockSemanticRole.navigation_or_metadata,
    "decorative": BlockSemanticRole.decorative_or_irrelevant,
}


class OpenAIClosedWorldSemanticClassifier:
    """Use GPT-5.6 for page semantics while deterministic code owns all evidence."""

    parser_name = "hybrid-physical-ir-gpt56"
    requires_page_image = True

    def __init__(self, compiler=None):
        self._compiler = compiler or OpenAISemanticCompiler()

    def classify_page(
        self,
        page: DocumentPage,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        del page_context  # The closed-world request is intentionally page-local.
        if page_image is None:
            return self._rejected(page, blocks, "page_image_required")
        try:
            compiler_input = build_closed_world_page_input(
                document_id="runtime",
                source_reference="runtime-physical-ir",
                page=page,
                blocks=blocks,
                image_reference="inline-page-image",
            )
            result = self._compiler.compile_page(compiler_input, page_image)
            materialized = derive_tasks(compiler_input, result)
            prompt_ids = {
                block_id
                for task in materialized
                for block_id in task["prompt_block_ids"]
            }
            rejected_roles = {
                item.block_id: _REJECTION_ROLES.get(item.reason, BlockSemanticRole.unknown)
                for item in result.rejected_blocks
            }
            decisions = []
            for block in blocks:
                if block.id in prompt_ids:
                    role = BlockSemanticRole.student_prompt
                elif block.id in rejected_roles:
                    role = rejected_roles[block.id]
                else:
                    role = block.semantic_role
                decisions.append(SemanticBlockDecision(block_id=block.id, role=role, confidence=1.0))
            tasks = [
                SemanticTaskCandidate(
                    label=task["subpart"] or str(task["group_index"]),
                    prompt_text=task["prompt_text"],
                    prompt_block_ids=task["prompt_block_ids"],
                    response_block_ids=task["response_candidate_ids"],
                    response_type="short_text",
                    confidence=1.0 if not task["needs_review"] else 0.0,
                )
                for task in materialized
                if task["prompt_text"].strip()
            ]
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=result.page_role,
                confidence=1.0 if not result.needs_review else 0.0,
                blocks=decisions,
                tasks=tasks,
                warnings=["openai_closed_world_compiler"],
            )
        except Exception as exc:
            # Never retain or log document text, page images, or provider output.
            logger.warning(
                "OpenAI closed-world classification rejected page_index=%s error_type=%s",
                page.page_index,
                type(exc).__name__,
            )
            return self._rejected(page, blocks, type(exc).__name__)

    @staticmethod
    def _rejected(
        page: DocumentPage,
        blocks: list[DocumentBlock],
        reason: str,
    ) -> SemanticPageResult:
        return SemanticPageResult(
            page_index=page.page_index,
            page_role="unknown",
            confidence=0.0,
            blocks=[
                SemanticBlockDecision(
                    block_id=block.id,
                    role=BlockSemanticRole.unknown,
                    confidence=0.0,
                )
                for block in blocks
            ],
            tasks=[],
            warnings=["openai_semantic_result_rejected", reason],
        )
