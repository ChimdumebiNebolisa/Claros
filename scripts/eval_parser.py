#!/usr/bin/env python3
"""Evaluate parser output against labeled worksheet fixtures (consent-safe synthetic PDFs)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parser import parse_pdf_with_diagnostics

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = ROOT / "tests" / "fixtures" / "parser"


def _load_labels(corpus: Path) -> list[tuple[Path, dict]]:
    labels_dir = corpus / "labels"
    if not labels_dir.exists():
        return []
    items = []
    for label_path in sorted(labels_dir.glob("*.json")):
        label = json.loads(label_path.read_text(encoding="utf-8"))
        pdf_path = corpus / label["pdf"]
        if not pdf_path.exists():
            raise FileNotFoundError(f"Missing PDF for label {label_path.name}: {pdf_path}")
        items.append((pdf_path, label))
    return items


def evaluate(corpus: Path) -> dict:
    results = []
    total_expected = 0
    matched = 0
    fallback_count = 0

    for pdf_path, label in _load_labels(corpus):
        title, questions, warnings, status = parse_pdf_with_diagnostics(pdf_path)
        if status != "ok":
            fallback_count += 1
        case = {
            "pdf": label["pdf"],
            "parse_status": status,
            "parse_warnings": warnings,
            "title": title,
            "question_ids": [q.id for q in questions],
        }
        for expected in label.get("questions", []):
            total_expected += 1
            found = next((q for q in questions if q.id == expected["id"]), None)
            ok = found is not None and expected["text_contains"].lower() in found.text.lower()
            if ok:
                matched += 1
            case.setdefault("checks", []).append(
                {"id": expected["id"], "passed": ok, "text_contains": expected["text_contains"]}
            )
        results.append(case)

    recall = (matched / total_expected) if total_expected else 1.0
    return {
        "corpus": str(corpus),
        "cases": len(results),
        "expected_questions": total_expected,
        "matched_questions": matched,
        "boundary_recall": recall,
        "fallback_rate": (fallback_count / len(results)) if results else 0.0,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Claros PDF parser against labeled corpus")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = evaluate(args.corpus)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote report to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
