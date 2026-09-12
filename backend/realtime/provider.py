"""OpenAI implementation of the narrow Realtime credential provider protocol."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import SecretStr

from backend.realtime.credentials import ClientSecretRequest
from backend.realtime.errors import ProviderRequestError


class OpenAIRealtimeCredentialProvider:
    """Mint ephemeral credentials without returning or logging the standard API key."""

    def __init__(
        self,
        *,
        api_key: SecretStr | str | None = None,
        client: Any | None = None,
    ) -> None:
        if client is None:
            secret = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            if not isinstance(secret, str) or not secret:
                raise ValueError("an OpenAI API key is required")
            client = AsyncOpenAI(api_key=secret, max_retries=0)
        self._client = client

    async def create_client_secret(
        self,
        request: ClientSecretRequest,
        *,
        safety_identifier: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        payload = request.model_dump(mode="json")
        try:
            response = await self._client.realtime.client_secrets.create(
                expires_after=payload["expires_after"],
                session=payload["session"],
                extra_headers={"OpenAI-Safety-Identifier": safety_identifier},
                timeout=timeout_seconds,
            )
        except APITimeoutError as error:
            raise ProviderRequestError("timeout") from error
        except APIConnectionError as error:
            raise ProviderRequestError("unavailable") from error
        except APIStatusError as error:
            kind = (
                "unavailable"
                if error.status_code == 429 or error.status_code >= 500
                else "rejected"
            )
            raise ProviderRequestError(kind) from error
        return _project_response(response)


def _project_response(response: Any) -> Mapping[str, Any]:
    session = getattr(response, "session", None)
    audio = getattr(session, "audio", None)
    audio_input = getattr(audio, "input", None)
    audio_output = getattr(audio, "output", None)
    transcription = getattr(audio_input, "transcription", None)
    noise_reduction = getattr(audio_input, "noise_reduction", None)
    turn_detection = getattr(audio_input, "turn_detection", None)
    reasoning = getattr(session, "reasoning", None)
    raw_tools = getattr(session, "tools", None) or ()
    tools = [
        {
            "type": getattr(tool, "type", None),
            "name": getattr(tool, "name", None),
        }
        for tool in raw_tools
    ]
    return {
        "value": getattr(response, "value", None),
        "expires_at": getattr(response, "expires_at", None),
        "session": {
            "id": getattr(session, "id", None),
            "object": getattr(session, "object", None),
            "type": getattr(session, "type", None),
            "model": getattr(session, "model", None),
            "instructions": getattr(session, "instructions", None),
            "audio": {
                "input": {
                    "transcription": {
                        "model": getattr(transcription, "model", None),
                    },
                    "noise_reduction": {
                        "type": getattr(noise_reduction, "type", None),
                    },
                    "turn_detection": {
                        "type": getattr(turn_detection, "type", None),
                        "eagerness": getattr(turn_detection, "eagerness", None),
                        "create_response": getattr(turn_detection, "create_response", None),
                        "interrupt_response": getattr(turn_detection, "interrupt_response", None),
                    },
                },
                "output": {
                    "voice": getattr(audio_output, "voice", None),
                },
            },
            "output_modalities": getattr(session, "output_modalities", None),
            "max_output_tokens": getattr(session, "max_output_tokens", None),
            "reasoning": {
                "effort": getattr(reasoning, "effort", None),
            },
            "tool_choice": getattr(session, "tool_choice", None),
            "tools": tools,
            "tracing": getattr(session, "tracing", None),
            "truncation": getattr(session, "truncation", None),
        },
    }
