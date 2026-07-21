#!/usr/bin/env python3
"""Build an isolated Label Studio project for the Claros PDF gold pilot."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import fitz

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from document_model import DocumentBlock, SourceKind
from document_pipeline import _native_blocks, _physical_response_blocks
from parser import parse_pdf_with_diagnostics

HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = Path(
    r"C:\Users\Chimdumebi\Downloads\claros-pdf-acceptance-corpus\claros-pdf-corpus"
)
DEFAULT_OUTPUT = ROOT / "output" / "pdf-gold-pilot"
RESPONSE_LABELS = {"answer_line", "form_field", "horizontal_rule_candidate"}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_selection(payload: dict) -> list[dict]:
    pages = payload.get("pages") or []
    if not 12 <= len(pages) <= 20:
        raise ValueError("pilot selection must contain 12 to 20 pages")
    pilot_ids = [item.get("pilot_id") for item in pages]
    coordinates = [(item.get("source_pdf"), item.get("page_number")) for item in pages]
    if None in pilot_ids or len(pilot_ids) != len(set(pilot_ids)):
        raise ValueError("pilot IDs must be present and unique")
    if len(coordinates) != len(set(coordinates)):
        raise ValueError("selected source pages must be unique")
    for item in pages:
        if not isinstance(item.get("page_number"), int) or item["page_number"] < 1:
            raise ValueError(f"invalid page number for {item['pilot_id']}")
    return pages


def _corpus_dir(root: Path, subdirectory: str) -> Path:
    nested = root / subdirectory
    return nested if nested.is_dir() else root


def _load_paddle_cache(path: Path | None) -> dict[tuple[str, int], list[DocumentBlock]]:
    if path is None:
        return {}
    payload = _load_json(path)
    result: dict[tuple[str, int], list[DocumentBlock]] = {}
    for page in payload.get("pages") or []:
        key = (str(page["source_pdf"]), int(page["page_number"]))
        blocks = []
        for raw in page.get("blocks") or []:
            block = DocumentBlock.model_validate(raw)
            if block.source != SourceKind.paddleocr:
                raise ValueError(f"non-Paddle block found in Paddle cache for {key}")
            blocks.append(block)
        result[key] = blocks
    return result


def _rectangle_value(bbox: list[float], width: float, height: float, labels: list[str]) -> dict:
    x0, y0, x1, y1 = bbox
    return {
        "x": round(100 * x0 / width, 6),
        "y": round(100 * y0 / height, 6),
        "width": round(100 * (x1 - x0) / width, 6),
        "height": round(100 * (y1 - y0) / height, 6),
        "rotation": 0,
        "rectanglelabels": labels,
    }


def _prediction_results(
    blocks: list[DocumentBlock],
    responses: list[dict],
    *,
    page_width: float,
    page_height: float,
) -> list[dict]:
    results: list[dict] = []
    for block in blocks:
        region_id = block.id
        results.extend(
            [
                {
                    "id": region_id,
                    "from_name": "region_labels",
                    "to_name": "page_image",
                    "type": "rectanglelabels",
                    "score": block.confidence,
                    "value": _rectangle_value(block.bbox, page_width, page_height, ["other"]),
                },
                {
                    "id": region_id,
                    "from_name": "physical_block_id",
                    "to_name": "page_image",
                    "type": "textarea",
                    "value": {"text": [block.id]},
                },
                {
                    "id": region_id,
                    "from_name": "physical_text",
                    "to_name": "page_image",
                    "type": "textarea",
                    "value": {"text": [block.text]},
                },
            ]
        )
    response_type_label = {
        "answer_line": "response_line",
        "horizontal_rule_candidate": "response_line",
        "form_field": "response_box",
    }
    for candidate in responses:
        region_id = candidate["id"]
        results.extend(
            [
                {
                    "id": region_id,
                    "from_name": "region_labels",
                    "to_name": "page_image",
                    "type": "rectanglelabels",
                    "score": candidate["confidence"],
                    "value": _rectangle_value(
                        candidate["bbox"],
                        page_width,
                        page_height,
                        [response_type_label[candidate["layout_label"]]],
                    ),
                },
                {
                    "id": region_id,
                    "from_name": "physical_block_id",
                    "to_name": "page_image",
                    "type": "textarea",
                    "value": {"text": [candidate["id"]]},
                },
                {
                    "id": region_id,
                    "from_name": "response_safety",
                    "to_name": "page_image",
                    "type": "choices",
                    "value": {"choices": [candidate["safety_suggestion"]]},
                },
            ]
        )
    return results


def _response_candidate(block: DocumentBlock) -> dict:
    safe = block.block_label in {"answer_line", "form_field"} and block.confidence >= 0.85
    return {
        "id": block.id,
        "page_index": block.page_index,
        "reading_order": block.reading_order,
        "layout_label": block.block_label,
        "bbox": block.bbox,
        "confidence": block.confidence,
        "source": block.source.value,
        "safe_for_writing": safe,
        "safety_suggestion": "safe_physical" if safe else "ambiguous",
    }


def _render_original(page: fitz.Page, path: Path, dpi: int) -> None:
    scale = dpi / 72.0
    page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(path)


def _render_physical_overlay(
    page: fitz.Page,
    path: Path,
    blocks: list[DocumentBlock],
    responses: list[dict],
    dpi: int,
) -> None:
    for block in blocks:
        color = (0.45, 0.45, 0.45) if block.source == SourceKind.native_pdf else (0.45, 0.15, 0.75)
        page.draw_rect(fitz.Rect(block.bbox), color=color, width=0.7, overlay=True)
    for candidate in responses:
        color = (0.0, 0.55, 0.2) if candidate["safe_for_writing"] else (0.95, 0.65, 0.0)
        page.draw_rect(fitz.Rect(candidate["bbox"]), color=color, width=1.8, overlay=True)
    banner = fitz.Rect(0, 0, min(page.rect.width, 540), 19)
    page.draw_rect(banner, fill=(1, 1, 1), color=None, overlay=True)
    page.insert_text(
        (4, 13),
        "suggestions only: gray=native, purple=Paddle, green=safe candidate, yellow=ambiguous",
        fontsize=7,
        color=(0.1, 0.1, 0.1),
        overlay=True,
    )
    _render_original(page, path, dpi)


def _legacy_by_page(path: Path) -> dict:
    started = time.perf_counter()
    _title, questions, warnings, status = parse_pdf_with_diagnostics(path)
    by_page: dict[int, list[dict]] = defaultdict(list)
    for question in questions:
        by_page[question.page].append(
            {
                "id": question.id,
                "label": question.label,
                "text": question.text,
                "prompt_region": question.prompt_region,
                "answer_region": question.answer_region,
                "layout_confidence": question.layout_confidence,
                "needs_layout_review": question.needs_layout_review,
            }
        )
    return {
        "pages": by_page,
        "warnings": warnings,
        "status": status,
        "processing_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _stored_comparison() -> dict[str, dict]:
    path = ROOT / "output" / "pdf-benchmark-final" / "comparison.json"
    if not path.exists():
        return {}
    return {row["filename"]: row for row in _load_json(path).get("results") or []}


def build(args: argparse.Namespace) -> dict:
    selection_payload = _load_json(args.selection)
    selected_pages = _validate_selection(selection_payload)
    corpus_dir = _corpus_dir(args.corpus.resolve(), selection_payload.get("corpus_subdirectory", "corpus"))
    output = args.out.resolve()
    rendered_dir = output / "rendered"
    overlay_dir = output / "physical-overlays"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.selection, output / "selection.json")
    shutil.copyfile(HERE / "label_studio_config.xml", output / "label_studio_config.xml")
    shutil.copyfile(HERE / "annotation-protocol.md", output / "annotation-protocol.md")
    shutil.copyfile(HERE / "evaluation-protocol.md", output / "evaluation-protocol.md")

    paddle_cache = _load_paddle_cache(args.paddle_cache)
    stored = _stored_comparison()
    legacy_cache: dict[str, dict] = {}
    inputs: list[dict] = []
    tasks: list[dict] = []
    baselines: list[dict] = []

    for selection in selected_pages:
        source_pdf = selection["source_pdf"]
        source_path = corpus_dir / source_pdf
        if not source_path.is_file():
            raise FileNotFoundError(f"selected corpus PDF is missing: {source_path}")
        page_number = selection["page_number"]
        page_index = page_number - 1
        document = fitz.open(source_path)
        try:
            if page_index >= document.page_count:
                raise IndexError(f"{source_pdf} does not contain page {page_number}")
            page = document[page_index]
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)
            page_rotation = int(page.rotation) % 360
            rendered_name = f"{selection['pilot_id']}.png"
            rendered_path = rendered_dir / rendered_name
            overlay_path = overlay_dir / rendered_name
            _render_original(page, rendered_path, args.dpi)

            native = _native_blocks(page, page_index)
            physical = _physical_response_blocks(page, page_index, len(native), native)
            cached_paddle = paddle_cache.get((source_pdf, page_number), [])
            prompt_blocks = native + [block for block in cached_paddle if block.block_label not in RESPONSE_LABELS]
            response_blocks = physical + [block for block in cached_paddle if block.block_label in RESPONSE_LABELS]
            responses = [_response_candidate(block) for block in response_blocks]
            _render_physical_overlay(page, overlay_path, prompt_blocks, responses, args.dpi)
        finally:
            document.close()

        page_warnings = []
        if not cached_paddle:
            page_warnings.append("structured_paddle_cache_unavailable")
        if not prompt_blocks:
            page_warnings.append("no_machine_readable_blocks_for_preannotation")
        physical_input = {
            "pilot_id": selection["pilot_id"],
            "source_pdf": source_pdf,
            "page_number": page_number,
            "page_index": page_index,
            "page_width_points": page_width,
            "page_height_points": page_height,
            "rotation": page_rotation,
            "image": f"rendered/{rendered_name}",
            "blocks": [block.model_dump(mode="json") for block in prompt_blocks],
            "response_candidates": responses,
            "warnings": page_warnings,
        }
        inputs.append(physical_input)

        prediction = _prediction_results(
            prompt_blocks,
            responses,
            page_width=physical_input["page_width_points"],
            page_height=physical_input["page_height_points"],
        )
        tasks.append(
            {
                "id": len(tasks) + 1,
                "data": {
                    "image": f"/data/local-files/?d={quote(physical_input['image'])}",
                    "pilot_id": selection["pilot_id"],
                    "source_pdf": source_pdf,
                    "page_number": page_number,
                    "selection_context": selection["selection_rationale"],
                    "selection_expectation_not_gold": selection["expected_page_type"],
                },
                "predictions": [
                    {
                        "model_version": "physical-suggestions-v1-not-gold",
                        "score": 0.0,
                        "result": prediction,
                    }
                ],
            }
        )

        if source_pdf not in legacy_cache:
            legacy_cache[source_pdf] = _legacy_by_page(source_path)
        legacy = legacy_cache[source_pdf]
        stored_row = stored.get(source_pdf, {})
        semantic_root = "pdf-benchmark-scans-combined" if source_pdf.startswith(("03_", "10_", "18_")) else "pdf-benchmark-semantic-full"
        semantic_overlay = ROOT / "output" / semantic_root / source_path.stem / f"page-{page_number:02d}-overlay.png"
        current_overlay = ROOT / "output" / "pdf-benchmark-current" / source_path.stem / f"page-{page_number:02d}-overlay.png"
        roles = stored_row.get("page_role_classification") or []
        baselines.append(
            {
                "pilot_id": selection["pilot_id"],
                "legacy": {
                    "source": "fresh_unmodified_legacy_parse",
                    "page_tasks": legacy["pages"].get(page_number, []),
                    "document_processing_ms": legacy["processing_ms"],
                    "document_status": legacy["status"],
                    "document_warnings": legacy["warnings"],
                    "overlay_path": str(current_overlay.resolve()) if current_overlay.exists() else None,
                },
                "free_form_gemini": {
                    "source": "stored_benchmark_summary_and_overlay",
                    "document_task_count": stored_row.get("final_claros_task_count"),
                    "page_role_prediction": roles[page_index] if page_index < len(roles) else None,
                    "overlay_path": str(semantic_overlay.resolve()) if semantic_overlay.exists() else None,
                    "scorable_against_task_gold": False,
                    "limitation": "The prior benchmark did not retain raw per-page task boxes/block membership.",
                },
            }
        )

    (output / "physical-inputs.json").write_text(
        json.dumps({"version": 1, "pages": inputs}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "label-studio-tasks.json").write_text(
        json.dumps(tasks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "baselines.json").write_text(
        json.dumps({"version": 1, "pages": baselines}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    status = {
        "selected_page_count": len(selected_pages),
        "human_gold_available": False,
        "gold_export_expected_path": str((output / "gold" / "annotations.json").resolve()),
        "label_studio_installed": bool(
            shutil.which("label-studio") or importlib.util.find_spec("label_studio")
        ),
        "structured_paddle_cache_supplied": bool(args.paddle_cache),
        "structured_paddle_cache_note": (
            "Cached benchmark overlays exist, but raw Paddle blocks were not retained. "
            "No coordinates or text were reconstructed from overlay pixels."
        ),
        "comparison_scoring_status": "blocked_until_human_gold_and_raw_free_form_predictions_exist",
    }
    (output / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--selection", type=Path, default=HERE / "selection.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--paddle-cache", type=Path)
    parser.add_argument("--dpi", type=int, default=144)
    args = parser.parse_args()
    status = build(args)
    print(
        f"Prepared {status['selected_page_count']} annotation pages; "
        f"human_gold_available={status['human_gold_available']} "
        f"label_studio_installed={status['label_studio_installed']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
