from __future__ import annotations

from dataclasses import replace

import pytest

from backend.semantic.benchmark import (
    MODEL_ORDER,
    GoldSemanticCase,
    RecordedSemanticRun,
    SemanticReplayCase,
    build_evaluation_fingerprint,
    replay_semantic_model,
    select_semantic_model,
)
from backend.semantic.errors import SemanticFailure
from backend.semantic.provider import FakeSemanticProvider, ProviderResult

FINGERPRINT = build_evaluation_fingerprint(b"recorded semantic corpus v1")
GOLD = (
    GoldSemanticCase("biology", ("Why do plants need sunlight?",)),
    GoldSemanticCase("ambiguous", expected_failure_code="semantic_ambiguous"),
)


def runs_for(
    model: str,
    *,
    cases: tuple[GoldSemanticCase, ...] = GOLD,
    wrong_case: str | None = None,
    invalid_ids: int = 0,
    latency_ms: int = 400,
    mode: str = "recorded",
    fingerprint=FINGERPRINT,
):
    records = []
    for case in cases:
        for run in (1, 2, 3):
            if case.expected_failure_code is not None:
                exact_questions = ()
                failure_code = (
                    "semantic_timeout" if case.case_id == wrong_case else case.expected_failure_code
                )
            else:
                exact_questions = ("wrong",) if case.case_id == wrong_case else case.exact_questions
                failure_code = None
            records.append(
                RecordedSemanticRun(
                    model=model,
                    case_id=case.case_id,
                    run=run,
                    exact_questions=exact_questions,
                    invalid_id_count=invalid_ids,
                    latency_ms=latency_ms,
                    mode=mode,
                    fingerprint=fingerprint,
                    failure_code=failure_code,
                    input_tokens=100,
                    output_tokens=20,
                    estimated_cost_usd_micros=7,
                )
            )
    return tuple(records)


def test_model_order_is_frozen() -> None:
    assert MODEL_ORDER == ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")


def test_selects_first_model_passing_positive_and_expected_negative_cases() -> None:
    runs = (*runs_for("gpt-5.6-luna", wrong_case="biology"), *runs_for("gpt-5.6-terra"))
    decision = select_semantic_model(
        cases=GOLD,
        runs=runs,
        mode="recorded",
        fingerprint=FINGERPRINT,
        latency_threshold_ms=1_000,
    )

    assert decision.selected_model == "gpt-5.6-terra"
    assert [item.model for item in decision.evidence] == [
        "gpt-5.6-luna",
        "gpt-5.6-terra",
    ]
    assert decision.evidence[0].correctness_percent < 100
    assert decision.evidence[1].accepted is True
    assert decision.evidence[1].p95_latency_ms == 400
    assert decision.evidence[1].total_input_tokens == 600
    assert decision.evidence[1].total_output_tokens == 120
    assert decision.evidence[1].estimated_cost_usd_micros == 42


@pytest.mark.parametrize(
    "runs",
    [
        runs_for("gpt-5.6-luna", invalid_ids=1),
        runs_for("gpt-5.6-luna", latency_ms=1_001),
        runs_for("gpt-5.6-luna")[:-1],
        runs_for("gpt-5.6-luna", wrong_case="ambiguous"),
        runs_for(
            "gpt-5.6-luna",
            fingerprint=replace(FINGERPRINT, corpus_sha256="f" * 64),
        ),
    ],
)
def test_invalid_evidence_blocks_selection(runs) -> None:
    with pytest.raises(SemanticFailure) as raised:
        select_semantic_model(
            cases=GOLD,
            runs=runs,
            mode="recorded",
            fingerprint=FINGERPRINT,
            latency_threshold_ms=1_000,
        )
    assert raised.value.code == "semantic_model_gate_failed"
    assert raised.value.recoverable is False


def test_live_selection_does_not_reuse_recorded_results() -> None:
    runs = (
        *runs_for("gpt-5.6-luna", mode="recorded"),
        *runs_for("gpt-5.6-luna", mode="live", wrong_case="biology"),
        *runs_for("gpt-5.6-terra", mode="live"),
    )
    decision = select_semantic_model(
        cases=GOLD,
        runs=runs,
        mode="live",
        fingerprint=FINGERPRINT,
        latency_threshold_ms=1_000,
    )
    assert decision.mode == "live"
    assert decision.selected_model == "gpt-5.6-terra"


def test_acceptance_uses_p95_instead_of_worst_latency() -> None:
    cases = tuple(
        GoldSemanticCase(f"case-{index:02d}", (f"Question {index}?",)) for index in range(20)
    )
    runs = list(runs_for("gpt-5.6-luna", cases=cases))
    runs[0] = replace(runs[0], latency_ms=9_999)
    decision = select_semantic_model(
        cases=cases,
        runs=tuple(runs),
        mode="recorded",
        fingerprint=FINGERPRINT,
        latency_threshold_ms=500,
    )
    assert decision.selected_model == "gpt-5.6-luna"
    assert decision.evidence[0].p95_latency_ms == 400


def test_fingerprint_hashes_corpus_prompt_and_schemas() -> None:
    repeat = build_evaluation_fingerprint(b"recorded semantic corpus v1")
    changed = build_evaluation_fingerprint(b"recorded semantic corpus v2")

    assert repeat == FINGERPRINT
    assert changed.corpus_sha256 != FINGERPRINT.corpus_sha256
    assert changed.prompt_sha256 == FINGERPRINT.prompt_sha256
    assert changed.schema_sha256 == FINGERPRINT.schema_sha256
    assert all(
        len(value) == 64
        for value in (repeat.corpus_sha256, repeat.prompt_sha256, repeat.schema_sha256)
    )


def test_current_gate_rejects_a_stale_prompt_or_schema_fingerprint() -> None:
    stale = replace(FINGERPRINT, prompt_sha256="f" * 64)
    with pytest.raises(ValueError, match="fingerprint is stale"):
        select_semantic_model(
            cases=GOLD,
            runs=runs_for("gpt-5.6-luna", fingerprint=stale),
            mode="recorded",
            fingerprint=stale,
            latency_threshold_ms=1_000,
        )


@pytest.mark.asyncio
async def test_replay_runs_real_mapper_and_records_only_sanitized_observations(
    semantic_ir, valid_mapping
) -> None:
    unknown_question = valid_mapping.questions[0].model_copy(
        update={"prompt_block_ids": ("blk_" + "f" * 32,)}
    )
    unknown_mapping = valid_mapping.model_copy(update={"questions": (unknown_question,)})
    provider = FakeSemanticProvider(
        mapping_results=(
            ProviderResult(parsed=valid_mapping, input_tokens=80, output_tokens=20),
            ProviderResult(parsed=unknown_mapping, input_tokens=70, output_tokens=10),
        )
    )
    cases = (
        SemanticReplayCase(
            GoldSemanticCase(
                "valid",
                (
                    "1. Why do plants need sunlight?",
                    "2. How does sunlight help a plant make food?",
                ),
            ),
            semantic_ir,
        ),
        SemanticReplayCase(
            GoldSemanticCase("unknown", expected_failure_code="semantic_unknown_id"),
            semantic_ir,
        ),
    )
    clock_values = iter((0, 10_000_000, 20_000_000, 35_000_000))

    records = await replay_semantic_model(
        model="gpt-5.6-luna",
        run=1,
        mode="live",
        fingerprint=FINGERPRINT,
        cases=cases,
        provider=provider,
        cost_estimator=lambda _model, input_tokens, output_tokens: input_tokens + output_tokens,
        clock_ns=lambda: next(clock_values),
    )

    assert records[0].exact_questions == cases[0].gold.exact_questions
    assert records[0].latency_ms == 10
    assert records[0].estimated_cost_usd_micros == 100
    assert records[1].failure_code == "semantic_unknown_id"
    assert records[1].invalid_id_count == 1
    assert records[1].latency_ms == 15
    assert [call[0] for call in provider.mapping_calls] == [
        "gpt-5.6-luna",
        "gpt-5.6-luna",
    ]
    assert not hasattr(records[0], "output_text")
