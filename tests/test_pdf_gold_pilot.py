import json
from pathlib import Path

import pytest

from evaluation.pdf_gold_pilot.build_annotation_project import DEFAULT_CORPUS, _validate_selection
from evaluation.pdf_gold_pilot.closed_world import (
    ClosedWorldPageResult,
    PilotPageInput,
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


def test_selection_has_required_size_and_diverse_cases():
    payload = json.loads(
        (ROOT / "evaluation" / "pdf_gold_pilot" / "selection.json").read_text(encoding="utf-8")
    )
    pages = _validate_selection(payload)
    tags = {tag for page in pages for tag in page["coverage_tags"]}
    assert len(pages) == 17
    assert {"image_only_scan", "teacher_guide", "answer_key", "compound_labels"} <= tags
    assert {"unnumbered_prompt", "table_or_form", "visual_activity", "multi_column"} <= tags


def test_default_corpus_is_repo_relative():
    assert DEFAULT_CORPUS == ROOT / "evaluation" / "corpora" / "pdf_acceptance"
    assert (DEFAULT_CORPUS / "corpus").is_dir()


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
