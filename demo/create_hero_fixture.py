"""Create the public synthetic worksheet used by the deterministic demo replay."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent
PDF = ROOT / "hero_worksheet.pdf"
MANIFEST = ROOT / "hero_worksheet_manifest.json"
RESULT = ROOT / "hero_compiler_result.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create() -> None:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((54, 52), "River Habitat Investigation", fontsize=18)
    page.insert_text((54, 78), "Read the data card. Answer in your own words; do not copy the example.", fontsize=10)
    page.insert_text((54, 126), "1. Study the table, then answer parts a and b.", fontsize=12)
    page.draw_rect(fitz.Rect(54, 145, 390, 218), color=(0.25, 0.35, 0.55), width=0.8)
    page.insert_text((66, 168), "Habitat A: clear water, many insects", fontsize=10)
    page.insert_text((66, 194), "Habitat B: cloudy water, few insects", fontsize=10)
    page.insert_text((54, 256), "a. Which habitat would best support fish?", fontsize=12)
    page.draw_line((54, 281), (455, 281), color=(0, 0, 0), width=0.8)
    page.insert_text((54, 326), "b. Explain one piece of evidence from the table.", fontsize=12)
    page.draw_line((54, 351), (455, 351), color=(0, 0, 0), width=0.8)
    page.insert_text((54, 414), "2. Sketch a food-chain arrow diagram using the data card.", fontsize=12)
    page.insert_text((54, 436), "Use the side response panel if the drawing area is unclear.", fontsize=10)
    doc.set_metadata({"title": "Claros Synthetic Hero Worksheet", "author": "Claros demo fixture"})
    doc.save(PDF)
    doc.close()

    sha = _hash(PDF)
    physical = {
        "pilot_id": "claros-hero-v1",
        "source_pdf": "hero_worksheet.pdf",
        "page_number": 1,
        "page_index": 0,
        "page_width_points": 612,
        "page_height_points": 792,
        "rotation": 0,
        "image": "generated-at-runtime",
        "blocks": [
            {"id": "h-title", "page_index": 0, "reading_order": 0, "text": "River Habitat Investigation", "block_label": "title", "bbox": [54, 34, 350, 60], "confidence": 1.0, "source": "native_pdf"},
            {"id": "h-instruction", "page_index": 0, "reading_order": 1, "text": "Read the data card. Answer in your own words; do not copy the example.", "block_label": "instruction", "bbox": [54, 68, 530, 85], "confidence": 1.0, "source": "native_pdf"},
            {"id": "h-q1", "page_index": 0, "reading_order": 2, "text": "1. Study the table, then answer parts a and b.", "block_label": "prompt", "bbox": [54, 114, 420, 132], "confidence": 1.0, "source": "native_pdf"},
            {"id": "h-a", "page_index": 0, "reading_order": 3, "text": "a. Which habitat would best support fish?", "block_label": "prompt", "bbox": [54, 244, 350, 262], "confidence": 1.0, "source": "native_pdf"},
            {"id": "h-b", "page_index": 0, "reading_order": 4, "text": "b. Explain one piece of evidence from the table.", "block_label": "prompt", "bbox": [54, 314, 380, 332], "confidence": 1.0, "source": "native_pdf"},
            {"id": "h-q2", "page_index": 0, "reading_order": 5, "text": "2. Sketch a food-chain arrow diagram using the data card.", "block_label": "prompt", "bbox": [54, 402, 430, 420], "confidence": 1.0, "source": "native_pdf"}
        ],
        "response_candidates": [
            {"id": "h-r-a", "page_index": 0, "reading_order": 6, "layout_label": "answer_line", "bbox": [54, 270, 455, 298], "confidence": 1.0, "source": "pdf_geometry", "safe_for_writing": True, "safety_suggestion": "safe_physical"},
            {"id": "h-r-b", "page_index": 0, "reading_order": 7, "layout_label": "answer_line", "bbox": [54, 340, 455, 368], "confidence": 1.0, "source": "pdf_geometry", "safe_for_writing": True, "safety_suggestion": "safe_physical"}
        ],
        "warnings": ["synthetic_demo_fixture"]
    }
    result = {
        "page_index": 0,
        "page_role": "student_worksheet",
        "selected_block_ids": ["h-q1", "h-a", "h-b", "h-q2"],
        "rejected_blocks": [{"block_id": "h-title", "reason": "navigation"}, {"block_id": "h-instruction", "reason": "teacher_instruction"}],
        "groupings": [
            {"group_index": 1, "prompt_block_ids": ["h-q1"], "visual_anchor_block_ids": [], "parent_group_index": None, "subpart": None, "response_candidate_ids": [], "response_disposition": "side_panel_only", "needs_review": True, "reason": "compound prompt has no single response region"},
            {"group_index": 2, "prompt_block_ids": ["h-a"], "visual_anchor_block_ids": [], "parent_group_index": 1, "subpart": "a", "response_candidate_ids": ["h-r-a"], "response_disposition": "safe_physical", "needs_review": False, "reason": "explicit answer line"},
            {"group_index": 3, "prompt_block_ids": ["h-b"], "visual_anchor_block_ids": [], "parent_group_index": 1, "subpart": "b", "response_candidate_ids": ["h-r-b"], "response_disposition": "safe_physical", "needs_review": False, "reason": "explicit answer line"},
            {"group_index": 4, "prompt_block_ids": ["h-q2"], "visual_anchor_block_ids": [], "parent_group_index": None, "subpart": None, "response_candidate_ids": [], "response_disposition": "side_panel_only", "needs_review": True, "reason": "drawing placement is intentionally uncertain"}
        ],
        "selected_response_candidate_ids": ["h-r-a", "h-r-b"],
        "needs_review": True,
        "reason": "synthetic fixture; replay is deterministic and not a live provider result"
    }
    MANIFEST.write_text(json.dumps({"source_type": "synthetic", "source_sha256": sha, "original_or_synthetic": "synthetic", "stored_result_origin": "synthetic fixture; not live GPT-5.6", "replay": True, "physical_input": physical}, indent=2) + "\n", encoding="utf-8")
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    create()
