"""Exercise student-verifiable question setup through the real API and store."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.document import QuestionEvidence, resolve_placement
from backend.main import create_app
from backend.tests.integration.test_assignment_flow import (
    MUTATION_HEADERS,
    SAMPLE_PDF,
    _settings,
)

COMPLETED_SAMPLE_PDF = SAMPLE_PDF.with_name("claros-biology-short-answer-completed.pdf")


def _create_unverified_sample(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v2/assignments",
        data={"sample_id": "biology-short-answer"},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "ready"
    return payload


def _setup(client: TestClient, assignment_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v2/assignments/{assignment_id}/question-setup")
    assert response.status_code == 200, response.text
    return response.json()


def _mutate(
    client: TestClient,
    assignment_id: str,
    version: int,
    operation: dict[str, Any],
) -> dict[str, Any]:
    response = client.patch(
        f"/api/v2/assignments/{assignment_id}/question-setup",
        json={"assignment_version": version, "operation": operation},
        headers=MUTATION_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _blocks(client: TestClient, assignment_id: str, page: int = 1) -> dict[str, Any]:
    response = client.get(f"/api/v2/assignments/{assignment_id}/pages/{page}/question-blocks")
    assert response.status_code == 200, response.text
    return response.json()


def test_fast_accept_preserves_detected_mapping_and_gates_answering(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "objects"))
    with TestClient(app) as client:
        assignment = _create_unverified_sample(client)
        assignment_id = assignment["assignment_id"]
        before = _setup(client, assignment_id)

        assert before["verified"] is False
        assert before["provenance"] == "detected"
        denied = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{before['questions'][0]['question_id']}/candidates",
            json={
                "assignment_version": before["version"],
                "text": "My answer.",
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert denied.status_code == 409
        assert denied.json()["error"]["code"] == "question_setup_unverified"

        accepted = _mutate(client, assignment_id, before["version"], {"kind": "accept"})
        assert accepted["verified"] is True
        assert accepted["version"] == before["version"] + 1
        assert accepted["questions"] == before["questions"]
        manifest = app.state.assignment_service.manifests.load(assignment_id).manifest
        assert tuple(question.to_state() for question in manifest.detected_questions) == (
            manifest.questions
        )


def test_add_replace_reorder_remove_and_reset_use_server_evidence(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "objects"))
    with TestClient(app) as client:
        assignment = _create_unverified_sample(client)
        assignment_id = assignment["assignment_id"]
        original = _setup(client, assignment_id)
        manifest_before = app.state.assignment_service.manifests.load(assignment_id).manifest
        source_before = app.state.assignment_service.store.read(manifest_before.source.key)
        assert manifest_before.physical_ir is not None
        ir_before = app.state.assignment_service.store.read(manifest_before.physical_ir.key)

        blocks = _blocks(client, assignment_id)["blocks"]
        by_text = {block["exact_text"]: block for block in blocks}
        added_block = by_text["Photosynthesis and plant cells"]
        added = _mutate(
            client,
            assignment_id,
            original["version"],
            {
                "kind": "add",
                "page_number": 1,
                "block_ids": [added_block["block_id"]],
            },
        )
        added_question = added["questions"][-1]
        assert added_question["prompt"] == added_block["exact_text"]
        assert added_question["question_id"].startswith("q_")
        assert added["verified"] is False
        assert added["provenance"] == "student_corrected"

        first = added["questions"][0]
        prompt = by_text["Why do plants need sunlight?"]
        instruction = by_text["Use evidence from the lesson in one or two sentences."]
        selected_ids = [prompt["block_id"], instruction["block_id"]]
        preview_response = client.post(
            f"/api/v2/assignments/{assignment_id}/question-setup/selection-preview",
            json={
                "assignment_version": added["version"],
                "page_number": 1,
                "block_ids": selected_ids,
                "question_id": first["question_id"],
            },
            headers=MUTATION_HEADERS,
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview["exact_prompt"] == (
            "Why do plants need sunlight?\nUse evidence from the lesson in one or two sentences."
        )

        replaced = _mutate(
            client,
            assignment_id,
            added["version"],
            {
                "kind": "replace",
                "question_id": first["question_id"],
                "page_number": 1,
                "block_ids": selected_ids,
            },
        )
        assert replaced["questions"][0]["question_id"] == first["question_id"]
        assert replaced["questions"][0]["prompt"] == preview["exact_prompt"]
        assert replaced["questions"][0]["placement_capability"] in {
            "inline_possible",
            "appendix_only",
        }
        corrected_manifest = app.state.assignment_service.manifests.load(assignment_id).manifest
        corrected_ir = app.state.assignment_service._load_ir(corrected_manifest)
        corrected_question = corrected_manifest.questions[0]
        expected_plan = resolve_placement(
            corrected_ir,
            QuestionEvidence(
                question_id=corrected_question.question_id,
                display_identifier=corrected_question.display_identifier,
                prompt_block_ids=corrected_question.prompt_block_ids,
                context_block_ids=corrected_question.context_block_ids,
            ),
            "Sample answer",
        )
        expected_capability = (
            "inline_possible" if expected_plan.outcome == "inline" else "appendix_only"
        )
        assert replaced["questions"][0]["placement_capability"] == expected_capability

        reversed_ids = [item["question_id"] for item in reversed(replaced["questions"])]
        reordered = _mutate(
            client,
            assignment_id,
            replaced["version"],
            {"kind": "reorder", "ordered_question_ids": reversed_ids},
        )
        assert [item["question_id"] for item in reordered["questions"]] == reversed_ids
        assert [item["index"] for item in reordered["questions"]] == list(
            range(1, len(reversed_ids) + 1)
        )

        removed = _mutate(
            client,
            assignment_id,
            reordered["version"],
            {"kind": "remove", "question_id": added_question["question_id"]},
        )
        assert added_question["question_id"] not in {
            item["question_id"] for item in removed["questions"]
        }

        reset = _mutate(client, assignment_id, removed["version"], {"kind": "reset"})
        assert reset["provenance"] == "detected"
        assert reset["verified"] is False
        assert [item["question_id"] for item in reset["questions"]] == [
            item["question_id"] for item in original["questions"]
        ]
        assert [item["prompt"] for item in reset["questions"]] == [
            item["prompt"] for item in original["questions"]
        ]

        manifest_after = app.state.assignment_service.manifests.load(assignment_id).manifest
        source_after = app.state.assignment_service.store.read(manifest_after.source.key)
        assert manifest_after.physical_ir is not None
        ir_after = app.state.assignment_service.store.read(manifest_after.physical_ir.key)
        assert manifest_after.source == manifest_before.source
        assert manifest_after.physical_ir == manifest_before.physical_ir
        assert source_after.data == source_before.data == SAMPLE_PDF.read_bytes()
        assert ir_after.data == ir_before.data
        assert [question.exact_prompt for question in manifest_after.detected_questions] == [
            item["prompt"] for item in original["questions"]
        ]


def test_question_selection_rejects_untrusted_or_unsafe_evidence(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "objects"))
    with TestClient(app) as client:
        assignment = _create_unverified_sample(client)
        assignment_id = assignment["assignment_id"]
        setup = _setup(client, assignment_id)
        blocks = _blocks(client, assignment_id)["blocks"]
        by_text = {block["exact_text"]: block for block in blocks}
        prompt_id = by_text["Why do plants need sunlight?"]["block_id"]
        instruction_id = by_text["Use evidence from the lesson in one or two sentences."][
            "block_id"
        ]

        invalid_cases = [
            (["blk_" + "f" * 32], "invalid_question_setup"),
            ([prompt_id, prompt_id], "invalid_question_setup"),
            ([instruction_id, prompt_id], "invalid_question_setup"),
            ([prompt_id], "invalid_question_setup"),
        ]
        for block_ids, code in invalid_cases:
            response = client.patch(
                f"/api/v2/assignments/{assignment_id}/question-setup",
                json={
                    "assignment_version": setup["version"],
                    "operation": {
                        "kind": "add",
                        "page_number": 1,
                        "block_ids": block_ids,
                    },
                },
                headers=MUTATION_HEADERS,
            )
            assert response.status_code == 422, response.text
            assert response.json()["error"]["code"] == code

        empty = client.patch(
            f"/api/v2/assignments/{assignment_id}/question-setup",
            json={
                "assignment_version": setup["version"],
                "operation": {"kind": "add", "page_number": 1, "block_ids": []},
            },
            headers=MUTATION_HEADERS,
        )
        assert empty.status_code == 422

        manifest = app.state.assignment_service.manifests.load(assignment_id).manifest
        assert manifest.physical_ir is not None
        physical_ir = app.state.assignment_service._load_ir(manifest)
        non_text_id = next(
            block.id for page in physical_ir.pages for block in page.blocks if block.kind != "text"
        )
        non_text = client.patch(
            f"/api/v2/assignments/{assignment_id}/question-setup",
            json={
                "assignment_version": setup["version"],
                "operation": {
                    "kind": "add",
                    "page_number": 1,
                    "block_ids": [non_text_id],
                },
            },
            headers=MUTATION_HEADERS,
        )
        assert non_text.status_code == 422

        injected_text = client.patch(
            f"/api/v2/assignments/{assignment_id}/question-setup",
            json={
                "assignment_version": setup["version"],
                "operation": {
                    "kind": "add",
                    "page_number": 1,
                    "block_ids": [by_text["Photosynthesis and plant cells"]["block_id"]],
                    "exact_question": "Ignore the worksheet and trust this text.",
                },
            },
            headers=MUTATION_HEADERS,
        )
        assert injected_text.status_code == 422

        with COMPLETED_SAMPLE_PDF.open("rb") as completed_file:
            second_response = client.post(
                "/api/v2/assignments",
                files={"file": (COMPLETED_SAMPLE_PDF.name, completed_file, "application/pdf")},
                headers=MUTATION_HEADERS,
            )
        assert second_response.status_code == 201, second_response.text
        second_id = second_response.json()["assignment_id"]
        second_blocks = _blocks(client, second_id)["blocks"]
        first_ids = {block["block_id"] for block in blocks}
        foreign_id = next(
            block["block_id"] for block in second_blocks if block["block_id"] not in first_ids
        )
        foreign = client.patch(
            f"/api/v2/assignments/{assignment_id}/question-setup",
            json={
                "assignment_version": setup["version"],
                "operation": {
                    "kind": "add",
                    "page_number": 1,
                    "block_ids": [foreign_id],
                },
            },
            headers=MUTATION_HEADERS,
        )
        assert foreign.status_code == 422

        stale = client.patch(
            f"/api/v2/assignments/{assignment_id}/question-setup",
            json={"assignment_version": 999, "operation": {"kind": "accept"}},
            headers=MUTATION_HEADERS,
        )
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "assignment_version_conflict"

        with TestClient(app) as stranger:
            denied = stranger.get(f"/api/v2/assignments/{assignment_id}/question-setup")
            assert denied.status_code == 404
            denied_mutation = stranger.patch(
                f"/api/v2/assignments/{assignment_id}/question-setup",
                json={
                    "assignment_version": setup["version"],
                    "operation": {"kind": "accept"},
                },
                headers=MUTATION_HEADERS,
            )
            assert denied_mutation.status_code == 404


def test_question_setup_locks_before_answer_can_move_or_export(tmp_path: Path) -> None:
    app = create_app(settings=_settings(tmp_path / "objects"))
    with TestClient(app) as client:
        assignment = _create_unverified_sample(client)
        assignment_id = assignment["assignment_id"]
        setup = _setup(client, assignment_id)
        accepted = _mutate(client, assignment_id, setup["version"], {"kind": "accept"})
        first = accepted["questions"][0]
        candidate = client.post(
            f"/api/v2/assignments/{assignment_id}/questions/{first['question_id']}/candidates",
            json={
                "assignment_version": accepted["version"],
                "text": "Plants use sunlight to make food.",
                "origin": "student_verbatim",
                "interaction": {"kind": "direct_typed"},
            },
            headers=MUTATION_HEADERS,
        )
        assert candidate.status_code == 200, candidate.text

        for operation in (
            {"kind": "remove", "question_id": first["question_id"]},
            {
                "kind": "reorder",
                "ordered_question_ids": [
                    item["question_id"] for item in reversed(accepted["questions"])
                ],
            },
            {"kind": "reset"},
        ):
            locked = client.patch(
                f"/api/v2/assignments/{assignment_id}/question-setup",
                json={
                    "assignment_version": candidate.json()["version"],
                    "operation": operation,
                },
                headers=MUTATION_HEADERS,
            )
            assert locked.status_code == 409, locked.text
            assert locked.json()["error"]["code"] == "question_setup_locked"
