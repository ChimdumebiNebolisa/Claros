#!/usr/bin/env python3
"""Compare Claros's current parser with the flagged hybrid PP-StructureV3 path."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from document_model import ReviewStatus, SourceKind
from document_pipeline import parse_document
from ocr_adapter import NullOCRAdapter, PaddleOCRAdapter
from parser import parse_pdf_with_diagnostics
from semantic_classifier import GeminiSemanticClassifier, NullSemanticClassifier

DEFAULT_EXPECTATIONS = ROOT / "tests" / "fixtures" / "pdf_acceptance_expectations.json"


def _native_page_flags(path: Path) -> list[bool]:
    document = fitz.open(path)
    try:
        return [len(page.get_text().strip()) >= 12 for page in document]
    finally:
        document.close()


def _draw_normalized(page, region, color):
    if not region:
        return
    rect = fitz.Rect(
        region["x"] * page.rect.width,
        region["y"] * page.rect.height,
        (region["x"] + region["width"]) * page.rect.width,
        (region["y"] + region["height"]) * page.rect.height,
    )
    page.draw_rect(rect, color=color, width=1.4, overlay=True)


def _render_overlays(path: Path, output_dir: Path, current_questions, parsed) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = fitz.open(path)
    try:
        blocks_by_page = {}
        for block in parsed.blocks:
            blocks_by_page.setdefault(block.page_index, []).append(block)
        tasks_by_page = {}
        for task in parsed.tasks:
            tasks_by_page.setdefault(task.page_index, []).append(task)
        current_by_page = {}
        for question in current_questions:
            current_by_page.setdefault(question.page - 1, []).append(question)
        paths = []
        for page_index, page in enumerate(source):
            for block in blocks_by_page.get(page_index, []):
                color = (0.45, 0.45, 0.45)
                if block.source == SourceKind.paddleocr:
                    color = (0.45, 0.15, 0.75)
                elif block.block_label in {"answer_line", "form_field"}:
                    color = (0.0, 0.55, 0.2)
                page.draw_rect(fitz.Rect(block.bbox), color=color, width=0.55, overlay=True)
            for question in current_by_page.get(page_index, []):
                _draw_normalized(page, question.prompt_region, (0.85, 0.0, 0.65))
            for task in tasks_by_page.get(page_index, []):
                if task.prompt_bbox:
                    page.draw_rect(fitz.Rect(task.prompt_bbox), color=(0.9, 0.05, 0.05), width=1.8, overlay=True)
                if task.answer_bbox:
                    page.draw_rect(fitz.Rect(task.answer_bbox), color=(0.0, 0.25, 0.95), width=1.8, overlay=True)
                if task.review_status == ReviewStatus.needs_review and task.prompt_bbox:
                    page.draw_rect(fitz.Rect(task.prompt_bbox), color=(1.0, 0.55, 0.0), width=3.0, overlay=True)
            role = parsed.pages[page_index].page_role.value
            page.draw_rect(fitz.Rect(0, 0, min(290, page.rect.width), 22), fill=(1, 1, 1), color=None, overlay=True)
            page.insert_text((5, 15), f"role={role}", fontsize=9, color=(0.1, 0.1, 0.1), overlay=True)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            output_path = output_dir / f"page-{page_index + 1:02d}-overlay.png"
            pixmap.save(output_path)
            paths.append(str(output_path.resolve()))
        return paths
    finally:
        source.close()


def _load_expectations(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _process_rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def benchmark(args) -> dict:
    corpus_dir = args.corpus / "corpus" if (args.corpus / "corpus").is_dir() else args.corpus
    pdfs = sorted(corpus_dir.glob("*.pdf"))
    if args.include:
        requested = set(args.include)
        pdfs = [path for path in pdfs if path.name in requested]
        missing = sorted(requested - {path.name for path in pdfs})
        if missing:
            raise FileNotFoundError(f"Requested corpus PDFs were not found: {', '.join(missing)}")
    if args.limit:
        pdfs = pdfs[: args.limit]
    expectations = _load_expectations(args.expectations)
    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ocr_adapter = PaddleOCRAdapter(dpi=args.dpi) if args.paddle else NullOCRAdapter()
    semantic_classifier = GeminiSemanticClassifier() if args.semantic else NullSemanticClassifier()
    rows = []
    total_started = time.perf_counter()

    for path in pdfs:
        native_flags = _native_page_flags(path)
        current_started = time.perf_counter()
        _title, current_questions, current_warnings, current_status = parse_pdf_with_diagnostics(path)
        current_ms = (time.perf_counter() - current_started) * 1000
        tracemalloc.start()
        rss_before = _process_rss_mb()
        parsed = parse_document(
            path.read_bytes(),
            ocr_adapter=ocr_adapter,
            semantic_classifier=semantic_classifier,
            review_mode="direct",
            paddle_all_pages=args.paddle_all_pages,
        )
        _current_alloc, peak_alloc = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rss_after = _process_rss_mb()
        expected = expectations.get(path.name, {}).get("expected_question_count")
        answer_status = Counter(task.answer_region_status.value for task in parsed.tasks)
        roles = [page.page_role.value for page in parsed.pages]
        overlay_paths = _render_overlays(path, output_dir / path.stem, current_questions, parsed)
        row = {
            "filename": path.name,
            "page_count": len(native_flags),
            "native_text_exists": any(native_flags),
            "native_text_pages": sum(native_flags),
            "ocr_required": any(not flag for flag in native_flags),
            "expected_question_count": expected,
            "current_parser_question_count": len(current_questions),
            "paddle_question_or_block_count": sum(page.paddle_block_count for page in parsed.pages),
            "final_claros_task_count": len(parsed.tasks),
            "missing_questions": "manual_review_required",
            "merged_questions": "manual_review_required",
            "false_positive_questions": "manual_review_required",
            "count_delta_from_expected": None if expected is None else len(parsed.tasks) - expected,
            "page_role_classification": roles,
            "answer_region_status": dict(answer_status),
            "task_summaries": [
                {
                    "id": task.id,
                    "label": task.label,
                    "page_index": task.page_index,
                    "confidence": round(task.confidence, 3),
                    "review_status": task.review_status.value,
                    "answer_region_status": task.answer_region_status.value,
                    "source_blocks": task.source_blocks,
                }
                for task in parsed.tasks
            ],
            "paddle_blocks_by_page": [page.paddle_block_count for page in parsed.pages],
            "warnings": list(dict.fromkeys(current_warnings + parsed.warnings)),
            "current_processing_ms": round(current_ms, 2),
            "hybrid_processing_ms": round(parsed.processing_ms, 2),
            "python_peak_alloc_mb": round(peak_alloc / (1024 * 1024), 2),
            "process_rss_delta_mb": (
                round(rss_after - rss_before, 2)
                if rss_before is not None and rss_after is not None
                else None
            ),
            "current_parse_status": current_status,
            "parse_status": parsed.status.value,
            "overlay_paths": overlay_paths,
        }
        rows.append(row)
        print(
            f"{path.name}: current={len(current_questions)} blocks={row['paddle_question_or_block_count']} "
            f"final={len(parsed.tasks)} status={parsed.status.value} {parsed.processing_ms:.0f}ms",
            flush=True,
        )

    report = {
        "corpus": str(args.corpus.resolve()),
        "paddle_enabled": args.paddle,
        "semantic_enabled": args.semantic,
        "paddle_all_pages": args.paddle_all_pages,
        "pdf_count": len(rows),
        "total_processing_ms": round((time.perf_counter() - total_started) * 1000, 2),
        "manual_scoring_note": (
            "Missing, merged, and false-positive tasks require fixed gold task annotations or visual review; "
            "the tool does not mislabel count deltas as precision/recall."
        ),
        "results": rows,
    }
    (output_dir / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_csv(output_dir / "benchmark.csv", rows)
    _write_markdown(output_dir / "benchmark.md", report)
    return report


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                    for key, value in row.items()
                }
            )


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Claros PDF parser comparison",
        "",
        f"- Corpus: `{report['corpus']}`",
        f"- PaddleOCR enabled: `{report['paddle_enabled']}`",
        f"- Gemini semantics enabled: `{report['semantic_enabled']}`",
        f"- PDFs: {report['pdf_count']}",
        "- Overlay legend: gray=native/physical blocks, purple=Paddle blocks, green=explicit physical response evidence, magenta=current-parser prompts, red=final prompts, blue=final answer regions, orange=review required.",
        "",
        "| PDF | Pages | Native | OCR | Expected | Current | Paddle blocks | Final tasks | Roles | Answer status | Time ms | Status | Overlays |",
        "|---|---:|---|---|---:|---:|---:|---:|---|---|---:|---|---|",
    ]
    for row in report["results"]:
        overlay = row["overlay_paths"][0] if row["overlay_paths"] else ""
        lines.append(
            "| {filename} | {page_count} | {native_text_pages} | {ocr_required} | {expected} | "
            "{current_parser_question_count} | {paddle_question_or_block_count} | {final_claros_task_count} | "
            "{roles} | {answers} | {hybrid_processing_ms} | {parse_status} | `{overlay}` |".format(
                expected=row["expected_question_count"] if row["expected_question_count"] is not None else "—",
                roles=", ".join(row["page_role_classification"]),
                answers=json.dumps(row["answer_region_status"]),
                overlay=overlay,
                **row,
            )
        )
    lines.extend(["", f"> {report['manual_scoring_note']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "output" / "pdf-benchmark")
    parser.add_argument("--expectations", type=Path, default=DEFAULT_EXPECTATIONS)
    parser.add_argument("--paddle", action="store_true")
    parser.add_argument("--paddle-all-pages", action="store_true")
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--include",
        action="append",
        help="Exact corpus filename to include; repeat for multiple PDFs.",
    )
    args = parser.parse_args()
    benchmark(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
