"""Teacher-review operations over the canonical document, never a flat copy."""
from __future__ import annotations

from document_model import (
    BlockSemanticRole,
    CoordinateSpace,
    DocumentResponseRegion,
    DocumentTask,
    IntermediateDocument,
    ResponseRegionType,
    ResponseSafety,
    ReviewStatus,
    SourceKind,
    page_has_reliable_native_write_evidence,
    source_prompt_text,
    stable_task_id,
    task_has_native_local_prompt_evidence,
    task_has_student_write_role,
)
from manifest import AssignmentManifest, validate_bbox_within_page


_PHYSICAL_RESPONSE_BLOCK_LABELS = {
    "answer_line",
    "bounded_box",
    "checkbox",
    "form_field",
    "writable_area",
}


def _page_geometry(document: IntermediateDocument) -> dict[int, tuple[float, float]]:
    return {
        page.page_index: (page.width_points, page.height_points)
        for page in document.pages
    }


def _find_task(document: IntermediateDocument, task_id: str) -> DocumentTask:
    try:
        return document.task(task_id)
    except KeyError as exc:
        raise ValueError(f"Unknown task_id: {task_id}") from exc


def _task_region_ids(task: DocumentTask) -> set[str]:
    return {link.response_region_id for link in task.response_links}


def _source_prompt_text(document: IntermediateDocument, prompt_block_ids: list[str]) -> str:
    block_by_id = {block.id: block for block in document.blocks}
    return source_prompt_text([block_by_id[block_id] for block_id in prompt_block_ids])


def _region_for_edit(document: IntermediateDocument, task: DocumentTask) -> DocumentResponseRegion | None:
    for link in sorted(task.response_links, key=lambda item: item.order):
        if link.role.value == "answer":
            return document.response_region(link.response_region_id)
    if task.response_links:
        return document.response_region(task.response_links[0].response_region_id)
    return None


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


def _apply_bbox(
    document: IntermediateDocument,
    task: DocumentTask,
    answer_bbox: list[float] | None,
    *,
    page_index: int,
    geometry: dict[int, tuple[float, float]],
) -> None:
    """Edit only an already-evidenced response region; never invent one."""
    if answer_bbox is None:
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
    region = _region_for_edit(document, task)
    if region is None:
        raise ValueError("answer_bbox cannot create a response region without physical evidence")
    if region.page_index != page_index:
        raise ValueError("answer_bbox cannot move a response region across pages")
    block_by_id = {block.id: block for block in document.blocks}
    if not any(
        block.source == SourceKind.pdf_geometry
        and block.semantic_role == BlockSemanticRole.response_area
        and block.block_label in _PHYSICAL_RESPONSE_BLOCK_LABELS
        and block.block_label == region.region_type.value
        and block.bbox is not None
        and block.bbox[0] <= bbox[0]
        and block.bbox[1] <= bbox[1]
        and bbox[2] <= block.bbox[2]
        and bbox[3] <= block.bbox[3]
        for block_id in region.source_block_ids
        if (block := block_by_id.get(block_id)) is not None
    ):
        raise ValueError("answer_bbox must fit within its physical response evidence")
    if not task_has_native_local_prompt_evidence(task, region, block_by_id):
        raise ValueError("answer_bbox requires native, local prompt evidence")
    region.bbox = bbox


def _approve_regions(document: IntermediateDocument, task: DocumentTask) -> None:
    block_by_id = {block.id: block for block in document.blocks}
    for link in task.response_links:
        region = document.response_region(link.response_region_id)
        if region.safety == ResponseSafety.approved:
            # Existing records remain representable. New promotion below is
            # the only operation that can grant fresh write authority.
            continue
        page = document.page(region.page_index)
        if (
            page.coordinate_space != CoordinateSpace.pdf_points
            or page.rotation != 0
            or page.display_transform_required
            or not page_has_reliable_native_write_evidence(page)
            or not task_has_student_write_role(task, page)
        ):
            raise ValueError("response regions without reliable native page evidence require the side-panel fallback")
        if region.region_type == ResponseRegionType.checkbox:
            # Review cannot promote a newly uncertain checkbox into a text
            # write target without a deterministic mark renderer.
            raise ValueError("checkbox response regions require a deterministic mark renderer")
        if not task_has_native_local_prompt_evidence(task, region, block_by_id):
            raise ValueError("response region requires native, local prompt evidence")
        if not any(
            block.source == SourceKind.pdf_geometry
            and block.semantic_role == BlockSemanticRole.response_area
            and block.block_label in _PHYSICAL_RESPONSE_BLOCK_LABELS
            and block.block_label == region.region_type.value
            and block.bbox is not None
            and block.bbox[0] <= region.bbox[0]
            and block.bbox[1] <= region.bbox[1]
            and region.bbox[2] <= block.bbox[2]
            and region.bbox[3] <= block.bbox[3]
            for block_id in region.source_block_ids
            if (block := block_by_id.get(block_id)) is not None
        ):
            raise ValueError("response region lacks deterministic physical response evidence")
        region.safety = ResponseSafety.approved


def _refresh_task_fallback(document: IntermediateDocument, task: DocumentTask) -> None:
    task.side_panel_fallback = (
        not task.response_links
        or not any(link.role.value == "answer" for link in task.response_links)
        or any(
        document.response_region(link.response_region_id).safety != ResponseSafety.approved
        for link in task.response_links
        )
    )


def _reorder_tasks(document: IntermediateDocument) -> None:
    for order, task in enumerate(sorted(document.tasks, key=lambda item: (item.order, item.id))):
        task.order = order
    document.tasks.sort(key=lambda item: item.order)


def _merge_tasks(document: IntermediateDocument, action: dict) -> None:
    task_ids = list(action.get("task_ids") or [])
    if len(task_ids) < 2:
        raise ValueError("merge requires at least two task_ids")
    sources = [_find_task(document, task_id) for task_id in task_ids]
    source_ids = {task.id for task in sources}
    first = min(sources, key=lambda item: item.order)
    prompt_block_ids = list(dict.fromkeys(block_id for task in sources for block_id in task.prompt_block_ids))
    if not prompt_block_ids:
        raise ValueError("merge requires source-backed prompt evidence")
    prompt_text = _source_prompt_text(document, prompt_block_ids)
    requested_prompt_text = action.get("prompt_text")
    if requested_prompt_text is not None and str(requested_prompt_text).strip() != prompt_text:
        raise ValueError("prompt_text must match the selected source blocks")
    label = action.get("label", first.label)
    merged_id = stable_task_id(first.anchor_page_index, prompt_block_ids, prompt_text)
    response_links = [
        link.model_copy(deep=True)
        for task in sources
        for link in sorted(task.response_links, key=lambda item: item.order)
    ]
    for order, link in enumerate(response_links):
        link.order = order
    merged = DocumentTask(
        id=merged_id,
        legacy_question_id=first.legacy_question_id,
        order=first.order,
        label=label,
        prompt_text=prompt_text,
        anchor_page_index=first.anchor_page_index,
        page_role=first.page_role,
        prompt_block_ids=prompt_block_ids,
        parent_task_id=first.parent_task_id,
        subpart=first.subpart,
        choices=[choice.model_copy(deep=True) for task in sources for choice in task.choices],
        response_links=response_links,
        side_panel_fallback=True,
        response_type=first.response_type,
        confidence=min(task.confidence for task in sources),
        review_status=ReviewStatus.approved if action.get("approve", False) else ReviewStatus.needs_review,
    )
    if action.get("approve", False):
        _approve_regions(document, merged)
    _refresh_task_fallback(document, merged)
    document.tasks = [task for task in document.tasks if task.id not in source_ids] + [merged]
    for task in document.tasks:
        if task.parent_task_id in source_ids:
            task.parent_task_id = merged.id
    _reorder_tasks(document)


def _split_task(document: IntermediateDocument, task: DocumentTask, action: dict) -> None:
    parts = list(action.get("parts") or [])
    if len(parts) < 2:
        raise ValueError("split requires at least two parts")
    original_block_ids = set(task.prompt_block_ids)
    for link in task.response_links:
        original_block_ids.update(document.response_region(link.response_region_id).source_block_ids)
    replacements: list[DocumentTask] = []
    used_legacy_ids = {item.legacy_question_id for item in document.tasks if item.id != task.id}
    next_legacy_id = max([task.legacy_question_id, *used_legacy_ids], default=0) + 1
    for part_index, part in enumerate(parts):
        prompt_ids = list(part.get("prompt_block_ids") or part.get("source_blocks") or [])
        if not prompt_ids:
            raise ValueError("each split part requires prompt_block_ids")
        if not set(prompt_ids).issubset(original_block_ids):
            raise ValueError("split part referenced blocks outside the original task")
        prompt_text = _source_prompt_text(document, prompt_ids)
        requested_prompt_text = part.get("prompt_text")
        if requested_prompt_text is not None and str(requested_prompt_text).strip() != prompt_text:
            raise ValueError("split prompt_text must match the selected source blocks")
        response_region_ids = list(part.get("response_region_ids") or [])
        if not response_region_ids:
            response_region_ids = [
                link.response_region_id
                for link in task.response_links
                if set(document.response_region(link.response_region_id).source_block_ids).issubset(set(prompt_ids))
            ]
        for region_id in response_region_ids:
            if region_id not in _task_region_ids(task):
                raise ValueError("split part referenced a response region outside the original task")
        source_link_by_region = {link.response_region_id: link for link in task.response_links}
        response_links = [
            source_link_by_region[region_id].model_copy(update={"order": index})
            for index, region_id in enumerate(response_region_ids)
        ]
        selected_choice_ids = {
            link.choice_id for link in response_links if link.choice_id is not None
        }
        choices = [
            choice.model_copy(deep=True)
            for choice in task.choices
            if choice.id in selected_choice_ids
        ]
        page_index = int(part.get("page_index", task.anchor_page_index))
        if page_index not in _page_geometry(document):
            raise ValueError("split part references an unknown page")
        label = part.get("label")
        legacy_question_id = task.legacy_question_id if part_index == 0 else next_legacy_id
        while legacy_question_id in used_legacy_ids:
            legacy_question_id += 1
        used_legacy_ids.add(legacy_question_id)
        next_legacy_id = legacy_question_id + 1
        replacement = DocumentTask(
            id=stable_task_id(page_index, prompt_ids, prompt_text),
            legacy_question_id=legacy_question_id,
            order=task.order + part_index,
            label=label,
            prompt_text=prompt_text,
            anchor_page_index=page_index,
            page_role=task.page_role,
            prompt_block_ids=prompt_ids,
            parent_task_id=task.parent_task_id,
            subpart=part.get("subpart"),
            choices=choices,
            response_links=response_links,
            side_panel_fallback=True,
            response_type=part.get("response_type", task.response_type),
            confidence=task.confidence,
            review_status=ReviewStatus.needs_review,
        )
        _refresh_task_fallback(document, replacement)
        replacements.append(replacement)
    document.tasks = [item for item in document.tasks if item.id != task.id] + replacements
    for item in document.tasks:
        if item.parent_task_id == task.id:
            item.parent_task_id = replacements[0].id
    _reorder_tasks(document)


def apply_review_actions(
    manifest: AssignmentManifest,
    actions: list[dict],
    *,
    pdf_bytes: bytes | None = None,
    finalize: bool = False,
) -> AssignmentManifest:
    """Apply explicit review decisions directly to canonical task/region evidence."""
    if manifest.review_mode != "teacher":
        raise ValueError("Assignment was not created for teacher review")
    document = manifest.document.model_copy(deep=True)
    geometry = _page_geometry(document)

    for action in actions:
        operation = action["action"]
        if operation == "merge":
            _merge_tasks(document, action)
            continue
        task = _find_task(document, action["task_id"])
        if operation == "accept":
            _approve_regions(document, task)
            task.review_status = ReviewStatus.approved
            _refresh_task_fallback(document, task)
        elif operation == "edit":
            if action.get("prompt_text") is not None:
                requested_prompt_text = str(action["prompt_text"]).strip()
                if requested_prompt_text != task.prompt_text:
                    raise ValueError("prompt_text must match immutable source evidence")
            if "label" in action:
                task.label = action.get("label")
            if action.get("response_type") is not None:
                task.response_type = action["response_type"]
            if "answer_bbox" in action or "answer_region" in action or action.get("page_index") is not None:
                page_index = int(action.get("page_index", task.anchor_page_index))
                answer_bbox = action.get("answer_bbox")
                if answer_bbox is None and action.get("answer_region") is not None:
                    answer_bbox = _bbox_from_normalized_region(
                        action["answer_region"], page_index=page_index, geometry=geometry
                    )
                _apply_bbox(document, task, answer_bbox, page_index=page_index, geometry=geometry)
            if action.get("approve", False):
                _approve_regions(document, task)
                task.review_status = ReviewStatus.approved
            else:
                task.review_status = ReviewStatus.needs_review
            _refresh_task_fallback(document, task)
        elif operation == "hide":
            task.review_status = ReviewStatus.hidden
        elif operation == "reject":
            task.review_status = ReviewStatus.rejected
        elif operation == "split":
            _split_task(document, task, action)
        else:
            raise ValueError(f"Unsupported review action: {operation}")

    _reorder_tasks(document)
    if finalize:
        unresolved = [task.id for task in document.tasks if task.review_status == ReviewStatus.needs_review]
        if unresolved:
            raise ValueError(f"Cannot finalize with unresolved tasks: {unresolved}")
        manifest_status = "approved"
    else:
        manifest_status = "draft"
    updated = manifest.model_copy(update={"document": document, "review_status": manifest_status})
    return AssignmentManifest.model_validate(updated.model_dump(mode="json"))
