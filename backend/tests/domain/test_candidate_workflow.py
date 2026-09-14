from __future__ import annotations

from datetime import timedelta

import pytest

from backend.domain.errors import (
    AssignmentVersionConflict,
    InvalidCandidateOrigin,
)
from backend.domain.models import (
    CandidateOrigin,
    DirectTypedInteraction,
    DirectVoiceInteraction,
    GuidedFinalInteraction,
    RephraseRecord,
    SelectedRephraseInteraction,
    StudentAttribution,
    StudentEditInteraction,
)
from backend.domain.workflow import record_rephrase, replace_candidate
from backend.tests.domain.conftest import NOW


@pytest.mark.parametrize(
    ("origin", "interaction"),
    [
        (CandidateOrigin.STUDENT_VERBATIM, DirectTypedInteraction()),
        (
            CandidateOrigin.STUDENT_VERBATIM,
            DirectVoiceInteraction(
                realtime_session_id="rt_direct",
                source_turn_ids=("turn_1",),
                normalization="none",
            ),
        ),
        (
            CandidateOrigin.STUDENT_NORMALIZED,
            DirectVoiceInteraction(
                realtime_session_id="rt_direct",
                source_turn_ids=("turn_1",),
                normalization="punctuation_only",
            ),
        ),
        (
            CandidateOrigin.STUDENT_AFTER_GUIDANCE,
            GuidedFinalInteraction(
                realtime_session_id="rt_guided",
                source_turn_ids=("turn_1", "turn_2"),
                input="typed",
            ),
        ),
    ],
)
def test_interaction_path_derives_allowed_origin(manifest_factory, origin, interaction) -> None:
    updated, candidate = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text="My exact answer.",
        origin=origin,
        interaction=interaction,
        now=NOW,
        candidate_id_factory=lambda: "cand_path",
    )
    assert updated.version == 2
    assert candidate.origin == origin


def test_forged_origin_preserves_previous_state(manifest_factory) -> None:
    manifest = manifest_factory()
    with pytest.raises(InvalidCandidateOrigin):
        replace_candidate(
            manifest,
            question_id="q_1",
            assignment_version=1,
            exact_text="Model-attributed text",
            origin=CandidateOrigin.CLAROS_REPHRASE,
            interaction=DirectTypedInteraction(),
            now=NOW,
        )
    assert manifest.version == 1
    assert manifest.questions[0].current_candidate is None


def test_exact_unicode_and_whitespace_are_not_normalized(manifest_factory) -> None:
    exact = "  José\N{RIGHT SINGLE QUOTATION MARK}s Δ result\N{EM DASH}42 °C.\nSecond line.  "
    updated, candidate = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text=exact,
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
        candidate_id_factory=lambda: "cand_unicode",
    )
    assert candidate.exact_text == exact
    assert updated.questions[0].current_candidate.exact_text == exact
    assert candidate.attribution == StudentAttribution.YOUR_WORDS


def test_stale_assignment_version_has_no_side_effect(manifest_factory) -> None:
    manifest = manifest_factory(version=4)
    with pytest.raises(AssignmentVersionConflict) as caught:
        replace_candidate(
            manifest,
            question_id="q_1",
            assignment_version=3,
            exact_text="Stale",
            origin=CandidateOrigin.STUDENT_VERBATIM,
            interaction=DirectTypedInteraction(),
            now=NOW,
        )
    assert caught.value.current_version == 4
    assert manifest.questions[0].candidate_sequence == 0


def test_student_edit_must_reference_current_candidate(manifest_factory) -> None:
    first_manifest, first = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text="First",
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
        candidate_id_factory=lambda: "cand_first",
    )
    with pytest.raises(InvalidCandidateOrigin):
        replace_candidate(
            first_manifest,
            question_id="q_1",
            assignment_version=2,
            exact_text="Edited",
            origin=CandidateOrigin.STUDENT_EDITED,
            interaction=StudentEditInteraction(
                prior_candidate_id="cand_other", prior_candidate_version=first.candidate_version
            ),
            now=NOW + timedelta(seconds=1),
        )

    updated, edited = replace_candidate(
        first_manifest,
        question_id="q_1",
        assignment_version=2,
        exact_text="Edited",
        origin=CandidateOrigin.STUDENT_EDITED,
        interaction=StudentEditInteraction(
            prior_candidate_id=first.candidate_id,
            prior_candidate_version=first.candidate_version,
        ),
        now=NOW + timedelta(seconds=1),
        candidate_id_factory=lambda: "cand_edited",
    )
    assert updated.version == 3
    assert edited.origin == CandidateOrigin.STUDENT_EDITED
    assert edited.attribution == StudentAttribution.YOUR_WORDS


def test_selected_rephrase_requires_matching_server_record(manifest_factory) -> None:
    manifest, original = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text="Plants need sunlight to make food.",
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
        candidate_id_factory=lambda: "cand_original",
    )
    question = manifest.questions[0].model_copy(
        update={
            "rephrases": (
                RephraseRecord(
                    rephrase_id="rph_one",
                    original_candidate_id="cand_original",
                    original_candidate_version=original.candidate_version,
                    suggestion_candidate_id="cand_suggestion",
                    suggestion_candidate_version=2,
                    suggestion_text="Plants use sunlight to make food.",
                    factual_delta_safe=True,
                ),
            )
        }
    )
    manifest = manifest.model_copy(update={"questions": (question,)})
    interaction = SelectedRephraseInteraction(
        rephrase_id="rph_one", suggestion_candidate_id="cand_suggestion"
    )
    updated, candidate = replace_candidate(
        manifest,
        question_id="q_1",
        assignment_version=manifest.version,
        exact_text="Plants use sunlight to make food.",
        origin=CandidateOrigin.CLAROS_REPHRASE,
        interaction=interaction,
        now=NOW,
        candidate_id_factory=lambda: "cand_selected",
    )
    assert updated.version == 3
    assert candidate.attribution == StudentAttribution.SUGGESTED_WORDING

    with pytest.raises(InvalidCandidateOrigin):
        replace_candidate(
            manifest,
            question_id="q_1",
            assignment_version=manifest.version,
            exact_text="A changed suggestion.",
            origin=CandidateOrigin.CLAROS_REPHRASE,
            interaction=interaction,
            now=NOW,
        )


def test_selected_rephrase_rejects_a_suggestion_after_the_original_changes(
    manifest_factory,
) -> None:
    with_candidate, candidate = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text="Plants need sunlight to make food.",
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
        candidate_id_factory=lambda: "cand_original",
    )
    with_rephrase, record = record_rephrase(
        with_candidate,
        question_id="q_1",
        assignment_version=with_candidate.version,
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.candidate_version,
        suggestion_text="Plants use sunlight to make food.",
        now=NOW,
        rephrase_id_factory=lambda: "rph_stale",
        candidate_id_factory=lambda: "cand_suggestion",
    )
    edited, _ = replace_candidate(
        with_rephrase,
        question_id="q_1",
        assignment_version=with_rephrase.version,
        exact_text="Plants use light energy to make food.",
        origin=CandidateOrigin.STUDENT_EDITED,
        interaction=StudentEditInteraction(
            prior_candidate_id=candidate.candidate_id,
            prior_candidate_version=candidate.candidate_version,
        ),
        now=NOW + timedelta(seconds=1),
        candidate_id_factory=lambda: "cand_edited",
    )

    with pytest.raises(InvalidCandidateOrigin):
        replace_candidate(
            edited,
            question_id="q_1",
            assignment_version=edited.version,
            exact_text=record.suggestion_text,
            origin=CandidateOrigin.CLAROS_REPHRASE,
            interaction=SelectedRephraseInteraction(
                rephrase_id=record.rephrase_id,
                suggestion_candidate_id=record.suggestion_candidate_id,
            ),
            now=NOW + timedelta(seconds=2),
        )


def test_record_rephrase_preserves_current_candidate_and_requires_explicit_selection(
    manifest_factory,
) -> None:
    with_candidate, candidate = replace_candidate(
        manifest_factory(),
        question_id="q_1",
        assignment_version=1,
        exact_text="Plants need sunlight to make food.",
        origin=CandidateOrigin.STUDENT_VERBATIM,
        interaction=DirectTypedInteraction(),
        now=NOW,
        candidate_id_factory=lambda: "cand_original",
    )

    updated, record = record_rephrase(
        with_candidate,
        question_id="q_1",
        assignment_version=with_candidate.version,
        candidate_id=candidate.candidate_id,
        candidate_version=candidate.candidate_version,
        suggestion_text="Plants use sunlight to produce food.",
        now=NOW,
        rephrase_id_factory=lambda: "rph_recorded",
        candidate_id_factory=lambda: "cand_suggestion",
    )

    question = updated.questions[0]
    assert updated.version == 3
    assert question.current_candidate == candidate
    assert question.candidate_sequence == candidate.candidate_version
    assert question.rephrases == (record,)
    assert record.original_candidate_id == candidate.candidate_id
    assert record.suggestion_candidate_version == candidate.candidate_version + 1
    assert record.factual_delta_safe is True
