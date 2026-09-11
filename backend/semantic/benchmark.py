"""Deterministic recorded/live semantic-model evaluation and selection."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from backend.document.models import PhysicalDocumentIR
from backend.semantic.errors import SemanticFailure, SemanticFailureCode, semantic_failure
from backend.semantic.mapper import SemanticMapper
from backend.semantic.models import (
    RephraseInput,
    RephraseOutput,
    SemanticMappingInput,
    SemanticMappingOutput,
)
from backend.semantic.prompt import mapping_prompt_prelude
from backend.semantic.provider import ProviderResult, SemanticProvider
from backend.semantic.validation import MappingExpectations

MODEL_ORDER = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
REQUIRED_RUNS = (1, 2, 3)
EvaluationMode = Literal["recorded", "live"]
CostEstimator = Callable[[str, int, int], int | None]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


@dataclass(frozen=True, slots=True)
class EvaluationFingerprint:
    corpus_sha256: str
    prompt_sha256: str
    schema_sha256: str

    def __post_init__(self) -> None:
        if not all(
            _is_sha256(value)
            for value in (self.corpus_sha256, self.prompt_sha256, self.schema_sha256)
        ):
            raise ValueError("evaluation fingerprints must be lowercase SHA-256 digests")


def build_evaluation_fingerprint(corpus_payload: bytes) -> EvaluationFingerprint:
    """Hash the exact corpus bytes and current prompt/schema contracts."""

    if not isinstance(corpus_payload, bytes):
        raise TypeError("corpus_payload must be bytes")
    prompt_payload = mapping_prompt_prelude()
    schema_payload = {
        "mapping_input": SemanticMappingInput.model_json_schema(),
        "mapping_output": SemanticMappingOutput.model_json_schema(),
        "rephrase_input": RephraseInput.model_json_schema(),
        "rephrase_output": RephraseOutput.model_json_schema(),
    }
    return EvaluationFingerprint(
        corpus_sha256=_sha256(corpus_payload),
        prompt_sha256=_sha256(_canonical_json_bytes(prompt_payload)),
        schema_sha256=_sha256(_canonical_json_bytes(schema_payload)),
    )


def _assert_current_contract(fingerprint: EvaluationFingerprint) -> None:
    current = build_evaluation_fingerprint(b"")
    if (
        fingerprint.prompt_sha256 != current.prompt_sha256
        or fingerprint.schema_sha256 != current.schema_sha256
    ):
        raise ValueError("evaluation prompt or schema fingerprint is stale")


@dataclass(frozen=True, slots=True)
class GoldSemanticCase:
    case_id: str
    exact_questions: tuple[str, ...] = ()
    expected_failure_code: SemanticFailureCode | None = None
    required: bool = True

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("gold cases require an identity")
        if bool(self.exact_questions) == bool(self.expected_failure_code):
            raise ValueError("gold cases require exact questions or one expected failure")


@dataclass(frozen=True, slots=True)
class SemanticReplayCase:
    gold: GoldSemanticCase
    ir: PhysicalDocumentIR
    expectations: MappingExpectations | None = None


@dataclass(frozen=True, slots=True)
class RecordedSemanticRun:
    model: str
    case_id: str
    run: int
    exact_questions: tuple[str, ...]
    invalid_id_count: int
    latency_ms: int
    mode: EvaluationMode
    fingerprint: EvaluationFingerprint
    failure_code: SemanticFailureCode | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd_micros: int | None = None

    def __post_init__(self) -> None:
        if self.model not in MODEL_ORDER:
            raise ValueError("recorded run uses an unsupported model")
        if not self.case_id or self.run not in REQUIRED_RUNS:
            raise ValueError("recorded run identity is invalid")
        if self.mode not in {"recorded", "live"}:
            raise ValueError("recorded run mode is invalid")
        metrics = (
            self.invalid_id_count,
            self.latency_ms,
            self.input_tokens,
            self.output_tokens,
            self.estimated_cost_usd_micros,
        )
        if any(
            value is not None
            and (not isinstance(value, int) or isinstance(value, bool) or value < 0)
            for value in metrics
        ):
            raise ValueError("recorded metrics must be non-negative integers")
        if self.failure_code is not None and self.exact_questions:
            raise ValueError("failed runs cannot record reconstructed questions")


@dataclass(frozen=True, slots=True)
class ModelEvidence:
    model: str
    complete_three_runs: bool
    fingerprints_match: bool
    correctness_percent: int
    invalid_id_count: int
    p95_latency_ms: int | None
    total_input_tokens: int | None
    total_output_tokens: int | None
    estimated_cost_usd_micros: int | None
    accepted: bool


@dataclass(frozen=True, slots=True)
class BenchmarkDecision:
    selected_model: str
    mode: EvaluationMode
    latency_threshold_ms: int
    fingerprint: EvaluationFingerprint
    evidence: tuple[ModelEvidence, ...]


def _p95(values: tuple[int, ...]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def _complete_sum(values: tuple[int | None, ...]) -> int | None:
    return None if any(value is None for value in values) else sum(value or 0 for value in values)


def _run_is_correct(run: RecordedSemanticRun, case: GoldSemanticCase) -> bool:
    if case.expected_failure_code is not None:
        return run.failure_code == case.expected_failure_code and not run.exact_questions
    return run.failure_code is None and run.exact_questions == case.exact_questions


def _model_evidence(
    model: str,
    *,
    cases: tuple[GoldSemanticCase, ...],
    runs: tuple[RecordedSemanticRun, ...],
    mode: EvaluationMode,
    fingerprint: EvaluationFingerprint,
    latency_threshold_ms: int,
) -> ModelEvidence:
    required_cases = tuple(case for case in cases if case.required)
    required_ids = {case.case_id for case in required_cases}
    expected_slots = {(case.case_id, run) for case in required_cases for run in REQUIRED_RUNS}
    relevant = tuple(
        run
        for run in runs
        if run.model == model and run.mode == mode and run.case_id in required_ids
    )
    seen_slots = {(run.case_id, run.run) for run in relevant}
    complete = seen_slots == expected_slots and len(relevant) == len(expected_slots)
    fingerprints_match = bool(relevant) and all(run.fingerprint == fingerprint for run in relevant)
    expected_by_id = {case.case_id: case for case in required_cases}
    correct = sum(_run_is_correct(run, expected_by_id[run.case_id]) for run in relevant)
    denominator = len(expected_slots)
    correctness = (100 * correct // denominator) if denominator else 0
    invalid_ids = sum(run.invalid_id_count for run in relevant)
    p95_latency = _p95(tuple(run.latency_ms for run in relevant))
    total_input_tokens = _complete_sum(tuple(run.input_tokens for run in relevant))
    total_output_tokens = _complete_sum(tuple(run.output_tokens for run in relevant))
    estimated_cost = _complete_sum(tuple(run.estimated_cost_usd_micros for run in relevant))
    accepted = (
        complete
        and fingerprints_match
        and correctness == 100
        and invalid_ids == 0
        and p95_latency is not None
        and p95_latency <= latency_threshold_ms
    )
    return ModelEvidence(
        model=model,
        complete_three_runs=complete,
        fingerprints_match=fingerprints_match,
        correctness_percent=correctness,
        invalid_id_count=invalid_ids,
        p95_latency_ms=p95_latency,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd_micros=estimated_cost,
        accepted=accepted,
    )


def select_semantic_model(
    *,
    cases: tuple[GoldSemanticCase, ...],
    runs: tuple[RecordedSemanticRun, ...],
    mode: EvaluationMode,
    fingerprint: EvaluationFingerprint,
    latency_threshold_ms: int,
) -> BenchmarkDecision:
    _assert_current_contract(fingerprint)
    if latency_threshold_ms <= 0 or not any(case.required for case in cases):
        raise ValueError("a positive latency threshold and required cases are required")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("gold case identities must be unique")
    evidence: list[ModelEvidence] = []
    for model in MODEL_ORDER:
        current = _model_evidence(
            model,
            cases=cases,
            runs=runs,
            mode=mode,
            fingerprint=fingerprint,
            latency_threshold_ms=latency_threshold_ms,
        )
        evidence.append(current)
        if current.accepted:
            return BenchmarkDecision(
                selected_model=model,
                mode=mode,
                latency_threshold_ms=latency_threshold_ms,
                fingerprint=fingerprint,
                evidence=tuple(evidence),
            )
    semantic_failure("semantic_model_gate_failed", recoverable=False)


class _CapturingProvider:
    def __init__(self, provider: SemanticProvider) -> None:
        self.provider = provider
        self.last_result: ProviderResult | None = None

    async def map_document(self, *, model: str, request: SemanticMappingInput) -> ProviderResult:
        self.last_result = await self.provider.map_document(model=model, request=request)
        return self.last_result

    async def rephrase_candidate(self, *, model: str, request: RephraseInput) -> ProviderResult:
        return await self.provider.rephrase_candidate(model=model, request=request)


async def replay_semantic_model(
    *,
    model: str,
    run: int,
    mode: EvaluationMode,
    fingerprint: EvaluationFingerprint,
    cases: tuple[SemanticReplayCase, ...],
    provider: SemanticProvider,
    timeout_seconds: float = 30.0,
    cost_estimator: CostEstimator | None = None,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
) -> tuple[RecordedSemanticRun, ...]:
    """Replay cases through ``SemanticMapper`` without retaining provider content."""

    _assert_current_contract(fingerprint)
    if model not in MODEL_ORDER or run not in REQUIRED_RUNS or not cases:
        raise ValueError("model, run, and replay cases must satisfy the benchmark contract")
    if len({case.gold.case_id for case in cases}) != len(cases):
        raise ValueError("replay case identities must be unique")

    capturing_provider = _CapturingProvider(provider)
    mapper = SemanticMapper(capturing_provider, model, timeout_seconds=timeout_seconds)
    records: list[RecordedSemanticRun] = []
    for case in cases:
        capturing_provider.last_result = None
        started_ns = clock_ns()
        exact_questions: tuple[str, ...] = ()
        failure_code: SemanticFailureCode | None = None
        invalid_id_count = 0
        try:
            mapping = await mapper.map_document(case.ir, expectations=case.expectations)
            exact_questions = tuple(question.exact_prompt for question in mapping.questions)
        except SemanticFailure as exc:
            failure_code = exc.code
            invalid_id_count = int(exc.code == "semantic_unknown_id")
        ended_ns = clock_ns()
        if ended_ns < started_ns:
            raise ValueError("benchmark clock must be monotonic")

        provider_result = capturing_provider.last_result
        input_tokens = provider_result.input_tokens if provider_result is not None else None
        output_tokens = provider_result.output_tokens if provider_result is not None else None
        estimated_cost: int | None = None
        if cost_estimator is not None and input_tokens is not None and output_tokens is not None:
            estimated_cost = cost_estimator(model, input_tokens, output_tokens)
            if estimated_cost is not None and (
                not isinstance(estimated_cost, int)
                or isinstance(estimated_cost, bool)
                or estimated_cost < 0
            ):
                raise ValueError("cost estimator must return non-negative integer USD micros")

        elapsed_ns = ended_ns - started_ns
        records.append(
            RecordedSemanticRun(
                model=model,
                case_id=case.gold.case_id,
                run=run,
                exact_questions=exact_questions,
                invalid_id_count=invalid_id_count,
                latency_ms=(elapsed_ns + 999_999) // 1_000_000,
                mode=mode,
                fingerprint=fingerprint,
                failure_code=failure_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd_micros=estimated_cost,
            )
        )
    return tuple(records)
