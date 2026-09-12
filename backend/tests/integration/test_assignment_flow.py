"""Exercise the durable typed path through the real API and PDF engine."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pikepdf
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.document import extract_physical_ir
from backend.main import create_app
from backend.semantic import FakeSemanticProvider, ProviderResult, SemanticMapper
from backend.semantic.models import (
    RephraseOutput,
    SemanticMappingOutput,
    SemanticQuestionOutput,
)
from backend.service import AssignmentApplicationService
from backend.storage import LocalObjectStore

ORIGIN = "http://testserver"
MUTATION_HEADERS = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
OWNER_TEST_SECRET = "integration-owner-secret-with-sufficient-entropy"  # noqa: S105
REVIEW_TEST_SECRET = "integration-review-secret-with-sufficient-entropy"  # noqa: S105
SAMPLE_PDF = (
    Path(__file__).resolve().parents[3] / "public" / "fixtures" / "claros-biology-short-answer.pdf"
)


def _settings(storage_root: Path) -> Settings:
    return Settings(
        environment="test",
        storage_backend="local",
        local_storage_path=storage_root,
        public_origin=ORIGIN,
        cookie_secret=OWNER_TEST_SECRET,
        review_token_secret=REVIEW_TEST_SECRET,
        semantic_engine="current",
        realtime_engine="current",
        openai_api_key=None,
    )


def _create_sample(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v2/assignments",
        data={"sample_id": "biology-short-answer"},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 201, response.text
    assert response.headers["etag"] == '"assignment-version-1"'
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["question_count"] == 3
    assert [item["prompt"] for item in payload["questions"]] == [
        "Why do plants need sunlight?",
        "How does sunlight help a plant make food?",
        "How can photosynthesis support other living things?",
    ]
    return payload


def test_typed_confirmation_partial_export_and_restart(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "objects")
    first_app = create_app(settings=settings)

    with TestClient(first_app) as client:
        assignment = _create_sample(client)
        assignment_id = str(assignment["assignment_id"])
        question = assignment["questions"][0]
        question_id = str(question["question_id"])

        source = client.get(
            f"/api/v2/assignments/{assignment_id}/source",
            headers={"Range": "bytes=0-31"},
        )
        assert source.status_code == 206
        assert source.headers["content-range"].startswith("bytes 0-31/")
        assert source.content.startswith(b"%PDF-")
        assert len(source.content) == 32

        unsatisfiable = client.get(
            f"/api/v2/assignments/{assignment_id}/source",
            headers={"Range": "bytes=999999999-"},
        )
        assert unsatisfiable.status_code == 416
        assert unsatisfiable.json()["error"]["code"] == "range_not_satisfiable"

        answer_text = "Chlorophyll captures sunlight—turning CO₂ and H₂O into food."
        candidate_response = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/candidates",
            json={
                "assignment_version": assignment["version"],
                "text": answer_text,
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert candidate_response.status_code == 200, candidate_response.text
        candidate_payload = candidate_response.json()
        assert candidate_payload["candidate"]["text"] == answer_text
        assert candidate_payload["candidate"]["attribution"] == "Your words"

        review_response = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/review",
            json={
                "assignment_version": candidate_payload["version"],
                "candidate_id": candidate_payload["candidate"]["candidate_id"],
                "candidate_version": candidate_payload["candidate"]["candidate_version"],
            },
            headers=MUTATION_HEADERS,
        )
        assert review_response.status_code == 200, review_response.text
        review = review_response.json()
        assert review["candidate"]["text"] == answer_text
        assert review["placement"] in {"inline", "appendix"}

        confirm_body = {
            "assignment_version": review["version"],
            "review_token": review["review_token"],
            "candidate_id": review["candidate"]["candidate_id"],
            "candidate_version": review["candidate"]["candidate_version"],
        }
        confirmation_response = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/confirm",
            json=confirm_body,
            headers=MUTATION_HEADERS,
        )
        assert confirmation_response.status_code == 200, confirmation_response.text
        confirmation = confirmation_response.json()
        assert confirmation["confirmed_answer"]["exact_text"] == answer_text
        assert confirmation["replayed"] is False

        replay_response = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/confirm",
            json=confirm_body,
            headers=MUTATION_HEADERS,
        )
        assert replay_response.status_code == 200, replay_response.text
        assert replay_response.json()["replayed"] is True
        assert replay_response.json()["confirmation_id"] == confirmation["confirmation_id"]

        owner_cookie = client.cookies.get(settings.owner_cookie_name)
        assert owner_cookie is not None

    restarted_app = create_app(settings=settings)
    with TestClient(restarted_app) as restarted:
        restarted.cookies.set(settings.owner_cookie_name, owner_cookie)
        restored_response = restarted.get(f"/api/v2/assignments/{assignment_id}")
        assert restored_response.status_code == 200, restored_response.text
        restored = restored_response.json()
        assert restored["questions"][0]["confirmed_answer"]["exact_text"] == answer_text

        export_response = restarted.post(
            f"/api/v2/assignments/{assignment_id}/exports",
            json={
                "assignment_version": restored["version"],
                "idempotency_key": "integration-export-key-0001",
            },
            headers=MUTATION_HEADERS,
        )
        assert export_response.status_code == 201, export_response.text
        exported = export_response.json()
        assert exported["status"] == "complete"
        assert exported["download_url"]

        replay_export = restarted.post(
            f"/api/v2/assignments/{assignment_id}/exports",
            json={
                "assignment_version": restored["version"],
                "idempotency_key": "integration-export-key-0001",
            },
            headers=MUTATION_HEADERS,
        )
        assert replay_export.status_code == 200, replay_export.text
        assert replay_export.json()["export_id"] == exported["export_id"]

        download = restarted.get(exported["download_url"])
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF-")
        with pikepdf.open(BytesIO(download.content)):
            pass

        refreshed = restarted.get(f"/api/v2/assignments/{assignment_id}").json()
        assert sum(item["confirmed_answer"] is not None for item in refreshed["questions"]) == 1


def test_owner_and_browser_boundaries_are_fail_closed(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "objects")
    app = create_app(settings=settings)
    with TestClient(app) as owner:
        assignment = _create_sample(owner)
        assignment_id = assignment["assignment_id"]

        with TestClient(app) as stranger:
            denied = stranger.get(f"/api/v2/assignments/{assignment_id}")
            assert denied.status_code == 404
            assert denied.json() == {
                "error": {
                    "code": "assignment_not_found",
                    "message": "This worksheet session is no longer available.",
                    "recoverable": False,
                }
            }

        blocked = owner.post(
            f"/api/v2/assignments/{assignment_id}/exports",
            json={
                "assignment_version": assignment["version"],
                "idempotency_key": "cross-site-export-key-0001",
            },
            headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
        )
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "origin_forbidden"


def test_stale_mutation_returns_current_version(tmp_path: Path) -> None:
    settings = _settings(tmp_path / "objects")
    with TestClient(create_app(settings=settings)) as client:
        assignment = _create_sample(client)
        assignment_id = assignment["assignment_id"]
        question_id = assignment["questions"][0]["question_id"]
        first = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/candidates",
            json={
                "assignment_version": assignment["version"],
                "text": "First exact answer.",
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert first.status_code == 200

        stale = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{question_id}/candidates",
            json={
                "assignment_version": assignment["version"],
                "text": "A stale overwrite.",
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "assignment_version_conflict"
        assert stale.json()["version"] == first.json()["version"]


def test_recorded_semantic_mapping_supports_both_typed_paths_rephrase_and_export(
    tmp_path: Path,
) -> None:
    source = SAMPLE_PDF.read_bytes()
    physical_ir = extract_physical_ir(source)

    def block_id(exact_text: str) -> str:
        return next(
            block.id
            for page in physical_ir.pages
            for block in page.blocks
            if block.text == exact_text
        )

    mapping = SemanticMappingOutput(
        document_id=physical_ir.document_id,
        complete=True,
        questions=(
            SemanticQuestionOutput(
                question_key="q_001",
                prompt_block_ids=(block_id("Why do plants need sunlight?"),),
                context_block_ids=(
                    block_id("Use evidence from the lesson in one or two sentences."),
                ),
                question_type="short_answer",
                grounding="grounded",
                visual_context_dependency=False,
            ),
            SemanticQuestionOutput(
                question_key="q_002",
                prompt_block_ids=(block_id("How does sunlight help a plant make food?"),),
                context_block_ids=(block_id("Describe the role of sunlight in your own words."),),
                question_type="short_answer",
                grounding="grounded",
                visual_context_dependency=False,
            ),
            SemanticQuestionOutput(
                question_key="q_003",
                prompt_block_ids=(block_id("How can photosynthesis support other living things?"),),
                context_block_ids=(block_id("Give one clear connection to another living thing."),),
                question_type="short_answer",
                grounding="grounded",
                visual_context_dependency=False,
            ),
        ),
    )
    provider = FakeSemanticProvider(
        mapping_results=(ProviderResult(parsed=mapping),),
        rephrase_results=(
            ProviderResult(
                parsed=RephraseOutput(
                    suggestion="Plants use sunlight to make food through photosynthesis.",
                    meaning_preserved=True,
                )
            ),
        ),
    )
    settings = _settings(tmp_path / "semantic-objects")
    service = AssignmentApplicationService(
        settings=settings,
        store=LocalObjectStore(settings.local_storage_path),
        semantic_mapper=SemanticMapper(provider, "gpt-5.6-luna"),
    )

    with TestClient(create_app(settings=settings, assignment_service=service)) as client:
        assignment = _create_sample(client)
        assignment_id = str(assignment["assignment_id"])
        first_question = assignment["questions"][0]
        second_question = assignment["questions"][1]
        assert [question["question_id"] for question in assignment["questions"]] == [
            "q_001",
            "q_002",
            "q_003",
        ]
        assert provider.mapping_calls[0][0] == "gpt-5.6-luna"
        assert all(
            set(block.model_dump())
            == {"id", "exact_text", "kind", "page_number", "reading_order", "relation_hints"}
            for block in provider.mapping_calls[0][1].blocks
        )

        direct = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/q_001/candidates",
            json={
                "assignment_version": assignment["version"],
                "text": "Plants need sunlight to make food.",
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert direct.status_code == 200, direct.text
        direct_payload = direct.json()
        rephrase = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/q_001/rephrase",
            json={
                "assignment_version": direct_payload["version"],
                "candidate_id": direct_payload["candidate"]["candidate_id"],
                "candidate_version": direct_payload["candidate"]["candidate_version"],
            },
            headers=MUTATION_HEADERS,
        )
        assert rephrase.status_code == 200, rephrase.text
        comparison = rephrase.json()
        assert comparison["original"]["text"] == "Plants need sunlight to make food."
        assert comparison["suggestion"]["attribution"] == "Suggested wording"
        assert comparison["selected_candidate_id"] is None
        persisted = service.manifests.load(assignment_id).manifest.questions[0]
        assert persisted.current_candidate is not None
        assert persisted.current_candidate.exact_text == comparison["original"]["text"]

        selected = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/q_001/candidates",
            json={
                "assignment_version": comparison["version"],
                "text": comparison["suggestion"]["text"],
                "origin": "claros_rephrase",
                "interaction": {
                    "kind": "selected_rephrase",
                    "rephrase_id": comparison["rephrase_id"],
                    "suggestion_candidate_id": comparison["suggestion"]["candidate_id"],
                },
            },
            headers=MUTATION_HEADERS,
        )
        assert selected.status_code == 200, selected.text
        selected_payload = selected.json()

        guided = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/q_002/candidates",
            json={
                "assignment_version": selected_payload["version"],
                "text": "Sunlight provides the energy a plant uses to make food.",
                "origin": "student_after_guidance",
                "interaction": {
                    "kind": "guided_final",
                    "realtime_session_id": "rt_recorded_typed",
                    "source_turn_ids": ["turn_1", "turn_2"],
                    "input": "typed",
                },
            },
            headers=MUTATION_HEADERS,
        )
        assert guided.status_code == 200, guided.text

        version = guided.json()["version"]
        confirmed = []
        for question, candidate in (
            (first_question, selected_payload["candidate"]),
            (second_question, guided.json()["candidate"]),
        ):
            review = client.post(
                f"/api/v2/assignments/{assignment_id}/questions/{question['question_id']}/review",
                json={
                    "assignment_version": version,
                    "candidate_id": candidate["candidate_id"],
                    "candidate_version": candidate["candidate_version"],
                },
                headers=MUTATION_HEADERS,
            )
            assert review.status_code == 200, review.text
            review_payload = review.json()
            confirmation = client.post(
                f"/api/v2/assignments/{assignment_id}/questions/{question['question_id']}/confirm",
                json={
                    "assignment_version": review_payload["version"],
                    "review_token": review_payload["review_token"],
                    "candidate_id": candidate["candidate_id"],
                    "candidate_version": candidate["candidate_version"],
                },
                headers=MUTATION_HEADERS,
            )
            assert confirmation.status_code == 200, confirmation.text
            version = confirmation.json()["version"]
            confirmed.append(confirmation.json()["confirmed_answer"])

        exported = client.post(
            f"/api/v2/assignments/{assignment_id}/exports",
            json={
                "assignment_version": version,
                "idempotency_key": "semantic-recorded-export-0001",
            },
            headers=MUTATION_HEADERS,
        )
        assert exported.status_code == 201, exported.text
        download = client.get(exported.json()["download_url"])
        with pikepdf.open(BytesIO(download.content)):
            pass
        assert [answer["origin"] for answer in confirmed] == [
            "claros_rephrase",
            "student_after_guidance",
        ]
        assert len(provider.mapping_calls) == 1
        assert len(provider.rephrase_calls) == 1


def test_semantic_provider_failure_preserves_safe_assignment_state_and_logs(
    tmp_path: Path,
    caplog,
) -> None:
    private_detail = "private worksheet answer from provider payload"
    provider = FakeSemanticProvider(mapping_results=(RuntimeError(private_detail),))
    settings = _settings(tmp_path / "semantic-failure-objects")
    service = AssignmentApplicationService(
        settings=settings,
        store=LocalObjectStore(settings.local_storage_path),
        semantic_mapper=SemanticMapper(provider, "gpt-5.6-luna"),
    )

    with TestClient(create_app(settings=settings, assignment_service=service)) as client:
        response = client.post(
            "/api/v2/assignments",
            data={"sample_id": "biology-short-answer"},
            headers=MUTATION_HEADERS,
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "analysis_failed"
    assert payload["warnings"] == [
        {
            "code": "semantic_provider_unavailable",
            "message": "Claros could not safely check this worksheet. Try another PDF.",
        }
    ]
    persisted = service.manifests.load(payload["assignment_id"]).manifest
    assert persisted.questions == ()
    assert persisted.physical_ir is None
    assert service.store.read(persisted.source.key).data.startswith(b"%PDF-")
    assert private_detail not in response.text
    assert private_detail not in caplog.text
