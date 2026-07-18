"""Safe, deterministic controls for local AI-adjudicated benchmark runs."""
from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATES = {
    "pending", "in_progress", "succeeded", "invalid_output", "rate_limited",
    "quota_blocked", "failed", "superseded",
}


def cost_ceiling_usd() -> float:
    raw = os.environ.get("SILVER_BENCHMARK_MAX_COST_USD", "5.00")
    try:
        ceiling = float(raw)
    except ValueError as exc:
        raise ValueError("SILVER_BENCHMARK_MAX_COST_USD must be numeric") from exc
    if ceiling <= 0:
        raise ValueError("SILVER_BENCHMARK_MAX_COST_USD must be positive")
    return ceiling


class RunLedger:
    """Atomic local checkpoint store; never overwrites a successful unit."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"units": {}}

    def get(self, key: str) -> dict[str, Any] | None:
        return self.data["units"].get(key)

    def checkpoint(self, key: str, record: dict[str, Any]) -> None:
        if record.get("state") not in VALID_STATES:
            raise ValueError("invalid benchmark run state")
        previous = self.get(key)
        if previous and previous.get("state") == "succeeded" and record.get("state") != "succeeded":
            return
        self.data["units"][key] = {**record, "updated_at": datetime.now(timezone.utc).isoformat()}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def summary(self) -> dict[str, int]:
        summary = {state: 0 for state in VALID_STATES}
        for value in self.data["units"].values():
            summary[value.get("state", "failed")] += 1
        return summary


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def unit_id(*, page_id: str, role: str, prompt_version: str, schema_version: str, model: str, input_hash: str) -> str:
    return canonical_hash({"page_id": page_id, "role": role, "prompt_version": prompt_version, "schema_version": schema_version, "model": model, "input_hash": input_hash})


def estimate_cost(pricing: dict[str, Any], model: str, *, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    rates = pricing["models"][model]
    regular_input = max(0, input_tokens - cached_input_tokens)
    return round(
        (regular_input * rates["input_per_million_usd"]
         + cached_input_tokens * rates["cached_input_per_million_usd"]
         + output_tokens * rates["output_per_million_usd"]) / 1_000_000,
        8,
    )


def worst_case_cost(pricing: dict[str, Any], model: str, *, input_token_estimate: int, max_output_tokens: int) -> float:
    return estimate_cost(pricing, model, input_tokens=input_token_estimate, output_tokens=max_output_tokens)


def classify_provider_error(*, status: int | None, error_type: str | None, code: str | None, message: str | None) -> str:
    values = " ".join(str(item or "").lower() for item in (error_type, code, message))
    if "insufficient_quota" in values or "billing" in values or "usage limit" in values or "budget" in values:
        return "quota_blocked"
    if status == 429 or "rate_limit" in values or "rate limit" in values:
        return "rate_limited"
    if status and 400 <= status < 500:
        return "invalid_output"
    return "failed"


def retry_delay_seconds(*, attempt: int, retry_after: float | None = None, reset_after: float | None = None, jitter: float = 0.0) -> float:
    base = min(120.0, 5.0 * (2 ** max(0, attempt - 1)))
    preferred = retry_after if retry_after is not None else reset_after
    return max(0.0, preferred if preferred is not None else base + random.uniform(0.0, jitter))


def safe_error_metadata(exc: Exception) -> dict[str, Any]:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    body = getattr(exc, "body", {}) or {}
    error = body.get("error", body) if isinstance(body, dict) else {}
    message = str(error.get("message", ""))[:240] if isinstance(error, dict) else ""
    return {
        "exception_class": type(exc).__name__,
        "http_status": getattr(exc, "status_code", None) or getattr(response, "status_code", None),
        "provider_error_type": error.get("type") if isinstance(error, dict) else None,
        "provider_error_code": error.get("code") if isinstance(error, dict) else None,
        "provider_message": message.replace("\n", " "),
        "x_request_id": headers.get("x-request-id"),
        "x_ratelimit_limit_requests": headers.get("x-ratelimit-limit-requests"),
        "x_ratelimit_remaining_requests": headers.get("x-ratelimit-remaining-requests"),
        "x_ratelimit_reset_requests": headers.get("x-ratelimit-reset-requests"),
        "x_ratelimit_limit_tokens": headers.get("x-ratelimit-limit-tokens"),
        "x_ratelimit_remaining_tokens": headers.get("x-ratelimit-remaining-tokens"),
        "x_ratelimit_reset_tokens": headers.get("x-ratelimit-reset-tokens"),
        "retry_after": headers.get("retry-after"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
