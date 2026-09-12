"""Pure Realtime lifecycle reduction for captions, recovery, and replay safety."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from backend.realtime.errors import event_invalid_error
from backend.realtime.models import (
    CandidateBinding,
    InputModality,
    StrictModel,
    TranscriptSpeaker,
    TurnIdentifier,
)

VoiceStatus = Literal[
    "Ready",
    "Listening",
    "Thinking",
    "Speaking",
    "Interrupted",
    "Connection lost",
    "Microphone unavailable",
]
CaptionText = Annotated[str, StringConstraints(min_length=1, max_length=4_000)]
DraftText = Annotated[str, StringConstraints(max_length=8_000)]
MAX_RELEVANT_CAPTIONS = 32
MAX_PROCESSED_EVENTS = 2_048


class CaptionTurn(StrictModel):
    turn_id: TurnIdentifier
    speaker: TranscriptSpeaker
    modality: InputModality
    text: CaptionText
    final: bool = False

    @model_validator(mode="after")
    def validate_text(self) -> CaptionTurn:
        _validate_text(self.text, allow_empty=False)
        return self


class VoiceSessionState(StrictModel):
    """Bounded application projection of one browser Realtime session."""

    status: VoiceStatus = "Ready"
    muted: bool = False
    captions: tuple[CaptionTurn, ...] = Field(default=(), max_length=MAX_RELEVANT_CAPTIONS)
    draft_text: DraftText = ""
    draft_version: int = Field(default=0, ge=0)
    draft_source_turn_ids: tuple[TurnIdentifier, ...] = Field(default=(), max_length=32)
    draft_input_modality: InputModality | None = None
    current_candidate: CandidateBinding | None = None
    automatic_reconnect_attempts: int = Field(default=0, ge=0, le=1)
    auto_reconnect_pending: bool = False
    processed_event_ids: tuple[TurnIdentifier, ...] = Field(
        default=(), max_length=MAX_PROCESSED_EVENTS
    )

    @property
    def retry_voice_available(self) -> bool:
        return self.status in {"Connection lost", "Microphone unavailable"}

    @property
    def continue_by_typing_available(self) -> Literal[True]:
        return True

    @model_validator(mode="after")
    def validate_state(self) -> VoiceSessionState:
        _validate_text(self.draft_text, allow_empty=True)
        if self.draft_version == 0 and (
            self.draft_text or self.draft_source_turn_ids or self.draft_input_modality is not None
        ):
            raise ValueError("an untouched draft cannot contain content")
        if self.draft_version > 0 and self.draft_input_modality is None:
            raise ValueError("an updated draft requires its trusted input modality")
        if self.auto_reconnect_pending and (
            self.status != "Connection lost" or self.automatic_reconnect_attempts != 0
        ):
            raise ValueError("automatic reconnect is pending only after the first disconnect")
        if len(self.processed_event_ids) != len(set(self.processed_event_ids)):
            raise ValueError("processed event identifiers must be unique")
        return self


class RealtimeLifecycleEvent(StrictModel):
    event_id: TurnIdentifier


class VoiceStatusEvent(RealtimeLifecycleEvent):
    kind: Literal["voice_status"] = "voice_status"
    status: VoiceStatus


class CaptionEvent(RealtimeLifecycleEvent):
    kind: Literal["caption"] = "caption"
    turn_id: TurnIdentifier
    speaker: TranscriptSpeaker
    modality: InputModality
    text: CaptionText
    final: bool = False

    @model_validator(mode="after")
    def validate_text(self) -> CaptionEvent:
        _validate_text(self.text, allow_empty=False)
        return self


class DraftUpdatedEvent(RealtimeLifecycleEvent):
    kind: Literal["draft_updated"] = "draft_updated"
    exact_text: DraftText
    source_turn_ids: tuple[TurnIdentifier, ...] = Field(default=(), max_length=32)
    input_modality: InputModality

    @model_validator(mode="after")
    def validate_draft(self) -> DraftUpdatedEvent:
        _validate_text(self.exact_text, allow_empty=True)
        if len(self.source_turn_ids) != len(set(self.source_turn_ids)):
            raise ValueError("draft source turn identifiers must be unique")
        return self


class CandidateSynchronizedEvent(RealtimeLifecycleEvent):
    kind: Literal["candidate_synchronized"] = "candidate_synchronized"
    candidate: CandidateBinding


class MuteChangedEvent(RealtimeLifecycleEvent):
    kind: Literal["mute_changed"] = "mute_changed"
    muted: bool


class ConnectionLostEvent(RealtimeLifecycleEvent):
    kind: Literal["connection_lost"] = "connection_lost"


class ReconnectStartedEvent(RealtimeLifecycleEvent):
    kind: Literal["reconnect_started"] = "reconnect_started"
    automatic: bool


class ConnectionRestoredEvent(RealtimeLifecycleEvent):
    kind: Literal["connection_restored"] = "connection_restored"


VoiceEvent = (
    VoiceStatusEvent
    | CaptionEvent
    | DraftUpdatedEvent
    | CandidateSynchronizedEvent
    | MuteChangedEvent
    | ConnectionLostEvent
    | ReconnectStartedEvent
    | ConnectionRestoredEvent
)


def apply_voice_event(state: VoiceSessionState, event: VoiceEvent) -> VoiceSessionState:
    """Apply one event once; duplicates are identity-preserving no-ops."""

    if event.event_id in state.processed_event_ids:
        return state
    if len(state.processed_event_ids) >= MAX_PROCESSED_EVENTS:
        raise event_invalid_error()

    updates: dict[str, object] = {
        "processed_event_ids": (*state.processed_event_ids, event.event_id)
    }
    if isinstance(event, VoiceStatusEvent):
        updates["status"] = event.status
        updates["auto_reconnect_pending"] = (
            event.status == "Connection lost" and state.automatic_reconnect_attempts == 0
        )
    elif isinstance(event, CaptionEvent):
        updates["captions"] = _apply_caption(state.captions, event)
    elif isinstance(event, DraftUpdatedEvent):
        source_turns = _student_source_turns(state.captions, event.source_turn_ids)
        if event.exact_text:
            if not source_turns:
                raise event_invalid_error()
            source_text = " ".join(turn.text for turn in source_turns)
            if source_text != event.exact_text:
                raise event_invalid_error()
            if any(turn.modality != event.input_modality for turn in source_turns):
                raise event_invalid_error()
        elif event.source_turn_ids:
            raise event_invalid_error()
        updates.update(
            draft_text=event.exact_text,
            draft_version=state.draft_version + 1,
            draft_source_turn_ids=event.source_turn_ids,
            draft_input_modality=event.input_modality,
        )
    elif isinstance(event, CandidateSynchronizedEvent):
        _validate_candidate_progression(state.current_candidate, event.candidate)
        source_turns = _student_source_turns(state.captions, state.draft_source_turn_ids)
        if (
            not state.draft_text
            or event.candidate.exact_text != state.draft_text
            or not source_turns
            or any(not turn.final for turn in source_turns)
        ):
            raise event_invalid_error()
        updates["current_candidate"] = event.candidate
    elif isinstance(event, MuteChangedEvent):
        updates["muted"] = event.muted
    elif isinstance(event, ConnectionLostEvent):
        updates["status"] = "Connection lost"
        updates["auto_reconnect_pending"] = state.automatic_reconnect_attempts == 0
    elif isinstance(event, ReconnectStartedEvent):
        if state.status != "Connection lost":
            raise event_invalid_error()
        if event.automatic:
            if state.automatic_reconnect_attempts >= 1:
                raise event_invalid_error()
            updates["automatic_reconnect_attempts"] = 1
        updates["auto_reconnect_pending"] = False
    elif isinstance(event, ConnectionRestoredEvent):
        if state.status != "Connection lost":
            raise event_invalid_error()
        updates["status"] = "Ready"
        updates["auto_reconnect_pending"] = False
    return VoiceSessionState.model_validate(
        {**state.model_dump(mode="python"), **updates}, strict=True
    )


def _apply_caption(
    captions: tuple[CaptionTurn, ...], event: CaptionEvent
) -> tuple[CaptionTurn, ...]:
    incoming = CaptionTurn(
        turn_id=event.turn_id,
        speaker=event.speaker,
        modality=event.modality,
        text=event.text,
        final=event.final,
    )
    updated = list(captions)
    for index, current in enumerate(updated):
        if current.turn_id != incoming.turn_id:
            continue
        if current.speaker != incoming.speaker or current.modality != incoming.modality:
            raise event_invalid_error()
        if current.final and current != incoming:
            raise event_invalid_error()
        updated[index] = incoming
        return tuple(updated)
    updated.append(incoming)
    return tuple(updated[-MAX_RELEVANT_CAPTIONS:])


def _validate_candidate_progression(
    current: CandidateBinding | None, incoming: CandidateBinding
) -> None:
    if current is None:
        return
    if incoming.candidate_id == current.candidate_id:
        if incoming.candidate_version < current.candidate_version:
            raise event_invalid_error()
        if (
            incoming.candidate_version == current.candidate_version
            and incoming.exact_text != current.exact_text
        ):
            raise event_invalid_error()


def _student_source_turns(
    captions: tuple[CaptionTurn, ...], source_turn_ids: tuple[str, ...]
) -> tuple[CaptionTurn, ...]:
    captions_by_id = {caption.turn_id: caption for caption in captions}
    turns: list[CaptionTurn] = []
    for turn_id in source_turn_ids:
        turn = captions_by_id.get(turn_id)
        if turn is None or turn.speaker != "student":
            raise event_invalid_error()
        turns.append(turn)
    return tuple(turns)


def _validate_text(value: str, *, allow_empty: bool) -> None:
    if "\x00" in value or (not allow_empty and not value.strip()):
        raise ValueError("Realtime text is invalid")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("Realtime text must be valid UTF-8") from error
