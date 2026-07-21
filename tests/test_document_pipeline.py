"""Hybrid document model, OCR normalization, semantics, and review safety tests."""
from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

from document_model import (
    AnswerRegionStatus,
    BlockSemanticRole,
    PageRole,
    ParseStatus,
    ReviewStatus,
)
from document_pipeline import _page_is_visually_structured, parse_document
from exporter import build_original_export_pdf
from manifest import build_manifest
from ocr_adapter import NullOCRAdapter, PaddleOCRAdapter, get_ocr_adapter
from review_service import apply_review_actions
from semantic_classifier import (
    GeminiSemanticClassifier,
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)


def _pdf_bytes(*, prompt: str = "Question 1: Explain the result?", answer_line: bool = True, rotation: int = 0):
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((12, 22), "Student Worksheet", fontsize=10)
    page.insert_text((12, 45), prompt, fontsize=9)
    if answer_line:
        page.draw_line((12, 70), (180, 70), width=1)
    if rotation:
        page.set_rotation(rotation)
    result = document.tobytes()
    document.close()
    return result


class _FakePaddlePipeline:
    def __init__(self, score=0.96):
        self.score = score

    def predict(self, _path):
        return [
            SimpleNamespace(
                json={
                    "res": {
                        "parsing_res_list": [
                            {
                                "block_bbox": [20, 40, 100, 80],
                                "block_label": "text",
                                "block_content": "Recognized prompt",
                                "block_id": 7,
                                "block_order": 0,
                            }
                        ],
                        "layout_det_res": {
                            "boxes": [
                                {
                                    "label": "text",
                                    "score": self.score,
                                    "coordinate": [20, 40, 100, 80],
                                }
                            ]
                        },
                    }
                }
            )
        ]


def test_paddle_adapter_normalizes_rotated_page_to_pdf_points():
    adapter = PaddleOCRAdapter(dpi=144, pipeline=_FakePaddlePipeline())
    result = adapter.extract_page(_pdf_bytes(rotation=90), 0)
    assert result.status == "parsed"
    assert result.rotation == 90
    assert result.width_points == 100
    assert result.height_points == 200
    assert result.blocks[0].bbox == (10.0, 20.0, 50.0, 40.0)
    assert result.blocks[0].confidence > 0.9


def test_paddle_adapter_marks_low_confidence_ocr_for_review():
    adapter = PaddleOCRAdapter(dpi=144, pipeline=_FakePaddlePipeline(score=0.4))
    result = adapter.extract_page(_pdf_bytes(), 0)
    assert result.status == "low_confidence"
    assert result.warnings == ["paddleocr_low_confidence"]


def test_paddle_adapter_accepts_standalone_page_image_with_pdf_geometry():
    source = fitz.open(stream=_pdf_bytes(), filetype="pdf")
    try:
        image_bytes = source[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).tobytes("png")
    finally:
        source.close()
    adapter = PaddleOCRAdapter(dpi=144, pipeline=_FakePaddlePipeline())
    result = adapter.extract_image(
        image_bytes,
        page_index=4,
        width_points=200,
        height_points=100,
        rotation=180,
    )
    assert result.page_index == 4
    assert result.rotation == 180
    assert result.blocks[0].bbox == (10.0, 20.0, 50.0, 40.0)
    assert result.metadata["input"] == "page_image"


def test_upload_request_cannot_enable_synchronous_paddle_without_explicit_worker_gate(monkeypatch):
    monkeypatch.setattr("config.ENABLE_PADDLEOCR", True)
    monkeypatch.setattr("config.ALLOW_SYNCHRONOUS_PADDLEOCR", False)
    assert isinstance(get_ocr_adapter(), NullOCRAdapter)
    monkeypatch.setattr("config.ALLOW_SYNCHRONOUS_PADDLEOCR", True)
    assert isinstance(get_ocr_adapter(), PaddleOCRAdapter)


def test_hybrid_trigger_ignores_decorative_rule_but_detects_table_grid():
    source = fitz.open()
    decorative = source.new_page(width=200, height=100)
    decorative.draw_line((10, 20), (190, 20), width=1)
    table = source.new_page(width=200, height=100)
    table.draw_line((10, 20), (190, 20), width=1)
    table.draw_line((10, 60), (190, 60), width=1)
    table.draw_line((10, 20), (10, 80), width=1)
    table.draw_line((100, 20), (100, 80), width=1)
    assert _page_is_visually_structured(source[0]) is False
    assert _page_is_visually_structured(source[1]) is True
    source.close()


def test_hybrid_trigger_detects_repeated_form_rectangles():
    source = fitz.open()
    page = source.new_page(width=200, height=140)
    page.draw_rect(fitz.Rect(10, 10, 190, 35), width=1)
    page.draw_rect(fitz.Rect(10, 45, 190, 70), width=1)
    page.draw_rect(fitz.Rect(10, 80, 190, 105), width=1)
    assert _page_is_visually_structured(page) is True
    source.close()


class _WorksheetClassifier:
    def __init__(self, *, response=True):
        self.response = response

    def classify_page(self, page, blocks, **_kwargs):
        prompt = next(block for block in blocks if "Question 1" in block.text)
        response = next((block for block in blocks if block.block_label == "answer_line"), None)
        return SemanticPageResult(
            page_index=page.page_index,
            page_role=PageRole.student_worksheet,
            confidence=0.96,
            blocks=[
                SemanticBlockDecision(
                    block_id=block.id,
                    role=(
                        BlockSemanticRole.student_prompt
                        if block.id == prompt.id
                        else block.semantic_role
                    ),
                    confidence=0.95,
                )
                for block in blocks
            ],
            tasks=[
                SemanticTaskCandidate(
                    label="1",
                    prompt_text="Explain the result?",
                    prompt_block_ids=[prompt.id],
                    response_block_ids=[response.id] if self.response and response else [],
                    response_type="short_text",
                    confidence=0.95,
                )
            ],
        )


def test_hybrid_document_has_provenance_and_auto_approves_only_physical_region(monkeypatch):
    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    document = parse_document(
        _pdf_bytes(),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(),
    )
    assert document.status == ParseStatus.parsed
    assert len(document.tasks) == 1
    task = document.tasks[0]
    assert task.id.startswith("q1-")
    assert task.source_blocks
    assert task.answer_bbox is not None
    assert task.answer_region_status == AnswerRegionStatus.detected
    assert task.review_status == ReviewStatus.auto_approved


def test_colon_label_with_same_row_vector_line_is_explicit_answer_evidence():
    source = fitz.open()
    page = source.new_page(width=200, height=100)
    page.insert_text((12, 22), "Student Worksheet", fontsize=10)
    page.insert_text((12, 50), "Student name:", fontsize=9)
    page.draw_line((75, 50), (180, 50), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    class _FieldClassifier:
        def classify_page(self, page, blocks, **_kwargs):
            prompt = next(block for block in blocks if block.text == "Student name:")
            response = next(block for block in blocks if block.block_label == "answer_line")
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.student_worksheet,
                confidence=0.96,
                blocks=[
                    SemanticBlockDecision(
                        block_id=block.id,
                        role=(
                            BlockSemanticRole.student_prompt
                            if block.id == prompt.id
                            else block.semantic_role
                        ),
                        confidence=0.95,
                    )
                    for block in blocks
                ],
                tasks=[
                    SemanticTaskCandidate(
                        label=None,
                        prompt_text="Student name:",
                        prompt_block_ids=[prompt.id],
                        response_block_ids=[response.id],
                        response_type="short_text",
                        confidence=0.95,
                    )
                ],
            )

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_FieldClassifier(),
    )
    assert parsed.tasks[0].answer_bbox is not None
    assert parsed.tasks[0].answer_region_status == AnswerRegionStatus.detected
    assert parsed.tasks[0].review_status == ReviewStatus.needs_review


def test_missing_response_region_uses_side_panel_and_needs_review():
    document = parse_document(
        _pdf_bytes(answer_line=False),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(response=False),
    )
    task = document.tasks[0]
    assert task.answer_bbox is None
    assert task.answer_region_status == AnswerRegionStatus.side_panel
    assert task.review_status == ReviewStatus.needs_review
    assert document.status == ParseStatus.low_confidence


def test_null_ocr_marks_image_only_page_requires_ocr():
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 30, 30), 0)
    pix.clear_with(220)
    page.insert_image(fitz.Rect(0, 0, 200, 100), pixmap=pix)
    pdf_bytes = document.tobytes()
    document.close()
    parsed = parse_document(pdf_bytes, ocr_adapter=NullOCRAdapter())
    assert parsed.status == ParseStatus.requires_ocr
    assert parsed.tasks == []


def test_teacher_review_accepts_side_panel_without_creating_coordinates():
    parsed = parse_document(
        _pdf_bytes(answer_line=False),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(response=False),
        review_mode="teacher",
    )
    from document_pipeline import document_questions

    manifest = build_manifest(
        assignment_id="teacher",
        title=parsed.title,
        questions=document_questions(parsed),
        review_mode="teacher",
        review_status="draft",
        document=parsed,
    )
    task_id = manifest.questions[0].task_id
    reviewed = apply_review_actions(
        manifest,
        [{"action": "accept", "task_id": task_id}],
        pdf_bytes=_pdf_bytes(answer_line=False),
        finalize=True,
    )
    question = reviewed.questions[0]
    assert reviewed.review_status == "approved"
    assert question.approved is True
    assert question.answer_region is None
    assert question.answer_region_status == "side_panel"


def test_teacher_review_rejects_answer_bbox_outside_original_page():
    pdf_bytes = _pdf_bytes(answer_line=False)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(response=False),
        review_mode="teacher",
    )
    from document_pipeline import document_questions

    manifest = build_manifest(
        assignment_id="teacher",
        title=parsed.title,
        questions=document_questions(parsed),
        review_mode="teacher",
        review_status="draft",
        document=parsed,
    )
    with pytest.raises(ValueError, match="outside page bounds"):
        apply_review_actions(
            manifest,
            [
                {
                    "action": "edit",
                    "task_id": manifest.questions[0].task_id,
                    "answer_bbox": [10, 10, 500, 500],
                    "approve": True,
                }
            ],
            pdf_bytes=pdf_bytes,
        )


def test_side_panel_export_preserves_original_and_appends_full_answer():
    source = _pdf_bytes(answer_line=False)
    exported = build_original_export_pdf(
        source,
        [{"id": 1, "label": "1", "text": "Explain", "page": 1, "answer_region": None}],
        [{"question_id": 1, "answer_text": "A confirmed side-panel answer"}],
    )
    document = fitz.open(stream=exported, filetype="pdf")
    try:
        assert document.page_count == 2
        assert "Student Worksheet" in document[0].get_text()
        assert "A confirmed side-panel answer" in document[1].get_text()
        assert "no approved writable region" in document[1].get_text()
    finally:
        document.close()


def test_invalid_semantic_output_is_rejected_without_tasks_or_content_logs(caplog):
    class _Models:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(
                parsed={
                    "page_index": 0,
                    "page_role": "student_worksheet",
                    "confidence": 0.99,
                    "blocks": [],
                    "tasks": [
                        {
                            "label": "1",
                            "prompt_text": "Invented",
                            "prompt_block_ids": ["missing"],
                            "response_block_ids": [],
                            "response_type": "short_text",
                            "confidence": 0.99,
                        }
                    ],
                    "warnings": [],
                },
                text="",
            )

    classifier = GeminiSemanticClassifier(client=SimpleNamespace(models=_Models()), model="test")
    parsed = parse_document(
        _pdf_bytes(),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=classifier,
    )
    assert parsed.tasks == []
    assert parsed.pages[0].page_role == PageRole.unknown
    assert "page_0:semantic_result_rejected" in parsed.warnings
    assert "Student Worksheet" not in caplog.text
    assert "Invented" not in caplog.text


def test_semantic_schema_rejects_duplicate_tasks_before_id_generation():
    candidate = SemanticTaskCandidate(
        label="3a",
        prompt_text="Explain.",
        prompt_block_ids=["block-1"],
        response_block_ids=[],
        response_type="short_text",
        confidence=0.9,
    )
    with pytest.raises(ValueError, match="semantic tasks must be unique"):
        SemanticPageResult(
            page_index=0,
            page_role=PageRole.student_worksheet,
            confidence=0.9,
            blocks=[],
            tasks=[candidate, candidate.model_copy()],
        )


def test_teacher_can_merge_then_split_with_block_provenance():
    pdf_bytes = _pdf_bytes()
    questions = [
        {
            "id": 1,
            "task_id": "q1-a",
            "label": "1",
            "text": "First prompt",
            "page": 1,
            "page_index": 0,
            "source_blocks": ["block-a"],
        },
        {
            "id": 2,
            "task_id": "q2-b",
            "label": "2",
            "text": "Second prompt",
            "page": 1,
            "page_index": 0,
            "source_blocks": ["block-b"],
        },
    ]
    manifest = build_manifest(
        assignment_id="teacher",
        title="Packet",
        questions=questions,
        review_mode="teacher",
        review_status="draft",
    )
    merged = apply_review_actions(
        manifest,
        [{"action": "merge", "task_ids": ["q1-a", "q2-b"]}],
        pdf_bytes=pdf_bytes,
    )
    assert len(merged.questions) == 1
    merged_task = merged.questions[0]
    assert merged_task.source_blocks == ["block-a", "block-b"]
    split = apply_review_actions(
        merged,
        [
            {
                "action": "split",
                "task_id": merged_task.task_id,
                "parts": [
                    {"prompt_text": "First prompt", "source_blocks": ["block-a"]},
                    {"prompt_text": "Second prompt", "source_blocks": ["block-b"]},
                ],
            }
        ],
        pdf_bytes=pdf_bytes,
    )
    assert [question.id for question in split.questions] == [1, 2]
    assert len({question.task_id for question in split.questions}) == 2
    assert all(question.answer_region_status == "side_panel" for question in split.questions)
