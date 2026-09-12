"""Explicit test double for deterministic Realtime credential integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.realtime.credentials import ClientSecretRequest


@dataclass(frozen=True, slots=True)
class CredentialProviderCall:
    request: ClientSecretRequest
    safety_identifier: str
    timeout_seconds: float


class FakeRealtimeCredentialProvider:
    """Return one scripted response or error without making a provider call."""

    def __init__(
        self,
        *,
        response: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        if (response is None) == (error is None):
            raise ValueError("configure exactly one fake response or error")
        self._response = response
        self._error = error
        self.calls: list[CredentialProviderCall] = []

    async def create_client_secret(
        self,
        request: ClientSecretRequest,
        *,
        safety_identifier: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        self.calls.append(
            CredentialProviderCall(
                request=request,
                safety_identifier=safety_identifier,
                timeout_seconds=timeout_seconds,
            )
        )
        if self._error is not None:
            raise self._error
        if self._response is None:  # pragma: no cover - constructor invariant
            raise AssertionError("fake provider response is missing")
        return self._response
