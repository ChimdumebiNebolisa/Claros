"""Provider-independent semantic mapping and rephrasing orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass

from pydantic import ValidationError

from backend.document.models import PhysicalDocumentIR
from backend.semantic.errors import SemanticFailure, semantic_failure
from backend.semantic.models import (
    RephraseInput,
    RephraseOutput,
    SafeRephrase,
    SemanticMappingOutput,
    ValidatedMapping,
)
from backend.semantic.prompt import build_mapping_input
from backend.semantic.provider import ProviderResult, SemanticProvider
from backend.semantic.validation import (
    MappingExpectations,
    parse_mapping_json,
    parse_mapping_payload,
    validate_mapping,
    validate_rephrase,
)


def _mapping_output(result: ProviderResult) -> SemanticMappingOutput:
    if result.refused:
        semantic_failure("semantic_refused")
    if result.incomplete:
        semantic_failure("semantic_malformed")
    if isinstance(result.parsed, SemanticMappingOutput):
        return result.parsed
    if result.parsed is not None:
        return parse_mapping_payload(result.parsed)
    if result.output_text is None:
        semantic_failure("semantic_malformed")
    return parse_mapping_json(result.output_text)


def _rephrase_output(result: ProviderResult) -> RephraseOutput:
    if result.refused:
        semantic_failure("semantic_refused")
    if result.incomplete:
        semantic_failure("semantic_malformed")
    if isinstance(result.parsed, RephraseOutput):
        return result.parsed
    try:
        if result.parsed is not None:
            return RephraseOutput.model_validate(result.parsed)
        if result.output_text is None:
            semantic_failure("semantic_malformed")
        return RephraseOutput.model_validate_json(result.output_text)
    except (ValidationError, TypeError, ValueError):
        semantic_failure("semantic_malformed")


@dataclass(slots=True)
class SemanticMapper:
    provider: SemanticProvider
    model: str
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    async def _provider_call(self, awaitable: Awaitable[ProviderResult]) -> ProviderResult:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await awaitable
        except TimeoutError:
            semantic_failure("semantic_timeout")
        except SemanticFailure:
            raise
        except Exception:
            semantic_failure("semantic_provider_unavailable")

    async def map_document(
        self,
        ir: PhysicalDocumentIR,
        *,
        expectations: MappingExpectations | None = None,
    ) -> ValidatedMapping:
        try:
            request = build_mapping_input(ir)
        except (ValidationError, TypeError, ValueError):
            semantic_failure("semantic_input_invalid")
        result = await self._provider_call(
            self.provider.map_document(model=self.model, request=request)
        )
        return validate_mapping(_mapping_output(result), ir, expectations=expectations)

    async def rephrase(
        self,
        *,
        ir: PhysicalDocumentIR,
        question_key: str,
        exact_question: str,
        exact_candidate: str,
        exact_allowed_context: str | None = None,
    ) -> SafeRephrase:
        try:
            request = RephraseInput(
                document_id=ir.document_id,
                question_key=question_key,
                exact_question=exact_question,
                exact_candidate=exact_candidate,
                exact_allowed_context=exact_allowed_context,
            )
        except (ValidationError, TypeError, ValueError):
            semantic_failure("semantic_input_invalid")
        result = await self._provider_call(
            self.provider.rephrase_candidate(model=self.model, request=request)
        )
        return validate_rephrase(
            exact_original=exact_candidate,
            provider_output=_rephrase_output(result),
        )
