"""Evaluate the narrow production boundary on deterministic first-party PDFs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from document_pipeline import parse_supported_worksheet
from ocr_adapter import NullOCRAdapter
from worksheet_contract import UnsupportedWorksheetError

from .fixtures import (
    FIXTURES,
    FixtureEvidenceSelector,
    FixtureSpec,
    fixture_manifest,
    generate_fixture_pdf,
)


DEFAULT_EXPECTATIONS = Path(__file__).with_name("expectations.json")
DEFAULT_GENERATED = Path(__file__).with_name("generated")
DEFAULT_MANIFEST = DEFAULT_GENERATED / "manifest.json"
DEFAULT_REPORT = DEFAULT_GENERATED / "report.json"


def _ratio(numerator: int, denominator: int) -> dict[str, int | float]:
    return {
        "value": round(numerator / denominator, 6) if denominator else 0.0,
        "numerator": numerator,
        "denominator": denominator,
    }


def _intersects(first: list[float], second: tuple[float, float, float, float]) -> bool:
    return max(first[0], second[0]) <= min(first[2], second[2]) and max(first[1], second[1]) <= min(
        first[3], second[3]
    )


def _supported_geometry_result(fixture: FixtureSpec, document) -> dict[str, Any]:
    expected_questions = sorted(fixture.questions, key=lambda item: (item.page_index, int(item.label)))
    actual_tasks = sorted(document.tasks, key=lambda item: item.order)
    expected_labels = [question.label for question in expected_questions]
    actual_labels = [task.label for task in actual_tasks]
    task_by_label = {task.label: task for task in actual_tasks}
    region_detection_matches = 0
    association_matches = 0
    response_type_matches = 0
    task_rows: list[dict[str, Any]] = []

    for question in expected_questions:
        task = task_by_label.get(question.label)
        regions = []
        if task is not None:
            regions = [document.response_region(link.response_region_id) for link in task.response_links]
        detected = bool(regions)
        region_detection_matches += int(detected)
        expected_page = question.response_page_index
        if expected_page is None:
            expected_page = question.page_index
        associated = bool(question.response_bbox) and bool(regions) and all(
            region.page_index == expected_page and _intersects(region.bbox, question.response_bbox)
            for region in regions
        )
        association_matches += int(associated)
        type_match = task is not None and task.response_type.value == question.response_type
        response_type_matches += int(type_match)
        task_rows.append(
            {
                "label": question.label,
                "region_detected": detected,
                "association_matches": associated,
                "response_type_matches": type_match,
                "response_region_count": len(regions),
            }
        )

    expected_count = len(expected_questions)
    return {
        "expected_question_count": expected_count,
        "actual_question_count": len(actual_tasks),
        "question_count_matches": len(actual_tasks) == expected_count,
        "question_order_matches": actual_labels == expected_labels,
        "region_detection_matches": region_detection_matches,
        "association_matches": association_matches,
        "response_type_matches": response_type_matches,
        "eligible_response_tasks": expected_count,
        "tasks": task_rows,
    }


def evaluate(
    expectations_path: Path = DEFAULT_EXPECTATIONS,
    report_path: Path | None = DEFAULT_REPORT,
    manifest_path: Path | None = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    expectations = json.loads(expectations_path.read_text(encoding="utf-8"))
    expected_decisions: dict[str, str] = expectations["documents"]
    fixture_ids = {fixture.fixture_id for fixture in FIXTURES}
    if set(expected_decisions) != fixture_ids:
        missing = sorted(set(expected_decisions) - fixture_ids)
        unexpected = sorted(fixture_ids - set(expected_decisions))
        raise ValueError(f"fixture/expectation mismatch: missing={missing}, unexpected={unexpected}")

    results: list[dict[str, Any]] = []
    rejection_reasons: Counter[str] = Counter()
    supported_question_documents = 0
    supported_question_count_matches = 0
    supported_question_order_matches = 0
    eligible_response_tasks = 0
    response_region_matches = 0
    association_matches = 0
    response_type_matches = 0

    for fixture in FIXTURES:
        expected = expected_decisions[fixture.fixture_id]
        document = None
        try:
            document = parse_supported_worksheet(
                generate_fixture_pdf(fixture),
                ocr_adapter=NullOCRAdapter(),
                semantic_classifier=FixtureEvidenceSelector(fixture),
            )
            actual = "supported"
            classification = document.worksheet_classification
        except UnsupportedWorksheetError as exc:
            actual = "unsupported"
            classification = exc.classification

        assert classification is not None
        decision_matches = actual == expected
        rejection_reasons.update(classification.reason_codes)
        if decision_matches and actual == "supported":
            disposition = "contract_behavior_confirmed"
        elif decision_matches:
            disposition = "correct_unsupported_rejection"
        elif expected == "supported":
            disposition = "supported_fixture_rejection_requires_review"
        else:
            disposition = "unsafe_acceptance_requires_review"

        geometry = None
        if expected == "supported":
            supported_question_documents += 1
            if document is not None:
                geometry = _supported_geometry_result(fixture, document)
                supported_question_count_matches += int(geometry["question_count_matches"])
                supported_question_order_matches += int(geometry["question_order_matches"])
                eligible_response_tasks += geometry["eligible_response_tasks"]
                response_region_matches += geometry["region_detection_matches"]
                association_matches += geometry["association_matches"]
                response_type_matches += geometry["response_type_matches"]
            else:
                eligible_response_tasks += len(fixture.questions)

        results.append(
            {
                "fixture_id": fixture.fixture_id,
                "tags": list(fixture.tags),
                "expected_decision": expected,
                "actual_decision": actual,
                "classification_status": classification.status.value,
                "decision_matches": decision_matches,
                "review_disposition": disposition,
                "reason_codes": classification.reason_codes,
                "question_count": classification.question_count,
                "semantic_provider_calls": classification.semantic_provider_calls,
                "geometry": geometry,
            }
        )

    results.sort(key=lambda item: item["fixture_id"])
    supported = [item for item in results if item["expected_decision"] == "supported"]
    unsupported = [item for item in results if item["expected_decision"] == "unsupported"]
    decision_matches = sum(item["decision_matches"] for item in results)
    supported_acceptances = sum(item["actual_decision"] == "supported" for item in supported)
    unsupported_rejections = sum(item["actual_decision"] == "unsupported" for item in unsupported)
    unsafe_acceptances = len(unsupported) - unsupported_rejections
    supported_rejections = len(supported) - supported_acceptances
    disagreements = [
        {
            "fixture_id": item["fixture_id"],
            "expected_decision": item["expected_decision"],
            "actual_decision": item["actual_decision"],
            "review_disposition": item["review_disposition"],
            "reason_codes": item["reason_codes"],
        }
        for item in results
        if not item["decision_matches"]
    ]

    report = {
        "report_schema_version": "worksheet-contract-evaluation-v2",
        "suite": expectations["suite"],
        "contract": "sequential-short-answer-v1",
        "label_policy": expectations["label_policy"],
        "counts": {
            "documents": len(results),
            "expected_supported": len(supported),
            "expected_unsupported": len(unsupported),
            "supported_rejections": supported_rejections,
            "unsafe_acceptances": unsafe_acceptances,
        },
        "metrics": {
            "decision_agreement": _ratio(decision_matches, len(results)),
            "supported_document_acceptance": _ratio(supported_acceptances, len(supported)),
            "unsupported_document_rejection": _ratio(unsupported_rejections, len(unsupported)),
            "question_count_agreement": _ratio(
                supported_question_count_matches, supported_question_documents
            ),
            "question_order_agreement": _ratio(
                supported_question_order_matches, supported_question_documents
            ),
            "response_region_detection_agreement": _ratio(
                response_region_matches, eligible_response_tasks
            ),
            "question_to_response_association_agreement": _ratio(
                association_matches, eligible_response_tasks
            ),
            "response_type_agreement": _ratio(response_type_matches, eligible_response_tasks),
        },
        "rejection_reason_counts": dict(sorted(rejection_reasons.items())),
        "disagreements": disagreements,
        "documents": results,
    }

    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(fixture_manifest(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = evaluate(args.expectations, args.out, args.manifest_out)
    print(json.dumps(report["metrics"], indent=2))
    print(f"Unsafe acceptances: {report['counts']['unsafe_acceptances']}")
    print(f"Supported rejections: {report['counts']['supported_rejections']}")
    print(f"Wrote worksheet contract evaluation to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
