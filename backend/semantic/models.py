"""Strict provider contracts for semantic mapping and opt-in rephrasing."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.document.models import BlockKind


class StrictSemanticModel(BaseModel):
    """Closed schemas are part of the semantic trust boundary."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


RelationKind = Literal["immediately_precedes", "immediately_follows"]


class RelationHint(StrictSemanticModel):
    kind: RelationKind
    other_block_id: str = Field(pattern=r"^blk_[0-9a-f]{32}$")


class ProviderBlock(StrictSemanticModel):
    """The only physical evidence exposed to a semantic provider."""

    id: str = Field(pattern=r"^blk_[0-9a-f]{32}$")
    exact_text: str | None
    kind: BlockKind
    page_number: int = Field(ge=1, le=8)
    reading_order: int = Field(ge=0)
    relation_hints: tuple[RelationHint, ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def exact_text_matches_kind(self) -> ProviderBlock:
        if self.kind == "text" and self.exact_text is None:
            raise ValueError("text evidence requires exact_text")
        if self.kind != "text" and self.exact_text is not None:
            raise ValueError("non-text evidence cannot carry text")
        return self


class SemanticMappingInput(StrictSemanticModel):
    schema_version: Literal[1] = 1
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{24}$")
    blocks: tuple[ProviderBlock, ...] = Field(min_length=1, max_length=4096)


QuestionType = Literal[
    "short_answer",
    "multiple_choice",
    "essay",
    "matching",
    "table",
    "other",
]
GroundingStatus = Literal["grounded", "ambiguous"]
MappingWarning = Literal["shared_instruction", "visual_context_required"]


class SemanticQuestionOutput(StrictSemanticModel):
    question_key: str = Field(pattern=r"^q_[0-9]{3}$")
    prompt_block_ids: tuple[str, ...] = Field(min_length=1, max_length=64)
    context_block_ids: tuple[str, ...] = Field(default=(), max_length=64)
    question_type: QuestionType
    grounding: GroundingStatus
    visual_context_dependency: bool
    warnings: tuple[MappingWarning, ...] = Field(default=(), max_length=2)


class SemanticMappingOutput(StrictSemanticModel):
    schema_version: Literal[1] = 1
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{24}$")
    complete: bool
    questions: tuple[SemanticQuestionOutput, ...] = Field(max_length=40)


class RephraseInput(StrictSemanticModel):
    schema_version: Literal[1] = 1
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{24}$")
    question_key: str = Field(pattern=r"^q_[0-9]{3}$")
    exact_question: str = Field(min_length=1, max_length=16_384)
    exact_candidate: str = Field(min_length=1, max_length=8_192)
    exact_allowed_context: str | None = Field(default=None, max_length=16_384)


class RephraseOutput(StrictSemanticModel):
    schema_version: Literal[1] = 1
    suggestion: str = Field(min_length=1, max_length=8_192)
    meaning_preserved: bool
    factual_changes: tuple[str, ...] = Field(default=(), max_length=16)
    unsupported_claims: tuple[str, ...] = Field(default=(), max_length=16)


class ValidatedQuestion(StrictSemanticModel):
    question_key: str = Field(pattern=r"^q_[0-9]{3}$")
    exact_prompt: str = Field(min_length=1)
    exact_context: str | None = None
    prompt_block_ids: tuple[str, ...]
    context_block_ids: tuple[str, ...]
    page_number: int = Field(ge=1, le=8)
    visual_context_dependency: bool
    warnings: tuple[MappingWarning, ...]


class ValidatedMapping(StrictSemanticModel):
    document_id: str
    questions: tuple[ValidatedQuestion, ...]


class SafeRephrase(StrictSemanticModel):
    """A comparison result; the original is retained byte-for-byte."""

    exact_original: str
    exact_suggestion: str
    factual_changes: tuple[str, ...]
    factual_delta_safe: Literal[True] = True


StrictJsonObject = Annotated[dict[str, object], Field()]
