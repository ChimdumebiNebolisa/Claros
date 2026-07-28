"""Stage 2 canonical document contract regressions."""
from __future__ import annotations

import json
import hashlib

import fitz
import pytest

from document_model import (
    BlockSemanticRole,
    CoordinateSpace,
    DocumentBlock,
    DocumentChoice,
    DocumentPage,
    DocumentResponseRegion,
    DocumentTask,
    IntermediateDocument,
    PageRole,
    ParseStatus,
    ResponseRegionType,
    ResponseSafety,
    ResponseType,
    ReviewStatus,
    SourceKind,
    TaskResponseLink,
    stable_response_region_id,
    stable_task_id,
)
from manifest import (
    AssignmentManifest,
    build_manifest,
    legacy_document_from_questions,
    parse_manifest_json,
)
from exporter import build_canonical_export_pdf
import session_service
from schemas import SessionConfirmRequest
from review_service import apply_review_actions


def _document() -> IntermediateDocument:
    pages = [
        DocumentPage(page_index=0, width_points=612, height_points=792, block_ids=["p0", "a", "b", "c", "d"]),
        DocumentPage(page_index=1, width_points=612, height_points=792, block_ids=["p1", "subpart", "explain"]),
    ]
    blocks = [
        DocumentBlock(
            id="p0",
            page_index=0,
            reading_order=0,
            text="Choose the best habitat and explain why.",
            block_label="native_text",
            bbox=[40, 40, 400, 62],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        *[
            DocumentBlock(
                id=choice_id,
                page_index=0,
                reading_order=index,
                text=choice_id.upper(),
                block_label="checkbox",
                bbox=[50, 90 + index * 30, 70, 110 + index * 30],
                confidence=1,
                source=SourceKind.pdf_geometry,
                semantic_role=BlockSemanticRole.response_area,
            )
            for index, choice_id in enumerate(["a", "b", "c", "d"], start=1)
        ],
        DocumentBlock(
            id="p1",
            page_index=1,
            reading_order=0,
            text="Explain your choice on the next page.",
            block_label="native_text",
            bbox=[40, 40, 400, 62],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
        DocumentBlock(
            id="explain",
            page_index=1,
            reading_order=2,
            text="",
            block_label="bounded_box",
            bbox=[40, 100, 500, 260],
            confidence=1,
            source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
        DocumentBlock(
            id="subpart",
            page_index=1,
            reading_order=1,
            text="State one supporting observation.",
            block_label="native_text",
            bbox=[40, 70, 400, 92],
            confidence=1,
            source=SourceKind.native_pdf,
            semantic_role=BlockSemanticRole.student_prompt,
        ),
    ]
    regions = [
        DocumentResponseRegion(
            id=f"r-{choice_id}",
            page_index=0,
            bbox=[50, 90 + index * 30, 70, 110 + index * 30],
            region_type=ResponseRegionType.checkbox,
            response_type=ResponseType.checkbox,
            safety=ResponseSafety.approved,
            confidence=1,
            source_block_ids=[choice_id],
        )
        for index, choice_id in enumerate(["a", "b", "c", "d"], start=1)
    ]
    regions.append(
        DocumentResponseRegion(
            id="r-explain",
            page_index=1,
            bbox=[40, 100, 500, 260],
            region_type=ResponseRegionType.bounded_box,
            response_type=ResponseType.long_text,
            safety=ResponseSafety.approved,
            confidence=1,
            source_block_ids=["explain"],
        )
    )
    task = DocumentTask(
        id="task-habitat",
        legacy_question_id=8,
        order=0,
        label="8",
        prompt_text="Choose the best habitat and explain why.\nExplain your choice on the next page.",
        anchor_page_index=0,
        page_role=PageRole.student_worksheet,
        prompt_block_ids=["p0", "p1"],
        choices=[
            DocumentChoice(id=f"choice-{choice_id}", order=index, label=choice_id.upper(), text=choice_id.upper(), source_block_ids=[choice_id])
            for index, choice_id in enumerate(["a", "b", "c", "d"])
        ],
        response_links=[
            *[
                TaskResponseLink(
                    response_region_id=f"r-{choice_id}",
                    role="choice",
                    order=index,
                    choice_id=f"choice-{choice_id}",
                )
                for index, choice_id in enumerate(["a", "b", "c", "d"])
            ],
            TaskResponseLink(response_region_id="r-explain", role="explanation", order=4),
        ],
        side_panel_fallback=True,
        response_type=ResponseType.choice,
        confidence=1,
        review_status=ReviewStatus.auto_approved,
    )
    subtask = DocumentTask(
        id="task-habitat-subpart",
        legacy_question_id=9,
        order=1,
        label="8a",
        prompt_text="State one supporting observation.",
        anchor_page_index=1,
        page_role=PageRole.student_worksheet,
        prompt_block_ids=["subpart"],
        parent_task_id="task-habitat",
        subpart="a",
        response_links=[],
        side_panel_fallback=True,
        response_type=ResponseType.short_text,
        confidence=1,
        review_status=ReviewStatus.approved,
    )
    return IntermediateDocument(
        title="Habitats",
        parser="test",
        status=ParseStatus.parsed,
        document_id="doc-1",
        pages=pages,
        blocks=blocks,
        response_regions=regions,
        tasks=[task, subtask],
    )


def test_canonical_contract_round_trips_rich_cross_page_document_without_flat_questions():
    manifest = build_manifest("assignment-1", "Habitats", document=_document())
    raw = manifest.model_dump_json()
    assert '"questions"' not in raw
    restored = parse_manifest_json(raw)
    task = restored.document.task("task-habitat")
    assert task.prompt_block_ids == ["p0", "p1"]
    assert task.prompt_text == "Choose the best habitat and explain why.\nExplain your choice on the next page."
    assert [link.response_region_id for link in task.response_links] == ["r-a", "r-b", "r-c", "r-d", "r-explain"]
    assert restored.document.task("task-habitat-subpart").parent_task_id == "task-habitat"
    assert restored.to_client_document()["tasks"][0]["id"] == "task-habitat"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data["pages"].append(data["pages"][0]), "page indexes must be unique"),
        (lambda data: data["response_regions"].append(data["response_regions"][0]), "response region IDs must be unique"),
        (lambda data: data["tasks"][1].update({"parent_task_id": "task-habitat-subpart"}), "cannot parent itself"),
        (lambda data: data["tasks"][0]["response_links"].append(data["tasks"][0]["response_links"][0]), "response links must be unique"),
        (lambda data: data["pages"][1].update({"page_index": 2}), "page indexes must be contiguous"),
        (lambda data: data["pages"][0].update({"rotation": 90}), "requiring display transform"),
        (lambda data: data["response_regions"][0].update({"bbox": [600, 90, 620, 110]}), "outside its page bounds"),
        (lambda data: data["response_regions"][0].update({"source_block_ids": ["p0"]}), "lacks physical response-area evidence"),
        (lambda data: data["response_regions"][0].update({"bbox": [300, 300, 330, 330]}), "does not fit within its physical evidence"),
        (lambda data: data["tasks"][0]["response_links"][0].update({"choice_id": "unknown-choice"}), "unknown choice"),
    ],
)
def test_canonical_contract_rejects_invalid_relationships(mutate, message):
    data = _document().model_dump(mode="json")
    mutate(data)
    with pytest.raises(ValueError, match=message):
        IntermediateDocument.model_validate(data)


def test_legacy_flat_manifest_migrates_to_side_panel_without_promoting_uncertain_geometry():
    raw = {
        "version": 3,
        "assignment_id": "legacy",
        "title": "Legacy",
        "questions": [
            {
                "id": 1,
                "text": "Explain.",
                "detected_answer_region": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.1},
                "needs_layout_review": True,
                "approved": False,
            }
        ],
    }
    manifest = parse_manifest_json(json.dumps(raw))
    task = manifest.document.tasks[0]
    assert task.response_links == []
    assert task.evidence_status.value == "legacy_unverified"
    assert manifest.document.blocks == []
    assert manifest.document.response_regions == []
    assert manifest.to_questions_dict()[0]["answer_region"] is None
    assert manifest.to_questions_dict()[0]["answer_region_status"] == "side_panel"


def test_idless_legacy_records_keep_quarantined_identity_across_reordering():
    first = legacy_document_from_questions(
        title="Legacy",
        questions=[{"text": "First prompt", "page": 1}, {"text": "Second prompt", "page": 1}],
    )
    reordered = legacy_document_from_questions(
        title="Legacy",
        questions=[{"text": "Second prompt", "page": 1}, {"text": "First prompt", "page": 1}],
    )
    first_ids = {
        task.prompt_text: (task.id, task.legacy_question_id, task.order) for task in first.tasks
    }
    reordered_ids = {
        task.prompt_text: (task.id, task.legacy_question_id, task.order)
        for task in reordered.tasks
    }
    assert first_ids == reordered_ids
    with pytest.raises(ValueError, match="distinct source fingerprints"):
        legacy_document_from_questions(
            title="Legacy",
            questions=[{"text": "Repeated", "page": 1}, {"text": "Repeated", "page": 1}],
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["blocks"][0].update({"id": ""}),
        lambda data: data["response_regions"][0].update({"id": ""}),
        lambda data: data["tasks"][0].update({"id": ""}),
        lambda data: data["tasks"][0]["response_links"][0].update({"response_region_id": ""}),
    ],
)
def test_canonical_identity_fields_reject_blank_values(mutate):
    data = _document().model_dump(mode="json")
    mutate(data)
    with pytest.raises(ValueError):
        IntermediateDocument.model_validate(data)


def test_stable_task_and_response_ids_ignore_model_list_order_and_labels():
    assert stable_task_id(0, ["prompt-b", "prompt-a"], "Prompt") == stable_task_id(
        0, ["prompt-a", "prompt-b"], "Prompt"
    )
    task_id = stable_task_id(0, ["prompt-a"], "Prompt")
    assert stable_response_region_id(task_id, ["candidate-b", "candidate-a"]) == stable_response_region_id(
        task_id, ["candidate-a", "candidate-b"]
    )


def test_confirmation_schema_rejects_browser_geometry():
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        SessionConfirmRequest.model_validate(
            {
                "session_secret": "s" * 12,
                "task_id": "task-habitat",
                "response_region_id": "r-a",
                "answer_text": "A",
                "answer_region": {"x": 0, "y": 0, "width": 1, "height": 1},
            }
        )


def test_manifest_rejects_unknown_fields_instead_of_dropping_them():
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        AssignmentManifest.model_validate(
            {
                "assignment_id": "x",
                "title": "X",
                "questions": [],
                "future_field": "must not be dropped",
            }
        )

    with pytest.raises(ValueError, match="parallel questions projection"):
        AssignmentManifest.model_validate(
            {
                "version": 4,
                "assignment_id": "x",
                "title": "X",
                "document": _document().model_dump(mode="json"),
                "questions": [],
            }
        )

    with pytest.raises(ValueError, match="unsupported manifest version"):
        AssignmentManifest.model_validate(
            {
                "version": 99,
                "assignment_id": "x",
                "title": "X",
                "document": _document().model_dump(mode="json"),
            }
        )


def test_canonical_model_rejects_reused_physical_response_evidence_and_invented_prompt_text():
    duplicate_region = _document().model_dump(mode="json")
    duplicate_region["response_regions"].append(
        {
            **duplicate_region["response_regions"][0],
            "id": "r-a-duplicate",
        }
    )
    duplicate_region["tasks"][1]["response_links"] = [
        {"response_region_id": "r-a-duplicate", "role": "answer", "order": 0}
    ]
    duplicate_region["tasks"][1]["side_panel_fallback"] = False
    with pytest.raises(ValueError, match="physical response source blocks"):
        IntermediateDocument.model_validate(duplicate_region)

    invented_prompt = _document().model_dump(mode="json")
    invented_prompt["tasks"][0]["prompt_text"] = "Invented wording"
    with pytest.raises(ValueError, match="prompt_text must match"):
        IntermediateDocument.model_validate(invented_prompt)

    invented_choice = _document().model_dump(mode="json")
    invented_choice["tasks"][0]["choices"][0]["text"] = "Invented choice"
    with pytest.raises(ValueError, match="choice choice-a text must match"):
        IntermediateDocument.model_validate(invented_choice)

    invented_choice_label = _document().model_dump(mode="json")
    invented_choice_label["tasks"][0]["choices"][0]["label"] = "Invented Z"
    with pytest.raises(ValueError, match="choice choice-a label must match"):
        IntermediateDocument.model_validate(invented_choice_label)

    oversized_sliver = _document().model_dump(mode="json")
    oversized_sliver["response_regions"][0]["bbox"] = [60, 130, 500, 500]
    with pytest.raises(ValueError, match="does not fit within its physical evidence"):
        IntermediateDocument.model_validate(oversized_sliver)

    out_of_page_source = _document().model_dump(mode="json")
    out_of_page_source["blocks"][1]["bbox"] = [0, 0, 9_999, 9_999]
    with pytest.raises(ValueError, match="block a is outside its page bounds"):
        IntermediateDocument.model_validate(out_of_page_source)

    model_labeled_text = _document().model_dump(mode="json")
    model_labeled_text["blocks"][0]["semantic_role"] = "response_area"
    model_labeled_text["response_regions"][0].update(
        {"source_block_ids": ["p0"], "bbox": [50, 45, 70, 55]}
    )
    with pytest.raises(ValueError, match="lacks physical response-area evidence"):
        IntermediateDocument.model_validate(model_labeled_text)

    overlapping_regions = _document().model_dump(mode="json")
    overlap_block = dict(overlapping_regions["blocks"][1])
    overlap_block.update({"id": "overlap", "bbox": [60, 130, 80, 150]})
    overlapping_regions["blocks"].append(overlap_block)
    overlapping_regions["pages"][0]["block_ids"].append("overlap")
    overlapping_regions["response_regions"].append(
        {
            **overlapping_regions["response_regions"][0],
            "id": "r-overlap",
            "bbox": [60, 130, 80, 150],
            "source_block_ids": ["overlap"],
        }
    )
    overlapping_regions["tasks"][1]["response_links"] = [
        {"response_region_id": "r-overlap", "role": "answer", "order": 0}
    ]
    overlapping_regions["tasks"][1]["side_panel_fallback"] = False
    with pytest.raises(ValueError, match="approved response regions may not overlap"):
        IntermediateDocument.model_validate(overlapping_regions)


def test_canonical_model_requires_real_finite_pages():
    empty_pages = _document().model_dump(mode="json")
    empty_pages["pages"] = []
    with pytest.raises(ValueError):
        IntermediateDocument.model_validate(empty_pages)

    infinite_page = _document().model_dump(mode="json")
    infinite_page["pages"][0]["width_points"] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        IntermediateDocument.model_validate(infinite_page)


def test_normalized_legacy_coordinate_space_projects_normalized_geometry_without_rescaling():
    page = DocumentPage(
        page_index=0,
        width_points=612,
        height_points=792,
        coordinate_space=CoordinateSpace.normalized_legacy,
        block_ids=["prompt", "response"],
    )
    document = IntermediateDocument(
        title="Legacy normalized",
        parser="test",
        status=ParseStatus.parsed,
        pages=[page],
        blocks=[
            DocumentBlock(
                id="prompt",
                page_index=0,
                reading_order=0,
                text="State the answer.",
                block_label="text",
                bbox=[0.1, 0.1, 0.8, 0.2],
                confidence=1,
                source=SourceKind.legacy_parser,
                semantic_role=BlockSemanticRole.student_prompt,
            ),
            DocumentBlock(
                id="response",
                page_index=0,
                reading_order=1,
                text="",
                block_label="answer_line",
                bbox=[0.1, 0.3, 0.8, 0.4],
                confidence=1,
                source=SourceKind.legacy_parser,
                semantic_role=BlockSemanticRole.response_area,
            ),
        ],
        response_regions=[
            DocumentResponseRegion(
                id="response-region",
                page_index=0,
                bbox=[0.1, 0.3, 0.8, 0.4],
                safety=ResponseSafety.approved,
                confidence=1,
                source_block_ids=["response"],
            )
        ],
        tasks=[
            DocumentTask(
                id="normalized-task",
                legacy_question_id=1,
                order=0,
                prompt_text="State the answer.",
                anchor_page_index=0,
                prompt_block_ids=["prompt"],
                response_links=[TaskResponseLink(response_region_id="response-region", order=0)],
                confidence=1,
                review_status=ReviewStatus.approved,
            )
        ],
    )
    assert document.normalized_region(document.response_region("response-region")) == {
        "x": 0.1,
        "y": 0.3,
        "width": 0.7,
        "height": 0.1,
    }


def test_canonical_export_routes_an_unsafe_linked_region_to_the_side_panel_even_if_client_supplies_geometry():
    canonical = _document().model_copy(deep=True)
    canonical.response_region("r-explain").safety = ResponseSafety.needs_review
    canonical.task("task-habitat").side_panel_fallback = True
    source = fitz.open()
    source.new_page(width=612, height=792)
    source.new_page(width=612, height=792)
    source_bytes = source.tobytes()
    source.close()

    exported = build_canonical_export_pdf(
        source_bytes,
        canonical,
        [
            {
                "task_id": "task-habitat",
                "response_region_id": "r-explain",
                "answer_text": "Exact explanation",
                "answer_region": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
            }
        ],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        assert output.page_count == 3
        assert "Exact explanation" not in output[1].get_text()
        assert "Exact explanation" in output[2].get_text()
    finally:
        output.close()


def test_canonical_export_routes_stale_pdf_dimensions_and_multiple_target_roles_to_distinct_side_panel_entries():
    data = _document().model_dump(mode="json")
    for page in data["pages"]:
        page["width_points"] = 1000
        page["height_points"] = 1000
    canonical = IntermediateDocument.model_validate(data)
    source = fitz.open()
    source.new_page(width=612, height=792)
    source.new_page(width=612, height=792)
    source_bytes = source.tobytes()
    source.close()

    exported = build_canonical_export_pdf(
        source_bytes,
        canonical,
        [
            {"task_id": "task-habitat", "response_region_id": "r-a", "answer_text": "A"},
            {
                "task_id": "task-habitat",
                "response_region_id": "r-explain",
                "answer_text": "Because water is retained.",
            },
        ],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        assert output.page_count == 4
        assert "Because water is retained." not in output[1].get_text()
        side_panel_text = "\n".join(page.get_text() for page in output[2:])
        assert "Question 8 - Choice A" in side_panel_text
        assert "Question 8 - Explanation" in side_panel_text
    finally:
        output.close()


def test_canonical_export_routes_a_same_size_but_different_source_pdf_to_side_panel():
    trusted = fitz.open()
    trusted.new_page(width=612, height=792).insert_text((72, 72), "Trusted source")
    trusted.new_page(width=612, height=792).insert_text((72, 72), "Trusted continuation")
    trusted_bytes = trusted.tobytes()
    trusted.close()
    replacement = fitz.open()
    replacement.new_page(width=612, height=792).insert_text((72, 72), "Different source")
    replacement.new_page(width=612, height=792).insert_text((72, 72), "Different continuation")
    replacement_bytes = replacement.tobytes()
    replacement.close()
    data = _document().model_dump(mode="json")
    data["source_sha256"] = hashlib.sha256(trusted_bytes).hexdigest()
    canonical = IntermediateDocument.model_validate(data)

    exported = build_canonical_export_pdf(
        replacement_bytes,
        canonical,
        [{"task_id": "task-habitat", "response_region_id": "r-a", "answer_text": "A"}],
    )
    output = fitz.open(stream=exported, filetype="pdf")
    try:
        assert output.page_count == 3
        assert "A" not in output[0].get_text()
        assert "A" in output[2].get_text()
    finally:
        output.close()


def test_canonical_export_revalidates_a_mutated_document_before_drawing():
    canonical = _document()
    canonical.response_region("r-a").bbox = [60, 130, 500, 500]
    source = fitz.open()
    source.new_page(width=612, height=792)
    source.new_page(width=612, height=792)
    source_bytes = source.tobytes()
    source.close()

    with pytest.raises(ValueError, match="canonical document validation failed"):
        build_canonical_export_pdf(
            source_bytes,
            canonical,
            [{"task_id": "task-habitat", "response_region_id": "r-a", "answer_text": "A"}],
        )


def test_choice_only_task_defaults_to_the_safe_side_panel_and_review_split_preserves_choice_mapping():
    student_manifest = build_manifest(
        "assignment-1",
        "Habitats",
        document=_document(),
        review_mode="direct",
    )
    view = student_manifest.to_client_document()["tasks"][0]
    assert view["label"] is None
    assert view["subpart"] is None
    assert view["response_target_id"] == "task-habitat:side-panel"
    assert view["response_regions"][0]["choice_id"] == "choice-a"

    manifest = build_manifest(
        "assignment-1",
        "Habitats",
        document=_document(),
        review_mode="teacher",
    )
    assert manifest.to_client_document()["tasks"][0]["label"] == "8"

    accepted = apply_review_actions(
        manifest,
        [{"action": "accept", "task_id": "task-habitat"}],
    )
    assert accepted.document.task("task-habitat").side_panel_fallback is True

    split = apply_review_actions(
        manifest,
        [
            {
                "action": "split",
                "task_id": "task-habitat",
                "parts": [
                    {
                        "prompt_block_ids": ["p0"],
                        "prompt_text": "Choose the best habitat and explain why.",
                        "response_region_ids": ["r-a", "r-b"],
                    },
                    {
                        "prompt_block_ids": ["p1"],
                        "prompt_text": "Explain your choice on the next page.",
                        "response_region_ids": ["r-c", "r-d", "r-explain"],
                    },
                ],
            }
        ],
    )
    first, second = split.document.tasks[:2]
    assert [(link.role.value, link.choice_id) for link in first.response_links] == [
        ("choice", "choice-a"),
        ("choice", "choice-b"),
    ]
    assert [choice.id for choice in first.choices] == ["choice-a", "choice-b"]
    assert [(link.role.value, link.choice_id) for link in second.response_links[:2]] == [
        ("choice", "choice-c"),
        ("choice", "choice-d"),
    ]
    assert [choice.id for choice in second.choices] == ["choice-c", "choice-d"]


def test_teacher_review_cannot_expand_a_response_region_beyond_its_source_evidence():
    manifest = build_manifest(
        "assignment-1",
        "Habitats",
        document=_document(),
        review_mode="teacher",
    )
    with pytest.raises(ValueError, match="must fit within its physical response evidence"):
        apply_review_actions(
            manifest,
            [
                {
                    "action": "edit",
                    "task_id": "task-habitat",
                    "answer_bbox": [60, 130, 500, 500],
                    "approve": True,
                }
            ],
        )


def test_session_state_is_independent_for_multiple_response_regions(monkeypatch):
    manifest = build_manifest("assignment-1", "Habitats", document=_document())
    tasks = manifest.to_questions_dict()
    stored: dict[str, bytes] = {}

    def upload(session_id, payload, **_kwargs):
        stored[session_id] = payload
        return ("memory", 1)

    def download(session_id, **_kwargs):
        return stored[session_id], 1

    monkeypatch.setattr(session_service.storage, "upload_session_to_gcs", upload)
    monkeypatch.setattr(session_service.storage, "download_session_from_gcs", download)
    created = session_service.create_session("assignment-1", tasks)
    task = tasks[0]
    answer_target = "r-a"
    explanation_target = "r-explain"

    answer = session_service.confirm_answer(
        created["session_id"],
        created["session_secret"],
        task_id=task["task_id"],
        response_region_id=answer_target,
        answer_text="A",
    )
    explanation = session_service.confirm_answer(
        created["session_id"],
        created["session_secret"],
        task_id=task["task_id"],
        response_region_id=explanation_target,
        answer_text="It retains water.",
    )
    state = session_service.load_session(created["session_id"])
    session_service.validate_write_token(
        state,
        task["task_id"],
        answer_target,
        "A",
        answer["write_token"],
    )
    session_service.mark_answer_written(state, task["task_id"], answer_target, "A", task)
    state = session_service.load_session(created["session_id"])
    session_service.validate_write_token(
        state,
        task["task_id"],
        explanation_target,
        "It retains water.",
        explanation["write_token"],
    )
    session_service.mark_answer_written(
        state, task["task_id"], explanation_target, "It retains water.", task
    )

    restored = session_service.restore_session_for_client(
        created["session_id"], created["session_secret"]
    )
    assert restored["responses"][answer_target]["written_answer"] == "A"
    assert restored["responses"][explanation_target]["written_answer"] == "It retains water."
