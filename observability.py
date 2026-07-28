"""Privacy-safe operational events with fixed names and bounded labels."""
import logging

logger = logging.getLogger(__name__)

EVENTS = {
    "pdf_parse",
    "page_render",
    "assignment_created",
    "assignment_expired",
    "assignment_deleted",
    "session_created",
    "session_expired",
    "session_cleanup",
    "confirmation",
    "write_conflict",
    "token_replay_rejected",
    "provider_failure",
    "restoration",
    "export",
    "rate_limit",
    "voice_connect",
    "voice_disconnect",
    "voice_reconnect",
}
STATUSES = {"ok", "error", "fallback", "expired", "conflict", "rejected", "blocked"}
REASONS = {
    "malformed",
    "provider",
    "microphone",
    "storage",
    "permission",
    "replay",
    "timeout",
    "unknown",
    "upload",
    "provider_session",
    "write",
    "assignment_mutation",
    "assignment_delete",
    "page_render",
    "debug_provider",
    "session_start",
}


def record_metric(event: str, *, status: str = "ok", reason: str | None = None, duration_ms: int | None = None) -> None:
    """Emit a bounded metric event without accepting arbitrary content labels."""
    if event not in EVENTS:
        raise ValueError("unsupported metric event")
    if status not in STATUSES:
        raise ValueError("unsupported metric status")
    if reason is not None and reason not in REASONS:
        raise ValueError("unsupported metric reason")
    if duration_ms is not None and (duration_ms < 0 or duration_ms > 3_600_000):
        raise ValueError("unsupported metric duration")
    logger.info(
        "metric event=%s status=%s reason=%s duration_ms=%s",
        event,
        status,
        reason or "none",
        duration_ms if duration_ms is not None else "none",
    )
