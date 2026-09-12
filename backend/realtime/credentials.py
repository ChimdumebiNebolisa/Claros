"""Short-lived WebRTC credential issuance behind a narrow provider protocol."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from anyio import fail_after
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.realtime.errors import (
    ProviderRequestError,
    RealtimeError,
    configuration_error,
    credential_expired_error,
    provider_rejected_error,
    provider_response_error,
    provider_timeout_error,
    provider_unavailable_error,
)
from backend.realtime.models import RealtimeSessionContext
from backend.realtime.policy import (
    REALTIME_MODEL,
    build_realtime_instructions,
    realtime_tool_definitions,
)

CLIENT_SECRET_TTL_SECONDS = 60
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 8.0
WEBRTC_CALLS_URL = "https://api.openai.com/v1/realtime/calls"


class CredentialModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExpirationRequest(CredentialModel):
    anchor: Literal["created_at"] = "created_at"
    seconds: int = Field(default=CLIENT_SECRET_TTL_SECONDS, ge=10, le=120)


class TranscriptionRequest(CredentialModel):
    model: Literal["gpt-4o-mini-transcribe"] = "gpt-4o-mini-transcribe"


class NoiseReductionRequest(CredentialModel):
    type: Literal["near_field"] = "near_field"


class TurnDetectionRequest(CredentialModel):
    type: Literal["semantic_vad"] = "semantic_vad"
    eagerness: Literal["auto"] = "auto"
    create_response: Literal[True] = True
    interrupt_response: Literal[True] = True


class AudioInputRequest(CredentialModel):
    transcription: TranscriptionRequest = TranscriptionRequest()
    noise_reduction: NoiseReductionRequest = NoiseReductionRequest()
    turn_detection: TurnDetectionRequest = TurnDetectionRequest()


class AudioOutputRequest(CredentialModel):
    voice: Literal["marin"] = "marin"


class AudioRequest(CredentialModel):
    input: AudioInputRequest = AudioInputRequest()
    output: AudioOutputRequest = AudioOutputRequest()


class ReasoningRequest(CredentialModel):
    effort: Literal["minimal", "low"]


class FunctionToolRequest(CredentialModel):
    type: Literal["function"] = "function"
    name: Literal[
        "create_draft_candidate",
        "request_rephrase",
        "enter_exact_review",
        "navigate_question",
    ]
    description: str = Field(min_length=1, max_length=1_000)
    parameters: dict[str, Any]


class SessionRequest(CredentialModel):
    type: Literal["realtime"] = "realtime"
    model: Literal["gpt-realtime-2.1"] = REALTIME_MODEL
    instructions: str = Field(min_length=1, max_length=16_000)
    audio: AudioRequest = AudioRequest()
    output_modalities: tuple[Literal["audio"], ...] = ("audio",)
    max_output_tokens: int = Field(default=600, ge=1, le=4_096)
    reasoning: ReasoningRequest
    tools: tuple[FunctionToolRequest, ...] = Field(min_length=4, max_length=4)
    tool_choice: Literal["auto"] = "auto"
    parallel_tool_calls: Literal[False] = False
    tracing: None = None
    truncation: Literal["auto"] = "auto"


class ClientSecretRequest(CredentialModel):
    expires_after: ExpirationRequest = ExpirationRequest()
    session: SessionRequest


class EffectiveTool(CredentialModel):
    type: Literal["function"]
    name: Literal[
        "create_draft_candidate",
        "request_rephrase",
        "enter_exact_review",
        "navigate_question",
    ]


class EffectiveTranscription(CredentialModel):
    model: Literal["gpt-4o-mini-transcribe"]


class EffectiveNoiseReduction(CredentialModel):
    type: Literal["near_field"]


class EffectiveTurnDetection(CredentialModel):
    type: Literal["semantic_vad"]
    eagerness: Literal["auto"]
    create_response: Literal[True]
    interrupt_response: Literal[True]


class EffectiveAudioInput(CredentialModel):
    transcription: EffectiveTranscription
    noise_reduction: EffectiveNoiseReduction
    turn_detection: EffectiveTurnDetection


class EffectiveAudioOutput(CredentialModel):
    voice: Literal["marin"]


class EffectiveAudio(CredentialModel):
    input: EffectiveAudioInput
    output: EffectiveAudioOutput


class EffectiveReasoning(CredentialModel):
    effort: Literal["minimal", "low"]


class EffectiveSession(CredentialModel):
    id: str = Field(min_length=8, max_length=128, pattern=r"^sess_[A-Za-z0-9_-]+$")
    object: Literal["realtime.session"]
    type: Literal["realtime"]
    model: Literal["gpt-realtime-2.1"]
    instructions: str = Field(min_length=1, max_length=16_000)
    audio: EffectiveAudio
    output_modalities: tuple[Literal["audio"], ...]
    max_output_tokens: Literal[600]
    reasoning: EffectiveReasoning
    tool_choice: Literal["auto"]
    tools: tuple[EffectiveTool, ...] = Field(min_length=4, max_length=4)
    tracing: None
    truncation: Literal["auto"]


class ProviderCredentialResponse(CredentialModel):
    value: str = Field(min_length=8, max_length=512, pattern=r"^ek_[A-Za-z0-9_-]+$")
    expires_at: int = Field(ge=1)
    session: EffectiveSession


class RealtimeCredentialProvider(Protocol):
    async def create_client_secret(
        self,
        request: ClientSecretRequest,
        *,
        safety_identifier: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class IssuedRealtimeCredential:
    session_id: str
    client_secret: str = field(repr=False)
    expires_at: datetime
    model: Literal["gpt-realtime-2.1"] = REALTIME_MODEL
    webrtc_url: str = WEBRTC_CALLS_URL


class RealtimeCredentialIssuer:
    """Issue only a bounded, policy-bound ephemeral key for one authorized context."""

    def __init__(
        self,
        provider: RealtimeCredentialProvider,
        *,
        now: Any | None = None,
        timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    ) -> None:
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Realtime provider timeout must be between 0 and 30 seconds")
        self._provider = provider
        self._now = now or _utc_now
        self._timeout_seconds = timeout_seconds

    async def issue(
        self,
        *,
        context: RealtimeSessionContext,
        safety_subject: str,
    ) -> IssuedRealtimeCredential:
        request = build_client_secret_request(context)
        safety_identifier = _safety_identifier(safety_subject)
        try:
            with fail_after(self._timeout_seconds):
                raw_response = await self._provider.create_client_secret(
                    request,
                    safety_identifier=safety_identifier,
                    timeout_seconds=self._timeout_seconds,
                )
        except TimeoutError as error:
            raise provider_timeout_error() from error
        except ProviderRequestError as error:
            if error.kind == "timeout":
                raise provider_timeout_error() from error
            if error.kind == "rejected":
                raise provider_rejected_error() from error
            raise provider_unavailable_error() from error
        except RealtimeError:
            raise
        except Exception as error:
            raise provider_unavailable_error() from error

        try:
            canonical_response = json.dumps(
                raw_response,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            response = ProviderCredentialResponse.model_validate_json(
                canonical_response,
                strict=True,
            )
        except (TypeError, ValueError, ValidationError) as error:
            raise provider_response_error() from error
        _validate_effective_session(request, response)

        current = _aware_utc(self._now())
        try:
            expires_at = datetime.fromtimestamp(response.expires_at, tz=UTC)
        except (OverflowError, OSError, ValueError) as error:
            raise provider_response_error() from error
        remaining = (expires_at - current).total_seconds()
        if remaining <= 5:
            raise credential_expired_error()
        if remaining > request.expires_after.seconds + 60:
            raise provider_response_error()
        return IssuedRealtimeCredential(
            session_id=response.session.id,
            client_secret=response.value,
            expires_at=expires_at,
        )


def build_client_secret_request(context: RealtimeSessionContext) -> ClientSecretRequest:
    try:
        tools = tuple(
            FunctionToolRequest.model_validate(tool, strict=True)
            for tool in realtime_tool_definitions()
        )
        return ClientSecretRequest(
            session=SessionRequest(
                instructions=build_realtime_instructions(context),
                reasoning=ReasoningRequest(effort="low"),
                tools=tools,
            )
        )
    except (TypeError, ValueError, ValidationError) as error:
        raise configuration_error() from error


def _validate_effective_session(
    request: ClientSecretRequest,
    response: ProviderCredentialResponse,
) -> None:
    expected_tools = tuple(tool.name for tool in request.session.tools)
    actual_tools = tuple(tool.name for tool in response.session.tools)
    if (
        not hmac.compare_digest(response.session.instructions, request.session.instructions)
        or actual_tools != expected_tools
        or response.session.output_modalities != request.session.output_modalities
        or response.session.audio.model_dump(mode="python")
        != request.session.audio.model_dump(mode="python")
        or response.session.max_output_tokens != request.session.max_output_tokens
        or response.session.reasoning.effort != request.session.reasoning.effort
        or response.session.tool_choice != request.session.tool_choice
        or response.session.tracing is not request.session.tracing
        or response.session.truncation != request.session.truncation
    ):
        raise provider_response_error()


def _safety_identifier(subject: str) -> str:
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise configuration_error()
    digest = hashlib.sha256(f"claros-realtime\0{subject}".encode()).hexdigest()
    return f"claros_{digest[:57]}"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise configuration_error()
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
