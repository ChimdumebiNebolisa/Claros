"""Evaluate production acceptance decisions on first-party worksheet fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.canonical_v1.evaluate import _CanonicalEvidenceSelector
from evaluation.canonical_v1.schema import CanonicalManifest
from ocr_adapter import NullOCRAdapter
from worksheet_contract import UnsupportedWorksheetError
from document_pipeline import parse_supported_worksheet

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "evaluation" / "canonical_v1" / "generated" / "manifest.json"
DEFAULT_EXPECTATIONS = Path(__file__).with_name("expectations.json")
DEFAULT_REPORT = Path(__file__).with_name("generated") / "report.json"


def evaluate(
    manifest_path: Path = DEFAULT_MANIFEST,
    expectations_path: Path = DEFAULT_EXPECTATIONS,
    report_path: Path | None = DEFAULT_REPORT,
) -> dict[str, Any]:
    manifest = CanonicalManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    expectations = json.loads(expectations_path.read_text(encoding="utf-8"))
    expected_decisions: dict[str, str] = expectations["documents"]
    manifest_root = manifest_path.parent
    results: list[dict[str, Any]] = []

    for expected_document in manifest.documents:
        expected = expected_decisions[expected_document.canonical_id]
        pdf_bytes = (manifest_root / expected_document.pdf).read_bytes()
        try:
            document = parse_supported_worksheet(
                pdf_bytes,
                ocr_adapter=NullOCRAdapter(),
                semantic_classifier=_CanonicalEvidenceSelector(expected_document),
            )
            actual = "supported"
            classification = document.worksheet_classification
        except UnsupportedWorksheetError as exc:
            actual = "unsupported"
            classification = exc.classification

        results.append(
            {
                "canonical_id": expected_document.canonical_id,
                "expected_decision": expected,
                "actual_decision": actual,
                "decision_matches": actual == expected,
                "reason_codes": classification.reason_codes,
                "question_count": classification.question_count,
                "semantic_provider_calls": classification.semantic_provider_calls,
            }
        )

    missing = sorted(set(expected_decisions) - {item.canonical_id for item in manifest.documents})
    if missing:
        raise ValueError(f"expectations reference missing canonical documents: {missing}")
    supported = [item for item in results if item["expected_decision"] == "supported"]
    unsupported = [item for item in results if item["expected_decision"] == "unsupported"]
    matches = sum(item["decision_matches"] for item in results)
    unsafe_acceptances = sum(
        item["expected_decision"] == "unsupported" and item["actual_decision"] == "supported" for item in results
    )
    report = {
        "report_schema_version": "worksheet-contract-evaluation-v1",
        "suite": expectations["suite"],
        "contract": "sequential-short-answer-v1",
        "counts": {
            "documents": len(results),
            "expected_supported": len(supported),
            "expected_unsupported": len(unsupported),
            "unsafe_acceptances": unsafe_acceptances,
        },
        "metrics": {
            "decision_agreement": round(matches / len(results), 6),
            "supported_acceptance": round(
                sum(item["actual_decision"] == "supported" for item in supported) / len(supported),
                6,
            ),
            "unsupported_rejection": round(
                sum(item["actual_decision"] == "unsupported" for item in unsupported) / len(unsupported),
                6,
            ),
        },
        "documents": results,
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
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = evaluate(args.manifest, args.expectations, args.out)
    print(json.dumps(report["metrics"], indent=2))
    print(f"Wrote worksheet contract evaluation to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
