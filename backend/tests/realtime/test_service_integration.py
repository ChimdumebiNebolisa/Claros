"""Exercise the authorized Realtime credential route through the real service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.config import Settings
from backend.main import create_app
from backend.realtime import (
    IssuedRealtimeCredential,
    RealtimeCredentialIssuer,
    RealtimeSessionContext,
)
from backend.service import AssignmentApplicationService, build_assignment_service
from backend.storage import LocalObjectStore

ORIGIN = "http://testserver"
MUTATION_HEADERS = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
NOW = datetime(2040, 1, 1, tzinfo=UTC)


@dataclass
class MutableClock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value


@dataclass
class CapturingIssuer:
    calls: list[tuple[RealtimeSessionContext, str]] = field(default_factory=list)

    async def issue(
        self, *, context: RealtimeSessionContext, safety_subject: str
    ) -> IssuedRealtimeCredential:
        self.calls.append((context, safety_subject))
        return IssuedRealtimeCredential(
            session_id="sess_service_integration",
            client_secret="ek_service_integration",  # noqa: S106
            expires_at=NOW + timedelta(seconds=60),
        )


def _settings(storage_root: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "storage_backend": "local",
        "local_storage_path": storage_root,
        "public_origin": ORIGIN,
        "cookie_secret": "realtime-owner-secret-with-sufficient-entropy",
        "review_token_secret": "realtime-review-secret-with-sufficient-entropy",
        "semantic_engine": "current",
        "realtime_engine": "current",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_realtime_configuration_requires_a_server_key_and_wires_the_issuer(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="OpenAI Realtime"):
        _settings(tmp_path / "missing", realtime_engine="openai", openai_api_key=None)

    service = build_assignment_service(
        _settings(
            tmp_path / "configured",
            realtime_engine="openai",
            openai_api_key="server-only-test-key",
        )
    )

    assert isinstance(service.realtime_credential_issuer, RealtimeCredentialIssuer)


def test_credential_route_binds_owner_question_mode_version_expiry_and_rate_limit(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path / "objects", realtime_rate_limit=2)
    clock = MutableClock()
    issuer = CapturingIssuer()
    service = AssignmentApplicationService(
        settings=settings,
        store=LocalObjectStore(settings.local_storage_path),
        now=clock,
        realtime_credential_issuer=issuer,  # type: ignore[arg-type]
    )
    app = create_app(settings=settings, assignment_service=service)

    with TestClient(app) as owner:
        created = owner.post(
            "/api/v2/assignments",
            data={"sample_id": "biology-short-answer"},
            headers=MUTATION_HEADERS,
        )
        assert created.status_code == 201, created.text
        assignment = created.json()
        body = {
            "assignment_id": assignment["assignment_id"],
            "assignment_version": assignment["version"],
            "question_id": assignment["questions"][0]["question_id"],
            "mode": "guided",
        }

        issued = owner.post("/api/v2/realtime/client-secret", json=body, headers=MUTATION_HEADERS)
        assert issued.status_code == 200, issued.text
        payload = issued.json()
        assert payload == {
            "version": assignment["version"],
            "session_id": "sess_service_integration",
            "client_secret": "ek_service_integration",
            "expires_at": "2040-01-01T00:01:00Z",
            "model": "gpt-realtime-2.1",
        }

        context, safety_subject = issuer.calls[0]
        assert context.assignment_id == assignment["assignment_id"]
        assert context.assignment_version == assignment["version"]
        assert context.question_id == assignment["questions"][0]["question_id"]
        assert context.mode == "guided"
        assert context.exact_question == assignment["questions"][0]["prompt"]
        assert context.current_candidate is None
        assert safety_subject not in issued.text

        with TestClient(app) as intruder:
            denied = intruder.post(
                "/api/v2/realtime/client-secret", json=body, headers=MUTATION_HEADERS
            )
        assert denied.status_code == 404

        stale = owner.post(
            "/api/v2/realtime/client-secret",
            json={**body, "assignment_version": assignment["version"] + 1},
            headers=MUTATION_HEADERS,
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "assignment_version_conflict"

        limited = owner.post("/api/v2/realtime/client-secret", json=body, headers=MUTATION_HEADERS)
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limit_exceeded"

        clock.value += timedelta(days=1)
        expired = owner.post("/api/v2/realtime/client-secret", json=body, headers=MUTATION_HEADERS)
        assert expired.status_code == 404
        assert expired.json()["error"]["code"] == "assignment_not_found"

    assert len(issuer.calls) == 1
