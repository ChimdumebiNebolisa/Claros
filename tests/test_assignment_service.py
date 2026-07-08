"""Assignment service unit tests."""
import pytest
from fastapi import HTTPException

import assignment_service
from tests.conftest import TEST_ASSIGNMENT_ID


def test_export_filename_strips_unsafe_characters():
    assert assignment_service._export_filename("550e8400-e29b-41d4-a716-446655440000") == (
        "claros-550e8400-e29b-41d4-a716-446655440000.pdf"
    )
    assert assignment_service._export_filename('..\\..\\550e8400-e29b-41d4-a716-446655440000') == (
        "claros-550e8400-e29b-41d4-a716-446655440000.pdf"
    )


def test_format_assignment_text_joins_questions():
    text = assignment_service.format_assignment_text(
        "Quiz",
        [{"id": 1, "text": "First?"}, {"id": 2, "text": "Second?"}],
    )
    assert "Quiz" in text
    assert "Question 1: First?" in text
    assert "Question 2: Second?" in text


def test_build_export_response_maps_value_error_to_404(monkeypatch):
    def raise_missing(_assignment_id: str):
        raise ValueError("missing")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_missing)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 404


def test_build_export_response_maps_backend_error_to_500(monkeypatch):
    def raise_backend(_assignment_id: str):
        raise RuntimeError("gcs down")

    monkeypatch.setattr(assignment_service, "load_assignment_from_gcs", raise_backend)

    with pytest.raises(HTTPException) as exc:
        assignment_service.build_export_response(TEST_ASSIGNMENT_ID, [])
    assert exc.value.status_code == 500
