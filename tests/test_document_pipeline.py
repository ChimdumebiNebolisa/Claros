"""Hybrid document model, OCR normalization, semantics, and review safety tests."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import fitz
import pytest

from document_model import (
    BlockSemanticRole,
    DocumentBlock,
    DocumentPage,
    DocumentResponseRegion,
    DocumentTask,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseRegionType,
    ResponseSafety,
    ReviewStatus,
    SourceKind,
    TaskResponseRole,
    TaskResponseLink,
)
from document_pipeline import (
    _build_tasks,
    _page_is_visually_structured,
    _vector_rectangle_bboxes,
    document_questions,
    parse_document,
)
from exporter import build_canonical_export_pdf, build_original_export_pdf
from manifest import build_manifest
from ocr_adapter import NullOCRAdapter, PaddleOCRAdapter, get_ocr_adapter
from review_service import apply_review_actions
from semantic_classifier import (
    GeminiSemanticClassifier,
    NullSemanticClassifier,
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)


def _pdf_bytes(
    *,
    prompt: str = "Question 1: Explain the result?",
    answer_line: bool = True,
    answer_line_width: float = 1,
    rotation: int = 0,
    crop: bool = False,
    user_unit: int | None = None,
):
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((12, 22), "Student Worksheet", fontsize=10)
    page.insert_text((12, 45), prompt, fontsize=9)
    page.insert_text((12, 60), "Answer:", fontsize=9)
    if answer_line:
        page.draw_line((12, 70), (180, 70), width=answer_line_width)
    if crop:
        page.set_cropbox(fitz.Rect(10, 10, 190, 90))
    if rotation:
        page.set_rotation(rotation)
    if user_unit is not None:
        document.xref_set_key(page.xref, "UserUnit", str(user_unit))
    result = document.tobytes()
    document.close()
    return result


def _add_visible_widget(page: fitz.Page, widget: fitz.Widget) -> None:
    """Add a widget whose AcroForm appearance visibly marks its rectangle."""
    widget.border_color = (0, 0, 0)
    widget.border_width = 1
    page.add_widget(widget)


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
    pdf_bytes = _pdf_bytes()
    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    document = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(),
    )
    assert document.status == ParseStatus.parsed
    assert document.source_sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    assert len(document.tasks) == 1
    task = document.tasks[0]
    assert task.id.startswith("q-")
    assert task.prompt_block_ids
    assert len(task.response_links) == 1
    region = document.response_region(task.response_links[0].response_region_id)
    assert region.bbox is not None
    assert region.safety == ResponseSafety.approved
    assert task.review_status == ReviewStatus.auto_approved


def test_rotated_pdf_uses_unrotated_evidence_bounds_and_routes_targets_to_the_side_panel(monkeypatch):
    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        _pdf_bytes(rotation=90),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(),
    )

    page = parsed.pages[0]
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert (page.width_points, page.height_points, page.rotation) == (200.0, 100.0, 90)
    assert region.safety == ResponseSafety.unsafe
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review
    assert "page_0:transformed_physical_targets_side_panel_only" in parsed.warnings


def test_cropped_pdf_routes_physical_targets_to_the_side_panel_until_transformed():
    parsed = parse_document(
        _pdf_bytes(crop=True),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(),
    )

    page = parsed.pages[0]
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert page.display_transform_required is True
    assert region.safety == ResponseSafety.unsafe
    assert task.side_panel_fallback is True


def test_user_unit_pdf_uses_scaled_extraction_bounds_and_routes_targets_to_the_side_panel():
    parsed = parse_document(
        _pdf_bytes(user_unit=2, answer_line_width=0.5),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(),
    )

    page = parsed.pages[0]
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert (page.width_points, page.height_points) == (400.0, 200.0)
    assert page.display_transform_required is True
    assert region.safety == ResponseSafety.unsafe
    assert task.side_panel_fallback is True
    assert "page_0:transformed_physical_targets_side_panel_only" in parsed.warnings


def test_transformed_paddle_geometry_is_retained_as_text_only(monkeypatch):
    from ocr_adapter import OCRPageResult, OCRTextBlock

    class _DisplayFrameOCR:
        def extract_page(self, _pdf_bytes, page_index):
            return OCRPageResult(
                page_index=page_index,
                blocks=[
                    OCRTextBlock(
                        text="OCR-only prompt",
                        bbox=(10, 150, 80, 180),
                        confidence=0.95,
                        label="form_field",
                        source_id="outside-unrotated-height",
                    )
                ],
                engine="test",
                warnings=[],
                width_points=100,
                height_points=200,
                rotation=90,
            )

    parsed = parse_document(
        _pdf_bytes(rotation=90),
        ocr_adapter=_DisplayFrameOCR(),
        semantic_classifier=NullSemanticClassifier(),
        paddle_all_pages=True,
    )

    paddle = next(block for block in parsed.blocks if block.source == SourceKind.paddleocr)
    assert paddle.bbox is None
    assert paddle.polygon is None
    assert "page_0:paddle_geometry_omitted_for_transformed_page" in parsed.warnings


def test_clipped_crop_geometry_is_sanitized_before_canonical_validation():
    source = fitz.open()
    page = source.new_page(width=200, height=100)
    page.insert_text((55, 30), "What is your answer?", fontsize=9)
    page.draw_line((0, 70), (200, 70))
    page.set_cropbox(fitz.Rect(50, 0, 150, 100))
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    assert parsed.pages[0].display_transform_required is True
    assert all(
        block.bbox is None
        or (0 <= block.bbox[0] < block.bbox[2] <= 100 and 0 <= block.bbox[1] < block.bbox[3] <= 100)
        for block in parsed.blocks
    )
    assert "page_0:extraction_geometry_clipped_or_omitted" in parsed.warnings


def test_clipped_vector_geometry_is_never_auto_approved_or_out_of_bounds():
    source = fitz.open()
    page = source.new_page(width=200, height=100)
    page.insert_text((12, 45), "Question 1: Explain the result?", fontsize=9)
    page.draw_line((-10, 70), (210, 70))
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    clipped = next(block for block in parsed.blocks if block.block_label == "clipped_response_candidate")
    assert clipped.bbox == [0.0, 65.0, 200.0, 89.0]
    assert clipped.semantic_role == BlockSemanticRole.unknown


def test_duplicate_semantic_response_selection_fails_closed_to_no_tasks():
    class _DuplicateResponseClassifier:
        def classify_page(self, page, blocks, **_kwargs):
            response = next(block for block in blocks if block.block_label == "answer_line")
            prompt_blocks = [block for block in blocks if block.text.strip()]
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.student_worksheet,
                confidence=0.96,
                blocks=[
                    SemanticBlockDecision(
                        block_id=block.id,
                        role=BlockSemanticRole.student_prompt,
                        confidence=0.95,
                    )
                    for block in blocks
                ],
                tasks=[
                    SemanticTaskCandidate(
                        label="1",
                        prompt_text="ignored",
                        prompt_block_ids=[prompt_blocks[0].id],
                        response_block_ids=[response.id],
                        response_type="short_text",
                        confidence=0.95,
                    ),
                    SemanticTaskCandidate(
                        label="2",
                        prompt_text="ignored",
                        prompt_block_ids=[prompt_blocks[-1].id],
                        response_block_ids=[response.id],
                        response_type="short_text",
                        confidence=0.95,
                    ),
                ],
            )

    parsed = parse_document(
        _pdf_bytes(),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_DuplicateResponseClassifier(),
    )
    assert parsed.tasks == []
    assert parsed.response_regions == []
    assert parsed.status == ParseStatus.low_confidence
    assert "semantic_task_materialization_rejected" in parsed.warnings


def test_semantic_candidate_order_cannot_change_canonical_task_order_or_legacy_display_ids():
    blocks = [
        DocumentBlock(
            id="prompt-first",
            page_index=0,
            reading_order=0,
            text="First physical prompt.",
            block_label="text",
            bbox=[12, 20, 180, 36],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="response-first",
            page_index=0,
            reading_order=1,
            text="",
            block_label="answer_line",
            bbox=[12, 42, 180, 56],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
        DocumentBlock(
            id="prompt-second",
            page_index=0,
            reading_order=2,
            text="Second physical prompt.",
            block_label="text",
            bbox=[12, 68, 180, 84],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="response-second",
            page_index=0,
            reading_order=3,
            text="",
            block_label="answer_line",
            bbox=[12, 90, 180, 104],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
    ]

    def materialize(reverse: bool):
        candidates = [
            SemanticTaskCandidate(
                label="model-second",
                prompt_text="ignored",
                prompt_block_ids=["prompt-second"],
                response_block_ids=["response-second"],
                response_type="short_text",
                confidence=0.99,
            ),
            SemanticTaskCandidate(
                label="model-first",
                prompt_text="ignored",
                prompt_block_ids=["prompt-first"],
                response_block_ids=["response-first"],
                response_type="short_text",
                confidence=0.99,
            ),
        ]
        if reverse:
            candidates.reverse()
        result = SemanticPageResult(
            page_index=0,
            page_role=PageRole.student_worksheet,
            confidence=0.99,
            blocks=[],
            tasks=candidates,
        )
        return _build_tasks(blocks, [result], review_mode="direct")[0]

    first = materialize(reverse=False)
    reversed_candidates = materialize(reverse=True)
    first_identity = [(task.id, task.legacy_question_id, task.order) for task in first]
    reversed_identity = [
        (task.id, task.legacy_question_id, task.order) for task in reversed_candidates
    ]
    assert first_identity == reversed_identity
    assert [task.prompt_text for task in first] == [
        "First physical prompt.",
        "Second physical prompt.",
    ]


def test_distinct_overlapping_semantic_response_blocks_fail_closed():
    blocks = [
        DocumentBlock(
            id="prompt-one",
            page_index=0,
            reading_order=0,
            text="First prompt.",
            block_label="text",
            bbox=[12, 20, 180, 36],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="response-one",
            page_index=0,
            reading_order=1,
            text="",
            block_label="answer_line",
            bbox=[12, 42, 180, 62],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
        DocumentBlock(
            id="prompt-two",
            page_index=0,
            reading_order=2,
            text="Second prompt.",
            block_label="text",
            bbox=[12, 70, 180, 86],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="response-two",
            page_index=0,
            reading_order=3,
            text="",
            block_label="answer_line",
            bbox=[30, 54, 180, 78],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
    ]
    result = SemanticPageResult(
        page_index=0,
        page_role=PageRole.student_worksheet,
        confidence=0.99,
        blocks=[],
        tasks=[
            SemanticTaskCandidate(
                prompt_text="ignored",
                prompt_block_ids=["prompt-one"],
                response_block_ids=["response-one"],
                response_type="short_text",
                confidence=0.99,
            ),
            SemanticTaskCandidate(
                prompt_text="ignored",
                prompt_block_ids=["prompt-two"],
                response_block_ids=["response-two"],
                response_type="short_text",
                confidence=0.99,
            ),
        ],
    )

    with pytest.raises(ValueError, match="overlapping physical response blocks"):
        _build_tasks(blocks, [result], review_mode="direct")


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
    task = parsed.tasks[0]
    assert len(task.response_links) == 1
    assert parsed.response_region(task.response_links[0].response_region_id).safety == ResponseSafety.needs_review
    assert parsed.tasks[0].review_status == ReviewStatus.needs_review


def test_missing_response_region_uses_side_panel_and_needs_review():
    document = parse_document(
        _pdf_bytes(answer_line=False),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_WorksheetClassifier(response=False),
    )
    task = document.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
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


def test_gemini_provider_failure_falls_back_without_content_logs(caplog):
    class _Models:
        def generate_content(self, **_kwargs):
            raise RuntimeError("provider unavailable")

    classifier = GeminiSemanticClassifier(client=SimpleNamespace(models=_Models()), model="gemini-test")
    parsed = parse_document(
        _pdf_bytes(),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=classifier,
    )
    assert parsed.tasks == []
    assert parsed.pages[0].page_role == PageRole.unknown
    assert "page_0:semantic_result_rejected" in parsed.warnings
    assert "Student Worksheet" not in caplog.text
    assert "provider unavailable" not in caplog.text


def test_gemini_semantic_tasks_reconstruct_prompt_text_from_selected_source_blocks():
    page = DocumentPage(page_index=0, width_points=612, height_points=792, block_ids=["prompt", "response"])
    blocks = [
        DocumentBlock(
            id="prompt",
            page_index=0,
            reading_order=1,
            text="Use the evidence from the table.",
            block_label="native_text",
            bbox=[10, 10, 300, 30],
            confidence=1.0,
            source=SourceKind.native_pdf,
        ),
        DocumentBlock(
            id="response",
            page_index=0,
            reading_order=2,
            text="",
            block_label="answer_line",
            bbox=[10, 40, 300, 60],
            confidence=1.0,
            source=SourceKind.pdf_geometry,
        ),
    ]

    class _Models:
        def generate_content(self, **_kwargs):
            return SimpleNamespace(
                parsed={
                    "page_index": 0,
                    "page_role": "student_worksheet",
                    "confidence": 1.0,
                    "blocks": [
                        {"block_id": "prompt", "role": "student_prompt", "confidence": 1.0},
                        {"block_id": "response", "role": "response_area", "confidence": 1.0},
                    ],
                    "tasks": [
                        {
                            "label": "1",
                            "prompt_text": "Model-authored replacement text",
                            "prompt_block_ids": ["prompt"],
                            "response_block_ids": ["response"],
                            "response_type": "short_text",
                            "confidence": 1.0,
                        }
                    ],
                    "warnings": [],
                },
                text="",
            )

    result = GeminiSemanticClassifier(client=SimpleNamespace(models=_Models()), model="gemini-test").classify_page(
        page,
        blocks,
    )
    assert result.tasks[0].prompt_text == "Use the evidence from the table."


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


def test_teacher_cannot_merge_quarantined_legacy_tasks_without_source_evidence():
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
    with pytest.raises(ValueError, match="source-backed prompt evidence"):
        apply_review_actions(
            manifest,
            [{"action": "merge", "task_ids": ["q1-a", "q2-b"]}],
        )


class _SourceSelector:
    """Deterministic semantic-selection fixture for canonical PDF tests."""

    def __init__(self, task_builder):
        self._task_builder = task_builder

    def classify_page(self, page, blocks, **_kwargs):
        tasks = self._task_builder(page, blocks)
        prompt_ids = {
            block_id
            for task in tasks
            for block_id in task.prompt_block_ids
        }
        return SemanticPageResult(
            page_index=page.page_index,
            page_role=PageRole.student_worksheet,
            confidence=0.99,
            blocks=[
                SemanticBlockDecision(
                    block_id=block.id,
                    role=(
                        BlockSemanticRole.student_prompt
                        if block.id in prompt_ids
                        else block.semantic_role
                    ),
                    confidence=0.99,
                )
                for block in blocks
            ],
            tasks=tasks,
        )


def _canonical_short_answer_pdf() -> bytes:
    source = fitz.open()
    page = source.new_page(width=330, height=220)
    page.insert_text((15, 22), "Short Answer Practice", fontsize=10)
    page.insert_text((15, 48), "1. Calculate 3 + 4.", fontsize=10)
    page.insert_text((15, 64), "Answer:", fontsize=10)
    page.draw_line((15, 76), (300, 76), width=1)
    page.insert_text((15, 108), "Show your work:", fontsize=10)
    page.draw_rect(fitz.Rect(15, 120, 300, 202), width=1)
    result = source.tobytes()
    source.close()
    return result


def test_stage3_short_answer_preserves_distinct_answer_and_show_work_regions(monkeypatch):
    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        responses = [
            block
            for block in blocks
            if block.block_label in {"answer_line", "writable_area"}
        ]
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in responses],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    pdf_bytes = _canonical_short_answer_pdf()
    first = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    second = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    task = first.tasks[0]
    regions = [first.response_region(link.response_region_id) for link in task.response_links]
    assert [region.region_type for region in regions] == [
        ResponseRegionType.answer_line,
        ResponseRegionType.writable_area,
    ]
    assert [link.role for link in task.response_links] == [
        TaskResponseRole.answer,
        TaskResponseRole.show_work,
    ]
    assert all(region.safety == ResponseSafety.approved for region in regions)
    assert task.side_panel_fallback is False
    assert [block.id for block in first.blocks if block.source == SourceKind.pdf_geometry] == [
        block.id for block in second.blocks if block.source == SourceKind.pdf_geometry
    ]
    assert [(region.id, region.bbox) for region in regions] == [
        (second.response_region(link.response_region_id).id, second.response_region(link.response_region_id).bbox)
        for link in second.tasks[0].response_links
    ]


def test_stage3_multiple_choice_extracts_source_backed_choices_but_never_auto_writes(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=190)
    page.insert_text((15, 24), "2. Choose the correct option.", fontsize=10)
    for y, text in ((55, "A. Alpha"), (85, "B. Beta"), (115, "C. Gamma")):
        page.draw_rect(fitz.Rect(15, y - 12, 29, y + 2), width=1)
        page.insert_text((40, y), text, fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("2. Choose"))
        controls = [block for block in blocks if block.block_label == "checkbox"]
        return [
            SemanticTaskCandidate(
                label="2",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in controls],
                response_type="choice",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    task = parsed.tasks[0]
    assert [choice.text for choice in task.choices] == ["A. Alpha", "B. Beta", "C. Gamma"]
    assert [link.role for link in task.response_links] == [TaskResponseRole.choice] * 3
    assert [link.choice_id for link in task.response_links] == [choice.id for choice in task.choices]
    assert all(
        parsed.response_region(link.response_region_id).region_type == ResponseRegionType.checkbox
        and parsed.response_region(link.response_region_id).safety == ResponseSafety.needs_review
        for link in task.response_links
    )
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_choice_and_explicit_explanation_preserve_distinct_response_regions(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=210)
    page.insert_text((15, 24), "1. Choose the correct option.", fontsize=10)
    for y, text in ((55, "A. Alpha"), (85, "B. Beta")):
        page.draw_rect(fitz.Rect(15, y - 12, 29, y + 2), width=1)
        page.insert_text((40, y), text, fontsize=10)
    page.insert_text((15, 116), "Explain why:", fontsize=10)
    field = fitz.Widget()
    field.field_name = "choice-explanation"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(15, 128, 300, 180)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Choose"))
        responses = [
            block
            for block in blocks
            if block.block_label in {"checkbox", "form_field"}
        ]
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in responses],
                response_type="choice",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    regions = [parsed.response_region(link.response_region_id) for link in task.response_links]
    assert [choice.text for choice in task.choices] == ["A. Alpha", "B. Beta"]
    assert [link.role for link in task.response_links] == [
        TaskResponseRole.choice,
        TaskResponseRole.choice,
        TaskResponseRole.explanation,
    ]
    assert [region.region_type for region in regions] == [
        ResponseRegionType.checkbox,
        ResponseRegionType.checkbox,
        ResponseRegionType.form_field,
    ]
    assert all(region.safety == ResponseSafety.needs_review for region in regions)
    assert task.side_panel_fallback is True


def test_stage3_math_underscore_blank_uses_the_physical_glyph_run(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=110)
    page.insert_text((15, 26), "3. Solve 8 + 5 = ____", fontsize=10)
    page.insert_text((15, 56), "snake_case is an identifier, not an answer blank.", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("3. Solve"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="3",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="numeric",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    answer_lines = [block for block in parsed.blocks if block.block_label == "answer_line"]
    assert len(answer_lines) == 1
    assert parsed.tasks[0].side_panel_fallback is False
    assert parsed.response_region(parsed.tasks[0].response_links[0].response_region_id).safety == ResponseSafety.approved


@pytest.mark.parametrize(
    "prompt",
    [
        "1. Solve: ____.",
        "1. What is ____?",
        "1. Complete: (____)",
    ],
)
def test_stage3_terminal_punctuation_does_not_remove_an_explicit_underscore_blank(prompt):
    source = fitz.open()
    page = source.new_page(width=330, height=90)
    page.insert_text((15, 25), prompt, fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    answer_lines = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry and block.block_label == "answer_line"
    ]
    assert len(answer_lines) == 1


def test_stage3_model_cannot_select_only_one_of_two_same_prompt_underscore_blanks(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 25), "1. Compute x = ____ and y = ____", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Compute"))
        answers = [block for block in blocks if block.block_label == "answer_line"]
        assert len(answers) == 2
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[answers[-1].id],
                response_type="numeric",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_underscore_blank_overlapping_another_native_line_is_not_write_evidence():
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 25), "1. Solve: ____", fontsize=10)
    page.insert_text((15, 37), "Printed instruction must remain.", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.block_label == "answer_line"
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_overlapping_underscore_runs_do_not_exempt_each_other():
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 25), "1. Solve: ____", fontsize=10)
    page.insert_text((53, 25), "DANGER ____ KEEP", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.block_label == "answer_line"
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_embedded_underscore_identifier_is_never_a_response_blank():
    source = fitz.open()
    page = source.new_page(width=330, height=90)
    page.insert_text((15, 25), "1. What does foo___bar represent?", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    assert not any(
        block.source == SourceKind.pdf_geometry and block.block_label == "answer_line"
        for block in parsed.blocks
    )


def test_stage3_widget_extraction_distinguishes_checkbox_empty_and_nonwritable_fields():
    source = fitz.open()
    page = source.new_page(width=330, height=180)
    page.insert_text((15, 25), "Widget controls", fontsize=10)

    checkbox = fitz.Widget()
    checkbox.field_name = "choice_a"
    checkbox.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    checkbox.rect = fitz.Rect(15, 40, 29, 54)
    _add_visible_widget(page, checkbox)

    empty_text = fitz.Widget()
    empty_text.field_name = "short_answer"
    empty_text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    empty_text.rect = fitz.Rect(15, 70, 220, 96)
    _add_visible_widget(page, empty_text)

    readonly_text = fitz.Widget()
    readonly_text.field_name = "read_only"
    readonly_text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    readonly_text.field_flags = fitz.PDF_FIELD_IS_READ_ONLY
    readonly_text.rect = fitz.Rect(15, 110, 220, 136)
    _add_visible_widget(page, readonly_text)

    filled_text = fitz.Widget()
    filled_text.field_name = "filled"
    filled_text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    filled_text.field_value = "already filled"
    filled_text.rect = fitz.Rect(15, 145, 220, 171)
    _add_visible_widget(page, filled_text)

    pdf_bytes = source.tobytes()
    source.close()
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    physical = [block for block in parsed.blocks if block.source == SourceKind.pdf_geometry]
    assert [block.block_label for block in physical] == ["checkbox", "form_field"]
    assert all(block.semantic_role == BlockSemanticRole.response_area for block in physical)


def test_stage3_hidden_form_widget_is_not_physical_write_evidence():
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    visible = fitz.Widget()
    visible.field_name = "visible"
    visible.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    visible.rect = fitz.Rect(15, 25, 300, 50)
    _add_visible_widget(page, visible)
    hidden = fitz.Widget()
    hidden.field_name = "hidden"
    hidden.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    hidden.rect = fitz.Rect(15, 70, 300, 95)
    _add_visible_widget(page, hidden)
    pdf_bytes = source.tobytes()
    source.close()

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        hidden_widget = next(widget for widget in document[0].widgets() if widget.field_name == "hidden")
        document.xref_set_key(hidden_widget.xref, "F", "2")
        pdf_bytes = document.tobytes()
    finally:
        document.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    fields = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry and block.block_label == "form_field"
    ]
    assert len(fields) == 1
    assert fields[0].bbox == [15.0, 25.0, 300.0, 50.0]


def test_stage3_unrendered_form_widget_is_not_physical_write_evidence():
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    widget = fitz.Widget()
    widget.field_name = "unrendered"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = fitz.Rect(15, 45, 300, 75)
    widget.border_color = None
    widget.fill_color = None
    widget.text_color = None
    page.add_widget(widget)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label == "form_field"
        for block in parsed.blocks
    )


@pytest.mark.parametrize(
    "concealment",
    ["transparent", "white", "covered", "covered_with_foreground_artifact"],
)
def test_stage3_rendered_invisible_native_text_cannot_authorize_a_response_line(concealment):
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 20), "Practice Sheet", fontsize=10)
    if concealment == "transparent":
        page.insert_text((15, 45), "1. Explain the result.", fontsize=10, fill_opacity=0.01)
    elif concealment == "white":
        page.insert_text((15, 45), "1. Explain the result.", fontsize=10, color=(1, 1, 1))
    else:
        page.insert_text((15, 45), "1. Explain the result.", fontsize=10)
        page.draw_rect(fitz.Rect(10, 30, 180, 50), color=None, fill=(1, 1, 1), overlay=True)
        if concealment == "covered_with_foreground_artifact":
            # A stray matching-color vector mark must not stand in for the
            # covered source glyphs when proving native prompt visibility.
            page.draw_rect(fitz.Rect(40, 35, 46, 40), color=(0, 0, 0), fill=(0, 0, 0))
    page.draw_line((15, 75), (300, 75), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    assert not any(block.text.startswith("1. Explain") for block in parsed.blocks)
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.block_label == "answer_line"
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_widgets_and_underscores_over_visible_content_are_not_write_evidence():
    source = fitz.open()

    widget_graphic = source.new_page(width=330, height=130)
    widget_graphic.insert_text((15, 24), "1. Explain the result.", fontsize=10)
    field = fitz.Widget()
    field.field_name = "graphic-overlay"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(15, 55, 300, 84)
    _add_visible_widget(widget_graphic, field)
    widget_graphic.draw_rect(
        fitz.Rect(15, 55, 300, 84), color=(0, 0, 0), fill=(0.2, 0.5, 0.8), width=1
    )

    widget_text = source.new_page(width=330, height=130)
    widget_text.insert_text((15, 24), "2. Explain the result.", fontsize=10)
    widget_text.insert_text((20, 75), "Already printed", fontsize=10)
    field = fitz.Widget()
    field.field_name = "printed-overlay"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(15, 55, 300, 84)
    _add_visible_widget(widget_text, field)

    underscore_graphic = source.new_page(width=330, height=130)
    underscore_graphic.insert_text((15, 24), "3. Record the result: ____", fontsize=10)
    underscore_graphic.draw_rect(
        fitz.Rect(10, 8, 300, 45), color=(0, 0, 0), fill=(0.2, 0.5, 0.8), width=1
    )
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    physical = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
    ]
    assert physical == []


def test_stage3_text_widget_shaped_like_a_choice_control_is_not_a_response_field():
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 24), "1. Choose an option.", fontsize=10)
    page.insert_text((55, 57), "A. Alpha", fontsize=10)
    field = fitz.Widget()
    field.field_name = "choice-shaped-text"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(15, 40, 43, 66)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(
        block.source == SourceKind.pdf_geometry and block.block_label == "form_field"
        for block in parsed.blocks
    )


@pytest.mark.parametrize(
    ("shape", "expected_label"),
    [("line", "answer_line"), ("box", "bounded_box")],
)
def test_stage3_compact_explicit_numeric_response_regions_are_extracted(shape, expected_label):
    source = fitz.open()
    page = source.new_page(width=180, height=100)
    page.insert_text((15, 25), "1. Calculate the result.", fontsize=10)
    page.insert_text((15, 40), "Answer:", fontsize=10)
    if shape == "line":
        page.draw_line((15, 60), (75, 60), width=1)
    else:
        page.draw_rect(fitz.Rect(15, 50, 75, 70), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    regions = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label == expected_label
    ]
    assert len(regions) == 1
    assert regions[0].bbox[2] - regions[0].bbox[0] == pytest.approx(60)


def test_stage3_compact_explicit_text_widget_is_not_misclassified_as_a_choice_control():
    source = fitz.open()
    page = source.new_page(width=180, height=100)
    page.insert_text((15, 25), "1. Calculate 3 + 4.", fontsize=10)
    page.insert_text((15, 50), "Answer:", fontsize=10)
    field = fitz.Widget()
    field.field_name = "single-digit-answer"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(70, 38, 94, 62)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    fields = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label == "form_field"
    ]
    assert len(fields) == 1
    assert fields[0].bbox == [70.0, 38.0, 94.0, 62.0]


@pytest.mark.parametrize("shape", ["line", "box"])
@pytest.mark.parametrize(
    ("color", "opacity", "expected"),
    [((0, 0, 0), 1.0, True), ((1, 1, 1), 1.0, False), ((0, 0, 0), 0.01, False)],
)
def test_stage3_vector_response_evidence_requires_rendered_contrast(shape, color, opacity, expected):
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 25), "1. Record the result.", fontsize=10)
    page.insert_text((15, 40), "Answer:", fontsize=10)
    if shape == "line":
        page.draw_line((15, 65), (300, 65), color=color, width=1, stroke_opacity=opacity)
        expected_label = "answer_line"
    else:
        page.draw_rect(
            fitz.Rect(15, 52, 300, 102),
            color=color,
            width=1,
            stroke_opacity=opacity,
        )
        expected_label = "bounded_box"
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    has_region = any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label == expected_label
        for block in parsed.blocks
    )
    assert has_region is expected


@pytest.mark.parametrize("line_width", [1.5, 1.51, 2.0, 3.0])
def test_stage3_explicit_visible_answer_rules_allow_common_thick_strokes(line_width):
    source = fitz.open()
    page = source.new_page(width=220, height=100)
    page.insert_text((15, 25), "1. Calculate the result.", fontsize=10)
    page.insert_text((15, 40), "Answer:", fontsize=10)
    page.draw_line((15, 60), (160, 60), color=(0, 0, 0), width=line_width)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label == "answer_line"
        for block in parsed.blocks
    )


@pytest.mark.parametrize(
    "response_label",
    ["Your answer:", "Final answer:", "Student response:", "Write your answer:"],
)
def test_stage3_explicit_answer_label_variants_keep_their_response_line(monkeypatch, response_label):
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 25), "1. Calculate 3 + 4.", fontsize=10)
    page.insert_text((15, 45), response_label, fontsize=10)
    page.draw_line((15, 68), (300, 68), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="numeric",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.side_panel_fallback is False
    assert task.review_status == ReviewStatus.auto_approved
    assert parsed.response_region(task.response_links[0].response_region_id).safety == ResponseSafety.approved


def test_stage3_right_aligned_explicit_answer_label_links_its_single_prompt(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=110)
    page.insert_text((15, 25), "1. Calculate 3 + 4.", fontsize=10)
    page.insert_text((170, 55), "Answer:", fontsize=10)
    page.draw_line((210, 55), (300, 55), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="numeric",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.side_panel_fallback is False
    assert task.review_status == ReviewStatus.auto_approved
    assert parsed.response_region(task.response_links[0].response_region_id).safety == ResponseSafety.approved


def test_stage3_inline_explicit_answer_label_preserves_a_distinct_show_work_region(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=210)
    page.insert_text((15, 25), "1. Calculate 3 + 4. Answer:", fontsize=10)
    page.draw_line((15, 45), (300, 45), width=1)
    page.insert_text((15, 78), "Show your work:", fontsize=10)
    page.draw_rect(fitz.Rect(15, 90, 300, 185), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        responses = [
            block
            for block in blocks
            if block.block_label in {"answer_line", "writable_area"}
        ]
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in responses],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    task = parsed.tasks[0]
    regions = [parsed.response_region(link.response_region_id) for link in task.response_links]
    assert [link.role for link in task.response_links] == [
        TaskResponseRole.answer,
        TaskResponseRole.show_work,
    ]
    assert all(region.safety == ResponseSafety.approved for region in regions)
    assert task.side_panel_fallback is False


def test_stage3_large_blank_choice_controls_accept_left_labels_and_reject_marks(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=165)
    page.insert_text((15, 20), "1. Choose the correct option.", fontsize=10)
    page.insert_text((15, 60), "A. Alpha", fontsize=10)
    page.draw_rect(fitz.Rect(100, 42, 133, 75), width=1)
    page.insert_text((15, 115), "B. Beta", fontsize=10)
    widget = fitz.Widget()
    widget.field_name = "large-choice"
    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget.rect = fitz.Rect(100, 97, 133, 130)
    _add_visible_widget(page, widget)
    page.draw_rect(fitz.Rect(15, 137, 29, 151), width=1)
    page.draw_rect(fitz.Rect(19, 141, 25, 147), color=None, fill=(0, 0, 0))
    page.insert_text((40, 150), "C. Gamma", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Choose"))
        controls = [block for block in blocks if block.block_label == "checkbox"]
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in controls],
                response_type="choice",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    controls = [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry and block.block_label == "checkbox"
    ]
    assert len(controls) == 2
    assert all(block.bbox[2] - block.bbox[0] == pytest.approx(33) for block in controls)
    assert [choice.text for choice in parsed.tasks[0].choices] == ["A. Alpha", "B. Beta"]
    assert parsed.tasks[0].side_panel_fallback is True


@pytest.mark.parametrize("layout", ["same_row", "overlapping_top"])
def test_stage3_unselected_imperative_cannot_bind_a_visible_field(monkeypatch, layout):
    source = fitz.open()
    page = source.new_page(width=380, height=120)
    page.insert_text((15, 25), "1. Explain the first result.", fontsize=10)
    if layout == "same_row":
        page.insert_text((120, 25), "Calculate the second result:", fontsize=10)
        page.insert_text((15, 55), "Answer:", fontsize=10)
        field_rect = fitz.Rect(60, 40, 350, 75)
    else:
        page.insert_text((15, 55), "Calculate the second result:", fontsize=10)
        field_rect = fitz.Rect(165, 40, 350, 75)
    field = fitz.Widget()
    field.field_name = f"competing-{layout}"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = field_rect
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        response = next(block for block in blocks if block.block_label == "form_field")
        return [
            SemanticTaskCandidate(
                label="wrong-link",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    task = parsed.tasks[0]
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review
    assert all(
        parsed.response_region(link.response_region_id).safety != ResponseSafety.approved
        for link in task.response_links
    )


def test_stage3_generic_metadata_label_cannot_bind_a_visible_field(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 25), "1. Explain your answer.", fontsize=10)
    page.insert_text((15, 55), "Name:", fontsize=10)
    field = fitz.Widget()
    field.field_name = "student-name"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(55, 40, 250, 70)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        response = next(block for block in blocks if block.block_label == "form_field")
        return [
            SemanticTaskCandidate(
                label="wrong-name-field",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )

    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


@pytest.mark.parametrize("choice_label", ["A. Alpha", "I. Indigo"])
def test_stage3_text_widget_adjacent_to_a_choice_label_is_not_a_response_field(choice_label):
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 24), "1. Choose an option.", fontsize=10)
    page.insert_text((15, 55), choice_label, fontsize=10)
    field = fitz.Widget()
    field.field_name = "wide-choice-control"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(78, 38, 122, 64)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(
        block.source == SourceKind.pdf_geometry and block.block_label == "form_field"
        for block in parsed.blocks
    )


@pytest.mark.parametrize(
    ("header", "banner", "split_font"),
    [
        ("Teacher guide - do not write on this page.", True, False),
        ("Teacher guide - do not write on this page.", True, True),
        ("Teacher's Guide", False, False),
        ("Instructor's Guide", False, False),
        ("Teacher Edition", False, False),
        ("Educator Guide", False, False),
        ("Solutions", False, False),
    ],
)
def test_stage3_source_nonstudent_write_cue_overrides_forged_student_semantics(
    monkeypatch,
    header,
    banner,
    split_font,
):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    if banner:
        page.draw_rect(fitz.Rect(10, 5, 320, 30), color=None, fill=(0.1, 0.3, 0.8))
    if split_font:
        page.insert_text((15, 20), "Teacher", fontsize=10, fontname="helv")
        page.insert_text((190, 20), "Guide", fontsize=10, fontname="cour")
    else:
        page.insert_text((15, 20), header, fontsize=10)
    page.insert_text((15, 48), "1. Explain the worked result.", fontsize=10)
    page.draw_line((15, 76), (300, 76), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert parsed.pages[0].needs_review is True
    assert region.safety == ResponseSafety.needs_review
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_unlabeled_checkbox_selection_routes_to_side_panel_without_invalid_relations():
    source = fitz.open()
    page = source.new_page(width=330, height=100)
    page.insert_text((15, 24), "1. Choose an option.", fontsize=10)
    checkbox = fitz.Widget()
    checkbox.field_name = "unlabeled"
    checkbox.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    checkbox.rect = fitz.Rect(15, 45, 29, 59)
    _add_visible_widget(page, checkbox)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Choose"))
        control = next(block for block in blocks if block.block_label == "checkbox")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[control.id],
                response_type="choice",
                confidence=0.99,
            )
        ]

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True
    assert parsed.response_regions == []


def test_stage3_graphic_panels_and_axes_are_not_writable_response_evidence():
    source = fitz.open()
    panel = source.new_page(width=330, height=220)
    panel.insert_text((15, 25), "1. Explain the diagram.", fontsize=10)
    panel.draw_rect(
        fitz.Rect(15, 50, 300, 178),
        color=(0, 0, 0),
        fill=(0.1, 0.3, 0.8),
        width=1,
    )
    axis = source.new_page(width=330, height=150)
    axis.insert_text((15, 25), "2. Explain the chart.", fontsize=10)
    axis.draw_line((15, 70), (300, 70), width=1)
    axis.draw_line((15, 45), (15, 120), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label in {"answer_line", "bounded_box", "writable_area"}
        for block in parsed.blocks
    )


def test_stage3_vector_boxes_support_line_cycles_and_demote_decorative_or_grid_geometry():
    source = fitz.open()
    page = source.new_page(width=330, height=260)
    page.insert_text((15, 25), "How to use this worksheet", fontsize=10)
    page.draw_line((15, 45), (300, 45), width=1)
    page.insert_text((15, 76), "1. Explain your answer.", fontsize=10)
    page.insert_text((15, 88), "Answer:", fontsize=10)
    # This bounded box is deliberately emitted as four line operators, not a
    # rectangle operator.
    page.draw_line((15, 92), (300, 92), width=1)
    page.draw_line((15, 142), (300, 142), width=1)
    page.draw_line((15, 92), (15, 142), width=1)
    page.draw_line((300, 92), (300, 142), width=1)
    page.insert_text((15, 171), "2. Complete the table.", fontsize=10)
    for x in (15, 105, 195):
        page.draw_line((x, 184), (x, 244), width=1)
    for y in (184, 214, 244):
        page.draw_line((15, y), (195, y), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    physical = [block for block in parsed.blocks if block.source == SourceKind.pdf_geometry]
    bounded = [block for block in physical if block.block_label == "bounded_box"]
    assert len(bounded) == 1
    assert bounded[0].bbox == [15.0, 92.0, 300.0, 142.0]
    assert not any(block.block_label == "answer_line" for block in physical)
    grid_boxes = [
        block
        for block in physical
        if block.bbox[1] >= 180 and block.block_label in {"bounded_box", "writable_area"}
    ]
    assert grid_boxes == []


def test_stage3_dense_vector_grid_is_nonwritable_without_combinatorial_extraction():
    source = fitz.open()
    page = source.new_page(width=360, height=360)
    page.insert_text((15, 20), "Complete the table.", fontsize=10)
    for offset in range(12):
        coordinate = 20 + offset * 25
        page.draw_line((20, coordinate), (295, coordinate), width=1)
        page.draw_line((coordinate, 20), (coordinate, 295), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert parsed.processing_ms < 2_000
    assert not any(
        block.block_label in {"bounded_box", "writable_area"}
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_raw_vector_rule_budget_discards_all_partial_line_evidence():
    source = fitz.open()
    page = source.new_page(width=400, height=1_500)
    page.insert_text((15, 25), "1. Explain the chart.", fontsize=10)
    for offset in range(300):
        y = 60 + offset * 4
        page.draw_line((15, y), (380, y), width=1)
        page.draw_line((20 + offset * 0.5, 45), (20 + offset * 0.5, 1_300), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )

    assert parsed.processing_ms < 1_500
    assert not any(block.source == SourceKind.pdf_geometry for block in parsed.blocks)


def test_stage3_disjoint_dense_grids_share_a_global_rectangle_candidate_budget():
    source = fitz.open()
    page = source.new_page(width=720, height=720)
    for grid_index in range(16):
        column = grid_index % 4
        row = grid_index // 4
        x0 = 15 + column * 170
        x1 = x0 + 140
        y0 = 18 + row * 165
        y1 = y0 + 93
        page.draw_line((x0, y0), (x0, y1), width=1)
        page.draw_line((x1, y0), (x1, y1), width=1)
        for offset in range(32):
            y = y0 + offset * 3
            page.draw_line((x0, y), (x1, y), width=1)
    rectangles, _, _ = _vector_rectangle_bboxes(page.get_drawings())
    assert rectangles == []
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert parsed.processing_ms < 1_500
    assert len([block for block in parsed.blocks if block.source == SourceKind.pdf_geometry]) <= 600


class _InjectedFormFieldOCR:
    def extract_page(self, _pdf_bytes, page_index):
        from ocr_adapter import OCRPageResult, OCRTextBlock

        return OCRPageResult(
            page_index=page_index,
            blocks=[
                OCRTextBlock(
                    text="OCR layout field",
                    bbox=(20, 64, 250, 92),
                    confidence=0.99,
                    label="form_field",
                    source_id="ocr-form-field",
                )
            ],
            engine="test",
            warnings=[],
            width_points=330,
            height_points=130,
        )


def test_stage3_ocr_layout_cannot_renumber_or_authorize_native_response_evidence(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    page.insert_text((15, 28), "1. Explain the result.", fontsize=10)
    page.insert_text((15, 48), "Answer:", fontsize=10)
    page.draw_line((15, 65), (300, 65), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    baseline = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    with_ocr = parse_document(
        pdf_bytes,
        ocr_adapter=_InjectedFormFieldOCR(),
        semantic_classifier=_SourceSelector(select),
        paddle_all_pages=True,
    )
    baseline_physical = [
        (block.id, block.reading_order, block.bbox, block.block_label)
        for block in baseline.blocks
        if block.source == SourceKind.pdf_geometry
    ]
    ocr_physical = [
        (block.id, block.reading_order, block.bbox, block.block_label)
        for block in with_ocr.blocks
        if block.source == SourceKind.pdf_geometry
    ]
    assert ocr_physical == baseline_physical
    assert with_ocr.tasks[0].id == baseline.tasks[0].id
    assert with_ocr.tasks[0].response_links[0].response_region_id == baseline.tasks[0].response_links[0].response_region_id
    assert with_ocr.response_region(with_ocr.tasks[0].response_links[0].response_region_id).safety == ResponseSafety.approved


def test_stage3_requires_ocr_page_cannot_auto_authorize_a_native_line(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=220, height=100)
    page.insert_text((15, 25), "1. X", fontsize=10)
    page.insert_text((15, 45), "Answer:", fontsize=10)
    page.draw_line((15, 60), (200, 60), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. X"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert parsed.pages[0].extraction_status == ParseStatus.requires_ocr
    assert region.safety == ResponseSafety.needs_review
    assert task.review_status == ReviewStatus.needs_review
    assert task.side_panel_fallback is True
    assert parsed.task_views()[0]["response_target_id"] == f"{task.id}:side-panel"
    exported = build_canonical_export_pdf(
        pdf_bytes,
        parsed,
        [
            {
                "task_id": task.id,
                "response_region_id": region.id,
                "answer_text": "Unsafe native target",
            }
        ],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        assert output.page_count == 2
        assert "Unsafe native target" not in output[0].get_text()
        assert "Unsafe native target" in output[1].get_text()
    finally:
        output.close()


def test_stage3_paddle_only_form_field_is_never_auto_approved(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    page.insert_text((15, 28), "1. Explain the result.", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    class _PaddleSelector:
        def classify_page(self, page, blocks, **_kwargs):
            prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
            response = next(block for block in blocks if block.source == SourceKind.paddleocr)
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.student_worksheet,
                confidence=0.99,
                blocks=[
                    SemanticBlockDecision(
                        block_id=block.id,
                        role=(
                            BlockSemanticRole.student_prompt
                            if block.id == prompt.id
                            else BlockSemanticRole.response_area
                            if block.id == response.id
                            else BlockSemanticRole.unknown
                        ),
                        confidence=0.99,
                    )
                    for block in blocks
                ],
                tasks=[
                    SemanticTaskCandidate(
                        label="1",
                        prompt_text="ignored",
                        prompt_block_ids=[prompt.id],
                        response_block_ids=[response.id],
                        response_type="short_text",
                        confidence=0.99,
                    )
                ],
            )

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=_InjectedFormFieldOCR(),
        semantic_classifier=_PaddleSelector(),
        paddle_all_pages=True,
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert region.source_block_ids == ["page-0-paddle-ocr-form-field"]
    assert region.safety == ResponseSafety.needs_review
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_ocr_prompt_evidence_cannot_auto_approve_a_native_widget(monkeypatch):
    from ocr_adapter import OCRPageResult, OCRTextBlock

    source = fitz.open()
    page = source.new_page(width=330, height=130)
    field = fitz.Widget()
    field.field_name = "answer"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(15, 75, 300, 105)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    class _OCRPrompts:
        def extract_page(self, _pdf_bytes, page_index):
            return OCRPageResult(
                page_index=page_index,
                blocks=[
                    OCRTextBlock(
                        text="1. What is shown?",
                        bbox=(15, 15, 210, 30),
                        confidence=0.99,
                        label="text",
                        source_id="prompt-one",
                    ),
                    OCRTextBlock(
                        text="Describe the second item",
                        bbox=(15, 44, 230, 59),
                        confidence=0.99,
                        label="text",
                        source_id="prompt-two",
                    ),
                ],
                engine="test",
                warnings=[],
                width_points=330,
                height_points=130,
            )

    class _Selector:
        def classify_page(self, page, blocks, **_kwargs):
            prompt = next(block for block in blocks if block.id.endswith("prompt-one"))
            response = next(block for block in blocks if block.block_label == "form_field")
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.student_worksheet,
                confidence=0.99,
                blocks=[
                    SemanticBlockDecision(
                        block_id=block.id,
                        role=(
                            BlockSemanticRole.student_prompt
                            if block.id == prompt.id
                            else block.semantic_role
                        ),
                        confidence=0.99,
                    )
                    for block in blocks
                ],
                tasks=[
                    SemanticTaskCandidate(
                        label="1",
                        prompt_text="ignored",
                        prompt_block_ids=[prompt.id],
                        response_block_ids=[response.id],
                        response_type="short_text",
                        confidence=0.99,
                    )
                ],
            )

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=_OCRPrompts(),
        semantic_classifier=_Selector(),
        paddle_all_pages=True,
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert region.safety == ResponseSafety.needs_review
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review
    manifest = build_manifest(
        "ocr-prompt",
        parsed.title,
        document=parsed,
        review_mode="teacher",
        review_status="draft",
    )
    with pytest.raises(ValueError, match="reliable native page evidence"):
        apply_review_actions(manifest, [{"action": "accept", "task_id": task.id}])


def test_stage3_reversed_or_cross_page_model_associations_route_to_side_panel(monkeypatch):
    source = fitz.open()
    first = source.new_page(width=330, height=150)
    first.insert_text((15, 24), "1. Explain the first result.", fontsize=10)
    first.draw_line((15, 55), (300, 55), width=1)
    first.insert_text((15, 85), "2. Explain the second result.", fontsize=10)
    first.draw_line((15, 116), (300, 116), width=1)
    second = source.new_page(width=330, height=130)
    second.insert_text((15, 24), "3. Explain the third result.", fontsize=10)
    second.draw_line((15, 65), (300, 65), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    baseline = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    cross_page_response = next(
        block
        for block in baseline.blocks
        if block.page_index == 1 and block.block_label == "answer_line"
    )

    class _BadAssociationSelector:
        def classify_page(self, page, blocks, **_kwargs):
            tasks = []
            if page.page_index == 0:
                first_prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
                second_response = sorted(
                    (block for block in blocks if block.block_label == "answer_line"),
                    key=lambda block: block.bbox[1],
                )[1]
                tasks = [
                    SemanticTaskCandidate(
                        label="reversed",
                        prompt_text="ignored",
                        prompt_block_ids=[first_prompt.id],
                        response_block_ids=[second_response.id],
                        response_type="short_text",
                        confidence=0.99,
                    ),
                    SemanticTaskCandidate(
                        label="cross-page",
                        prompt_text="ignored",
                        prompt_block_ids=[next(block for block in blocks if block.text.startswith("2. Explain")).id],
                        response_block_ids=[cross_page_response.id],
                        response_type="short_text",
                        confidence=0.99,
                    ),
                ]
            prompt_ids = {block_id for task in tasks for block_id in task.prompt_block_ids}
            return SemanticPageResult(
                page_index=page.page_index,
                page_role=PageRole.student_worksheet,
                confidence=0.99,
                blocks=[
                    SemanticBlockDecision(
                        block_id=block.id,
                        role=(
                            BlockSemanticRole.student_prompt
                            if block.id in prompt_ids
                            else block.semantic_role
                        ),
                        confidence=0.99,
                    )
                    for block in blocks
                ],
                tasks=tasks,
            )

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_BadAssociationSelector(),
    )
    assert len(parsed.tasks) == 2
    assert parsed.response_regions == []
    assert all(task.response_links == [] for task in parsed.tasks)
    assert all(task.side_panel_fallback for task in parsed.tasks)
    assert all(task.review_status == ReviewStatus.needs_review for task in parsed.tasks)


def test_stage3_two_numbered_prompts_cannot_be_merged_to_authorize_one_response(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=140)
    page.insert_text((15, 25), "1. Explain the first result.", fontsize=10)
    page.insert_text((15, 58), "2. Explain the second result.", fontsize=10)
    page.draw_line((15, 88), (300, 88), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompts = [
            block
            for block in blocks
            if block.text.startswith(("1. Explain", "2. Explain"))
        ]
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="merged",
                prompt_text="ignored",
                prompt_block_ids=[block.id for block in prompts],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review
    assert parsed.response_regions == []


def test_stage3_numbered_and_unnumbered_prompts_cannot_be_merged_to_authorize_one_response(
    monkeypatch,
):
    source = fitz.open()
    page = source.new_page(width=330, height=140)
    page.insert_text((15, 25), "1. Explain the first result.", fontsize=10)
    page.insert_text((15, 48), "Describe the second result.", fontsize=10)
    page.insert_text((15, 64), "Answer:", fontsize=10)
    page.draw_line((15, 84), (300, 84), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        first = next(block for block in blocks if block.text.startswith("1. Explain"))
        second = next(block for block in blocks if block.text.startswith("Describe the second"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="merged",
                prompt_text="ignored",
                prompt_block_ids=[first.id, second.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review
    assert parsed.response_regions == []


def test_stage3_wrapped_prompt_rule_rejects_a_second_interrogative_prompt(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=140)
    page.insert_text((15, 25), "1. Record the first answer.", fontsize=10)
    page.insert_text((15, 48), "What is the second answer?", fontsize=10)
    page.insert_text((15, 64), "Answer:", fontsize=10)
    page.draw_line((15, 84), (300, 84), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        first = next(block for block in blocks if block.text.startswith("1. Record"))
        second = next(block for block in blocks if block.text.startswith("What is the second"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="merged",
                prompt_text="ignored",
                prompt_block_ids=[first.id, second.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_tightly_wrapped_numbered_prompt_can_keep_its_single_answer_line(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=125)
    page.insert_text((15, 25), "1. Explain why the habitat changes", fontsize=10)
    page.insert_text((15, 40), "using evidence from the passage.", fontsize=10)
    page.insert_text((15, 55), "Answer:", fontsize=10)
    page.draw_line((15, 72), (300, 72), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt_blocks = [
            block
            for block in blocks
            if block.text.startswith(("1. Explain", "using evidence"))
        ]
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[block.id for block in prompt_blocks],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert len(task.prompt_block_ids) == 2
    assert task.side_panel_fallback is False
    assert task.review_status == ReviewStatus.auto_approved
    assert parsed.response_region(task.response_links[0].response_region_id).safety == ResponseSafety.approved


def test_stage3_review_cannot_promote_checkbox_to_a_text_write_target():
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 24), "1. Choose an option.", fontsize=10)
    page.draw_rect(fitz.Rect(15, 42, 29, 56), width=1)
    page.insert_text((40, 54), "A. Alpha", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Choose"))
        control = next(block for block in blocks if block.block_label == "checkbox")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[control.id],
                response_type="choice",
                confidence=0.99,
            )
        ]

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
        review_mode="teacher",
    )
    manifest = build_manifest(
        assignment_id="checkbox-review",
        title=parsed.title,
        questions=document_questions(parsed),
        review_mode="teacher",
        review_status="draft",
        document=parsed,
    )
    with pytest.raises(ValueError, match="deterministic mark renderer"):
        apply_review_actions(
            manifest,
            [{"action": "accept", "task_id": parsed.tasks[0].id}],
            pdf_bytes=pdf_bytes,
        )


def test_stage3_line_overlapping_prompt_text_cannot_become_a_response_region():
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 48), "1. Explain the result.", fontsize=10)
    # A typographic underline crossing the prompt, not an answer destination.
    page.draw_line((15, 45), (300, 45), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    assert not any(block.text.startswith("1. Explain") for block in parsed.blocks)
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_imperative_headings_cannot_authorize_decorative_lines_or_boxes(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=180)
    page.insert_text((15, 25), "1. Explain the scoring rubric", fontsize=10)
    page.draw_line((15, 45), (300, 45), width=1)
    page.insert_text((15, 84), "2. Complete the packet overview", fontsize=10)
    page.draw_rect(fitz.Rect(15, 96, 300, 160), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        first_heading = next(block for block in blocks if block.text.startswith("1. Explain the scoring"))
        second_heading = next(block for block in blocks if block.text.startswith("2. Complete the packet"))
        geometry = [block for block in blocks if block.source == SourceKind.pdf_geometry]
        return [
            SemanticTaskCandidate(
                label="heading-line",
                prompt_text="ignored",
                prompt_block_ids=[first_heading.id],
                response_block_ids=[geometry[0].id],
                response_type="short_text",
                confidence=0.99,
            ),
            SemanticTaskCandidate(
                label="heading-box",
                prompt_text="ignored",
                prompt_block_ids=[second_heading.id],
                response_block_ids=[geometry[1].id],
                response_type="short_text",
                confidence=0.99,
            ),
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert all(task.side_panel_fallback for task in parsed.tasks)
    assert all(task.review_status == ReviewStatus.needs_review for task in parsed.tasks)
    assert all(region.safety != ResponseSafety.approved for region in parsed.response_regions)
    assert not any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        for block in parsed.blocks
    )


def test_stage3_underscore_heading_cannot_bypass_task_association(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=90)
    page.insert_text((15, 25), "Teacher notes: ____", fontsize=10)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        heading = next(block for block in blocks if block.text.startswith("Teacher notes"))
        blank = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="teacher-notes",
                prompt_text="ignored",
                prompt_block_ids=[heading.id],
                response_block_ids=[blank.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True
    assert parsed.tasks[0].review_status == ReviewStatus.needs_review
    assert parsed.response_regions == []


def test_stage3_intervening_unselected_text_blocks_a_cross_task_line_leap(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=120)
    page.insert_text((15, 25), "1. Explain the first result?", fontsize=10)
    page.insert_text((15, 45), "Describe the second result", fontsize=10)
    page.insert_text((15, 60), "Answer:", fontsize=10)
    page.draw_line((15, 72), (300, 72), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        first_prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        line = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="wrong-link",
                prompt_text="ignored",
                prompt_block_ids=[first_prompt.id],
                response_block_ids=[line.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True
    assert parsed.tasks[0].review_status == ReviewStatus.needs_review
    assert parsed.response_regions == []


def test_stage3_column_locality_blocks_a_wrong_column_response_link(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=360, height=110)
    page.insert_text((15, 25), "1. Explain the left result.", fontsize=10)
    page.insert_text((190, 25), "2. Calculate the right result.", fontsize=10)
    page.draw_line((15, 60), (165, 60), width=1)
    page.draw_line((190, 60), (340, 60), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        wrong_line = max(
            (block for block in blocks if block.block_label == "answer_line"),
            key=lambda block: block.bbox[0],
        )
        return [
            SemanticTaskCandidate(
                label="wrong-column",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[wrong_line.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True


def test_stage3_same_row_competing_prompt_blocks_a_wrong_field_link(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=430, height=80)
    page.insert_text((15, 25), "1. First answer:", fontsize=10)
    page.insert_text((125, 25), "2. Second answer:", fontsize=10)
    field = fitz.Widget()
    field.field_name = "second-answer"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(255, 10, 410, 35)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        first_prompt = next(block for block in blocks if block.text.startswith("1. First"))
        response = next(block for block in blocks if block.block_label == "form_field")
        return [
            SemanticTaskCandidate(
                label="wrong-field",
                prompt_text="ignored",
                prompt_block_ids=[first_prompt.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True


def test_stage3_cannot_skip_an_earlier_physical_response_area(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=140)
    page.insert_text((15, 25), "1. Explain the result.", fontsize=10)
    for index, y in enumerate((42, 84), start=1):
        field = fitz.Widget()
        field.field_name = f"response-{index}"
        field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        field.rect = fitz.Rect(15, y, 300, y + 24)
        _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        second_field = max(
            (block for block in blocks if block.block_label == "form_field"),
            key=lambda block: block.bbox[1],
        )
        return [
            SemanticTaskCandidate(
                label="skipped-first-blank",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[second_field.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True


def test_stage3_multiple_unlabeled_response_areas_cannot_be_promoted_together(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=140)
    page.insert_text((15, 25), "1. Explain the result in one sentence.", fontsize=10)
    for index, y in enumerate((42, 84), start=1):
        field = fitz.Widget()
        field.field_name = f"unlabeled-{index}"
        field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        field.rect = fitz.Rect(15, y, 300, y + 24)
        _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Explain"))
        fields = [block for block in blocks if block.block_label == "form_field"]
        return [
            SemanticTaskCandidate(
                label="multiple-unlabeled",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in fields],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    assert parsed.tasks[0].response_links == []
    assert parsed.tasks[0].side_panel_fallback is True


def test_stage3_choice_text_cannot_be_selected_as_a_text_answer_prompt(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    page.insert_text((15, 25), "1. Explain why plants need light.", fontsize=10)
    page.insert_text((15, 52), "A. They need energy", fontsize=10)
    # Keep the real numbered prompt close enough that the line is a valid
    # physical candidate; the attack is selecting the adjacent choice text
    # as that candidate's prompt instead.
    page.draw_line((15, 70), (300, 70), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        choice_text = next(block for block in blocks if block.text.startswith("A. They"))
        response = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="choice-as-prompt",
                prompt_text="ignored",
                prompt_block_ids=[choice_text.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert region.safety == ResponseSafety.needs_review
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


@pytest.mark.parametrize(
    "instruction",
    ["1. Choose the correct option.", "1. Write the correct option."],
)
def test_stage3_later_numeric_choice_cannot_be_reframed_as_a_prompt(monkeypatch, instruction):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    page.insert_text((15, 25), instruction, fontsize=10)
    page.insert_text((15, 42), "1. Alpha", fontsize=10)
    page.insert_text((15, 55), "2. Beta", fontsize=10)
    page.draw_line((15, 75), (300, 75), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        choice_text = next(block for block in blocks if block.text.startswith("2. Beta"))
        # Choice-list underlines stay non-authoritative bare-rule candidates.
        response = next(
            block
            for block in blocks
            if block.block_label in {"horizontal_rule_candidate", "answer_line"}
        )
        return [
            SemanticTaskCandidate(
                label="choice-as-prompt",
                prompt_text="ignored",
                prompt_block_ids=[choice_text.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert task.response_links == []
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review

    # A forged stored record cannot turn the rejected bare-rule candidate into
    # a live target: the canonical contract rejects it before export because
    # it has no physical response-area evidence.
    choice_text = next(block for block in parsed.blocks if block.text.startswith("2. Beta"))
    bare_rule = next(
        block
        for block in parsed.blocks
        if block.block_label in {"horizontal_rule_candidate", "answer_line"}
    )
    region = DocumentResponseRegion(
        id="forged-region",
        page_index=0,
        bbox=bare_rule.bbox,
        region_type=ResponseRegionType.answer_line,
        safety=ResponseSafety.approved,
        confidence=1,
        source_block_ids=[bare_rule.id],
    )
    with pytest.raises(ValueError, match="lacks physical response-area evidence"):
        IntermediateDocument(
            title=parsed.title,
            parser=parsed.parser,
            status=parsed.status,
            source_sha256=parsed.source_sha256,
            pages=[parsed.pages[0].model_copy(update={"needs_review": False})],
            blocks=parsed.blocks,
            response_regions=[region],
            tasks=[
                DocumentTask(
                    id="forged-task",
                    legacy_question_id=1,
                    order=0,
                    prompt_text=choice_text.text,
                    anchor_page_index=0,
                    page_role=PageRole.student_worksheet,
                    prompt_block_ids=[choice_text.id],
                    response_links=[TaskResponseLink(response_region_id=region.id, order=0)],
                    side_panel_fallback=False,
                    confidence=1,
                    review_status=ReviewStatus.auto_approved,
                )
            ],
        )


def test_stage3_generic_form_label_requires_review_even_when_the_widget_is_real(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=90)
    page.insert_text((15, 25), "Student name:", fontsize=10)
    field = fitz.Widget()
    field.field_name = "student-name"
    field.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    field.rect = fitz.Rect(90, 10, 300, 35)
    _add_visible_widget(page, field)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        label = next(block for block in blocks if block.text == "Student name:")
        response = next(block for block in blocks if block.block_label == "form_field")
        return [
            SemanticTaskCandidate(
                label="header-field",
                prompt_text="ignored",
                prompt_block_ids=[label.id],
                response_block_ids=[response.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    region = parsed.response_region(task.response_links[0].response_region_id)
    assert region.safety == ResponseSafety.needs_review
    assert task.side_panel_fallback is True
    assert task.review_status == ReviewStatus.needs_review


def test_stage3_unknown_semantic_role_cannot_promote_physical_label(monkeypatch):
    blocks = [
        DocumentBlock(
            id="prompt",
            page_index=0,
            reading_order=0,
            text="1. Explain the result.",
            block_label="native_text",
            bbox=[15, 20, 180, 34],
            confidence=1.0,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="unclassified-response",
            page_index=0,
            reading_order=1,
            text="",
            block_label="answer_line",
            bbox=[15, 48, 300, 72],
            confidence=1.0,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.unknown,
        ),
    ]
    result = SemanticPageResult(
        page_index=0,
        page_role=PageRole.student_worksheet,
        confidence=0.99,
        blocks=[],
        tasks=[
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=["prompt"],
                response_block_ids=["unclassified-response"],
                response_type="short_text",
                confidence=0.99,
            )
        ],
    )
    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    tasks, regions = _build_tasks(blocks, [result], review_mode="direct")
    assert regions[0].safety == ResponseSafety.needs_review
    assert tasks[0].side_panel_fallback is True


def test_stage3_physical_response_order_is_geometry_stable_when_draw_commands_reverse():
    def make_pdf(reverse: bool) -> bytes:
        source = fitz.open()
        page = source.new_page(width=330, height=170)
        page.insert_text((15, 25), "1. Explain the first result.", fontsize=10)
        page.insert_text((15, 100), "2. Explain the second result.", fontsize=10)
        lines = [((15, 55), (300, 55)), ((15, 130), (300, 130))]
        for start, end in reversed(lines) if reverse else lines:
            page.draw_line(start, end, width=1)
        result = source.tobytes()
        source.close()
        return result

    first = parse_document(
        make_pdf(reverse=False),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    reversed_draw_order = parse_document(
        make_pdf(reverse=True),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    physical = lambda document: [
        (block.id, block.reading_order, block.bbox, block.block_label)
        for block in document.blocks
        if block.source == SourceKind.pdf_geometry
    ]
    assert physical(reversed_draw_order) == physical(first)


def test_stage3_canonical_validation_rejects_checkbox_type_or_role_relabeling():
    page = DocumentPage(page_index=0, width_points=200, height_points=100, block_ids=["prompt", "box"])
    blocks = [
        DocumentBlock(
            id="prompt",
            page_index=0,
            reading_order=0,
            text="1. Choose an option.",
            block_label="native_text",
            bbox=[10, 10, 180, 24],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="box",
            page_index=0,
            reading_order=1,
            text="",
            block_label="checkbox",
            bbox=[10, 35, 42, 67],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
    ]

    def document_for(region_type, link_role):
        return IntermediateDocument(
            title="Checkbox boundary",
            parser="test",
            status=ParseStatus.parsed,
            pages=[page],
            blocks=blocks,
            response_regions=[
                DocumentResponseRegion(
                    id="region",
                    page_index=0,
                    bbox=[10, 35, 42, 67],
                    region_type=region_type,
                    safety=ResponseSafety.approved,
                    confidence=1,
                    source_block_ids=["box"],
                )
            ],
            tasks=[
                DocumentTask(
                    id="task",
                    legacy_question_id=1,
                    order=0,
                    prompt_text="1. Choose an option.",
                    anchor_page_index=0,
                    prompt_block_ids=["prompt"],
                    response_links=[TaskResponseLink(response_region_id="region", role=link_role, order=0)],
                    side_panel_fallback=link_role != TaskResponseRole.answer,
                    confidence=1,
                    review_status=ReviewStatus.approved,
                )
            ],
        )

    with pytest.raises(ValueError, match="lacks physical response-area evidence"):
        document_for(ResponseRegionType.answer_line, TaskResponseRole.answer)
    with pytest.raises(ValueError, match="checkbox response regions require choice response links"):
        document_for(ResponseRegionType.checkbox, TaskResponseRole.answer)


def test_stage3_export_rechecks_actual_pdf_transform_before_writing():
    source = fitz.open()
    page = source.new_page(width=200, height=100)
    page.insert_text((10, 20), "1. Explain the result.", fontsize=10)
    page.set_rotation(90)
    pdf_bytes = source.tobytes()
    source.close()

    # This record has a valid source hash but intentionally lies about the
    # page transform. Export must trust the source PDF's actual page state.
    canonical = IntermediateDocument(
        title="Rotated source",
        parser="test",
        status=ParseStatus.parsed,
        source_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        pages=[
            DocumentPage(
                page_index=0,
                width_points=100,
                height_points=200,
                rotation=0,
                display_transform_required=False,
                block_ids=["prompt", "response"],
            )
        ],
        blocks=[
            DocumentBlock(
                id="prompt",
                page_index=0,
                reading_order=0,
                text="1. Explain the result.",
                block_label="native_text",
                bbox=[10, 10, 90, 24],
                confidence=1,
                source=SourceKind.native_pdf,
                semantic_role=BlockSemanticRole.student_prompt,
            ),
            DocumentBlock(
                id="response",
                page_index=0,
                reading_order=1,
                text="",
                block_label="answer_line",
                bbox=[10, 60, 90, 85],
                confidence=1,
                source=SourceKind.pdf_geometry,
                semantic_role=BlockSemanticRole.response_area,
            ),
        ],
        response_regions=[
            DocumentResponseRegion(
                id="region",
                page_index=0,
                bbox=[10, 60, 90, 85],
                region_type=ResponseRegionType.answer_line,
                safety=ResponseSafety.approved,
                confidence=1,
                source_block_ids=["response"],
            )
        ],
        tasks=[
            DocumentTask(
                id="task",
                legacy_question_id=1,
                order=0,
                prompt_text="1. Explain the result.",
                anchor_page_index=0,
                prompt_block_ids=["prompt"],
                response_links=[TaskResponseLink(response_region_id="region", order=0)],
                side_panel_fallback=False,
                confidence=1,
                review_status=ReviewStatus.approved,
            )
        ],
    )
    exported = build_canonical_export_pdf(
        pdf_bytes,
        canonical,
        [{"task_id": "task", "response_region_id": "region", "answer_text": "X"}],
    )
    result = fitz.open(stream=exported, filetype="pdf")
    try:
        assert result.page_count == 2
        assert "X" not in result[0].get_text()
        assert "X" in result[1].get_text()
    finally:
        result.close()


def test_stage3_export_rederives_source_evidence_and_requires_task_approval(monkeypatch):
    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        line = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[line.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    source_pdf = _canonical_short_answer_pdf()
    parsed = parse_document(
        source_pdf,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    target = task.response_links[0].response_region_id
    exported = build_canonical_export_pdf(
        source_pdf,
        parsed,
        [{"task_id": task.id, "response_region_id": target, "answer_text": "Seven"}],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        assert output.page_count == 1
        assert "Seven" in output[0].get_text()
    finally:
        output.close()


def test_stage3_export_uses_a_fresh_unicode_font_alias_when_source_reuses_the_old_name(monkeypatch):
    source = fitz.open()
    page = source.new_page(width=330, height=130)
    # A source worksheet controls its own PDF resource aliases. This Latin
    # font deliberately occupies the historic fixed answer-font name.
    page.insert_font(fontname="ClarosUnicode", fontbuffer=fitz.Font(fontname="helv").buffer)
    page.insert_text((15, 22), "Short Answer Practice", fontsize=10)
    page.insert_text((15, 48), "1. Calculate 3 + 4.", fontsize=10)
    page.insert_text((15, 64), "Answer:", fontsize=10)
    page.draw_line((15, 76), (300, 76), width=1)
    source_pdf = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if block.text.startswith("1. Calculate"))
        line = next(block for block in blocks if block.block_label == "answer_line")
        return [
            SemanticTaskCandidate(
                label="1",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[line.id],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        source_pdf,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    target = task.response_links[0].response_region_id
    answer = "Case $x$  π"
    exported = build_canonical_export_pdf(
        source_pdf,
        parsed,
        [{"task_id": task.id, "response_region_id": target, "answer_text": answer}],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        font_names = {font[4] for font in output[0].get_fonts(full=True)}
        assert "ClarosUnicode" in font_names
        assert any(name.startswith("ClarosAnswer") for name in font_names)
        assert answer in output[0].get_text()
    finally:
        output.close()

    unapproved = parsed.model_copy(deep=True)
    unapproved.task(task.id).review_status = ReviewStatus.needs_review
    routed = build_canonical_export_pdf(
        source_pdf,
        unapproved,
        [{"task_id": task.id, "response_region_id": target, "answer_text": "Seven"}],
    )
    output = fitz.open(stream=routed, filetype="pdf")
    try:
        assert output.page_count == 2
        assert "Seven" not in output[0].get_text()
        assert "Seven" in output[1].get_text()
    finally:
        output.close()

    teacher_page = parsed.model_copy(deep=True)
    teacher_page.pages[0].page_role = PageRole.teacher_guide
    teacher_page.task(task.id).page_role = PageRole.teacher_guide
    assert teacher_page.task_views()[0]["response_target_id"] == f"{task.id}:side-panel"
    routed = build_canonical_export_pdf(
        source_pdf,
        teacher_page,
        [{"task_id": task.id, "response_region_id": target, "answer_text": "Seven"}],
    )
    output = fitz.open(stream=routed, filetype="pdf")
    try:
        assert output.page_count == 2
        assert "Seven" not in output[0].get_text()
        assert "Seven" in output[1].get_text()
    finally:
        output.close()

    source = fitz.open()
    page = source.new_page(width=330, height=220)
    page.insert_text((15, 25), "1. Explain the diagram.", fontsize=10)
    page.draw_rect(
        fitz.Rect(15, 50, 300, 178),
        color=(0, 0, 0),
        fill=(0.1, 0.3, 0.8),
        width=1,
    )
    diagram_pdf = source.tobytes()
    source.close()
    extracted = parse_document(
        diagram_pdf,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=NullSemanticClassifier(),
    )
    prompt = next(block for block in extracted.blocks if block.source == SourceKind.native_pdf)
    canonical = IntermediateDocument(
        title="Forged panel",
        parser="test",
        status=ParseStatus.parsed,
        source_sha256=hashlib.sha256(diagram_pdf).hexdigest(),
        pages=[
            extracted.pages[0].model_copy(update={"block_ids": [prompt.id, "forged-panel"]})
        ],
        blocks=[
            prompt,
            DocumentBlock(
                id="forged-panel",
                page_index=0,
                reading_order=1,
                text="",
                block_label="writable_area",
                bbox=[15, 50, 300, 178],
                confidence=1,
                source=SourceKind.pdf_geometry,
                semantic_role=BlockSemanticRole.response_area,
            ),
        ],
        response_regions=[
            DocumentResponseRegion(
                id="forged-region",
                page_index=0,
                bbox=[15, 50, 300, 178],
                region_type=ResponseRegionType.writable_area,
                safety=ResponseSafety.approved,
                confidence=1,
                source_block_ids=["forged-panel"],
            )
        ],
        tasks=[
            DocumentTask(
                id="forged-task",
                legacy_question_id=1,
                order=0,
                prompt_text=prompt.text,
                anchor_page_index=0,
                prompt_block_ids=[prompt.id],
                response_links=[TaskResponseLink(response_region_id="forged-region", order=0)],
                confidence=1,
                review_status=ReviewStatus.approved,
            )
        ],
    )
    routed = build_canonical_export_pdf(
        diagram_pdf,
        canonical,
        [{"task_id": "forged-task", "response_region_id": "forged-region", "answer_text": "X"}],
    )
    output = fitz.open(stream=routed, filetype="pdf")
    try:
        assert output.page_count == 2
        assert "X" not in output[0].get_text()
        assert "X" in output[1].get_text()
    finally:
        output.close()


def _writable_response_blocks(parsed: IntermediateDocument) -> list[DocumentBlock]:
    return [
        block
        for block in parsed.blocks
        if block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label in {
            "answer_line",
            "bounded_box",
            "writable_area",
            "checkbox",
            "form_field",
        }
    ]


def test_stage3_unnumbered_wrapped_prompt_expands_and_keeps_answer_show_work(monkeypatch):
    """Regression: wrap fragment must join the prompt, not block association."""
    source = fitz.open()
    page = source.new_page(width=500, height=280)
    page.insert_text(
        (40, 40),
        "A class collects 27 cans on Monday and 16 cans on Tuesday. How many cans do they collect in",
        fontsize=10,
    )
    page.insert_text((40, 54), "all?", fontsize=10)
    page.insert_text((20, 82), "Answer:", fontsize=10)
    page.draw_line((70, 94), (460, 94), width=1)
    page.insert_text((20, 122), "Show your work:", fontsize=10)
    page.draw_rect(fitz.Rect(20, 132, 460, 220), width=1)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        # Intentionally select only the first visual line, as offline selectors
        # and models often do for wrapped prompts.
        first = next(
            block
            for block in blocks
            if block.text.startswith("A class collects")
        )
        responses = [
            block
            for block in blocks
            if block.block_label in {"answer_line", "bounded_box", "writable_area"}
        ]
        return [
            SemanticTaskCandidate(
                label="2",
                prompt_text="ignored",
                prompt_block_ids=[first.id],
                response_block_ids=[block.id for block in responses],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    task = parsed.tasks[0]
    assert "all?" in task.prompt_text
    assert len(task.prompt_block_ids) >= 2
    assert len(task.response_links) == 2
    roles = [link.role for link in task.response_links]
    assert TaskResponseRole.answer in roles
    assert TaskResponseRole.show_work in roles


def test_stage3_rounded_answer_box_does_not_mint_edge_answer_line(monkeypatch):
    """Regression: inset/rounded box strokes are not extra writable lines."""
    source = fitz.open()
    page = source.new_page(width=400, height=220)
    page.insert_text((40, 36), "1. Jordan has $30 and spends $12. How much remains?", fontsize=10)
    page.insert_text((20, 68), "Answer:", fontsize=10)
    page.draw_rect(fitz.Rect(20, 78, 370, 112), width=1, radius=0.2)
    page.insert_text((20, 138), "Show your work:", fontsize=10)
    page.draw_rect(fitz.Rect(20, 148, 370, 200), width=1, radius=0.15)
    pdf_bytes = source.tobytes()
    source.close()

    def select(_page, blocks):
        prompt = next(block for block in blocks if "Jordan has" in block.text)
        responses = [
            block
            for block in blocks
            if block.block_label in {"bounded_box", "writable_area"}
        ]
        return [
            SemanticTaskCandidate(
                label="5",
                prompt_text="ignored",
                prompt_block_ids=[prompt.id],
                response_block_ids=[block.id for block in responses],
                response_type="short_text",
                confidence=0.99,
            )
        ]

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    writable = _writable_response_blocks(parsed)
    assert all(block.block_label != "answer_line" for block in writable)
    assert len([block for block in writable if block.block_label in {"bounded_box", "writable_area"}]) >= 2
    task = parsed.tasks[0]
    assert len(task.response_links) == 2
    assert {link.role for link in task.response_links} == {
        TaskResponseRole.answer,
        TaskResponseRole.show_work,
    }


@pytest.mark.parametrize(
    "perturbation",
    [
        "spacing",
        "prompt_length",
        "box_shape",
        "checkbox_size",
        "choice_length",
        "question_count",
        "page_break",
    ],
)
def test_stage3_redteam_layout_perturbations_keep_physical_evidence(monkeypatch, perturbation):
    """General layout variation must not require fixture-specific coordinates."""
    source = fitz.open()
    page = source.new_page(width=420, height=520)
    y = 36.0
    gap = 28.0 if perturbation == "spacing" else 18.0
    prompts = [
        "1. Maya places 18 books on 3 shelves. How many per shelf?",
        "2. A notebook costs $4. Lena buys 5 notebooks. What is the total?",
    ]
    if perturbation == "prompt_length":
        # Keep the interrogative on the first span and wrap a lowercase tail.
        prompts[0] = (
            "1. Maya has eighteen library books that need to be placed equally "
            "across three classroom shelves before Friday. How many books go on",
            "each shelf?",
        )
    if perturbation == "question_count":
        prompts.append("3. Jordan has $30 and spends $12. How much money remains?")

    def wrap_insert(text, x: float, start_y: float) -> float:
        lines = text if isinstance(text, tuple) else (text,)
        cursor = start_y
        max_chars = 54 if perturbation == "prompt_length" else 62
        for chunk in lines:
            words = chunk.split()
            line = ""
            for word in words:
                trial = f"{line} {word}".strip()
                if len(trial) > max_chars and line:
                    page.insert_text((x, cursor), line, fontsize=10)
                    cursor += 14
                    line = word
                else:
                    line = trial
            if line:
                page.insert_text((x, cursor), line, fontsize=10)
                cursor += 14
        return cursor

    for index, prompt in enumerate(prompts, start=1):
        if perturbation == "page_break" and index == 2:
            page = source.new_page(width=420, height=320)
            y = 36.0
        y = wrap_insert(prompt, 40, y)
        if perturbation == "box_shape":
            page.insert_text((20, y + 6), "Answer:", fontsize=10)
            page.draw_rect(fitz.Rect(20, y + 16, 390, y + 48), width=1, radius=0.18)
            y += 64 + gap
        elif perturbation in {"checkbox_size", "choice_length"}:
            page.insert_text((20, y + 4), "Choose one:", fontsize=10)
            y += 20
            size = 18 if perturbation == "checkbox_size" else 12
            choices = (
                ["A. Recycle paper carefully", "B. Leave devices unlocked overnight"]
                if perturbation == "choice_length"
                else ["A. Alpha", "B. Beta"]
            )
            for choice in choices:
                page.draw_rect(fitz.Rect(20, y, 20 + size, y + size), width=1)
                page.insert_text((20 + size + 10, y + size - 2), choice, fontsize=10)
                y += size + 14
            y += gap
        else:
            page.insert_text((20, y + 6), "Answer:", fontsize=10)
            page.draw_line((70, y + 18), (390, y + 18), width=1)
            y += 36 + gap

    pdf_bytes = source.tobytes()
    source.close()

    def select(page_obj, blocks):
        page_prompts = [
            block
            for block in blocks
            if block.page_index == page_obj.page_index
            and block.source == SourceKind.native_pdf
            and block.text.strip()
            and (
                block.text.startswith(("1.", "2.", "3."))
                or (
                    block.text[:1].islower()
                    and any(
                        anchor.bbox is not None
                        and block.bbox is not None
                        and abs(block.bbox[0] - anchor.bbox[0]) <= 48
                        and 0 <= block.bbox[1] - anchor.bbox[3] <= 24
                        for anchor in blocks
                        if anchor.source == SourceKind.native_pdf
                        and anchor.text.startswith(("1.", "2.", "3."))
                    )
                )
            )
        ]
        anchors = [
            block
            for block in page_prompts
            if block.text.startswith(("1.", "2.", "3."))
        ]
        tasks = []
        claimed = set()
        for order, prompt in enumerate(anchors, start=1):
            if perturbation in {"checkbox_size", "choice_length"}:
                responses = [
                    block
                    for block in blocks
                    if block.page_index == page_obj.page_index
                    and block.block_label == "checkbox"
                    and block.id not in claimed
                    and block.bbox is not None
                    and block.bbox[1] >= prompt.bbox[3] - 4
                ][:2]
            else:
                responses = [
                    block
                    for block in blocks
                    if block.page_index == page_obj.page_index
                    and block.block_label in {"answer_line", "bounded_box", "writable_area"}
                    and block.id not in claimed
                    and block.bbox is not None
                    and block.bbox[1] >= prompt.bbox[3] - 4
                ][:1]
            if not responses:
                continue
            claimed.update(block.id for block in responses)
            tasks.append(
                SemanticTaskCandidate(
                    label=str(order),
                    prompt_text="ignored",
                    prompt_block_ids=[prompt.id],
                    response_block_ids=[block.id for block in responses],
                    response_type=(
                        "choice"
                        if perturbation in {"checkbox_size", "choice_length"}
                        else "short_text"
                    ),
                    confidence=0.99,
                )
            )
        return tasks

    monkeypatch.setattr("config.ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SourceSelector(select),
    )
    expected_tasks = 3 if perturbation == "question_count" else 2
    assert len(parsed.tasks) == expected_tasks
    assert all(task.response_links for task in parsed.tasks)
    writable = _writable_response_blocks(parsed)
    if perturbation in {"checkbox_size", "choice_length"}:
        assert sum(1 for block in writable if block.block_label == "checkbox") >= 4
        assert all(task.choices for task in parsed.tasks)
    else:
        assert writable
        # Controlled layouts should not invent many extra blanks beyond the
        # intended answer destinations.
        assert len(writable) <= expected_tasks + 1
