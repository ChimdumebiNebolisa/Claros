from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend.semantic.errors import SemanticFailure
from backend.semantic.mapper import SemanticMapper
from backend.semantic.models import RephraseInput, RephraseOutput, SemanticMappingInput
from backend.semantic.prompt import build_mapping_input
from backend.semantic.provider import (
    FakeSemanticProvider,
    OpenAIResponsesSemanticProvider,
    ProviderResult,
)


class RecordingResponses:
    def __init__(self, response) -> None:
        self.response = response
        self.parse_calls = []

    async def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return self.response


@pytest.mark.asyncio
async def test_responses_parse_is_bounded_stateless_and_sanitized(
    semantic_ir, valid_mapping
) -> None:
    responses = RecordingResponses(
        SimpleNamespace(
            output_parsed=valid_mapping,
            output_text="raw provider text must not leave the adapter",
            output=[],
            status="completed",
            incomplete_details=None,
            usage=SimpleNamespace(input_tokens=321, output_tokens=45),
        )
    )
    provider = OpenAIResponsesSemanticProvider(
        SimpleNamespace(responses=responses), max_output_tokens=2_048
    )
    result = await provider.map_document(
        model="gpt-5.6-luna", request=build_mapping_input(semantic_ir)
    )

    assert result.parsed == valid_mapping
    assert result.output_text is None
    assert (result.input_tokens, result.output_tokens) == (321, 45)
    call = responses.parse_calls[0]
    assert call["model"] == "gpt-5.6-luna"
    assert call["store"] is False
    assert call["tools"] == []
    assert call["max_output_tokens"] == 2_048
    assert call["truncation"] == "disabled"
    assert call["text_format"].__name__ == "SemanticMappingOutput"


@pytest.mark.asyncio
async def test_incomplete_responses_fail_closed_even_with_parseable_text(
    semantic_ir, valid_mapping
) -> None:
    provider = FakeSemanticProvider(
        mapping_results=(
            ProviderResult(
                output_text=valid_mapping.model_dump_json(),
                incomplete=True,
            ),
        )
    )
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)
    assert raised.value.code == "semantic_malformed"


@pytest.mark.asyncio
async def test_rephrase_uses_the_same_strict_parse_boundary(semantic_ir) -> None:
    output = RephraseOutput(
        suggestion="Plants use sunlight to make food.",
        meaning_preserved=True,
    )
    responses = RecordingResponses(
        SimpleNamespace(
            output_parsed=output,
            output_text=None,
            output=[],
            status="completed",
            incomplete_details=None,
            usage=None,
        )
    )
    provider = OpenAIResponsesSemanticProvider(SimpleNamespace(responses=responses))
    result = await provider.rephrase_candidate(
        model="gpt-5.6-luna",
        request=RephraseInput(
            document_id=semantic_ir.document_id,
            question_key="q_001",
            exact_question="Why do plants need sunlight?",
            exact_candidate="Plants need light for food.",
        ),
    )

    assert result.parsed == output
    call = responses.parse_calls[0]
    assert call["text_format"] is RephraseOutput
    assert call["store"] is False
    assert call["tools"] == []


@pytest.mark.parametrize("value", [0, 16_385, True, 2.5])
def test_responses_output_bound_is_validated(value) -> None:
    with pytest.raises(ValueError, match="max_output_tokens"):
        OpenAIResponsesSemanticProvider(object(), max_output_tokens=value)


def test_provider_result_rejects_unsanitized_token_counts() -> None:
    with pytest.raises(ValueError, match="token counts"):
        ProviderResult(input_tokens=-1)


@pytest.mark.asyncio
async def test_mapper_accepts_recorded_valid_output(semantic_ir, valid_mapping) -> None:
    provider = FakeSemanticProvider(mapping_results=(ProviderResult(parsed=valid_mapping),))
    result = await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)

    assert result.questions[0].exact_prompt == "1. Why do plants need sunlight?"
    assert provider.mapping_calls[0][0] == "gpt-5.6-luna"


@pytest.mark.asyncio
async def test_mapper_accepts_strict_json_output(semantic_ir, valid_mapping) -> None:
    provider = FakeSemanticProvider(
        mapping_results=(FakeSemanticProvider.json_result(valid_mapping.model_dump(mode="json")),)
    )
    result = await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)
    assert result.questions[1].question_key == "q_002"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "code"),
    [
        (ProviderResult(refused=True), "semantic_refused"),
        (ProviderResult(output_text="{"), "semantic_malformed"),
    ],
)
async def test_refused_and_malformed_outputs_are_stable(semantic_ir, result, code) -> None:
    provider = FakeSemanticProvider(mapping_results=(result,))
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)
    assert raised.value.code == code


@pytest.mark.asyncio
async def test_provider_exception_is_sanitized(semantic_ir) -> None:
    provider = FakeSemanticProvider(mapping_results=(RuntimeError("provider detail"),))
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)
    assert raised.value.code == "semantic_provider_unavailable"
    assert "provider detail" not in str(raised.value)


class SlowProvider(FakeSemanticProvider):
    async def map_document(self, *, model, request):
        await asyncio.sleep(0.05)
        return ProviderResult()


@pytest.mark.asyncio
async def test_provider_timeout_is_stable(semantic_ir) -> None:
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(SlowProvider(), "gpt-5.6-luna", timeout_seconds=0.001).map_document(
            semantic_ir
        )
    assert raised.value.code == "semantic_timeout"


@pytest.mark.asyncio
async def test_mapping_input_validation_is_a_stable_failure(monkeypatch, semantic_ir) -> None:
    def invalid_mapping_input(_ir):
        return SemanticMappingInput.model_validate({})

    monkeypatch.setattr("backend.semantic.mapper.build_mapping_input", invalid_mapping_input)
    provider = FakeSemanticProvider()
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").map_document(semantic_ir)
    assert raised.value.code == "semantic_input_invalid"
    assert provider.mapping_calls == []


@pytest.mark.asyncio
async def test_rephrase_input_validation_is_a_stable_failure(semantic_ir) -> None:
    provider = FakeSemanticProvider()
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").rephrase(
            ir=semantic_ir,
            question_key="q_001",
            exact_question="Why?",
            exact_candidate="",
        )
    assert raised.value.code == "semantic_input_invalid"
    assert provider.rephrase_calls == []


@pytest.mark.asyncio
async def test_safe_rephrase_preserves_exact_original(semantic_ir) -> None:
    exact = "  Plants use sunlight to make glucose — food.  "
    provider = FakeSemanticProvider(
        rephrase_results=(
            ProviderResult(
                parsed=RephraseOutput(
                    suggestion="Plants use sunlight to make glucose, which is food.",
                    meaning_preserved=True,
                    factual_changes=(),
                    unsupported_claims=(),
                )
            ),
        )
    )
    result = await SemanticMapper(provider, "gpt-5.6-luna").rephrase(
        ir=semantic_ir,
        question_key="q_001",
        exact_question="Why do plants need sunlight?",
        exact_candidate=exact,
    )

    assert result.exact_original == exact
    assert result.exact_suggestion == "Plants use sunlight to make glucose, which is food."
    assert result.factual_delta_safe is True


@pytest.mark.asyncio
async def test_safe_rephrase_accepts_strict_json(semantic_ir) -> None:
    provider = FakeSemanticProvider(
        rephrase_results=(
            FakeSemanticProvider.json_result(
                RephraseOutput(
                    suggestion="Plants use sunlight to make food.",
                    meaning_preserved=True,
                ).model_dump(mode="json")
            ),
        )
    )
    result = await SemanticMapper(provider, "gpt-5.6-luna").rephrase(
        ir=semantic_ir,
        question_key="q_001",
        exact_question="Why do plants need sunlight?",
        exact_candidate="Plants need sunlight to make food.",
    )
    assert result.exact_suggestion == "Plants use sunlight to make food."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output",
    [
        RephraseOutput(
            suggestion="Plants also release oxygen.",
            meaning_preserved=False,
            factual_changes=("Added oxygen claim",),
            unsupported_claims=("Plants release oxygen",),
        ),
        RephraseOutput(
            suggestion="Plants use sunlight.",
            meaning_preserved=True,
            factual_changes=("Removed glucose",),
        ),
    ],
)
async def test_unsafe_rephrase_never_replaces_candidate(semantic_ir, output) -> None:
    provider = FakeSemanticProvider(rephrase_results=(ProviderResult(parsed=output),))
    with pytest.raises(SemanticFailure) as raised:
        await SemanticMapper(provider, "gpt-5.6-luna").rephrase(
            ir=semantic_ir,
            question_key="q_001",
            exact_question="Why?",
            exact_candidate="Original",
        )
    assert raised.value.code == "semantic_unsafe_rephrase"
