"""Stage 4 product-flow coverage for official canonical sample worksheets."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

import assignment_service
import config
import main
from evaluation.canonical_v1.evaluate import _CanonicalEvidenceSelector
from evaluation.canonical_v1.schema import CanonicalManifest
from sample_catalog import DEFAULT_SAMPLE_ID, get_product_sample, list_product_samples

MANIFEST = CanonicalManifest.model_validate_json(
    Path("evaluation/canonical_v1/generated/manifest.json").read_text(encoding="utf-8")
)
EXPECTED_BY_ID = {document.canonical_id: document for document in MANIFEST.documents}
SUPPORTED_SAMPLE_IDS = {"canonical-short-answer-ecosystems"}


class _CatalogEvidenceClassifier:
    """Select only among Stage 3-extracted blocks for offline product-flow tests."""

    parser_name = "stage4-product-flow+canonical_evidence_selector"

    def __init__(self, expected):
        self._selector = _CanonicalEvidenceSelector(expected)

    def classify_page(self, page, blocks, **kwargs):
        return self._selector.classify_page(page, blocks, **kwargs)


def test_product_catalog_contains_only_contract_supported_fixture():
    assert {sample.canonical_id for sample in list_product_samples()} == SUPPORTED_SAMPLE_IDS
    assert get_product_sample(None).canonical_id == "canonical-short-answer-ecosystems"
    assert get_product_sample("1").canonical_id == "canonical-short-answer-ecosystems"
    with pytest.raises(KeyError):
        get_product_sample("canonical-choice-digital-safety")
    with pytest.raises(KeyError):
        get_product_sample("canonical-numeric-everyday-math")


@pytest.fixture
def local_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CLAROS_DEMO_MODE", False)
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_STORAGE_DIR", str(tmp_path / ".claros-data"))
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_SEMANTICS", True)
    monkeypatch.setattr(config, "ALLOW_SYNCHRONOUS_DOCUMENT_SEMANTICS", True)


def _install_sample_classifier(monkeypatch, sample_id: str):
    expected = EXPECTED_BY_ID[sample_id]

    def fake_parse_supported_worksheet(pdf_bytes, *, semantic_classifier=None, **kwargs):
        del semantic_classifier
        from document_pipeline import parse_supported_worksheet
        from ocr_adapter import NullOCRAdapter

        return parse_supported_worksheet(
            pdf_bytes,
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=_CatalogEvidenceClassifier(expected),
            **kwargs,
        )

    monkeypatch.setattr(
        assignment_service,
        "parse_supported_worksheet",
        fake_parse_supported_worksheet,
    )


def _upload_sample(client: TestClient, sample_id: str) -> dict:
    sample = get_product_sample(sample_id)
    response = client.post(
        "/upload",
        files={
            "file": (
                sample.upload_filename,
                sample.pdf_path.read_bytes(),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _writable_targets(payload: dict) -> list[dict]:
    return [
        question for question in payload["questions"] if question.get("response_target_id") and question.get("task_id")
    ]


@pytest.mark.parametrize(
    "sample_id",
    [sample.canonical_id for sample in list_product_samples()],
)
def test_official_sample_catalog_and_pdf_routes(sample_id):
    sample = get_product_sample(sample_id)
    with TestClient(main.app) as client:
        catalog = client.get("/api/samples")
        assert catalog.status_code == 200
        body = catalog.json()
        assert body["default_sample_id"] == DEFAULT_SAMPLE_ID
        assert {entry["id"] for entry in body["samples"]} == {item.canonical_id for item in list_product_samples()}

        pdf = client.get(sample.to_public_dict()["pdf_url"])
        assert pdf.status_code == 200
        assert pdf.headers.get("content-type", "").startswith("application/pdf")
        assert pdf.content[:4] == b"%PDF"
        assert pdf.content == sample.pdf_path.read_bytes()

        preview = client.get(sample.to_public_dict()["preview_url"])
        assert preview.status_code == 200
        assert preview.headers.get("content-type", "").startswith("image/png")
        assert preview.content.startswith(b"\x89PNG")


def test_legacy_sample_alias_serves_default_official_pdf():
    default = get_product_sample(None)
    with TestClient(main.app) as client:
        response = client.get("/sample-assignment.pdf")
        assert response.status_code == 200
        assert response.content == default.pdf_path.read_bytes()


@pytest.mark.parametrize(
    "sample_id",
    [sample.canonical_id for sample in list_product_samples()],
)
def test_canonical_sample_uses_normal_upload_not_demo_parser(
    local_storage,
    monkeypatch,
    sample_id,
):
    _install_sample_classifier(monkeypatch, sample_id)
    with TestClient(main.app) as client:
        payload = _upload_sample(client, sample_id)
        assert payload["parser"] != "offline-synthetic-fixture-v1"
        assert "hybrid" in payload["parser"] or "physical" in payload["parser"] or "stage4" in payload["parser"]
        assert len(payload["questions"]) >= 5
        assert all(question.get("task_id") for question in payload["questions"])


@pytest.mark.parametrize(
    "sample_id",
    [sample.canonical_id for sample in list_product_samples()],
)
def test_canonical_sample_task_switch_partial_export_delete_and_retry(
    local_storage,
    monkeypatch,
    sample_id,
):
    _install_sample_classifier(monkeypatch, sample_id)
    sample = get_product_sample(sample_id)

    with TestClient(main.app) as client:
        first = _upload_sample(client, sample_id)
        targets = _writable_targets(first)
        assert len(targets) >= 2
        headers = {"X-Assignment-Capability": first["assignment_capability"]}

        started = client.post(
            "/api/session/start",
            json={"assignment_id": first["assignment_id"]},
            headers=headers,
        )
        assert started.status_code == 200, started.text
        session = started.json()

        zero_export = client.post(
            f"/export/{first['assignment_id']}",
            json={
                "session_id": session["session_id"],
                "session_secret": session["session_secret"],
            },
            headers=headers,
        )
        # Product export requires at least one confirmed written answer.
        assert zero_export.status_code == 409, zero_export.text

        answers = {}
        for index, target in enumerate(targets[:2], start=1):
            answer = f"Sample answer {index} for {sample.sample_name}"
            answers[target["response_target_id"]] = answer
            confirmed = client.post(
                f"/api/session/{session['session_id']}/confirm",
                json={
                    "session_secret": session["session_secret"],
                    "task_id": target["task_id"],
                    "response_region_id": target["response_target_id"],
                    "answer_text": answer,
                },
                headers=headers,
            )
            assert confirmed.status_code == 200, confirmed.text
            write_token = confirmed.json()["write_token"]

            # Invalid token must fail closed and remain retryable with the real token.
            failed = client.post(
                f"/api/write/{first['assignment_id']}",
                json={
                    "task_id": target["task_id"],
                    "response_region_id": target["response_target_id"],
                    "conversation": [],
                    "answer_candidate": answer,
                    "write_token": "not-a-valid-token",
                    "session_id": session["session_id"],
                    "session_secret": session["session_secret"],
                },
                headers=headers,
            )
            assert failed.status_code in {400, 401, 403, 409}, failed.text

            written = client.post(
                f"/api/write/{first['assignment_id']}",
                json={
                    "task_id": target["task_id"],
                    "response_region_id": target["response_target_id"],
                    "conversation": [],
                    "answer_candidate": answer,
                    "write_token": write_token,
                    "session_id": session["session_id"],
                    "session_secret": session["session_secret"],
                },
                headers=headers,
            )
            assert written.status_code == 200, written.text

        restored = client.post(
            f"/api/session/{session['session_id']}/restore",
            json={
                "session_secret": session["session_secret"],
                "assignment_id": first["assignment_id"],
            },
            headers=headers,
        )
        assert restored.status_code == 200, restored.text
        restored_body = restored.json()
        for response_region_id, answer in answers.items():
            restored_response = restored_body["responses"][response_region_id]
            assert restored_response["confirmed"] is True
            assert restored_response["written"] is True
            assert restored_response["confirmed_answer"] == answer
            assert restored_response["written_answer"] == answer

        partial_export = client.post(
            f"/export/{first['assignment_id']}",
            json={
                "session_id": session["session_id"],
                "session_secret": session["session_secret"],
            },
            headers=headers,
        )
        assert partial_export.status_code == 200, partial_export.text
        partial_doc = fitz.open(stream=partial_export.content, filetype="pdf")
        try:
            exported_text = "\n".join(page.get_text() for page in partial_doc)
            for answer in answers.values():
                assert answer in exported_text
        finally:
            partial_doc.close()

        # Complete remaining writable targets for full-completion coverage.
        for index, target in enumerate(targets[2:], start=3):
            answer = f"Sample answer {index} for {sample.sample_name}"
            confirmed = client.post(
                f"/api/session/{session['session_id']}/confirm",
                json={
                    "session_secret": session["session_secret"],
                    "task_id": target["task_id"],
                    "response_region_id": target["response_target_id"],
                    "answer_text": answer,
                },
                headers=headers,
            )
            assert confirmed.status_code == 200, confirmed.text
            written = client.post(
                f"/api/write/{first['assignment_id']}",
                json={
                    "task_id": target["task_id"],
                    "response_region_id": target["response_target_id"],
                    "conversation": [],
                    "answer_candidate": answer,
                    "write_token": confirmed.json()["write_token"],
                    "session_id": session["session_id"],
                    "session_secret": session["session_secret"],
                },
                headers=headers,
            )
            assert written.status_code == 200, written.text
            answers[target["response_target_id"]] = answer

        full_export = client.post(
            f"/export/{first['assignment_id']}",
            json={
                "session_id": session["session_id"],
                "session_secret": session["session_secret"],
            },
            headers=headers,
        )
        assert full_export.status_code == 200, full_export.text
        full_doc = fitz.open(stream=full_export.content, filetype="pdf")
        try:
            exported_text = "\n".join(page.get_text() for page in full_doc)
            for answer in answers.values():
                assert answer in exported_text
        finally:
            full_doc.close()

        deleted = client.delete(f"/api/assignments/{first['assignment_id']}", headers=headers)
        assert deleted.status_code == 200, deleted.text

        missing = client.get(
            f"/api/assignments/{first['assignment_id']}/parse-diagnostics",
            headers=headers,
        )
        assert missing.status_code in {404, 410}

        # Replacement upload creates a fresh assignment on the same normal path.
        second = _upload_sample(client, sample_id)
        assert second["assignment_id"] != first["assignment_id"]
        assert second["parser"] != "offline-synthetic-fixture-v1"
