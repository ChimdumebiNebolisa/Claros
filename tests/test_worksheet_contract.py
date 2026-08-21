"""Narrow production worksheet contract and workload ceilings."""

from __future__ import annotations

import re

import fitz
import pytest

import config
import semantic_classifier
from document_model import BlockSemanticRole, PageRole, WorksheetSupportStatus
from document_pipeline import parse_supported_worksheet
from ocr_adapter import NullOCRAdapter
from semantic_classifier import (
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)
from worksheet_contract import UnsupportedWorksheetError


def _worksheet_pdf(
    questions: list[tuple[str, int]],
    *,
    extra_line: bool = False,
    two_columns: bool = False,
) -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 55), "Student Worksheet", fontsize=14)
    for index, (prompt, line_count) in enumerate(questions):
        if two_columns:
            x = 72 if index == 0 else 330
            y = 130
            width = 220
        else:
            x = 72
            y = 120 + index * 180
            width = 468
        page.insert_text((x, y), prompt, fontsize=11)
        for line_index in range(line_count):
            line_y = y + 42 + line_index * 28
            page.draw_line((x, line_y), (x + width, line_y), width=1)
    if extra_line:
        page.draw_line((72, 255), (540, 255), width=1)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


class _SequentialClassifier:
    provider_call_units = 0

    def __init__(self, *, response_type: str = "short_text", omit_last_line: bool = False):
        self.response_type = response_type
        self.omit_last_line = omit_last_line

    def classify_page(self, page, blocks, **_kwargs):
        prompts = sorted(
            (block for block in blocks if re.match(r"^[1-9][0-9]*\.", block.text.strip())),
            key=lambda block: (block.bbox[1], block.bbox[0]),
        )
        lines = sorted(
            (
                block
                for block in blocks
                if block.block_label in {"answer_line", "bounded_box", "writable_area", "form_field"}
            ),
            key=lambda block: (block.bbox[1], block.bbox[0]),
        )
        tasks = []
        for index, prompt in enumerate(prompts):
            next_top = prompts[index + 1].bbox[1] if index + 1 < len(prompts) else page.height_points
            responses = [line for line in lines if prompt.bbox[3] <= line.bbox[1] < next_top]
            if self.omit_last_line and responses:
                responses = responses[:-1]
            tasks.append(
                SemanticTaskCandidate(
                    label=str(index + 1),
                    prompt_text="ignored",
                    prompt_block_ids=[prompt.id],
                    response_block_ids=[line.id for line in responses],
                    response_type=self.response_type,
                    confidence=0.99,
                )
            )
        return SemanticPageResult(
            page_index=page.page_index,
            page_role=PageRole.student_worksheet,
            confidence=0.99,
            blocks=[
                SemanticBlockDecision(
                    block_id=block.id,
                    role=(BlockSemanticRole.student_prompt if block in prompts else block.semantic_role),
                    confidence=0.99,
                )
                for block in blocks
            ],
            tasks=tasks,
        )


def test_supported_single_line_box_and_aligned_line_group(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    document = parse_supported_worksheet(
        _worksheet_pdf([("1. Explain the result.", 3)]),
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SequentialClassifier(),
    )

    assert document.worksheet_classification is not None
    assert document.worksheet_classification.status == WorksheetSupportStatus.supported
    # The physical extractor may coalesce a visible aligned line group into one
    # deterministic writable area; either representation stays one answer
    # space under the contract.
    assert len(document.tasks[0].response_links) >= 1
    assert all(
        document.response_region(link.response_region_id).safety.value == "approved"
        for link in document.tasks[0].response_links
    )


def test_supported_variations_span_pages_multiline_prompts_boxes_and_page_edges(monkeypatch):
    document = fitz.open()
    first = document.new_page(width=612, height=792)
    first.insert_textbox(
        fitz.Rect(72, 80, 540, 125),
        "1. Explain in one short sentence why plants need sunlight.",
        fontsize=11,
    )
    first.draw_line((72, 150), (540, 150), width=1)
    first.draw_line((72, 176), (540, 176), width=1)
    first.insert_text((72, 260), "2. Name one producer in an ecosystem.", fontsize=11)
    first.draw_rect(fitz.Rect(72, 290, 540, 350), width=1)
    second = document.new_page(width=612, height=792)
    second.insert_text((72, 690), "3. State one nonliving ecosystem factor.", fontsize=11)
    second.draw_line((72, 735), (540, 735), width=1)
    pdf_bytes = document.tobytes()
    document.close()

    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    parsed = parse_supported_worksheet(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=_SequentialClassifier(),
    )

    assert len(parsed.tasks) == 3
    assert {region.region_type.value for region in parsed.response_regions} >= {
        "answer_line",
        "bounded_box",
    }
    assert parsed.tasks[-1].anchor_page_index == 1


def _unsupported_structure_pdf(kind: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    if kind == "answer_key":
        page.insert_text((72, 50), "Answer Key", fontsize=14)
        page.insert_text((72, 120), "1. Explain the result.", fontsize=11)
        page.draw_line((72, 165), (540, 165), width=1)
    elif kind == "remote_answer":
        page.insert_text((72, 90), "1. Explain the result.", fontsize=11)
        page.draw_line((72, 700), (540, 700), width=1)
    elif kind == "answer_table":
        page.insert_text((72, 90), "1. Record the result in the table.", fontsize=11)
        for y in (140, 180, 220):
            page.draw_line((72, y), (540, y), width=1)
        for x in (72, 228, 384, 540):
            page.draw_line((x, 140), (x, 220), width=1)
    elif kind == "essay_area":
        page.insert_text((72, 90), "1. Explain the result.", fontsize=11)
        page.draw_rect(fitz.Rect(72, 120, 540, 420), width=1)
    else:
        raise AssertionError(kind)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


@pytest.mark.parametrize(
    "kind",
    ["answer_key", "remote_answer", "answer_table", "essay_area"],
)
def test_other_unsupported_classes_reject_without_writable_assignment(monkeypatch, kind):
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    with pytest.raises(UnsupportedWorksheetError):
        parse_supported_worksheet(
            _unsupported_structure_pdf(kind),
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=_SequentialClassifier(),
        )


@pytest.mark.parametrize(
    ("pdf_bytes", "classifier", "reason"),
    [
        (
            _worksheet_pdf([("1. Choose the best answer.", 1)]),
            _SequentialClassifier(response_type="choice"),
            "unsupported_response_type",
        ),
        (
            _worksheet_pdf([("1. First prompt.", 1), ("2. Second prompt.", 1)], two_columns=True),
            _SequentialClassifier(),
            "multi_column_layout",
        ),
        (
            _worksheet_pdf([("1. Explain the result.", 2)]),
            _SequentialClassifier(omit_last_line=True),
            "unclaimed_writable_space",
        ),
    ],
)
def test_unsupported_and_ambiguous_layouts_fail_closed(monkeypatch, pdf_bytes, classifier, reason):
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    with pytest.raises(UnsupportedWorksheetError) as rejected:
        parse_supported_worksheet(
            pdf_bytes,
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=classifier,
        )
    assert reason in rejected.value.classification.reason_codes


def test_staggered_two_column_questions_fail_closed(monkeypatch):
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 100), "1. Explain the first result.", fontsize=11)
    page.draw_line((72, 140), (280, 140), width=1)
    page.insert_text((330, 300), "2. Explain the second result.", fontsize=11)
    page.draw_line((330, 340), (540, 340), width=1)
    pdf_bytes = document.tobytes()
    document.close()

    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    with pytest.raises(UnsupportedWorksheetError) as rejected:
        parse_supported_worksheet(
            pdf_bytes,
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=_SequentialClassifier(),
        )
    assert "multi_column_layout" in rejected.value.classification.reason_codes


def test_question_ceiling_rejects_as_results_arrive(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_DOCUMENT_TASK_AUTO_APPROVE", True)
    monkeypatch.setattr(config, "MAX_WORKSHEET_QUESTIONS", 1)
    with pytest.raises(UnsupportedWorksheetError) as rejected:
        parse_supported_worksheet(
            _worksheet_pdf([("1. First prompt.", 1), ("2. Second prompt.", 1)]),
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=_SequentialClassifier(),
        )
    assert rejected.value.classification.reason_codes == ["question_limit_exceeded"]


def test_page_ceiling_is_a_controlled_rejection_before_classification():
    document = fitz.open()
    for _ in range(config.MAX_PDF_PAGES + 1):
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 120), "1. Explain the result.", fontsize=11)
        page.draw_line((72, 165), (540, 165), width=1)
    pdf_bytes = document.tobytes()
    document.close()

    with pytest.raises(UnsupportedWorksheetError) as rejected:
        parse_supported_worksheet(
            pdf_bytes,
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=_SequentialClassifier(),
        )
    assert rejected.value.classification.reason_codes == ["page_limit_exceeded"]


def test_semantic_provider_call_ceiling_is_preflighted(monkeypatch):
    class _CountingProvider:
        provider_call_units = 1

        def __init__(self):
            self.calls = 0

        def classify_page(self, page, blocks, **_kwargs):
            self.calls += 1
            raise AssertionError("preflight must reject before provider work")

    document = fitz.open()
    for _ in range(9):
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 120), "1. Explain the result.", fontsize=11)
        page.draw_line((72, 165), (540, 165), width=1)
    pdf_bytes = document.tobytes()
    document.close()
    provider = _CountingProvider()
    monkeypatch.setattr(config, "MAX_PDF_PAGES", 10)
    monkeypatch.setattr(config, "MAX_SEMANTIC_PROVIDER_CALLS", 8)

    with pytest.raises(UnsupportedWorksheetError) as rejected:
        parse_supported_worksheet(
            pdf_bytes,
            ocr_adapter=NullOCRAdapter(),
            semantic_classifier=provider,
        )
    assert rejected.value.classification.reason_codes == ["semantic_call_budget_exceeded"]
    assert provider.calls == 0


def test_semantic_provider_client_has_one_bounded_attempt(monkeypatch):
    captured = {}
    sentinel = object()

    def fake_client(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(semantic_classifier.genai, "Client", fake_client)
    monkeypatch.setattr(semantic_classifier, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(config, "SEMANTIC_PROVIDER_TIMEOUT_MS", 12_345)

    classifier = semantic_classifier.GeminiSemanticClassifier()
    assert classifier._get_client() is sentinel
    options = captured["http_options"]
    assert options.timeout == 12_345
    assert options.retry_options.attempts == 1
