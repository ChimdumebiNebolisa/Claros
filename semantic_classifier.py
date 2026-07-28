"""Strict Gemini semantic classification for physically extracted document blocks."""
from __future__ import annotations

import json
import logging
from typing import Literal, Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, model_validator

from config import get_api_key, get_text_model
from document_model import BlockSemanticRole, DocumentBlock, DocumentPage, PageRole

logger = logging.getLogger(__name__)


class SemanticBlockDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    role: BlockSemanticRole
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticTaskCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = None
    prompt_text: str
    prompt_block_ids: list[str] = Field(min_length=1)
    response_block_ids: list[str] = Field(default_factory=list)
    response_type: Literal["short_text", "long_text", "numeric", "choice", "drawing", "table", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)


class SemanticPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    page_role: PageRole
    confidence: float = Field(ge=0.0, le=1.0)
    blocks: list[SemanticBlockDecision]
    tasks: list[SemanticTaskCandidate]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_references(self):
        block_ids = [item.block_id for item in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("semantic block decisions must be unique")
        task_signatures = [
            (
                item.label,
                item.prompt_text.strip(),
                tuple(item.prompt_block_ids),
                tuple(item.response_block_ids),
            )
            for item in self.tasks
        ]
        if len(task_signatures) != len(set(task_signatures)):
            raise ValueError("semantic tasks must be unique")
        return self


class SemanticClassifier(Protocol):
    def classify_page(
        self,
        page: DocumentPage,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        """Classify one page and return strictly validated semantic output."""


class NullSemanticClassifier:
    def classify_page(
        self,
        page: DocumentPage,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        return SemanticPageResult(
            page_index=page.page_index,
            page_role=PageRole.unknown,
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
            warnings=["semantic_classifier_not_configured"],
        )


_SYSTEM_INSTRUCTION = """You classify educational packet pages after physical PDF/OCR extraction.
Use layout labels, geometry, reading order, page context, and the page image when present.
Do not assume that numbered text is a student question. Distinguish teacher directions,
answer keys, examples, rubrics, standards, tables/reference values, metadata, and student-answerable prompts.
Only return a task when the page contains a prompt the student is expected to answer.
Only reference a response block when the physical block itself is an explicit writable area.
Never invent block IDs, coordinates, response areas, or educational content."""


def _classification_prompt(page: DocumentPage, blocks: list[DocumentBlock], page_context: str) -> str:
    block_payload = [
        {
            "id": block.id,
            "order": block.reading_order,
            "layout_label": block.block_label,
            "bbox_points": [round(value, 1) for value in block.bbox],
            "confidence": round(block.confidence, 3),
            "text": block.text[:2000],
        }
        for block in blocks
    ]
    return json.dumps(
        {
            "page_index": page.page_index,
            "page_width_points": page.width_points,
            "page_height_points": page.height_points,
            "native_text_exists": page.native_text_exists,
            "page_context": page_context[:2000],
            "blocks": block_payload,
        },
        ensure_ascii=False,
    )


class GeminiSemanticClassifier:
    """Gemini structured-output semantic layer using Claros's existing credentials."""

    def __init__(self, client=None, model: str | None = None):
        self._client = client
        self._model = model

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(
                api_key=get_api_key(),
                http_options=types.HttpOptions(api_version="v1alpha"),
            )
        return self._client

    def classify_page(
        self,
        page: DocumentPage,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        known_block_ids = {block.id for block in blocks}
        contents: list[object] = [_classification_prompt(page, blocks, page_context)]
        if page_image:
            contents.append(types.Part.from_bytes(data=page_image, mime_type="image/png"))
        try:
            response = self._get_client().models.generate_content(
                model=self._model or get_text_model(),
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_json_schema=SemanticPageResult.model_json_schema(),
                    temperature=0,
                ),
            )
            raw = getattr(response, "parsed", None)
            if isinstance(raw, SemanticPageResult):
                result = raw
            elif raw is not None:
                result = SemanticPageResult.model_validate(raw)
            else:
                result = SemanticPageResult.model_validate_json(response.text or "")
            if result.page_index != page.page_index:
                raise ValueError("semantic page_index did not match the requested page")
            decision_ids = {item.block_id for item in result.blocks}
            if decision_ids != known_block_ids:
                raise ValueError("semantic block decisions did not exactly cover extracted blocks")
            for task in result.tasks:
                references = task.prompt_block_ids + task.response_block_ids
                if any(block_id not in known_block_ids for block_id in references):
                    raise ValueError("semantic task referenced an unknown block")
                if not task.prompt_text.strip():
                    raise ValueError("semantic task prompt_text was empty")
            if result.page_role not in {PageRole.student_worksheet, PageRole.mixed} and result.tasks:
                raise ValueError("non-student page returned student tasks")
            source_blocks = {block.id: block for block in blocks}
            materialized_tasks = []
            for task in result.tasks:
                selected_blocks = sorted(
                    (source_blocks[block_id] for block_id in task.prompt_block_ids),
                    key=lambda block: block.reading_order,
                )
                prompt_text = "\n".join(block.text.strip() for block in selected_blocks if block.text.strip())
                if not prompt_text:
                    raise ValueError("semantic task selected no source prompt text")
                materialized_tasks.append(task.model_copy(update={"prompt_text": prompt_text}))
            return result.model_copy(update={"tasks": materialized_tasks})
        except Exception as exc:
            # Do not log page text, model output, or image bytes.
            logger.warning(
                "Semantic classification rejected page_index=%s error_type=%s",
                page.page_index,
                type(exc).__name__,
            )
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.unknown,
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
                warnings=["semantic_result_rejected", type(exc).__name__],
            )
