"""Verify ephemeral credential issuance without live provider calls."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import SecretStr

from backend.realtime import (
    FakeRealtimeCredentialProvider,
    OpenAIRealtimeCredentialProvider,
    RealtimeCredentialIssuer,
    RealtimeError,
    build_client_secret_request,
)
from backend.realtime.credentials import ClientSecretRequest
from backend.realtime.errors import ProviderRequestError


class HangingProvider:
    async def create_client_secret(
        self,
        request: ClientSecretRequest,
        *,
        safety_identifier: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        del request, safety_identifier, timeout_seconds
        await _never_returns()
        raise AssertionError("unreachable")


async def _never_returns() -> None:
    import anyio

    await anyio.sleep_forever()


def _provider_response(request: ClientSecretRequest, now: datetime) -> dict[str, Any]:
    return {
        "value": "ek_ephemeral_test_1234567890",
        "expires_at": int(now.timestamp()) + request.expires_after.seconds,
        "session": {
            "id": "sess_realtime_test_1234",
            "object": "realtime.session",
            "type": "realtime",
            "model": "gpt-realtime-2.1",
            "instructions": request.session.instructions,
            "audio": request.session.audio.model_dump(mode="json"),
            "output_modalities": ["audio"],
            "max_output_tokens": 600,
            "reasoning": request.session.reasoning.model_dump(mode="json"),
            "tool_choice": "auto",
            "tools": [{"type": "function", "name": tool.name} for tool in request.session.tools],
            "tracing": None,
            "truncation": "auto",
        },
    }


@pytest.mark.asyncio
async def test_issuer_returns_only_ephemeral_browser_credential_and_fixed_policy(
    context_factory: Any,
) -> None:
    now = datetime(2040, 1, 1, tzinfo=UTC)
    context = context_factory(mode="guided")
    request = build_client_secret_request(context)
    provider = FakeRealtimeCredentialProvider(response=_provider_response(request, now))
    issuer = RealtimeCredentialIssuer(provider, now=lambda: now, timeout_seconds=2)

    credential = await issuer.issue(context=context, safety_subject="owner-internal-123")

    assert credential.session_id == "sess_realtime_test_1234"
    assert credential.client_secret == "ek_ephemeral_test_1234567890"  # noqa: S105
    assert credential.model == "gpt-realtime-2.1"
    assert credential.webrtc_url == "https://api.openai.com/v1/realtime/calls"
    assert "ek_ephemeral_test_1234567890" not in repr(credential)
    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.request == request
    assert call.safety_identifier.startswith("claros_")
    assert len(call.safety_identifier) == 64
    assert "owner-internal-123" not in call.safety_identifier
    assert call.timeout_seconds == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["timeout", "unavailable", "rejected"])
async def test_provider_failures_map_to_stable_safe_codes(
    context_factory: Any,
    kind: str,
) -> None:
    provider = FakeRealtimeCredentialProvider(
        error=ProviderRequestError(kind),  # type: ignore[arg-type]
    )
    issuer = RealtimeCredentialIssuer(provider, timeout_seconds=2)

    with pytest.raises(RealtimeError) as raised:
        await issuer.issue(context=context_factory(), safety_subject="owner-123")

    assert (
        raised.value.code
        == {
            "timeout": "realtime_provider_timeout",
            "unavailable": "realtime_provider_unavailable",
            "rejected": "realtime_provider_rejected",
        }[kind]
    )
    assert "owner-123" not in raised.value.safe_message


@pytest.mark.asyncio
async def test_issuer_enforces_its_own_provider_deadline(context_factory: Any) -> None:
    issuer = RealtimeCredentialIssuer(HangingProvider(), timeout_seconds=0.01)
    with pytest.raises(RealtimeError) as raised:
        await issuer.issue(context=context_factory(), safety_subject="owner-123")
    assert raised.value.code == "realtime_provider_timeout"
    assert raised.value.recoverable is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (lambda payload: payload.update(value="sk_standard_key_shape"), "invalid"),
        (lambda payload: payload.update(value="not_ephemeral"), "invalid"),
        (lambda payload: payload.update(unexpected="field"), "invalid"),
        (lambda payload: payload["session"].update(model="gpt-realtime-2"), "invalid"),
        (lambda payload: payload["session"].update(type="transcription"), "invalid"),
        (lambda payload: payload["session"].update(id="call_wrong_prefix"), "invalid"),
        (lambda payload: payload["session"].update(tools=[]), "invalid"),
        (lambda payload: payload["session"].update(instructions="weakened"), "invalid"),
        (
            lambda payload: payload["session"]["audio"]["input"]["transcription"].update(
                model="unsupported-transcriber"
            ),
            "invalid",
        ),
        (
            lambda payload: payload["session"]["audio"]["input"]["turn_detection"].update(
                interrupt_response=False
            ),
            "invalid",
        ),
        (lambda payload: payload["session"].update(max_output_tokens=4096), "invalid"),
        (
            lambda payload: payload["session"]["reasoning"].update(effort="high"),
            "invalid",
        ),
        (lambda payload: payload["session"].update(tracing={"workflow_name": "leak"}), "invalid"),
        (lambda payload: payload["session"].update(truncation="disabled"), "invalid"),
        (lambda payload: payload.update(expires_at=1), "expired"),
        (lambda payload: payload.update(expires_at=9_999_999_999), "invalid"),
    ],
)
async def test_credential_response_is_strictly_validated(
    context_factory: Any,
    mutate: Any,
    expected_code: str,
) -> None:
    now = datetime(2040, 1, 1, tzinfo=UTC)
    context = context_factory()
    request = build_client_secret_request(context)
    payload = deepcopy(_provider_response(request, now))
    mutate(payload)
    provider = FakeRealtimeCredentialProvider(response=payload)
    issuer = RealtimeCredentialIssuer(provider, now=lambda: now, timeout_seconds=2)

    with pytest.raises(RealtimeError) as raised:
        await issuer.issue(context=context, safety_subject="owner-123")

    expected = (
        "realtime_credential_expired"
        if expected_code == "expired"
        else "realtime_provider_response_invalid"
    )
    assert raised.value.code == expected


class FakeSDKSecrets:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


class FailingSDKSecrets:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def create(self, **kwargs: Any) -> Any:
        del kwargs
        raise self.error


@pytest.mark.asyncio
async def test_openai_provider_uses_server_header_and_projects_a_minimal_response(
    context_factory: Any,
) -> None:
    context = context_factory()
    request = build_client_secret_request(context)
    now = datetime(2040, 1, 1, tzinfo=UTC)
    effective = _provider_response(request, now)
    session_payload = effective["session"]
    audio_payload = session_payload["audio"]
    audio_input = audio_payload["input"]
    sdk_response = SimpleNamespace(
        value=effective["value"],
        expires_at=effective["expires_at"],
        session=SimpleNamespace(
            **{
                **session_payload,
                "tools": [SimpleNamespace(**tool) for tool in session_payload["tools"]],
                "audio": SimpleNamespace(
                    input=SimpleNamespace(
                        transcription=SimpleNamespace(**audio_input["transcription"]),
                        noise_reduction=SimpleNamespace(**audio_input["noise_reduction"]),
                        turn_detection=SimpleNamespace(**audio_input["turn_detection"]),
                    ),
                    output=SimpleNamespace(**audio_payload["output"]),
                ),
                "reasoning": SimpleNamespace(**session_payload["reasoning"]),
            }
        ),
    )
    secrets = FakeSDKSecrets(sdk_response)
    client = SimpleNamespace(realtime=SimpleNamespace(client_secrets=secrets))
    standard_key = "sk-standard-key-must-never-leave-server"
    provider = OpenAIRealtimeCredentialProvider(api_key=standard_key, client=client)

    projected = await provider.create_client_secret(
        request,
        safety_identifier="claros_safety_hash",
        timeout_seconds=3,
    )

    assert projected == effective
    assert secrets.kwargs is not None
    assert secrets.kwargs["extra_headers"] == {"OpenAI-Safety-Identifier": "claros_safety_hash"}
    assert secrets.kwargs["timeout"] == 3
    serialized_call = repr(secrets.kwargs)
    assert standard_key not in serialized_call
    assert standard_key not in repr(provider)


def test_openai_provider_requires_a_server_key_and_keeps_secret_wrapper_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="OpenAI API key"):
        OpenAIRealtimeCredentialProvider()

    captured: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("backend.realtime.provider.AsyncOpenAI", fake_client)
    key = SecretStr("server-only-test-key")
    provider = OpenAIRealtimeCredentialProvider(api_key=key)

    assert captured == {"api_key": "server-only-test-key", "max_retries": 0}
    assert "server-only-test-key" not in repr(provider)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "expected_kind"),
    [
        (APITimeoutError(httpx2.Request("POST", "https://api.openai.com")), "timeout"),
        (
            APIConnectionError(request=httpx2.Request("POST", "https://api.openai.com")),
            "unavailable",
        ),
        (
            APIStatusError(
                "private provider detail",
                response=httpx2.Response(
                    401,
                    request=httpx2.Request("POST", "https://api.openai.com"),
                ),
                body={"private": "detail"},
            ),
            "rejected",
        ),
        (
            APIStatusError(
                "rate limited",
                response=httpx2.Response(
                    429,
                    request=httpx2.Request("POST", "https://api.openai.com"),
                ),
                body=None,
            ),
            "unavailable",
        ),
        (
            APIStatusError(
                "provider down",
                response=httpx2.Response(
                    503,
                    request=httpx2.Request("POST", "https://api.openai.com"),
                ),
                body=None,
            ),
            "unavailable",
        ),
    ],
)
async def test_openai_provider_classifies_sdk_failures_without_leaking_details(
    context_factory: Any,
    provider_error: Exception,
    expected_kind: str,
) -> None:
    client = SimpleNamespace(
        realtime=SimpleNamespace(client_secrets=FailingSDKSecrets(provider_error))
    )
    provider = OpenAIRealtimeCredentialProvider(client=client)

    with pytest.raises(ProviderRequestError) as raised:
        await provider.create_client_secret(
            build_client_secret_request(context_factory()),
            safety_identifier="claros_safe_hash",
            timeout_seconds=2,
        )
    assert raised.value.kind == expected_kind
    assert "private provider detail" not in str(raised.value)
