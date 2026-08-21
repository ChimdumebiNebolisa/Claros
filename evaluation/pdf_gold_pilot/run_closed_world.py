#!/usr/bin/env python3
"""Gold-gated runner for the isolated closed-world Gemini experiment."""

from __future__ import annotations

import argparse
import json
import os
import time
import tracemalloc
from pathlib import Path

from .closed_world import ClosedWorldGeminiClassifier, PilotPageInput, derive_tasks

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "output" / "pdf-gold-pilot"


def _load_pages(path: Path) -> list[PilotPageInput]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [PilotPageInput.model_validate(page) for page in payload.get("pages") or []]


def _rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def _reference_set_exists(path: Path | None) -> bool:
    if path is None or not path.is_file() or path.stat().st_size == 0:
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    return bool(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=DEFAULT_OUTPUT / "physical-inputs.json")
    parser.add_argument("--image-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT / "closed-world-predictions.json")
    parser.add_argument("--reference-set", type=Path)
    parser.add_argument("--model")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    pages = _load_pages(args.inputs)
    if not pages:
        raise ValueError("physical input file contains no pilot pages")
    incomplete = [page.pilot_id for page in pages if not page.blocks]
    if args.validate_only:
        print(
            f"Validated {len(pages)} closed-world page inputs; pages_without_blocks={len(incomplete)}; "
            "Gemini was not called.",
            flush=True,
        )
        return 0
    if not args.execute:
        raise RuntimeError(
            "use --validate-only, or explicitly pass --execute after an approved adjudicated reference set exists"
        )
    if os.environ.get("CLAROS_PDF_GOLD_PILOT", "").strip().lower() not in {"1", "true", "yes"}:
        raise RuntimeError("set CLAROS_PDF_GOLD_PILOT=1 for this isolated experiment")
    if not _reference_set_exists(args.reference_set):
        raise RuntimeError(
            "a non-empty approved Label Studio adjudicated reference export is required before Gemini execution"
        )
    if incomplete:
        raise RuntimeError("structured physical blocks are missing for selected pages: " + ", ".join(incomplete))

    classifier = ClosedWorldGeminiClassifier(model=args.model)
    records = []
    for page in pages:
        image_path = args.image_root / page.image
        if not image_path.is_file():
            raise FileNotFoundError(f"rendered pilot page is missing: {image_path}")
        started = time.perf_counter()
        rss_before = _rss_mb()
        tracemalloc.start()
        result = classifier.classify_page(page, image_path.read_bytes())
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rss_after = _rss_mb()
        records.append(
            {
                "pilot_id": page.pilot_id,
                "result": result.model_dump(mode="json"),
                "derived_tasks": derive_tasks(page, result),
                "processing_ms": round((time.perf_counter() - started) * 1000, 2),
                "python_peak_alloc_mb": round(peak / (1024 * 1024), 2),
                "process_rss_delta_mb": (
                    round(rss_after - rss_before, 2) if rss_before is not None and rss_after is not None else None
                ),
            }
        )
        print(f"Classified {page.pilot_id}; raw educational content was not logged.", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "version": 1,
                "experiment": "closed_world_gemini",
                "production_write_authorized": False,
                "pages": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
