#!/usr/bin/env python3
"""Merge current, physical Paddle, and semantic benchmark stages without raw document text."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(report: dict) -> dict[str, dict]:
    return {row["filename"]: row for row in report["results"]}


def merge(
    current: dict,
    paddle: dict,
    semantic: dict,
    paddle_overrides: list[dict],
    semantic_overrides: list[dict],
) -> dict:
    current_rows = _rows(current)
    paddle_rows = _rows(paddle)
    semantic_rows = _rows(semantic)
    for override in paddle_overrides:
        paddle_rows.update(_rows(override))
    for override in semantic_overrides:
        semantic_rows.update(_rows(override))
    if set(current_rows) != set(paddle_rows) or set(current_rows) != set(semantic_rows):
        raise ValueError("Benchmark stages do not cover the same corpus filenames")

    results = []
    for filename in current_rows:
        baseline = current_rows[filename]
        physical = paddle_rows[filename]
        meaning = semantic_rows[filename]
        results.append(
            {
                "filename": filename,
                "page_count": baseline["page_count"],
                "native_text_exists": baseline["native_text_exists"],
                "native_text_pages": baseline["native_text_pages"],
                "ocr_required": baseline["ocr_required"],
                "expected_question_count": baseline["expected_question_count"],
                "current_parser_question_count": baseline["current_parser_question_count"],
                "paddle_question_or_block_count": physical["paddle_question_or_block_count"],
                "final_claros_task_count": meaning["final_claros_task_count"],
                "missing_questions": meaning["missing_questions"],
                "merged_questions": meaning["merged_questions"],
                "false_positive_questions": meaning["false_positive_questions"],
                "count_delta_from_expected": meaning["count_delta_from_expected"],
                "page_role_classification": meaning["page_role_classification"],
                "answer_region_status": meaning["answer_region_status"],
                "warnings": list(dict.fromkeys(baseline["warnings"] + physical["warnings"] + meaning["warnings"])),
                "current_processing_ms": baseline["current_processing_ms"],
                "paddle_processing_ms": physical["hybrid_processing_ms"],
                "semantic_processing_ms": meaning["hybrid_processing_ms"],
                "paddle_python_peak_alloc_mb": physical["python_peak_alloc_mb"],
                "paddle_process_rss_delta_mb": physical["process_rss_delta_mb"],
                "current_parse_status": baseline["current_parse_status"],
                "paddle_parse_status": physical["parse_status"],
                "parse_status": meaning["parse_status"],
                "paddle_overlay_paths": physical["overlay_paths"],
                "semantic_overlay_paths": meaning["overlay_paths"],
            }
        )
    return {
        "corpus": current["corpus"],
        "pdf_count": len(results),
        "stage_note": (
            "Paddle physical extraction and Gemini semantic classification were measured as separate stages. "
            "Missing/merged/false-positive values require task-level gold annotations or visual review."
        ),
        "results": results,
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                    for key, value in row.items()
                }
            )


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Claros staged PDF parser comparison",
        "",
        f"- Corpus: `{report['corpus']}`",
        f"- PDFs: {report['pdf_count']}",
        f"- {report['stage_note']}",
        "",
        "| PDF | Pages | Native pages | OCR needed | Expected | Current | Paddle blocks | Final tasks | Answer status | Current ms | Paddle ms | Semantic ms | Status |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in report["results"]:
        expected = row["expected_question_count"] if row["expected_question_count"] is not None else "—"
        lines.append(
            f"| {row['filename']} | {row['page_count']} | {row['native_text_pages']} | "
            f"{row['ocr_required']} | {expected} | {row['current_parser_question_count']} | "
            f"{row['paddle_question_or_block_count']} | {row['final_claros_task_count']} | "
            f"{json.dumps(row['answer_region_status'])} | {row['current_processing_ms']} | "
            f"{row['paddle_processing_ms']} | {row['semantic_processing_ms']} | {row['parse_status']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--paddle", type=Path, required=True)
    parser.add_argument("--semantic", type=Path, required=True)
    parser.add_argument("--paddle-override", type=Path, action="append", default=[])
    parser.add_argument("--semantic-override", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = merge(
        _load(args.current),
        _load(args.paddle),
        _load(args.semantic),
        [_load(path) for path in args.paddle_override],
        [_load(path) for path in args.semantic_override],
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_csv(args.out / "comparison.csv", report["results"])
    _write_markdown(args.out / "comparison.md", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
