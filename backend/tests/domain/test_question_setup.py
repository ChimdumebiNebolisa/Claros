from __future__ import annotations

import pytest

from backend.domain import (
    CandidateOrigin,
    DirectTypedInteraction,
    InvalidQuestionSetup,
    QuestionDefinition,
    QuestionSetupLocked,
    QuestionSetupProvenance,
    QuestionSetupUnverified,
    accept_question_setup,
    replace_candidate,
    replace_question_setup,
    reset_question_setup,
)
from backend.tests.domain.conftest import NOW


def _pending_setup(manifest_factory, *, question_count: int = 2):
    manifest = manifest_factory(question_count=question_count)
    detected = tuple(QuestionDefinition.from_state(item) for item in manifest.questions)
    return manifest.model_copy(
        update={
            "detected_questions": detected,
            "question_setup_verified": False,
        }
    )


def test_fast_path_accept_preserves_detected_mapping(manifest_factory) -> None:
    manifest = _pending_setup(manifest_factory)

    accepted = accept_question_setup(
        manifest,
        assignment_version=manifest.version,
        now=NOW,
    )

    assert accepted.version == manifest.version + 1
    assert accepted.question_setup_verified is True
    assert accepted.question_setup_provenance == QuestionSetupProvenance.DETECTED
    assert accepted.questions == manifest.questions
    assert accepted.detected_questions == manifest.detected_questions


def test_reorder_preserves_stable_identity_and_reset_restores_detection(
    manifest_factory,
) -> None:
    manifest = _pending_setup(manifest_factory)
    first, second = manifest.questions
    reordered = (
        second.model_copy(update={"index": 1, "display_identifier": "1"}),
        first.model_copy(update={"index": 2, "display_identifier": "2"}),
    )

    corrected = replace_question_setup(
        manifest,
        questions=reordered,
        assignment_version=manifest.version,
        provenance=QuestionSetupProvenance.STUDENT_CORRECTED,
        now=NOW,
    )

    assert [item.question_id for item in corrected.questions] == ["q_2", "q_1"]
    assert corrected.question_setup_verified is False
    assert corrected.question_setup_provenance == QuestionSetupProvenance.STUDENT_CORRECTED

    restored = reset_question_setup(
        corrected,
        assignment_version=corrected.version,
        now=NOW,
    )

    assert [item.question_id for item in restored.questions] == ["q_1", "q_2"]
    assert restored.questions == tuple(item.to_state() for item in restored.detected_questions)
    assert restored.question_setup_provenance == QuestionSetupProvenance.DETECTED


def test_invalid_order_and_empty_setup_are_rejected(manifest_factory) -> None:
    manifest = _pending_setup(manifest_factory)

    with pytest.raises(InvalidQuestionSetup):
        replace_question_setup(
            manifest,
            questions=(),
            assignment_version=manifest.version,
            provenance=QuestionSetupProvenance.STUDENT_CORRECTED,
            now=NOW,
        )

    with pytest.raises(InvalidQuestionSetup):
        replace_question_setup(
            manifest,
            questions=tuple(reversed(manifest.questions)),
            assignment_version=manifest.version,
            provenance=QuestionSetupProvenance.STUDENT_CORRECTED,
            now=NOW,
        )


def test_unverified_setup_cannot_create_answer_state(manifest_factory) -> None:
    manifest = _pending_setup(manifest_factory)

    with pytest.raises(QuestionSetupUnverified):
        replace_candidate(
            manifest,
            question_id="q_1",
            assignment_version=manifest.version,
            exact_text="Plants need sunlight.",
            origin=CandidateOrigin.STUDENT_VERBATIM,
            interaction=DirectTypedInteraction(),
            now=NOW,
        )


def test_setup_changes_lock_after_candidate_state(manifest_factory) -> None:
    manifest, _candidate = replace_candidate(
        manifest_factory(question_count=2),
        question_id="q_1",
        assignment_version=1,
        exact_text="Plants need sunlight.",
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
    )
    detected = tuple(QuestionDefinition.from_state(item) for item in manifest.questions)
    manifest = manifest.model_copy(update={"detected_questions": detected})

    with pytest.raises(QuestionSetupLocked):
        reset_question_setup(
            manifest,
            assignment_version=manifest.version,
            now=NOW,
        )
