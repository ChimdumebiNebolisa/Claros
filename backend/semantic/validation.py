"""Post-schema validation and exact server-side reconstruction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from backend.document.models import PhysicalBlock, PhysicalDocumentIR
from backend.semantic.errors import semantic_failure
from backend.semantic.models import (
    SafeRephrase,
    SemanticMappingOutput,
    SemanticQuestionOutput,
    ValidatedMapping,
    ValidatedQuestion,
)

_FORBIDDEN_GEOMETRY_KEYS = frozenset(
    {
        "x",
        "y",
        "x0",
        "y0",
        "x1",
        "y1",
        "bbox",
        "bbox_mpt",
        "rect",
        "rectangle",
        "coordinates",
        "placement",
    }
)
_PLACEMENT_ONLY_FLAGS = frozenset(
    {
        "curve_bbox_only",
        "curves_present",
        "non_default_crop_box",
        "non_identity_rotation",
        "non_unit_user_unit",
    }
)


@dataclass(frozen=True, slots=True)
class MappingExpectations:
    expected_question_count: int | None = None
    required_prompt_block_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.expected_question_count is not None and not (
            1 <= self.expected_question_count <= 40
        ):
            raise ValueError("expected_question_count must be between 1 and 40")
        if len(self.required_prompt_block_ids) != len(set(self.required_prompt_block_ids)):
            raise ValueError("required prompt IDs must be unique")


def _has_forbidden_geometry(value: object) -> bool:
    if isinstance(value, dict):
        if any(str(key).lower() in _FORBIDDEN_GEOMETRY_KEYS for key in value):
            return True
        return any(_has_forbidden_geometry(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_has_forbidden_geometry(item) for item in value)
    return False


def parse_mapping_payload(value: object) -> SemanticMappingOutput:
    if _has_forbidden_geometry(value):
        semantic_failure("semantic_forbidden_geometry")
    try:
        return SemanticMappingOutput.model_validate(value)
    except (ValidationError, TypeError, ValueError):
        semantic_failure("semantic_malformed")


def parse_mapping_json(value: str) -> SemanticMappingOutput:
    try:
        decoded = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        semantic_failure("semantic_malformed")
    if _has_forbidden_geometry(decoded):
        semantic_failure("semantic_forbidden_geometry")
    try:
        return SemanticMappingOutput.model_validate_json(value)
    except (ValidationError, TypeError, ValueError):
        semantic_failure("semantic_malformed")


def _block_map(ir: PhysicalDocumentIR) -> dict[str, PhysicalBlock]:
    return {block.id: block for page in ir.pages for block in page.blocks}


def _positions(ir: PhysicalDocumentIR) -> dict[str, tuple[int, int]]:
    return {
        block.id: (block.page_index, block.reading_order)
        for page in ir.pages
        for block in page.blocks
    }


def _assert_unique(ids: tuple[str, ...]) -> None:
    if len(ids) != len(set(ids)):
        semantic_failure("semantic_duplicate_id")


def _assert_known(ids: tuple[str, ...], blocks: dict[str, PhysicalBlock]) -> None:
    if any(block_id not in blocks for block_id in ids):
        semantic_failure("semantic_unknown_id")


def _assert_source_order(ids: tuple[str, ...], positions: dict[str, tuple[int, int]]) -> None:
    order = [positions[block_id] for block_id in ids]
    if order != sorted(order):
        semantic_failure("semantic_reordered")


def _validate_question_shape(
    question: SemanticQuestionOutput,
    blocks: dict[str, PhysicalBlock],
    positions: dict[str, tuple[int, int]],
) -> None:
    _assert_unique(question.prompt_block_ids)
    _assert_unique(question.context_block_ids)
    all_ids = (*question.prompt_block_ids, *question.context_block_ids)
    _assert_known(all_ids, blocks)
    _assert_source_order(question.prompt_block_ids, positions)
    _assert_source_order(question.context_block_ids, positions)
    if set(question.prompt_block_ids) & set(question.context_block_ids):
        semantic_failure("semantic_overlapping")
    if any(blocks[block_id].kind != "text" for block_id in question.prompt_block_ids):
        semantic_failure("semantic_unsupported")
    if question.question_type != "short_answer":
        semantic_failure("semantic_unsupported")
    if question.grounding != "grounded":
        semantic_failure("semantic_ambiguous")
    if question.visual_context_dependency and not any(
        blocks[block_id].kind == "image" for block_id in question.context_block_ids
    ):
        semantic_failure("semantic_incomplete")


def _assert_overlap_rules(
    questions: tuple[SemanticQuestionOutput, ...],
    positions: dict[str, tuple[int, int]],
) -> None:
    prompt_owners: dict[str, str] = {}
    context_owners: dict[str, list[SemanticQuestionOutput]] = {}
    for question in questions:
        for block_id in question.prompt_block_ids:
            if block_id in prompt_owners:
                semantic_failure("semantic_overlapping")
            prompt_owners[block_id] = question.question_key
        for block_id in question.context_block_ids:
            context_owners.setdefault(block_id, []).append(question)

    if set(prompt_owners) & set(context_owners):
        semantic_failure("semantic_overlapping")

    for block_id, owners in context_owners.items():
        if len(owners) < 2:
            continue
        if any("shared_instruction" not in owner.warnings for owner in owners):
            semantic_failure("semantic_overlapping")
        context_position = positions[block_id]
        if any(context_position >= positions[owner.prompt_block_ids[0]] for owner in owners):
            semantic_failure("semantic_overlapping")


def _reconstruct_context(
    ir: PhysicalDocumentIR,
    question: SemanticQuestionOutput,
    blocks: dict[str, PhysicalBlock],
) -> str | None:
    text_ids = tuple(
        block_id for block_id in question.context_block_ids if blocks[block_id].kind == "text"
    )
    return ir.reconstruct_text(text_ids) if text_ids else None


def validate_mapping(
    output: SemanticMappingOutput,
    ir: PhysicalDocumentIR,
    *,
    expectations: MappingExpectations | None = None,
) -> ValidatedMapping:
    expectations = expectations or MappingExpectations()
    if output.document_id != ir.document_id:
        semantic_failure("semantic_unknown_id")
    if not output.complete or not output.questions:
        semantic_failure("semantic_incomplete")
    semantic_document_flags = set(ir.ambiguity_flags) - _PLACEMENT_ONLY_FLAGS
    semantic_page_flags = {
        flag
        for page in ir.pages
        for flag in page.ambiguity_flags
        if flag not in _PLACEMENT_ONLY_FLAGS
    }
    if semantic_document_flags or semantic_page_flags:
        semantic_failure("semantic_ambiguous")

    expected_keys = tuple(f"q_{index:03d}" for index in range(1, len(output.questions) + 1))
    actual_keys = tuple(question.question_key for question in output.questions)
    if len(actual_keys) != len(set(actual_keys)):
        semantic_failure("semantic_duplicate_id")
    if actual_keys != expected_keys:
        semantic_failure("semantic_incomplete")
    if (
        expectations.expected_question_count is not None
        and len(output.questions) != expectations.expected_question_count
    ):
        semantic_failure("semantic_incomplete")

    blocks = _block_map(ir)
    positions = _positions(ir)
    for question in output.questions:
        _validate_question_shape(question, blocks, positions)
        selected_ids = (*question.prompt_block_ids, *question.context_block_ids)
        if any(
            set(blocks[block_id].ambiguity_flags) - _PLACEMENT_ONLY_FLAGS
            for block_id in selected_ids
        ):
            semantic_failure("semantic_ambiguous")

    prompt_starts = [positions[question.prompt_block_ids[0]] for question in output.questions]
    if prompt_starts != sorted(prompt_starts) or len(prompt_starts) != len(set(prompt_starts)):
        semantic_failure("semantic_reordered")
    _assert_overlap_rules(output.questions, positions)

    used_prompt_ids = {
        block_id for question in output.questions for block_id in question.prompt_block_ids
    }
    if not set(expectations.required_prompt_block_ids).issubset(used_prompt_ids):
        semantic_failure("semantic_incomplete")

    validated: list[ValidatedQuestion] = []
    for question in output.questions:
        first_block = blocks[question.prompt_block_ids[0]]
        validated.append(
            ValidatedQuestion(
                question_key=question.question_key,
                exact_prompt=ir.reconstruct_text(question.prompt_block_ids),
                exact_context=_reconstruct_context(ir, question, blocks),
                prompt_block_ids=question.prompt_block_ids,
                context_block_ids=question.context_block_ids,
                page_number=first_block.page_index + 1,
                visual_context_dependency=question.visual_context_dependency,
                warnings=question.warnings,
            )
        )
    return ValidatedMapping(document_id=ir.document_id, questions=tuple(validated))


def validate_rephrase(*, exact_original: str, provider_output: Any) -> SafeRephrase:
    from backend.semantic.models import RephraseOutput

    try:
        parsed = (
            provider_output
            if isinstance(provider_output, RephraseOutput)
            else RephraseOutput.model_validate(provider_output)
        )
    except (ValidationError, TypeError, ValueError):
        semantic_failure("semantic_malformed")
    if (
        not parsed.meaning_preserved
        or parsed.factual_changes
        or parsed.unsupported_claims
        or "\x00" in parsed.suggestion
        or not parsed.suggestion.strip()
    ):
        semantic_failure("semantic_unsafe_rephrase")
    return SafeRephrase(
        exact_original=exact_original,
        exact_suggestion=parsed.suggestion,
        factual_changes=parsed.factual_changes,
    )
