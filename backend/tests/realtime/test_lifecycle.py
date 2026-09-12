"""Verify the transport lifecycle preserves student work and rejects replay."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.realtime import (
    CandidateBinding,
    CandidateSynchronizedEvent,
    CaptionEvent,
    ConnectionLostEvent,
    ConnectionRestoredEvent,
    DraftUpdatedEvent,
    MuteChangedEvent,
    RealtimeError,
    ReconnectStartedEvent,
    VoiceSessionState,
    VoiceStatusEvent,
    apply_voice_event,
)


def test_captions_mute_and_interruption_remain_explicit_text_state() -> None:
    state = VoiceSessionState()
    assert state.status == "Ready"
    assert state.continue_by_typing_available is True

    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-caption-1",
            turn_id="turn-student-1",
            speaker="student",
            modality="audio",
            text="Chlorophyll captures light.",
            final=True,
        ),
    )
    state = apply_voice_event(
        state,
        VoiceStatusEvent(event_id="event-speaking", status="Speaking"),
    )
    state = apply_voice_event(
        state,
        MuteChangedEvent(event_id="event-muted", muted=True),
    )
    state = apply_voice_event(
        state,
        VoiceStatusEvent(event_id="event-interrupted", status="Interrupted"),
    )

    assert state.status == "Interrupted"
    assert state.muted is True
    assert state.captions[0].text == "Chlorophyll captures light."
    assert state.captions[0].speaker == "student"


@pytest.mark.parametrize(
    "status",
    [
        "Ready",
        "Listening",
        "Thinking",
        "Speaking",
        "Interrupted",
        "Connection lost",
        "Microphone unavailable",
    ],
)
def test_every_required_voice_state_is_an_explicit_label(status: str) -> None:
    event = VoiceStatusEvent.model_validate(
        {"event_id": f"event-{status.replace(' ', '-')}", "status": status}, strict=True
    )
    assert apply_voice_event(VoiceSessionState(), event).status == status


def test_disconnect_preserves_work_and_allows_only_one_automatic_reconnect(
    candidate: CandidateBinding,
) -> None:
    state = VoiceSessionState(current_candidate=candidate)
    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-caption",
            turn_id="turn-student-1",
            speaker="student",
            modality="audio",
            text=candidate.exact_text,
            final=True,
        ),
    )
    state = apply_voice_event(
        state,
        DraftUpdatedEvent(
            event_id="event-draft",
            exact_text=candidate.exact_text,
            source_turn_ids=("turn-student-1",),
            input_modality="audio",
        ),
    )
    state = apply_voice_event(state, ConnectionLostEvent(event_id="event-lost-1"))

    assert state.status == "Connection lost"
    assert state.auto_reconnect_pending is True
    assert state.retry_voice_available is True
    assert state.current_candidate == candidate
    assert state.draft_text == candidate.exact_text

    state = apply_voice_event(
        state,
        ReconnectStartedEvent(event_id="event-reconnect-1", automatic=True),
    )
    assert state.automatic_reconnect_attempts == 1
    assert state.auto_reconnect_pending is False
    state = apply_voice_event(
        state,
        ConnectionRestoredEvent(event_id="event-restored-1"),
    )
    state = apply_voice_event(state, ConnectionLostEvent(event_id="event-lost-2"))
    assert state.auto_reconnect_pending is False

    with pytest.raises(RealtimeError) as raised:
        apply_voice_event(
            state,
            ReconnectStartedEvent(event_id="event-reconnect-2", automatic=True),
        )
    assert raised.value.code == "realtime_event_invalid"

    manual_retry = apply_voice_event(
        state,
        ReconnectStartedEvent(event_id="event-manual-retry", automatic=False),
    )
    assert manual_retry.automatic_reconnect_attempts == 1


def test_replayed_events_do_not_duplicate_draft_or_candidate(
    candidate: CandidateBinding,
) -> None:
    state = VoiceSessionState()
    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-caption",
            turn_id="turn-final",
            speaker="student",
            modality="text",
            text=candidate.exact_text,
            final=True,
        ),
    )
    draft = DraftUpdatedEvent(
        event_id="event-draft",
        exact_text=candidate.exact_text,
        source_turn_ids=("turn-final",),
        input_modality="text",
    )
    state = apply_voice_event(state, draft)
    replayed = apply_voice_event(state, draft)

    assert replayed is state
    assert state.draft_version == 1

    sync = CandidateSynchronizedEvent(event_id="event-candidate", candidate=candidate)
    state = apply_voice_event(state, sync)
    replayed = apply_voice_event(state, sync)
    assert replayed is state
    assert state.current_candidate == candidate


@pytest.mark.parametrize("failure_status", ["Connection lost", "Microphone unavailable"])
def test_typed_turn_remains_available_during_voice_failure(failure_status: str) -> None:
    state = apply_voice_event(
        VoiceSessionState(),
        VoiceStatusEvent(event_id="event-failure", status=failure_status),  # type: ignore[arg-type]
    )
    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-typed-caption",
            turn_id="turn-typed",
            speaker="student",
            modality="text",
            text="I can finish this by typing.",
            final=True,
        ),
    )
    state = apply_voice_event(
        state,
        DraftUpdatedEvent(
            event_id="event-typed-draft",
            exact_text="I can finish this by typing.",
            source_turn_ids=("turn-typed",),
            input_modality="text",
        ),
    )

    assert state.status == failure_status
    assert state.continue_by_typing_available is True
    assert state.draft_text == "I can finish this by typing."


def test_final_caption_cannot_silently_diverge_under_a_new_event_id() -> None:
    state = apply_voice_event(
        VoiceSessionState(),
        CaptionEvent(
            event_id="event-caption-final",
            turn_id="turn-student",
            speaker="student",
            modality="audio",
            text="The exact final transcript.",
            final=True,
        ),
    )
    with pytest.raises(RealtimeError) as raised:
        apply_voice_event(
            state,
            CaptionEvent(
                event_id="event-caption-rewrite",
                turn_id="turn-student",
                speaker="student",
                modality="audio",
                text="A changed transcript.",
                final=True,
            ),
        )
    assert raised.value.code == "realtime_event_invalid"


def test_draft_and_candidate_cannot_silently_diverge_from_visible_student_words(
    candidate: CandidateBinding,
) -> None:
    partial = CaptionEvent(
        event_id="event-caption-partial",
        turn_id="turn-student",
        speaker="student",
        modality="audio",
        text=candidate.exact_text,
        final=False,
    )
    state = apply_voice_event(VoiceSessionState(), partial)

    with pytest.raises(RealtimeError) as rewritten_draft:
        apply_voice_event(
            state,
            DraftUpdatedEvent(
                event_id="event-draft-rewritten",
                exact_text="The model silently changed the student's words.",
                source_turn_ids=("turn-student",),
                input_modality="audio",
            ),
        )
    assert rewritten_draft.value.code == "realtime_event_invalid"

    state = apply_voice_event(
        state,
        DraftUpdatedEvent(
            event_id="event-draft-exact",
            exact_text=candidate.exact_text,
            source_turn_ids=("turn-student",),
            input_modality="audio",
        ),
    )
    with pytest.raises(RealtimeError) as unfinished_transcript:
        apply_voice_event(
            state,
            CandidateSynchronizedEvent(event_id="event-candidate-early", candidate=candidate),
        )
    assert unfinished_transcript.value.code == "realtime_event_invalid"

    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-caption-final",
            turn_id="turn-student",
            speaker="student",
            modality="audio",
            text=candidate.exact_text,
            final=True,
        ),
    )
    divergent = candidate.model_copy(update={"exact_text": "Different candidate text."})
    with pytest.raises(RealtimeError) as rewritten_candidate:
        apply_voice_event(
            state,
            CandidateSynchronizedEvent(event_id="event-candidate-divergent", candidate=divergent),
        )
    assert rewritten_candidate.value.code == "realtime_event_invalid"

    synchronized = apply_voice_event(
        state,
        CandidateSynchronizedEvent(event_id="event-candidate-exact", candidate=candidate),
    )
    assert synchronized.current_candidate == candidate


def test_invalid_lifecycle_snapshots_and_events_fail_closed() -> None:
    invalid_states = (
        {"draft_text": "orphaned"},
        {"draft_version": 1},
        {"status": "Ready", "auto_reconnect_pending": True},
        {"processed_event_ids": ("duplicate", "duplicate")},
    )
    for values in invalid_states:
        with pytest.raises(ValidationError):
            VoiceSessionState.model_validate(values, strict=True)

    with pytest.raises(ValidationError):
        DraftUpdatedEvent(
            event_id="event-duplicate-source",
            exact_text="Repeated source.",
            source_turn_ids=("turn-1", "turn-1"),
            input_modality="text",
        )
    with pytest.raises(ValidationError):
        CaptionEvent(
            event_id="event-null-caption",
            turn_id="turn-1",
            speaker="student",
            modality="audio",
            text="bad\x00caption",
        )


def test_draft_requires_exact_student_caption_and_observed_modality() -> None:
    assistant_state = apply_voice_event(
        VoiceSessionState(),
        CaptionEvent(
            event_id="event-assistant-caption",
            turn_id="turn-assistant",
            speaker="claros",
            modality="audio",
            text="A prompt, not the student's answer.",
            final=True,
        ),
    )
    with pytest.raises(RealtimeError):
        apply_voice_event(
            assistant_state,
            DraftUpdatedEvent(
                event_id="event-assistant-draft",
                exact_text="A prompt, not the student's answer.",
                source_turn_ids=("turn-assistant",),
                input_modality="audio",
            ),
        )

    student_state = apply_voice_event(
        VoiceSessionState(),
        CaptionEvent(
            event_id="event-student-caption",
            turn_id="turn-student",
            speaker="student",
            modality="audio",
            text="My answer.",
            final=True,
        ),
    )
    for event in (
        DraftUpdatedEvent(
            event_id="event-no-source",
            exact_text="My answer.",
            input_modality="audio",
        ),
        DraftUpdatedEvent(
            event_id="event-wrong-modality",
            exact_text="My answer.",
            source_turn_ids=("turn-student",),
            input_modality="text",
        ),
        DraftUpdatedEvent(
            event_id="event-clear-with-source",
            exact_text="",
            source_turn_ids=("turn-student",),
            input_modality="audio",
        ),
    ):
        with pytest.raises(RealtimeError):
            apply_voice_event(student_state, event)


def test_caption_identity_and_candidate_versions_cannot_be_rebound(
    candidate: CandidateBinding,
) -> None:
    state = apply_voice_event(
        VoiceSessionState(),
        CaptionEvent(
            event_id="event-caption-partial",
            turn_id="turn-1",
            speaker="student",
            modality="audio",
            text="Partial",
        ),
    )
    state = apply_voice_event(
        state,
        CaptionEvent(
            event_id="event-caption-update",
            turn_id="turn-1",
            speaker="student",
            modality="audio",
            text="Complete",
            final=True,
        ),
    )
    for index, changed in enumerate(
        (
            {"speaker": "claros"},
            {"modality": "text"},
        ),
        start=1,
    ):
        with pytest.raises(RealtimeError):
            apply_voice_event(
                state,
                CaptionEvent.model_validate(
                    {
                        "event_id": f"event-rebind-{index}",
                        "turn_id": "turn-1",
                        "speaker": "student",
                        "modality": "audio",
                        "text": "Complete",
                        "final": True,
                        **changed,
                    },
                    strict=True,
                ),
            )

    bound = VoiceSessionState(current_candidate=candidate)
    older = candidate.model_copy(update={"candidate_version": 2})
    changed = candidate.model_copy(update={"exact_text": "Changed at the same version."})
    for index, replacement in enumerate((older, changed), start=1):
        with pytest.raises(RealtimeError):
            apply_voice_event(
                bound,
                CandidateSynchronizedEvent(
                    event_id=f"event-invalid-candidate-{index}", candidate=replacement
                ),
            )


def test_reconnect_transitions_and_event_ledger_are_bounded() -> None:
    ready = VoiceSessionState()
    for event in (
        ReconnectStartedEvent(event_id="event-reconnect-ready", automatic=True),
        ConnectionRestoredEvent(event_id="event-restored-ready"),
    ):
        with pytest.raises(RealtimeError):
            apply_voice_event(ready, event)

    saturated = VoiceSessionState(
        processed_event_ids=tuple(f"event-{index}" for index in range(2_048))
    )
    with pytest.raises(RealtimeError) as raised:
        apply_voice_event(
            saturated,
            VoiceStatusEvent(event_id="event-overflow", status="Listening"),
        )
    assert raised.value.code == "realtime_event_invalid"
