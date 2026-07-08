"""Upload endpoint validation: size limits and PDF signature checks."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

import config
import main as main_module
import storage

client = TestClient(main_module.app)

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.fixture
def upload_mocks(monkeypatch):
    monkeypatch.setattr(storage, "upload_pdf_to_gcs", lambda *_a, **_k: "gs://bucket/assignments/x/assignment.pdf")

    def fake_parse(_path):
        from types import SimpleNamespace

        return "Test Title", [SimpleNamespace(id=1, text="Question one?")]

    monkeypatch.setattr(main_module, "parse_pdf", fake_parse)


def test_upload_rejects_oversize_file(monkeypatch):
    monkeypatch.setattr(main_module.config, "MAX_UPLOAD_BYTES", 32)
    response = client.post(
        "/upload",
        files={"file": ("big.pdf", BytesIO(_MINIMAL_PDF * 4), "application/pdf")},
    )
    assert response.status_code == 413
    assert "maximum upload size" in response.json()["detail"].lower()


def test_upload_rejects_non_pdf_bytes_with_pdf_extension():
    response = client.post(
        "/upload",
        files={"file": ("fake.pdf", BytesIO(b"not-a-pdf"), "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid pdf" in response.json()["detail"].lower()


def test_upload_accepts_pdf_with_leading_whitespace(upload_mocks):
    response = client.post(
        "/upload",
        files={"file": ("worksheet.pdf", BytesIO(b" \r\n" + _MINIMAL_PDF), "application/pdf")},
    )
    assert response.status_code == 200


def test_upload_accepts_pdf_with_utf8_bom(upload_mocks):
    response = client.post(
        "/upload",
        files={"file": ("worksheet.pdf", BytesIO(b"\xef\xbb\xbf" + _MINIMAL_PDF), "application/pdf")},
    )
    assert response.status_code == 200


def test_upload_rejects_non_pdf_extension():
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", BytesIO(b"plain text"), "text/plain")},
    )
    assert response.status_code == 400
    assert "only pdf" in response.json()["detail"].lower()


def test_upload_accepts_valid_pdf(upload_mocks):
    response = client.post(
        "/upload",
        files={"file": ("worksheet.pdf", BytesIO(_MINIMAL_PDF), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "assignment_id" in body
    assert body["title"] == "Test Title"
    assert body["questions"] == [{"id": 1, "text": "Question one?"}]
