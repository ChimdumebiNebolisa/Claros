"""Validated, hash-bound synthetic hero worksheet replay fixture."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.pdf_gold_pilot.closed_world import ClosedWorldPageResult, PilotPageInput, derive_tasks, validate_closed_world_result

ROOT = Path(__file__).resolve().parent


def load_hero(pdf_bytes: bytes) -> tuple[PilotPageInput, ClosedWorldPageResult, list[dict]] | None:
    manifest = json.loads((ROOT / "hero_worksheet_manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(pdf_bytes).hexdigest() != manifest["source_sha256"]:
        return None
    page = PilotPageInput.model_validate(manifest["physical_input"])
    result = ClosedWorldPageResult.model_validate_json((ROOT / "hero_compiler_result.json").read_text(encoding="utf-8"))
    validate_closed_world_result(page, result)
    return page, result, derive_tasks(page, result)


def manifest_questions(pdf_bytes: bytes) -> list[dict] | None:
    loaded = load_hero(pdf_bytes)
    if loaded is None:
        return None
    page, _result, tasks = loaded
    questions = []
    for index, task in enumerate(tasks, start=1):
        bbox = task["response_bbox"]
        region = None if bbox is None else {
            "x": round(bbox[0] / page.page_width_points, 6),
            "y": round(bbox[1] / page.page_height_points, 6),
            "width": round((bbox[2] - bbox[0]) / page.page_width_points, 6),
            "height": round((bbox[3] - bbox[1]) / page.page_height_points, 6),
        }
        side_panel = task["response_disposition"] != "safe_physical"
        questions.append({
            "id": index,
            "task_id": task["id"],
            "label": task["subpart"] or str(task["group_index"]),
            "text": task["prompt_text"],
            "page": 1,
            "page_index": 0,
            "page_role": task["page_role"],
            "prompt_bbox": task["prompt_bbox"],
            "answer_bbox": bbox,
            "answer_region": region,
            "detected_answer_region": region,
            "response_type": "drawing" if task["group_index"] == 4 else "short_text",
            "confidence": 1.0,
            "layout_confidence": 1.0 if region else 0.0,
            "needs_layout_review": False,
            "review_status": "needs_review" if side_panel else "auto_approved",
            "answer_region_status": "side_panel" if side_panel else "approved",
            "source_blocks": task["prompt_block_ids"],
            "approved": not side_panel,
        })
    return questions
