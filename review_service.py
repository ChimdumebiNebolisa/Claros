"""Teacher review operations for assignment manifests."""
from __future__ import annotations

from copy import deepcopy

import fitz

from document_model import AnswerRegionStatus, DocumentTask, PageRole, ReviewStatus, stable_task_id
from manifest import AssignmentManifest, ManifestQuestion, validate_bbox_within_page


def _page_geometry(manifest: AssignmentManifest, pdf_bytes: bytes) -> dict[int, tuple[float, float]]:
    if manifest.document is not None:
        return {
            page.page_index: (page.width_points, page.height_points)
            for page in manifest.document.pages
        }
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return {
            page_index: (float(page.rect.width), float(page.rect.height))
            for page_index, page in enumerate(document)
        }
    finally:
        document.close()


def _task_key(question: ManifestQuestion) -> str:
    return question.task_id or f"legacy-{question.id}"


def _find(questions: list[ManifestQuestion], task_id: str) -> ManifestQuestion:
    question = next((item for item in questions if _task_key(item) == task_id), None)
    if question is None:
        raise ValueError(f"Unknown task_id: {task_id}")
    return question


def _apply_bbox(
    question: ManifestQuestion,
    answer_bbox: list[float] | None,
    *,
    page_index: int,
    geometry: dict[int, tuple[float, float]],
) -> None:
    question.page_index = page_index
    question.page = page_index + 1
    if answer_bbox is None:
        question.answer_bbox = None
        question.answer_region = None
        question.answer_region_status = AnswerRegionStatus.side_panel.value
        return
    page_size = geometry.get(page_index)
    if page_size is None:
        raise ValueError("answer_bbox references an unknown page")
    bbox = validate_bbox_within_page(
        answer_bbox,
        page_width=page_size[0],
        page_height=page_size[1],
        label="answer_bbox",
    )
    question.answer_bbox = bbox
    question.answer_region = {
        "x": round(bbox[0] / page_size[0], 6),
        "y": round(bbox[1] / page_size[1], 6),
        "width": round((bbox[2] - bbox[0]) / page_size[0], 6),
        "height": round((bbox[3] - bbox[1]) / page_size[1], 6),
    }
    question.detected_answer_region = deepcopy(question.answer_region)
    question.answer_region_status = AnswerRegionStatus.approved.value


def _bbox_from_normalized_region(
    region: dict | None,
    *,
    page_index: int,
    geometry: dict[int, tuple[float, float]],
) -> list[float] | None:
    if region is None:
        return None
    page_size = geometry.get(page_index)
    if page_size is None:
        raise ValueError("answer_region references an unknown page")
    try:
        x = float(region["x"])
        y = float(region["y"])
        width = float(region["width"])
        height = float(region["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("answer_region is invalid") from exc
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ValueError("answer_region is outside the page")
    return [
        x * page_size[0],
        y * page_size[1],
        (x + width) * page_size[0],
        (y + height) * page_size[1],
    ]


def apply_review_actions(
    manifest: AssignmentManifest,
    actions: list[dict],
    *,
    pdf_bytes: bytes,
    finalize: bool = False,
) -> AssignmentManifest:
    """Apply explicit teacher decisions; no action invents an answer region."""
    if manifest.review_mode != "teacher":
        raise ValueError("Assignment was not created for teacher review")
    updated = manifest.model_copy(deep=True)
    questions = updated.questions
    geometry = _page_geometry(updated, pdf_bytes)

    for action in actions:
        operation = action["action"]
        if operation in {"accept", "edit", "hide", "reject", "split"}:
            question = _find(questions, action["task_id"])
        if operation == "accept":
            question.approved = True
            question.needs_layout_review = False
            question.review_status = ReviewStatus.approved.value
            question.answer_region_status = (
                AnswerRegionStatus.approved.value if question.answer_region else AnswerRegionStatus.side_panel.value
            )
        elif operation == "edit":
            if action.get("prompt_text") is not None:
                prompt_text = action["prompt_text"].strip()
                if not prompt_text:
                    raise ValueError("prompt_text cannot be empty")
                question.text = prompt_text
            if "label" in action:
                question.label = action.get("label")
            if action.get("response_type") is not None:
                question.response_type = action["response_type"]
            if "answer_bbox" in action or "answer_region" in action or action.get("page_index") is not None:
                page_index = int(action.get("page_index", question.page_index or question.page - 1))
                answer_bbox = action.get("answer_bbox")
                if answer_bbox is None and action.get("answer_region") is not None:
                    answer_bbox = _bbox_from_normalized_region(
                        action["answer_region"],
                        page_index=page_index,
                        geometry=geometry,
                    )
                _apply_bbox(
                    question,
                    answer_bbox,
                    page_index=page_index,
                    geometry=geometry,
                )
            question.approved = bool(action.get("approve", False))
            question.needs_layout_review = not question.approved
            question.review_status = (
                ReviewStatus.approved.value if question.approved else ReviewStatus.needs_review.value
            )
        elif operation == "hide":
            question.approved = False
            question.needs_layout_review = False
            question.review_status = ReviewStatus.hidden.value
        elif operation == "reject":
            question.approved = False
            question.needs_layout_review = False
            question.review_status = ReviewStatus.rejected.value
        elif operation == "merge":
            task_ids = action.get("task_ids") or []
            if len(task_ids) < 2:
                raise ValueError("merge requires at least two task_ids")
            sources = [_find(questions, task_id) for task_id in task_ids]
            page_indexes = {item.page_index if item.page_index is not None else item.page - 1 for item in sources}
            if len(page_indexes) != 1:
                raise ValueError("merge cannot cross PDF pages")
            first = sources[0]
            first.text = (action.get("prompt_text") or "\n".join(item.text for item in sources)).strip()
            first.label = action.get("label", first.label)
            first.source_blocks = list(dict.fromkeys(block for item in sources for block in item.source_blocks))
            first.task_id = stable_task_id(next(iter(page_indexes)), first.label, first.source_blocks, first.text)
            _apply_bbox(
                first,
                action.get("answer_bbox"),
                page_index=next(iter(page_indexes)),
                geometry=geometry,
            )
            first.approved = bool(action.get("approve", False))
            first.needs_layout_review = not first.approved
            first.review_status = ReviewStatus.approved.value if first.approved else ReviewStatus.needs_review.value
            questions = [item for item in questions if item is first or item not in sources]
        elif operation == "split":
            parts = action.get("parts") or []
            if len(parts) < 2:
                raise ValueError("split requires at least two parts")
            original_blocks = set(question.source_blocks)
            replacements = []
            for part in parts:
                prompt_text = str(part.get("prompt_text") or "").strip()
                source_blocks = list(part.get("source_blocks") or [])
                if not prompt_text or not source_blocks:
                    raise ValueError("each split part requires prompt_text and source_blocks")
                if original_blocks and not set(source_blocks).issubset(original_blocks):
                    raise ValueError("split part referenced blocks outside the original task")
                page_index = int(part.get("page_index", question.page_index or question.page - 1))
                replacement = ManifestQuestion(
                    id=1,
                    task_id=stable_task_id(page_index, part.get("label"), source_blocks, prompt_text),
                    label=part.get("label"),
                    text=prompt_text,
                    page=page_index + 1,
                    page_index=page_index,
                    page_role=question.page_role,
                    prompt_bbox=part.get("prompt_bbox"),
                    response_type=part.get("response_type", question.response_type),
                    confidence=question.confidence,
                    needs_layout_review=True,
                    review_status=ReviewStatus.needs_review.value,
                    answer_region_status=AnswerRegionStatus.side_panel.value,
                    source_blocks=source_blocks,
                    approved=False,
                )
                _apply_bbox(
                    replacement,
                    part.get("answer_bbox"),
                    page_index=page_index,
                    geometry=geometry,
                )
                replacements.append(replacement)
            index = questions.index(question)
            questions[index : index + 1] = replacements
        else:
            raise ValueError(f"Unsupported review action: {operation}")

    for index, question in enumerate(questions, start=1):
        question.id = index
    updated.questions = questions
    if updated.document is not None:
        updated.document.tasks = [
            DocumentTask(
                id=question.task_id,
                legacy_question_id=question.id,
                label=question.label,
                prompt_text=question.text,
                page_index=question.page_index if question.page_index is not None else question.page - 1,
                page_role=PageRole(question.page_role),
                prompt_bbox=question.prompt_bbox,
                answer_bbox=question.answer_bbox,
                response_type=question.response_type,
                confidence=question.confidence,
                review_status=ReviewStatus(question.review_status),
                answer_region_status=AnswerRegionStatus(question.answer_region_status),
                source_blocks=question.source_blocks,
            )
            for question in questions
            if question.task_id and question.source_blocks
        ]
    if finalize:
        unresolved = [
            _task_key(question)
            for question in questions
            if question.review_status == ReviewStatus.needs_review.value
        ]
        if unresolved:
            raise ValueError(f"Cannot finalize with unresolved tasks: {unresolved}")
        updated.review_status = "approved"
    else:
        updated.review_status = "draft"
    return AssignmentManifest.model_validate(updated.model_dump())
