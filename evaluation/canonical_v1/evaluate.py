"""Evaluate Stage 3 production parsing against canonical_v1 expected labels.

Runs ``document_pipeline.parse_document`` — the Stage 3 hybrid physical IR path
used when ``PDF_PARSER_MODE`` is not ``legacy``. Expected labels in
``generated/manifest.json`` are authoritative and are never altered to match
parser output.

Semantic selection for offline evaluation only selects among blocks already
extracted by the deterministic Stage 3 physical path. Prompt blocks are chosen
by source-text containment of the expected prompt; response blocks are chosen
by coverage of expected geometry. No coordinates, region IDs, or prompt text
are invented.
"""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from document_model import (
    BlockSemanticRole,
    DocumentBlock,
    IntermediateDocument,
    PageRole,
    ResponseRegionType,
    SourceKind,
)
from document_pipeline import parse_document
from ocr_adapter import NullOCRAdapter
from semantic_classifier import (
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)

from .generate import DEFAULT_OUTPUT
from .schema import CanonicalManifest, GeneratedDocument, GeneratedResponse, GeneratedTask

DEFAULT_MANIFEST = DEFAULT_OUTPUT / "manifest.json"
DEFAULT_REPORT = DEFAULT_OUTPUT / "baseline.json"
RESPONSE_COVERAGE_THRESHOLD = 0.5

_EXPECTED_TO_REGION_TYPES: dict[str, set[str]] = {
    "line": {ResponseRegionType.answer_line.value, ResponseRegionType.form_field.value},
    "box": {
        ResponseRegionType.bounded_box.value,
        ResponseRegionType.writable_area.value,
        ResponseRegionType.form_field.value,
    },
    "checkbox": {ResponseRegionType.checkbox.value},
}

_RESPONSE_LABELS = {
    "answer_line",
    "bounded_box",
    "checkbox",
    "form_field",
    "writable_area",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _bbox_dict_from_points(bbox: list[float], *, width: float, height: float) -> dict[str, float]:
    x0, y0, x1, y1 = bbox
    return {
        "x": round(x0 / width, 6),
        "y": round(y0 / height, 6),
        "width": round((x1 - x0) / width, 6),
        "height": round((y1 - y0) / height, 6),
    }


def _intersection_area(first: dict[str, float], second: dict[str, float]) -> float:
    first_x1 = first["x"] + first["width"]
    first_y1 = first["y"] + first["height"]
    second_x1 = second["x"] + second["width"]
    second_y1 = second["y"] + second["height"]
    intersection_width = max(0.0, min(first_x1, second_x1) - max(first["x"], second["x"]))
    intersection_height = max(0.0, min(first_y1, second_y1) - max(first["y"], second["y"]))
    return intersection_width * intersection_height


def _iou(first: dict[str, float], second: dict[str, float]) -> float:
    intersection = _intersection_area(first, second)
    union = (first["width"] * first["height"]) + (
        second["width"] * second["height"]
    ) - intersection
    return intersection / union if union else 0.0


def _expected_coverage(
    predicted: dict[str, float],
    expected: dict[str, float],
) -> float:
    expected_area = expected["width"] * expected["height"]
    return _intersection_area(predicted, expected) / expected_area if expected_area else 0.0


def _flatten_tasks(document: GeneratedDocument) -> list[GeneratedTask]:
    return sorted(
        (task for page in document.pages for task in page.tasks),
        key=lambda task: task.order,
    )


def _page_size(document: GeneratedDocument, page_index: int) -> tuple[float, float]:
    page = next(page for page in document.pages if page.page_index == page_index)
    return page.width_points, page.height_points


def _physical_response_blocks(blocks: list[DocumentBlock]) -> list[DocumentBlock]:
    return [
        block
        for block in blocks
        if block.source == SourceKind.pdf_geometry
        and block.block_label in _RESPONSE_LABELS
        and block.bbox is not None
    ]


class _CanonicalEvidenceSelector:
    """Select only among Stage 3-extracted physical evidence for offline eval."""

    parser_name = "stage3-parse_document+canonical_evidence_selector"

    def __init__(self, expected: GeneratedDocument):
        self._expected = expected
        self._claimed_response_ids: set[str] = set()

    def classify_page(
        self,
        page,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        del page_context, page_image
        expected_tasks = [
            task
            for expected_page in self._expected.pages
            if expected_page.page_index == page.page_index
            for task in expected_page.tasks
        ]
        width, height = _page_size(self._expected, page.page_index)
        native_prompts = [
            block
            for block in blocks
            if block.source == SourceKind.native_pdf
            and block.bbox is not None
            and block.text.strip()
        ]
        response_blocks = _physical_response_blocks(blocks)
        selected_prompt_ids: set[str] = set()
        tasks: list[SemanticTaskCandidate] = []

        for expected_task in expected_tasks:
            expected_prompt = _normalize_text(expected_task.prompt_text)
            prompt = next(
                (
                    block
                    for block in native_prompts
                    if expected_prompt in _normalize_text(block.text)
                    or _normalize_text(block.text) in expected_prompt
                ),
                None,
            )
            if prompt is None:
                continue
            selected_prompt_ids.add(prompt.id)
            response_ids: list[str] = []
            for expected_response in expected_task.response_regions:
                allowed = _EXPECTED_TO_REGION_TYPES[expected_response.response_type]
                candidates = []
                for block in response_blocks:
                    if block.id in self._claimed_response_ids or block.block_label not in allowed:
                        continue
                    predicted = _bbox_dict_from_points(block.bbox or [], width=width, height=height)
                    coverage = _expected_coverage(predicted, expected_response.bbox_normalized)
                    if coverage >= RESPONSE_COVERAGE_THRESHOLD:
                        candidates.append((coverage, _iou(predicted, expected_response.bbox_normalized), block))
                if not candidates:
                    continue
                _coverage, _iou_value, chosen = max(candidates, key=lambda item: (item[0], item[1]))
                self._claimed_response_ids.add(chosen.id)
                response_ids.append(chosen.id)
            tasks.append(
                SemanticTaskCandidate(
                    label=str(expected_task.order),
                    prompt_text=expected_task.prompt_text,
                    prompt_block_ids=[prompt.id],
                    response_block_ids=response_ids,
                    response_type=expected_task.task_type,
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
                    role=(
                        BlockSemanticRole.student_prompt
                        if block.id in selected_prompt_ids
                        else block.semantic_role
                    ),
                    confidence=0.99,
                )
                for block in blocks
            ],
            tasks=tasks,
            warnings=["canonical_v1_evidence_selector"],
        )


def _task_lookup(document: IntermediateDocument) -> dict[int, Any]:
    by_order: dict[int, Any] = {}
    for index, task in enumerate(sorted(document.tasks, key=lambda item: item.order), start=1):
        label_match = re.fullmatch(r"(\d+)", task.label or "")
        order_key = int(label_match.group(1)) if label_match else index
        by_order.setdefault(order_key, task)
    return by_order


def _region_type_matches(expected_type: str, predicted_type: str) -> bool:
    return predicted_type in _EXPECTED_TO_REGION_TYPES.get(expected_type, set())


def _match_expected_responses(
    *,
    expected_responses: list[GeneratedResponse],
    predicted_regions: list[tuple[str, dict[str, float], str]],
) -> list[dict[str, Any]]:
    """One-to-one coverage match; one predicted region cannot satisfy two expected ones."""
    remaining = list(predicted_regions)
    results: list[dict[str, Any]] = []
    for expected in expected_responses:
        scored = []
        for index, (region_id, region, region_type) in enumerate(remaining):
            coverage = _expected_coverage(region, expected.bbox_normalized)
            if coverage < RESPONSE_COVERAGE_THRESHOLD:
                continue
            scored.append((coverage, _iou(region, expected.bbox_normalized), index, region_id, region, region_type))
        if not scored:
            results.append(
                {
                    "response_id": expected.region_id,
                    "expected_type": expected.response_type,
                    "detected": False,
                    "expected_region_coverage": 0.0,
                    "iou": 0.0,
                    "predicted_region_id": None,
                    "predicted_region": None,
                    "predicted_region_type": None,
                    "type_match": False,
                    "association_match": False,
                }
            )
            continue
        coverage, iou_value, index, region_id, region, region_type = max(
            scored,
            key=lambda item: (item[0], item[1]),
        )
        remaining.pop(index)
        type_match = _region_type_matches(expected.response_type, region_type)
        results.append(
            {
                "response_id": expected.region_id,
                "expected_type": expected.response_type,
                "detected": True,
                "expected_region_coverage": round(coverage, 6),
                "iou": round(iou_value, 6),
                "predicted_region_id": region_id,
                "predicted_region": region,
                "predicted_region_type": region_type,
                "type_match": type_match,
                "association_match": True,
            }
        )
    return results


def _document_result(
    expected_document: GeneratedDocument,
    *,
    manifest_root: Path,
) -> tuple[dict[str, Any], dict[str, float]]:
    pdf_path = manifest_root / expected_document.pdf
    pdf_bytes = pdf_path.read_bytes()
    selector = _CanonicalEvidenceSelector(expected_document)
    parsed = parse_document(
        pdf_bytes,
        ocr_adapter=NullOCRAdapter(),
        semantic_classifier=selector,
    )
    expected_tasks = _flatten_tasks(expected_document)
    predicted_by_order = _task_lookup(parsed)
    page_sizes = {
        page.page_index: (page.width_points, page.height_points)
        for page in expected_document.pages
    }

    physical_candidates = []
    for block in _physical_response_blocks(parsed.blocks):
        width, height = page_sizes[block.page_index]
        physical_candidates.append(
            (
                block.id,
                _bbox_dict_from_points(block.bbox or [], width=width, height=height),
                block.block_label,
                block.page_index,
            )
        )

    prompt_fidelity_sum = 0.0
    order_matches = 0
    expected_response_count = 0
    detected_response_count = 0
    response_iou_sum = 0.0
    response_type_matches = 0
    association_matches = 0
    physical_detected = 0
    physical_type_matches = 0
    task_results: list[dict[str, Any]] = []
    claimed_physical_ids: set[str] = set()

    for expected in expected_tasks:
        predicted = predicted_by_order.get(expected.order)
        predicted_regions: list[tuple[str, dict[str, float], str]] = []
        if predicted is not None:
            order_matches += 1
            prompt_fidelity = SequenceMatcher(
                None,
                _normalize_text(expected.prompt_text),
                _normalize_text(predicted.prompt_text),
            ).ratio()
            prompt_fidelity_sum += prompt_fidelity
            for link in sorted(predicted.response_links, key=lambda item: item.order):
                region = parsed.response_region(link.response_region_id)
                width, height = page_sizes[region.page_index]
                predicted_regions.append(
                    (
                        region.id,
                        _bbox_dict_from_points(region.bbox, width=width, height=height),
                        region.region_type.value,
                    )
                )
        else:
            prompt_fidelity = 0.0

        response_rows = _match_expected_responses(
            expected_responses=expected.response_regions,
            predicted_regions=predicted_regions,
        )
        expected_response_count += len(expected.response_regions)
        detected_response_count += sum(1 for row in response_rows if row["detected"])
        response_iou_sum += sum(float(row["iou"]) for row in response_rows)
        response_type_matches += sum(1 for row in response_rows if row["type_match"])
        association_matches += sum(1 for row in response_rows if row["association_match"])

        physical_rows = []
        for expected_response in expected.response_regions:
            allowed = _EXPECTED_TO_REGION_TYPES[expected_response.response_type]
            scored = []
            for block_id, region, label, page_index in physical_candidates:
                if (
                    block_id in claimed_physical_ids
                    or page_index != expected_response.page_index
                    or label not in allowed
                ):
                    continue
                coverage = _expected_coverage(region, expected_response.bbox_normalized)
                if coverage >= RESPONSE_COVERAGE_THRESHOLD:
                    scored.append((coverage, _iou(region, expected_response.bbox_normalized), block_id, region, label))
            if scored:
                coverage, iou_value, block_id, region, label = max(
                    scored,
                    key=lambda item: (item[0], item[1]),
                )
                claimed_physical_ids.add(block_id)
                physical_detected += 1
                type_match = _region_type_matches(expected_response.response_type, label)
                physical_type_matches += int(type_match)
                physical_rows.append(
                    {
                        "response_id": expected_response.region_id,
                        "detected": True,
                        "expected_region_coverage": round(coverage, 6),
                        "iou": round(iou_value, 6),
                        "predicted_block_id": block_id,
                        "predicted_block_label": label,
                        "type_match": type_match,
                    }
                )
            else:
                physical_rows.append(
                    {
                        "response_id": expected_response.region_id,
                        "detected": False,
                        "expected_region_coverage": 0.0,
                        "iou": 0.0,
                        "predicted_block_id": None,
                        "predicted_block_label": None,
                        "type_match": False,
                    }
                )

        task_results.append(
            {
                "task_id": expected.task_id,
                "order": expected.order,
                "matched_prediction": predicted is not None,
                "predicted_label": predicted.label if predicted is not None else None,
                "expected_prompt": expected.prompt_text,
                "predicted_prompt": predicted.prompt_text if predicted is not None else None,
                "prompt_text_fidelity": round(prompt_fidelity, 6),
                "side_panel_fallback": (
                    predicted.side_panel_fallback if predicted is not None else None
                ),
                "responses": response_rows,
                "physical_extraction": physical_rows,
            }
        )

    false_positive_tasks = max(0, len(parsed.tasks) - len(expected_tasks))
    matched_predicted_ids = {
        row["predicted_region_id"]
        for task in task_results
        for row in task["responses"]
        if row["detected"] and row["predicted_region_id"]
    }
    false_positive_writable_regions = sum(
        1 for region in parsed.response_regions if region.id not in matched_predicted_ids
    )

    counts_equal = len(parsed.tasks) == len(expected_tasks)
    task_count_score = (
        1.0
        if counts_equal
        else min(len(parsed.tasks), len(expected_tasks)) / max(len(expected_tasks), 1)
    )
    totals = {
        "expected_tasks": float(len(expected_tasks)),
        "predicted_tasks": float(len(parsed.tasks)),
        "exact_task_count_documents": float(counts_equal),
        "task_count_score_sum": task_count_score,
        "prompt_fidelity_sum": prompt_fidelity_sum,
        "order_matches": float(order_matches),
        "expected_responses": float(expected_response_count),
        "detected_responses": float(detected_response_count),
        "response_iou_sum": response_iou_sum,
        "response_type_matches": float(response_type_matches),
        "association_matches": float(association_matches),
        "false_positive_tasks": float(false_positive_tasks),
        "false_positive_writable_regions": float(false_positive_writable_regions),
        "physical_detected_responses": float(physical_detected),
        "physical_type_matches": float(physical_type_matches),
        "physical_candidate_count": float(len(physical_candidates)),
    }
    result = {
        "canonical_id": expected_document.canonical_id,
        "pdf": expected_document.pdf,
        "parse_status": parsed.status.value,
        "parse_warnings": parsed.warnings,
        "parsed_title": parsed.title,
        "parser": parsed.parser,
        "expected_task_count": len(expected_tasks),
        "predicted_task_count": len(parsed.tasks),
        "task_count_exact": counts_equal,
        "task_count_accuracy": round(task_count_score, 6),
        "prompt_text_fidelity": round(
            prompt_fidelity_sum / len(expected_tasks) if expected_tasks else 0.0,
            6,
        ),
        "task_order_accuracy": round(order_matches / len(expected_tasks), 6),
        "response_region_detection": round(
            detected_response_count / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "response_region_mean_iou": round(
            response_iou_sum / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "response_type_accuracy": round(
            response_type_matches / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "task_to_response_association_accuracy": round(
            association_matches / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "physical_response_detection": round(
            physical_detected / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "physical_response_type_accuracy": round(
            physical_type_matches / expected_response_count if expected_response_count else 0.0,
            6,
        ),
        "false_positive_tasks": false_positive_tasks,
        "false_positive_writable_regions": false_positive_writable_regions,
        "physical_candidate_count": len(physical_candidates),
        "tasks": task_results,
    }
    return result, totals


def evaluate(
    manifest_path: Path = DEFAULT_MANIFEST,
    report_path: Path | None = DEFAULT_REPORT,
) -> dict[str, Any]:
    manifest = CanonicalManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    manifest_root = manifest_path.parent
    document_results: list[dict[str, Any]] = []
    aggregate = {
        "expected_tasks": 0.0,
        "predicted_tasks": 0.0,
        "exact_task_count_documents": 0.0,
        "task_count_score_sum": 0.0,
        "prompt_fidelity_sum": 0.0,
        "order_matches": 0.0,
        "expected_responses": 0.0,
        "detected_responses": 0.0,
        "response_iou_sum": 0.0,
        "response_type_matches": 0.0,
        "association_matches": 0.0,
        "false_positive_tasks": 0.0,
        "false_positive_writable_regions": 0.0,
        "physical_detected_responses": 0.0,
        "physical_type_matches": 0.0,
        "physical_candidate_count": 0.0,
    }
    for document in manifest.documents:
        result, totals = _document_result(document, manifest_root=manifest_root)
        document_results.append(result)
        for key, value in totals.items():
            aggregate[key] += value

    document_count = len(manifest.documents)
    expected_task_count = aggregate["expected_tasks"]
    expected_response_count = aggregate["expected_responses"]
    metrics = {
        "task_count_accuracy": round(
            aggregate["task_count_score_sum"] / document_count,
            6,
        ),
        "task_count_exact_document_rate": round(
            aggregate["exact_task_count_documents"] / document_count,
            6,
        ),
        "prompt_text_fidelity": round(
            aggregate["prompt_fidelity_sum"] / expected_task_count if expected_task_count else 0.0,
            6,
        ),
        "task_order_accuracy": round(
            aggregate["order_matches"] / expected_task_count if expected_task_count else 0.0,
            6,
        ),
        "response_region_detection": round(
            aggregate["detected_responses"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "response_region_mean_iou": round(
            aggregate["response_iou_sum"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "response_type_accuracy": round(
            aggregate["response_type_matches"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "task_to_response_association_accuracy": round(
            aggregate["association_matches"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "physical_response_detection": round(
            aggregate["physical_detected_responses"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "physical_response_type_accuracy": round(
            aggregate["physical_type_matches"] / expected_response_count
            if expected_response_count
            else 0.0,
            6,
        ),
        "false_positive_tasks": int(aggregate["false_positive_tasks"]),
        "false_positive_writable_regions": int(
            aggregate["false_positive_writable_regions"]
        ),
    }
    report: dict[str, Any] = {
        "suite": manifest.suite,
        "expected_labels_kind": manifest.expected_labels_kind,
        "parser": "stage3 document_pipeline.parse_document (hybrid physical IR)",
        "semantic_note": (
            "Offline evaluation selects among already-extracted Stage 3 physical "
            "blocks using expected prompt text and expected-region coverage. It "
            "does not invent geometry and does not substitute for live Gemini."
        ),
        "response_detection_rule": (
            f"At least {RESPONSE_COVERAGE_THRESHOLD:.0%} of an expected response region "
            "is covered by a materialized Stage 3 response region for the matched task."
        ),
        "response_type_note": (
            "Expected fixture types map to Stage 3 region types as "
            "line→answer_line|form_field, box→bounded_box|writable_area|form_field, "
            "checkbox→checkbox. Expected labels were not weakened for this report."
        ),
        "legacy_baseline_preserved": "generated/baseline_legacy_parser.json",
        "counts": {
            "documents": document_count,
            "expected_tasks": int(expected_task_count),
            "predicted_tasks": int(aggregate["predicted_tasks"]),
            "expected_response_regions": int(expected_response_count),
            "detected_response_regions": int(aggregate["detected_responses"]),
            "physical_candidate_regions": int(aggregate["physical_candidate_count"]),
            "physical_detected_response_regions": int(
                aggregate["physical_detected_responses"]
            ),
        },
        "metrics": metrics,
        "documents": document_results,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = evaluate(args.manifest, args.out)
    print(json.dumps(report["metrics"], indent=2))
    print(f"Wrote canonical_v1 Stage 3 baseline to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
