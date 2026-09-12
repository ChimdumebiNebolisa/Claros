"""Typed Realtime context and application-owned action intents."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        strip_whitespace=False,
    ),
]
ExactText = Annotated[str, StringConstraints(min_length=1, max_length=8_000)]
ContextText = Annotated[str, StringConstraints(max_length=2_000)]
TurnIdentifier = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        strip_whitespace=False,
    ),
]

RealtimeMode = Literal["direct", "guided"]
RealtimePhase = Literal["answering", "candidate_ready", "exact_review"]
InputModality = Literal["audio", "text"]
TranscriptSpeaker = Literal["student", "claros"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CandidateBinding(StrictModel):
    candidate_id: Identifier
    candidate_version: int = Field(ge=1)
    exact_text: ExactText

    @model_validator(mode="after")
    def validate_text(self) -> CandidateBinding:
        _validate_content(self.exact_text, label="candidate")
        return self


class RealtimeSessionContext(StrictModel):
    """Server-authorized context for exactly one active assignment question."""

    assignment_id: Identifier
    assignment_version: int = Field(ge=1)
    question_id: Identifier
    mode: RealtimeMode
    phase: RealtimePhase = "answering"
    exact_question: Annotated[str, StringConstraints(min_length=1, max_length=4_000)]
    relevant_context: tuple[ContextText, ...] = Field(default=(), max_length=8)
    current_candidate: CandidateBinding | None = None
    exact_text_visible: bool = False
    hear_it_offered: bool = False

    @model_validator(mode="after")
    def validate_state(self) -> RealtimeSessionContext:
        _validate_content(self.exact_question, label="question")
        for item in self.relevant_context:
            _validate_content(item, label="context", allow_empty=True)
        if sum(len(item) for item in self.relevant_context) > 8_000:
            raise ValueError("relevant context is too large")
        if self.phase in {"candidate_ready", "exact_review"} and self.current_candidate is None:
            raise ValueError("the current phase requires a candidate")
        if self.phase == "exact_review" and not (self.exact_text_visible and self.hear_it_offered):
            raise ValueError("exact review requires visible text and the Hear it offer")
        if self.phase != "exact_review" and (self.exact_text_visible or self.hear_it_offered):
            raise ValueError("review readiness is valid only in exact review")
        return self


class DraftCandidateIntent(StrictModel):
    kind: Literal["create_draft_candidate"] = "create_draft_candidate"
    assignment_id: Identifier
    assignment_version: int = Field(ge=1)
    question_id: Identifier
    exact_text: ExactText
    source_turn_ids: tuple[TurnIdentifier, ...] = Field(min_length=1, max_length=32)
    input_modality: InputModality

    @model_validator(mode="after")
    def validate_draft(self) -> DraftCandidateIntent:
        _validate_content(self.exact_text, label="candidate")
        if len(self.source_turn_ids) != len(set(self.source_turn_ids)):
            raise ValueError("source turn identifiers must be unique")
        return self


class RephraseIntent(StrictModel):
    kind: Literal["request_rephrase"] = "request_rephrase"
    assignment_id: Identifier
    assignment_version: int = Field(ge=1)
    question_id: Identifier
    candidate_id: Identifier
    candidate_version: int = Field(ge=1)


class EnterExactReviewIntent(StrictModel):
    kind: Literal["enter_exact_review"] = "enter_exact_review"
    assignment_id: Identifier
    assignment_version: int = Field(ge=1)
    question_id: Identifier
    candidate_id: Identifier
    candidate_version: int = Field(ge=1)


class VoiceConfirmationIntent(StrictModel):
    """A request for the normal confirmation API, never confirmation itself."""

    kind: Literal["request_exact_confirmation"] = "request_exact_confirmation"
    assignment_id: Identifier
    assignment_version: int = Field(ge=1)
    question_id: Identifier
    candidate_id: Identifier
    candidate_version: int = Field(ge=1)
    trigger: Literal["exact_voice_phrase"] = "exact_voice_phrase"


RealtimeActionIntent = DraftCandidateIntent | RephraseIntent | EnterExactReviewIntent


def _validate_content(value: str, *, label: str, allow_empty: bool = False) -> None:
    if "\x00" in value or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} text is invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} text must be valid UTF-8") from error
