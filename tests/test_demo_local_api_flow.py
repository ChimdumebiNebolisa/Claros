"""End-to-end API coverage for the offline hero demo using local storage."""
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

import config
import main


def _upload_hero(client: TestClient) -> dict:
    response = client.post(
        "/upload",
        files={"file": ("hero_worksheet.pdf", Path("demo/hero_worksheet.pdf").read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_offline_hero_upload_confirm_write_export_and_second_upload(monkeypatch, tmp_path):
    """The local demo completes its safe flow without GCS or a live provider."""
    monkeypatch.setattr(config, "CLAROS_DEMO_MODE", True)
    monkeypatch.setattr(config, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(config, "LOCAL_STORAGE_DIR", str(tmp_path / ".claros-data"))

    with TestClient(main.app) as client:
        first = _upload_hero(client)
        assert first["parser"] == "offline-synthetic-fixture-v1"
        assert len(first["questions"]) == 4
        assert first["questions"][1]["answer_region_status"] == "approved"
        assert first["questions"][3]["answer_region_status"] == "side_panel"

        headers = {"X-Assignment-Capability": first["assignment_capability"]}
        started = client.post("/api/session/start", json={"assignment_id": first["assignment_id"]}, headers=headers)
        assert started.status_code == 200, started.text
        session = started.json()

        answer = "The river water was clearer after the litter was removed."
        confirmed = client.post(
            f"/api/session/{session['session_id']}/confirm",
            json={"session_secret": session["session_secret"], "question_id": 2, "answer_text": answer},
            headers=headers,
        )
        assert confirmed.status_code == 200, confirmed.text

        written = client.post(
            f"/api/write/{first['assignment_id']}",
            json={
                "question_id": 2,
                "conversation": [],
                "answer_candidate": answer,
                "write_token": confirmed.json()["write_token"],
                "session_id": session["session_id"],
                "session_secret": session["session_secret"],
            },
            headers=headers,
        )
        assert written.status_code == 200, written.text
        assert answer in written.text

        exported = client.post(
            f"/export/{first['assignment_id']}",
            json={"session_id": session["session_id"], "session_secret": session["session_secret"]},
            headers=headers,
        )
        assert exported.status_code == 200, exported.text
        document = fitz.open(stream=exported.content, filetype="pdf")
        try:
            assert document.page_count == 1
            assert answer in document[0].get_text()
        finally:
            document.close()

        second = _upload_hero(client)
        assert second["assignment_id"] != first["assignment_id"]
        second_headers = {"X-Assignment-Capability": second["assignment_capability"]}
        second_session = client.post(
            "/api/session/start", json={"assignment_id": second["assignment_id"]}, headers=second_headers
        )
        assert second_session.status_code == 200, second_session.text
        restored = client.post(
            f"/api/session/{second_session.json()['session_id']}/restore",
            json={"session_secret": second_session.json()["session_secret"]},
            headers=second_headers,
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["questions"]["2"]["confirmed"] is False
