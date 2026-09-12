"""Deterministic Realtime test contexts."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from backend.realtime import CandidateBinding, RealtimeSessionContext


@pytest.fixture
def context_factory() -> Callable[..., RealtimeSessionContext]:
    def build(**updates: object) -> RealtimeSessionContext:
        values: dict[str, object] = {
            "assignment_id": "asn_realtime_test",
            "assignment_version": 7,
            "question_id": "q_photosynthesis",
            "mode": "guided",
            "phase": "answering",
            "exact_question": "How does sunlight help a plant make food?",
            "relevant_context": (
                "Use evidence from the diagram.",
                "The plant contains chlorophyll.",
            ),
            "current_candidate": None,
            "exact_text_visible": False,
            "hear_it_offered": False,
        }
        values.update(updates)
        return RealtimeSessionContext.model_validate(values, strict=True)

    return build


@pytest.fixture
def candidate() -> CandidateBinding:
    return CandidateBinding(
        candidate_id="cand_realtime_test",
        candidate_version=3,
        exact_text="Chlorophyll captures sunlight to help make glucose.",
    )
