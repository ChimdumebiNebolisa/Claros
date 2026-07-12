"""Privacy-safe operational events with fixed names and bounded labels."""
import logging

logger = logging.getLogger(__name__)

EVENTS = {
    "pdf_parse",
    "assignment_created",
    "session_created",
    "session_expired",
    "confirmation",
    "write_conflict",
    "token_replay_rejected",
    "provider_failure",
    "restoration",
    "export",
}
STATUSES = {"ok", "error", "fallback", "expired", "conflict", "rejected"}
REASONS = {"malformed", "provider", "microphone", "storage", "permission", "replay", "timeout", "unknown"}


def record_metric(event: str, *, status: str = "ok", reason: str | None = None) -> None:
    """Emit a bounded metric event without accepting arbitrary content labels."""
    if event not in EVENTS:
        raise ValueError("unsupported metric event")
    if status not in STATUSES:
        raise ValueError("unsupported metric status")
    if reason is not None and reason not in REASONS:
        raise ValueError("unsupported metric reason")
    logger.info("metric event=%s status=%s reason=%s", event, status, reason or "none")
