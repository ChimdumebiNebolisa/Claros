import json
from pathlib import Path

import fitz
import pytest

from document_model import DocumentBlock, ResponseSafety, SourceKind
from evaluation.pdf_gold_pilot.build_annotation_project import (
    _pilot_page_geometry,
    _response_candidate,
    _validate_selection,
)
from evaluation.pdf_gold_pilot.closed_world import (
    ClosedWorldPageResult,
    PilotPageInput,
    derive_canonical_document,
    derive_canonical_document_for_pages,
    derive_tasks,
    validate_closed_world_result,
)

ROOT = Path(__file__).resolve().parents[1]


def _page() -> PilotPageInput:
    return PilotPageInput.model_validate(
        {
            "pilot_id": "fixture-p01",
            "source_pdf": "fixture.pdf",
            "page_number": 1,
            "page_index": 0,
            "page_width_points": 600,
            "page_height_points": 800,
            "rotation": 0,
            "image": "rendered/fixture.png",
            "blocks": [
                {
                    "id": "block-1",
                    "page_index": 0,
                    "reading_order": 1,
                    "text": "3a. Explain the result.",
                    "block_label": "native_text",
                    "bbox": [20, 30, 300, 60],
                    "confidence": 1.0,
                    "source": "native_pdf",
                },
                {
                    "id": "block-2",
                    "page_index": 0,
                    "reading_order": 2,
                    "text": "Use evidence from the table.",
                    "block_label": "native_text",
                    "bbox": [20, 62, 320, 86],
                    "confidence": 1.0,
                    "source": "native_pdf",
                },
            ],
            "response_candidates": [
                {
                    "id": "line-1",
                    "page_index": 0,
                    "reading_order": 3,
                    "layout_label": "answer_line",
                    "bbox": [20, 100, 400, 130],
                    "confidence": 0.92,
                    "source": "pdf_geometry",
                    "safe_for_writing": True,
                    "safety_suggestion": "safe_physical",
                }
            ],
            "warnings": [],
        }
    )


def _result(**overrides) -> ClosedWorldPageResult:
    payload = {
        "page_index": 0,
        "page_role": "student_worksheet",
        "selected_block_ids": ["block-1", "block-2"],
        "rejected_blocks": [],
        "groupings": [
            {
                "group_index": 1,
                "prompt_block_ids": ["block-1", "block-2"],
                "visual_anchor_block_ids": [],
                "parent_group_index": None,
                "subpart": "3a",
                "response_candidate_ids": ["line-1"],
                "response_disposition": "safe_physical",
                "needs_review": False,
                "reason": "Explicit prompt blocks and answer line.",
            }
        ],
        "selected_response_candidate_ids": ["line-1"],
        "needs_review": False,
        "reason": "Student worksheet with one grouped task.",
    }
    payload.update(overrides)
    return ClosedWorldPageResult.model_validate(payload)


def _second_page() -> PilotPageInput:
    payload = _page().model_dump(mode="json")
    payload.update(
        {
            "pilot_id": "fixture-p02",
            "page_number": 2,
            "page_index": 1,
            "image": "rendered/fixture-p02.png",
        }
    )
    payload["blocks"][0].update(
        {
            "id": "block-1-p02",
            "page_index": 1,
            "text": "4. State the conclusion.",
        }
    )
    payload["blocks"][1].update(
        {
            "id": "block-2-p02",
            "page_index": 1,
            "text": "Cite one observation.",
        }
    )
    payload["response_candidates"][0].update(
        {"id": "line-1-p02", "page_index": 1}
    )
    return PilotPageInput.model_validate(payload)


def _second_result() -> ClosedWorldPageResult:
    payload = _result().model_dump(mode="json")
    payload["page_index"] = 1
    payload["selected_block_ids"] = ["block-1-p02", "block-2-p02"]
    payload["groupings"][0]["prompt_block_ids"] = ["block-1-p02", "block-2-p02"]
    payload["groupings"][0]["response_candidate_ids"] = ["line-1-p02"]
    payload["selected_response_candidate_ids"] = ["line-1-p02"]
    return ClosedWorldPageResult.model_validate(payload)


def test_selection_has_required_size_and_diverse_cases():
    payload = json.loads(
        (ROOT / "evaluation" / "pdf_gold_pilot" / "selection.json").read_text(encoding="utf-8")
    )
    pages = _validate_selection(payload)
    tags = {tag for page in pages for tag in page["coverage_tags"]}
    assert len(pages) == 17
    assert {"image_only_scan", "teacher_guide", "answer_key", "compound_labels"} <= tags
    assert {"unnumbered_prompt", "table_or_form", "visual_activity", "multi_column"} <= tags


def test_closed_world_derives_text_and_geometry_only_from_known_ids():
    page = _page()
    result = _result()
    tasks = derive_tasks(page, result)
    assert tasks == [
        {
            "id": tasks[0]["id"],
            "page_index": 0,
            "page_role": "student_worksheet",
            "group_index": 1,
            "parent_group_index": None,
            "subpart": "3a",
            "prompt_text": "3a. Explain the result.\nUse evidence from the table.",
            "prompt_block_ids": ["block-1", "block-2"],
            "visual_anchor_block_ids": [],
            "prompt_bbox": [20.0, 30.0, 320.0, 86.0],
            "response_candidate_ids": ["line-1"],
            "response_bbox": [20.0, 100.0, 400.0, 130.0],
            "response_disposition": "safe_physical",
            "needs_review": False,
            "reason": "Explicit prompt blocks and answer line.",
            "write_authorized": False,
        }
    ]


def test_closed_world_rejects_unknown_or_unpartitioned_blocks():
    page = _page()
    result = _result(selected_block_ids=["block-1", "invented-block"])
    with pytest.raises(ValueError, match="partition"):
        validate_closed_world_result(page, result)


def test_closed_world_rejects_unsafe_candidate_claimed_as_safe():
    page_payload = _page().model_dump(mode="json")
    page_payload["response_candidates"][0]["safe_for_writing"] = False
    page_payload["response_candidates"][0]["safety_suggestion"] = "ambiguous"
    with pytest.raises(ValueError, match="unsafe physical candidate"):
        validate_closed_world_result(PilotPageInput.model_validate(page_payload), _result())


def test_side_panel_task_selects_no_response_candidate():
    page = _page()
    payload = _result().model_dump(mode="json")
    payload["groupings"][0]["response_candidate_ids"] = []
    payload["groupings"][0]["response_disposition"] = "side_panel_only"
    payload["groupings"][0]["needs_review"] = True
    payload["selected_response_candidate_ids"] = []
    result = ClosedWorldPageResult.model_validate(payload)
    tasks = derive_tasks(page, result)
    assert tasks[0]["response_bbox"] is None
    assert tasks[0]["write_authorized"] is False


@pytest.mark.parametrize(
    "path",
    [
        ("blocks", 0, "bbox"),
        ("response_candidates", 0, "bbox"),
    ],
)
def test_pilot_input_rejects_geometry_outside_its_extraction_frame(path):
    payload = _page().model_dump(mode="json")
    payload[path[0]][path[1]][path[2]] = [20, 30, 601, 60]

    with pytest.raises(ValueError, match="stay within the extraction frame"):
        PilotPageInput.model_validate(payload)


def test_canonical_document_assembles_actual_contiguous_pages_in_global_order():
    first_page = _page()
    second_page = _second_page()
    single_page_document = derive_canonical_document(first_page, _result())

    document = derive_canonical_document_for_pages(
        [second_page, first_page],
        [_second_result(), _result()],
    )

    assert document.title == "fixture.pdf"
    assert document.document_id == "fixture.pdf"
    assert single_page_document.title == "fixture-p01"
    assert single_page_document.document_id == "fixture-p01"
    assert [page.page_index for page in document.pages] == [0, 1]
    assert len(document.pages) == 2
    assert [task.anchor_page_index for task in document.tasks] == [0, 1]
    assert [task.order for task in document.tasks] == [0, 1]
    assert [task.legacy_question_id for task in document.tasks] == [1, 2]
    assert document.tasks[1].prompt_text == "4. State the conclusion.\nCite one observation."
    assert document.tasks[1].response_links[0].response_region_id == "cw-region-line-1-p02"
    assert document.response_region("cw-region-line-1-p02").source_block_ids == ["line-1-p02"]
    assert document.page(1).block_ids == ["block-1-p02", "block-2-p02", "line-1-p02"]


def test_canonical_document_rejects_nonzero_standalone_page_without_placeholder_pages():
    with pytest.raises(ValueError, match="standalone canonical document derivation requires page_index 0"):
        derive_canonical_document(_second_page(), _second_result())


def test_transformed_pilot_geometry_uses_extraction_bounds_and_disables_physical_candidates():
    pdf = fitz.open()
    page = pdf.new_page(width=200, height=100)
    page.set_cropbox(fitz.Rect(10, 10, 190, 90))
    page.set_rotation(90)
    try:
        width, height, rotation, display_transform_required = _pilot_page_geometry(page)
    finally:
        pdf.close()

    response_block = DocumentBlock(
        id="candidate-1",
        page_index=0,
        reading_order=0,
        block_label="answer_line",
        bbox=[20, 30, 160, 50],
        confidence=0.95,
        source=SourceKind.pdf_geometry,
    )
    candidate = _response_candidate(
        response_block,
        display_transform_required=display_transform_required,
    )

    assert (width, height, rotation) == (180.0, 80.0, 90)
    assert display_transform_required is True
    assert candidate["safe_for_writing"] is False
    assert candidate["safety_suggestion"] == "ambiguous"


@pytest.mark.parametrize(
    ("mutate", "transform_expected"),
    [
        (
            lambda payload: payload.update(
                {"rotation": 90, "display_transform_required": True}
            ),
            True,
        ),
        (
            lambda payload: payload["response_candidates"][0].update(
                {"layout_label": "unrecognized_response_area"}
            ),
            False,
        ),
    ],
)
def test_canonical_adapter_routes_ineligible_physical_candidates_to_side_panel(
    mutate,
    transform_expected,
):
    page_payload = _page().model_dump(mode="json")
    mutate(page_payload)
    document = derive_canonical_document(PilotPageInput.model_validate(page_payload), _result())

    region = document.response_region(document.tasks[0].response_links[0].response_region_id)
    assert region.safety == ResponseSafety.needs_review
    assert document.tasks[0].side_panel_fallback is True
    assert document.tasks[0].review_status.value == "needs_review"
    assert document.pages[0].display_transform_required is transform_expected
