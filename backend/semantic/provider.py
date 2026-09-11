"""Responses API boundary and deterministic semantic provider fakes."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Protocol, TypeVar

from backend.semantic.models import (
    RephraseInput,
    RephraseOutput,
    SemanticMappingInput,
    SemanticMappingOutput,
)
from backend.semantic.prompt import mapping_messages, rephrase_messages

OutputT = TypeVar("OutputT", SemanticMappingOutput, RephraseOutput)
DEFAULT_MAX_OUTPUT_TOKENS = 8_192
MAX_OUTPUT_TOKENS = 16_384


@dataclass(frozen=True, slots=True)
class ProviderResult:
    """Sanitized provider result; raw provider payloads never leave this adapter."""

    parsed: object | None = None
    output_text: str | None = None
    refused: bool = False
    incomplete: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError("provider token counts must be non-negative integers")


class SemanticProvider(Protocol):
    async def map_document(
        self, *, model: str, request: SemanticMappingInput
    ) -> ProviderResult: ...

    async def rephrase_candidate(self, *, model: str, request: RephraseInput) -> ProviderResult: ...


def _has_refusal(response: object) -> bool:
    if getattr(response, "refusal", None):
        return True
    for item in getattr(response, "output", ()) or ():
        for content in getattr(item, "content", ()) or ():
            if getattr(content, "type", None) == "refusal":
                return True
    return False


def _usage_count(response: object, name: str) -> int | None:
    usage = getattr(response, "usage", None)
    value = getattr(usage, name, None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


class OpenAIResponsesSemanticProvider:
    """Narrow injected ``AsyncOpenAI.responses`` integration.

    The SDK's typed ``parse`` helper owns strict-schema conversion. Provider
    storage and tools are disabled on every request, and only sanitized token
    counts leave this adapter alongside the parsed result.
    """

    def __init__(
        self,
        client: object,
        *,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> None:
        if (
            not isinstance(max_output_tokens, int)
            or isinstance(max_output_tokens, bool)
            or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS
        ):
            raise ValueError(f"max_output_tokens must be between 1 and {MAX_OUTPUT_TOKENS}")
        self._client = client
        self._max_output_tokens = max_output_tokens

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        *,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> OpenAIResponsesSemanticProvider:
        # Kept lazy so deterministic tests and document processing do not need
        # the provider SDK. Production dependency wiring owns installation.
        from openai import AsyncOpenAI

        return cls(AsyncOpenAI(api_key=api_key), max_output_tokens=max_output_tokens)

    async def _request(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        output_type: type[OutputT],
    ) -> ProviderResult:
        responses = self._client.responses
        response = await responses.parse(
            model=model,
            input=messages,
            text_format=output_type,
            store=False,
            tools=[],
            max_output_tokens=self._max_output_tokens,
            truncation="disabled",
        )
        return ProviderResult(
            parsed=getattr(response, "output_parsed", None),
            output_text=getattr(response, "output_text", None),
            refused=_has_refusal(response),
            incomplete=(
                getattr(response, "status", None) == "incomplete"
                or getattr(response, "incomplete_details", None) is not None
            ),
            input_tokens=_usage_count(response, "input_tokens"),
            output_tokens=_usage_count(response, "output_tokens"),
        )

    async def map_document(self, *, model: str, request: SemanticMappingInput) -> ProviderResult:
        return await self._request(
            model=model,
            messages=mapping_messages(request),
            output_type=SemanticMappingOutput,
        )

    async def rephrase_candidate(self, *, model: str, request: RephraseInput) -> ProviderResult:
        return await self._request(
            model=model,
            messages=rephrase_messages(request),
            output_type=RephraseOutput,
        )


class FakeSemanticProvider:
    """FIFO fake used by recorded evaluations and service tests."""

    def __init__(
        self,
        *,
        mapping_results: tuple[ProviderResult | Exception, ...] = (),
        rephrase_results: tuple[ProviderResult | Exception, ...] = (),
    ) -> None:
        self.mapping_results = deque(mapping_results)
        self.rephrase_results = deque(rephrase_results)
        self.mapping_calls: list[tuple[str, SemanticMappingInput]] = []
        self.rephrase_calls: list[tuple[str, RephraseInput]] = []

    @staticmethod
    def json_result(value: object) -> ProviderResult:
        return ProviderResult(
            output_text=json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )

    @staticmethod
    def _take(queue: deque[ProviderResult | Exception]) -> ProviderResult:
        if not queue:
            raise RuntimeError("fake semantic provider result queue is empty")
        result = queue.popleft()
        if isinstance(result, Exception):
            raise result
        return result

    async def map_document(self, *, model: str, request: SemanticMappingInput) -> ProviderResult:
        self.mapping_calls.append((model, request))
        return self._take(self.mapping_results)

    async def rephrase_candidate(self, *, model: str, request: RephraseInput) -> ProviderResult:
        self.rephrase_calls.append((model, request))
        return self._take(self.rephrase_results)
