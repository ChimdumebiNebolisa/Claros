"""Stable, student-safe failures for the Realtime boundary."""

from __future__ import annotations

from typing import Literal

RealtimeErrorCode = Literal[
    "realtime_configuration_invalid",
    "realtime_credential_expired",
    "realtime_event_invalid",
    "realtime_provider_rejected",
    "realtime_provider_response_invalid",
    "realtime_provider_timeout",
    "realtime_provider_unavailable",
    "realtime_tool_not_allowed",
    "realtime_tool_payload_invalid",
]


class RealtimeError(Exception):
    """A stable error that never includes provider or worksheet contents."""

    def __init__(
        self,
        *,
        code: RealtimeErrorCode,
        safe_message: str,
        recoverable: bool,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.recoverable = recoverable


class ProviderRequestError(Exception):
    """Internal provider classification consumed by the credential issuer."""

    def __init__(self, kind: Literal["rejected", "timeout", "unavailable"]) -> None:
        super().__init__(kind)
        self.kind = kind


def configuration_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_configuration_invalid",
        safe_message="Voice could not start for this question. Continue by typing.",
        recoverable=True,
    )


def credential_expired_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_credential_expired",
        safe_message="The voice connection took too long to start. Try voice again.",
        recoverable=True,
    )


def event_invalid_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_event_invalid",
        safe_message="That voice update could not be accepted. Continue by typing.",
        recoverable=True,
    )


def provider_rejected_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_provider_rejected",
        safe_message="Voice is not available for this request. Continue by typing.",
        recoverable=False,
    )


def provider_response_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_provider_response_invalid",
        safe_message="Voice returned an invalid connection. Try voice again.",
        recoverable=True,
    )


def provider_timeout_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_provider_timeout",
        safe_message="Voice took too long to connect. Continue by typing or try again.",
        recoverable=True,
    )


def provider_unavailable_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_provider_unavailable",
        safe_message="Voice is unavailable right now. Continue by typing.",
        recoverable=True,
    )


def tool_not_allowed_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_tool_not_allowed",
        safe_message="That voice action is not available.",
        recoverable=True,
    )


def tool_payload_error() -> RealtimeError:
    return RealtimeError(
        code="realtime_tool_payload_invalid",
        safe_message="That voice action could not be accepted. Continue by typing.",
        recoverable=True,
    )
